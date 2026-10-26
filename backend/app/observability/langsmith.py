"""Opt-in LangSmith traces; application execution does not require an account."""

import logging
from contextlib import contextmanager
from functools import lru_cache

from langsmith import Client, tracing_context


@lru_cache(maxsize=4)
def tracing_client(api_key, endpoint, hide_inputs, hide_outputs):
    return Client(
        api_key=api_key,
        api_url=endpoint,
        hide_inputs=hide_inputs,
        hide_outputs=hide_outputs,
        timeout_ms=2000,
    )


@contextmanager
def tracing_scope(cfg):
    client = None
    if cfg.langsmith_tracing:
        if not cfg.langsmith_api_key:
            logging.warning("LangSmith tracing requested without an API key; tracing disabled.")
        else:
            try:
                client = tracing_client(
                    cfg.langsmith_api_key,
                    cfg.langsmith_endpoint,
                    cfg.langsmith_hide_inputs or cfg.guardrails_enabled,
                    cfg.langsmith_hide_outputs or cfg.guardrails_enabled,
                )
            except Exception:
                logging.warning("LangSmith client unavailable; continuing without hosted traces.")
    with tracing_context(
        enabled=client is not None,
        client=client,
        project_name=cfg.langsmith_project,
    ):
        yield
