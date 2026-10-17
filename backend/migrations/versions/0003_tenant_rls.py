"""Default-deny tenant policies, reapplied on each application transaction."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    tenant = "current_setting('app.tenant_id', true)"
    policies = {
        "tenants": f"id = {tenant}",
        "users": f"tenant_id = {tenant}",
        **{
            table: f"tenant_id = {tenant}"
            for table in (
                "documents",
                "document_versions",
                "document_chunks",
                "conversations",
                "queries",
                "evaluations",
                "employees",
            )
        },
        "messages": "EXISTS (SELECT 1 FROM conversations c WHERE c.id = conversation_id)",
        "retrieval_results": "EXISTS (SELECT 1 FROM queries q WHERE q.id = query_id)",
        "feedback": "EXISTS (SELECT 1 FROM queries q WHERE q.id = query_id)",
    }
    for table, condition in policies.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_boundary ON {table} USING ({condition}) WITH CHECK ({condition})")
    # Authentication can read one supplied identity before a tenant is established.
    # This SELECT-only policy cannot authorize tenant writes.
    op.execute(
        "CREATE POLICY authentication_lookup ON users FOR SELECT USING "
        "(id = current_setting('app.user_id', true) OR "
        "email = current_setting('app.login_email', true))"
    )


def downgrade():
    raise RuntimeError("Tenant isolation cannot be silently disabled; restore an audited backup instead.")
