import io
import re
import streamlit as st
import pandas as pd

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
st.markdown("### Banks")
st.dataframe(pd.DataFrame(banks), use_container_width=True, hide_index=True)

st.divider()
st.markdown("### Categories")
st.dataframe(pd.DataFrame(cats), use_container_width=True, hide_index=True)

st.divider()

# =========================
# 2) CATEGORISATION
# =========================
st.subheader("2) Categorisation (Draft → Suggest → Review)")

active_banks = [b for b in banks if b.get("is_active", True)]
bank_options = {f"{b['id']} | {b['bank_name']} ({b.get('account_type','')})": b["id"] for b in active_banks}

if not bank_options:
    st.warning("No active banks found for this client.")
    st.stop()

bank_label = st.selectbox("Select Bank", options=list(bank_options.keys()))
bank_id = bank_options[bank_label]
bank_row = next((b for b in active_banks if b["id"] == bank_id), {})
bank_account_type = bank_row.get("account_type", "")

# Period (simple)
year = st.selectbox("Year", options=list(range(2020, 2031)), index=list(range(2020, 2031)).index(2025))
month = st.selectbox("Month", options=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], index=9)
m_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
period = f"{year}-{m_map[month]:02d}"
st.text_input("Period (auto)", value=period, disabled=True)

draft_periods = crud.list_draft_periods(client_id, bank_id)
st.markdown("### Existing Drafts (this client + bank)")
st.dataframe(pd.DataFrame(draft_periods), use_container_width=True, hide_index=True)

st.divider()

# =========================
# Step-6 Suggest
# =========================
st.subheader("Step-6: Suggest Category + Vendor (Draft)")

def safe_vendor_memory(cid: int):
    # Never crash the app if vendor_memory table isn't ready
    if hasattr(crud, "list_vendor_memory"):
        try:
            return crud.list_vendor_memory(cid)
        except Exception:
            return []
    return []

if st.button("Process Suggestions (for this bank+period)"):
    rows = crud.get_draft_rows(client_id, bank_id, period, limit=3000)
    if not rows:
        st.warning("No draft rows found for this bank+period. Save draft first.")
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

    st.caption("Final fields editable: final_category + final_vendor. Save to persist.")
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
        st.success("Saved ✅")
        st.rerun()
