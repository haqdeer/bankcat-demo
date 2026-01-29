# app.py - COMPLETE UPDATED FILE
import io
import sys
import calendar
import datetime as dt
import urllib.parse
import base64
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit import cache_data

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import init_db
from src import crud


def _logo_data_uri(path: Path) -> str:
    """Convert image to data URI - FIXED DUPLICATE"""
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".")
    
    if suffix in {"svg"}:
        svg_text = path.read_text(encoding="utf-8")
        encoded = urllib.parse.quote(svg_text)
        return f"data:image/svg+xml;utf8,{encoded}"
    
    # For JPEG, PNG, etc.
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    
    # Determine MIME type
    if suffix in {"jpg", "jpeg"}:
        mime = "image/jpeg"
    elif suffix == "png":
        mime = "image/png"
    elif suffix == "gif":
        mime = "image/gif"
    else:
        mime = f"image/{suffix}"
    
    return f"data:{mime};base64,{encoded}"


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
    "list_tables",
    "drafts_summary",
    "get_draft_summary",
    "get_commit_summary",
    "insert_draft_rows",
    "process_suggestions",
    "load_draft",
    "load_draft_rows",
    "load_committed_rows",
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


def _run_schema_check() -> dict[str, object]:
    truth_path = Path("docs/DB_SCHEMA_TRUTH.md")
    if not truth_path.exists():
        return {"error": "docs/DB_SCHEMA_TRUTH.md not found. Please add schema truth file."}
    truth = _load_schema_truth(truth_path)
    expected_tables = set(truth.keys())
    actual_tables = set(crud.list_tables())
    tables = sorted(expected_tables | actual_tables)
    allowed_extra = {"updated_at"}
    results = []
    for table in tables:
        expected = truth.get(table, [])
        actual = crud.list_table_columns(table) if table in actual_tables else []
        missing = [c for c in expected if c not in actual]
        extra = [c for c in actual if c not in expected and c not in allowed_extra]
        results.append(
            {
                "table": table,
                "table_present": "Yes" if table in actual_tables else "No",
                "missing_columns": ", ".join(missing) or "—",
                "extra_columns": ", ".join(extra) or "—",
            }
        )
    issues = [
        r
        for r in results
        if r["missing_columns"] != "—"
        or r["extra_columns"] != "—"
        or r["table_present"] == "No"
    ]
    return {"issues": issues}


# ---------------- Session State Initialization ----------------
def init_session_state():
    """Initialize all session state variables - FIXED MISSING VALUES"""
    defaults = {
        "active_page": st.session_state.get("nav_page", "Home"),
        "active_subpage": None,
        "active_client_id": None,
        "active_client_name": None,
        "bank_id": None,
        "period": None,
        "date_from": None,
        "date_to": None,
        "df_raw": None,
        "year": 2025,
        "month": "Oct",
        "setup_banks_mode": "list",
        "setup_bank_edit_id": None,
        "setup_categories_mode": "list",
        "setup_category_edit_id": None,
        "sidebar_companies_open": False,
        "sidebar_setup_open": False,
        "edit_client_id": None,
        "edit_client_mode": False,
        "standardized_rows": [],
        "categorisation_selected_item": None,
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    # Set subpage defaults based on page
    if st.session_state.active_page == "Companies" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "List"
    if st.session_state.active_page == "Setup" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "Banks"
    
    # Set sidebar open states
    if st.session_state.active_page == "Companies":
        st.session_state.sidebar_companies_open = True
    if st.session_state.active_page == "Setup":
        st.session_state.sidebar_setup_open = True


init_session_state()

# ---------------- Header & Sidebar ----------------
active_page = st.session_state.active_page
active_subpage = st.session_state.active_subpage
page_title = active_page
if active_page == "Companies" and active_subpage:
    page_title = f"Companies > {active_subpage}"
elif active_page == "Setup" and active_subpage:
    page_title = f"Setup > {active_subpage}"

logo_path = ROOT / "assets" / "bankcat-logo.jpeg"
logo_uri = _logo_data_uri(logo_path)

st.markdown(
    f"""
<style>
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,
footer {{
    display: none;
}}
[data-testid="stSidebarCollapseButton"] {{
    display: none;
}}
body.bankcat-sidebar-collapsed [data-testid="stSidebar"] {{
    margin-left: -260px;
    width: 0;
    min-width: 0;
}}
[data-testid="stSidebar"] {{
    width: 240px;
    min-width: 240px;
    top: 64px;
    height: calc(100vh - 64px);
    background: #ffffff;
    z-index: 900;
    transition: margin-left 0.2s ease, width 0.2s ease;
}}
[data-testid="stSidebar"] .block-container {{
    padding-top: 1rem;
    padding-bottom: 0.75rem;
}}
[data-testid="stAppViewContainer"] > .main {{
    padding-top: 5rem;
}}
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {{
    background: #0f9d58;
    color: #ffffff;
    border-radius: 10px;
    border: 1px solid #0f9d58;
    font-weight: 600;
}}
[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {{
    background: #0c8048;
    border-color: #0c8048;
    color: #ffffff;
}}
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {{
    background: #ffffff;
    color: #0f9d58;
    border: 1px solid #0f9d58;
    border-radius: 10px;
    font-weight: 600;
}}
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover {{
    background: #f3f4f6;
    color: #0f9d58;
    border: 1px solid #0f9d58;
}}
.bankcat-header {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 64px;
    display: flex;
    align-items: center;
    z-index: 1000;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}}
.bankcat-header__section {{
    height: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 18px;
}}
.bankcat-header__left {{
    background: #ffffff;
    flex: 0 0 34%;
}}
.bankcat-header__middle {{
    background: #0f9d58;
    flex: 1;
    justify-content: center;
    color: #ffffff;
}}
.bankcat-header__right {{
    background: #ffffff;
    flex: 0 0 28%;
    justify-content: flex-end;
}}
.bankcat-header__logo {{
    height: 38px;
}}
.bankcat-header__btn {{
    background: transparent;
    border: none;
    color: inherit;
    font-size: 18px;
    cursor: pointer;
}}
.bankcat-header__title {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
.bankcat-header__right select {{
    border-radius: 16px;
    padding: 6px 10px;
    border: 1px solid #e5e7eb;
}}
</style>
<div class="bankcat-header">
  <div class="bankcat-header__section bankcat-header__left">
    <button class="bankcat-header__btn" id="sidebar-toggle" aria-label="Toggle sidebar">☰</button>
    <img class="bankcat-header__logo" src="{logo_uri}" alt="BankCat logo" />
  </div>
  <div class="bankcat-header__section bankcat-header__middle">
    <span class="bankcat-header__title">{page_title}</span>
  </div>
  <div class="bankcat-header__section bankcat-header__right">
    <button class="bankcat-header__btn" aria-label="Theme">🌓</button>
    <button class="bankcat-header__btn" id="fullscreen-toggle" aria-label="Fullscreen">⛶</button>
    <button class="bankcat-header__btn" aria-label="Notifications">🔔</button>
    <select aria-label="User menu">
      <option>Admin</option>
      <option>Profile</option>
      <option>Sign out</option>
    </select>
  </div>
</div>
<script>
const toggleSidebar = () => {{
  document.body.classList.toggle('bankcat-sidebar-collapsed');
}};
const toggleFullscreen = () => {{
  if (!document.fullscreenElement) {{
    document.documentElement.requestFullscreen();
  }} else {{
    document.exitFullscreen();
  }}
}};
document.getElementById('sidebar-toggle')?.addEventListener('click', toggleSidebar);
document.getElementById('fullscreen-toggle')?.addEventListener('click', toggleFullscreen);
</script>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Navigation")
    
    def _set_active_page(page: str, subpage: str | None = None) -> None:
        st.session_state.active_page = page
        st.session_state.active_subpage = subpage
        st.rerun()

    def _button_type(is_active: bool) -> str:
        return "secondary" if is_active else "primary"

    page_labels = {
        "Home": "🏠 Home",
        "Reports": "📊 Reports",
        "Dashboard": "📈 Dashboard",
        "Categorisation": "🧠 Categorisation",
        "Settings": "⚙️ Settings",
    }
    
    for page in ["Home", "Reports", "Dashboard", "Categorisation", "Settings"]:
        is_active = st.session_state.active_page == page
        if st.button(
            page_labels[page],
            use_container_width=True,
            key=f"nav_{page}",
            type=_button_type(is_active),
        ):
            st.session_state.sidebar_companies_open = False
            st.session_state.sidebar_setup_open = False
            _set_active_page(page, None)

    companies_chevron = "▾" if st.session_state.sidebar_companies_open else "▸"
    companies_active = st.session_state.active_page == "Companies"
    if st.button(
        f"{companies_chevron} 🏢 Companies",
        use_container_width=True,
        key="toggle_companies",
        type=_button_type(companies_active),
    ):
        if companies_active:
            st.session_state.sidebar_companies_open = not st.session_state.sidebar_companies_open
            st.rerun()
        else:
            st.session_state.sidebar_companies_open = True
            st.session_state.sidebar_setup_open = False
            _set_active_page("Companies", "List")
    
    if st.session_state.sidebar_companies_open:
        for tab in ["List", "Change Company", "Add Company"]:
            tab_active = (
                st.session_state.active_page == "Companies"
                and st.session_state.active_subpage == tab
            )
            if st.button(
                tab,
                use_container_width=True,
                key=f"companies_tab_{tab}",
                type=_button_type(tab_active),
            ):
                st.session_state.sidebar_companies_open = True
                st.session_state.sidebar_setup_open = False
                _set_active_page("Companies", tab)

    setup_chevron = "▾" if st.session_state.sidebar_setup_open else "▸"
    setup_active = st.session_state.active_page == "Setup"
    if st.button(
        f"{setup_chevron} 🛠️ Setup",
        use_container_width=True,
        key="toggle_setup",
        type=_button_type(setup_active),
    ):
        if setup_active:
            st.session_state.sidebar_setup_open = not st.session_state.sidebar_setup_open
            st.rerun()
        else:
            st.session_state.sidebar_setup_open = True
            st.session_state.sidebar_companies_open = False
            _set_active_page("Setup", "Banks")
    
    if st.session_state.sidebar_setup_open:
        for tab in ["Banks", "Categories"]:
            tab_active = (
                st.session_state.active_page == "Setup"
                and st.session_state.active_subpage == tab
            )
            if st.button(
                tab,
                use_container_width=True,
                key=f"setup_tab_{tab}",
                type=_button_type(tab_active),
            ):
                st.session_state.sidebar_setup_open = True
                st.session_state.sidebar_companies_open = False
                _set_active_page("Setup", tab)

    # Export section added
    st.markdown("---")
    st.markdown("### 📤 Export")
    if st.button("Export Transactions", use_container_width=True):
        if st.session_state.active_client_id:
            st.info("Export feature will be implemented here")
        else:
            st.warning("Select a company first")


# ---------------- Helper Functions ----------------
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


# ---------------- Page Render Functions ----------------
def render_home():
    if logo_path.exists():
        col_left, col_center, col_right = st.columns([1, 4, 1])
        with col_center:
            st.image(str(logo_path), width=520)
    clients = cached_clients()
    _select_active_client(clients)
    st.markdown("**BankCat Demo**")
    st.write("Welcome to the BankCat demo workspace.")
    st.caption("Shortcuts and quick links will be added later.")


def render_dashboard():
    st.title("📊 Financial Dashboard")
    
    client_id = _require_active_client()
    if not client_id:
        return
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", dt.date.today() - dt.timedelta(days=90))
    with col2:
        end_date = st.date_input("End Date", dt.date.today())
    
    # Get transaction data
    try:
        transactions = crud.list_committed_transactions(
            client_id, 
            date_from=start_date, 
            date_to=end_date
        )
        
        if transactions:
            df = pd.DataFrame(transactions)
            
            # 1. Income vs Expense summary
            st.subheader("💰 Income vs Expense")
            total_income = df['credit'].sum()
            total_expense = df['debit'].sum()
            net = total_income - total_expense
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Income", f"${total_income:,.2f}")
            col2.metric("Total Expense", f"${total_expense:,.2f}")
            col3.metric("Net", f"${net:,.2f}", 
                       delta_color="normal" if net >= 0 else "inverse")
            
            # 2. Monthly trend
            st.subheader("📈 Monthly Trend")
            df['month'] = pd.to_datetime(df['tx_date']).dt.strftime('%Y-%m')
            monthly = df.groupby('month').agg({
                'debit': 'sum',
                'credit': 'sum'
            }).reset_index()
            
            if not monthly.empty:
                st.line_chart(monthly.set_index('month'))
            else:
                st.info("No monthly data available")
                
            # 3. Top categories
            st.subheader("🏷️ Top Expense Categories")
            expenses = df[df['debit'] > 0]
            if not expenses.empty:
                top_categories = expenses.groupby('category')['debit'].sum().nlargest(10)
                st.bar_chart(top_categories)
            else:
                st.info("No expense data available")
                
        else:
            st.info("No committed transactions found for the selected period.")
            
    except Exception as e:
        st.error(f"Unable to load dashboard data: {_format_exc(e)}")


def render_reports():
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
            st.info("No committed transactions found for the selected filters.")
    except Exception as e:
        st.error(f"Unable to load committed transactions. {_format_exc(e)}")

    st.subheader("P&L Summary")
    try:
        pl_summary = crud.list_committed_pl_summary(
            client_id,
            bank_id=bank_filter_id,
            date_from=date_filter_from,
            date_to=date_filter_to,
            period=period_filter,
        )
        if pl_summary:
            df_pl = pd.DataFrame(pl_summary)
            st.dataframe(
                df_pl[["category", "category_type", "total_debit", "total_credit", "net_amount"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No P&L summary available for the selected filters.")
    except Exception as e:
        st.error(f"Unable to load P&L summary. {_format_exc(e)}")

    st.subheader("Commit Metrics")
    try:
        commit_metrics = crud.list_commit_metrics(
            client_id,
            bank_id=bank_filter_id,
            date_from=date_filter_from,
            date_to=date_filter_to,
            period=period_filter,
        )
        if commit_metrics:
            df_metrics = pd.DataFrame(commit_metrics)
            st.dataframe(
                df_metrics[
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
            st.info("No commit metrics found for the selected filters.")
    except Exception as e:
        st.error(f"Unable to load commit metrics. {_format_exc(e)}")


def render_companies_list():
    client_id = st.session_state.active_client_id
    clients = cached_clients()
    if not clients:
        st.info("No companies yet. Add one below.")
        return

    st.subheader("Company List")
    header = st.columns([2, 2, 1, 1, 1])
    header[0].markdown("**Name**")
    header[1].markdown("**Industry**")
    header[2].markdown("**Active**")
    header[3].markdown("**Select**")
    header[4].markdown("**Edit**")

    for c in clients:
        row = st.columns([2, 2, 1, 1, 1])
        row[0].write(c["name"])
        row[1].write(c["industry"])
        row[2].write("Yes" if c["is_active"] else "No")
        if row[3].button("✔", key=f"sel_client_{c['id']}"):
            st.session_state.active_client_id = c["id"]
            st.session_state.active_client_name = c["name"]
            st.success(f"Selected client: {c['name']}")
        if row[4].button("✎", key=f"edit_client_{c['id']}"):
            st.session_state.edit_client_id = c["id"]
            st.session_state.edit_client_mode = True

    if "edit_client_mode" in st.session_state and st.session_state.edit_client_mode:
        edit = [c for c in clients if c["id"] == st.session_state.edit_client_id][0]
        st.subheader("Edit Company")
        name = st.text_input("Company Name *", value=edit["name"], key="edit_client_name")
        industry = st.text_input("Industry", value=edit.get("industry") or "", key="edit_client_industry")
        country = st.text_input("Country", value=edit.get("country") or "", key="edit_client_country")
        desc = st.text_area("Business Description", value=edit.get("business_description") or "", key="edit_client_desc")
        is_active = st.checkbox("Is Active", value=bool(edit["is_active"]), key="edit_client_active")
        col1, col2 = st.columns(2)
        if col1.button("Save Changes", key="edit_client_save"):
            if not name.strip():
                st.error("Name required.")
            else:
                try:
                    crud.update_client(edit["id"], name, industry, country, desc)
                    crud.set_client_active(edit["id"], is_active)
                    st.success("Company updated ✅")
                    cache_data.clear()
                    st.session_state.edit_client_mode = False
                    st.session_state.edit_client_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed ❌\n\n{_format_exc(e)}")
        if col2.button("Cancel", key="edit_client_cancel"):
            st.session_state.edit_client_mode = False
            st.session_state.edit_client_id = None
            st.rerun()


def render_companies_change():
    clients = cached_clients()
    if not clients:
        st.info("No companies yet. Add one below.")
        return

    st.subheader("Change Company")
    _select_active_client(clients)


def render_companies_add():
    st.subheader("Add Company")
    name = st.text_input("Company Name *", key="add_client_name")
    industry = st.text_input("Industry", key="add_client_industry")
    country = st.text_input("Country", key="add_client_country")
    desc = st.text_area("Business Description", key="add_client_desc")
    if st.button("Save Company"):
        if not name.strip():
            st.error("Name required.")
        else:
            try:
                cid = crud.create_client(name, industry, country, desc)
                st.success(f"Created client id={cid}")
                cache_data.clear()
                st.session_state.active_client_id = cid
                st.session_state.active_client_name = name
                st.rerun()
            except Exception as e:
                st.error(f"Create client failed ❌\n\n{_format_exc(e)}")


def render_companies():
    """Main companies page router - NEW ADDED FUNCTION"""
    subpage = st.session_state.active_subpage
    
    if subpage == "List":
        render_companies_list()
    elif subpage == "Change Company":
        render_companies_change()
    elif subpage == "Add Company":
        render_companies_add()
    else:
        render_companies_list()


def render_setup_banks():
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
                    cache_data.clear()
                    st.session_state.setup_banks_mode = "list"
                    st.r
