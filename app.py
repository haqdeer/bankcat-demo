import io
import re
import streamlit as st
import pandas as pd
from datetime import date

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
# SECTION 1: INTRO (Masters - light view)
# =========================================================
st.subheader("1) Intro (Client + Bank Selection)")

clients = cached_clients()
client_df = pd.DataFrame(clients) if clients else pd.DataFrame(columns=["id","name","industry","country","is_active","created_at"])
st.dataframe(client_df, use_container_width=True, hide_index=True)

client_options = {f"{r['id']} | {r['name']}": r["id"] for r in clients} if clients else {}
selected_label = st.selectbox("Select Client", options=["(Create new client first)"] + list(client_options.keys()))
client_id = client_options.get(selected_label)

if not client_id:
    st.info("Select a client to continue.")
    st.stop()

banks = cached_banks(client_id)
active_banks = [b for b in banks if b.get("is_active", True)]
bank_options = {f"{b['id']} | {b['bank_name']} ({b.get('account_type','')})": b["id"] for b in active_banks}

if not bank_options:
    st.warning("No active banks found. Create/enable a bank first.")
    st.stop()

bank_label = st.selectbox("Select Bank", options=list(bank_options.keys()))
bank_id = bank_options[bank_label]

st.divider()

# =========================================================
# SECTION 2: CATEGORISATION (Step-5)
# =========================================================
st.subheader("2) Categorisation (Upload → Map → Standardize → Save Draft)")

# ---- PERIOD (Statement month) + date range ----
st.markdown("### Statement Period")
months = [
    ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4), ("May", 5), ("Jun", 6),
    ("Jul", 7), ("Aug", 8), ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
]
m_labels = [m[0] for m in months]
m_map = {m[0]: m[1] for m in months}

c1, c2, c3 = st.columns(3)
with c1:
    year = st.selectbox("Year", options=list(range(2020, 2031)), index=list(range(2020, 2031)).index(2026))
with c2:
    mon_label = st.selectbox("Month", options=m_labels, index=m_labels.index("Jan"))
with c3:
    period = f"{year}-{m_map[mon_label]:02d}"
    st.text_input("Period (auto)", value=period, disabled=True)

st.caption("Period = statement month label (Sep 2025 etc). Even if date range overlaps months, keep period as statement month.")

st.markdown("### Statement Date Range (optional but recommended)")
# allow range that crosses months
date_range = st.date_input(
    "Select From-To",
    value=(date(year, m_map[mon_label], 1), date(year, m_map[mon_label], 28)),
)
# normalize
from_date, to_date = None, None
if isinstance(date_range, tuple) and len(date_range) == 2:
    from_date, to_date = date_range[0], date_range[1]

# ---- Draft summary ----
st.markdown("### Existing Drafts (this client + bank)")
draft_periods = crud.list_draft_periods(client_id, bank_id)
st.dataframe(pd.DataFrame(draft_periods), use_container_width=True, hide_index=True)

# ---- Download CSV template for uploads ----
st.markdown("### Upload Template (CSV)")
tmpl = pd.DataFrame([
    {"Date": "2025-09-01", "Description": "POS Purchase Example Vendor", "Dr": "100.00", "Cr": "", "Closing": "5000.00"},
    {"Date": "2025-09-02", "Description": "Bank Charges", "Dr": "25.00", "Cr": "", "Closing": "4975.00"},
    {"Date": "2025-09-03", "Description": "Customer Payment", "Dr": "", "Cr": "300.00", "Closing": "5275.00"},
])
buf = io.StringIO()
tmpl.to_csv(buf, index=False)
st.download_button(
    "Download Statement CSV Template",
    data=buf.getvalue().encode("utf-8"),
    file_name="statement_template.csv",
    mime="text/csv",
)

st.caption("Minimum required columns: Date + Description. Dr/Cr optional but recommended. Closing optional (can be blank).")

st.divider()

# ---- Upload (CSV only to avoid openpyxl dependency) ----
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

def parse_date_any(x):
    """
    Handles: 2025-09-01, 01-09-2025, 1/9/25 etc.
    """
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    # try dayfirst=True for Pakistani style dates too
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

if upload is not None:
    try:
        df = pd.read_csv(upload)

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

            st.markdown("### Standardize Preview")
            standardized = []
            errors = 0
            flags = 0
            out_of_range = 0

            for _, r in df.iterrows():
                txd = parse_date_any(r.get(col_date))
                desc = str(r.get(col_desc, "")).strip()

                debit = None if col_debit == "(blank)" else clean_num(r.get(col_debit))
                credit = None if col_credit == "(blank)" else clean_num(r.get(col_credit))
                bal = None if col_bal == "(blank)" else clean_num(r.get(col_bal))

                if not txd or not desc:
                    errors += 1
                    continue

                # optional: range check only if user selected range
                if from_date and to_date and not (from_date <= txd <= to_date):
                    out_of_range += 1
                    # still keep it (do not drop), because some statements include few lines outside
                    # but we count it for user awareness

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

            st.write(
                f"Rows parsed: **{len(standardized)}** | Dropped (missing date/desc): **{errors}** | "
                f"Flags (amount-in-desc suspicion): **{flags}** | Out-of-range (FYI): **{out_of_range}**"
            )
            st.dataframe(pd.DataFrame(standardized[:200]), use_container_width=True, hide_index=True)

            st.markdown("### Save Draft")
            replace_existing = st.checkbox("Replace existing draft for this bank+period", value=True)

            if st.button("Save Draft Now"):
                if len(standardized) == 0:
                    st.error("No valid rows to save.")
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
