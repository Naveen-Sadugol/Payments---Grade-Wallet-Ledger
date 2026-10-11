from concurrent.futures import ThreadPoolExecutor


def headers(user: str, key: str | None = None) -> dict[str, str]:
    result = {"X-User-Id": user}
    if key:
        result["X-Idempotency-Key"] = key
    return result


def create_wallet(client, user: str):
    response = client.post("/wallets", json={"currency": "USD"}, headers=headers(user))
    assert response.status_code == 201
    return response.json()["id"]


def top_up(client, user: str, wallet_id: str, amount: str, key: str):
    response = client.post(
        f"/wallets/{wallet_id}/topups",
        json={"amount": amount, "reference": key},
        headers=headers(user, key),
    )
    assert response.status_code == 201
    return response.json()


def test_idempotent_topup_replays_same_response(client):
    wallet_id = create_wallet(client, "alice")
    first = top_up(client, "alice", wallet_id, "10.00", "same-topup")
    second = top_up(client, "alice", wallet_id, "10.00", "same-topup")

    assert first == second
    balance = client.get(f"/wallets/{wallet_id}", headers=headers("alice")).json()["balance"]
    assert balance == "10.00"


def test_idempotency_key_body_mismatch_returns_conflict(client):
    wallet_id = create_wallet(client, "alice")
    top_up(client, "alice", wallet_id, "10.00", "reuse-key")
    response = client.post(
        f"/wallets/{wallet_id}/topups",
        json={"amount": "11.00", "reference": "reuse-key"},
        headers=headers("alice", "reuse-key"),
    )
    assert response.status_code == 409


def test_transfer_prevents_overdraft(client):
    alice = create_wallet(client, "alice")
    bob = create_wallet(client, "bob")
    top_up(client, "alice", alice, "5.00", "small-topup")

    response = client.post(
        "/transfers",
        json={"from_wallet_id": alice, "to_wallet_id": bob, "amount": "6.00", "memo": "too much"},
        headers=headers("alice", "too-much"),
    )
    assert response.status_code == 409


def test_concurrent_stampede_allows_only_available_funds(client):
    alice = create_wallet(client, "alice")
    bob = create_wallet(client, "bob")
    top_up(client, "alice", alice, "50.00", "stampede-funds")

    def attempt(i: int) -> int:
        response = client.post(
            "/transfers",
            json={"from_wallet_id": alice, "to_wallet_id": bob, "amount": "10.00", "memo": f"try {i}"},
            headers=headers("alice", f"stampede-{i}"),
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(attempt, range(10)))

    assert statuses.count(201) == 5
    assert statuses.count(409) == 5
    alice_balance = client.get(f"/wallets/{alice}", headers=headers("alice")).json()["balance"]
    bob_balance = client.get(f"/wallets/{bob}", headers=headers("bob")).json()["balance"]
    assert alice_balance == "0.00"
    assert bob_balance == "50.00"


def test_statement_qna_is_scoped_to_calling_user(client):
    alice = create_wallet(client, "alice")
    bob = create_wallet(client, "bob")
    top_up(client, "alice", alice, "20.00", "alice-topup")
    top_up(client, "bob", bob, "99.00", "bob-topup")

    response = client.post(
        "/qna/statement",
        json={"question": "How much did I top up?"},
        headers=headers("alice"),
    )
    assert response.status_code == 200
    assert response.json()["amount"] == "20.00"

