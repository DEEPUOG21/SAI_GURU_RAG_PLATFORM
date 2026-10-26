from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://sai:sai@localhost:5432/sai_guru"
    sql_database_url: str = ""
    jwt_secret: str = ""
    cors_origins: str = "http://localhost:5173"
    embedding_provider: Literal["local", "http"] = "local"
    inference_api_key: str = ""
    embedding_url: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    reranker_provider: Literal["local", "http", "cloudflare"] = "local"
    reranker_url: str = ""
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    llm_url: str = "http://localhost:11434/v1"
    llm_provider: Literal["openai", "cloudflare"] = "openai"
    llm_model: str = "qwen2.5:3b"
    llm_api_key: str = ""
    llm_input_cost_per_million: float = 0
    llm_output_cost_per_million: float = 0
    generation_mode: Literal["llm", "extractive"] = "llm"
    grounding_action: Literal["refuse", "regenerate"] = "regenerate"
    general_fallback_enabled: bool = True
    guardrails_enabled: bool = True
    guardrails_redact_identifiers: bool = True
    langsmith_tracing: bool = False
    langsmith_api_key: str = Field(default="", repr=False)
    langsmith_project: str = "sai-guru"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_hide_inputs: bool = True
    langsmith_hide_outputs: bool = True
    max_upload_mb: int = Field(default=10, ge=1, le=20)
    query_timeout_seconds: int = Field(default=120, ge=10, le=600)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=300)
    seed_admin_email: str = "admin@saitech.example"
    seed_admin_password: str = ""

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, value):
        origins = [origin.strip() for origin in value.split(",")]
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "*" in origin
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ORIGINS must contain explicit HTTP(S) origins without wildcards or credentials"
                )
        return ",".join(origin.rstrip("/") for origin in origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
