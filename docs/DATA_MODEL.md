# BankCat Demo – Data Model (MVP)

## Overview
This document defines the core database tables used in the BankCat demo software.
All data is client-specific and stored in a persistent Postgres database.

---

## clients
Stores client/company profiles.

Columns:
- id (PK)
- name
- business_description
- industry
- country
- created_at

---

## banks
Stores bank accounts/cards per client.

Columns:
- id (PK)
- client_id (FK → clients.id)
- bank_name
- account_type (Current / Credit Card / Savings)
- currency
- opening_balance

---

## categories
Client-specific category master.

Columns:
- id (PK)
- client_id (FK)
- category_code
- category_name
- type (Income / Expense / Other)
- nature (Dr / Cr / Any)

---

## transactions_draft
Temporary working table before finalization.

Columns:
- id (PK)
- client_id
- bank_id
- date
- description
- debit
- credit
- balance
- suggested_category
- suggested_vendor
- confidence
- final_category
- final_vendor
- status (Draft)

---

## transactions_committed
Locked and finalized transactions.

Columns:
- id (PK)
- client_id
- bank_id
- date
- description
- debit
- credit
- balance
- category
- vendor
- commit_id

---

## vendor_memory
Client-wise vendor learning table.

Columns:
- id (PK)
- client_id
- vendor_name (or vendor)
- category_name
- confidence
- times_used
- updated_at

Constraints:
- UNIQUE (client_id, vendor_name) or UNIQUE (client_id, vendor) depending on the column present in the DB

---

## keyword_model
Keyword/bigram learning table.

Columns:
- id (PK)
- client_id
- token
- category
- weight
- times_used

---

## commits
Tracks each commit event.

Columns:
- id (PK)
- client_id
- bank_id
- period
- committed_by
- rows_committed
- accuracy
- is_active
- created_at
## transactions_draft (working table)
Purpose: Stores standardized transactions before commit (editable).
Key columns:
- client_id, bank_id, period
- tx_date, description, debit, credit, balance
- suggested_category, suggested_vendor, confidence, reason
- final_category, final_vendor
Note: Review saves update final_* inside draft. Commit will copy to committed table.

## vendor_memory (learning)
Purpose: Client-wise vendor→category memory used for suggestions.
Columns:
- client_id, vendor_name, category_name, confidence, created_at
