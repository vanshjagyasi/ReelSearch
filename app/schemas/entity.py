from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntityResponse(BaseModel):
    id: UUID
    name: str
    type: str
    mention_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntityDetail(EntityResponse):
    normalized_name: str
    attributes: dict = {}
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EntityLinkedReel(BaseModel):
    post_id: UUID
    url: str
    platform: str | None = None
    ai_summary: str | None = None
    relationship: str | None = None
    context: str | None = None


class EntityWithReels(EntityDetail):
    linked_reels: list[EntityLinkedReel] = []


class RelatedEntity(BaseModel):
    id: UUID
    name: str
    type: str
    relation_type: str
    strength: int

    model_config = ConfigDict(from_attributes=True)
