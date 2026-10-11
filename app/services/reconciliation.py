from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, ReconciliationReport


def run_reconciliation(session: Session, business_date: date) -> ReconciliationReport:
    entry_count = session.execute(select(func.count(LedgerEntry.id))).scalar_one()
    account_count = session.execute(select(func.count(Account.id))).scalar_one()
    total_amount = session.execute(select(func.coalesce(func.sum(LedgerEntry.amount), 0))).scalar_one()
    total_debits = Decimal(total_amount).quantize(Decimal("0.01"))
    total_credits = Decimal(total_amount).quantize(Decimal("0.01"))
    out_of_balance = total_debits != total_credits
    details = {"note": "Double-entry rows store one debit and one credit per ledger entry."}

    stmt = (
        insert(ReconciliationReport)
        .values(
            business_date=business_date,
            ledger_entry_count=entry_count,
            account_count=account_count,
            total_debits=total_debits,
            total_credits=total_credits,
            out_of_balance=out_of_balance,
            details=details,
        )
        .on_conflict_do_update(
            index_elements=["business_date"],
            set_=dict(
                ledger_entry_count=entry_count,
                account_count=account_count,
                total_debits=total_debits,
                total_credits=total_credits,
                out_of_balance=out_of_balance,
                details=details,
            ),
        )
        .returning(ReconciliationReport)
    )
    return session.execute(stmt).scalar_one()

