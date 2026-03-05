# Sessao 1 - Bootstrap do Projeto

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA usando Python/FastAPI + LangChain + LangGraph + RAG (pgvector)
**Local**: `/Users/lucastavares/Projetos/code-repository/ai-mastery-lab/`
**Modo**: Pair programming - o mentor orienta, o usuario implementa. NAO altere codigo diretamente.
**Referencia**: Seguir padroes do `spring-mastery-lab` (mesmo repositorio)

## Pre-requisitos

- Python 3.12+ instalado
- Docker + Docker Compose instalados
- Diretorio `ai-mastery-lab/` criado

## Plano desta sessao

Criar a base do projeto: dependencias, infraestrutura Docker, CLAUDE.md e CI pipeline.

---

## Passo 0.1 - pyproject.toml, .gitignore, .env

### pyproject.toml

Equivalente ao `pom.xml` do spring-mastery-lab. Organizar dependencias em grupos:

**[project]**: name `ai-mastery-lab`, version `0.1.0`, requires-python `>=3.12`

**dependencies** (core):
- `fastapi[standard]` - framework web (equivalente Spring Boot Web)
- `uvicorn[standard]` - servidor ASGI (equivalente Tomcat)
- `sqlalchemy[asyncio]` - ORM async (equivalente Hibernate/JPA)
- `asyncpg` - driver PostgreSQL async (equivalente JDBC)
- `pydantic>=2.0` - validacao (equivalente Bean Validation)
- `pydantic-settings` - configuracao via .env (equivalente @ConfigurationProperties)
- `alembic` - migrations (equivalente Flyway)
- `httpx` - HTTP client async (equivalente WebClient)

**dependencies** (observabilidade):
- `structlog` - logging estruturado JSON (equivalente Logback + Loki)
- `prometheus-fastapi-instrumentator` - metricas (equivalente Micrometer + Actuator)

**dependencies** (IA - usadas a partir da Fase 2):
- `langchain-core` - core do LangChain
- `langchain-google-genai` - integracao Gemini
- `langgraph` - grafos de agentes
- `langchain-text-splitters` - chunking para RAG
- `pgvector` - integracao SQLAlchemy com pgvector

**[project.optional-dependencies] dev**:
- `pytest` - framework de testes (equivalente JUnit 5)
- `pytest-asyncio` - suporte async nos testes
- `pytest-cov` - cobertura de testes (equivalente JaCoCo)
- `respx` - mock de HTTP requests (equivalente WireMock)
- `testcontainers[postgres]` - Testcontainers Python
- `ruff` - linter + formatter (equivalente Checkstyle + SpotBugs)

**[tool.pytest.ini_options]**: asyncio_mode = "auto", testpaths = ["tests"]
**[tool.ruff]**: line-length = 100, target-version = "py312"

### .gitignore

Padroes Python:
```
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.env
.coverage
htmlcov/
*.egg-info/
dist/
build/
.idea/
.vscode/
.DS_Store
.ruff_cache/
```

### .env.example (commitado)

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ai_mastery_lab
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-pro
GEMINI_EMBEDDING_MODEL=models/embedding-001
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### .env (gitignored)

Copiar de `.env.example` e preencher com valores reais.

### Validacao

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Deve instalar sem erros.

---

## Passo 0.2 - Docker Compose

### docker-compose.yml

4 servicos (portas com offset +1 para evitar conflito com spring-mastery-lab):

**postgres-lab**:
- Imagem: `pgvector/pgvector:pg16` (PostgreSQL 16 com pgvector pre-instalado)
- Container name: `postgres_ai_lab`
- Porta: **5433:5432**
- Environment: POSTGRES_DB=ai_mastery_lab, POSTGRES_USER=postgres, POSTGRES_PASSWORD=postgres
- Volume: `postgres-ai-lab:/var/lib/postgresql/data`
- Healthcheck: `pg_isready -U postgres` (interval 10s, timeout 5s, retries 5)

**prometheus**:
- Imagem: `prom/prometheus`
- Container name: `prometheus_ai`
- Porta: **9091:9090**
- Volume mount: `./prometheus.yml:/etc/prometheus/prometheus.yml`

**grafana**:
- Imagem: `grafana/grafana`
- Container name: `grafana_ai_lab`
- Porta: **3001:3000**
- Environment: GF_SECURITY_ADMIN_PASSWORD=admin
- Volume: `grafana-ai:/var/lib/grafana`

**loki**:
- Imagem: `grafana/loki:3.0.0`
- Container name: `loki_ai`
- Porta: **3101:3100**

**volumes**: postgres-ai-lab, grafana-ai

### prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ai-mastery-lab'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['host.docker.internal:8000']
```

### Validacao

```bash
docker compose up -d postgres-lab
docker compose ps  # deve mostrar postgres_ai_lab healthy
```

---

## Passo 0.3 - CLAUDE.md

Criar `CLAUDE.md` na raiz do projeto com:

### Secoes obrigatorias (seguir padrao do spring-mastery-lab/CLAUDE.md):

**Project Overview**:
- AI Mastery Lab - API bancaria com agente IA (LangChain/LangGraph), RAG (pgvector), padroes production-grade
- Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- Portfolio de Senior AI Engineer - Banco BV

**Build & Run Commands**:
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

**Architecture**: Tres camadas (routers -> services -> repositories) + agent layer (graph -> nodes -> tools) + RAG layer (embeddings -> chunker -> retriever)

**Estrutura de diretorios**: listar a arvore completa do projeto

**Configuration**: `.env` + `pydantic-settings`. Listar variaveis: DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, LOG_LEVEL, ENVIRONMENT

**Key Patterns**:
- Dependency Injection via `Depends()`
- async SQLAlchemy sessions
- Pydantic schema separation (Create/Response/Update)
- Testcontainers para integration tests
- respx para mock HTTP/LLM
- structlog para logging JSON

**Docker**: listar servicos e portas (5433, 9091, 3001, 3101)

**Testing**: explicar estrategia (unit com mock, integration com Testcontainers + respx)

---

## Passo 0.4 - GitHub Actions CI

### .github/workflows/ci.yml

4 jobs em cadeia (igual spring-mastery-lab):

**lint** (runs-on ubuntu-latest):
- Checkout, setup Python 3.12, pip install ruff
- `ruff check app/ tests/`
- `ruff format --check app/ tests/`

**test** (needs: lint):
- Service container: `pgvector/pgvector:pg16` (porta 5432, healthcheck)
- Checkout, setup Python 3.12, pip install -e ".[dev]"
- `pytest --cov=app --cov-report=xml`
- Environment: DATABASE_URL apontando para service container, GEMINI_API_KEY=test-key, ENVIRONMENT=test

**quality** (needs: test):
- Placeholder para SonarQube

**docker** (needs: quality):
- Checkout, `docker build -t ai-mastery-lab:latest .`

### Validacao

Commit e push - verificar pipeline verde no GitHub.

---

## Entrega da Sessao 1

Ao final, o projeto deve ter:
```
ai-mastery-lab/
├── .github/workflows/ci.yml
├── docs/
│   └── (arquivos de sessao)
├── pyproject.toml
├── docker-compose.yml
├── prometheus.yml
├── .env.example
├── .env              (gitignored)
├── .gitignore
├── CLAUDE.md
└── .venv/            (gitignored)
```

E deve ser possivel:
- `pip install -e ".[dev]"` sem erros
- `docker compose up -d postgres-lab` sobe e healthcheck OK
- `ruff check` roda (sem arquivos Python ainda, mas funciona)
