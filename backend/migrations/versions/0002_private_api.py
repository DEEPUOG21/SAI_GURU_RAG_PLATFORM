"""Keep app tables out of Supabase anonymous/authenticated Data API access."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Roles exist on Supabase but not ordinary PostgreSQL. Conditional SQL works in both.
    for role in ("PUBLIC", "anon", "authenticated"):
        statement = f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"
        if role == "PUBLIC":
            op.execute(statement)
        else:
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN "
                f"{statement}; END IF; END $$"
            )


def downgrade():
    raise RuntimeError(
        "Do not restore public table access. Restore an audited privilege configuration explicitly."
    )
