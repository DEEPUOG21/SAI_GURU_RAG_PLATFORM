import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.api import auth, chat, documents, evaluation, observability
from app.core.config import get_settings
from app.database.session import engine, require_runtime_role
from app.security.body_limit import BodyLimitMiddleware
from app.security.capacity import CapacityMiddleware

logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app):
    await require_runtime_role()
    yield
    await engine.dispose()


class ErrorDetail(BaseModel):
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


app = FastAPI(
    title="Sai Guru API",
    version="0.1.0",
    lifespan=lifespan,
    responses={status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 413, 422, 429, 500, 503)},
)
settings = get_settings()
app.add_middleware(BodyLimitMiddleware, limit=settings.max_upload_mb * 1024 * 1024 + 65536)
app.add_middleware(CapacityMiddleware)
for router in (auth.router, chat.router, documents.router, evaluation.router, observability.router):
    app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(exc.detail), "request_id": request.state.request_id}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Invalid request. Check required fields and limits.",
                "request_id": request.state.request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.error("request_failed request_id=%s", request.state.request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "An internal error occurred. Check server logs using the request ID.",
                "request_id": request.state.request_id,
            }
        },
    )


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "sai-guru", "max_upload_mb": settings.max_upload_mb}
