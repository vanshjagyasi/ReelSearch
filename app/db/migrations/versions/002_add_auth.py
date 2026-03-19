"""Add users table and user_id to posts/entities.

Revision ID: 002_add_auth
Revises: 001_initial_tables
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002_add_auth"
down_revision = "001"
branch_labels = None
depends_on = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_username", "users", ["username"], unique=True)

    # 2. Insert system user for existing data (hash is bcrypt of a random value — account cannot be logged into)
    op.execute(
        f"INSERT INTO users (id, username, hashed_password, display_name) "
        f"VALUES ('{SYSTEM_USER_ID}', 'system', "
        f"'$2b$12$LJ3m4ys3uz0HjsLWKMZqueelhXhBRkHY0jRqaJBBQMPehDK3J2tDe', 'System')"
    )

    # 3. Add user_id to posts
    op.add_column("posts", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE posts SET user_id = '{SYSTEM_USER_ID}'")
    op.alter_column("posts", "user_id", nullable=False)
    op.create_foreign_key("fk_posts_user_id", "posts", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("idx_posts_user_id", "posts", ["user_id"])

    # Drop old unique constraint on url, add composite unique
    op.drop_constraint("posts_url_key", "posts", type_="unique")
    op.create_unique_constraint("uq_post_url_user", "posts", ["url", "user_id"])

    # 4. Add user_id to entities
    op.add_column("entities", sa.Column("user_id", UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE entities SET user_id = '{SYSTEM_USER_ID}'")
    op.alter_column("entities", "user_id", nullable=False)
    op.create_foreign_key("fk_entities_user_id", "entities", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("idx_entities_user_id", "entities", ["user_id"])


def downgrade() -> None:
    # Entities
    op.drop_index("idx_entities_user_id", "entities")
    op.drop_constraint("fk_entities_user_id", "entities", type_="foreignkey")
    op.drop_column("entities", "user_id")

    # Posts
    op.drop_constraint("uq_post_url_user", "posts", type_="unique")
    op.create_unique_constraint("posts_url_key", "posts", ["url"])
    op.drop_index("idx_posts_user_id", "posts")
    op.drop_constraint("fk_posts_user_id", "posts", type_="foreignkey")
    op.drop_column("posts", "user_id")

    # Users
    op.drop_index("idx_users_username", "users")
    op.drop_table("users")
