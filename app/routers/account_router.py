from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["Accounts"])


async def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    repository = AccountRepository(db)
    return AccountService(repository)


@router.post("/", status_code=201, response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    service: AccountService = Depends(get_account_service),
):
    return await service.create_account(data)


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    service: AccountService = Depends(get_account_service),
):
    return await service.get_all_accounts()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    service: AccountService = Depends(get_account_service),
):
    return await service.get_account(account_id)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    service: AccountService = Depends(get_account_service),
):
    return await service.update_account(account_id, data)


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    service: AccountService = Depends(get_account_service),
):
    await service.delete_account(account_id)
    return {"message": f"Account {account_id} deleted"}
