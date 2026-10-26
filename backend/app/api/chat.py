from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.database.session import get_db
from app.models.entities import Conversation, Feedback, Message, Query
from app.schemas.requests import ChatRequest, FeedbackRequest
from app.schemas.responses import ConversationResponse, MessageResponse
from app.security.auth import current_scope, rate_limit
from app.security.guardrails import redact
from app.services.access import sources_visible
from app.services.chat import chat_stream, conversation_history
from app.services.conversation import history_sources

router = APIRouter(prefix="/api/v1", tags=["Assistant"])


async def owned_conversation(db, scope, id):
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == id,
            Conversation.tenant_id == scope.tenant_id,
            Conversation.user_id == scope.user_id,
        )
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found.")
    return conversation


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE events: meta, status, reset, final, error, done. Answers are emitted only after policy checks. Errors after headers use an error event followed by done.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def chat(body: ChatRequest, request: Request, scope=Depends(current_scope), db=Depends(get_db)):
    if not body.question.strip():
        raise HTTPException(422, "Enter a question.")
    await rate_limit(db, "query:" + scope.user_id)
    question = redact(body.question)
    if body.conversation_id:
        conversation = await owned_conversation(db, scope, body.conversation_id)
    else:
        conversation = Conversation(tenant_id=scope.tenant_id, user_id=scope.user_id, title=question[:160])
        db.add(conversation)
        await db.flush()
    history = await conversation_history(db, conversation.id, scope)
    query = Query(
        tenant_id=scope.tenant_id,
        user_id=scope.user_id,
        conversation_id=conversation.id,
        question=question,
        request_id=request.state.request_id,
    )
    db.add(query)
    await db.flush()
    db.add(Message(conversation_id=conversation.id, role="user", content=question, query_id=query.id))
    await db.commit()
    return StreamingResponse(
        chat_stream(query.id, conversation.id, body.question, scope, history, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def conversations(scope=Depends(current_scope), db=Depends(get_db)):
    rows = (
        await db.scalars(
            select(Conversation)
            .where(Conversation.tenant_id == scope.tenant_id, Conversation.user_id == scope.user_id)
            .order_by(Conversation.created_at.desc())
            .limit(100)
        )
    ).all()
    return [{"id": row.id, "title": row.title, "created_at": row.created_at} for row in rows]


@router.delete("/conversations/{id}", status_code=204)
async def delete_conversation(id: str, scope=Depends(current_scope), db=Depends(get_db)):
    conversation = await owned_conversation(db, scope, id)
    await db.execute(delete(Query).where(Query.conversation_id == id, Query.user_id == scope.user_id))
    await db.delete(conversation)
    await db.commit()


@router.get("/conversations/{id}/messages", response_model=list[MessageResponse])
async def messages(id: str, scope=Depends(current_scope), db=Depends(get_db)):
    await owned_conversation(db, scope, id)
    rows = (
        await db.execute(
            select(Message, Query.grounding, Query.trace)
            .outerjoin(Query, Message.query_id == Query.id)
            .where(Message.conversation_id == id)
            .order_by(Message.created_at, Message.id)
            .limit(500)
        )
    ).all()
    result = []
    for row, grounding, trace in rows:
        visible = await sources_visible(db, scope, (row.citations or []) + history_sources(trace))
        result.append(
            {
                "id": row.id,
                "role": row.role,
                "query_id": row.query_id,
                "content": row.content
                if visible
                else "Source access changed. Regenerate this answer against the current knowledge base.",
                "citations": row.citations if visible else [],
                "grounding": (grounding if visible else "INSUFFICIENT") if row.role == "assistant" else None,
                "guardrails": [
                    step["output"] | {"stage": step["node"].removeprefix("guardrail_")}
                    for step in (trace or [])
                    if step.get("node", "").startswith("guardrail_") and isinstance(step.get("output"), dict)
                ]
                if visible and row.role == "assistant"
                else [],
            }
        )
    return result


@router.post("/feedback")
async def feedback(body: FeedbackRequest, scope=Depends(current_scope), db=Depends(get_db)):
    query = await db.scalar(
        select(Query).where(
            Query.id == body.query_id,
            Query.tenant_id == scope.tenant_id,
            Query.user_id == scope.user_id,
            Query.status == "COMPLETED",
        )
    )
    if not query:
        raise HTTPException(404, "Completed query not found.")
    await db.execute(
        insert(Feedback)
        .values(query_id=query.id, user_id=scope.user_id, rating=body.rating, comment=body.comment)
        .on_conflict_do_update(
            index_elements=[Feedback.query_id, Feedback.user_id],
            set_={"rating": body.rating, "comment": body.comment},
        )
    )
    await db.commit()
    return {"status": "saved"}
