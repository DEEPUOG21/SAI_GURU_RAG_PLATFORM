"""Initial schema: frozen SQL checked into the migration directory."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in Path(__file__).with_suffix(".sql").read_text().split(";\n"):
        if statement.strip():
            op.execute(statement.strip())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled. Restore a database backup instead.")
