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

@st.cache_data(ttl=10)
def cached_vendor_memory(client_id: int):
    return crud.list_vendor_memory(client_id)

def clear_cache():
    st.cache_data.clear()

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

# =========================
# 1) INTRO (Masters)
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
vendor_mem = cached_vendor_memory(client_id)

st.divider()
st.markdown("### Banks")
st.dataframe(pd.DataFrame(banks), use_container_width=True, hide_index=True)

st.divider()
st.markdown("### Categories")
st.dataframe(pd.DataFrame(cats), use_container_width=True, hide_index=True)

st.divider()

# =========================
# 2) Step-5 + Step-6
# =========================
st.subheader("2) Categorisation (Upload → Standardize → Suggest → Review)")

active_banks = [b for b in banks if b.get("is_active", True)]
bank_options = {f"{b['id']} | {b['bank_name']} ({b.get('account_type','')})": b["id"] for b in active_banks}

if not bank_options:
    st.warning("No active banks found for this client.")
    st.stop()

bank_label = st.selectbox("Select Bank", options=list(bank_options.keys()))
bank_id = bank_options[bank_label]
bank_row = next((b for b in active_banks if b["id"] == bank_id), {})
bank_account_type = bank_row.get("account_type", "")

# Statement period
months = [("Jan",1),("Feb",2),("Mar",3),("Apr",4),("May",5),("Jun",6),("Jul",7),("Aug",8),("Sep",9),("Oct",10),("Nov",11),("Dec",12)]
m_labels = [m[0] for m in months]
m_map = {m[0]: m[1] for m in months}

p1, p2, p3 = st.columns(3)
with p1:
    year = st.selectbox("Year", options=list(range(2020, 2031)), index=list(range(2020, 2031)).index(2025))
with p2:
    mon_label = st.selectbox("Month", options=m_labels, index=m_labels.index("Oct"))
with p3:
    period = f"{year}-{m_map[mon_label]:02d}"
    st.text_input("Period (auto)", value=period, disabled=True)

draft_periods = crud.list_draft_periods(client_id, bank_id)
st.markdown("### Existing Drafts (this client + bank)")
st.dataframe(pd.DataFrame(draft_periods), use_container_width=True, hide_index=True)

# ---- Upload template ----
st.markdown("### Statement CSV Template")
tmpl = pd.DataFrame([
    {"Date": "01 Oct", "Description": "POS Purchase Example Vendor", "Dr": "100.00", "Cr": "", "Closing": ""},
    {"Date": "02 Oct", "Description": "Bank Charges", "Dr": "25.00", "Cr": "", "Closing": ""},
])
buf = io.StringIO()
tmpl.to_csv(buf, index=False)
st.download_button("Download Statement CSV Template", data=buf.getvalue().encode("utf-8"),
                   file_name="statement_template.csv", mime="text/csv")

# ---- Upload ----
upload = st.file_uploader("Upload Statement (CSV)", type=["csv"])

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

if upload is not None:
    df = pd.read_csv(upload)
    st.success(f"Loaded ✅ Rows: {len(df)}")
    st.dataframe(df.head(15), use_container_width=True)

    cols = list(df.columns)
    col_date = st.selectbox("Map Date", options=cols, index=0)
    col_desc = st.selectbox("Map Description", options=cols, index=1 if len(cols) > 1 else 0)
    col_dr = st.selectbox("Map Debit (Dr)", options=["(blank)"] + cols, index=2 if len(cols) > 2 else 0)
    col_cr = st.selectbox("Map Credit (Cr)", options=["(blank)"] + cols, index=3 if len(cols) > 3 else 0)
    col_bal = st.selectbox("Map Closing (optional)", options=["(blank)"] + cols, index=4 if len(cols) > 4 else 0)

    standardized = []
    for _, r in df.iterrows():
        txd = parse_date_any(r.get(col_date), default_year=year)
        desc = str(r.get(col_desc, "")).strip()

        debit = None if col_dr == "(blank)" else clean_num(r.get(col_dr))
        credit = None if col_cr == "(blank)" else clean_num(r.get(col_cr))
        bal = None if col_bal == "(blank)" else clean_num(r.get(col_bal))

        if not txd or not desc:
            continue

        standardized.append({
            "tx_date": txd,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "balance": bal,
        })

    st.markdown("### Standardize Preview")
    st.write(f"Valid rows: **{len(standardized)}**")
    st.dataframe(pd.DataFrame(standardized[:200]), use_container_width=True, hide_index=True)

    replace_existing = st.checkbox("Replace existing draft for this bank+period", value=True)

    if st.button("Save Draft"):
        if replace_existing:
            crud.delete_draft_period(client_id, bank_id, period)
        crud.insert_draft_bulk(client_id, bank_id, period, standardized)
        st.success("Draft saved ✅")
        st.rerun()

st.divider()

# ---- Step-6: Process suggestions ----
st.subheader("Step-6: Suggest Category + Vendor (Draft)")

if st.button("Process Suggestions (for this bank+period)"):
    rows = crud.get_draft_rows(client_id, bank_id, period, limit=2000)
    if not rows:
        st.warning("No draft rows found for this bank+period.")
    else:
        cats_active = [c for c in cats if c.get("is_active", True)]
        vm = vendor_mem

        updates = []
        for r in rows:
            sc, sv, cf, rs = suggest_one(
                desc=r.get("description"),
                debit=float(r.get("debit") or 0) if r.get("debit") is not None else None,
                credit=float(r.get("credit") or 0) if r.get("credit") is not None else None,
                bank_account_type=bank_account_type,
                categories=cats_active,
                vendor_memory=vm,
            )
            updates.append({
                "id": r["id"],
                "suggested_category": sc,
                "suggested_vendor": sv,
                "confidence": cf,
                "reason": rs
            })

        crud.update_suggestions_bulk(updates)
        st.success(f"Processed ✅ rows: {len(updates)}")
        st.rerun()

# ---- Review UI ----
st.subheader("Review + Finalize (Draft)")

rows = crud.get_draft_rows(client_id, bank_id, period, limit=500)
if not rows:
    st.info("Upload + Save Draft first (then Process Suggestions).")
else:
    dfv = pd.DataFrame(rows)

    category_options = [c["category_name"] for c in cats if c.get("is_active", True)]
    # show suggestion but allow edit final
    if "final_category" not in dfv.columns:
        dfv["final_category"] = None
    if "final_vendor" not in dfv.columns:
        dfv["final_vendor"] = None

    st.caption("Tip: final_category/final_vendor edit karo. Save Review dabao. (ERP-style human-in-loop)")

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
        st.success("Saved ✅ final_category/final_vendor updated.")
        st.rerun()
