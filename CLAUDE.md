# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Mastery Lab — API bancaria com agente IA (LangChain/LangGraph), RAG (pgvector), padroes production-grade. Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2. Portfolio de Senior AI Engineer — Banco BV.

## Build & Run Commands

```bash
# Setup
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run
uvicorn app.main:app --reload        # Dev server porta 8000
pytest                                # Todos os testes
pytest tests/unit                     # Apenas unit tests
pytest tests/integration              # Apenas integration tests
pytest --cov=app --cov-report=html    # Com cobertura
ruff check app/ tests/                # Lint
ruff format app/ tests/               # Format

# Database
alembic upgrade head                  # Rodar migrations
alembic revision --autogenerate -m "desc"  # Gerar migration

# RAG
python scripts/ingest.py              # Ingerir documentos bancarios

# Docker
docker compose up -d                  # Infraestrutura
docker compose down                   # Parar
```

## Architecture

Three layers (routers -> services -> repositories) + agent layer (graph -> nodes -> tools) + RAG layer (embeddings -> chunker -> retriever).

```
app/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings via pydantic-settings
├── routers/                 # REST endpoints (equivalente controllers/)
├── services/                # Business logic
├── repositories/            # Data access (SQLAlchemy async)
├── models/                  # SQLAlchemy ORM models
├── schemas/                 # Pydantic schemas (Create/Response/Update)
├── agent/                   # LangGraph agent
│   ├── graph.py             # StateGraph definition
│   ├── nodes/               # Graph nodes (functions)
│   └── tools/               # Agent tools (account lookup, etc.)
├── rag/                     # RAG pipeline
│   ├── embeddings.py        # Embedding generation
│   ├── chunker.py           # Document chunking
│   └── retriever.py         # Vector similarity search
└── database.py              # Async engine + session factory
tests/
├── unit/                    # Testes com mock
└── integration/             # Testes com Testcontainers + respx
scripts/
└── ingest.py                # Ingestao de documentos para RAG
```

## Configuration

`.env` + `pydantic-settings`. Variables:

- `DATABASE_URL` — connection string PostgreSQL async (porta 5433)
- `GEMINI_API_KEY` — API key do Google Gemini
- `GEMINI_MODEL` — modelo LLM (default: gemini-pro)
- `GEMINI_EMBEDDING_MODEL` — modelo de embeddings (default: models/embedding-001)
- `LOG_LEVEL` — nivel de log (default: DEBUG)
- `ENVIRONMENT` — ambiente (development/test/production)

## Key Patterns

- Dependency Injection via `Depends()`
- async SQLAlchemy sessions with `AsyncSession`
- Pydantic schema separation (Create/Response/Update)
- Testcontainers para integration tests
- respx para mock HTTP/LLM calls
- structlog para logging JSON estruturado
- Alembic para database migrations

## Docker

Docker Compose com 4 servicos (portas com offset +1 do spring-mastery-lab):

| Servico | Container | Porta |
|---------|-----------|-------|
| PostgreSQL 16 + pgvector | postgres_ai_lab | 5433 |
| Prometheus | prometheus_ai | 9091 |
| Grafana | grafana_ai_lab | 3001 |
| Loki | loki_ai | 3101 |

## CI/CD

GitHub Actions pipeline at `.github/workflows/ci.yml`:
- **Jobs**: lint → test → quality (placeholder) → docker
- **Trigger**: push and pull_request to `main`
- **Test**: service container pgvector/pgvector:pg16, pytest with coverage

## Testing

- **Unit tests** (`tests/unit/`): mock de dependencias, sem I/O externo
- **Integration tests** (`tests/integration/`): Testcontainers (PostgreSQL real), respx (mock HTTP para LLM)
- **Coverage**: pytest-cov com relatorio HTML
