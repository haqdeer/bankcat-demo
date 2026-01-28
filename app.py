# app.py
import io
import sys
import calendar
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import init_db
from src import crud

st.set_page_config(page_title="BankCat Demo", layout="wide")

st.title("BankCat Demo ✅")


REQUIRED_CRUD_APIS = (
    "list_clients",
    "create_client",
    "update_client",
    "set_client_active",
    "list_banks",
    "add_bank",
    "update_bank",
    "bank_has_transactions",
    "set_bank_active",
    "list_categories",
    "add_category",
    "update_category",
    "set_category_active",
    "bulk_add_categories",
    "list_table_columns",
    "drafts_summary",
    "insert_draft_rows",
    "process_suggestions",
    "load_draft",
    "save_review_changes",
    "commit_period",
    "committed_sample",
    "list_committed_periods",
    "list_committed_transactions",
    "list_committed_pl_summary",
    "list_commit_metrics",
)


def _format_exc(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def _validate_crud() -> None:
    missing = [name for name in REQUIRED_CRUD_APIS if not hasattr(crud, name)]
    if missing:
        st.error(
            "The app could not load required database helpers. "
            f"Missing: {', '.join(missing)}. "
            "Please redeploy with the latest src/crud.py."
        )
        st.stop()


_validate_crud()


# ---------------- Cached Masters ----------------
@st.cache_data(ttl=30)
def cached_clients():
    try:
        return crud.list_clients(include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load clients. {_format_exc(e)}")
        return []


@st.cache_data(ttl=30)
def cached_banks(client_id: int):
    try:
        return crud.list_banks(client_id, include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load banks. {_format_exc(e)}")
        return []


@st.cache_data(ttl=30)
def cached_categories(client_id: int):
    try:
        return crud.list_categories(client_id, include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load categories. {_format_exc(e)}")
        return []


def _load_schema_truth(path: Path) -> dict[str, list[str]]:
    truth: dict[str, list[str]] = {}
    current_table: str | None = None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            current_table = line.replace("## ", "").strip()
            truth[current_table] = []
            continue
        if current_table and line.strip().startswith("- "):
            col = line.strip()[2:].strip()
            if col:
                truth[current_table].append(col)
    return truth


# ---------------- Sidebar Navigation ----------------
st.markdown(
    """
<style>
[data-testid="stSidebar"] {
    width: 220px;
    min-width: 220px;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
}
</style>
    """,
    unsafe_allow_html=True,
)

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Home"
if "companies_subpage" not in st.session_state:
    st.session_state.companies_subpage = "List"
if "setup_subpage" not in st.session_state:
    st.session_state.setup_subpage = "Banks"
if "active_client_id" not in st.session_state:
    st.session_state.active_client_id = None
if "active_client_name" not in st.session_state:
    st.session_state.active_client_name = None
if "bank_id" not in st.session_state:
    st.session_state.bank_id = None
if "period" not in st.session_state:
    st.session_state.period = None
if "date_from" not in st.session_state:
    st.session_state.date_from = None
if "date_to" not in st.session_state:
    st.session_state.date_to = None
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "year" not in st.session_state:
    st.session_state.year = 2025
if "month" not in st.session_state:
    st.session_state.month = "Oct"
if "setup_banks_mode" not in st.session_state:
    st.session_state.setup_banks_mode = "list"
if "setup_bank_edit_id" not in st.session_state:
    st.session_state.setup_bank_edit_id = None
if "setup_categories_mode" not in st.session_state:
    st.session_state.setup_categories_mode = "list"
if "setup_category_edit_id" not in st.session_state:
    st.session_state.setup_category_edit_id = None
if "companies_tab" not in st.session_state:
    st.session_state.companies_tab = "List"
if "setup_tab" not in st.session_state:
    st.session_state.setup_tab = "Banks"


with st.sidebar:
    st.markdown("### Navigation")
    for page in ["Home", "Reports", "Dashboard", "Companies", "Setup", "Categorisation", "Settings"]:
        if st.button(page, use_container_width=True, key=f"nav_{page}"):
            st.session_state.nav_page = page

    with st.expander("Companies", expanded=st.session_state.nav_page == "Companies"):
        for tab in ["List", "Change Company", "Add Company"]:
            if st.button(tab, use_container_width=True, key=f"companies_tab_{tab}"):
                st.session_state.nav_page = "Companies"
                st.session_state.companies_tab = tab

    with st.expander("Setup", expanded=st.session_state.nav_page == "Setup"):
        for tab in ["Banks", "Categories"]:
            if st.button(tab, use_container_width=True, key=f"setup_tab_{tab}"):
                st.session_state.nav_page = "Setup"
                st.session_state.setup_tab = tab


def _require_active_client() -> int | None:
    client_id = st.session_state.active_client_id
    if not client_id:
        st.warning("Select a company on Home first.")
        return None
    return client_id


def _select_active_client(clients: list[dict]) -> int | None:
    options = ["(none)"] + [f"{c['id']} | {c['name']}" for c in clients]
    selected_index = 0
    if st.session_state.active_client_id:
        for i, opt in enumerate(options):
            if opt.startswith(f"{st.session_state.active_client_id} |"):
                selected_index = i
                break
    client_pick = st.selectbox(
        "Select Client",
        options=options,
        index=selected_index,
        key="active_client_select",
    )
    if client_pick == "(none)":
        st.session_state.active_client_id = None
        st.session_state.active_client_name = None
        return None
    client_id = int(client_pick.split("|")[0].strip())
    st.session_state.active_client_id = client_id
    st.session_state.active_client_name = client_pick.split("|")[1].strip()
    return client_id


def _select_bank(banks_active: list[dict]) -> tuple[int, dict]:
    bank_options = [f"{b['id']} | {b['bank_name']} ({b['account_type']})" for b in banks_active]
    selected_index = 0
    if st.session_state.bank_id:
        for i, opt in enumerate(bank_options):
            if opt.startswith(f"{st.session_state.bank_id} |"):
                selected_index = i
                break
    bank_pick = st.selectbox(
        "Select Bank (for statement upload)",
        bank_options,
        index=selected_index,
        key="bank_select",
    )
    bank_id = int(bank_pick.split("|")[0].strip())
    st.session_state.bank_id = bank_id
    bank_obj = [b for b in banks_active if int(b["id"]) == bank_id][0]
    return bank_id, bank_obj


def render_home():
    st.header("Home")
    clients = cached_clients()
    _select_active_client(clients)
    st.markdown("**BankCat Demo**")
    st.write("Welcome to the BankCat demo workspace.")
    st.caption("Shortcuts and quick links will be added later.")


def render_dashboard():
    st.header("Dashboard")
    st.write("Dashboard coming soon.")


def render_reports():
    st.header("Reports")
    client_id = _require_active_client()
    if not client_id:
        return

    st.caption("Reports in this section only use committed (locked) transactions.")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        banks_for_filter = cached_banks(client_id)
        bank_options = ["(All Banks)"] + [
            f"{b['id']} | {b['bank_name']} ({b['account_type']})" for b in banks_for_filter
        ]
        bank_filter_pick = st.selectbox("Bank filter", bank_options, key="dash_bank_filter")
        bank_filter_id = (
            int(bank_filter_pick.split("|")[0].strip())
            if bank_filter_pick != "(All Banks)"
            else None
        )

    with filter_col2:
        default_from = dt.date.today() - dt.timedelta(days=30)
        date_filter_from = st.date_input("From Date", value=default_from, key="dash_from_date")

    with filter_col3:
        date_filter_to = st.date_input("To Date", value=dt.date.today(), key="dash_to_date")

    with filter_col4:
        try:
            periods = crud.list_committed_periods(client_id, bank_id=bank_filter_id)
        except Exception as e:
            st.error(f"Unable to load committed periods. {_format_exc(e)}")
            periods = []
        period_options = ["(All Periods)"] + periods
        period_pick = st.selectbox("Period (optional)", period_options, key="dash_period_filter")
        period_filter = None if period_pick == "(All Periods)" else period_pick

    if date_filter_from > date_filter_to:
        st.error("From Date must be before To Date.")
        date_filter_from, date_filter_to = date_filter_to, date_filter_from

    st.subheader("Committed Transactions")
    try:
        committed_rows = crud.list_committed_transactions(
            client_id,
            bank_id=bank_filter_id,
            date_from=date_filter_from,
            date_to=date_filter_to,
            period=period_filter,
        )
        if committed_rows:
            df_committed = pd.DataFrame(committed_rows)
            st.dataframe(
                df_committed[
                    [
                        "tx_date",
                        "description",
                        "debit",
                        "credit",
                        "balance",
                        "category",
                        "vendor",
                        "confidence",
                        "reason",
                        "bank_name",
                        "period",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No committed transactions match the filters.")
    except Exception as e:
        st.error(f"Unable to load committed transactions. {_format_exc(e)}")

    st.subheader("P&L Summary")
    try:
        pl_rows = crud.list_committed_pl_summary(
            client_id,
            bank_id=bank_filter_id,
            date_from=date_filter_from,
            date_to=date_filter_to,
            period=period_filter,
        )
        if pl_rows:
            df_pl = pd.DataFrame(pl_rows)
            df_pl["category_type"] = df_pl["category_type"].fillna("Unmapped")

            income_total = df_pl.loc[df_pl["category_type"] == "Income", "net_amount"].sum()
            expense_total_raw = df_pl.loc[df_pl["category_type"] == "Expense", "net_amount"].sum()
            expense_total = abs(expense_total_raw)
            net_total = income_total - expense_total

            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Total Income", f"{income_total:,.2f}")
            metric_col2.metric("Total Expense", f"{expense_total:,.2f}")
            metric_col3.metric("Net (Income – Expense)", f"{net_total:,.2f}")

            st.dataframe(
                df_pl[
                    [
                        "category",
                        "category_type",
                        "total_debit",
                        "total_credit",
                        "net_amount",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No committed data for P&L summary with current filters.")
    except Exception as e:
        st.error(f"Unable to load P&L summary. {_format_exc(e)}")

    st.subheader("Commit Metrics")
    try:
        commit_rows = crud.list_commit_metrics(
            client_id,
            bank_id=bank_filter_id,
            date_from=date_filter_from,
            date_to=date_filter_to,
            period=period_filter,
        )
        if commit_rows:
            df_commits = pd.DataFrame(commit_rows)
            st.dataframe(
                df_commits[
                    [
                        "commit_id",
                        "period",
                        "bank_name",
                        "rows_committed",
                        "accuracy",
                        "committed_at",
                        "committed_by",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No commit metrics for the selected filters.")
    except Exception as e:
        st.error(f"Unable to load commit metrics. {_format_exc(e)}")


def render_companies_list():
    st.subheader("Company List")
    clients = cached_clients()
    dfc = pd.DataFrame(clients) if clients else pd.DataFrame()
    st.dataframe(dfc, use_container_width=True, hide_index=True)


def render_companies_change():
    st.subheader("Change Company")
    clients = cached_clients()
    options = ["(none)"] + [f"{c['id']} | {c['name']}" for c in clients]
    client_pick = st.selectbox("Select Company", options, key="change_company_select")
    if client_pick == "(none)":
        st.info("Select a client to edit details.")
        return

    client_id = int(client_pick.split("|")[0].strip())
    current = next((c for c in clients if int(c["id"]) == client_id), None)
    if not current:
        st.info("Selected client not found.")
        return

    name = st.text_input("Client/Company Name *", value=current.get("name") or "")
    industry = st.selectbox(
        "Industry",
        ["Professional Services", "Retail", "Manufacturing", "NGO", "Other"],
        index=["Professional Services", "Retail", "Manufacturing", "NGO", "Other"].index(
            current.get("industry") or "Professional Services"
        ),
    )
    country = st.text_input("Country (optional)", value=current.get("country") or "")
    description = st.text_area(
        "Business Description (optional)", value=current.get("business_description") or ""
    )
    is_active = st.checkbox("Is Active", value=bool(current.get("is_active", True)))

    if st.button("Save Company Changes"):
        if not name.strip():
            st.error("Client name required.")
            return
        try:
            crud.update_client(client_id, name, industry, country, description)
            crud.set_client_active(client_id, is_active)
            st.success("Company updated ✅")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Update failed ❌\n\n{_format_exc(e)}")


def render_companies_add():
    st.subheader("Add Company")
    c1, c2 = st.columns(2)
    with c1:
        new_name = st.text_input("Client/Company Name *", value="")
        new_industry = st.selectbox(
            "Industry",
            ["Professional Services", "Retail", "Manufacturing", "NGO", "Other"],
        )
    with c2:
        new_country = st.text_input("Country (optional)", value="")
    new_desc = st.text_area("Business Description (optional)", value="")
    if st.button("Create Client"):
        if not new_name.strip():
            st.error("Client name required.")
        else:
            try:
                cid = crud.create_client(new_name, new_industry, new_country, new_desc)
                st.success(f"Created client id={cid}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Create client failed ❌\n\n{_format_exc(e)}")


def render_companies():
    st.header("Companies")
    if st.session_state.companies_tab == "List":
        render_companies_list()
    elif st.session_state.companies_tab == "Change Company":
        render_companies_change()
    else:
        render_companies_add()


def render_setup_banks():
    st.subheader("Banks")
    client_id = _require_active_client()
    if not client_id:
        return

    banks = cached_banks(client_id)

    if st.button("Add new bank"):
        st.session_state.setup_banks_mode = "add"
        st.session_state.setup_bank_edit_id = None
        st.rerun()

    if st.session_state.setup_banks_mode == "add":
        st.markdown("#### Add Bank")
        bank_name = st.text_input("Bank Name *", key="add_bank_name")
        masked = st.text_input("Account Number / Masked ID (optional)", key="add_bank_mask")
        acct_type = st.selectbox(
            "Account Type *",
            ["Current", "Savings", "Credit Card", "Wallet", "Investment"],
            key="add_bank_type",
        )
        currency = st.text_input("Currency (optional)", key="add_bank_currency")
        opening = st.number_input(
            "Opening Balance (optional)", value=0.0, step=1.0, key="add_bank_opening"
        )
        col1, col2 = st.columns(2)
        if col1.button("Save Bank", key="add_bank_save"):
            if not bank_name.strip():
                st.error("Bank name required.")
            else:
                try:
                    crud.add_bank(client_id, bank_name, acct_type, currency, masked, opening)
                    st.success("Bank added ✅")
                    st.cache_data.clear()
                    st.session_state.setup_banks_mode = "list"
                    st.rerun()
                except Exception as e:
                    st.error(f"Add bank failed ❌\n\n{_format_exc(e)}")
        if col2.button("Cancel", key="add_bank_cancel"):
            st.session_state.setup_banks_mode = "list"
            st.rerun()

    if st.session_state.setup_banks_mode == "edit":
        edit_bank = next(
            (b for b in banks if int(b["id"]) == st.session_state.setup_bank_edit_id),
            None,
        )
        if not edit_bank:
            st.info("Bank not found.")
            st.session_state.setup_banks_mode = "list"
            st.session_state.setup_bank_edit_id = None
            st.rerun()
        st.markdown("#### Edit Bank")
        bank_name = st.text_input(
            "Bank Name *", value=edit_bank.get("bank_name") or "", key="edit_bank_name"
        )
        masked = st.text_input(
            "Account Number / Masked ID (optional)",
            value=edit_bank.get("account_number_masked") or "",
            key="edit_bank_mask",
        )
        acct_type = st.selectbox(
            "Account Type *",
            ["Current", "Savings", "Credit Card", "Wallet", "Investment"],
            index=["Current", "Savings", "Credit Card", "Wallet", "Investment"].index(
                edit_bank.get("account_type") or "Current"
            ),
            key="edit_bank_type",
        )
        currency = st.text_input(
            "Currency (optional)", value=edit_bank.get("currency") or "", key="edit_bank_currency"
        )
        has_tx = crud.bank_has_transactions(edit_bank["id"])
        if has_tx:
            st.info("Opening balance locked after transactions exist.")
        opening = st.number_input(
            "Opening Balance (optional)",
            value=float(edit_bank.get("opening_balance") or 0.0),
            step=1.0,
            disabled=has_tx,
            key="edit_bank_opening",
        )
        is_active = st.checkbox(
            "Is Active", value=bool(edit_bank.get("is_active", True)), key="edit_bank_active"
        )
        col1, col2 = st.columns(2)
        if col1.button("Save Bank Changes", key="edit_bank_save"):
            if not bank_name.strip():
                st.error("Bank name required.")
            else:
                try:
                    crud.update_bank(
                        edit_bank["id"],
                        bank_name,
                        masked,
                        acct_type,
                        currency,
                        None if has_tx else opening,
                    )
                    crud.set_bank_active(edit_bank["id"], is_active)
                    st.success("Bank updated ✅")
                    st.cache_data.clear()
                    st.session_state.setup_banks_mode = "list"
                    st.session_state.setup_bank_edit_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Update bank failed ❌\n\n{_format_exc(e)}")
        if col2.button("Cancel", key="edit_bank_cancel"):
            st.session_state.setup_banks_mode = "list"
            st.session_state.setup_bank_edit_id = None
            st.rerun()

    if banks:
        st.markdown("#### Bank List")
        header = st.columns([3, 2, 2, 2, 1])
        header[0].markdown("**Bank**")
        header[1].markdown("**Account Type**")
        header[2].markdown("**Currency**")
        header[3].markdown("**Masked**")
        header[4].markdown("**Edit**")
        for bank in banks:
            row = st.columns([3, 2, 2, 2, 1])
            row[0].write(bank.get("bank_name"))
            row[1].write(bank.get("account_type"))
            row[2].write(bank.get("currency"))
            row[3].write(bank.get("account_number_masked") or "")
            if row[4].button("✏️", key=f"edit_bank_{bank['id']}"):
                st.session_state.setup_banks_mode = "edit"
                st.session_state.setup_bank_edit_id = bank["id"]
                st.rerun()


def render_setup_categories():
    st.subheader("Categories")
    client_id = _require_active_client()
    if not client_id:
        return

    cats = cached_categories(client_id)

    col1, col2 = st.columns(2)
    if col1.button("Add new category"):
        st.session_state.setup_categories_mode = "add"
        st.session_state.setup_category_edit_id = None
        st.rerun()
    if col2.button("Bulk upload categories (CSV)"):
        st.session_state.setup_categories_mode = "bulk_upload"
        st.session_state.setup_category_edit_id = None
        st.rerun()

    st.markdown("#### Download Category Template (CSV)")
    template = pd.DataFrame([
        {"category_name": "", "type": "Expense", "nature": "Any"}
    ])
    buf = io.StringIO()
    template.to_csv(buf, index=False)
    st.download_button(
        "Download Category CSV Template",
        data=buf.getvalue(),
        file_name="category_template.csv",
        mime="text/csv",
    )

    if st.session_state.setup_categories_mode == "add":
        st.markdown("#### Add Category")
        cat_name = st.text_input("Category Name *", key="add_cat_name")
        cat_type = st.selectbox("Type *", ["Expense", "Income", "Other"], key="add_cat_type")
        cat_nature = st.selectbox(
            "Nature (Debit/Credit/Any)",
            ["Any", "Debit", "Credit"],
            key="add_cat_nature",
        )
        col1, col2 = st.columns(2)
        if col1.button("Save Category", key="add_cat_save"):
            if not cat_name.strip():
                st.error("Category name required.")
            else:
                try:
                    crud.add_category(client_id, cat_name, cat_type, cat_nature)
                    st.success("Category added ✅")
                    st.cache_data.clear()
                    st.session_state.setup_categories_mode = "list"
                    st.rerun()
                except Exception as e:
                    st.error(f"Add category failed ❌\n\n{_format_exc(e)}")
        if col2.button("Cancel", key="add_cat_cancel"):
            st.session_state.setup_categories_mode = "list"
            st.rerun()

    if st.session_state.setup_categories_mode == "edit":
        edit_cat = next(
            (c for c in cats if int(c["id"]) == st.session_state.setup_category_edit_id),
            None,
        )
        if not edit_cat:
            st.info("Category not found.")
            st.session_state.setup_categories_mode = "list"
            st.session_state.setup_category_edit_id = None
            st.rerun()
        st.markdown("#### Edit Category")
        allowed_natures = ["Any", "Debit", "Credit"]
        raw_nature = (edit_cat.get("nature") or "Any").strip()
        if raw_nature.lower() in {"dr", "debit"}:
            current_nature = "Debit"
        elif raw_nature.lower() in {"cr", "credit"}:
            current_nature = "Credit"
        else:
            current_nature = "Any"
        if current_nature not in allowed_natures:
            current_nature = "Any"
        cat_name = st.text_input(
            "Category Name *",
            value=edit_cat.get("category_name") or "",
            key="edit_cat_name",
        )
        st.text_input(
            "Category Code",
            value=edit_cat.get("category_code") or "",
            disabled=True,
            key="edit_cat_code",
        )
        cat_type = st.selectbox(
            "Type *",
            ["Expense", "Income", "Other"],
            index=["Expense", "Income", "Other"].index(edit_cat.get("type") or "Expense"),
            key="edit_cat_type",
        )
        cat_nature = st.selectbox(
            "Nature (Debit/Credit/Any)",
            allowed_natures,
            index=allowed_natures.index(current_nature),
            key="edit_cat_nature",
        )
        is_active = st.checkbox(
            "Is Active", value=bool(edit_cat.get("is_active", True)), key="edit_cat_active"
        )
        col1, col2 = st.columns(2)
        if col1.button("Save Category Changes", key="edit_cat_save"):
            if not cat_name.strip():
                st.error("Category name required.")
            else:
                try:
                    crud.update_category(edit_cat["id"], cat_name, cat_type, cat_nature)
                    crud.set_category_active(edit_cat["id"], is_active)
                    st.success("Category updated ✅")
                    st.cache_data.clear()
                    st.session_state.setup_categories_mode = "list"
                    st.session_state.setup_category_edit_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Update category failed ❌\n\n{_format_exc(e)}")
        if col2.button("Cancel", key="edit_cat_cancel"):
            st.session_state.setup_categories_mode = "list"
            st.session_state.setup_category_edit_id = None
            st.rerun()

    if st.session_state.setup_categories_mode == "bulk_upload":
        st.markdown("#### Bulk Upload Categories (CSV)")
        cat_file = st.file_uploader("Upload CSV", type=["csv"], key="cat_csv")
        if cat_file:
            try:
                dfu = pd.read_csv(cat_file)
                st.dataframe(dfu.head(20), use_container_width=True, hide_index=True)
                rows = dfu.to_dict(orient="records")
                if st.button("Import Categories Now"):
                    ok, bad = crud.bulk_add_categories(client_id, rows)
                    st.success(f"Imported ✅ ok={ok}, skipped={bad}")
                    st.cache_data.clear()
                    st.session_state.setup_categories_mode = "list"
                    st.rerun()
            except Exception as e:
                st.error(f"Category upload parse failed ❌\n\n{_format_exc(e)}")
        if st.button("Cancel Bulk Upload"):
            st.session_state.setup_categories_mode = "list"
            st.rerun()

    if cats:
        st.markdown("#### Category List")
        header = st.columns([3, 2, 2, 2, 1])
        header[0].markdown("**Category**")
        header[1].markdown("**Type**")
        header[2].markdown("**Nature**")
        header[3].markdown("**Active**")
        header[4].markdown("**Edit**")
        for cat in cats:
            row = st.columns([3, 2, 2, 2, 1])
            row[0].write(cat.get("category_name"))
            row[1].write(cat.get("type"))
            row[2].write(cat.get("nature"))
            row[3].write("Yes" if cat.get("is_active", True) else "No")
            if row[4].button("✏️", key=f"edit_cat_{cat['id']}"):
                st.session_state.setup_categories_mode = "edit"
                st.session_state.setup_category_edit_id = cat["id"]
                st.rerun()


def render_categorisation():
    st.header(
        "Categorisation (Upload → Map → Standardize → Save Draft → Suggest → Review → Commit)"
    )
    client_id = _require_active_client()
    if not client_id:
        return

    try:
        banks_active = crud.list_banks(client_id, include_inactive=False)
    except Exception as e:
        st.error(f"Unable to load active banks. {_format_exc(e)}")
        return

    if not banks_active:
        st.info("Add at least 1 active bank first.")
        return

    bank_id, bank_obj = _select_bank(banks_active)
    bank_type = bank_obj.get("account_type", "Current")

    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        year_range = list(range(2020, 2031))
        year = st.selectbox("Year", year_range, index=year_range.index(st.session_state.year))
        st.session_state.year = year
    with mcol2:
        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        month = st.selectbox("Month", month_names, index=month_names.index(st.session_state.month))
        st.session_state.month = month
    with mcol3:
        period = f"{year}-{month_names.index(month)+1:02d}"
        st.text_input("Period (auto)", value=period, disabled=True)
    st.session_state.period = period

    st.caption(
        "Period = statement month label. Even if date range overlaps months, keep period as statement month."
    )

    st.subheader("Statement Date Range (optional but recommended)")
    month_idx = month_names.index(month) + 1
    last_day = calendar.monthrange(year, month_idx)[1]
    default_range = (
        st.session_state.date_from or dt.date(year, month_idx, 1),
        st.session_state.date_to or dt.date(year, month_idx, last_day),
    )
    dr = st.date_input("Select From-To", value=default_range)
    date_from, date_to = dr if isinstance(dr, tuple) else (dr, dr)
    st.session_state.date_from = date_from
    st.session_state.date_to = date_to

    st.subheader("Existing Drafts (this client + bank)")
    try:
        summary = crud.drafts_summary(client_id, bank_id)
        st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Draft summary unavailable. ({_format_exc(e)})")

    st.subheader("Upload Template (CSV)")
    stmt_template = pd.DataFrame([
        {
            "Date": "2025-10-01",
            "Description": "POS Purchase Example Vendor",
            "Dr": 100.00,
            "Cr": 0.00,
            "Closing": "",
        }
    ])
    buf2 = io.StringIO()
    stmt_template.to_csv(buf2, index=False)
    st.download_button(
        "Download Statement CSV Template",
        data=buf2.getvalue(),
        file_name="statement_template.csv",
        mime="text/csv",
    )
    st.caption("Minimum columns: Date + Description. Dr/Cr recommended. Closing optional (can be blank).")

    st.subheader("Upload Statement (CSV) — Mode 1 (already converted)")
    up_stmt = st.file_uploader("Upload CSV File", type=["csv"], key="stmt_csv")
    df_raw = None
    if up_stmt is not None:
        try:
            df_raw = pd.read_csv(up_stmt)
            st.session_state.df_raw = df_raw
            st.success(f"Loaded ✅ Rows: {len(df_raw)}")
            st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Upload/Parse failed ❌\n\n{_format_exc(e)}")
    else:
        df_raw = st.session_state.df_raw

    render_mapping_section(client_id, bank_id, period, date_from, date_to, df_raw)

    st.subheader("Step-6: Suggest Category + Vendor (Draft)")
    if st.button("Process Suggestions for this bank+period"):
        try:
            n = crud.process_suggestions(client_id, bank_id, period, bank_account_type=bank_type)
            st.success(f"Suggestions done ✅ rows={n}")
        except Exception as e:
            st.error(f"Suggestion processing failed ❌\n\n{_format_exc(e)}")

    st.subheader("Review + Finalize (Draft)")
    try:
        draft_rows = crud.load_draft(client_id, bank_id, period)
    except Exception as e:
        st.error(f"Unable to load draft rows. {_format_exc(e)}")
        draft_rows = []

    if draft_rows:
        df_d = pd.DataFrame(draft_rows)

        try:
            cats_active = crud.list_categories(client_id, include_inactive=False)
        except Exception as e:
            st.error(f"Unable to load categories. {_format_exc(e)}")
            cats_active = []
        cat_list = [c["category_name"] for c in cats_active]

        view = df_d[
            [
                "id",
                "tx_date",
                "description",
                "debit",
                "credit",
                "balance",
                "suggested_category",
                "suggested_vendor",
                "confidence",
                "reason",
                "final_category",
                "final_vendor",
                "status",
            ]
        ].copy()

        st.caption("Edit final_category/final_vendor. This saves INSIDE DRAFT (not committed yet).")
        edited = st.data_editor(view, use_container_width=True, hide_index=True, num_rows="fixed")

        if st.button("Save Review Changes"):
            recs = edited.to_dict(orient="records")
            for rr in recs:
                fc = (rr.get("final_category") or "").strip()
                if fc and (fc not in cat_list):
                    st.error(
                        f"Final category '{fc}' is not in active Category Master. Add it first."
                    )
                    st.stop()
            try:
                crud.save_review_changes(recs)
                st.success("Saved review changes ✅")
            except Exception as e:
                st.error(f"Save review changes failed ❌\n\n{_format_exc(e)}")

    else:
        st.info("No draft yet for this bank+period.")

    st.subheader("Step-7: Commit / Lock / Learn (FINAL)")
    committed_by = st.text_input("Committed by (optional)", value="")
    lock_ok = st.checkbox(
        "I confirm categories/vendors are final and should be locked for reporting (Commit).",
        value=False,
    )

    if st.button("Commit This Period (Lock & Learn)"):
        if not lock_ok:
            st.error("Please tick the confirmation checkbox first.")
        else:
            try:
                result = crud.commit_period(
                    client_id, bank_id, period, committed_by=committed_by or None
                )
                if result.get("ok"):
                    st.success(
                        f"Committed ✅ commit_id={result['commit_id']} rows={result['rows']} accuracy={result['accuracy']}"
                    )
                else:
                    st.error(result.get("msg", "Commit failed."))
            except Exception as e:
                st.error(f"Commit failed ❌\n\n{_format_exc(e)}")

    st.subheader("Committed Sample (this bank + period)")
    try:
        sample = crud.committed_sample(client_id, bank_id, period, limit=200)
        if sample:
            st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)
        else:
            st.info("No committed rows yet for this period.")
    except Exception as e:
        st.warning(f"Committed sample not available yet. ({_format_exc(e)})")


def render_mapping_section(
    client_id: int,
    bank_id: int,
    period: str,
    date_from: dt.date,
    date_to: dt.date,
    df_raw: pd.DataFrame | None,
):
    st.subheader("Map Columns → Standard Format")
    if df_raw is None or len(df_raw) == 0:
        st.info("Upload a statement first to map columns.")
        return

    cols = ["(blank)"] + list(df_raw.columns)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        map_date = st.selectbox("Date *", cols, index=cols.index("Date") if "Date" in cols else 0)
    with c2:
        map_desc = st.selectbox(
            "Description *", cols, index=cols.index("Description") if "Description" in cols else 0
        )
    with c3:
        map_dr = st.selectbox("Debit (Dr)", cols, index=cols.index("Dr") if "Dr" in cols else 0)
    with c4:
        map_cr = st.selectbox("Credit (Cr)", cols, index=cols.index("Cr") if "Cr" in cols else 0)
    with c5:
        map_bal = st.selectbox(
            "Closing Balance", cols, index=cols.index("Closing") if "Closing" in cols else 0
        )

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

        if d < date_from or d > date_to:
            out_of_range += 1

        drv = (
            pd.to_numeric(r[map_dr], errors="coerce")
            if map_dr != "(blank)"
            else None
        )
        crv = (
            pd.to_numeric(r[map_cr], errors="coerce")
            if map_cr != "(blank)"
            else None
        )
        bal = (
            pd.to_numeric(r[map_bal], errors="coerce")
            if map_bal != "(blank)"
            else None
        )

        std_rows.append(
            {
                "tx_date": d,
                "description": ds,
                "debit": round(float(drv or 0.0), 2),
                "credit": round(float(crv or 0.0), 2),
                "balance": None if pd.isna(bal) else float(bal),
            }
        )

    st.subheader("Standardize Preview")
    st.caption(
        f"Rows parsed: {len(std_rows)} | Dropped (missing date/desc): {dropped} | Out-of-range (FYI): {out_of_range}"
    )
    st.dataframe(pd.DataFrame(std_rows[:50]), use_container_width=True, hide_index=True)

    st.subheader("Save Draft")
    replace = st.checkbox("Replace existing draft for this bank+period", value=True)
    if st.button("Save Draft Now"):
        if not std_rows:
            st.error("No valid rows to save.")
        else:
            try:
                n = crud.insert_draft_rows(client_id, bank_id, period, std_rows, replace=replace)
                st.success(f"Draft saved ✅ rows={n}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Save draft failed ❌\n\n{_format_exc(e)}")


def render_settings():
    st.header("Settings")
    st.markdown("### Utilities")
    if st.button("Test DB Connection"):
        try:
            _ = crud.list_clients(include_inactive=True)
            st.success("DB Connected ✅")
        except Exception as e:
            st.error(f"DB connection failed ❌\n\n{_format_exc(e)}")

    if st.button("Initialize / Migrate DB"):
        try:
            init_db()
            st.success("DB schema initialized + migrated ✅")
            st.cache_data.clear()
            st.cache_resource.clear()
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{_format_exc(e)}")

    if st.button("Refresh Lists"):
        st.cache_data.clear()
        st.success("Refreshed ✅")

    st.markdown("### Verify DB Schema")
    if st.button("Verify DB Schema"):
        truth_path = Path("docs/DB_SCHEMA_TRUTH.md")
        if not truth_path.exists():
            st.error("docs/DB_SCHEMA_TRUTH.md not found. Please add schema truth file.")
            return
        truth = _load_schema_truth(truth_path)
        tables = [
            "banks",
            "categories",
            "clients",
            "commits",
            "draft_batches",
            "keyword_model",
            "transactions_committed",
            "transactions_draft",
            "vendor_memory",
        ]
        results = []
        for table in tables:
            cols = crud.list_table_columns(table)
            expected = truth.get(table, [])
            missing = [c for c in expected if c not in cols]
            results.append(
                {
                    "table": table,
                    "missing": ", ".join(missing) or "—",
                }
            )
        issues = [r for r in results if r["missing"] != "—"]
        if not issues:
            st.success("✅ DB schema matches docs/DB_SCHEMA_TRUTH.md")
        else:
            st.warning("⚠️ Schema mismatch detected")
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)


def render_setup():
    st.header("Setup")
    if st.session_state.setup_tab == "Banks":
        render_setup_banks()
    else:
        render_setup_categories()


# ---------------- Page Rendering ----------------
page = st.session_state.nav_page
if page == "Home":
    render_home()
elif page == "Dashboard":
    render_dashboard()
elif page == "Reports":
    render_reports()
elif page == "Companies":
    render_companies()
elif page == "Setup":
    render_setup()
elif page == "Categorisation":
    render_categorisation()
elif page == "Settings":
    render_settings()
