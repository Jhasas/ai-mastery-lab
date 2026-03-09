from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, account: Account) -> Account:
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def get_by_id(self, account_id: int) -> Account | None:
        result = await self.session.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def get_by_document(self, document: str) -> Account | None:
        result = await self.session.execute(
            select(Account).where(Account.owner_document == document)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Account]:
        result = await self.session.execute(select(Account))
        return list(result.scalars().all())

    async def update(self, account: Account) -> Account:
        merged = await self.session.merge(account)
        await self.session.commit()
        await self.session.refresh(merged)
        return merged

    async def delete(self, account_id: int) -> bool:
        account = await self.get_by_id(account_id)
        if not account:
            return False
        await self.session.delete(account)
        await self.session.commit()
        return True
