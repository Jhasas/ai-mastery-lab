from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransferRequest(BaseModel):
    origin_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0)
    description: str | None = None


class TransactionResponse(BaseModel):
    id: int
    account_id: int
    type: str
    amount: Decimal
    description: str | None = None
    related_account_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransferResponse(BaseModel):
    origin_transaction: TransactionResponse
    destination_transaction: TransactionResponse
    message: str
