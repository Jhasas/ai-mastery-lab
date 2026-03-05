# Sessao 4 - Observabilidade, Alembic e Dockerfile

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA
**Fase**: 1 (API Bancaria FastAPI) - FINALIZACAO
**Passos**: 1.8, 1.9, 1.10
**Pre-requisito**: Sessao 3 completa (Account + Transaction CRUD funcional)
**Modo**: Pair programming - orientar, NAO alterar codigo

## Objetivo

Finalizar a Fase 1 com observabilidade (logging estruturado + metricas Prometheus), migrations com Alembic, e Dockerfile para containerizacao. Equivalente ao que foi feito no spring-mastery-lab com logback-spring.xml + Micrometer + Prometheus.

---

## Passo 1.8 - Observabilidade

### app/observability/logging.py

Equivalente ao `logback-spring.xml` do spring-mastery-lab.

Configurar structlog para logging estruturado:

```python
import structlog

def setup_logging(log_level: str = "INFO", environment: str = "development"):
    """Configura structlog. JSON em prod, console colorido em dev."""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

Em dev, output colorido no console. Em prod, JSON puro (pronto para Loki/Elasticsearch).

Equivalencias com spring-mastery-lab:

| spring-mastery-lab | ai-mastery-lab |
|-------------------|----------------|
| `logback-spring.xml` CONSOLE appender | structlog ConsoleRenderer |
| `logback-spring.xml` LOKI appender | structlog JSONRenderer (Loki le JSON) |
| `%X{traceId}` no pattern | `structlog.contextvars` (adicionar trace_id manualmente) |
| `@Slf4j` / `LoggerFactory` | `structlog.get_logger()` |

### app/observability/metrics.py

Equivalente ao Micrometer + `MeterRegistry` do spring-mastery-lab.

```python
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram

# Metricas automaticas de HTTP (equivalente ao actuator/prometheus do Spring)
instrumentator = Instrumentator()

# Custom counters (equivalente ao MeterRegistry.counter() do spring-mastery-lab)
transfer_requests_total = Counter(
    "transfer_requests_total",
    "Total de transferencias realizadas",
    ["status"]  # labels: success, failed
)

transfer_amount_total = Counter(
    "transfer_amount_total",
    "Valor total transferido em reais"
)

transfer_duration_seconds = Histogram(
    "transfer_duration_seconds",
    "Duracao das transferencias"
)
```

Instrumentar `TransactionService.execute_transfer` com:
```python
with transfer_duration_seconds.time():
    # logica da transferencia
    ...
transfer_requests_total.labels(status="success").inc()
transfer_amount_total.inc(float(amount))
```

### Atualizar app/main.py

```python
from app.observability.logging import setup_logging
from app.observability.metrics import instrumentator

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.environment)
    await init_db()
    yield

app = FastAPI(...)
instrumentator.instrument(app).expose(app, endpoint="/metrics")
```

### Validacao

```bash
# Subir app
uvicorn app.main:app --reload

# Fazer algumas requests
curl http://localhost:8000/accounts
curl -X POST http://localhost:8000/transactions/transfer -H "Content-Type: application/json" -d '...'

# Verificar metricas
curl http://localhost:8000/metrics | grep transfer

# Subir Prometheus e verificar targets
docker compose up -d prometheus
# Abrir http://localhost:9091 → Targets → ai-mastery-lab deve estar UP
```

---

## Passo 1.9 - Alembic Migrations

Equivalente ao Flyway do spring-mastery-lab / GIP core-back.

### Inicializar Alembic

```bash
alembic init alembic
```

### alembic.ini

Modificar `sqlalchemy.url` para ler do environment:
```ini
# Sera sobrescrito pelo env.py
sqlalchemy.url = postgresql://postgres:postgres@localhost:5433/ai_mastery_lab
```

### alembic/env.py

Configurar para:
1. Ler `DATABASE_URL` do environment (substituir `asyncpg` por `psycopg2` para Alembic sync)
2. Importar `Base.metadata` de `app.models` (para autogenerate funcionar)
3. Importar todos os models

```python
from app.config.database import Base
from app.models import account, transaction  # importar para discovery

target_metadata = Base.metadata
```

**IMPORTANTE**: Alembic roda sync (nao async). Precisa converter a URL de `asyncpg` para `psycopg2` ou usar `psycopg2` apenas no alembic.ini. Alternativa: instalar `psycopg2-binary` como dependencia adicional.

Adicionar `psycopg2-binary` ao pyproject.toml nas dependencias dev.

### Gerar primeira migration

```bash
alembic revision --autogenerate -m "create accounts and transactions tables"
```

Revisar o arquivo gerado em `alembic/versions/`. Deve conter:
- `CREATE TABLE accounts (...)` com todos os campos
- `CREATE TABLE transactions (...)` com FK para accounts

### Aplicar migration

```bash
alembic upgrade head
```

### Atualizar app/main.py

Remover `init_db()` que usa `create_all`. Em producao, apenas Alembic gerencia o schema.
Em dev/test, manter `create_all` como fallback.

---

## Passo 1.10 - Dockerfile

Equivalente ao `Dockerfile` multi-stage do spring-mastery-lab.

```dockerfile
# Stage 1: Builder - instala dependencias
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Stage 2: Runtime - copia app e dependencias
FROM python:3.12-slim
WORKDIR /app

# Copiar dependencias instaladas
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar codigo
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY data/ ./data/

# Porta
EXPOSE 8000

# Non-root user (mesmo padrao do spring-mastery-lab)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Validacao

```bash
docker build -t ai-mastery-lab:latest .
# Deve buildar sem erros

# Testar rodando
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5433/ai_mastery_lab \
  ai-mastery-lab:latest
# Abrir http://localhost:8000/docs
```

---

## Entrega da Sessao 4 (Fase 1 COMPLETA)

Ao final, alem do que ja existia:
```
app/
├── observability/
│   ├── __init__.py
│   ├── logging.py              # NOVO
│   └── metrics.py              # NOVO
alembic/
├── env.py                      # NOVO
├── versions/
│   └── 001_create_tables.py    # NOVO
├── alembic.ini                 # NOVO
Dockerfile                      # NOVO
```

**Fase 1 completa**. O projeto agora tem:
- CRUD Account + Transaction com validacao de saldo
- Transferencias atomicas
- Testes unit + integration (Testcontainers)
- Logging estruturado (structlog)
- Metricas Prometheus em `/metrics`
- Migrations com Alembic
- Dockerfile multi-stage
- CI pipeline (GitHub Actions)
- Docker Compose com PostgreSQL, Prometheus, Grafana, Loki
