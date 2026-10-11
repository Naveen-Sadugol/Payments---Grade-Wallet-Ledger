import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import IdempotencyKey


def request_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_idempotent(
    session: Session,
    *,
    user_id: str,
    key: str | None,
    body_hash: str,
    operation: Callable[[], tuple[int, dict]],
) -> tuple[int, dict]:
    if not key:
        return operation()

    insert_stmt = (
        insert(IdempotencyKey)
        .values(user_id=user_id, key=key, request_hash=body_hash)
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
    )
    session.execute(insert_stmt)

    record = session.execute(
        select(IdempotencyKey)
        .where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
        .with_for_update()
    ).scalar_one()

    if record.request_hash != body_hash:
        raise HTTPException(status_code=409, detail="Idempotency key was reused with a different request body")
    if record.response_json is not None and record.status_code is not None:
        return record.status_code, record.response_json

    status_code, response = operation()
    record.status_code = status_code
    record.response_json = response
    return status_code, response

