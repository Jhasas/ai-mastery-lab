import pytest


VALID_ACCOUNT = {
    "owner_name": "João Silva",
    "owner_document": "12345678901",
    "account_type": "CORRENTE",
    "initial_balance": "1000.00",
}


class TestCreateAccount:
    async def test_should_return_201_when_creating_account(self, client):
        response = await client.post("/accounts/", json=VALID_ACCOUNT)

        assert response.status_code == 201
        body = response.json()
        assert body["owner_name"] == "João Silva"
        assert body["owner_document"] == "12345678901"
        assert body["balance"] == "1000.00"
        assert body["id"] is not None

    async def test_should_return_409_when_duplicate_cpf(self, client):
        await client.post("/accounts/", json=VALID_ACCOUNT)

        response = await client.post("/accounts/", json=VALID_ACCOUNT)

        assert response.status_code == 409
        assert "already exists" in response.json()["message"]

    async def test_should_return_422_when_owner_name_is_blank(self, client):
        payload = {**VALID_ACCOUNT, "owner_name": "", "owner_document": "99900000001"}
        response = await client.post("/accounts/", json=payload)

        assert response.status_code == 422

    async def test_should_return_422_when_cpf_format_is_invalid(self, client):
        payload = {**VALID_ACCOUNT, "owner_document": "abc"}
        response = await client.post("/accounts/", json=payload)

        assert response.status_code == 422


class TestGetAccount:
    async def test_should_return_200_and_account_when_id_exists(self, client):
        create_response = await client.post(
            "/accounts/",
            json={**VALID_ACCOUNT, "owner_document": "11111111111"},
        )
        account_id = create_response.json()["id"]

        response = await client.get(f"/accounts/{account_id}")

        assert response.status_code == 200
        assert response.json()["owner_document"] == "11111111111"

    async def test_should_return_404_when_account_does_not_exist(self, client):
        response = await client.get("/accounts/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()


class TestListAccounts:
    async def test_should_return_200_when_listing_all_accounts(self, client):
        await client.post(
            "/accounts/",
            json={**VALID_ACCOUNT, "owner_document": "22222222222"},
        )
        await client.post(
            "/accounts/",
            json={**VALID_ACCOUNT, "owner_document": "33333333333"},
        )

        response = await client.get("/accounts/")

        assert response.status_code == 200
        assert len(response.json()) >= 2


class TestUpdateAccount:
    async def test_should_return_200_when_partial_update_succeeds(self, client):
        create_response = await client.post(
            "/accounts/",
            json={**VALID_ACCOUNT, "owner_document": "44444444444"},
        )
        account_id = create_response.json()["id"]

        response = await client.patch(
            f"/accounts/{account_id}",
            json={"owner_name": "Maria Santos"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["owner_name"] == "Maria Santos"
        assert body["balance"] == "1000.00"
