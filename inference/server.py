"""Optional private CPU inference service. No database or uploaded-file storage."""

import asyncio
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

key = os.environ.get("INFERENCE_API_KEY", "")
if len(key) < 32:
    raise RuntimeError("Set INFERENCE_API_KEY to at least 32 random characters.")
semaphore = asyncio.Semaphore(1)
models = {}


async def authenticate(authorization: str = Header("")):
    if not hmac.compare_digest(authorization, "Bearer " + key):
        raise HTTPException(401, "Invalid inference credential.")


class EmbeddingRequest(BaseModel):
    input: list[str] = Field(min_length=1, max_length=32)
    model: str = "BAAI/bge-small-en-v1.5"


class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=3000)
    documents: list[str] = Field(min_length=1, max_length=40)


def validate_texts(texts):
    if any(len(t) > 16000 for t in texts):
        raise HTTPException(422, "Text exceeds the 16000-character inference limit.")


app = FastAPI(title="Sai Guru private inference", dependencies=[Depends(authenticate)])


@app.post("/embeddings")
async def embed(body: EmbeddingRequest):
    validate_texts(body.input)
    if body.model != "BAAI/bge-small-en-v1.5":
        raise HTTPException(
            422, "This service uses BAAI/bge-small-en-v1.5 (384 dimensions)."
        )

    def run():
        from fastembed import TextEmbedding

        if "embed" not in models:
            models["embed"] = TextEmbedding(model_name=body.model, threads=2)
        return {
            "data": [
                {"index": i, "embedding": v.tolist()}
                for i, v in enumerate(models["embed"].embed(body.input))
            ]
        }

    async with semaphore:
        return await asyncio.to_thread(run)


@app.post("/rerank")
async def rerank(body: RerankRequest):
    validate_texts(body.documents)

    def run():
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        if "rank" not in models:
            models["rank"] = TextCrossEncoder(
                model_name="Xenova/ms-marco-MiniLM-L-6-v2", threads=2
            )
        return {
            "scores": [
                float(s) for s in models["rank"].rerank(body.query, body.documents)
            ]
        }

    async with semaphore:
        return await asyncio.to_thread(run)


def build_application():
    from huggingface_hub import hf_hub_download
    from llama_cpp.server.app import create_app
    from llama_cpp.server.settings import Settings

    model = os.environ.get("MODEL_PATH") or hf_hub_download(
        repo_id=os.environ.get("MODEL_REPO", "Qwen/Qwen2.5-3B-Instruct-GGUF"),
        filename=os.environ.get("MODEL_FILE", "qwen2.5-3b-instruct-q4_k_m.gguf"),
        revision=os.environ.get("MODEL_REVISION", "7dabda4d13d513e3e842b20f0d435c732f172cbe"),
    )
    llm_app = create_app(
        Settings(
            model=model,
            model_alias="sai-local",
            n_ctx=8192,
            n_threads=int(os.environ.get("MODEL_THREADS", "2")),
            n_threads_batch=int(os.environ.get("MODEL_THREADS", "2")),
            api_key=key,
            interrupt_requests=False,
            cache=False,
            verbose=False,
            host="0.0.0.0",
            port=7860,
        )
    )
    app.mount("/", llm_app)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(parent):
        async with original(parent), llm_app.router.lifespan_context(llm_app):
            yield

    app.router.lifespan_context = lifespan
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        build_application(), host="0.0.0.0", port=int(os.environ.get("PORT", "7860"))
    )
