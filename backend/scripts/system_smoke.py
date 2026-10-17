"""Native local verification: actual models, database, SQL permissions and evaluations.

Requires scripts/local_test_database.py, migrated sai_guru_test and the optional inference service.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

load_dotenv()
os.environ["DATABASE_URL"] = Path(".local-runtime-url" if os.getenv("SAI_RUNTIME") == "1" else ".local-test-url").read_text()
os.environ["SQL_DATABASE_URL"] = (
    make_url(os.environ["DATABASE_URL"])
    .set(username="sai_reader", password=os.environ["SQL_READER_PASSWORD"])
    .render_as_string(hide_password=False)
)
os.environ["LLM_URL"] = "http://127.0.0.1:7860/v1"
os.environ["LLM_MODEL"] = "sai-local"
os.environ["LLM_API_KEY"] = Path(".local-inference-key").read_text()
os.environ["GENERATION_MODE"] = "llm"
os.environ["QUERY_TIMEOUT_SECONDS"] = "300"
os.environ["EMBEDDING_PROVIDER"] = "http"
os.environ["RERANKER_PROVIDER"] = "http"
os.environ["EMBEDDING_URL"] = "http://127.0.0.1:7860/embeddings"
os.environ["RERANKER_URL"] = "http://127.0.0.1:7860/rerank"
os.environ["INFERENCE_API_KEY"] = Path(".local-inference-key").read_text()

from app.agents.sql import run_sql, sql_engine  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.database.seed import main as seed  # noqa: E402
from app.database.session import Session, engine  # noqa: E402
from app.database.setup_sql import main as setup_sql  # noqa: E402
from app.ingestion.worker import process_one  # noqa: E402
from app.main import app  # noqa: E402
from app.models.entities import Document, User  # noqa: E402
from app.security.scope import Scope  # noqa: E402
from app.services.grounding import check_grounding  # noqa: E402
from app.services.llm import llm  # noqa: E402


async def main():
    await setup_sql()
    await seed()
    async with Session() as db:
        user = await db.scalar(select(User).where(User.email == get_settings().seed_admin_email))
        docs = (await db.scalars(select(Document).where(Document.tenant_id == user.tenant_id))).all()
        scope = Scope(user.tenant_id, user.id, user.role)
    for doc in docs:
        await process_one(doc.id)
    print("Eight synthetic documents processed through HTTP embedding provider.", flush=True)
    sql_result = await run_sql("How many employees joined last month?", scope)
    assert "employee_count" in sql_result["rows"][0]
    async with sql_engine().connect() as connection:
        try:
            await connection.execute(text("DELETE FROM employees"))
            raise AssertionError("Read-only SQL role allowed DELETE")
        except Exception as exc:
            if isinstance(exc, AssertionError):
                raise
            await connection.rollback()
        try:
            await connection.execute(text("SELECT * FROM users"))
            raise AssertionError("Read-only SQL role could read users")
        except Exception as exc:
            if isinstance(exc, AssertionError):
                raise
            await connection.rollback()
    print("Read-only SQL execution and permission denials verified.", flush=True)
    # The verifier must reject a deliberately wrong claim about the real synthetic policy.
    policy = (Path("data/demo/Leave-Policy.md")).read_text(encoding="utf-8")
    rejected, _ = await check_grounding(
        llm(),
        "Annual leave allowance",
        "Employees receive 99 paid annual leave days. [Source 1]",
        [{"label": "Source 1", "document": "Leave-Policy.md", "section": "Annual leave", "text": policy}],
    )
    assert rejected["status"] == "UNSUPPORTED", rejected
    print("Grounding pipeline rejected a deliberately incorrect 99-day claim.", flush=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=650) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": get_settings().seed_admin_email, "password": get_settings().seed_admin_password},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        answer = await client.post(
            "/api/v1/chat",
            headers=headers,
            json={"question": "How many paid annual leave days do full-time SaiTech employees receive?"},
        )
        frames = [json.loads(line[6:]) for line in answer.text.splitlines() if line.startswith("data: ")]
        final = next((frame for frame in frames if "answer" in frame), None)
        assert final, answer.text
        assert final["grounding"] == "SUPPORTED" and "24" in final["answer"], final
        assert any("text" in frame for frame in frames), "No real streamed LLM tokens received"
        print(
            {
                "llm_grounding": final["grounding"],
                "answer": final["answer"],
                "citation_count": len(final["citations"]),
            },
            flush=True,
        )
        result = await client.post("/api/v1/evaluation/run", headers=headers)
        assert result.status_code == 200, result.text
        evaluation = result.json()
        assert evaluation["status"] == "COMPLETED", evaluation
        print({"evaluation": evaluation["status"], "metrics": evaluation["results"]["aggregate"]}, flush=True)
        Path("docs/local-verification.json").write_text(
            json.dumps(
                {
                    "database": "native PostgreSQL + pgvector",
                    "documents": len(docs),
                    "sql_permissions": "verified",
                    "llm_model": get_settings().llm_model,
                    "answer": final["answer"],
                    "grounding": final["grounding"],
                    "citation_count": len(final["citations"]),
                    "evaluation": evaluation["results"],
                },
                indent=2,
            )
        )
    await sql_engine().dispose()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
