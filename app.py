# app.py
import io
import datetime as dt
import pandas as pd
import streamlit as st

from src.schema import init_db
from src import crud

st.set_page_config(page_title="BankCat Demo", layout="wide")

st.title("BankCat Demo ✅")

# ---------------- Utilities Sidebar ----------------
with st.sidebar:
    st.markdown("### Utilities")
    if st.button("Test DB Connection"):
        try:
            _ = crud.list_clients(include_inactive=True)
            st.success("DB Connected ✅")
        except Exception as e:
            st.error(f"DB connection failed ❌\n\n{e}")

    if st.button("Initialize / Migrate DB"):
        try:
            init_db()
            st.success("DB schema initialized + migrated ✅")
            st.cache_data.clear()
            st.cache_resource.clear()
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{e}")

    if st.button("Refresh Lists"):
        st.cache_data.clear()
        st.success("Refreshed ✅")


# ---------------- Cached Masters ----------------
@st.cache_data(ttl=30)
def cached_clients():
    return crud.list_clients(include_inactive=True)

@st.cache_data(ttl=30)
def cached_banks(client_id: int):
    return crud.list_banks(client_id, include_inactive=True)

@st.cache_data(ttl=30)
def cached_categories(client_id: int):
    return crud.list_categories(client_id, include_inactive=True)


# ---------------- Section 1: Intro ----------------
st.header("1) Intro (Client Profile & Masters)")

clients = cached_clients()
dfc = pd.DataFrame(clients) if clients else pd.DataFrame()
st.dataframe(dfc, width="stretch", hide_index=True)

client_options = ["(none)"] + [f"{c['id']} | {c['name']}" for c in clients]
client_pick = st.selectbox("Select Client", options=client_options, index=1 if len(client_options) > 1 else 0)
client_id = int(client_pick.split("|")[0].strip()) if client_pick != "(none)" else None

st.subheader("Create New Client")
c1, c2 = st.columns(2)
with c1:
    new_name = st.text_input("Client/Company Name *", value="")
    new_industry = st.selectbox("Industry", ["Professional Services", "Retail", "Manufacturing", "NGO", "Other"])
with c2:
    new_country = st.text_input("Country (optional)", value="")
new_desc = st.text_area("Business Description (optional)", value="")
if st.button("Create Client"):
    if not new_name.strip():
        st.error("Client name required.")
    else:
        cid = crud.create_client(new_name, new_industry, new_country, new_desc)
        st.success(f"Created client id={cid}")
        st.cache_data.clear()

if client_id:
    # Banks
    st.subheader("Banks (Client-specific Master)")
    banks = cached_banks(client_id)
    st.dataframe(pd.DataFrame(banks), width="stretch", hide_index=True)

    b1, b2, b3 = st.columns(3)
    with b1:
        bank_name = st.text_input("Bank Name *", "")
        masked = st.text_input("Account Number / Masked ID (optional)", "")
    with b2:
        acct_type = st.selectbox("Account Type *", ["Current", "Savings", "Credit Card", "Wallet", "Investment"])
        currency = st.text_input("Currency (optional)", "")
    with b3:
        opening = st.number_input("Opening Balance (optional)", value=0.0, step=1.0)
    if st.button("Add Bank"):
        if not bank_name.strip():
            st.error("Bank name required.")
        else:
            crud.add_bank(client_id, bank_name, acct_type, currency, masked, opening)
            st.success("Bank added ✅")
            st.cache_data.clear()

    st.markdown("#### Edit / Disable Bank")
    bank_map = {f"{b['id']} | {b['bank_name']} ({b['account_type']})": b for b in banks}
    bank_edit_pick = st.selectbox("Select Bank to disable/enable", ["(none)"] + list(bank_map.keys()))
    if bank_edit_pick != "(none)":
        b = bank_map[bank_edit_pick]
        new_active = st.checkbox("Is Active", value=bool(b.get("is_active", True)))
        if st.button("Save Bank Active"):
            crud.set_bank_active(int(b["id"]), bool(new_active))
            st.success("Saved ✅")
            st.cache_data.clear()

    # Categories
    st.subheader("Categories (Client-specific Master)")
    cats = cached_categories(client_id)
    st.dataframe(pd.DataFrame(cats), width="stretch", hide_index=True)

    st.markdown("#### Download Category Template (CSV)")
    template = pd.DataFrame([{"category_name": "", "type": "Expense", "nature": "Any"}])
    buf = io.StringIO()
    template.to_csv(buf, index=False)
    st.download_button("Download Category CSV Template", data=buf.getvalue(), file_name="category_template.csv", mime="text/csv")

    st.markdown("#### Add Single Category")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        cat_name = st.text_input("Category Name", "")
    with cc2:
        cat_type = st.selectbox("Type", ["Income", "Expense", "Other"])
    with cc3:
        cat_nature = st.selectbox("Nature", ["Any", "Debit", "Credit"])
    if st.button("Add Category (Single)"):
        if not cat_name.strip():
            st.error("Category name required.")
        else:
            crud.add_category(client_id, cat_name, cat_type, cat_nature)
            st.success("Category added ✅")
            st.cache_data.clear()

    st.markdown("#### Bulk Upload Categories (CSV)")
    up = st.file_uploader("Upload Categories CSV", type=["csv"])
    if up is not None:
        try:
            dfu = pd.read_csv(up)
            st.dataframe(dfu.head(20), width="stretch", hide_index=True)
            rows = dfu.to_dict(orient="records")
            if st.button("Import Categories Now"):
                ok, bad = crud.bulk_add_categories(client_id, rows)
                st.success(f"Imported ✅ ok={ok}, skipped={bad}")
                st.cache_data.clear()
        except Exception as e:
            st.error(f"Category upload parse failed ❌\n\n{e}")

# ---------------- Section 2: Categorisation ----------------
st.divider()
st.header("2) Categorisation (Upload → Map → Standardize → Save Draft → Suggest → Review → Commit)")

if not client_id:
    st.info("Select a client first.")
    st.stop()

banks_active = crud.list_banks(client_id, include_inactive=False)
if not banks_active:
    st.info("Add at least 1 active bank first.")
    st.stop()

bank_pick = st.selectbox("Select Bank (for statement upload)", [f"{b['id']} | {b['bank_name']} ({b['account_type']})" for b in banks_active])
bank_id = int(bank_pick.split("|")[0].strip())
bank_obj = [b for b in banks_active if int(b["id"]) == bank_id][0]
bank_type = bank_obj.get("account_type", "Current")

# Period: Year + Month
mcol1, mcol2, mcol3 = st.columns(3)
with mcol1:
    year = st.selectbox("Year", list(range(2020, 2031)), index=list(range(2020, 2031)).index(2025))
with mcol2:
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    month = st.selectbox("Month", month_names, index=9)  # Oct default
with mcol3:
    period = f"{year}-{month_names.index(month)+1:02d}"
    st.text_input("Period (auto)", value=period, disabled=True)

st.caption("Period = statement month label. Even if date range overlaps months, keep period as statement month.")

# Date range (optional)
st.subheader("Statement Date Range (optional but recommended)")
dr = st.date_input("Select From-To", value=(dt.date(year, month_names.index(month)+1, 1), dt.date(year, month_names.index(month)+1, 28)))
date_from, date_to = dr if isinstance(dr, tuple) else (dr, dr)

# Existing drafts summary
st.subheader("Existing Drafts (this client + bank)")
summary = crud.drafts_summary(client_id, bank_id)
st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)

# Download statement template CSV
st.subheader("Upload Template (CSV)")
stmt_template = pd.DataFrame([{"Date": "2025-10-01", "Description": "POS Purchase Example Vendor", "Dr": 100.00, "Cr": 0.00, "Closing": ""}])
buf2 = io.StringIO()
stmt_template.to_csv(buf2, index=False)
st.download_button("Download Statement CSV Template", data=buf2.getvalue(), file_name="statement_template.csv", mime="text/csv")
st.caption("Minimum columns: Date + Description. Dr/Cr recommended. Closing optional (can be blank).")

# Upload CSV
st.subheader("Upload Statement (CSV) — Mode 1 (already converted)")
up_stmt = st.file_uploader("Upload CSV File", type=["csv"], key="stmt_csv")
df_raw = None
if up_stmt is not None:
    try:
        df_raw = pd.read_csv(up_stmt)
        st.success(f"Loaded ✅ Rows: {len(df_raw)}")
        st.dataframe(df_raw.head(20), width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Upload/Parse failed ❌\n\n{e}")

# Map columns
st.subheader("Map Columns → Standard Format")
if df_raw is not None and len(df_raw) > 0:
    cols = ["(blank)"] + list(df_raw.columns)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        map_date = st.selectbox("Date *", cols, index=cols.index("Date") if "Date" in cols else 0)
    with c2:
        map_desc = st.selectbox("Description *", cols, index=cols.index("Description") if "Description" in cols else 0)
    with c3:
        map_dr = st.selectbox("Debit (Dr)", cols, index=cols.index("Dr") if "Dr" in cols else 0)
    with c4:
        map_cr = st.selectbox("Credit (Cr)", cols, index=cols.index("Cr") if "Cr" in cols else 0)
    with c5:
        map_bal = st.selectbox("Closing Balance", cols, index=cols.index("Closing") if "Closing" in cols else 0)

    def _to_date(x):
        if pd.isna(x):
            return None
        try:
            return pd.to_datetime(x).date()
        except Exception:
            return None

    std_rows = []
    dropped = 0
    out_of_range = 0
    for _, r in df_raw.iterrows():
        d = _to_date(r[map_date]) if map_date != "(blank)" else None
        ds = str(r[map_desc]).strip() if map_desc != "(blank)" else ""
        if not d or not ds:
            dropped += 1
            continue

        # Date range FYI only (we don't drop)
        if d < date_from or d > date_to:
            out_of_range += 1

        drv = float(r[map_dr]) if map_dr != "(blank)" and pd.notna(r[map_dr]) else 0.0
        crv = float(r[map_cr]) if map_cr != "(blank)" and pd.notna(r[map_cr]) else 0.0
        bal = float(r[map_bal]) if map_bal != "(blank)" and pd.notna(r[map_bal]) and str(r[map_bal]).strip() != "" else None

        std_rows.append({
            "tx_date": d,
            "description": ds,
            "debit": round(drv, 2),
            "credit": round(crv, 2),
            "balance": bal
        })

    st.subheader("Standardize Preview")
    st.caption(f"Rows parsed: {len(std_rows)} | Dropped (missing date/desc): {dropped} | Out-of-range (FYI): {out_of_range}")
    st.dataframe(pd.DataFrame(std_rows[:50]), width="stretch", hide_index=True)

    st.subheader("Save Draft")
    replace = st.checkbox("Replace existing draft for this bank+period", value=True)
    if st.button("Save Draft Now"):
        if not std_rows:
            st.error("No valid rows to save.")
        else:
            n = crud.insert_draft_rows(client_id, bank_id, period, std_rows, replace=replace)
            st.success(f"Draft saved ✅ rows={n}")
            st.cache_data.clear()

# Step 6 Suggest
st.subheader("Step-6: Suggest Category + Vendor (Draft)")
if st.button("Process Suggestions for this bank+period"):
    n = crud.process_suggestions(client_id, bank_id, period, bank_account_type=bank_type)
    st.success(f"Suggestions done ✅ rows={n}")

# Review + Finalize
st.subheader("Review + Finalize (Draft)")
draft_rows = crud.load_draft(client_id, bank_id, period)
if draft_rows:
    df_d = pd.DataFrame(draft_rows)

    # show only key columns for editing
    cats_active = crud.list_categories(client_id, include_inactive=False)
    cat_list = [c["category_name"] for c in cats_active]

    # build editable frame
    view = df_d[["id","tx_date","description","debit","credit","balance","suggested_category","suggested_vendor","confidence","reason","final_category","final_vendor","status"]].copy()

    st.caption("Edit final_category/final_vendor. This saves INSIDE DRAFT (not committed yet).")
    edited = st.data_editor(view, width="stretch", hide_index=True, num_rows="fixed")

    if st.button("Save Review Changes"):
        recs = edited.to_dict(orient="records")
        # Basic guard: final_category if provided must be in active categories
        for rr in recs:
            fc = (rr.get("final_category") or "").strip()
            if fc and (fc not in cat_list):
                st.error(f"Final category '{fc}' is not in active Category Master. Add it first.")
                st.stop()
        crud.save_review_changes(recs)
        st.success("Saved review changes ✅")

else:
    st.info("No draft yet for this bank+period.")

# Step 7 Commit / Lock / Learn
st.subheader("Step-7: Commit / Lock / Learn (FINAL)")
committed_by = st.text_input("Committed by (optional)", value="")
lock_ok = st.checkbox("I confirm categories/vendors are final and should be locked for reporting (Commit).", value=False)

if st.button("Commit This Period (Lock & Learn)"):
    if not lock_ok:
        st.error("Please tick the confirmation checkbox first.")
    else:
        result = crud.commit_period(client_id, bank_id, period, committed_by=committed_by or None)
        if result.get("ok"):
            st.success(f"Committed ✅ commit_id={result['commit_id']} rows={result['rows']} accuracy={result['accuracy']}")
        else:
            st.error(result.get("msg", "Commit failed."))

st.subheader("Committed Sample (this bank + period)")
try:
    sample = crud.committed_sample(client_id, bank_id, period, limit=200)
    if sample:
        st.dataframe(pd.DataFrame(sample), width="stretch", hide_index=True)
    else:
        st.info("No committed rows yet for this period.")
except Exception as e:
    st.warning(f"Committed sample not available yet. ({e})")
