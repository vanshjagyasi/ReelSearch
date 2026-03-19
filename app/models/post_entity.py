import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PostEntity(Base):
    __tablename__ = "post_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship: Mapped[str | None] = mapped_column(
        String(50), server_default=text("'mentions'")
    )
    context: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("post_id", "entity_id", name="uq_post_entity"),
        Index("idx_post_entities_post", "post_id"),
        Index("idx_post_entities_entity", "entity_id"),
    )
