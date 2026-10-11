# Schema

## Accounts

`accounts` stores wallets and platform/external clearing accounts. Wallet balances are cached for fast reads and guarded by a database check constraint:

```text
balance >= 0 OR kind != 'wallet'
```

Wallet IDs are deterministic in this baseline: `{user_id}-{currency}`, for example `alice-USD`.

## Ledger Transactions

`ledger_transactions` groups ledger entries by business operation. It stores:

- `type`: `topup`, `peer_transfer`, or `withdrawal`.
- `status`: `posted` or `held`.
- `initiated_by`: caller user ID.
- `memo`: optional business reference.

## Ledger Entries

`ledger_entries` is append-only. The migration installs a PostgreSQL trigger that rejects direct updates and deletes. Each row has:

- `debit_account_id`
- `credit_account_id`
- `amount`

The amount is positive, and debit/credit accounts must be different. This single-row double-entry shape makes reconciliation deterministic: every ledger row contributes exactly one debit and one credit of the same amount.

## Idempotency

`idempotency_keys` is unique by `(user_id, key)`. The service stores:

- A SHA-256 hash of the canonical request body plus route context.
- The first completed response body and status code.

Same user, same key, same body returns the stored response. Same user, same key, different body returns `409`.

## Transfer Audit

`transfer_audits` records status transitions for transfers. This baseline writes the initial status. A production version would add review, release, cancel, and reversal statuses.

## Fraud Events

`fraud_events` stores baseline rule outcomes:

- `large_transfer_hold`
- `rapid_transfer_flag`

## Reconciliation Reports

`reconciliation_reports` stores one report per business date. It records account and entry counts, total debit/credit amounts, and whether the ledger is out of balance.
