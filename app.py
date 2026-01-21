import io
import streamlit as st
import pandas as pd

from src.db import ping_db
from src.schema import init_db
import src.crud as crud

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

# ------------------ Sidebar: Utilities ------------------
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
st.subheader("Intro (Client Profile & Masters)")

# ------------------ Clients ------------------
clients = cached_clients()
client_df = pd.DataFrame(clients) if clients else pd.DataFrame(columns=["id","name","industry","country","is_active","created_at"])
st.dataframe(client_df, use_container_width=True, hide_index=True)

client_options = {f"{r['id']} | {r['name']}": r["id"] for r in clients} if clients else {}
selected_label = st.selectbox("Select Client", options=["(Create new client first)"] + list(client_options.keys()))
selected_client_id = client_options.get(selected_label)

st.divider()

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
            crud.add_client(name, business_description, industry, country)
            clear_cache()
            st.success("Client created ✅")
            st.rerun()

if not selected_client_id:
    st.info("Select a client above to manage Banks and Categories.")
    st.stop()

st.divider()
st.markdown("### A2) Edit / Disable / Delete Client")

current_client = next((c for c in clients if c["id"] == selected_client_id), None)
if current_client:
    with st.form("edit_client_form"):
        e1, e2 = st.columns(2)
        with e1:
            e_name = st.text_input("Client Name", value=current_client.get("name",""))
            e_industry = st.text_input("Industry", value=current_client.get("industry","") or "")
        with e2:
            e_country = st.text_input("Country", value=current_client.get("country","") or "")
            e_active = st.checkbox("Client Active", value=bool(current_client.get("is_active", True)))
        e_bd = st.text_area("Business Description", value=current_client.get("business_description","") or "", height=80)

        if st.form_submit_button("Save Client Changes"):
            crud.update_client(selected_client_id, e_name, e_bd, e_industry, e_country)
            crud.set_client_active(selected_client_id, e_active)
            clear_cache()
            st.success("Client updated ✅")
            st.rerun()

    if st.button("Delete Client (only if unused)"):
        if not crud.can_delete_client(selected_client_id):
            st.error("Cannot delete: Client has banks/categories/transactions. Disable instead.")
        else:
            ok = crud.delete_client(selected_client_id)
            if ok:
                clear_cache()
                st.success("Client deleted ✅")
                st.rerun()

st.divider()

# ------------------ Banks ------------------
st.markdown("### B) Banks (Client-specific Master)")
banks = cached_banks(selected_client_id)
banks_df = pd.DataFrame(banks) if banks else pd.DataFrame(columns=[
    "id","bank_name","account_masked","account_type","currency","opening_balance","is_active","created_at"
])
st.dataframe(banks_df, use_container_width=True, hide_index=True)

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
            crud.add_bank(selected_client_id, bank_name, account_masked, account_type, currency, opening_balance)
            clear_cache()
            st.success("Bank added ✅")
            st.rerun()

st.markdown("#### Edit / Disable / Delete Bank")
bank_options = {f"{b['id']} | {b['bank_name']}": b["id"] for b in banks} if banks else {}
bank_label = st.selectbox("Select Bank", options=["(none)"] + list(bank_options.keys()))
sel_bank_id = bank_options.get(bank_label)

if sel_bank_id:
    bank_row = next((b for b in banks if b["id"] == sel_bank_id), None)
    if bank_row:
        with st.form("edit_bank_form"):
            x1, x2, x3 = st.columns(3)
            with x1:
                ebn = st.text_input("Bank Name", value=bank_row.get("bank_name",""))
                eat = st.text_input("Account Type", value=bank_row.get("account_type",""))
            with x2:
                eam = st.text_input("Masked Account", value=bank_row.get("account_masked","") or "")
                ecur = st.text_input("Currency", value=bank_row.get("currency","") or "")
            with x3:
                eob = st.number_input("Opening Balance", value=float(bank_row.get("opening_balance") or 0.0), step=1000.0)
                eact = st.checkbox("Bank Active", value=bool(bank_row.get("is_active", True)))

            if st.form_submit_button("Save Bank Changes"):
                crud.update_bank(sel_bank_id, ebn, eam, eat, ecur, eob)
                crud.set_bank_active(sel_bank_id, eact)
                clear_cache()
                st.success("Bank updated ✅")
                st.rerun()

        if st.button("Delete Bank (only if unused)"):
            if not crud.can_delete_bank(sel_bank_id):
                st.error("Cannot delete: Bank has transactions. Disable instead.")
            else:
                ok = crud.delete_bank(sel_bank_id)
                if ok:
                    clear_cache()
                    st.success("Bank deleted ✅")
                    st.rerun()

st.divider()

# ------------------ Categories ------------------
st.markdown("### C) Category Master (Client-specific)")
cats = cached_categories(selected_client_id)
cats_df = pd.DataFrame(cats) if cats else pd.DataFrame(columns=[
    "id","category_code","category_name","type","nature","is_active","created_at"
])
st.dataframe(cats_df, use_container_width=True, hide_index=True)

st.markdown("#### Download Category Template (CSV)")
tmpl = pd.DataFrame([
    {"category_name": "Meals & Entertainment", "type": "Expense", "nature": "Dr"},
    {"category_name": "Sales", "type": "Income", "nature": "Cr"},
    {"category_name": "Internal Transfer", "type": "Other", "nature": "Any"},
])
csv_buf = io.StringIO()
tmpl.to_csv(csv_buf, index=False)
st.download_button(
    label="Download CSV Template",
    data=csv_buf.getvalue().encode("utf-8"),
    file_name="category_template.csv",
    mime="text/csv",
)

st.divider()

st.markdown("#### Add Single Category")
with st.form("add_category_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        category_name = st.text_input("Category Name *")
    with c2:
        type_ = st.selectbox("Type *", options=["Income","Expense","Other"])
    with c3:
        nature = st.selectbox("Nature *", options=["Dr","Cr","Any"])

    if st.form_submit_button("Add Category (Single)"):
        if not category_name.strip():
            st.error("Category Name is required.")
        else:
            crud.add_category(selected_client_id, category_name, type_, nature)
            clear_cache()
            st.success("Category added ✅")
            st.rerun()

st.markdown("#### Edit / Disable / Delete Category")
cat_options = {f"{c['id']} | {c['category_name']}": c["id"] for c in cats} if cats else {}
cat_label = st.selectbox("Select Category", options=["(none)"] + list(cat_options.keys()))
sel_cat_id = cat_options.get(cat_label)

if sel_cat_id:
    cat_row = next((c for c in cats if c["id"] == sel_cat_id), None)
    if cat_row:
        with st.form("edit_cat_form"):
            y1, y2, y3 = st.columns(3)
            with y1:
                ecn = st.text_input("Category Name", value=cat_row.get("category_name",""))
            with y2:
                etp = st.selectbox("Type", options=["Income","Expense","Other"], index=["Income","Expense","Other"].index(cat_row.get("type","Expense")))
            with y3:
                ent = st.selectbox("Nature", options=["Dr","Cr","Any"], index=["Dr","Cr","Any"].index(cat_row.get("nature","Dr")))
                eact = st.checkbox("Category Active", value=bool(cat_row.get("is_active", True)))

            if st.form_submit_button("Save Category Changes"):
                crud.update_category(sel_cat_id, ecn, etp, ent)
                crud.set_category_active(sel_cat_id, eact)
                clear_cache()
                st.success("Category updated ✅")
                st.rerun()

        if st.button("Delete Category (only if unused)"):
            if not crud.can_delete_category(sel_cat_id):
                st.error("Cannot delete: Category is used in transactions. Disable instead.")
            else:
                ok = crud.delete_category(sel_cat_id)
                if ok:
                    clear_cache()
                    st.success("Category deleted ✅")
                    st.rerun()

st.divider()

st.markdown("#### Bulk Upload Categories (CSV/XLSX)")
upload = st.file_uploader("Upload Categories File", type=["csv","xlsx"])
if upload is not None:
    try:
        if upload.name.lower().endswith(".csv"):
            df = pd.read_csv(upload)
        else:
            df = pd.read_excel(upload)

        cols = list(df.columns)
        col_name = st.selectbox("Map: Category Name *", options=cols, index=0)
        default_type = st.selectbox("Default Type", options=["Expense","Income","Other"], index=0)
        default_nature = st.selectbox("Default Nature", options=["Dr","Cr","Any"], index=0)

        prepared = []
        for _, r in df.iterrows():
            prepared.append((str(r.get(col_name,"")).strip(), default_type, default_nature, None))

        if st.button("Import Categories Now"):
            result = crud.bulk_add_categories(selected_client_id, prepared)
            clear_cache()
            st.success(f"Imported ✅ Inserted: {result['inserted']} | Skipped: {result['skipped']}")
            st.rerun()

    except Exception as e:
        st.error(f"Import failed ❌\n\n{e}")

st.divider()
st.info("Next: Categorisation screen (upload statement → standardize → suggest → draft save).")
