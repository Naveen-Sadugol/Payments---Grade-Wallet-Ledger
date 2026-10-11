from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WalletCreate(BaseModel):
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class WalletResponse(BaseModel):
    id: str
    owner_user_id: str
    currency: str
    balance: Decimal
    model_config = ConfigDict(from_attributes=True)


class MoneyRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2)
    reference: str | None = Field(default=None, max_length=120)


class TransferRequest(BaseModel):
    from_wallet_id: str
    to_wallet_id: str
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2)
    memo: str | None = Field(default=None, max_length=255)


class TransferResponse(BaseModel):
    transaction_id: str
    status: str
    amount: Decimal
    from_wallet_id: str
    to_wallet_id: str
    fraud_action: str | None = None


class LedgerEntryResponse(BaseModel):
    transaction_id: str
    type: str
    status: str
    debit_account_id: str
    credit_account_id: str
    amount: Decimal
    created_at: datetime


class QnaRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)


class QnaResponse(BaseModel):
    answer: str
    matched_intent: str
    amount: Decimal | None = None

