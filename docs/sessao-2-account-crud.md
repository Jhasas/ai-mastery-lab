# Sessao 2 - Account CRUD Completo

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA
**Fase**: 1 (API Bancaria FastAPI)
**Passos**: 1.1 a 1.6
**Pre-requisito**: Sessao 1 completa (pyproject.toml, docker-compose, CLAUDE.md)
**Modo**: Pair programming - orientar, NAO alterar codigo

## Objetivo

Criar o CRUD completo de Account: settings, database, model, schema, repository, service, router, exception handler, e testes (unit + integration com Testcontainers).

Equivalente ao que foi feito no spring-mastery-lab com CustomerController/CustomerService, mas com dominio bancario.

---

## Passo 1.1 - Settings e Database

### app/config/settings.py

Equivalente ao `ApiProperties.java` (Records) do spring-mastery-lab.

Criar classe `Settings(BaseSettings)` com:
- `database_url: str` (default: postgresql+asyncpg://postgres:postgres@localhost:5433/ai_mastery_lab)
- `gemini_api_key: str = ""` (vazio por padrao, obrigatorio apenas nas fases 2+)
- `gemini_model: str = "gemini-pro"`
- `gemini_embedding_model: str = "models/embedding-001"`
- `log_level: str = "INFO"`
- `environment: str = "development"`
- `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")`

Funcao `get_settings()` com `@lru_cache` (singleton, igual @Bean do Spring):
```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### app/config/database.py

Equivalente ao DataSource + EntityManager do Spring.

Criar:
- `engine = create_async_engine(settings.database_url, echo=True)` em dev
- `async_session_factory = async_sessionmaker(engine, expire_on_commit=False)`
- `Base = declarative_base()` (classe base de todos os models, equivalente ao @MappedSuperclass)
- `async def get_db() -> AsyncGenerator[AsyncSession, None]` (dependency que faz yield de session e fecha automaticamente - equivalente ao @Transactional)
- `async def init_db()` que cria tabelas via `Base.metadata.create_all` (para dev; producao usa Alembic)

### Arquivos __init__.py

Criar: `app/__init__.py`, `app/config/__init__.py` (todos vazios)

---

## Passo 1.2 - Account Model e Schema

### app/models/account.py

Equivalente a `Customer.java` (@Entity) do spring-mastery-lab, mas com dominio bancario.

SQLAlchemy 2.0 style (Mapped annotations):

| Campo | Tipo | Constraints | Equivalente Spring |
|-------|------|-------------|-------------------|
| `id` | `Mapped[int]` | PK, auto-increment | `@Id @GeneratedValue(IDENTITY)` |
| `owner_name` | `Mapped[str]` | NotNull | `@NotBlank` |
| `owner_document` | `Mapped[str]` | Unique, NotNull (CPF) | `@Column(unique=true)` |
| `balance` | `Mapped[Decimal]` | Default 0, precision(15,2) | `BigDecimal` |
| `account_type` | `Mapped[str]` | NotNull (CORRENTE/POUPANCA) | `@Enumerated` |
| `created_at` | `Mapped[datetime]` | server_default=func.now() | `@CreatedDate` |
| `updated_at` | `Mapped[datetime | None]` | onupdate=func.now() | `@LastModifiedDate` |
| `is_active` | `Mapped[bool]` | Default True | campo booleano |

`__tablename__ = "accounts"`

### app/models/__init__.py

Importar `Base` do database.py e `Account` para que Alembic descubra os models.

### app/schemas/account.py

Equivalente aos DTOs. Pydantic v2 com separacao Create/Response/Update:

**AccountCreate(BaseModel)**:
- `owner_name: str` com `Field(min_length=1)` (equivalente @NotBlank)
- `owner_document: str` com `Field(pattern=r"^\d{11}$")` (CPF: 11 digitos)
- `account_type: Literal["CORRENTE", "POUPANCA"]`
- `initial_balance: Decimal = Field(default=Decimal("0"), ge=0)`

**AccountResponse(BaseModel)**:
- Todos os campos do model
- `model_config = ConfigDict(from_attributes=True)` (equivalente a converter Entity -> DTO)

**AccountUpdate(BaseModel)**:
- `owner_name: str | None = None`
- `is_active: bool | None = None`
- Campos opcionais para partial update (PATCH)

### app/schemas/__init__.py

Vazio.

---

## Passo 1.3 - Account Repository

### app/repositories/account_repository.py

Equivalente ao `CustomerRepository extends JpaRepository` do spring-mastery-lab, mas explicito (sem Spring Data magic).

Classe `AccountRepository` com `__init__(self, session: AsyncSession)`:

| Metodo | SQL equivalente | Retorno |
|--------|----------------|---------|
| `create(account: Account)` | INSERT | `Account` |
| `get_by_id(account_id: int)` | SELECT WHERE id = ? | `Account \| None` |
| `get_by_document(document: str)` | SELECT WHERE owner_document = ? | `Account \| None` |
| `get_all()` | SELECT * | `list[Account]` |
| `update(account: Account)` | UPDATE (session.merge) | `Account` |
| `delete(account_id: int)` | DELETE WHERE id = ? | `bool` |

Todos os metodos sao `async def` e usam `await session.execute(select(...))`.

### app/repositories/__init__.py

Vazio.

---

## Passo 1.4 - Account Service + Exceptions

### app/services/account_service.py

Equivalente ao `CustomerService.java` do spring-mastery-lab.

Classe `AccountService` com `AccountRepository` injetado:

| Metodo | Logica | Exception |
|--------|--------|-----------|
| `create_account(data: AccountCreate)` | Verifica CPF duplicado → cria Account com initial_balance | `DuplicateDocumentException` se CPF existe |
| `get_account(account_id: int)` | Busca por ID | `AccountNotFoundException` se nao encontrar |
| `get_all_accounts()` | Lista todos | - |
| `update_account(account_id: int, data: AccountUpdate)` | Busca → atualiza apenas campos nao-None (partial update, igual PATCH do spring-mastery-lab) | `AccountNotFoundException` |
| `delete_account(account_id: int)` | Busca → deleta | `AccountNotFoundException` |

Usar structlog para logging com timing (mesmo padrao do spring-mastery-lab: `start = time.time()`, log elapsed):
```python
import structlog
logger = structlog.get_logger()

async def get_account(self, account_id: int) -> Account:
    start = time.time()
    account = await self.repository.get_by_id(account_id)
    if not account:
        raise AccountNotFoundException(account_id)
    elapsed = (time.time() - start) * 1000
    logger.info("account_fetched", account_id=account_id, elapsed_ms=round(elapsed, 2))
    return account
```

### app/exceptions/handlers.py

Equivalente ao `GlobalExceptionHandler.java` do spring-mastery-lab.

**Exceptions customizadas**:
- `AccountNotFoundException(Exception)` - campo `account_id`
- `InsufficientBalanceException(Exception)` - campos `account_id`, `balance`, `amount`
- `DuplicateDocumentException(Exception)` - campo `document`

**Exception handlers** (registrados no FastAPI app):
- `AccountNotFoundException` → 404 `{"error": "Not Found", "message": "Account not found: {id}", "status": 404}`
- `InsufficientBalanceException` → 400 `{"error": "Bad Request", "message": "...", "status": 400}`
- `DuplicateDocumentException` → 409 `{"error": "Conflict", "message": "...", "status": 409}`
- `RequestValidationError` → 422 com detalhes dos campos (automatico do FastAPI, mas customizar formato)
- `Exception` (catch-all) → 500 `{"error": "Internal Server Error", "message": "...", "status": 500}`

### Testes unitarios: tests/unit/test_account_service.py

Equivalente ao `CustomerServiceTest.java` do spring-mastery-lab.

Usar `unittest.mock.AsyncMock` para mockar `AccountRepository`:

| Teste | O que valida |
|-------|-------------|
| `test_should_create_account_successfully` | Chama repository.create, retorna account |
| `test_should_raise_not_found_when_account_does_not_exist` | repository.get_by_id retorna None → AccountNotFoundException |
| `test_should_raise_error_when_duplicate_cpf` | repository.get_by_document retorna existente → DuplicateDocumentException |
| `test_should_update_only_provided_fields` | AccountUpdate com apenas owner_name → balance/is_active nao mudam |
| `test_should_delete_account_successfully` | Chama repository.delete |
| `test_should_raise_not_found_when_deleting_nonexistent` | repository.get_by_id retorna None → AccountNotFoundException |

Padrao AAA (Arrange-Act-Assert), `@pytest.mark.asyncio` em todos.

---

## Passo 1.5 - Account Router + Main App

### app/routers/account_router.py

Equivalente ao `CustomerController.java` do spring-mastery-lab.

`router = APIRouter(prefix="/accounts", tags=["Accounts"])`

| Endpoint | Metodo | Status | Descricao |
|----------|--------|--------|-----------|
| `POST /` | create_account | 201 | Cria conta, recebe AccountCreate, retorna AccountResponse |
| `GET /` | list_accounts | 200 | Lista todas as contas |
| `GET /{account_id}` | get_account | 200/404 | Busca conta por ID |
| `PATCH /{account_id}` | update_account | 200/404 | Partial update |
| `DELETE /{account_id}` | delete_account | 200/404 | Deleta conta |

Injecao via `Depends()`:
```python
async def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    repository = AccountRepository(db)
    return AccountService(repository)

@router.post("/", status_code=201, response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    service: AccountService = Depends(get_account_service)
):
    account = await service.create_account(data)
    return account
```

### app/main.py

Equivalente ao `FundamentalsApplication.java` + router registration.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # cria tabelas no startup
    yield

app = FastAPI(title="AI Mastery Lab", version="0.1.0", lifespan=lifespan)
app.include_router(account_router)
# Registrar exception handlers
```

### Validacao manual

```bash
uvicorn app.main:app --reload
# Abrir http://localhost:8000/docs
# Testar POST /accounts, GET /accounts, etc. via Swagger UI
```

---

## Passo 1.6 - Testes de Integracao com Testcontainers

### tests/conftest.py

Equivalente ao `TestcontainersConfiguration.java` + `@ServiceConnection`.

**Fixtures compartilhadas**:

```python
# Fixture scope="session": sobe container PostgreSQL UMA VEZ para todos os testes
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield postgres

# Fixture scope="session": engine conectado ao container
@pytest.fixture(scope="session")
async def async_engine(postgres_container):
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

# Fixture per-test: session com rollback automatico (cada teste comeca limpo)
@pytest.fixture
async def db_session(async_engine):
    async with async_sessionmaker(async_engine)() as session:
        yield session
        await session.rollback()

# Fixture: httpx.AsyncClient contra o app FastAPI com DB override
@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

### tests/integration/test_account_router.py

Equivalente ao `CustomerControllerTest.java` (@WebMvcTest) do spring-mastery-lab.

| Teste | Request | Assertacao |
|-------|---------|-----------|
| `test_should_return_201_when_creating_account` | POST / com body valido | status 201, response tem id e owner_name |
| `test_should_return_200_and_account_when_id_exists` | POST + GET /{id} | status 200, dados corretos |
| `test_should_return_404_when_account_does_not_exist` | GET /99999 | status 404, error message |
| `test_should_return_422_when_owner_name_is_blank` | POST / com name="" | status 422, detalhe do campo |
| `test_should_return_422_when_cpf_format_is_invalid` | POST / com document="abc" | status 422 |
| `test_should_return_200_when_listing_all_accounts` | POST 2 contas + GET / | status 200, lista com 2 |
| `test_should_return_200_when_partial_update_succeeds` | POST + PATCH /{id} com novo nome | status 200, nome atualizado, balance inalterado |
| `test_should_return_409_when_duplicate_cpf` | POST mesma + POST com mesmo CPF | status 409 |

Todos usam `httpx.AsyncClient` (equivalente ao MockMvc/TestClient).

### Arquivos __init__.py

Criar: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`

### Validacao

```bash
pytest tests/ -v
# Todos os testes devem passar
# Testcontainers sobe PostgreSQL automaticamente
```

---

## Entrega da Sessao 2

Ao final, o projeto deve ter:
```
ai-mastery-lab/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── account.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── account.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── account_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── account_service.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── account_router.py
│   └── exceptions/
│       ├── __init__.py
│       └── handlers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   └── test_account_service.py
│   └── integration/
│       ├── __init__.py
│       └── test_account_router.py
└── (arquivos da sessao 1)
```

Deve ser possivel:
- `uvicorn app.main:app --reload` → Swagger em `/docs` com endpoints de Account
- `pytest tests/` → todos passam (unit + integration com Testcontainers)
- POST com CPF invalido → 422, POST com CPF duplicado → 409, GET inexistente → 404
