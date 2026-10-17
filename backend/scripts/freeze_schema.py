"""Generate initial migration SQL before release; not used at application startup."""

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database.session import Base
from app.models import entities  # noqa: F401

dialect = postgresql.dialect()
statements = ["CREATE EXTENSION IF NOT EXISTS vector"]
for table in Base.metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=dialect)).strip())
    statements.extend(str(CreateIndex(index).compile(dialect=dialect)).strip() for index in table.indexes)
Path("backend/migrations/versions/0001_initial.sql").write_text(";\n".join(statements) + ";\n")
