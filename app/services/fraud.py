from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FraudEvent, LedgerTransaction

HOLD_THRESHOLD = Decimal("10000.00")
RAPID_TRANSFER_LIMIT = 5


def evaluate_transfer(session: Session, *, user_id: str, amount: Decimal, transaction_id: str | None = None) -> tuple[str, str | None]:
    if amount >= HOLD_THRESHOLD:
        if transaction_id:
            record_fraud_event(
                session,
                transaction_id=transaction_id,
                user_id=user_id,
                rule="large_transfer_hold",
                action="hold",
                details={"amount": str(amount), "threshold": str(HOLD_THRESHOLD)},
            )
        return "hold", "Large transfer requires manual review"

    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent_count = session.execute(
        select(func.count(LedgerTransaction.id)).where(
            LedgerTransaction.initiated_by == user_id,
            LedgerTransaction.type == "peer_transfer",
            LedgerTransaction.created_at >= since,
        )
    ).scalar_one()
    if recent_count >= RAPID_TRANSFER_LIMIT:
        if transaction_id:
            record_fraud_event(
                session,
                transaction_id=transaction_id,
                user_id=user_id,
                rule="rapid_transfer_flag",
                action="flag",
                details={"recent_transfer_count": int(recent_count), "window_minutes": 1},
            )
        return "flag", "Rapid transfer pattern flagged"

    return "allow", None


def record_fraud_event(
    session: Session,
    *,
    transaction_id: str,
    user_id: str,
    rule: str,
    action: str,
    details: dict,
) -> None:
    session.add(
        FraudEvent(
            transaction_id=transaction_id,
            user_id=user_id,
            rule=rule,
            action=action,
            details=details,
        )
    )
