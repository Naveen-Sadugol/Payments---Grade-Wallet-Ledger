# Payments-Grade Wallet Ledger

A runnable baseline for a wallet ledger service using Python FastAPI, PostgreSQL 15+, SQLAlchemy, Alembic, and Docker Compose.

This milestone implements the core payments safety shape:

- Double-entry ledger with immutable ledger entries.
- Wallet creation, balance, statement, top-up, peer transfer, and withdrawal.
- Ordered `SELECT FOR UPDATE` account locking for money movement.
- Non-negative wallet balance checks.
- Per-user idempotency keys with request-body hash, replay, and mismatch handling.
- Transfer status audit records.
- Baseline fraud hold/flag rules.
- Nightly reconciliation report endpoint/CLI.
- Deterministic statement Q&A using parameterized queries scoped to caller wallets.
- Tests for idempotency and concurrent transfer stampede behavior.

## Quick Start In VS Code On Windows

1. Install these once:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - [VS Code](https://code.visualstudio.com/)
   - VS Code extensions: **Python** and **Docker**

2. Open this folder in VS Code:
   - VS Code -> File -> Open Folder
   - Pick this project folder.

3. Open the VS Code terminal:
   - Terminal -> New Terminal

4. Start everything:

   ```powershell
   docker compose up --build
   ```

5. Open the API docs:

   ```text
   http://localhost:8000/docs
   ```

6. Seed demo wallets in a second VS Code terminal:

   ```powershell
   docker compose exec api python -m app.seed
   ```

7. Run tests:

   ```powershell
   docker compose exec api pytest
   ```

## Example API Calls

Use the Swagger page at `http://localhost:8000/docs`, or run these in PowerShell.

Create a wallet:

```powershell
curl.exe -X POST http://localhost:8000/wallets `
  -H "Content-Type: application/json" `
  -H "X-User-Id: alice" `
  -d "{\"currency\":\"USD\"}"
```

Top up a wallet:

```powershell
curl.exe -X POST http://localhost:8000/wallets/alice-USD/topups `
  -H "Content-Type: application/json" `
  -H "X-User-Id: alice" `
  -H "X-Idempotency-Key: topup-001" `
  -d "{\"amount\":\"25.00\",\"reference\":\"card-demo\"}"
```

Transfer to another user:

```powershell
curl.exe -X POST http://localhost:8000/transfers `
  -H "Content-Type: application/json" `
  -H "X-User-Id: alice" `
  -H "X-Idempotency-Key: transfer-001" `
  -d "{\"from_wallet_id\":\"alice-USD\",\"to_wallet_id\":\"bob-USD\",\"amount\":\"5.00\",\"memo\":\"lunch\"}"
```

Ask a statement question:

```powershell
curl.exe -X POST http://localhost:8000/qna/statement `
  -H "Content-Type: application/json" `
  -H "X-User-Id: alice" `
  -d "{\"question\":\"How much did I send this month?\"}"
```

## Implemented Milestones

- **Ledger core:** append-only entries, transaction grouping, account cached balances, and reconciliation.
- **Wallet APIs:** create, read balance, statement, top-up, transfer, withdrawal.
- **Safety:** ordered row locks, wallet overdraft prevention, request idempotency, audit records.
- **Fraud baseline:** large transactions are held; rapid repeated transfers are flagged.
- **Q&A baseline:** deterministic rule-based answers; no free-form SQL generation.
- **Docs:** schema and isolation notes.

## Pending Production Hardening

- Real authentication/authorization provider instead of `X-User-Id`.
- Real payment processor integration for top-ups and withdrawals.
- Background scheduler for nightly reconciliation; current baseline exposes a CLI and endpoint.
- Rich fraud case management and review workflow.
- Observability: metrics, tracing, and structured audit export.

