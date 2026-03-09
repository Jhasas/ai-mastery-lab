from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import TransactionResponse, TransferRequest, TransferResponse
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


async def get_transaction_service(db: AsyncSession = Depends(get_db)) -> TransactionService:
    account_repo = AccountRepository(db)
    transaction_repo = TransactionRepository(db)
    return TransactionService(account_repo, transaction_repo)


@router.post("/transfer", status_code=201, response_model=TransferResponse)
async def execute_transfer(
    data: TransferRequest,
    service: TransactionService = Depends(get_transaction_service),
):
    return await service.execute_transfer(data)


@router.get("/{account_id}", response_model=list[TransactionResponse])
async def list_transactions(
    account_id: int,
    service: TransactionService = Depends(get_transaction_service),
):
    return await service.list_transactions(account_id)
