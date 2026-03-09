import time

import structlog

from app.exceptions.handlers import AccountNotFoundException, DuplicateDocumentException
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate

logger = structlog.get_logger()


class AccountService:
    def __init__(self, repository: AccountRepository):
        self.repository = repository

    async def create_account(self, data: AccountCreate) -> Account:
        start = time.time()

        existing = await self.repository.get_by_document(data.owner_document)
        if existing:
            raise DuplicateDocumentException(data.owner_document)

        account = Account(
            owner_name=data.owner_name,
            owner_document=data.owner_document,
            balance=data.initial_balance,
            account_type=data.account_type,
        )

        created = await self.repository.create(account)
        elapsed = (time.time() - start) * 1000
        logger.info("account_created", account_id=created.id, elapsed_ms=round(elapsed, 2))
        return created

    async def get_account(self, account_id: int) -> Account:
        start = time.time()
        account = await self.repository.get_by_id(account_id)
        if not account:
            raise AccountNotFoundException(account_id)
        elapsed = (time.time() - start) * 1000
        logger.info("account_fetched", account_id=account_id, elapsed_ms=round(elapsed, 2))
        return account

    async def get_all_accounts(self) -> list[Account]:
        return await self.repository.get_all()

    async def update_account(self, account_id: int, data: AccountUpdate) -> Account:
        start = time.time()
        account = await self.repository.get_by_id(account_id)
        if not account:
            raise AccountNotFoundException(account_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)

        updated = await self.repository.update(account)
        elapsed = (time.time() - start) * 1000
        logger.info("account_updated", account_id=account_id, elapsed_ms=round(elapsed, 2))
        return updated

    async def delete_account(self, account_id: int) -> None:
        account = await self.repository.get_by_id(account_id)
        if not account:
            raise AccountNotFoundException(account_id)
        await self.repository.delete(account_id)
        logger.info("account_deleted", account_id=account_id)
