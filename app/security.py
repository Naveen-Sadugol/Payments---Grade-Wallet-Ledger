from fastapi import Header, HTTPException


def current_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="X-User-Id header is required for this baseline")
    return x_user_id.strip()

