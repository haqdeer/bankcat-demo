import io
import re
import streamlit as st
import pandas as pd

from src.db import ping_db
from src.schema import init_db
import src.crud as crud

st.set_page_config(page_title="BankCat Demo", layout="wide")
st.title("BankCat Demo ✅")

# -------- cache (speed) --------
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

# -------- sidebar utilities --------
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
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{e}")

    if st.button("Refresh Lists"):
        clear_cache()
        st.success("Refreshed ✅")
        st.rerun()

st.divider()

# =========================================================
# SECTION 1: INTRO (Masters)
# =========================================================
st.subheader("1) Intro (Client Profile & Masters)")

clients = cached_clients()
client_df = pd.DataFrame(clients) if clients else pd.DataFrame(columns=["id","name","industry","country","is_active","created_at"])
st.dataframe(client_df, use_container_width=True, hide_index=True)

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
    business_description = st.text_area("Business Description (optional)", height=80)

    if st.form_submit_button("Create Client"):
        if not name.strip():
            st.error("Client/Company Name is required.")
        else:
            crud.add_client(name, business_description, industry, country)
            clear_cache()
            st.success("Client created ✅")
            st.rerun()

if not client_id:
    st.info("Select a client to continue.")
    st.stop()

banks = cached_banks(client_id)
cats = cached_categories(client_id)

st.markdown("### Banks (View)")
st.dataframe(pd.DataFrame(banks), use_container_width=True, hide_index=True)

st.markdown("### Categories (View)")
st.dataframe(pd.DataFrame(cats), use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# SECTION 2: CATEGORISATION (Step-5)
# =========================================================
st.subheader("2) Categorisation (Upload → Map → Standardize → Save Draft)")

# ---- selectors ----
active_banks = [b for b in banks if b.get("is_active", True)]
bank_options = {f"{b['id']} | {b['bank_name']} ({b.get('account_type','')})": b["id"] for b in active_banks}

if not bank_options:
    st.warning("No active banks found for this client. Create/enable a bank first.")
    st.stop()

bank_label = st.selectbox("Select Bank (Bank Code)", options=list(bank_options.keys()))
bank_id = bank_options[bank_label]

period = st.text_input("Period (YYYY-MM)", value="2026-01")
st.caption("Tip: Period is used for draft grouping and later commit/reporting.")

# ---- draft summary ----
st.markdown("### Existing Drafts (this client + bank)")
draft_periods = crud.list_draft_periods(client_id, bank_id)
st.dataframe(pd.DataFrame(draft_periods), use_container_width=True, hide_index=True)

st.markdown("### Upload Statement (CSV/XLSX) — Mode 1 (already converted)")

upload = st.file_uploader("Upload file", type=["csv", "xlsx"])

def clean_num(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = s.replace(",", "").replace(" ", "")
    # handle 1,234.56Cr or 1234CR patterns
    s = re.sub(r"(cr|dr)$", "", s, flags=re.IGNORECASE)
    try:
        return float(s)
    except:
        return None

def parse_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def flag_amount_in_desc(desc: str) -> bool:
    if not desc:
        return False
    # if description ends with big number pattern -> possible amount pushed into desc
    return bool(re.search(r"(\b\d{1,3}(,\d{3})*(\.\d+)?\b)\s*$", desc.strip()))

if upload is not None:
    try:
        if upload.name.lower().endswith(".csv"):
            df = pd.read_csv(upload)
        else:
            df = pd.read_excel(upload)

        if df.empty:
            st.error("File is empty.")
        else:
            st.success(f"Loaded ✅ Rows: {len(df)}")
            st.dataframe(df.head(20), use_container_width=True)

            cols = list(df.columns)

            def guess_col(keywords):
                for c in cols:
                    low = str(c).lower()
                    if any(k in low for k in keywords):
                        return c
                return None

            guess_date = guess_col(["date", "tx_date", "transaction date"])
            guess_desc = guess_col(["description", "details", "narration", "merchant"])
            guess_debit = guess_col(["debit", "dr", "withdrawal", "paid out"])
            guess_credit = guess_col(["credit", "cr", "deposit", "paid in"])
            guess_bal = guess_col(["balance", "closing", "running"])

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

            st.markdown("### Standardize Preview")
            standardized = []
            errors = 0
            flags = 0

            for _, r in df.iterrows():
                txd = parse_date(r.get(col_date))
                desc = str(r.get(col_desc, "")).strip()
                debit = None if col_debit == "(blank)" else clean_num(r.get(col_debit))
                credit = None if col_credit == "(blank)" else clean_num(r.get(col_credit))
                bal = None if col_bal == "(blank)" else clean_num(r.get(col_bal))

                if not txd or not desc:
                    errors += 1
                    continue

                if flag_amount_in_desc(desc) and (debit is None and credit is None):
                    flags += 1

                # basic: both debit and credit filled -> keep as is but mark low confidence later
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

            st.write(f"Rows parsed: **{len(standardized)}** | Dropped (missing date/desc): **{errors}** | Flags (amount-in-desc suspicion): **{flags}**")
            preview_df = pd.DataFrame(standardized[:200])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            st.markdown("### Save Draft")
            colA, colB = st.columns(2)

            with colA:
                replace_existing = st.checkbox("Replace existing draft for this bank+period", value=True)
                st.caption("If ON: system will delete old draft rows for this bank+period and insert fresh upload.")

            with colB:
                if st.button("Save Draft Now"):
                    if not re.match(r"^\d{4}-\d{2}$", period.strip()):
                        st.error("Period format must be YYYY-MM (e.g., 2026-01).")
                    elif len(standardized) == 0:
                        st.error("No valid rows to save.")
                    else:
                        if replace_existing:
                            deleted = crud.delete_draft_period(client_id, bank_id, period.strip())
                            st.info(f"Deleted previous draft rows: {deleted}")

                        inserted = crud.insert_draft_bulk(client_id, bank_id, period.strip(), standardized)
                        st.success(f"Draft saved ✅ Inserted rows: {inserted}")
                        st.rerun()

    except Exception as e:
        st.error(f"Upload/Parse failed ❌\n\n{e}")

st.divider()

# ---- view a draft sample ----
st.subheader("Draft Viewer (Sample)")
if draft_periods:
    p_list = [d["period"] for d in draft_periods]
    sel_p = st.selectbox("Select draft period to view", options=p_list)
    sample = crud.get_draft_sample(client_id, bank_id, sel_p, limit=200)
    st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)

    if st.button("Delete this draft period"):
        deleted = crud.delete_draft_period(client_id, bank_id, sel_p)
        st.warning(f"Deleted rows: {deleted}")
        st.rerun()
else:
    st.info("No drafts yet for this bank.")
