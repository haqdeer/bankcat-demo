# DB Schema Truth

This file defines the expected column names per table for schema verification.

## clients
- id
- name
- business_description
- industry
- country
- created_at
- is_active
- updated_at

## banks
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

## categories
- id
- client_id
- category_code
- category_name
- type
- nature
- created_at
- is_active
- updated_at

## draft_batches
- id
- client_id
- bank_id
- period
- status
- created_at
- updated_at

## transactions_draft
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

## commits
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

## transactions_committed
- id
- commit_id
- client_id
- bank_id
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

## vendor_memory
- id
- client_id
- vendor_key
- category
- confidence
- times_confirmed
- last_seen

## keyword_model
- id
- client_id
- token
- category
- weight
- times_used
- updated_at
