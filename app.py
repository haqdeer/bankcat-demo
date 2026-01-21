import io
import streamlit as st
import pandas as pd

from src.db import ping_db
from src.schema import init_db
from src.crud import (
    list_clients, add_client,
    list_banks, add_bank,
    list_categories, add_category, bulk_add_categories
)

st.set_page_config(page_title="BankCat Demo", layout="wide")
st.title("BankCat Demo ✅")

# ------------------ Caching (speed) ------------------
@st.cache_data(ttl=10)
def cached_clients():
    return list_clients()

@st.cache_data(ttl=10)
def cached_banks(client_id: int):
    return list_banks(client_id)

@st.cache_data(ttl=10)
def cached_categories(client_id: int):
    return list_categories(client_id)

def clear_cache():
    st.cache_data.clear()

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

    if st.button("Refresh Lists (Clear Cache)"):
        clear_cache()
        st.success("Cache cleared ✅")
        st.rerun()

st.divider()

# ------------------ Page: Intro (Clients + Banks + Categories) ------------------
st.subheader("Intro (Client Profile & Masters)")

clients = cached_clients()
client_df = pd.DataFrame(clients) if clients else pd.DataFrame(columns=["id", "name", "industry", "country", "created_at"])
st.dataframe(client_df, use_container_width=True, hide_index=True)

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
            _ = add_client(name, business_description, industry, country)
            clear_cache()
            st.success("Client created ✅")
            st.rerun()

st.divider()

if not selected_client_id:
    st.info("Select a client above to manage Banks and Categories.")
    st.stop()

# ------------------ Banks Section ------------------
st.markdown("### B) Banks (Client-specific Master)")
banks = cached_banks(selected_client_id)
banks_df = pd.DataFrame(banks) if banks else pd.DataFrame(columns=[
    "id", "bank_name", "account_masked", "account_type", "currency", "opening_balance", "created_at"
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
            clear_cache()
            st.success("Bank added ✅")
            st.rerun()

st.divider()

# ------------------ Categories Section ------------------
st.markdown("### C) Category Master (Client-specific)")

cats = cached_categories(selected_client_id)
cats_df = pd.DataFrame(cats) if cats else pd.DataFrame(columns=[
    "id", "category_code", "category_name", "type", "nature", "created_at"
])
st.dataframe(cats_df, use_container_width=True, hide_index=True)

# ---- Download Template ----
st.markdown("#### Download Category Template")
tmpl = pd.DataFrame([
    {"category_name": "Meals & Entertainment", "type": "Expense", "nature": "Dr"},
    {"category_name": "Sales", "type": "Income", "nature": "Cr"},
    {"category_name": "Internal Transfer", "type": "Other", "nature": "Any"},
])
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    tmpl.to_excel(writer, index=False, sheet_name="categories")
st.download_button(
    label="Download Excel Template",
    data=buf.getvalue(),
    file_name="category_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption("User only fills: category_name (required). Type/Nature optional. System auto-generates category_code, id, created_at.")

st.divider()

# Manual add (still available)
st.markdown("#### Add Single Category")
with st.form("add_category_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        category_name = st.text_input("Category Name *")
    with c2:
        type_ = st.selectbox("Type *", options=["Income", "Expense", "Other"])
    with c3:
        nature = st.selectbox("Nature *", options=["Dr", "Cr", "Any"])

    cat_submit = st.form_submit_button("Add Category (Single)")

    if cat_submit:
        if not category_name.strip():
            st.error("Category Name is required.")
        else:
            add_category(selected_client_id, category_name, type_, nature)
            clear_cache()
            st.success("Category added ✅")
            st.rerun()

st.divider()

# -------- Bulk import categories from Excel/CSV --------
st.markdown("#### Bulk Upload Categories (Excel/CSV)")
st.caption("Minimum required column: category_name (or any column you map as Category Name). Type/Nature optional.")

upload = st.file_uploader("Upload Categories File", type=["csv", "xlsx"])
if upload is not None:
    try:
        if upload.name.lower().endswith(".csv"):
            df = pd.read_csv(upload)
        else:
            df = pd.read_excel(upload)

        if df.empty:
            st.error("File is empty.")
        else:
            st.success(f"Loaded file ✅ Rows: {len(df)}")
            st.dataframe(df.head(20), use_container_width=True)

            cols = list(df.columns)

            def guess_col(keywords):
                for c in cols:
                    low = str(c).lower()
                    if any(k in low for k in keywords):
                        return c
                return None

            guess_name = guess_col(["category", "name"])
            guess_type = guess_col(["type"])
            guess_nature = guess_col(["nature", "dr", "cr"])
            guess_code = guess_col(["code"])

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                col_name = st.selectbox("Map: Category Name *", options=cols, index=cols.index(guess_name) if guess_name in cols else 0)
            with m2:
                col_type = st.selectbox("Map: Type", options=["(blank)"] + cols,
                                        index=(["(blank)"] + cols).index(guess_type) if guess_type in cols else 0)
            with m3:
                col_nature = st.selectbox("Map: Nature", options=["(blank)"] + cols,
                                          index=(["(blank)"] + cols).index(guess_nature) if guess_nature in cols else 0)
            with m4:
                col_code = st.selectbox("Map: Category Code", options=["(blank)"] + cols,
                                        index=(["(blank)"] + cols).index(guess_code) if guess_code in cols else 0)

            default_type = st.selectbox("Default Type (if blank)", options=["Expense", "Income", "Other"], index=0)
            default_nature = st.selectbox("Default Nature (if blank)", options=["Dr", "Cr", "Any"], index=0)

            prepared = []
            for _, r in df.iterrows():
                nm = str(r.get(col_name, "")).strip()
                tp = default_type if col_type == "(blank)" else str(r.get(col_type, "")).strip() or default_type
                nt = default_nature if col_nature == "(blank)" else str(r.get(col_nature, "")).strip() or default_nature
                cc = None if col_code == "(blank)" else str(r.get(col_code, "")).strip() or None
                prepared.append((nm, tp, nt, cc))

            preview_rows = pd.DataFrame(prepared, columns=["Category Name", "Type", "Nature", "Category Code"])
            st.markdown("**Import Preview (first 20 rows):**")
            st.dataframe(preview_rows.head(20), use_container_width=True, hide_index=True)

            if st.button("Import Categories Now"):
                result = bulk_add_categories(selected_client_id, prepared)
                clear_cache()
                st.success(f"Imported ✅ Inserted: {result['inserted']} | Skipped: {result['skipped']} (duplicates/blank)")
                st.rerun()

    except Exception as e:
        st.error(f"Failed to read file ❌\n\n{e}")

st.divider()
st.info("Next: Categorisation screen (upload statement → standardize → suggest → draft save).")
