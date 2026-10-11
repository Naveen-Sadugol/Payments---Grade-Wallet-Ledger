from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction, TransferAudit

PLATFORM_USER = "platform"
TOPUP_ACCOUNT_ID = "platform-topup-USD"
WITHDRAWAL_ACCOUNT_ID = "platform-withdrawal-USD"


def wallet_id(user_id: str, currency: str) -> str:
    return f"{user_id}-{currency.upper()}"


def ensure_platform_accounts(session: Session, currency: str = "USD") -> None:
    for account_id, kind in [
        (f"platform-topup-{currency}", "external"),
        (f"platform-withdrawal-{currency}", "external"),
        (f"platform-hold-{currency}", "hold"),
    ]:
        account = session.get(Account, account_id)
        if account is None:
            session.add(Account(id=account_id, owner_user_id=None, currency=currency, kind=kind, balance=Decimal("0.00")))


def create_wallet(session: Session, user_id: str, currency: str) -> Account:
    currency = currency.upper()
    account_id = wallet_id(user_id, currency)
    existing = session.get(Account, account_id)
    if existing:
        return existing
    account = Account(id=account_id, owner_user_id=user_id, currency=currency, kind="wallet", balance=Decimal("0.00"))
    session.add(account)
    ensure_platform_accounts(session, currency)
    return account


def get_wallet_for_user(session: Session, user_id: str, account_id: str) -> Account:
    account = session.get(Account, account_id)
    if not account or account.kind != "wallet" or account.owner_user_id != user_id:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return account


def _lock_accounts(session: Session, account_ids: list[str]) -> dict[str, Account]:
    ordered_ids = sorted(set(account_ids))
    accounts = session.execute(
        select(Account)
        .where(Account.id.in_(ordered_ids))
        .order_by(Account.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    found = {account.id: account for account in accounts}
    missing = [account_id for account_id in ordered_ids if account_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Account not found: {missing[0]}")
    return found


def post_entry(
    session: Session,
    *,
    debit_account_id: str,
    credit_account_id: str,
    amount: Decimal,
    tx_type: str,
    initiated_by: str,
    memo: str | None = None,
    status: str = "posted",
) -> LedgerTransaction:
    amount = amount.quantize(Decimal("0.01"))
    accounts = _lock_accounts(session, [debit_account_id, credit_account_id])
    debit = accounts[debit_account_id]
    credit = accounts[credit_account_id]

    if debit.kind == "wallet" and debit.balance < amount:
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")

    debit.balance -= amount
    credit.balance += amount

    tx = LedgerTransaction(id=str(uuid4()), type=tx_type, status=status, initiated_by=initiated_by, memo=memo)
    entry = LedgerEntry(
        id=str(uuid4()),
        transaction_id=tx.id,
        debit_account_id=debit_account_id,
        credit_account_id=credit_account_id,
        amount=amount,
    )
    session.add_all([tx, entry])
    return tx


def top_up(session: Session, *, user_id: str, wallet: Account, amount: Decimal, reference: str | None) -> LedgerTransaction:
    ensure_platform_accounts(session, wallet.currency)
    return post_entry(
        session,
        debit_account_id=f"platform-topup-{wallet.currency}",
        credit_account_id=wallet.id,
        amount=amount,
        tx_type="topup",
        initiated_by=user_id,
        memo=reference,
    )


def withdraw(session: Session, *, user_id: str, wallet: Account, amount: Decimal, reference: str | None) -> LedgerTransaction:
    ensure_platform_accounts(session, wallet.currency)
    return post_entry(
        session,
        debit_account_id=wallet.id,
        credit_account_id=f"platform-withdrawal-{wallet.currency}",
        amount=amount,
        tx_type="withdrawal",
        initiated_by=user_id,
        memo=reference,
    )


def transfer(
    session: Session,
    *,
    user_id: str,
    from_wallet: Account,
    to_wallet: Account,
    amount: Decimal,
    memo: str | None,
    status: str = "posted",
) -> LedgerTransaction:
    if from_wallet.currency != to_wallet.currency:
        raise HTTPException(status_code=409, detail="Cross-currency transfers are not supported in this baseline")
    ensure_platform_accounts(session, from_wallet.currency)
    credit_account_id = to_wallet.id if status == "posted" else f"platform-hold-{from_wallet.currency}"
    tx = post_entry(
        session,
        debit_account_id=from_wallet.id,
        credit_account_id=credit_account_id,
        amount=amount,
        tx_type="peer_transfer",
        initiated_by=user_id,
        memo=memo,
        status=status,
    )
    session.add(TransferAudit(transaction_id=tx.id, status=status, reason=memo if status != "posted" else None))
    return tx
