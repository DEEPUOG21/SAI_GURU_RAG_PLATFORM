"""Unit/regression tests must not export traces using developer credentials."""

import os

os.environ["LANGSMITH_TRACING"] = "false"
