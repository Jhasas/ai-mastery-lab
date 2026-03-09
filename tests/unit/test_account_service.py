from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.exceptions.handlers import AccountNotFoundException, DuplicateDocumentException
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.account_service import AccountService


@pytest.fixture
def mock_repository():
    return AsyncMock()


@pytest.fixture
def service(mock_repository):
    return AccountService(repository=mock_repository)


def make_account(**overrides) -> Account:
    defaults = {
        "id": 1,
        "owner_name": "João Silva",
        "owner_document": "12345678901",
        "balance": Decimal("1000.00"),
        "account_type": "CORRENTE",
        "is_active": True,
    }
    defaults.update(overrides)
    return Account(**defaults)


class TestCreateAccount:
    async def test_should_create_account_successfully(self, service, mock_repository):
        data = AccountCreate(
            owner_name="João Silva",
            owner_document="12345678901",
            account_type="CORRENTE",
            initial_balance=Decimal("1000.00"),
        )
        mock_repository.get_by_document.return_value = None
        mock_repository.create.return_value = make_account()

        result = await service.create_account(data)

        assert result.owner_name == "João Silva"
        assert result.balance == Decimal("1000.00")
        mock_repository.create.assert_called_once()

    async def test_should_raise_error_when_duplicate_cpf(self, service, mock_repository):
        data = AccountCreate(
            owner_name="João Silva",
            owner_document="12345678901",
            account_type="CORRENTE",
        )
        mock_repository.get_by_document.return_value = make_account()

        with pytest.raises(DuplicateDocumentException):
            await service.create_account(data)

        mock_repository.create.assert_not_called()


class TestGetAccount:
    async def test_should_return_account_when_exists(self, service, mock_repository):
        mock_repository.get_by_id.return_value = make_account()

        result = await service.get_account(1)

        assert result.id == 1
        assert result.owner_name == "João Silva"

    async def test_should_raise_not_found_when_account_does_not_exist(
        self, service, mock_repository
    ):
        mock_repository.get_by_id.return_value = None

        with pytest.raises(AccountNotFoundException):
            await service.get_account(99999)


class TestUpdateAccount:
    async def test_should_update_only_provided_fields(self, service, mock_repository):
        account = make_account()
        mock_repository.get_by_id.return_value = account
        mock_repository.update.return_value = make_account(owner_name="Maria Santos")

        data = AccountUpdate(owner_name="Maria Santos")
        result = await service.update_account(1, data)

        assert result.owner_name == "Maria Santos"
        mock_repository.update.assert_called_once()

    async def test_should_raise_not_found_when_updating_nonexistent(
        self, service, mock_repository
    ):
        mock_repository.get_by_id.return_value = None

        with pytest.raises(AccountNotFoundException):
            await service.update_account(99999, AccountUpdate(owner_name="Novo Nome"))


class TestDeleteAccount:
    async def test_should_delete_account_successfully(self, service, mock_repository):
        mock_repository.get_by_id.return_value = make_account()
        mock_repository.delete.return_value = True

        await service.delete_account(1)

        mock_repository.delete.assert_called_once_with(1)

    async def test_should_raise_not_found_when_deleting_nonexistent(
        self, service, mock_repository
    ):
        mock_repository.get_by_id.return_value = None

        with pytest.raises(AccountNotFoundException):
            await service.delete_account(99999)
