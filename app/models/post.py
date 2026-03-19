import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20))
    creator: Mapped[str | None] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    frame_description: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    content_type: Mapped[str | None] = mapped_column(String(50))
    mood: Mapped[str | None] = mapped_column(String(50))
    embedding = mapped_column(Vector(1536), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    user_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    @property
    def thumbnail_url(self) -> str | None:
        if isinstance(self.metadata_, dict):
            return self.metadata_.get("thumbnail")
        return None

    __table_args__ = (
        UniqueConstraint("url", "user_id", name="uq_post_url_user"),
        Index("idx_posts_user_id", "user_id"),
        Index("idx_posts_status", "status"),
        Index("idx_posts_platform", "platform"),
        Index("idx_posts_ai_tags", "ai_tags", postgresql_using="gin"),
    )
