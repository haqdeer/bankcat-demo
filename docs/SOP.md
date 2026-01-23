# BankCat Demo – Operating SOP (MVP)

## Purpose
This SOP explains how an accountant/bookkeeper will use the BankCat software
to process bank statements, categorize transactions, and generate reports
in an audit-safe manner.

---

## Step 1: Client & Bank Setup (One-time)
1. Open the application
2. Create or select a Client
3. Add client Banks (Current / Credit Card / Savings etc.)
4. Define Categories (Income / Expense / Other)

This setup controls learning and categorization behavior per client.

---

## Step 2: Statement Processing
1. Select Client
2. Select Bank
3. Select Period (Month / Year)
4. Upload bank statement (CSV / Excel)

System converts data into standard format:
Date | Description | Debit | Credit | Balance

---

## Step 3: Categorisation Review
1. Click “Process”
2. System suggests:
   - Category
   - Vendor
   - Reason
   - Confidence %

3. User reviews suggestions
4. User corrects Category/Vendor if needed

System does NOT auto-finalize.

---

## Step 4: Draft Save
- User can save work as Draft
- Draft data is editable
- Multiple banks can be processed before finalization

---

## Step 5: Commit & Lock
1. User clicks “Commit”
2. Transactions are locked
3. Final data is saved for reporting
4. Learning model is updated based on user confirmations

---

## Step 6: Reporting (Dashboard)
1. Select date range
2. View P&L by category
3. Review accuracy metrics

Only committed data appears in reports.

---

## Key Control Rules
- No transaction is silently deleted
- Amounts never appear inside Description
- Final decisions always belong to the user
- Learning is client-specific

Step 1: Client & Bank Setup is done inside Intro screen
## Categorisation (Mode-1 CSV)

### Step-5: Upload → Map → Standardize → Save Draft
- User selects Client, Bank, Period
- Upload CSV (already converted)
- Map columns to standard fields (Date, Description, Dr, Cr, Closing optional)
- System parses dates (supports missing year by using selected Period year)
- Save Draft stores rows in `transactions_draft` for that client+bank+period

### Step-6: Suggest → Review
- User clicks "Process Suggestions" to fill:
  suggested_category, suggested_vendor, confidence, reason
- User reviews and sets:
  final_category (dropdown), final_vendor (text)
- "Save Review Changes" updates draft rows only (not committed)
### Step-7: Commit / Lock
- User reviews draft and clicks Commit
- Draft rows are copied to committed table (read-only)
- System learns:
  - Vendor → Category (vendor_memory)
  - Keywords → Category (keyword_model)
- Accuracy metrics updated per commit
### Step-7: Commit / Lock / Learn
- Commit copies draft rows to transactions_committed (read-only)
- Updates draft_batches status to Committed
- Updates learning:
  - vendor_memory: vendor → category (+confidence)
  - keyword_model: tokens → category (weights)
- Stores commit metrics: rows_committed, accuracy
