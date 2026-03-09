import pytest

_cpf_counter = 100


def _next_cpf():
    global _cpf_counter
    _cpf_counter += 1
    return f"{_cpf_counter:011d}"


async def create_two_accounts(client, balance="5000.00"):
    a = await client.post("/accounts/", json={
        "owner_name": "Alice",
        "owner_document": _next_cpf(),
        "account_type": "CORRENTE",
        "initial_balance": balance,
    })
    b = await client.post("/accounts/", json={
        "owner_name": "Bob",
        "owner_document": _next_cpf(),
        "account_type": "CORRENTE",
        "initial_balance": balance,
    })
    return a.json()["id"], b.json()["id"]


class TestTransfer:
    async def test_should_return_201_when_transfer_succeeds(self, client):
        id_a, id_b = await create_two_accounts(client)

        response = await client.post("/transactions/transfer", json={
            "origin_account_id": id_a,
            "destination_account_id": id_b,
            "amount": "1000.00",
        })

        assert response.status_code == 201
        assert "sucesso" in response.json()["message"]

    async def test_should_return_400_when_insufficient_balance(self, client):
        id_a, id_b = await create_two_accounts(client, balance="100.00")

        response = await client.post("/transactions/transfer", json={
            "origin_account_id": id_a,
            "destination_account_id": id_b,
            "amount": "500.00",
        })

        assert response.status_code == 400
        assert "Insufficient" in response.json()["message"]

    async def test_should_return_404_when_origin_not_found(self, client):
        response = await client.post("/transactions/transfer", json={
            "origin_account_id": 99999,
            "destination_account_id": 99998,
            "amount": "100.00",
        })

        assert response.status_code == 404

    async def test_should_return_200_when_listing_transactions(self, client):
        id_a, id_b = await create_two_accounts(client)
        await client.post("/transactions/transfer", json={
            "origin_account_id": id_a,
            "destination_account_id": id_b,
            "amount": "500.00",
        })

        response = await client.get(f"/transactions/{id_a}")

        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_should_update_balances_after_transfer(self, client):
        id_a, id_b = await create_two_accounts(client)

        await client.post("/transactions/transfer", json={
            "origin_account_id": id_a,
            "destination_account_id": id_b,
            "amount": "1000.00",
        })

        origin = await client.get(f"/accounts/{id_a}")
        destination = await client.get(f"/accounts/{id_b}")

        assert origin.json()["balance"] == "4000.00"
        assert destination.json()["balance"] == "6000.00"
