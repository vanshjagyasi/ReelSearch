"""Hybrid search engine.

Combines three search tiers and merges results via Reciprocal Rank Fusion:

  Tier 1 — Entity graph traversal (highest weight)
  Tier 2 — Tag array matching (medium weight)
  Tier 3 — Vector cosine similarity via pgvector (lowest weight, catches all)
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.prompts.query import (
    QUERY_DECOMPOSITION_SYSTEM_PROMPT,
    QUERY_DECOMPOSITION_USER_PROMPT,
)
from app.services.embedding import generate_embedding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query decomposition
# ---------------------------------------------------------------------------

async def decompose_query(query: str) -> dict:
    """Use LLM to break a natural language query into structured parts."""
    if not settings.OPENAI_API_KEY:
        return {
            "entity_search": [],
            "tag_filters": [],
            "content_type": None,
            "semantic_query": query,
        }

    from langchain_openai import ChatOpenAI
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0,
        api_key=settings.OPENAI_API_KEY, max_tokens=500,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", QUERY_DECOMPOSITION_SYSTEM_PROMPT),
        ("human", QUERY_DECOMPOSITION_USER_PROMPT),
    ])
    chain = prompt | llm | JsonOutputParser()

    try:
        result = await chain.ainvoke({"query": query})
        result.setdefault("entity_search", [])
        result.setdefault("tag_filters", [])
        result.setdefault("content_type", None)
        result.setdefault("semantic_query", query)
        return result
    except Exception:
        logger.exception("Query decomposition failed, falling back to raw query")
        return {
            "entity_search": [],
            "tag_filters": [],
            "content_type": None,
            "semantic_query": query,
        }


# ---------------------------------------------------------------------------
# Tier 1: Entity graph traversal
# ---------------------------------------------------------------------------

async def _search_by_entities(
    session: AsyncSession,
    entity_names: list[str],
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[dict]:
    """Find posts linked to entities matching the given names."""
    if not entity_names:
        return []

    search_terms = [n.lower().strip() for n in entity_names]

    query = text("""
        SELECT DISTINCT ON (p.id)
            p.id AS post_id, p.url, p.platform, p.ai_summary,
            p.creator, p.caption, p.ai_tags,
            p.metadata->>'thumbnail' AS thumbnail_url,
            e.name AS matched_entity,
            GREATEST(
                CASE WHEN e.normalized_name = ANY(:exact_terms) THEN 1.0 ELSE 0.0 END,
                similarity(e.normalized_name, :first_term)
            ) AS score
        FROM posts p
        JOIN post_entities pe ON p.id = pe.post_id
        JOIN entities e ON pe.entity_id = e.id
        WHERE p.status = 'ready'
          AND p.user_id = :user_id
          AND (
            e.normalized_name = ANY(:exact_terms)
            OR similarity(e.normalized_name, :first_term) > 0.3
          )
        ORDER BY p.id, score DESC
        LIMIT :limit
    """)

    result = await session.execute(query, {
        "exact_terms": search_terms,
        "first_term": search_terms[0] if search_terms else "",
        "user_id": user_id,
        "limit": limit,
    })
    rows = result.mappings().all()

    posts: dict[uuid.UUID, dict] = {}
    for row in rows:
        pid = row["post_id"]
        if pid not in posts:
            posts[pid] = {
                "post_id": pid,
                "url": row["url"],
                "platform": row["platform"],
                "creator": row["creator"],
                "caption": row["caption"],
                "thumbnail_url": row["thumbnail_url"],
                "ai_summary": row["ai_summary"],
                "ai_tags": list(row["ai_tags"]) if row["ai_tags"] else [],
                "score": float(row["score"]),
                "matched_entities": [],
            }
        posts[pid]["matched_entities"].append(row["matched_entity"])

    return sorted(posts.values(), key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Tier 2: Tag matching
# ---------------------------------------------------------------------------

async def _search_by_tags(
    session: AsyncSession,
    tag_filters: list[str],
    user_id: uuid.UUID,
    content_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Find posts with overlapping ai_tags."""
    if not tag_filters:
        return []

    where_clause = "p.status = 'ready' AND p.user_id = :user_id AND p.ai_tags && :tags"
    params: dict = {"tags": tag_filters, "user_id": user_id, "limit": limit}

    if content_type:
        where_clause += " AND p.content_type = :content_type"
        params["content_type"] = content_type

    query = text(f"""
        SELECT p.id AS post_id, p.url, p.platform, p.ai_summary,
            p.creator, p.caption, p.ai_tags,
            p.metadata->>'thumbnail' AS thumbnail_url,
            (
                SELECT COUNT(*)::float FROM unnest(p.ai_tags) tag
                WHERE tag = ANY(:tags)
            ) / :tag_count AS score
        FROM posts p
        WHERE {where_clause}
        ORDER BY score DESC
        LIMIT :limit
    """)
    params["tag_count"] = float(len(tag_filters))

    result = await session.execute(query, params)
    rows = result.mappings().all()

    return [
        {
            "post_id": row["post_id"],
            "url": row["url"],
            "platform": row["platform"],
            "creator": row["creator"],
            "caption": row["caption"],
            "thumbnail_url": row["thumbnail_url"],
            "ai_summary": row["ai_summary"],
            "ai_tags": list(row["ai_tags"]) if row["ai_tags"] else [],
            "score": float(row["score"]),
            "matched_entities": [],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Tier 3: Vector similarity
# ---------------------------------------------------------------------------

async def _search_by_vector(
    session: AsyncSession,
    query_text: str,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[dict]:
    """Semantic search via pgvector cosine similarity."""
    embedding = await generate_embedding(query_text)
    if not embedding:
        return []

    query = text("""
        SELECT p.id AS post_id, p.url, p.platform, p.ai_summary,
               p.creator, p.caption, p.ai_tags,
               p.metadata->>'thumbnail' AS thumbnail_url,
               1 - (p.embedding <=> CAST(:query_embedding AS vector)) AS score
        FROM posts p
        WHERE p.status = 'ready'
          AND p.user_id = :user_id
          AND p.embedding IS NOT NULL
        ORDER BY p.embedding <=> CAST(:query_embedding AS vector)
        LIMIT :limit
    """)

    result = await session.execute(query, {
        "query_embedding": str(embedding),
        "user_id": user_id,
        "limit": limit,
    })
    rows = result.mappings().all()

    return [
        {
            "post_id": row["post_id"],
            "url": row["url"],
            "platform": row["platform"],
            "creator": row["creator"],
            "caption": row["caption"],
            "thumbnail_url": row["thumbnail_url"],
            "ai_summary": row["ai_summary"],
            "ai_tags": list(row["ai_tags"]) if row["ai_tags"] else [],
            "score": float(row["score"]),
            "matched_entities": [],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """Merge multiple ranked result lists using RRF."""
    scores: dict[uuid.UUID, dict] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list):
            item_id = item["post_id"]
            if item_id not in scores:
                scores[item_id] = {
                    "post_id": item["post_id"],
                    "url": item["url"],
                    "platform": item["platform"],
                    "creator": item.get("creator"),
                    "caption": item.get("caption"),
                    "thumbnail_url": item.get("thumbnail_url"),
                    "ai_summary": item["ai_summary"],
                    "ai_tags": item.get("ai_tags", []),
                    "score": 0.0,
                    "matched_entities": [],
                }
            scores[item_id]["score"] += 1.0 / (k + rank + 1)

            for entity in item.get("matched_entities", []):
                if entity not in scores[item_id]["matched_entities"]:
                    scores[item_id]["matched_entities"].append(entity)

    merged = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def hybrid_search(
    session: AsyncSession,
    query: str,
    user_id: uuid.UUID,
    limit: int = 20,
) -> dict:
    """Run the full hybrid search pipeline scoped to a user."""
    # Step 1: decompose
    decomposed = await decompose_query(query)
    logger.info("Query decomposed: %s", decomposed)

    entity_names = decomposed.get("entity_search", [])
    tag_filters = decomposed.get("tag_filters", [])
    content_type = decomposed.get("content_type")
    semantic_query = decomposed.get("semantic_query", query)

    # Step 2: run all three tiers
    tier1 = await _search_by_entities(session, entity_names, user_id)
    tier2 = await _search_by_tags(session, tag_filters, user_id, content_type)
    tier3 = await _search_by_vector(session, semantic_query, user_id)

    logger.info(
        "Search tiers: %d entity results, %d tag results, %d vector results",
        len(tier1), len(tier2), len(tier3),
    )

    # Step 3: merge
    merged = reciprocal_rank_fusion([tier1, tier2, tier3])

    # Step 4: trim to limit
    results = merged[:limit]

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }
