import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.entity import Entity
from app.models.post import Post
from app.models.user import User
from app.schemas.post import ReelDetail, ReelListResponse, ReelResponse, SaveReelRequest
from app.services.ingest import ingest_reel
from app.services.metadata import clean_url, detect_platform

router = APIRouter()


@router.post("/reels", response_model=ReelResponse, status_code=201)
async def save_reel(
    request: SaveReelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a new reel URL for processing."""
    url = clean_url(request.url)

    result = await db.execute(
        select(Post).where(Post.url == url, Post.user_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This URL has already been saved")

    post = Post(
        url=url,
        platform=detect_platform(url),
        user_id=current_user.id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    asyncio.create_task(ingest_reel(post.id))
    return post


@router.get("/reels", response_model=ReelListResponse)
async def list_reels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all saved reels for the current user."""
    result = await db.execute(
        select(Post).where(Post.user_id == current_user.id).order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()
    return ReelListResponse(count=len(posts), reels=posts)


@router.get("/reels/{reel_id}", response_model=ReelDetail)
async def get_reel(
    reel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a saved reel."""
    result = await db.execute(
        select(Post).where(Post.id == reel_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Reel not found")
    return post


@router.delete("/reels/{reel_id}", status_code=204)
async def delete_reel(
    reel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved reel."""
    result = await db.execute(
        select(Post).where(Post.id == reel_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Reel not found")
    await db.delete(post)
    await db.commit()



@router.get("/reels/{reel_id}/status")
async def get_reel_status(
    reel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the processing status of a reel."""
    result = await db.execute(
        select(Post).where(Post.id == reel_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Reel not found")
    return {
        "id": post.id,
        "status": post.status,
        "has_transcript": post.transcript is not None,
        "has_frame_description": post.frame_description is not None,
    }


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Processing stats for the current user."""
    status_rows = await db.execute(
        select(Post.status, func.count()).where(
            Post.user_id == current_user.id,
        ).group_by(Post.status)
    )
    by_status = {row[0]: row[1] for row in status_rows}

    entity_count = await db.execute(
        select(func.count()).select_from(Entity).where(Entity.user_id == current_user.id)
    )

    return {
        "reels": {
            "pending": by_status.get("pending", 0),
            "processing": by_status.get("processing", 0),
            "ready": by_status.get("ready", 0),
            "failed": by_status.get("failed", 0),
            "total": sum(by_status.values()),
        },
        "entities": entity_count.scalar(),
    }
