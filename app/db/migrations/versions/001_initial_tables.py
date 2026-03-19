"""initial tables

Revision ID: 001
Revises:
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required Postgres extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # --- posts ---
    op.create_table(
        "posts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("platform", sa.String(20)),
        sa.Column("creator", sa.String(255)),
        sa.Column("caption", sa.Text()),
        sa.Column("transcript", sa.Text()),
        sa.Column("frame_description", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_tags", sa.ARRAY(sa.Text())),
        sa.Column("content_type", sa.String(50)),
        sa.Column("mood", sa.String(50)),
        sa.Column("embedding", Vector(1536)),
        sa.Column(
            "status", sa.String(20), server_default=sa.text("'pending'")
        ),
        sa.Column("user_tags", sa.ARRAY(sa.Text())),
        sa.Column("category_id", sa.UUID()),
        sa.Column("metadata", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_posts_status", "posts", ["status"])
    op.create_index("idx_posts_platform", "posts", ["platform"])
    op.create_index(
        "idx_posts_ai_tags", "posts", ["ai_tags"], postgresql_using="gin"
    )

    # --- entities ---
    op.create_table(
        "entities",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("attributes", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column("mention_count", sa.Integer(), server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_entities_type", "entities", ["type"])
    op.create_index(
        "idx_entities_normalized_name", "entities", ["normalized_name"]
    )
    op.create_index(
        "idx_entities_name_trgm",
        "entities",
        ["normalized_name"],
        postgresql_using="gin",
        postgresql_ops={"normalized_name": "gin_trgm_ops"},
    )

    # --- post_entities ---
    op.create_table(
        "post_entities",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "post_id",
            sa.UUID(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship",
            sa.String(50),
            server_default=sa.text("'mentions'"),
        ),
        sa.Column("context", sa.Text()),
        sa.UniqueConstraint("post_id", "entity_id", name="uq_post_entity"),
    )
    op.create_index("idx_post_entities_post", "post_entities", ["post_id"])
    op.create_index(
        "idx_post_entities_entity", "post_entities", ["entity_id"]
    )

    # --- entity_relations ---
    op.create_table(
        "entity_relations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "entity_a_id",
            sa.UUID(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_b_id",
            sa.UUID(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("strength", sa.Integer(), server_default=sa.text("1")),
        sa.UniqueConstraint(
            "entity_a_id",
            "entity_b_id",
            "relation_type",
            name="uq_entity_relation",
        ),
    )
    op.create_index(
        "idx_entity_relations_a", "entity_relations", ["entity_a_id"]
    )
    op.create_index(
        "idx_entity_relations_b", "entity_relations", ["entity_b_id"]
    )


def downgrade() -> None:
    op.drop_table("entity_relations")
    op.drop_table("post_entities")
    op.drop_table("entities")
    op.drop_table("posts")
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "vector"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
