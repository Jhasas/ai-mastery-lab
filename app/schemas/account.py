from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    owner_name: str = Field(min_length=1)
    owner_document: str = Field(pattern=r"^\d{11}$")
    account_type: Literal["CORRENTE", "POUPANCA"]
    initial_balance: Decimal = Field(default=Decimal("0"), ge=0)


class AccountResponse(BaseModel):
    id: int
    owner_name: str
    owner_document: str
    balance: Decimal
    account_type: str
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AccountUpdate(BaseModel):
    owner_name: str | None = None
    is_active: bool | None = None
