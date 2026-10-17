from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database.session import get_db
from app.evaluation.service import run_evaluation
from app.models.entities import Evaluation
from app.schemas.responses import EvaluationResponse
from app.security.auth import current_scope, rate_limit, require_role
from app.services.access import sources_visible

router = APIRouter(prefix="/api/v1/evaluation", tags=["Evaluation"])


@router.post("/run")
async def run(scope=Depends(current_scope), db=Depends(get_db)):
    require_role(scope, 1)
    await rate_limit(db, "evaluation:" + scope.user_id, 1)
    return await run_evaluation(scope)


@router.get("/results", response_model=list[EvaluationResponse])
async def results(scope=Depends(current_scope), db=Depends(get_db)):
    require_role(scope, 1)
    rows = (
        await db.scalars(
            select(Evaluation)
            .where(Evaluation.tenant_id == scope.tenant_id, Evaluation.user_id == scope.user_id)
            .order_by(Evaluation.created_at.desc())
            .limit(20)
        )
    ).all()
    output = []
    for row in rows:
        citations = [source for case in row.results.get("cases", []) for source in case.get("citations", [])]
        visible = await sources_visible(db, scope, citations)
        output.append(
            {
                "id": row.id,
                "status": row.status,
                "created_at": row.created_at,
                "results": row.results if visible else {"error": "Source access changed; rerun evaluation."},
            }
        )
    return output
