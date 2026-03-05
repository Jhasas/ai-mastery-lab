# Sessao 3 - Transactions e Transfer Logic

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA
**Fase**: 1 (API Bancaria FastAPI)
**Passo**: 1.7
**Pre-requisito**: Sessao 2 completa (Account CRUD funcional com testes)
**Modo**: Pair programming - orientar, NAO alterar codigo

## Objetivo

Criar o modelo de Transaction e a logica de transferencia entre contas com validacao de saldo. Esta e a regra de negocio mais critica do projeto - a transferencia deve ser atomica (debitar origem e creditar destino na mesma transacao de banco).

Na Fase 3, o agente LangGraph vai usar essa logica via tool `transfer()`.

---

## Passo 1.7 - Transaction Model + Transfer

### app/models/transaction.py

| Campo | Tipo | Constraints | Descricao |
|-------|------|-------------|-----------|
| `id` | `Mapped[int]` | PK, auto-increment | ID unico |
| `account_id` | `Mapped[int]` | FK → accounts.id, NotNull | Conta da transacao |
| `type` | `Mapped[str]` | NotNull | DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT |
| `amount` | `Mapped[Decimal]` | NotNull, precision(15,2) | Valor da transacao (sempre positivo) |
| `description` | `Mapped[str \| None]` | Nullable | Descricao opcional |
| `related_account_id` | `Mapped[int \| None]` | Nullable | Para transfers: a outra conta envolvida |
| `created_at` | `Mapped[datetime]` | server_default=func.now() | Data da transacao |

`__tablename__ = "transactions"`

ForeignKey para accounts: `ForeignKey("accounts.id")`

**Atualizar** `app/models/__init__.py` para importar Transaction.

### app/schemas/transaction.py

**TransferRequest(BaseModel)**:
- `origin_account_id: int`
- `destination_account_id: int`
- `amount: Decimal = Field(gt=0)` (deve ser positivo)
- `description: str | None = None`

**TransactionResponse(BaseModel)**:
- Todos os campos do model
- `model_config = ConfigDict(from_attributes=True)`

**TransferResponse(BaseModel)**:
- `origin_transaction: TransactionResponse`
- `destination_transaction: TransactionResponse`
- `message: str` (ex: "Transferencia de R$ 1.000,00 realizada com sucesso")

### app/repositories/transaction_repository.py

Classe `TransactionRepository` com `AsyncSession`:

| Metodo | Descricao |
|--------|-----------|
| `create(transaction: Transaction)` | Persiste transacao |
| `get_by_account_id(account_id: int, limit: int = 10)` | Lista transacoes de uma conta, ordenadas por created_at DESC |
| `get_by_id(transaction_id: int)` | Busca por ID |

### app/services/transaction_service.py

**METODO CRITICO**: `execute_transfer(data: TransferRequest) -> TransferResponse`

Logica passo a passo (tudo dentro de UMA transacao DB):

1. Buscar conta origem → `AccountNotFoundException` se nao existir
2. Buscar conta destino → `AccountNotFoundException` se nao existir
3. Validar saldo: `origin.balance >= data.amount` → `InsufficientBalanceException` se nao
4. Debitar origem: `origin.balance -= data.amount`
5. Creditar destino: `destination.balance += data.amount`
6. Criar Transaction TRANSFER_OUT (account_id=origin, related_account_id=destination)
7. Criar Transaction TRANSFER_IN (account_id=destination, related_account_id=origin)
8. Commit (via session)
9. Retornar TransferResponse com ambas transacoes

```python
async def execute_transfer(self, data: TransferRequest) -> TransferResponse:
    start = time.time()

    origin = await self.account_repo.get_by_id(data.origin_account_id)
    if not origin:
        raise AccountNotFoundException(data.origin_account_id)

    destination = await self.account_repo.get_by_id(data.destination_account_id)
    if not destination:
        raise AccountNotFoundException(data.destination_account_id)

    if origin.balance < data.amount:
        raise InsufficientBalanceException(origin.id, origin.balance, data.amount)

    origin.balance -= data.amount
    destination.balance += data.amount

    tx_out = Transaction(
        account_id=origin.id,
        type="TRANSFER_OUT",
        amount=data.amount,
        description=data.description,
        related_account_id=destination.id
    )
    tx_in = Transaction(
        account_id=destination.id,
        type="TRANSFER_IN",
        amount=data.amount,
        description=data.description,
        related_account_id=origin.id
    )

    await self.transaction_repo.create(tx_out)
    await self.transaction_repo.create(tx_in)

    elapsed = (time.time() - start) * 1000
    logger.info("transfer_executed",
        origin_id=origin.id, destination_id=destination.id,
        amount=str(data.amount), elapsed_ms=round(elapsed, 2)
    )

    return TransferResponse(
        origin_transaction=tx_out,
        destination_transaction=tx_in,
        message=f"Transferencia de R$ {data.amount} realizada com sucesso"
    )
```

**Segundo metodo**: `list_transactions(account_id: int, limit: int = 10) -> list[Transaction]`
- Busca conta (404 se nao existir) → lista transacoes ordenadas por data DESC

### app/routers/transaction_router.py

`router = APIRouter(prefix="/transactions", tags=["Transactions"])`

| Endpoint | Metodo | Status | Descricao |
|----------|--------|--------|-----------|
| `POST /transfer` | execute_transfer | 201 | Executa transferencia, retorna TransferResponse |
| `GET /{account_id}` | list_transactions | 200 | Lista transacoes de uma conta |

Injecao via `Depends()` (mesmo padrao do account_router):
```python
async def get_transaction_service(db: AsyncSession = Depends(get_db)) -> TransactionService:
    account_repo = AccountRepository(db)
    transaction_repo = TransactionRepository(db)
    return TransactionService(account_repo, transaction_repo)
```

**Atualizar** `app/main.py`: `app.include_router(transaction_router)`

---

## Testes

### tests/unit/test_transaction_service.py

Mockar `AccountRepository` e `TransactionRepository` com `AsyncMock`:

| Teste | Cenario | Assertacao |
|-------|---------|-----------|
| `test_should_execute_transfer_when_balance_sufficient` | Origem com R$ 5000, transferir R$ 1000 | Saldos atualizados, 2 transacoes criadas |
| `test_should_raise_insufficient_balance` | Origem com R$ 500, transferir R$ 1000 | `InsufficientBalanceException` |
| `test_should_raise_not_found_when_origin_missing` | Origem nao existe | `AccountNotFoundException` |
| `test_should_raise_not_found_when_destination_missing` | Destino nao existe | `AccountNotFoundException` |
| `test_should_create_transfer_out_and_transfer_in` | Transfer valida | Verifica tipos TRANSFER_OUT e TRANSFER_IN, related_account_id correto |

### tests/integration/test_transaction_router.py

Testes end-to-end com Testcontainers:

| Teste | Setup | Request | Assertacao |
|-------|-------|---------|-----------|
| `test_should_return_201_when_transfer_succeeds` | Criar 2 contas (R$ 5000 cada) | POST /transfer R$ 1000 | 201, message com "sucesso" |
| `test_should_return_400_when_insufficient_balance` | Criar conta com R$ 100 | POST /transfer R$ 500 | 400, "Insufficient balance" |
| `test_should_return_404_when_origin_not_found` | Nenhuma conta | POST /transfer origin=999 | 404 |
| `test_should_return_200_when_listing_transactions` | Criar contas + transfer | GET /transactions/{id} | 200, lista com transacao |
| `test_should_update_balances_after_transfer` | Criar 2 contas R$ 5000 | POST /transfer R$ 1000 + GET contas | Origem R$ 4000, Destino R$ 6000 |

---

## Entrega da Sessao 3

Ao final, alem do que ja existia:
```
app/
├── models/
│   └── transaction.py          # NOVO
├── schemas/
│   └── transaction.py          # NOVO
├── repositories/
│   └── transaction_repository.py  # NOVO
├── services/
│   └── transaction_service.py  # NOVO
├── routers/
│   └── transaction_router.py   # NOVO
tests/
├── unit/
│   └── test_transaction_service.py  # NOVO
├── integration/
│   └── test_transaction_router.py   # NOVO
```

Deve ser possivel:
- POST /transactions/transfer com saldo suficiente → 201
- POST /transactions/transfer com saldo insuficiente → 400
- GET /transactions/{account_id} → lista transacoes
- `pytest tests/` → todos passam (incluindo testes da sessao 2)
