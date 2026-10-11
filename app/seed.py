from decimal import Decimal

from app.db import SessionLocal
from app.services.ledger import create_wallet, top_up, transfer


def main() -> None:
    with SessionLocal() as session:
        with session.begin():
            alice = create_wallet(session, "alice", "USD")
            bob = create_wallet(session, "bob", "USD")
            if alice.balance == Decimal("0.00"):
                top_up(session, user_id="alice", wallet=alice, amount=Decimal("100.00"), reference="seed")
                transfer(session, user_id="alice", from_wallet=alice, to_wallet=bob, amount=Decimal("12.50"), memo="seed transfer")
    print("Seeded alice-USD and bob-USD")


if __name__ == "__main__":
    main()

