from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction


def answer_statement_question(session: Session, *, user_id: str, question: str) -> tuple[str, str, Decimal | None]:
    normalized = question.lower()
    wallet_ids = select(Account.id).where(Account.owner_user_id == user_id, Account.kind == "wallet")

    if "send" in normalized or "sent" in normalized or "transfer out" in normalized:
        amount = session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
            .where(LedgerEntry.debit_account_id.in_(wallet_ids), LedgerTransaction.type == "peer_transfer")
        ).scalar_one()
        amount = Decimal(amount).quantize(Decimal("0.01"))
        return f"You sent {amount} across your wallets.", "sent_total", amount

    if "receive" in normalized or "received" in normalized or "transfer in" in normalized:
        amount = session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
            .where(LedgerEntry.credit_account_id.in_(wallet_ids), LedgerTransaction.type == "peer_transfer")
        ).scalar_one()
        amount = Decimal(amount).quantize(Decimal("0.01"))
        return f"You received {amount} across your wallets.", "received_total", amount

    if "top" in normalized or "deposit" in normalized:
        amount = session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
            .where(LedgerEntry.credit_account_id.in_(wallet_ids), LedgerTransaction.type == "topup")
        ).scalar_one()
        amount = Decimal(amount).quantize(Decimal("0.01"))
        return f"You topped up {amount}.", "topup_total", amount

    count = session.execute(
        select(func.count(LedgerEntry.id)).where(
            or_(LedgerEntry.debit_account_id.in_(wallet_ids), LedgerEntry.credit_account_id.in_(wallet_ids))
        )
    ).scalar_one()
    return f"I found {count} statement entries for your wallets.", "entry_count", None

