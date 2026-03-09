import time

import structlog

from app.exceptions.handlers import AccountNotFoundException, InsufficientBalanceException
from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import TransferRequest, TransferResponse

logger = structlog.get_logger()


class TransactionService:
    def __init__(self, account_repo: AccountRepository, transaction_repo: TransactionRepository):
        self.account_repo = account_repo
        self.transaction_repo = transaction_repo

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
            related_account_id=destination.id,
        )
        tx_in = Transaction(
            account_id=destination.id,
            type="TRANSFER_IN",
            amount=data.amount,
            description=data.description,
            related_account_id=origin.id,
        )

        await self.transaction_repo.create(tx_out)
        await self.transaction_repo.create(tx_in)

        elapsed = (time.time() - start) * 1000
        logger.info(
            "transfer_executed",
            origin_id=origin.id,
            destination_id=destination.id,
            amount=str(data.amount),
            elapsed_ms=round(elapsed, 2),
        )

        return TransferResponse(
            origin_transaction=tx_out,
            destination_transaction=tx_in,
            message=f"Transferencia de R$ {data.amount} realizada com sucesso",
        )

    async def list_transactions(self, account_id: int, limit: int = 10) -> list[Transaction]:
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundException(account_id)
        return await self.transaction_repo.get_by_account_id(account_id, limit)
