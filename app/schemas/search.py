from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    post_id: UUID
    url: str
    platform: str | None = None
    creator: str | None = None
    caption: str | None = None
    thumbnail_url: str | None = None
    ai_summary: str | None = None
    ai_tags: list[str] = []
    score: float = 0.0
    matched_entities: list[str] = []


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchResult]
