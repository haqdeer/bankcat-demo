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
