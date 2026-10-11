# Transaction Isolation And Safety

This project uses PostgreSQL row locks to serialize money movement.

## Ordered Account Locks

Before posting a ledger entry, the service locks every involved account using:

```sql
SELECT ... FOR UPDATE
ORDER BY account_id
```

The deterministic account ID ordering prevents two transfers from locking the same accounts in opposite orders. That is the main deadlock-avoidance rule in this baseline.

## Non-Negative Wallet Balances

Wallet debits check the cached wallet balance while the wallet row is locked. The database also has a check constraint so a negative wallet balance cannot be committed accidentally.

## Idempotency Locking

Idempotent requests insert or find the caller's `(user_id, key)` record and lock it with `SELECT FOR UPDATE`.

That means a concurrent stampede using the same idempotency key waits for the first request, then replays its stored response instead of performing the operation again.

## Isolation Level

The baseline uses PostgreSQL's default `READ COMMITTED` isolation level plus explicit row locks. This is a common and practical shape for wallet movement when all balance-changing operations lock the relevant rows before reading/updating them.

## Immutable Ledger

The application never updates or deletes ledger entries. The migration also installs a database trigger that rejects direct ledger entry updates and deletes. Corrections should be represented as new reversing entries.
