"""Server-side account session revocation counter."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")


def downgrade():
    raise RuntimeError("Do not silently remove session revocation state.")
