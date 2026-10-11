from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("balance >= 0 OR kind != 'wallet'", name="wallet_balance_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(80), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    kind: Mapped[str] = mapped_column(String(30))
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    initiated_by: Mapped[str] = mapped_column(String(80))
    memo: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ledger_entry_positive_amount"),
        CheckConstraint("debit_account_id <> credit_account_id", name="ledger_entry_distinct_accounts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("ledger_transactions.id"), index=True)
    debit_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("accounts.id"), index=True)
    credit_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("accounts.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transaction: Mapped[LedgerTransaction] = relationship(back_populates="entries")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TransferAudit(Base):
    __tablename__ = "transfer_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("ledger_transactions.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FraudEvent(Base):
    __tablename__ = "fraud_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ledger_transactions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    rule: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, unique=True)
    ledger_entry_count: Mapped[int] = mapped_column(Integer)
    account_count: Mapped[int] = mapped_column(Integer)
    total_debits: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_credits: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    out_of_balance: Mapped[bool] = mapped_column(Boolean)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

