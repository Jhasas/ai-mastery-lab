from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.exceptions.handlers import AccountNotFoundException, InsufficientBalanceException
from app.models.account import Account
from app.schemas.transaction import TransferRequest
from app.services.transaction_service import TransactionService

_tx_id_counter = 0


def _fake_create(tx):
    global _tx_id_counter
    _tx_id_counter += 1
    tx.id = _tx_id_counter
    tx.created_at = datetime.now(timezone.utc)
    return tx


@pytest.fixture
def mock_account_repo():
    return AsyncMock()


@pytest.fixture
def mock_transaction_repo():
    mock = AsyncMock()
    mock.create.side_effect = _fake_create
    return mock


@pytest.fixture
def service(mock_account_repo, mock_transaction_repo):
    return TransactionService(mock_account_repo, mock_transaction_repo)


def make_account(id: int, balance: Decimal = Decimal("5000.00")) -> Account:
    return Account(
        id=id,
        owner_name=f"User {id}",
        owner_document=f"{id:011d}",
        balance=balance,
        account_type="CORRENTE",
        is_active=True,
    )


TRANSFER_DATA = TransferRequest(
    origin_account_id=1,
    destination_account_id=2,
    amount=Decimal("1000.00"),
    description="Test transfer",
)


class TestExecuteTransfer:
    async def test_should_execute_transfer_when_balance_sufficient(
        self, service, mock_account_repo, mock_transaction_repo
    ):
        origin = make_account(1, Decimal("5000.00"))
        destination = make_account(2, Decimal("5000.00"))
        mock_account_repo.get_by_id.side_effect = lambda id: {1: origin, 2: destination}[id]

        result = await service.execute_transfer(TRANSFER_DATA)

        assert origin.balance == Decimal("4000.00")
        assert destination.balance == Decimal("6000.00")
        assert mock_transaction_repo.create.call_count == 2
        assert "sucesso" in result.message

    async def test_should_raise_insufficient_balance(
        self, service, mock_account_repo
    ):
        origin = make_account(1, Decimal("500.00"))
        destination = make_account(2)
        mock_account_repo.get_by_id.side_effect = lambda id: {1: origin, 2: destination}[id]

        with pytest.raises(InsufficientBalanceException):
            await service.execute_transfer(TRANSFER_DATA)

    async def test_should_raise_not_found_when_origin_missing(
        self, service, mock_account_repo
    ):
        mock_account_repo.get_by_id.return_value = None

        with pytest.raises(AccountNotFoundException):
            await service.execute_transfer(TRANSFER_DATA)

    async def test_should_raise_not_found_when_destination_missing(
        self, service, mock_account_repo
    ):
        mock_account_repo.get_by_id.side_effect = lambda id: make_account(1) if id == 1 else None

        with pytest.raises(AccountNotFoundException):
            await service.execute_transfer(TRANSFER_DATA)

    async def test_should_create_transfer_out_and_transfer_in(
        self, service, mock_account_repo, mock_transaction_repo
    ):
        origin = make_account(1)
        destination = make_account(2)
        mock_account_repo.get_by_id.side_effect = lambda id: {1: origin, 2: destination}[id]

        await service.execute_transfer(TRANSFER_DATA)

        calls = mock_transaction_repo.create.call_args_list
        tx_out = calls[0][0][0]
        tx_in = calls[1][0][0]

        assert tx_out.type == "TRANSFER_OUT"
        assert tx_out.account_id == 1
        assert tx_out.related_account_id == 2

        assert tx_in.type == "TRANSFER_IN"
        assert tx_in.account_id == 2
        assert tx_in.related_account_id == 1
