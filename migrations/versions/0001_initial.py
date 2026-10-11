"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=80), nullable=True, index=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("balance >= 0 OR kind != 'wallet'", name="wallet_balance_non_negative"),
    )
    op.create_index("ix_accounts_owner_currency", "accounts", ["owner_user_id", "currency"])

    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("initiated_by", sa.String(length=80), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transaction_id", sa.String(length=36), sa.ForeignKey("ledger_transactions.id"), nullable=False, index=True),
        sa.Column("debit_account_id", sa.String(length=80), sa.ForeignKey("accounts.id"), nullable=False, index=True),
        sa.Column("credit_account_id", sa.String(length=80), sa.ForeignKey("accounts.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ledger_entry_positive_amount"),
        sa.CheckConstraint("debit_account_id <> credit_account_id", name="ledger_entry_distinct_accounts"),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
    )

    op.create_table(
        "transfer_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=36), sa.ForeignKey("ledger_transactions.id"), nullable=False, index=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fraud_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=36), sa.ForeignKey("ledger_transactions.id"), nullable=True, index=True),
        sa.Column("user_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("rule", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "reconciliation_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_date", sa.Date(), nullable=False, unique=True),
        sa.Column("ledger_entry_count", sa.Integer(), nullable=False),
        sa.Column("account_count", sa.Integer(), nullable=False),
        sa.Column("total_debits", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_credits", sa.Numeric(18, 2), nullable=False),
        sa.Column("out_of_balance", sa.Boolean(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_ledger_entry_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'ledger_entries are immutable; post a reversing entry instead';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_entries_immutable
        BEFORE UPDATE OR DELETE ON ledger_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_ledger_entry_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_entries_immutable ON ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS prevent_ledger_entry_mutation")
    op.drop_table("reconciliation_reports")
    op.drop_table("fraud_events")
    op.drop_table("transfer_audits")
    op.drop_table("idempotency_keys")
    op.drop_table("ledger_entries")
    op.drop_table("ledger_transactions")
    op.drop_index("ix_accounts_owner_currency", table_name="accounts")
    op.drop_table("accounts")
