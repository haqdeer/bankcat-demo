# DB Schema Truth

This file defines the expected column names per table for schema verification.

## clients
- id
- name
- industry
- country
- business_description
- is_active
- created_at

## banks
- id
- client_id
- bank_name
- account_number_masked
- account_type
- currency
- opening_balance
- is_active
- created_at

## categories
- id
- client_id
- category_code
- category_name
- type
- nature
- is_active
- created_at

## draft_batches
(Columns not defined in current app schema.)

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
- final_category
- final_vendor
- suggested_category
- suggested_vendor
- confidence
- reason
- status
- created_at

## commits
- id
- client_id
- bank_id
- period
- committed_by
- rows_committed
- accuracy
- is_active
- created_at

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
- suggested_category
- suggested_vendor
- confidence
- reason
- created_at

## vendor_memory
- id
- client_id
- vendor_name
- category_name
- confidence
- times_used
- updated_at

## keyword_model
- id
- client_id
- token
- category
- weight
- times_used
