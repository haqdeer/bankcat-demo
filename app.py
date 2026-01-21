import streamlit as st
import pandas as pd

from src.db import ping_db
from src.schema import init_db
from src.crud import (
    list_clients, add_client,
    list_banks, add_bank,
    list_categories, add_category
)

st.set_page_config(page_title="BankCat Demo", layout="wide")
st.title("BankCat Demo ✅")

# ------------------ Sidebar: Utilities ------------------
with st.sidebar:
    st.header("Utilities")
    if st.button("Test DB Connection"):
        try:
            val = ping_db()
            st.success(f"DB Connected ✅ (select 1 = {val})")
        except Exception as e:
            st.error(f"DB connection failed ❌\n\n{e}")

    if st.button("Initialize Database (Create Tables)"):
        try:
            msg = init_db()
            st.success(msg)
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{e}")

st.divider()

# ------------------ Page: Intro (Clients + Banks + Categories) ------------------
st.subheader("Intro (Client Profile & Masters)")

clients = list_clients()
if not clients:
    st.warning("No clients yet. Create your first client below.")
else:
    st.caption("Existing clients")

client_df = pd.DataFrame(clients) if clients else pd.DataFrame(columns=["id","name","industry","country","created_at"])
st.dataframe(client_df, use_container_width=True, hide_index=True)

# Client selector
client_options = {f"{row['id']} | {row['name']}": row["id"] for row in clients} if clients else {}
selected_label = st.selectbox("Select Client", options=["(Create new client first)"] + list(client_options.keys()))
selected_client_id = client_options.get(selected_label)

st.divider()

# ---- Create Client ----
st.markdown("### A) Create New Client")
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
    submitted = st.form_submit_button("Create Client")

    if submitted:
        if not name.strip():
            st.error("Client/Company Name is required.")
        else:
            new_id = add_client(name, business_description, industry, country)
            st.success(f"Client created ✅ (ID: {new_id}). Refreshing list…")
            st.rerun()

st.divider()

# If no client selected, stop here
if not selected_client_id:
    st.info("Select a client above to manage Banks and Categories.")
    st.stop()

# ------------------ Banks Section ------------------
st.markdown("### B) Banks (Client-specific Master)")
banks = list_banks(selected_client_id)
banks_df = pd.DataFrame(banks) if banks else pd.DataFrame(columns=[
    "id","bank_name","account_masked","account_type","currency","opening_balance","created_at"
])
st.dataframe(banks_df, use_container_width=True, hide_index=True)

with st.form("add_bank_form", clear_on_submit=True):
    b1, b2, b3 = st.columns(3)
    with b1:
        bank_name = st.text_input("Bank Name *")
        account_type = st.selectbox("Account Type *", options=["Current", "Credit Card", "Savings", "Investment", "Wallet", "Other"])
    with b2:
        account_masked = st.text_input("Account Number / Masked ID (optional)")
        currency = st.text_input("Currency (optional)", value="PKR")
    with b3:
        opening_balance = st.number_input("Opening Balance (optional)", value=0.0, step=1000.0)

    bank_submit = st.form_submit_button("Add Bank")

    if bank_submit:
        if not bank_name.strip():
            st.error("Bank Name is required.")
        else:
            add_bank(selected_client_id, bank_name, account_masked, account_type, currency, opening_balance)
            st.success("Bank added ✅")
            st.rerun()

st.divider()

# ------------------ Categories Section ------------------
st.markdown("### C) Category Master (Client-specific)")
cats = list_categories(selected_client_id)
cats_df = pd.DataFrame(cats) if cats else pd.DataFrame(columns=[
    "id","category_code","category_name","type","nature","created_at"
])
st.dataframe(cats_df, use_container_width=True, hide_index=True)

with st.form("add_category_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        category_name = st.text_input("Category Name *")
    with c2:
        type_ = st.selectbox("Type *", options=["Income", "Expense", "Other"])
    with c3:
        nature = st.selectbox("Nature *", options=["Dr", "Cr", "Any"])

    cat_submit = st.form_submit_button("Add Category")

    if cat_submit:
        if not category_name.strip():
            st.error("Category Name is required.")
        else:
            add_category(selected_client_id, category_name, type_, nature)
            st.success("Category added ✅")
            st.rerun()

st.divider()
st.info("Next: Categorisation screen (upload CSV/XLSX → standardize → suggest → draft save).")
