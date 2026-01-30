# app.py - COMPLETE FIXED VERSION WITH LOADER & ALL CONTENT
import io
import sys
import calendar
import datetime as dt
import urllib.parse
import base64
from pathlib import Path
import time

import pandas as pd
import streamlit as st
from streamlit import cache_data

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import init_db
from src import crud


def _logo_data_uri(path: Path) -> str:
    """Convert image to data URI"""
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".")
    
    if suffix in {"svg"}:
        svg_text = path.read_text(encoding="utf-8")
        encoded = urllib.parse.quote(svg_text)
        return f"data:image/svg+xml;utf8,{encoded}"
    
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    
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
    """Initialize all session state variables"""
    defaults = {
        "active_page": st.session_state.get("nav_page", "Home"),
        "active_subpage": None,
        "active_client_id": st.session_state.get("active_client_id"),
        "active_client_name": st.session_state.get("active_client_name"),
        "bank_id": st.session_state.get("bank_id"),
        "period": st.session_state.get("period"),
        "date_from": st.session_state.get("date_from"),
        "date_to": st.session_state.get("date_to"),
        "df_raw": st.session_state.get("df_raw"),
        "year": st.session_state.get("year", 2025),
        "month": st.session_state.get("month", "Oct"),
        "setup_banks_mode": st.session_state.get("setup_banks_mode", "list"),
        "setup_bank_edit_id": st.session_state.get("setup_bank_edit_id"),
        "setup_categories_mode": st.session_state.get("setup_categories_mode", "list"),
        "setup_category_edit_id": st.session_state.get("setup_category_edit_id"),
        "sidebar_companies_open": st.session_state.get("sidebar_companies_open", False),
        "sidebar_setup_open": st.session_state.get("sidebar_setup_open", False),
        "edit_client_id": st.session_state.get("edit_client_id"),
        "edit_client_mode": st.session_state.get("edit_client_mode", False),
        "standardized_rows": st.session_state.get("standardized_rows", []),
        "categorisation_selected_item": st.session_state.get("categorisation_selected_item"),
        # Loader states
        "app_initialized": st.session_state.get("app_initialized", False),
        "page_transition_loader": st.session_state.get("page_transition_loader", False),
        "loader_start_time": st.session_state.get("loader_start_time", 0),
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    if st.session_state.active_page == "Companies" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "List"
    if st.session_state.active_page == "Setup" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "Banks"


init_session_state()

# ---------------- Loader System ----------------
def show_loader_instant(duration=1.8, message="LOADING"):
    """Show instant loader that appears immediately"""
    loader_html = f"""
    <div id="bankcat-instant-loader" style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100vh;
        background: white;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 99999;
        animation: fadeIn 0.1s ease-in;
    ">
        <style>
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes smoothSpin {{
            0% {{ transform: rotate(0deg); opacity: 0.8; }}
            50% {{ transform: rotate(180deg); opacity: 1; filter: drop-shadow(0 0 20px rgba(124, 255, 178, 0.9)); }}
            100% {{ transform: rotate(360deg); opacity: 0.8; }}
        }}
        
        @keyframes fadeOut {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; visibility: hidden; }}
        }}
        
        .loader-core {{
            animation: smoothSpin 1.5s cubic-bezier(0.68, -0.55, 0.27, 1.55) infinite;
            width: 180px;
            height: 180px;
        }}
        
        .loader-text {{
            margin-top: 25px;
            color: #4a5568;
            font-size: 16px;
            font-weight: 500;
            letter-spacing: 3px;
            animation: smoothSpin 3s ease-in-out infinite;
            opacity: 0.7;
        }}
        </style>
    """
    
    # Add SVG or fallback
    loader_svg_path = ROOT / "assets" / "bankcat-loader.gif.svg"
    if loader_svg_path.exists():
        svg_bytes = loader_svg_path.read_bytes()
        svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
        loader_html += f"""
        <img src="data:image/svg+xml;base64,{svg_base64}" 
             class="loader-core" 
             alt="Loading..."/>
        """
    else:
        loader_html += """
        <div class="loader-core" style="
            border: 12px solid #f3f3f3;
            border-top: 12px solid #7CFFB2;
            border-radius: 50%;
        "></div>
        """
    
    loader_html += f"""
        <div class="loader-text">{message}</div>
    </div>
    
    <script>
    // Auto-remove after duration
    setTimeout(function() {{
        var loader = document.getElementById('bankcat-instant-loader');
        if (loader) {{
            loader.style.animation = 'fadeOut 0.3s forwards';
            setTimeout(function() {{
                if (loader.parentNode) {{
                    loader.parentNode.removeChild(loader);
                }}
            }}, 300);
        }}
    }}, {int(duration * 1000)});
    </script>
    """
    
    return loader_html

# ---------------- App Startup Loader ----------------
if not st.session_state.app_initialized:
    # Show instant loader
    st.markdown(show_loader_instant(2.5, "LOADING BANKCAT"), unsafe_allow_html=True)
    
    # Mark as initialized
    st.session_state.app_initialized = True
    
    # Wait for loader duration and rerun
    time.sleep(2.5)
    st.rerun()

# ---------------- Custom CSS ----------------
st.markdown(
    """
<style>
/* Sidebar logo styling - TIGHT ALIGNMENT */
.sidebar-logo {
    text-align: center;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* Home page logo styling - MINIMAL SPACING */
.home-logo-container {
    text-align: center;
    margin: 1rem auto;
    padding: 0.5rem 0;
}

.home-logo-container img {
    max-width: 520px;
    height: auto;
    margin: 0 auto;
}

/* Page title styling */
.page-title {
    margin-top: 0.75rem;
    margin-bottom: 1.5rem;
}

/* Content spacing */
.main .block-container {
    padding-top: 1rem !important;
}

/* Categorisation specific styling */
.categorisation-container {
    padding: 1rem;
}

.section-card {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    border: 1px solid #e5e7eb;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Page Title ----------------
active_page = st.session_state.active_page
active_subpage = st.session_state.active_subpage
page_title = active_page
if active_page == "Companies" and active_subpage:
    page_title = f"Companies > {active_subpage}"
elif active_page == "Setup" and active_subpage:
    page_title = f"Setup > {active_subpage}"

logo_path = ROOT / "assets" / "bankcat-logo.jpeg"

# فقط ہوم پیج پر لوگو دکھائیں
if active_page == "Home" and logo_path.exists():
    st.markdown('<div class="home-logo-container">', unsafe_allow_html=True)
    st.image(str(logo_path), width=520)
    st.markdown('</div>', unsafe_allow_html=True)
    # ہوم پیج پر الگ سے ٹائٹل نہیں دکھائیں گے
else:
    # دیگر صفحات پر صرف ٹائٹل دکھائیں گے
    st.markdown(f'<h1 class="page-title">{page_title}</h1>', unsafe_allow_html=True)

# ---------------- Page Transition Handler ----------------
def handle_page_transition(new_page: str, subpage: str | None = None):
    """Handle page transitions with loader"""
    if st.session_state.active_page != new_page:
        # Show loader
        st.markdown(show_loader_instant(1.8, "LOADING PAGE"), unsafe_allow_html=True)
        
        # Update page state
        st.session_state.active_page = new_page
        if subpage:
            st.session_state.active_subpage = subpage
        
        # Set loader start time
        st.session_state.page_transition_loader = True
        st.session_state.loader_start_time = time.time()
        
        # Force rerun
        st.rerun()

# Check if loader should be shown
if st.session_state.page_transition_loader:
    elapsed = time.time() - st.session_state.loader_start_time
    if elapsed < 1.8:
        # Still within loader duration
        time.sleep(1.8 - elapsed)
    
    # Clear loader state
    st.session_state.page_transition_loader = False
    st.session_state.loader_start_time = 0

# ---------------- Sidebar Content ----------------
with st.sidebar:
    # Add logo to sidebar top (سینٹر میں)
    if logo_path.exists():
        st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
        st.image(str(logo_path), width=220)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("### Navigation")
    
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
            handle_page_transition(page)

    # Companies - SIMPLE BUTTON
    companies_active = st.session_state.active_page == "Companies"
    if st.button(
        "🏢 Companies",
        use_container_width=True,
        key="nav_companies",
        type=_button_type(companies_active),
    ):
        handle_page_transition("Companies", "List")

    # Setup - EXPANDABLE
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
            handle_page_transition("Setup", "Banks")
    
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
                st.session_state.active_subpage = tab
                st.rerun()

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
    bank_options = []
    for b in banks_active:
        bank_options.append(f"{b['id']} | {b['bank_name']} ({b['account_type']})")
    
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
    clients = cached_clients()
    _select_active_client(clients)
    
    st.markdown("## BankCat Demo")
    st.write("Welcome to the BankCat demo workspace.")
    st.caption("Shortcuts and quick links will be added later.")


def render_dashboard():
    st.markdown("## 📊 Financial Dashboard")
    
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
            
            df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
            df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
            
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
                if 'category' in expenses.columns:
                    expenses['category'] = expenses['category'].fillna('Uncategorized')
                    expenses['debit'] = pd.to_numeric(expenses['debit'], errors='coerce').fillna(0)
                    
                    top_categories = expenses.groupby('category')['debit'].sum()
                    
                    if not top_categories.empty:
                        top_categories = top_categories.sort_values(ascending=False).head(10)
                        if not top_categories.empty:
                            chart_data = pd.DataFrame({
                                'Category': top_categories.index,
                                'Amount': top_categories.values
                            })
                            st.bar_chart(chart_data.set_index('Category'))
                        else:
                            st.info("No expense categories to display")
                    else:
                        st.info("No expense data available for chart")
                else:
                    st.info("Category data not available in the selected transactions")
            else:
                st.info("No expense data available")
                
        else:
            st.info("No committed transactions found for the selected period.")
            
    except Exception as e:
        st.error(f"Unable to load dashboard data: {_format_exc(e)}")


def render_reports():
    st.markdown("## 📊 Reports")
    
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
    
    st.markdown("## 🏢 Companies")
    
    if st.button("➕ Add Company", type="primary"):
        st.session_state.active_subpage = "Add Company"
        st.rerun()
    
    st.markdown("---")
    
    if not clients:
        st.info("No companies yet. Add one above.")
        return

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
            st.rerun()
        if row[4].button("✎", key=f"edit_client_{c['id']}"):
            st.session_state.edit_client_id = c["id"]
            st.session_state.edit_client_mode = True
            st.rerun()

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


def render_companies_add():
    st.markdown("## 🏢 Companies > Add Company")
    
    name = st.text_input("Company Name *", key="add_client_name")
    industry = st.text_input("Industry", key="add_client_industry")
    country = st.text_input("Country", key="add_client_country")
    desc = st.text_area("Business Description", key="add_client_desc")
    
    col1, col2 = st.columns(2)
    if col1.button("Save Company", type="primary"):
        if not name.strip():
            st.error("Name required.")
        else:
            try:
                cid = crud.create_client(name, industry, country, desc)
                st.success(f"Created client id={cid}")
                cache_data.clear()
                st.session_state.active_client_id = cid
                st.session_state.active_client_name = name
                st.session_state.active_subpage = "List"
                st.rerun()
            except Exception as e:
                st.error(f"Create client failed ❌\n\n{_format_exc(e)}")
    
    if col2.button("Cancel"):
        st.session_state.active_subpage = "List"
        st.rerun()


def render_companies():
    """Main companies page router"""
    subpage = st.session_state.active_subpage
    
    if subpage == "List":
        render_companies_list()
    elif subpage == "Add Company":
        render_companies_add()
    else:
        st.session_state.active_subpage = "List"
        st.rerun()


def render_setup_banks():
    st.markdown("## 🛠️ Setup > Banks")
    
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
            value=edit_bank.get("account_masked") or "",
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
                    cache_data.clear()
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
            row[3].write(bank.get("account_masked") or "")
            if row[4].button("✎", key=f"edit_bank_{bank['id']}", help="Edit bank"):
                st.session_state.setup_banks_mode = "edit"
                st.session_state.setup_bank_edit_id = bank["id"]
                st.rerun()


def render_setup_categories():
    st.markdown("## 🛠️ Setup > Categories")
    
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
                    cache_data.clear()
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
        allowed_natures = ["Any", "Debit", "Credit"]
        current_nature = edit_cat.get("nature") or "Any"
        if current_nature not in allowed_natures:
            current_nature = "Any"
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
                    cache_data.clear()
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
        
        sample_data = pd.DataFrame({
            'category_name': ['Office Supplies', 'Travel Expenses', 'Software Subscriptions'],
            'type': ['Expense', 'Expense', 'Expense'],
            'nature': ['Debit', 'Debit', 'Debit']
        })
        
        csv = sample_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Sample CSV",
            data=csv,
            file_name="categories_sample.csv",
            mime="text/csv",
            key="download_sample"
        )
        
        st.caption("Required columns: category_name, type (Income/Expense/Other), nature (Any/Debit/Credit)")
        
        cat_file = st.file_uploader("Upload CSV", type=["csv"], key="cat_csv")
        if cat_file:
            try:
                dfu = pd.read_csv(cat_file)
                st.dataframe(dfu.head(20), use_container_width=True, hide_index=True)
                rows = dfu.to_dict(orient="records")
                if st.button("Import Categories Now"):
                    ok, bad = crud.bulk_add_categories(client_id, rows)
                    st.success(f"Imported ✅ ok={ok}, skipped={bad}")
                    cache_data.clear()
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
            if row[4].button("✎", key=f"edit_cat_{cat['id']}", help="Edit category"):
                st.session_state.setup_categories_mode = "edit"
                st.session_state.setup_category_edit_id = cat["id"]
                st.rerun()


def render_setup():
    """Setup page with Banks and Categories based on subpage"""
    if st.session_state.active_subpage == "Banks":
        render_setup_banks()
    else:
        render_setup_categories()


def render_categorisation():
    st.markdown("## 🧠 Categorisation")
    
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

    # Bank Selection
    col1, col2 = st.columns([2, 1])
    with col1:
        bank_options = []
        for b in banks_active:
            bank_options.append(f"{b['id']} | {b['bank_name']} ({b['account_type']})")
        
        selected_index = 0
        if st.session_state.bank_id:
            for i, opt in enumerate(bank_options):
                if opt.startswith(f"{st.session_state.bank_id} |"):
                    selected_index = i
                    break
        
        bank_pick = st.selectbox("Select Bank", bank_options, index=selected_index, key="cat_bank_select")
        bank_id = int(bank_pick.split("|")[0].strip())
        st.session_state.bank_id = bank_id
        bank_obj = [b for b in banks_active if int(b["id"]) == bank_id][0]
        bank_type = bank_obj.get("account_type", "Current")
    
    with col2:
        st.info(f"Selected: {bank_obj['bank_name']}")

    # Period Selection
    st.markdown("---")
    st.markdown("### Period Selection")
    
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    
    row2 = st.columns([1, 1, 1, 2])
    with row2[0]:
        year_range = list(range(2020, 2031))
        year = st.selectbox("Year", year_range, index=year_range.index(st.session_state.year))
        st.session_state.year = year
    
    with row2[1]:
        month = st.selectbox("Month", month_names, index=month_names.index(st.session_state.month))
        st.session_state.month = month
    
    with row2[2]:
        period = f"{year}-{month_names.index(month)+1:02d}"
        st.text_input("Period (auto)", value=period, disabled=True)
        st.session_state.period = period
    
    with row2[3]:
        month_idx = month_names.index(month) + 1
        last_day = calendar.monthrange(year, month_idx)[1]
        default_range = (
            st.session_state.date_from or dt.date(year, month_idx, 1),
            st.session_state.date_to or dt.date(year, month_idx, last_day),
        )
        dr = st.date_input("Statement Date Range", value=default_range, key="cat_date_range")
        date_from, date_to = dr if isinstance(dr, tuple) else (dr, dr)
        st.session_state.date_from = date_from
        st.session_state.date_to = date_to

    draft_summary = crud.get_draft_summary(client_id, bank_id, period)
    commit_summary = crud.get_commit_summary(client_id, bank_id, period)

    # Saved Items Section
    st.markdown("---")
    st.markdown("### 📁 Saved Items")
    
    item_rows: list[dict] = []
    if draft_summary:
        item_rows.append(
            {
                "id": "draft_saved",
                "item_type": "Draft",
                "status_label": "Draft Saved",
                "row_count": int(draft_summary.get("row_count") or 0),
                "min_date": draft_summary.get("min_date"),
                "max_date": draft_summary.get("max_date"),
                "last_updated": draft_summary.get("last_saved"),
            }
        )
        if int(draft_summary.get("suggested_count") or 0) > 0:
            item_rows.append(
                {
                    "id": "draft_categorised",
                    "item_type": "Draft",
                    "status_label": "Draft Categorised",
                    "row_count": int(draft_summary.get("row_count") or 0),
                    "min_date": draft_summary.get("min_date"),
                    "max_date": draft_summary.get("max_date"),
                    "last_updated": draft_summary.get("last_saved"),
                }
            )
    if commit_summary:
        item_rows.append(
            {
                "id": f"committed_{commit_summary.get('commit_id')}",
                "item_type": "Committed",
                "status_label": "Committed",
                "row_count": int(commit_summary.get("row_count") or 0),
                "min_date": commit_summary.get("min_date"),
                "max_date": commit_summary.get("max_date"),
                "last_updated": commit_summary.get("committed_at"),
            }
        )

    if "categorisation_selected_item" not in st.session_state:
        st.session_state.categorisation_selected_item = None

    if item_rows:
        items_df = pd.DataFrame(item_rows).set_index("id")
        selected_item = st.session_state.categorisation_selected_item
        if selected_item not in items_df.index:
            selected_item = items_df.index[0]
            st.session_state.categorisation_selected_item = selected_item
        
        # Display saved items
        for item in item_rows:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.write(f"**{item['status_label']}**")
            with col2:
                st.write(f"Rows: {item['row_count']}")
            with col3:
                st.write(f"Updated: {item['last_updated'][:10] if item['last_updated'] else 'N/A'}")
            with col4:
                if st.button("Select", key=f"select_{item['id']}"):
                    st.session_state.categorisation_selected_item = item['id']
                    st.rerun()
    else:
        st.info("No saved items yet for this bank + period.")

    # Upload Section
    st.markdown("---")
    st.markdown("### 📤 Upload Statement")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        stmt_template = pd.DataFrame([
            {"Date": "2025-10-01", "Description": "POS Purchase Example", "Dr": 100.00, "Cr": 0.00, "Closing": ""}
        ])
        buf2 = io.StringIO()
        stmt_template.to_csv(buf2, index=False)
        st.download_button(
            "📥 Download Template",
            data=buf2.getvalue(),
            file_name="statement_template.csv",
            mime="text/csv",
        )
    
    with col2:
        up_stmt = st.file_uploader("Upload CSV statement", type=["csv"], key="stmt_csv")

    df_raw = None
    if up_stmt is not None:
        try:
            df_raw = pd.read_csv(up_stmt)
            st.session_state.df_raw = df_raw
            st.success(f"✅ Loaded {len(df_raw)} rows")
        except Exception as e:
            st.error(f"❌ Upload failed: {_format_exc(e)}")
    else:
        df_raw = st.session_state.df_raw

    # Mapping Section
    standardized_rows = []
    if df_raw is not None and len(df_raw) > 0:
        st.markdown("### 🗺️ Column Mapping")
        
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
        
        # Process rows
        standardized_rows = []
        for _, r in df_raw.iterrows():
            try:
                d = pd.to_datetime(r[map_date]).date() if map_date != "(blank)" else None
                ds = str(r[map_desc]).strip() if map_desc != "(blank)" else ""
                
                if d and ds:
                    drv = pd.to_numeric(r[map_dr], errors="coerce") if map_dr != "(blank)" else 0
                    crv = pd.to_numeric(r[map_cr], errors="coerce") if map_cr != "(blank)" else 0
                    bal = pd.to_numeric(r[map_bal], errors="coerce") if map_bal != "(blank)" else None
                    
                    standardized_rows.append({
                        "tx_date": d,
                        "description": ds,
                        "debit": round(float(drv or 0.0), 2),
                        "credit": round(float(crv or 0.0), 2),
                        "balance": float(bal) if bal is not None else None,
                    })
            except:
                continue
        
        st.session_state.standardized_rows = standardized_rows
        st.info(f"✅ Mapped {len(standardized_rows)} rows")

    # Main View
    st.markdown("---")
    st.markdown("### 👁️ Main View")
    
    selected_item = st.session_state.categorisation_selected_item
    if selected_item in {"draft_saved", "draft_categorised"}:
        try:
            draft_rows = crud.load_draft_rows(client_id, bank_id, period)
            if draft_rows:
                df_d = pd.DataFrame(draft_rows)
                st.dataframe(df_d, use_container_width=True, hide_index=True)
            else:
                st.info("No draft rows found.")
        except Exception as e:
            st.error(f"Unable to load draft rows: {_format_exc(e)}")
    elif selected_item and selected_item.startswith("committed"):
        try:
            committed_rows = crud.load_committed_rows(client_id, bank_id, period)
            if committed_rows:
                st.dataframe(pd.DataFrame(committed_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No committed rows found.")
        except Exception as e:
            st.error(f"Unable to load committed rows: {_format_exc(e)}")
    elif standardized_rows:
        st.dataframe(pd.DataFrame(standardized_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Select a saved item or upload a statement to view data.")

    # Process Status
    st.markdown("---")
    st.markdown("### 📊 Process Status")
    
    status_cols = st.columns(3)
    with status_cols[0]:
        if draft_summary:
            st.metric("Draft Rows", draft_summary.get("row_count", 0))
    with status_cols[1]:
        if draft_summary:
            st.metric("Categorized", draft_summary.get("suggested_count", 0))
    with status_cols[2]:
        if commit_summary:
            st.metric("Committed", "Yes")
        else:
            st.metric("Committed", "No")

    # Action Buttons
    st.markdown("---")
    st.markdown("### 🎯 Actions")
    
    action_col1, action_col2, action_col3 = st.columns(3)
    
    with action_col1:
        if standardized_rows and not draft_summary:
            if st.button("💾 Save Draft", type="primary", use_container_width=True):
                try:
                    n = crud.insert_draft_rows(client_id, bank_id, period, standardized_rows, replace=True)
                    st.success(f"✅ Draft saved ({n} rows)")
                    st.session_state.standardized_rows = []
                    st.session_state.df_raw = None
                    cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Save failed: {_format_exc(e)}")
    
    with action_col2:
        if draft_summary and int(draft_summary.get("suggested_count", 0)) == 0:
            if st.button("🤖 Suggest Categories", type="secondary", use_container_width=True):
                try:
                    n = crud.process_suggestions(client_id, bank_id, period, bank_account_type=bank_type)
                    st.success(f"✅ Categories suggested ({n} rows)")
                    cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Suggestion failed: {_format_exc(e)}")
    
    with action_col3:
        if draft_summary and int(draft_summary.get("suggested_count", 0)) > 0 and not commit_summary:
            if st.button("🔒 Commit Final", type="primary", use_container_width=True):
                committed_by = st.text_input("Committed by", key="commit_by")
                confirm = st.checkbox("Confirm final commit", key="confirm_commit")
                
                if confirm and committed_by:
                    try:
                        result = crud.commit_period(client_id, bank_id, period, committed_by=committed_by)
                        if result.get("ok"):
                            st.success(f"✅ Committed ({result.get('rows', 0)} rows)")
                            cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"❌ Commit failed: {result.get('msg', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"❌ Commit failed: {_format_exc(e)}")


def render_settings():
    st.markdown("## ⚙️ Settings")
    
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
            cache_data.clear()
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{_format_exc(e)}")

    if st.button("Refresh Lists"):
        cache_data.clear()
        st.success("Refreshed ✅")

    st.markdown("### Verify DB Schema")
    if "schema_check_result" not in st.session_state:
        st.session_state.schema_check_result = None
    if st.button("Verify DB Schema"):
        st.session_state.schema_check_result = _run_schema_check()
        st.rerun()

    schema_result = st.session_state.schema_check_result
    if schema_result:
        if schema_result.get("error"):
            st.error(schema_result["error"])
            return
        issues = schema_result.get("issues", [])
        if not issues:
            st.success("✅ DB schema matches docs/DB_SCHEMA_TRUTH.md")
        else:
            st.warning("⚠️ Schema mismatch detected")
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)


# ---------------- Main Page Router ----------------
def main():
    page = st.session_state.active_page
    
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
    else:
        render_home()


if __name__ == "__main__":
    main()
