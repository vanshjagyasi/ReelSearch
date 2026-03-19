from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.entity import Entity
from app.models.entity_relation import EntityRelation
from app.models.post_entity import PostEntity
from app.models.post import Post
from app.models.user import User
from app.schemas.entity import (
    EntityDetail,
    EntityLinkedReel,
    EntityResponse,
    EntityWithReels,
    RelatedEntity,
)

router = APIRouter()


@router.get("/entities", response_model=list[EntityResponse])
async def list_entities(
    type: str | None = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List top entities for the current user, sorted by mention count."""
    query = (
        select(Entity)
        .where(Entity.user_id == current_user.id)
        .order_by(Entity.mention_count.desc())
        .limit(limit)
    )
    if type:
        query = query.where(Entity.type == type)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/entities/{entity_id}", response_model=EntityWithReels)
async def get_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get entity details with all linked reels (scoped to current user)."""
    result = await db.execute(
        select(Entity).where(Entity.id == entity_id, Entity.user_id == current_user.id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Fetch linked reels (only user's reels)
    reel_query = (
        select(
            Post.id.label("post_id"),
            Post.url,
            Post.platform,
            Post.ai_summary,
            PostEntity.relationship,
            PostEntity.context,
        )
        .join(PostEntity, Post.id == PostEntity.post_id)
        .where(PostEntity.entity_id == entity_id, Post.user_id == current_user.id)
        .order_by(Post.created_at.desc())
    )
    reel_rows = await db.execute(reel_query)
    linked_reels = [
        EntityLinkedReel(**dict(row._mapping))
        for row in reel_rows
    ]

    return EntityWithReels(
        id=entity.id,
        name=entity.name,
        normalized_name=entity.normalized_name,
        type=entity.type,
        attributes=entity.attributes or {},
        mention_count=entity.mention_count,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        linked_reels=linked_reels,
    )


@router.get("/entities/{entity_id}/related", response_model=list[RelatedEntity])
async def get_related_entities(
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get entities related to a given entity (scoped to current user)."""
    result = await db.execute(
        select(Entity).where(Entity.id == entity_id, Entity.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Entity not found")

    query = text("""
        SELECT e.id, e.name, e.type, er.relation_type, er.strength
        FROM entity_relations er
        JOIN entities e ON e.id = CASE
            WHEN er.entity_a_id = :eid THEN er.entity_b_id
            ELSE er.entity_a_id
        END
        WHERE (er.entity_a_id = :eid OR er.entity_b_id = :eid)
          AND e.user_id = :user_id
        ORDER BY er.strength DESC
        LIMIT 50
    """)
    result = await db.execute(query, {"eid": entity_id, "user_id": current_user.id})
    rows = result.mappings().all()

    return [RelatedEntity(**dict(row)) for row in rows]
