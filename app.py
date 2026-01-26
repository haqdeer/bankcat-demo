import io
import re
import streamlit as st
import pandas as pd
from datetime import date

from src.db import ping_db
from src.schema import init_db
import src.crud as crud
from src.engine import suggest_one

st.set_page_config(page_title="BankCat Demo", layout="wide")
st.title("BankCat Demo ✅")

@st.cache_data(ttl=10)
def cached_clients():
    return crud.list_clients(include_inactive=True)

@st.cache_data(ttl=10)
def cached_banks(client_id: int):
    return crud.list_banks(client_id, include_inactive=True)

@st.cache_data(ttl=10)
def cached_categories(client_id: int):
    return crud.list_categories(client_id, include_inactive=True)

def clear_cache():
    st.cache_data.clear()

def safe_vendor_memory(client_id: int):
    if hasattr(crud, "list_vendor_memory"):
        try:
            return crud.list_vendor_memory(client_id)
        except Exception:
            return []
    return []

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Utilities")

    if st.button("Test DB Connection"):
        try:
            val = ping_db()
            st.success(f"DB Connected ✅ (select 1 = {val})")
        except Exception as e:
            st.error(f"DB connection failed ❌\n\n{e}")

    if st.button("Initialize/ Migrate DB"):
        try:
            msg = init_db()
            clear_cache()
            st.success(msg)
            st.rerun()
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{e}")

    if st.button("Refresh Lists"):
        clear_cache()
        st.success("Refreshed ✅")
        st.rerun()

st.divider()

# =========================
# 1) INTRO
# =========================
st.subheader("1) Intro (Client Profile & Masters)")

clients = cached_clients()
st.dataframe(pd.DataFrame(clients), use_container_width=True, hide_index=True)

client_options = {f"{r['id']} | {r['name']}": r["id"] for r in clients} if clients else {}
selected_label = st.selectbox("Select Client", options=["(Create new client first)"] + list(client_options.keys()))
client_id = client_options.get(selected_label)

st.markdown("### Create New Client")
with st.form("create_client_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Client/Company Name *")
        industry = st.selectbox("Industry", options=[
            "Professional Services", "Retail", "E-Commerce", "Manufacturing",
            "Real Estate", "NGO/Non-Profit", "Hospitality", "Other"
        ])
    with c2:
        country = st.text_input("Country (optional)", value="")
    business_description = st.text_area("Business Description (optional)", height=90)

    if st.form_submit_button("Create Client"):
        if not name.strip():
            st.error("Client/Company Name is required.")
        else:
            crud.add_client(name, business_description, industry, country)
            clear_cache()
            st.success("Client created ✅")
            st.rerun()

if not client_id:
    st.stop()

banks = cached_banks(client_id)
cats = cached_categories(client_id)

st.divider()
st.markdown("## Banks (Client-specific Master)")
st.dataframe(pd.DataFrame(banks), use_container_width=True, hide_index=True)

with st.form("add_bank_form", clear_on_submit=True):
    b1, b2, b3 = st.columns(3)
    with b1:
        bank_name = st.text_input("Bank Name *")
        account_type = st.selectbox("Account Type *", options=["Current","Credit Card","Savings","Investment","Wallet","Other"])
    with b2:
        account_masked = st.text_input("Account Number / Masked ID (optional)")
        currency = st.text_input("Currency (optional)", value="PKR")
    with b3:
        opening_balance = st.number_input("Opening Balance (optional)", value=0.0, step=1000.0)

    if st.form_submit_button("Add Bank"):
        if not bank_name.strip():
            st.error("Bank Name is required.")
        else:
            crud.add_bank(client_id, bank_name, account_masked, account_type, currency, opening_balance)
            clear_cache()
            st.success("Bank added ✅")
            st.rerun()

st.divider()
st.markdown("## Categories (Client-specific Master)")
st.dataframe(pd.DataFrame(cats), use_container_width=True, hide_index=True)

st.markdown("### Download Category Template (CSV)")
tmpl_cat = pd.DataFrame([
    {"category_name": "Meals & Entertainment", "type": "Expense", "nature": "Debit"},
    {"category_name": "Sales", "type": "Income", "nature": "Credit"},
    {"category_name": "Internal Transfer", "type": "Other", "nature": "Any"},
])
buf_cat = io.StringIO()
tmpl_cat.to_csv(buf_cat, index=False)
st.download_button(
    "Download Category CSV Template",
    data=buf_cat.getvalue().encode("utf-8"),
    file_name="category_template.csv",
    mime="text/csv",
)

st.markdown("### Add Single Category")
with st.form("add_category_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        category_name = st.text_input("Category Name *")
    with c2:
        type_ = st.selectbox("Type *", options=["Income","Expense","Other"])
    with c3:
        nature = st.selectbox("Nature *", options=["Debit","Credit","Any"])

    if st.form_submit_button("Add Category (Single)"):
        if not category_name.strip():
            st.error("Category Name is required.")
        else:
            crud.add_category(client_id, category_name, type_, nature)
            clear_cache()
            st.success("Category added ✅")
            st.rerun()

st.markdown("### Bulk Upload Categories (CSV)")
upload_cat = st.file_uploader("Upload Categories CSV", type=["csv"], key="cat_upload")
if upload_cat is not None:
    try:
        dfc = pd.read_csv(upload_cat)
        cols = list(dfc.columns)
        col_name = st.selectbox("Map: Category Name *", options=cols, index=0, key="cat_map_name")
        col_type = st.selectbox("Map: Type (optional)", options=["(use default)"] + cols, index=0, key="cat_map_type")
        col_nat = st.selectbox("Map: Nature (optional)", options=["(use default)"] + cols, index=0, key="cat_map_nat")

        default_type = st.selectbox("Default Type", options=["Expense","Income","Other"], index=0, key="cat_def_type")
        default_nature = st.selectbox("Default Nature", options=["Debit","Credit","Any"], index=0, key="cat_def_nature")

        prepared = []
        for _, r in dfc.iterrows():
            nm = str(r.get(col_name, "")).strip()
            if not nm:
                continue
            tp = default_type if col_type == "(use default)" else str(r.get(col_type, default_type)).strip() or default_type
            nt = default_nature if col_nat == "(use default)" else str(r.get(col_nat, default_nature)).strip() or default_nature
            prepared.append((nm, tp, nt, None))

        if st.button("Import Categories Now", key="cat_import_btn"):
            result = crud.bulk_add_categories(client_id, prepared)
            clear_cache()
            st.success(f"Imported ✅ Inserted: {result['inserted']} | Skipped: {result['skipped']}")
            st.rerun()

    except Exception as e:
        st.error(f"Category import failed ❌\n\n{e}")

st.divider()

# =========================
# 2) CATEGORISATION
# =========================
st.subheader("2) Categorisation (Upload → Map → Standardize → Save Draft → Suggest → Review → Commit)")

active_banks = [b for b in banks if b.get("is_active", True)]
bank_options = {f"{b['id']} | {b['bank_name']} ({b.get('account_type','')})": b["id"] for b in active_banks}
if not bank_options:
    st.warning("No active banks found for this client.")
    st.stop()

bank_label = st.selectbox("Select Bank (for statement upload)", options=list(bank_options.keys()))
bank_id = bank_options[bank_label]
bank_row = next((b for b in active_banks if b["id"] == bank_id), {})
bank_account_type = bank_row.get("account_type", "")

# Period
months = [("Jan",1),("Feb",2),("Mar",3),("Apr",4),("May",5),("Jun",6),("Jul",7),("Aug",8),("Sep",9),("Oct",10),("Nov",11),("Dec",12)]
m_labels = [m[0] for m in months]
m_map = {m[0]: m[1] for m in months}

st.markdown("### Statement Period")
p1, p2, p3 = st.columns(3)
with p1:
    year = st.selectbox("Year", options=list(range(2020, 2031)), index=list(range(2020, 2031)).index(2025))
with p2:
    mon_label = st.selectbox("Month", options=m_labels, index=m_labels.index("Oct"))
with p3:
    period = f"{year}-{m_map[mon_label]:02d}"
    st.text_input("Period (auto)", value=period, disabled=True)

st.caption("Period = statement month label. Even if date range overlaps months, keep period as statement month.")

st.markdown("### Statement Date Range (optional but recommended)")
date_range = st.date_input(
    "Select From-To",
    value=(date(year, m_map[mon_label], 1), date(year, m_map[mon_label], 28)),
)
from_date, to_date = None, None
if isinstance(date_range, tuple) and len(date_range) == 2:
    from_date, to_date = date_range[0], date_range[1]

st.markdown("### Existing Drafts (this client + bank)")
draft_periods = crud.list_draft_periods(client_id, bank_id)
st.dataframe(pd.DataFrame(draft_periods), use_container_width=True, hide_index=True)

st.markdown("### Upload Template (CSV)")
tmpl = pd.DataFrame([
    {"Date": "2025-10-01", "Description": "POS Purchase Example Vendor", "Dr": "100.00", "Cr": "", "Closing": "5000.00"},
    {"Date": "01 Oct", "Description": "Example without year (system uses selected period year)", "Dr": "25.00", "Cr": "", "Closing": ""},
])
buf = io.StringIO()
tmpl.to_csv(buf, index=False)
st.download_button(
    "Download Statement CSV Template",
    data=buf.getvalue().encode("utf-8"),
    file_name="statement_template.csv",
    mime="text/csv",
)
st.caption("Minimum: Date + Description. Dr/Cr recommended. Closing optional (blank allowed).")

st.divider()
st.markdown("### Upload Statement (CSV) — Mode 1 (already converted)")
upload = st.file_uploader("Upload CSV file", type=["csv"])

def clean_num(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = s.replace(",", "").replace(" ", "")
    s = re.sub(r"(cr|dr)$", "", s, flags=re.IGNORECASE)
    try:
        return float(s)
    except:
        return None

def parse_date_any(x, default_year: int):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", s))
    if not has_year:
        s = f"{s} {default_year}"
    for dayfirst in (True, False):
        try:
            return pd.to_datetime(s, dayfirst=dayfirst, errors="raise").date()
        except:
            pass
    return None

def flag_amount_in_desc(desc: str) -> bool:
    if not desc:
        return False
    return bool(re.search(r"(\b\d{1,3}(,\d{3})*(\.\d+)?\b)\s*$", desc.strip()))

standardized = []
bad_dates_examples = []

if upload is not None:
    try:
        df = pd.read_csv(upload)
        if df.empty:
            st.error("File is empty.")
        else:
            st.success(f"Loaded ✅ Rows: {len(df)}")
            st.dataframe(df.head(20), use_container_width=True)

            cols = list(df.columns)

            def guess_col(keys):
                for c in cols:
                    low = str(c).lower()
                    if any(k in low for k in keys):
                        return c
                return None

            guess_date = guess_col(["date"])
            guess_desc = guess_col(["description", "details", "narration", "merchant"])
            guess_debit = guess_col(["debit", "dr", "withdrawal"])
            guess_credit = guess_col(["credit", "cr", "deposit"])
            guess_bal = guess_col(["balance", "closing"])

            st.markdown("### Map Columns → Standard Format")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                col_date = st.selectbox("Date *", options=cols, index=cols.index(guess_date) if guess_date in cols else 0)
            with m2:
                col_desc = st.selectbox("Description *", options=cols, index=cols.index(guess_desc) if guess_desc in cols else 0)
            with m3:
                col_debit = st.selectbox("Debit (Dr)", options=["(blank)"] + cols,
                                         index=(["(blank)"] + cols).index(guess_debit) if guess_debit in cols else 0)
            with m4:
                col_credit = st.selectbox("Credit (Cr)", options=["(blank)"] + cols,
                                          index=(["(blank)"] + cols).index(guess_credit) if guess_credit in cols else 0)
            with m5:
                col_bal = st.selectbox("Closing Balance", options=["(blank)"] + cols,
                                       index=(["(blank)"] + cols).index(guess_bal) if guess_bal in cols else 0)

            errors = 0
            flags = 0
            out_of_range = 0
            standardized = []
            bad_dates_examples = []

            for _, r in df.iterrows():
                raw_date = r.get(col_date)
                txd = parse_date_any(raw_date, default_year=year)
                desc = str(r.get(col_desc, "")).strip()

                debit = None if col_debit == "(blank)" else clean_num(r.get(col_debit))
                credit = None if col_credit == "(blank)" else clean_num(r.get(col_credit))
                bal = None if col_bal == "(blank)" else clean_num(r.get(col_bal))

                if not txd or not desc:
                    errors += 1
                    if not txd and len(bad_dates_examples) < 5:
                        bad_dates_examples.append(str(raw_date))
                    continue

                if from_date and to_date and not (from_date <= txd <= to_date):
                    out_of_range += 1

                if flag_amount_in_desc(desc) and (debit is None and credit is None):
                    flags += 1

                standardized.append({
                    "tx_date": txd,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": bal,
                    "suggested_category": None,
                    "suggested_vendor": None,
                    "reason": None,
                    "confidence": None
                })

            st.markdown("### Standardize Preview")
            st.write(
                f"Rows parsed: **{len(standardized)}** | Dropped (missing date/desc): **{errors}** | "
                f"Flags (amount-in-desc suspicion): **{flags}** | Out-of-range (FYI): **{out_of_range}**"
            )
            if bad_dates_examples:
                st.warning(f"Some date values could not be parsed (examples): {bad_dates_examples}")
            st.dataframe(pd.DataFrame(standardized[:200]), use_container_width=True, hide_index=True)

            st.markdown("### Save Draft")
            replace_existing = st.checkbox("Replace existing draft for this bank+period", value=True)

            if st.button("Save Draft Now"):
                if len(standardized) == 0:
                    st.error("No valid rows to save. (Date parsing failed).")
                else:
                    if replace_existing:
                        deleted = crud.delete_draft_period(client_id, bank_id, period)
                        st.info(f"Deleted previous draft rows: {deleted}")

                    inserted = crud.insert_draft_bulk(client_id, bank_id, period, standardized)
                    st.success(f"Draft saved ✅ Inserted rows: {inserted}")
                    st.rerun()

    except Exception as e:
        st.error(f"Upload/Parse failed ❌\n\n{e}")

st.divider()

# =========================
# Step-6 Suggest
# =========================
st.subheader("Step-6: Suggest Category + Vendor (Draft)")

if st.button("Process Suggestions (for this bank+period)"):
    rows = crud.get_draft_rows(client_id, bank_id, period, limit=3000)
    if not rows:
        st.warning("No draft rows found for this bank+period. Upload + Save Draft first.")
    else:
        cats_active = [c for c in cats if c.get("is_active", True)]
        vendor_mem = safe_vendor_memory(client_id)

        updates = []
        for r in rows:
            sc, sv, cf, rs = suggest_one(
                desc=r.get("description"),
                debit=float(r.get("debit") or 0) if r.get("debit") is not None else None,
                credit=float(r.get("credit") or 0) if r.get("credit") is not None else None,
                bank_account_type=bank_account_type,
                categories=cats_active,
                vendor_memory=vendor_mem,
            )
            updates.append({
                "id": r["id"],
                "suggested_category": sc,
                "suggested_vendor": sv,
                "confidence": cf,
                "reason": rs
            })

        crud.update_suggestions_bulk(updates)
        crud.upsert_draft_batch(client_id, bank_id, period, "System Categorised")
        st.success(f"Processed ✅ rows: {len(updates)}")
        st.rerun()

# Review
st.subheader("Review + Finalize (Draft)")

rows = crud.get_draft_rows(client_id, bank_id, period, limit=500)
if not rows:
    st.info("No draft rows for this bank+period.")
else:
    dfv = pd.DataFrame(rows)
    category_options = [c["category_name"] for c in cats if c.get("is_active", True)]

    st.caption("Editable fields: final_category + final_vendor. This saves INSIDE draft (not Commit).")
    edited = st.data_editor(
        dfv[["id","tx_date","description","debit","credit","balance","suggested_category","suggested_vendor","confidence","reason","final_category","final_vendor"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "final_category": st.column_config.SelectboxColumn("final_category", options=category_options),
        },
        disabled=["id","tx_date","description","debit","credit","balance","suggested_category","suggested_vendor","confidence","reason"],
        key="review_editor"
    )

    if st.button("Save Review Changes"):
        changed = []
        for _, r in edited.iterrows():
            changed.append({
                "id": int(r["id"]),
                "final_category": r.get("final_category"),
                "final_vendor": r.get("final_vendor")
            })
        crud.save_review_bulk(changed)
        crud.upsert_draft_batch(client_id, bank_id, period, "User Completed")
        st.success("Saved ✅ Draft updated (final_category/final_vendor).")
        st.rerun()

st.divider()

# =========================
# Step-7 Commit / Lock / Learn
# =========================
st.subheader("Step-7: Commit / Lock / Learn (FINAL)")

rows_all = crud.get_draft_rows(client_id, bank_id, period, limit=5000)
if not rows_all:
    st.info("No draft rows to commit for this bank+period.")
else:
    total = len(rows_all)
    filled = sum(1 for r in rows_all if (r.get("final_category") and str(r.get("final_category")).strip()))
    st.write(f"Rows in draft: **{total}** | Rows with final_category: **{filled}**")

    committed_by = st.text_input("Committed by (optional)", value="")

    confirm = st.checkbox("I confirm: categories/vendors are final and should be locked for reporting (Commit).", value=False)
    if st.button("✅ Commit This Period (Lock & Learn)", disabled=not confirm):
        result = crud.commit_period(client_id, bank_id, period, committed_by=committed_by or None)
        if not result.get("ok"):
            st.error(result.get("msg"))
        else:
            st.success(result.get("msg"))
            st.rerun()

st.markdown("### Committed Sample (this bank + period)")
try:
    sample = crud.committed_sample(client_id, bank_id, period, limit=200)
    st.dataframe(sample, use_container_width=True)
except Exception as e:
    st.info("No committed data yet (or table not ready). Run a Commit first, or re-run Initialize/Migrate DB.")
if sample:
    st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)
else:
    st.info("No committed rows yet for this period.")

st.divider()

# =========================
# Draft Viewer (Sample)
# =========================
st.subheader("Draft Viewer (Sample)")

if draft_periods:
    p_list = [d["period"] for d in draft_periods]
    sel_p = st.selectbox("Select draft period to view", options=p_list, key="draft_view_sel")
    sample_d = crud.get_draft_sample(client_id, bank_id, sel_p, limit=200)
    st.dataframe(pd.DataFrame(sample_d), use_container_width=True, hide_index=True)

    if st.button("Delete this draft period", key="draft_del_btn"):
        deleted = crud.delete_draft_period(client_id, bank_id, sel_p)
        st.warning(f"Deleted rows: {deleted}")
        st.rerun()
else:
    st.info("No drafts yet for this bank.")
