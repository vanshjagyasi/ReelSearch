import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

SUPPORTED_URL_PATTERNS = [
    r"(https?://)?(www\.)?instagram\.com/",
    r"(https?://)?(www\.)?youtube\.com/",
    r"(https?://)?(www\.)?youtu\.be/",
    r"(https?://)?(www\.)?tiktok\.com/",
]


class SaveReelRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_reel_url(cls, v: str) -> str:
        if not any(re.match(p, v) for p in SUPPORTED_URL_PATTERNS):
            raise ValueError("URL must be from Instagram, YouTube, or TikTok")
        return v


class ReelResponse(BaseModel):
    id: UUID
    url: str
    platform: str | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReelDetail(ReelResponse):
    creator: str | None = None
    caption: str | None = None
    transcript: str | None = None
    frame_description: str | None = None
    ai_summary: str | None = None
    ai_tags: list[str] | None = None
    content_type: str | None = None
    mood: str | None = None
    metadata_: dict | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReelListResponse(BaseModel):
    count: int
    reels: list[ReelResponse]
