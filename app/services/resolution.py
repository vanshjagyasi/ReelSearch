"""Entity resolution service.

Implements a 3-step cascade to deduplicate extracted entities against the
existing entity directory (scoped per user):

  1. Exact match   — normalized_name + type + user_id
  2. Fuzzy match   — pg_trgm similarity() > 0.3, same type + user_id
  3. LLM judge     — batch ambiguous pairs into one GPT-4o call

After resolution, entities, post_entities, and entity_relations rows are
created or updated.
"""

import json
import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entity import Entity
from app.models.entity_relation import EntityRelation
from app.models.post_entity import PostEntity

logger = logging.getLogger(__name__)


def normalize_entity_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse internal spaces."""
    return " ".join(name.lower().strip().split())


# ---------------------------------------------------------------------------
# Step 1: Exact match
# ---------------------------------------------------------------------------

async def _exact_match(
    session: AsyncSession, normalized_name: str, entity_type: str, user_id: uuid.UUID,
) -> Entity | None:
    result = await session.execute(
        select(Entity).where(
            Entity.normalized_name == normalized_name,
            Entity.type == entity_type,
            Entity.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Step 2: Fuzzy match via pg_trgm
# ---------------------------------------------------------------------------

async def _fuzzy_candidates(
    session: AsyncSession, normalized_name: str, entity_type: str,
    user_id: uuid.UUID, threshold: float = 0.3, limit: int = 5,
) -> list[dict]:
    """Return candidate entities with similarity score above threshold."""
    query = text("""
        SELECT id, name, normalized_name, type, attributes,
               similarity(normalized_name, :search_name) AS sim
        FROM entities
        WHERE type = :entity_type
          AND user_id = :user_id
          AND similarity(normalized_name, :search_name) > :threshold
        ORDER BY sim DESC
        LIMIT :limit
    """)
    result = await session.execute(query, {
        "search_name": normalized_name,
        "entity_type": entity_type,
        "user_id": user_id,
        "threshold": threshold,
        "limit": limit,
    })
    rows = result.mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Step 3: LLM judge (batched)
# ---------------------------------------------------------------------------

async def _llm_resolve_batch(
    ambiguous_pairs: list[dict],
) -> list[dict]:
    """Ask GPT-4o to judge a batch of ambiguous entity pairs."""
    if not ambiguous_pairs or not settings.OPENAI_API_KEY:
        return [
            {"new_entity": p["new_entity"]["name"], "matched_existing_id": None, "confidence": 0.0}
            for p in ambiguous_pairs
        ]

    from langchain_openai import ChatOpenAI
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    from app.prompts.resolution import RESOLUTION_SYSTEM_PROMPT, RESOLUTION_USER_PROMPT

    pair_descriptions: list[str] = []
    for i, pair in enumerate(ambiguous_pairs, 1):
        new = pair["new_entity"]
        candidates_str = "\n".join(
            f"    - id={c['id']}  name=\"{c['name']}\"  type={c['type']}  similarity={c['sim']:.2f}"
            for c in pair["candidates"]
        )
        pair_descriptions.append(
            f"Item {i}:\n"
            f"  NEW: name=\"{new['name']}\"  type={new['type']}\n"
            f"  EXISTING CANDIDATES:\n{candidates_str}"
        )

    entity_pairs_text = "\n\n".join(pair_descriptions)

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0,
        api_key=settings.OPENAI_API_KEY, max_tokens=2000,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", RESOLUTION_SYSTEM_PROMPT),
        ("human", RESOLUTION_USER_PROMPT),
    ])
    chain = prompt | llm | JsonOutputParser()

    try:
        response = await chain.ainvoke({"entity_pairs": entity_pairs_text})
        return response.get("results", [])
    except Exception:
        logger.exception("LLM entity resolution failed")
        return [
            {"new_entity": p["new_entity"]["name"], "matched_existing_id": None, "confidence": 0.0}
            for p in ambiguous_pairs
        ]


# ---------------------------------------------------------------------------
# Orchestrator: resolve one extracted entity
# ---------------------------------------------------------------------------

async def _resolve_single_entity(
    session: AsyncSession,
    extracted: dict,
    user_id: uuid.UUID,
    ambiguous_batch: list[dict],
) -> Entity | None:
    """Try exact then fuzzy match for a single entity.

    If fuzzy gives candidates but no certain match, append to *ambiguous_batch*
    for later LLM resolution. Returns the matched Entity or None (pending LLM).
    """
    name = extracted.get("name", "").strip()
    entity_type = extracted.get("type", "other").strip()
    if not name:
        return None

    normalized = normalize_entity_name(name)

    # Step 1: exact
    match = await _exact_match(session, normalized, entity_type, user_id)
    if match:
        logger.debug("Exact match for '%s' → entity %s", name, match.id)
        return match

    # Step 2: fuzzy
    candidates = await _fuzzy_candidates(session, normalized, entity_type, user_id)

    if not candidates:
        return None

    top = candidates[0]
    if top["sim"] >= 0.85:
        logger.debug("High-similarity match for '%s' → '%s' (%.2f)", name, top["name"], top["sim"])
        entity = await session.get(Entity, top["id"])
        return entity

    ambiguous_batch.append({
        "new_entity": {"name": name, "type": entity_type},
        "candidates": candidates,
    })
    return None


# ---------------------------------------------------------------------------
# Public API: resolve all entities for a post
# ---------------------------------------------------------------------------

async def resolve_and_persist_entities(
    session: AsyncSession,
    post_id: uuid.UUID,
    extracted_entities: list[dict],
    extracted_relationships: list[dict],
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Resolve extracted entities and persist them + relationships.

    Returns list of entity IDs linked to this post.
    """
    if not extracted_entities:
        return []

    # --- Phase A: resolve each entity ---
    resolved: dict[str, Entity] = {}
    ambiguous_batch: list[dict] = []
    pending_creates: dict[str, dict] = {}

    for ext in extracted_entities:
        name = ext.get("name", "").strip()
        if not name:
            continue

        match = await _resolve_single_entity(session, ext, user_id, ambiguous_batch)
        if match:
            resolved[name] = match
        else:
            pending_creates[name] = ext

    # --- Phase B: LLM resolution for ambiguous entities ---
    if ambiguous_batch:
        logger.info("Sending %d ambiguous entities to LLM for resolution", len(ambiguous_batch))
        llm_results = await _llm_resolve_batch(ambiguous_batch)

        for result in llm_results:
            entity_name = result.get("new_entity", "")
            matched_id = result.get("matched_existing_id")
            confidence = result.get("confidence", 0.0)

            if matched_id and confidence >= 0.7:
                try:
                    existing = await session.get(Entity, uuid.UUID(str(matched_id)))
                    if existing:
                        resolved[entity_name] = existing
                        pending_creates.pop(entity_name, None)
                        logger.info("LLM matched '%s' → '%s' (%.0f%%)", entity_name, existing.name, confidence * 100)
                        continue
                except (ValueError, Exception):
                    pass

            if entity_name not in pending_creates:
                for ext in extracted_entities:
                    if ext.get("name", "").strip() == entity_name:
                        pending_creates[entity_name] = ext
                        break

    # --- Phase C: create new entities for unresolved ---
    for name, ext in pending_creates.items():
        normalized = normalize_entity_name(name)
        entity_type = ext.get("type", "other")
        attributes = ext.get("attributes", {})

        new_entity = Entity(
            name=name,
            normalized_name=normalized,
            type=entity_type,
            attributes=attributes or {},
            mention_count=1,
            user_id=user_id,
        )
        session.add(new_entity)
        await session.flush()
        resolved[name] = new_entity
        logger.info("Created new entity '%s' (type=%s, id=%s)", name, entity_type, new_entity.id)

    # --- Phase D: update mention counts for matched (not newly created) ---
    for name, entity in resolved.items():
        if name not in pending_creates:
            entity.mention_count = (entity.mention_count or 0) + 1
            ext = next((e for e in extracted_entities if e.get("name", "").strip() == name), None)
            if ext and ext.get("attributes"):
                merged = {**(entity.attributes or {}), **ext["attributes"]}
                entity.attributes = merged

    # --- Phase E: create post_entity links ---
    entity_ids = []
    for name, entity in resolved.items():
        entity_ids.append(entity.id)

        ext = next((e for e in extracted_entities if e.get("name", "").strip() == name), None)
        relationship = "mentions"
        context = None
        if ext:
            relationship = ext.get("relationship", "mentions") or "mentions"
            context = ext.get("context")

        stmt = pg_insert(PostEntity).values(
            post_id=post_id,
            entity_id=entity.id,
            relationship=relationship,
            context=context,
        ).on_conflict_do_nothing(constraint="uq_post_entity")
        await session.execute(stmt)

    # --- Phase F: create/update entity_relations ---
    for rel in extracted_relationships:
        entity_a_name = rel.get("entity_a", "").strip()
        entity_b_name = rel.get("entity_b", "").strip()
        relation_type = rel.get("relation", "pairs_with")

        entity_a = resolved.get(entity_a_name)
        entity_b = resolved.get(entity_b_name)
        if not entity_a or not entity_b:
            continue

        stmt = pg_insert(EntityRelation).values(
            entity_a_id=entity_a.id,
            entity_b_id=entity_b.id,
            relation_type=relation_type,
        ).on_conflict_do_update(
            constraint="uq_entity_relation",
            set_={"strength": EntityRelation.strength + 1},
        )
        await session.execute(stmt)

    await session.commit()
    logger.info("Resolved %d entities for post %s (%d new, %d existing)",
                len(resolved), post_id, len(pending_creates),
                len(resolved) - len(pending_creates))

    return entity_ids
