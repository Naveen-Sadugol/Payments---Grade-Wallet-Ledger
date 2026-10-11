from datetime import date
from decimal import Decimal

from fastapi import Depends, Header, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.idempotency import request_hash, run_idempotent
from app.models import Account, LedgerEntry, LedgerTransaction
from app.schemas import (
    LedgerEntryResponse,
    MoneyRequest,
    QnaRequest,
    QnaResponse,
    TransferRequest,
    TransferResponse,
    WalletCreate,
    WalletResponse,
)
from app.security import current_user_id
from app.services.fraud import HOLD_THRESHOLD, RAPID_TRANSFER_LIMIT, evaluate_transfer, record_fraud_event
from app.services.ledger import create_wallet, get_wallet_for_user, top_up, transfer, withdraw
from app.services.qna import answer_statement_question
from app.services.reconciliation import run_reconciliation

from fastapi import FastAPI

app = FastAPI(title="Payments-Grade Wallet Ledger", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/wallets", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet_endpoint(
    payload: WalletCreate,
    user_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    with session.begin():
        wallet = create_wallet(session, user_id, payload.currency)
    return wallet


@app.get("/wallets/{wallet_id}", response_model=WalletResponse)
def get_wallet_endpoint(wallet_id: str, user_id: str = Depends(current_user_id), session: Session = Depends(get_session)):
    return get_wallet_for_user(session, user_id, wallet_id)


@app.get("/wallets/{wallet_id}/statement", response_model=list[LedgerEntryResponse])
def statement(wallet_id: str, user_id: str = Depends(current_user_id), session: Session = Depends(get_session)):
    get_wallet_for_user(session, user_id, wallet_id)
    rows = session.execute(
        select(LedgerEntry, LedgerTransaction)
        .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
        .where(or_(LedgerEntry.debit_account_id == wallet_id, LedgerEntry.credit_account_id == wallet_id))
        .order_by(LedgerEntry.created_at.desc())
    ).all()
    return [
        LedgerEntryResponse(
            transaction_id=tx.id,
            type=tx.type,
            status=tx.status,
            debit_account_id=entry.debit_account_id,
            credit_account_id=entry.credit_account_id,
            amount=entry.amount,
            created_at=entry.created_at,
        )
        for entry, tx in rows
    ]


@app.post("/wallets/{wallet_id}/topups", status_code=status.HTTP_201_CREATED)
def topup_endpoint(
    wallet_id: str,
    payload: MoneyRequest,
    response: Response,
    user_id: str = Depends(current_user_id),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    session: Session = Depends(get_session),
):
    body_hash = request_hash(payload.model_dump(mode="json") | {"wallet_id": wallet_id, "route": "topup"})
    with session.begin():
        def operation() -> tuple[int, dict]:
            wallet = get_wallet_for_user(session, user_id, wallet_id)
            tx = top_up(session, user_id=user_id, wallet=wallet, amount=payload.amount, reference=payload.reference)
            return 201, {"transaction_id": tx.id, "status": tx.status, "amount": str(payload.amount), "wallet_id": wallet_id}

        status_code, data = run_idempotent(
            session, user_id=user_id, key=idempotency_key, body_hash=body_hash, operation=operation
        )
    response.status_code = status_code
    return data


@app.post("/wallets/{wallet_id}/withdrawals", status_code=status.HTTP_201_CREATED)
def withdrawal_endpoint(
    wallet_id: str,
    payload: MoneyRequest,
    response: Response,
    user_id: str = Depends(current_user_id),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    session: Session = Depends(get_session),
):
    body_hash = request_hash(payload.model_dump(mode="json") | {"wallet_id": wallet_id, "route": "withdrawal"})
    with session.begin():
        def operation() -> tuple[int, dict]:
            wallet = get_wallet_for_user(session, user_id, wallet_id)
            tx = withdraw(session, user_id=user_id, wallet=wallet, amount=payload.amount, reference=payload.reference)
            return 201, {"transaction_id": tx.id, "status": tx.status, "amount": str(payload.amount), "wallet_id": wallet_id}

        status_code, data = run_idempotent(
            session, user_id=user_id, key=idempotency_key, body_hash=body_hash, operation=operation
        )
    response.status_code = status_code
    return data


@app.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def transfer_endpoint(
    payload: TransferRequest,
    response: Response,
    user_id: str = Depends(current_user_id),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    session: Session = Depends(get_session),
):
    body_hash = request_hash(payload.model_dump(mode="json") | {"route": "transfer"})
    with session.begin():
        def operation() -> tuple[int, dict]:
            from_wallet = get_wallet_for_user(session, user_id, payload.from_wallet_id)
            to_wallet = session.get(Account, payload.to_wallet_id)
            if not to_wallet or to_wallet.kind != "wallet":
                raise HTTPException(status_code=404, detail="Destination wallet not found")

            fraud_action, fraud_reason = evaluate_transfer(session, user_id=user_id, amount=payload.amount)
            tx_status = "held" if fraud_action == "hold" else "posted"
            tx = transfer(
                session,
                user_id=user_id,
                from_wallet=from_wallet,
                to_wallet=to_wallet,
                amount=payload.amount,
                memo=payload.memo or fraud_reason,
                status=tx_status,
            )
            if fraud_action == "hold":
                record_fraud_event(
                    session,
                    transaction_id=tx.id,
                    user_id=user_id,
                    rule="large_transfer_hold",
                    action="hold",
                    details={"amount": str(payload.amount), "threshold": str(HOLD_THRESHOLD)},
                )
            elif fraud_action == "flag":
                record_fraud_event(
                    session,
                    transaction_id=tx.id,
                    user_id=user_id,
                    rule="rapid_transfer_flag",
                    action="flag",
                    details={"limit": RAPID_TRANSFER_LIMIT, "window_minutes": 1},
                )
            return 201, {
                "transaction_id": tx.id,
                "status": tx.status,
                "amount": str(payload.amount),
                "from_wallet_id": payload.from_wallet_id,
                "to_wallet_id": payload.to_wallet_id,
                "fraud_action": fraud_action,
            }

        status_code, data = run_idempotent(
            session, user_id=user_id, key=idempotency_key, body_hash=body_hash, operation=operation
        )
    response.status_code = status_code
    return data


@app.post("/qna/statement", response_model=QnaResponse)
def qna_endpoint(payload: QnaRequest, user_id: str = Depends(current_user_id), session: Session = Depends(get_session)):
    answer, intent, amount = answer_statement_question(session, user_id=user_id, question=payload.question)
    return QnaResponse(answer=answer, matched_intent=intent, amount=amount)


@app.post("/ops/reconciliation/{business_date}")
def reconciliation_endpoint(business_date: date, session: Session = Depends(get_session)):
    with session.begin():
        report = run_reconciliation(session, business_date)
    return {
        "business_date": str(report.business_date),
        "ledger_entry_count": report.ledger_entry_count,
        "account_count": report.account_count,
        "total_debits": str(report.total_debits),
        "total_credits": str(report.total_credits),
        "out_of_balance": report.out_of_balance,
        "details": report.details,
    }
