# DB Schema Truth (Supabase) — BankCat Demo
This document is the single source of truth for the live Supabase database (public schema).
All code (`src/schema.py`, `src/crud.py`, UI queries) and all migrations MUST match this schema.
Never invent column names.

Last verified: 2026-01-27

---

## Tables (public)
- clients
- banks
- categories
- draft_batches
- transactions_draft
- commits
- transactions_committed
- vendor_memory
- keyword_model

---

## clients
Columns:
- id
- name
- business_description
- industry
- country
- created_at
- is_active
- updated_at

---

## banks
Columns:
- id
- client_id
- bank_name
- account_masked
- account_type
- currency
- opening_balance
- created_at
- is_active
- updated_at

Notes:
- banks belong to a client (client_id)

---

## categories
Columns:
- id
- client_id
- category_code
- category_name
- type
- nature
- created_at
- is_active
- updated_at

Notes:
- categories are client-specific (client_id)
- type = Income/Expense/Other
- nature = Dr/Cr/Any (soft rule)

---

## draft_batches
Columns:
- id
- client_id
- bank_id
- period
- status
- created_at
- updated_at

Notes:
- one draft batch represents a working set for (client, bank, period)

---

## transactions_draft
Columns:
- id
- client_id
- bank_id
- period
- tx_date
- description
- debit
- credit
- balance
- suggested_category
- suggested_vendor
- reason
- confidence
- final_category
- final_vendor
- status
- created_at
- updated_at

Notes:
- this table is editable (draft)
- final_* are user choices (before commit)
- status is used for workflow states (e.g., imported / processed / user-reviewed)

---

## commits
Columns:
- id
- client_id
- bank_id
- period
- from_date
- to_date
- row_count
- accuracy_percent
- created_at
- committed_by
- committed_at
- rows_committed
- accuracy
- notes
- is_active

Notes:
- commits are “headers” for a locked submission (client, bank, period)
- only ONE commit should be active for a (client, bank, period)
  (if new commit happens, old should be set is_active=false)

---

## transactions_committed
Columns:
- id
- client_id
- bank_id
- commit_id
- period
- tx_date
- description
- debit
- credit
- balance
- category
- vendor
- created_at
- suggested_category
- suggested_vendor
- confidence
- reason

Notes:
- this table is locked (read-only in UI)
- commit_id links to commits

---

## vendor_memory
Columns:
- id
- client_id
- vendor_key
- category
- confidence
- times_confirmed
- last_seen

Key rules:
- unique per client is (client_id, vendor_key)
- DO NOT use vendor/vendor_name columns (they do not exist)

---

## keyword_model
Columns:
- id
- client_id
- token
- category
- weight
- times_used
- updated_at

Key rules:
- unique key is (client_id, token, category)
- DO NOT use category_name column here (it does not exist)

---

## Migration Rules (Postgres)
- Never assume columns. Always confirm with:
  `information_schema.columns`
- Postgres does not support `ADD CONSTRAINT IF NOT EXISTS`.
  Use `DO $$ BEGIN ... IF NOT EXISTS(SELECT 1 FROM pg_constraint ...) THEN ... END IF; END $$;`
- If DB schema changes:
  1) add SQL file under docs/migrations/YYYYMMDD_<name>.sql
  2) update src/schema.py to be idempotent
  3) update docs/DATA_MODEL.md + this file

