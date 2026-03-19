from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.search import hybrid_search

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_reels(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search reels using natural language (scoped to current user)."""
    raw = await hybrid_search(db, request.query, user_id=current_user.id, limit=request.limit)

    results = [
        SearchResult(
            post_id=r["post_id"],
            url=r["url"],
            platform=r["platform"],
            creator=r.get("creator"),
            caption=r.get("caption"),
            thumbnail_url=r.get("thumbnail_url"),
            ai_summary=r["ai_summary"],
            ai_tags=r.get("ai_tags") or [],
            score=r["score"],
            matched_entities=r.get("matched_entities", []),
        )
        for r in raw["results"]
    ]

    return SearchResponse(
        query=raw["query"],
        count=raw["count"],
        results=results,
    )
