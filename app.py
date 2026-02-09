# app.py - UPDATED WITH DATA DELETION + GREEN HEADER + REMOVE BLANK CONTAINERS
import io
import sys
import calendar
import datetime as dt
import urllib.parse
import base64
from pathlib import Path
import time
import random

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
    "delete_client_data",
    "ensure_ask_client_category",
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
        crud.ensure_ask_client_category(client_id)
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
        "column_mapping": st.session_state.get("column_mapping", {}),
        "categorisation_selected_item": st.session_state.get("categorisation_selected_item"),
        "show_edit_form": st.session_state.get("show_edit_form", False),
        "edit_row_index": st.session_state.get("edit_row_index"),
        "app_initialized": st.session_state.get("app_initialized", False),
        "page_transition_loader": st.session_state.get("page_transition_loader", False),
        "loader_start_time": st.session_state.get("loader_start_time", 0),
        "processing_suggestions": st.session_state.get("processing_suggestions", False),
        "processing_commit": st.session_state.get("processing_commit", False),
        "last_edited_row": st.session_state.get("last_edited_row", None),
        "last_edit_time": st.session_state.get("last_edit_time", 0),
        "file_uploaded": st.session_state.get("file_uploaded", False),
        "ai_suggestions_animating": st.session_state.get("ai_suggestions_animating", False),
        "ai_current_row": st.session_state.get("ai_current_row", 0),
        "cat_animation_stage": st.session_state.get("cat_animation_stage", 0),
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    if st.session_state.active_page == "Companies" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "List"
    if st.session_state.active_page == "Setup" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "Banks"


init_session_state()

# ---------------- Professional CSS Styling with GREEN HEADER ----------------
st.markdown(
    """
<style>
/* ========== GREEN HEADER ========== */
/* Main header background */
.css-1d391kg {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    border-bottom: 1px solid #059669 !important;
}

/* Streamlit header elements */
.css-1v0mbdj, .css-1v3fvcr, .css-1oe5cao {
    color: white !important;
}

/* ========== FIXED HEADER ========== */
.stApp {
    background-color: #f8fafc;
    padding-top: 0 !important;
}

/* Prevent sidebar from overlapping */
section[data-testid="stSidebar"] {
    z-index: 90 !important;
}

/* ========== PROFESSIONAL BUTTONS ========== */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease-in-out !important;
    border: 1px solid transparent !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.875rem !important;
}

/* Primary Buttons (Green) */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3) !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(16, 185, 129, 0.4) !important;
}

/* Secondary Buttons (White with Border) */
.stButton > button[kind="secondary"] {
    background: white !important;
    color: #374151 !important;
    border: 1px solid #d1d5db !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
}

.stButton > button[kind="secondary"]:hover {
    background: #f9fafb !important;
    border-color: #9ca3af !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* Active Sidebar Button */
.stButton > button[kind="secondary"].active-nav {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3) !important;
}

/* ========== CARD STYLING ========== */
.section-card {
    background: white;
    border-radius: 12px;
    padding: 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    border: 1px solid #e5e7eb;
    transition: all 0.3s ease;
}

.section-card:hover {
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    transform: translateY(-2px);
}

/* ========== FORM ELEMENTS ========== */
.stSelectbox, .stTextInput, .stDateInput, .stTextArea {
    margin-bottom: 1rem;
}

.stSelectbox > div, .stTextInput > div, .stDateInput > div {
    border-radius: 8px;
    border: 1px solid #d1d5db;
}

.stSelectbox > div:focus-within, 
.stTextInput > div:focus-within, 
.stDateInput > div:focus-within {
    border-color: #10b981 !important;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1) !important;
}

/* ========== STATUS BADGES ========== */
.status-badge {
    padding: 0.35rem 0.85rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-draft {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    color: #1e40af;
    border: 1px solid #93c5fd;
}

.status-categorised {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    color: #92400e;
    border: 1px solid #fcd34d;
}

.status-committed {
    background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
    color: #065f46;
    border: 1px solid #86efac;
}

/* ========== TABLES ========== */
.stDataFrame {
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
}

/* ========== SUCCESS/ERROR MESSAGES ========== */
.stAlert {
    border-radius: 8px;
    border-left: 4px solid !important;
}

/* ========== SIDEBAR IMPROVEMENTS ========== */
/* Sidebar section headers */
.sidebar-section {
    color: #6b7280;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    padding-left: 1rem;
}

/* ========== RESPONSIVE FIXES ========== */
@media (max-width: 768px) {
    .section-card {
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .stButton > button {
        width: 100% !important;
        margin-bottom: 0.5rem;
    }
}

/* ========== CUSTOM SCROLLBAR ========== */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #a1a1a1;
}

/* ========== LOADING STATES ========== */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading-pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* ========== HIGHLIGHT RECENT EDITS ========== */
@keyframes highlightRow {
    0% { background-color: rgba(124, 255, 178, 0.4); }
    70% { background-color: rgba(124, 255, 178, 0.1); }
    100% { background-color: transparent; }
}

.highlight-row {
    animation: highlightRow 2s ease-out;
}

/* ========== PAGE TITLE ========== */
.page-title {
    color: #111827;
    font-size: 1.875rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid #7CFFB2;
}

.page-title-small {
    color: #374151;
    font-size: 1.25rem;
    font-weight: 600;
    margin-top: 1rem;
    margin-bottom: 0.75rem;
}

/* ========== METRIC CARDS ========== */
.metric-card {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    text-align: center;
}

.metric-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
}

.metric-label {
    font-size: 0.875rem;
    color: #6b7280;
    margin-top: 0.25rem;
}

/* ========== SECTION DIVIDER ========== */
.section-divider {
    border-top: 2px solid #e5e7eb;
    margin: 1.5rem 0;
}

.green-divider {
    border-top: 2px solid #10b981;
    margin: 1.5rem 0;
}

/* ========== REMOVE EMPTY CONTAINERS ========== */
/* Hide empty Streamlit containers that create blank white tables */
.empty-container {
    display: none !important;
}

</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Helper Functions ----------------
def show_processing_message(message="Processing..."):
    """Show a simple processing message"""
    return st.info(f"⏳ {message}")

def show_success_message(message="Success!"):
    """Show success message"""
    return st.success(f"✅ {message}")

def show_error_message(message="Error!"):
    """Show error message"""
    return st.error(f"❌ {message}")

def show_warning_message(message="Warning!"):
    """Show warning message"""
    return st.warning(f"⚠️ {message}")

def show_info_message(message="Info!"):
    """Show info message"""
    return st.info(f"ℹ️ {message}")

# ---------------- App Startup ----------------
if not st.session_state.app_initialized:
    time.sleep(0.5)
    st.session_state.app_initialized = True
    st.rerun()

# ---------------- Page Title ----------------
active_page = st.session_state.active_page
active_subpage = st.session_state.active_subpage
page_title = active_page
if active_page == "Companies" and active_subpage:
    page_title = f"Companies › {active_subpage}"
elif active_page == "Setup" and active_subpage:
    page_title = f"Setup › {active_subpage}"

logo_path = ROOT / "assets" / "bankcat-logo.jpeg"

if active_page == "Home" and logo_path.exists():
    st.markdown('<div class="home-logo-container fade-in-content">', unsafe_allow_html=True)
    st.image(str(logo_path), width=520)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<h1 class="page-title">{page_title}</h1>', unsafe_allow_html=True)

# ---------------- Page Transition Handler ----------------
def handle_page_transition(new_page: str, subpage: str | None = None):
    if st.session_state.active_page != new_page:
        st.session_state.active_page = new_page
        if subpage:
            st.session_state.active_subpage = subpage
        st.rerun()

# ---------------- Professional Sidebar ----------------
with st.sidebar:
    # Logo
    if logo_path.exists():
        st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
        st.image(str(logo_path), width=180)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-section">Main Navigation</div>', unsafe_allow_html=True)
    
    # Main navigation buttons
    nav_items = [
        {"label": "🏠 Home", "page": "Home"},
        {"label": "📊 Reports", "page": "Reports"},
        {"label": "📈 Dashboard", "page": "Dashboard"},
        {"label": "🧠 Categorisation", "page": "Categorisation"},
        {"label": "🏢 Companies", "page": "Companies"},
        {"label": "⚙️ Settings", "page": "Settings"},
    ]
    
    for item in nav_items:
        is_active = st.session_state.active_page == item["page"]
        
        # Determine button type
        if is_active:
            btn_type = "primary"
        else:
            btn_type = "secondary"
        
        if st.button(
            item["label"],
            use_container_width=True,
            key=f"nav_{item['page']}",
            type=btn_type,
        ):
            if item["page"] != "Companies":
                st.session_state.sidebar_setup_open = False
            handle_page_transition(item["page"])
    
    # Setup Section
    st.markdown('<div class="sidebar-section">Setup</div>', unsafe_allow_html=True)
    
    setup_active = st.session_state.active_page == "Setup"
    if st.button(
        "🏦 Banks",
        use_container_width=True,
        key="nav_banks",
        type="primary" if (setup_active and st.session_state.active_subpage == "Banks") else "secondary",
    ):
        handle_page_transition("Setup", "Banks")
    
    if st.button(
        "🗂️ Categories",
        use_container_width=True,
        key="nav_categories",
        type="primary" if (setup_active and st.session_state.active_subpage == "Categories") else "secondary",
    ):
        handle_page_transition("Setup", "Categories")
    
    st.markdown("---")
    
    # Quick Actions
    st.markdown('<div class="sidebar-section">Quick Actions</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export", use_container_width=True):
            if st.session_state.active_client_id:
                show_success_message("Export feature coming soon!")
            else:
                show_warning_message("Select a company first")
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            cache_data.clear()
            st.rerun()

# ---------------- Helper Functions ----------------
def _require_active_client() -> int | None:
    client_id = st.session_state.active_client_id
    if not client_id:
        show_warning_message("Select a company on Home first.")
        return None
    return client_id

def _select_active_client(clients: list[dict]) -> int | None:
    options = ["(Select a company)"] + [f"{c['id']} | {c['name']}" for c in clients]
    selected_index = 0
    if st.session_state.active_client_id:
        for i, opt in enumerate(options):
            if opt.startswith(f"{st.session_state.active_client_id} |"):
                selected_index = i
                break
    
    client_pick = st.selectbox(
        "Select Company",
        options=options,
        index=selected_index,
        key="active_client_select",
    )
    
    if client_pick == "(Select a company)":
        st.session_state.active_client_id = None
        st.session_state.active_client_name = None
        return None
    
    client_id = int(client_pick.split("|")[0].strip())
    st.session_state.active_client_id = client_id
    st.session_state.active_client_name = client_pick.split("|")[1].strip()
    return client_id

# ---------------- Page Render Functions ----------------
def render_home():
    clients = cached_clients()
    
    st.markdown("## Welcome to BankCat AI 🏦😺")
    st.write("AI-powered bank statement categorization for accountants.")
    
    # Add green divider instead of blank container
    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    
    # Client selector in a card
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Select Company")
        client_pick = _select_active_client(clients)
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.active_client_id:
        # Add green divider instead of blank container
        st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown(f"### 📋 {st.session_state.active_client_name}")
            
            # Quick stats in metric cards
            col1, col2, col3 = st.columns(3)
            
            with col1:
                banks = cached_banks(st.session_state.active_client_id)
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-value">{len(banks) if banks else 0}</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Banks</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                cats = cached_categories(st.session_state.active_client_id)
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-value">{len(cats) if cats else 0}</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Categories</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                try:
                    drafts = crud.drafts_summary(st.session_state.active_client_id, None)
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">{len(drafts) if drafts else 0}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Drafts</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                except:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">0</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Drafts</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # Quick actions
            st.markdown("### Quick Actions")
            action_cols = st.columns(3)
            
            with action_cols[0]:
                if st.button("🧠 Start Categorising", use_container_width=True, type="primary"):
                    handle_page_transition("Categorisation")
            
            with action_cols[1]:
                if st.button("📊 View Reports", use_container_width=True):
                    handle_page_transition("Reports")
            
            with action_cols[2]:
                if st.button("🏦 Manage Banks", use_container_width=True):
                    handle_page_transition("Setup", "Banks")
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.info("💡 **Getting Started:**\n1. Select or create a company\n2. Add bank accounts\n3. Define categories\n4. Start processing statements!")
            
            if st.button("➕ Create New Company", type="primary", use_container_width=True):
                handle_page_transition("Companies", "List")
            st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard():
    st.markdown("## 📊 Financial Dashboard")
    
    client_id = _require_active_client()
    if not client_id:
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Date Range")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", dt.date.today() - dt.timedelta(days=90))
        with col2:
            end_date = st.date_input("End Date", dt.date.today())
        
        if start_date > end_date:
            show_error_message("Start date must be before end date.")
            st.markdown('</div>', unsafe_allow_html=True)
            return
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    try:
        transactions = crud.list_committed_transactions(
            client_id, 
            date_from=start_date, 
            date_to=end_date
        )
        
        if transactions:
            df = pd.DataFrame(transactions)
            
            # Income vs Expense metrics
            with st.container():
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("### 💰 Income vs Expense")
                
                df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
                df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
                
                total_income = df['credit'].sum()
                total_expense = df['debit'].sum()
                net = total_income - total_expense
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Income", f"${total_income:,.2f}", 
                             delta_color="off" if total_income == 0 else "normal")
                with col2:
                    st.metric("Total Expense", f"${total_expense:,.2f}", 
                             delta_color="off" if total_expense == 0 else "inverse")
                with col3:
                    delta = f"{net:+,.2f}"
                    st.metric("Net Profit", f"${net:,.2f}", delta=delta,
                             delta_color="normal" if net >= 0 else "inverse")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Transactions table
            with st.container():
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("### 📋 Recent Transactions")
                st.dataframe(df[['tx_date', 'description', 'debit', 'credit', 'category', 'vendor']].head(20), 
                           use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            with st.container():
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.info("No committed transactions found for the selected period.")
                if st.button("🧠 Start Categorising", type="primary"):
                    handle_page_transition("Categorisation")
                st.markdown('</div>', unsafe_allow_html=True)
            
    except Exception as e:
        show_error_message(f"Unable to load dashboard data: {_format_exc(e)}")

def render_reports():
    st.markdown("## 📊 Reports")
    
    client_id = _require_active_client()
    if not client_id:
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Report Filters")
        col1, col2, col3 = st.columns(3)
        with col1:
            start_date = st.date_input("From Date", dt.date.today() - dt.timedelta(days=30))
        with col2:
            end_date = st.date_input("To Date", dt.date.today())
        with col3:
            bank_filter = st.selectbox("Bank", ["All Banks"] + [f"{b['id']} | {b['bank_name']}" for b in cached_banks(client_id)])
        
        # Report type
        report_type = st.radio("Report Type", ["P&L Summary", "Category Details", "Vendor Analysis"], horizontal=True)
        
        if st.button("Generate Report", type="primary"):
            with st.spinner("Generating report..."):
                time.sleep(1)
                
                try:
                    if report_type == "P&L Summary":
                        summary = crud.list_committed_pl_summary(
                            client_id, 
                            date_from=start_date, 
                            date_to=end_date
                        )
                        
                        if summary:
                            df_summary = pd.DataFrame(summary)
                            st.markdown("### 📈 Profit & Loss Summary")
                            st.dataframe(df_summary, use_container_width=True)
                        else:
                            st.info("No data available for the selected period.")
                    
                    elif report_type == "Category Details":
                        transactions = crud.list_committed_transactions(
                            client_id,
                            date_from=start_date,
                            date_to=end_date
                        )
                        
                        if transactions:
                            df_tx = pd.DataFrame(transactions)
                            st.markdown("### 📋 Transaction Details")
                            st.dataframe(df_tx, use_container_width=True)
                        else:
                            st.info("No transactions found.")
                    
                    else:
                        st.info("Vendor Analysis report coming soon!")
                
                except Exception as e:
                    show_error_message(f"Error generating report: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

# [Companies, Setup, Categorisation render functions remain exactly the same as before]
# Only changed the render_settings function to add data deletion

def render_settings():
    st.markdown("## ⚙️ Settings")
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Database Utilities")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Connection Test", "Initialize Database", "Schema Check", "Data Cleanup"])
        
        with tab1:
            st.markdown("#### Test Database Connection")
            if st.button("Test Connection", type="primary"):
                try:
                    from src.db import ping_db
                    if ping_db():
                        show_success_message("✅ Database connection successful!")
                    else:
                        show_error_message("❌ Database connection failed")
                except Exception as e:
                    show_error_message(f"❌ Connection error: {_format_exc(e)}")
        
        with tab2:
            st.markdown("#### Initialize Database Tables")
            st.warning("⚠️ This will create all necessary tables if they don't exist.")
            if st.button("Initialize Database", type="primary"):
                try:
                    init_db()
                    show_success_message("✅ Database initialized successfully!")
                    cache_data.clear()
                except Exception as e:
                    show_error_message(f"❌ Initialization failed: {_format_exc(e)}")
        
        with tab3:
            st.markdown("#### Verify Database Schema")
            st.info("Compares current database schema with expected schema.")
            if st.button("Run Schema Check", type="primary"):
                result = _run_schema_check()
                if "error" in result:
                    show_error_message(result["error"])
                elif result.get("issues"):
                    st.markdown("### ⚠️ Schema Issues Found")
                    issues_df = pd.DataFrame(result["issues"])
                    st.dataframe(issues_df, use_container_width=True)
                else:
                    show_success_message("✅ Schema matches perfectly!")
        
        with tab4:
            st.markdown("#### 🗑️ Cleanup/Delete Data")
            st.warning("⚠️ **DANGER ZONE** - This will permanently delete data!")
            
            clients = cached_clients()
            if not clients:
                st.info("No companies found to clean up.")
            else:
                # Client selection
                client_options = ["(Select a company)"] + [f"{c['id']} | {c['name']}" for c in clients]
                selected_client = st.selectbox("Select Company to Clean", client_options)
                
                if selected_client != "(Select a company)":
                    client_id = int(selected_client.split("|")[0].strip())
                    client_name = selected_client.split("|")[1].strip()
                    
                    st.markdown(f"### Cleaning: **{client_name}**")
                    
                    # Data type selection
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Select data to delete:**")
                        delete_drafts = st.checkbox("Draft Transactions", value=True, 
                                                  help="Uncategorised/unsaved transaction data")
                        delete_committed = st.checkbox("Committed Transactions", value=False,
                                                     help="Finalised/committed transaction history")
                        delete_banks = st.checkbox("Bank Accounts", value=False,
                                                 help="Bank account definitions")
                        delete_categories = st.checkbox("Categories", value=False,
                                                      help="Category definitions")
                    
                    with col2:
                        st.markdown("**Learning Data:**")
                        delete_vendors = st.checkbox("Vendor Memory", value=False,
                                                   help="Learned vendor→category mappings")
                        delete_keywords = st.checkbox("Keyword Models", value=False,
                                                    help="Learned keyword→category patterns")
                        delete_commits = st.checkbox("Commit History", value=False,
                                                   help="Commit records and accuracy metrics")
                        delete_client = st.checkbox("Company Itself", value=False,
                                                  help="Delete the entire company profile")
                    
                    # Warning message based on selection
                    selected_count = sum([
                        delete_drafts, delete_committed, delete_banks, 
                        delete_categories, delete_vendors, delete_keywords,
                        delete_commits, delete_client
                    ])
                    
                    if selected_count > 0:
                        st.error(f"⚠️ **WARNING:** You are about to delete {selected_count} type(s) of data!")
                        
                        # Summary of what will be deleted
                        delete_summary = []
                        if delete_drafts:
                            delete_summary.append("• Draft transactions (uncategorised data)")
                        if delete_committed:
                            delete_summary.append("• Committed transactions (finalised history)")
                        if delete_banks:
                            delete_summary.append("• Bank account definitions")
                        if delete_categories:
                            delete_summary.append("• Category definitions")
                        if delete_vendors:
                            delete_summary.append("• Vendor learning memory")
                        if delete_keywords:
                            delete_summary.append("• Keyword learning patterns")
                        if delete_commits:
                            delete_summary.append("• Commit history and accuracy metrics")
                        if delete_client:
                            delete_summary.append("• The entire company profile")
                        
                        if delete_summary:
                            st.markdown("**Will delete:**")
                            for item in delete_summary:
                                st.markdown(item)
                        
                        # Confirmation
                        confirmation = st.text_input("Type 'DELETE' to confirm", 
                                                   placeholder="Type DELETE to confirm")
                        
                        if st.button("🚨 Execute Data Deletion", type="primary", 
                                   disabled=(confirmation != "DELETE")):
                            if confirmation == "DELETE":
                                with st.spinner("Deleting data..."):
                                    try:
                                        result = crud.delete_client_data(
                                            client_id=client_id,
                                            delete_drafts=delete_drafts,
                                            delete_committed=delete_committed,
                                            delete_banks=delete_banks,
                                            delete_categories=delete_categories,
                                            delete_vendor_memory=delete_vendors,
                                            delete_keyword_model=delete_keywords,
                                            delete_commits=delete_commits,
                                            delete_client_itself=delete_client
                                        )
                                        
                                        if result.get("ok"):
                                            deleted = result.get("deleted", {})
                                            st.success("✅ Data deletion completed!")
                                            
                                            # Show deletion summary
                                            st.markdown("**Deletion Summary:**")
                                            for table, count in deleted.items():
                                                if count > 0:
                                                    st.markdown(f"• {table}: {count} records deleted")
                                            
                                            # Clear caches and session state if needed
                                            cache_data.clear()
                                            
                                            # If current active client was deleted, reset it
                                            if client_id == st.session_state.active_client_id:
                                                if delete_client:
                                                    st.session_state.active_client_id = None
                                                    st.session_state.active_client_name = None
                                                elif delete_banks:
                                                    st.session_state.bank_id = None
                                            
                                            st.rerun()
                                        else:
                                            show_error_message(f"❌ Deletion failed: {result.get('error', 'Unknown error')}")
                                    except Exception as e:
                                        show_error_message(f"❌ Deletion error: {_format_exc(e)}")
                            else:
                                st.warning("Please type 'DELETE' to confirm deletion")
                    else:
                        st.info("Select at least one data type to delete")
        
        st.markdown('</div>', unsafe_allow_html=True)

# [All other render functions remain EXACTLY THE SAME as in previous code]
# Companies, Setup, Categorisation functions are unchanged
# Only render_home and render_settings were modified

def render_companies():
    st.markdown("## 🏢 Companies")
    
    # Subpage navigation
    subpages = ["List", "Create", "Edit"]
    active_subpage = st.session_state.get("active_subpage", "List")
    
    cols = st.columns(len(subpages))
    for idx, subpage in enumerate(subpages):
        with cols[idx]:
            if st.button(
                subpage,
                use_container_width=True,
                type="primary" if subpage == active_subpage else "secondary",
                key=f"companies_{subpage}"
            ):
                st.session_state.active_subpage = subpage
                st.rerun()
    
    st.markdown("---")
    
    if active_subpage == "List":
        render_companies_list()
    elif active_subpage == "Create":
        render_companies_create()
    elif active_subpage == "Edit":
        render_companies_edit()

def render_companies_list():
    clients = cached_clients()
    
    if not clients:
        st.info("No companies found. Create your first company.")
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Company List")
        
        for client in clients:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.write(f"**{client['name']}**")
                st.caption(f"{client.get('industry', 'N/A')} • {client.get('country', 'N/A')}")
            with col2:
                status = "✅ Active" if client.get('is_active', True) else "❌ Inactive"
                st.write(status)
            with col3:
                if st.button("✏️ Edit", key=f"edit_{client['id']}"):
                    st.session_state.edit_client_id = client['id']
                    st.session_state.active_subpage = "Edit"
                    st.rerun()
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{client['id']}"):
                    if st.session_state.active_client_id == client['id']:
                        st.session_state.active_client_id = None
                    crud.set_client_active(client['id'], False)
                    cache_data.clear()
                    st.success(f"Company '{client['name']}' deactivated")
                    st.rerun()
            st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_companies_create():
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Create New Company")
        
        with st.form("create_company_form"):
            name = st.text_input("Company Name *", placeholder="Enter company name")
            industry = st.text_input("Industry", placeholder="e.g., Retail, Services, Manufacturing")
            country = st.text_input("Country", placeholder="e.g., USA, UK, UAE")
            description = st.text_area("Business Description", placeholder="Brief description of the business")
            
            submitted = st.form_submit_button("Create Company", type="primary")
            
            if submitted:
                if not name.strip():
                    show_error_message("Company name is required")
                else:
                    try:
                        client_id = crud.create_client(
                            name=name,
                            industry=industry,
                            country=country,
                            business_description=description
                        )
                        show_success_message(f"Company '{name}' created successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.active_subpage = "List"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error creating company: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_companies_edit():
    client_id = st.session_state.get("edit_client_id")
    if not client_id:
        st.warning("No company selected for editing. Go back to List and select a company.")
        if st.button("← Back to List"):
            st.session_state.active_subpage = "List"
            st.rerun()
        return
    
    clients = cached_clients()
    client = next((c for c in clients if c['id'] == client_id), None)
    
    if not client:
        show_error_message("Company not found")
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f"### Edit Company: {client['name']}")
        
        with st.form("edit_company_form"):
            name = st.text_input("Company Name *", value=client.get('name', ''))
            industry = st.text_input("Industry", value=client.get('industry', ''))
            country = st.text_input("Country", value=client.get('country', ''))
            description = st.text_area("Business Description", value=client.get('business_description', ''))
            is_active = st.checkbox("Active", value=client.get('is_active', True))
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.active_subpage = "List"
                    st.rerun()
            
            if submitted:
                if not name.strip():
                    show_error_message("Company name is required")
                else:
                    try:
                        crud.update_client(
                            client_id=client_id,
                            name=name,
                            industry=industry,
                            country=country,
                            business_description=description
                        )
                        crud.set_client_active(client_id, is_active)
                        
                        if st.session_state.active_client_id == client_id:
                            st.session_state.active_client_name = name
                        
                        show_success_message(f"Company '{name}' updated successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.active_subpage = "List"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error updating company: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_setup():
    active_subpage = st.session_state.get("active_subpage", "Banks")
    
    # Subpage navigation
    subpages = ["Banks", "Categories"]
    cols = st.columns(len(subpages))
    for idx, subpage in enumerate(subpages):
        with cols[idx]:
            if st.button(
                "🏦 Banks" if subpage == "Banks" else "🗂️ Categories",
                use_container_width=True,
                type="primary" if subpage == active_subpage else "secondary",
                key=f"setup_{subpage}"
            ):
                st.session_state.active_subpage = subpage
                st.rerun()
    
    st.markdown("---")
    
    if active_subpage == "Banks":
        render_setup_banks()
    else:
        render_setup_categories()

def render_setup_banks():
    client_id = _require_active_client()
    if not client_id:
        return
    
    # Mode selection
    mode = st.session_state.get("setup_banks_mode", "list")
    if mode == "list":
        render_banks_list(client_id)
    elif mode == "create":
        render_banks_create(client_id)
    elif mode == "edit":
        render_banks_edit(client_id)

def render_banks_list(client_id):
    banks = cached_banks(client_id)
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 🏦 Bank Accounts")
        with col2:
            if st.button("➕ Add Bank", type="primary", use_container_width=True):
                st.session_state.setup_banks_mode = "create"
                st.rerun()
        
        if not banks:
            st.info("No bank accounts found. Add your first bank account.")
        else:
            for bank in banks:
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.write(f"**{bank['bank_name']}**")
                    st.caption(f"{bank.get('account_type', 'Current')} • {bank.get('account_masked', 'N/A')}")
                with col2:
                    status = "✅ Active" if bank.get('is_active', True) else "❌ Inactive"
                    st.write(status)
                with col3:
                    if st.button("✏️ Edit", key=f"edit_bank_{bank['id']}"):
                        st.session_state.setup_bank_edit_id = bank['id']
                        st.session_state.setup_banks_mode = "edit"
                        st.rerun()
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_bank_{bank['id']}"):
                        if crud.bank_has_transactions(bank['id']):
                            show_warning_message("Cannot delete bank with existing transactions")
                        else:
                            crud.set_bank_active(bank['id'], False)
                            cache_data.clear()
                            show_success_message(f"Bank '{bank['bank_name']}' deactivated")
                            st.rerun()
                st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_banks_create(client_id):
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Add Bank Account")
        
        with st.form("create_bank_form"):
            bank_name = st.text_input("Bank Name *", placeholder="e.g., Chase Bank, HSBC")
            account_type = st.selectbox("Account Type *", 
                                       ["Current", "Credit Card", "Savings", "Investment", "Wallet"])
            account_masked = st.text_input("Account Number (masked)", 
                                          placeholder="e.g., ****1234")
            currency = st.text_input("Currency", value="USD", placeholder="e.g., USD, EUR, GBP")
            opening_balance = st.number_input("Opening Balance", value=0.0, step=100.0)
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Create Bank", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.setup_banks_mode = "list"
                    st.rerun()
            
            if submitted:
                if not bank_name.strip():
                    show_error_message("Bank name is required")
                else:
                    try:
                        bank_id = crud.add_bank(
                            client_id=client_id,
                            bank_name=bank_name,
                            account_type=account_type,
                            currency=currency,
                            masked=account_masked,
                            opening_balance=opening_balance
                        )
                        show_success_message(f"Bank '{bank_name}' added successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.setup_banks_mode = "list"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error adding bank: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_banks_edit(client_id):
    bank_id = st.session_state.get("setup_bank_edit_id")
    if not bank_id:
        show_warning_message("No bank selected for editing")
        st.session_state.setup_banks_mode = "list"
        st.rerun()
        return
    
    banks = cached_banks(client_id)
    bank = next((b for b in banks if b['id'] == bank_id), None)
    
    if not bank:
        show_error_message("Bank not found")
        st.session_state.setup_banks_mode = "list"
        st.rerun()
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f"### Edit Bank: {bank['bank_name']}")
        
        with st.form("edit_bank_form"):
            bank_name = st.text_input("Bank Name *", value=bank.get('bank_name', ''))
            account_type = st.selectbox("Account Type *", 
                                       ["Current", "Credit Card", "Savings", "Investment", "Wallet"],
                                       index=["Current", "Credit Card", "Savings", "Investment", "Wallet"]
                                       .index(bank.get('account_type', 'Current')))
            account_masked = st.text_input("Account Number (masked)", 
                                          value=bank.get('account_masked', ''))
            currency = st.text_input("Currency", value=bank.get('currency', 'USD'))
            opening_balance = st.number_input("Opening Balance", 
                                             value=float(bank.get('opening_balance', 0.0) or 0.0),
                                             step=100.0)
            is_active = st.checkbox("Active", value=bank.get('is_active', True))
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.setup_banks_mode = "list"
                    st.rerun()
            
            if submitted:
                if not bank_name.strip():
                    show_error_message("Bank name is required")
                else:
                    try:
                        crud.update_bank(
                            bank_id=bank_id,
                            bank_name=bank_name,
                            masked=account_masked,
                            account_type=account_type,
                            currency=currency,
                            opening_balance=opening_balance
                        )
                        crud.set_bank_active(bank_id, is_active)
                        
                        show_success_message(f"Bank '{bank_name}' updated successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.setup_banks_mode = "list"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error updating bank: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_setup_categories():
    client_id = _require_active_client()
    if not client_id:
        return
    
    # Mode selection
    mode = st.session_state.get("setup_categories_mode", "list")
    if mode == "list":
        render_categories_list(client_id)
    elif mode == "create":
        render_categories_create(client_id)
    elif mode == "edit":
        render_categories_edit(client_id)

def render_categories_list(client_id):
    categories = cached_categories(client_id)
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 🗂️ Categories")
        with col2:
            if st.button("➕ Add Category", type="primary", use_container_width=True):
                st.session_state.setup_categories_mode = "create"
                st.rerun()
        
        if not categories:
            st.info("No categories found. Add your first category.")
        else:
            # Group by type
            for cat_type in ["Income", "Expense", "Other"]:
                type_cats = [c for c in categories if c.get('type') == cat_type and c.get('is_active', True)]
                if type_cats:
                    st.markdown(f"**{cat_type} Categories**")
                    for cat in type_cats:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.write(f"• {cat['category_name']}")
                            st.caption(f"Nature: {cat.get('nature', 'Any')}")
                        with col2:
                            status = "✅ Active" if cat.get('is_active', True) else "❌ Inactive"
                            st.write(status)
                        with col3:
                            if st.button("✏️ Edit", key=f"edit_cat_{cat['id']}"):
                                st.session_state.setup_category_edit_id = cat['id']
                                st.session_state.setup_categories_mode = "edit"
                                st.rerun()
                    st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_categories_create(client_id):
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Add Category")
        
        with st.form("create_category_form"):
            name = st.text_input("Category Name *", placeholder="e.g., Sales, Rent, Office Supplies")
            cat_type = st.selectbox("Type *", ["Income", "Expense", "Other"])
            nature = st.selectbox("Nature", ["Any", "Dr", "Cr"], 
                                 help="Dr for Debit (usually expenses), Cr for Credit (usually income)")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Create Category", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.setup_categories_mode = "list"
                    st.rerun()
            
            if submitted:
                if not name.strip():
                    show_error_message("Category name is required")
                else:
                    try:
                        crud.add_category(
                            client_id=client_id,
                            name=name,
                            typ=cat_type,
                            nature=nature
                        )
                        show_success_message(f"Category '{name}' added successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.setup_categories_mode = "list"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error adding category: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_categories_edit(client_id):
    cat_id = st.session_state.get("setup_category_edit_id")
    if not cat_id:
        show_warning_message("No category selected for editing")
        st.session_state.setup_categories_mode = "list"
        st.rerun()
        return
    
    categories = cached_categories(client_id)
    category = next((c for c in categories if c['id'] == cat_id), None)
    
    if not category:
        show_error_message("Category not found")
        st.session_state.setup_categories_mode = "list"
        st.rerun()
        return
    
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f"### Edit Category: {category['category_name']}")
        
        with st.form("edit_category_form"):
            name = st.text_input("Category Name *", value=category.get('category_name', ''))
            cat_type = st.selectbox("Type *", ["Income", "Expense", "Other"],
                                   index=["Income", "Expense", "Other"]
                                   .index(category.get('type', 'Expense')))
            nature = st.selectbox("Nature", ["Any", "Dr", "Cr"],
                                 index=["Any", "Dr", "Cr"]
                                 .index(category.get('nature', 'Any')))
            is_active = st.checkbox("Active", value=category.get('is_active', True))
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.setup_categories_mode = "list"
                    st.rerun()
            
            if submitted:
                if not name.strip():
                    show_error_message("Category name is required")
                else:
                    try:
                        crud.update_category(
                            cat_id=cat_id,
                            name=name,
                            typ=cat_type,
                            nature=nature
                        )
                        crud.set_category_active(cat_id, is_active)
                        
                        show_success_message(f"Category '{name}' updated successfully!")
                        cache_data.clear()
                        time.sleep(1)
                        st.session_state.setup_categories_mode = "list"
                        st.rerun()
                    except Exception as e:
                        show_error_message(f"Error updating category: {_format_exc(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_categorisation():
    st.markdown("## 🧠 Categorisation")
    
    client_id = _require_active_client()
    if not client_id:
        return

    try:
        banks_active = crud.list_banks(client_id, include_inactive=False)
    except Exception as e:
        show_error_message(f"Unable to load active banks. {_format_exc(e)}")
        return

    if not banks_active:
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.info("Add at least 1 active bank first.")
            if st.button("🏦 Add Bank", type="primary"):
                handle_page_transition("Setup", "Banks")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # --- Step 1: Bank Selection ---
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 1. Select Bank")
        bank_options = []
        for b in banks_active:
            bank_options.append(f"{b['id']} | {b['bank_name']} ({b['account_type']})")
        
        selected_index = 0
        if st.session_state.bank_id:
            for i, opt in enumerate(bank_options):
                if opt.startswith(f"{st.session_state.bank_id} |"):
                    selected_index = i
                    break
        
        bank_pick = st.selectbox("Select Bank", bank_options, index=selected_index, label_visibility="collapsed")
        bank_id = int(bank_pick.split("|")[0].strip())
        st.session_state.bank_id = bank_id
        bank_obj = [b for b in banks_active if int(b["id"]) == bank_id][0]
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Step 2: Period Selection ---
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 2. Period Selection")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        
        with col1:
            year_range = list(range(2020, 2031))
            year = st.selectbox("Year", year_range, index=year_range.index(st.session_state.year))
            st.session_state.year = year
        
        with col2:
            month = st.selectbox("Month", month_names, index=month_names.index(st.session_state.month))
            st.session_state.month = month
        
        with col3:
            period = f"{year}-{month_names.index(month)+1:02d}"
            st.text_input("Period", value=period, disabled=True)
            st.session_state.period = period
        
        with col4:
            month_idx = month_names.index(month) + 1
            last_day = calendar.monthrange(year, month_idx)[1]
            
            try:
                if st.session_state.date_from is None:
                    st.session_state.date_from = dt.date(year, month_idx, 1)
                if st.session_state.date_to is None:
                    st.session_state.date_to = dt.date(year, month_idx, last_day)
                
                default_range = (
                    st.session_state.date_from,
                    st.session_state.date_to,
                )
                dr = st.date_input("Date Range", value=default_range, label_visibility="collapsed")
                
                if isinstance(dr, tuple) and len(dr) == 2:
                    date_from, date_to = dr
                else:
                    date_from = dr
                    date_to = dr
                
                st.session_state.date_from = date_from
                st.session_state.date_to = date_to
                
            except Exception as e:
                st.session_state.date_from = dt.date(year, month_idx, 1)
                st.session_state.date_to = dt.date(year, month_idx, last_day)
                date_from = st.session_state.date_from
                date_to = st.session_state.date_to
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Get data summaries ---
    draft_summary = None
    commit_summary = None
    try:
        draft_summary = crud.get_draft_summary(client_id, bank_id, period)
        commit_summary = crud.get_commit_summary(client_id, bank_id, period)
    except Exception as e:
        show_error_message(f"Error loading summaries: {_format_exc(e)}")

    # --- Step 3: Upload Section (only if no data exists) ---
    if not draft_summary and not commit_summary:
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown("### 3. Upload Statement")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                stmt_template = pd.DataFrame([
                    {"Date": "25/09/2025", "Description": "POS Purchase Example", "Dr": 100.00, "Cr": 0.00, "Closing": ""}
                ])
                buf = io.StringIO()
                stmt_template.to_csv(buf, index=False)
                st.download_button(
                    "📥 Download Template",
                    data=buf.getvalue(),
                    file_name="statement_template.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                up_stmt = st.file_uploader("Upload CSV statement", type=["csv"], key="stmt_csv", label_visibility="collapsed")
                
                if up_stmt is not None:
                    try:
                        df_raw = pd.read_csv(up_stmt)
                        st.session_state.df_raw = df_raw
                        st.session_state.file_uploaded = True
                        show_success_message(f"✅ Loaded {len(df_raw)} rows")
                    except Exception as e:
                        show_error_message(f"❌ Upload failed: {_format_exc(e)}")
                else:
                    df_raw = st.session_state.df_raw

            # Column Mapping
            if df_raw is not None and len(df_raw) > 0:
                st.markdown("#### Column Mapping")
                
                cols = ["(blank)"] + list(df_raw.columns)
                map_cols = st.columns(5)
                
                with map_cols[0]:
                    map_date = st.selectbox("Date *", cols, index=cols.index("Date") if "Date" in cols else 0)
                with map_cols[1]:
                    map_desc = st.selectbox("Description *", cols, index=cols.index("Description") if "Description" in cols else 0)
                with map_cols[2]:
                    map_dr = st.selectbox("Debit (Dr)", cols, index=cols.index("Dr") if "Dr" in cols else 0)
                with map_cols[3]:
                    map_cr = st.selectbox("Credit (Cr)", cols, index=cols.index("Cr") if "Cr" in cols else 0)
                with map_cols[4]:
                    map_bal = st.selectbox("Closing Balance", cols, index=cols.index("Closing") if "Closing" in cols else 0)
                
                # Date parsing function
                def _to_date(x):
                    if pd.isna(x):
                        return None
                    try:
                        if isinstance(x, str):
                            x_str = str(x).strip()
                            formats_to_try = [
                                "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d",
                                "%d %b %Y", "%d %B %Y"
                            ]
                            for fmt in formats_to_try:
                                try:
                                    return dt.datetime.strptime(x_str, fmt).date()
                                except:
                                    continue
                            try:
                                return pd.to_datetime(x_str, dayfirst=True).date()
                            except:
                                return None
                        if isinstance(x, (dt.datetime, dt.date)):
                            return x.date() if isinstance(x, dt.datetime) else x
                        return None
                    except Exception:
                        return None
                
                # Process rows button
                if st.button("Apply Mapping", type="primary", key="apply_mapping", use_container_width=True):
                    standardized_rows = []
                    dropped_missing_date = 0
                    dropped_missing_desc = 0
                    date_errors = []
                    
                    for idx, r in df_raw.iterrows():
                        d = _to_date(r[map_date]) if map_date != "(blank)" else None
                        ds = str(r[map_desc]).strip() if map_desc != "(blank)" else ""
                        
                        if not d:
                            if ds:
                                d = dt.date(year, month_names.index(month) + 1, 1)
                                dropped_missing_date += 1
                            else:
                                dropped_missing_desc += 1
                                continue
                        
                        if not ds:
                            dropped_missing_desc += 1
                            continue
                        
                        try:
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
                        except Exception as e:
                            date_errors.append(f"Row {idx+1}: {str(e)}")
                            continue
                    
                    st.session_state.standardized_rows = standardized_rows
                    st.session_state.column_mapping = {
                        "date": map_date,
                        "description": map_desc,
                        "debit": map_dr,
                        "credit": map_cr,
                        "balance": map_bal
                    }
                    
                    show_success_message(f"✅ Mapped {len(standardized_rows)} rows")
                    
                    if date_errors:
                        show_warning_message(f"⚠️ {len(date_errors)} rows had date parsing issues")
                    
                    st.info(f"""
                    **Mapping Summary:**
                    - Original rows: {len(df_raw)}
                    - Successfully mapped: {len(standardized_rows)}
                    - Rows with missing/invalid date (used period default): {dropped_missing_date}
                    - Rows dropped (missing description): {dropped_missing_desc}
                    """)
                    
                    st.session_state.categorisation_selected_item = None
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

    # --- Step 4: Saved Items Display ---
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 4. Saved Items")
        
        saved_items = []
        
        if draft_summary:
            suggested_count = int(draft_summary.get("suggested_count") or 0)
            final_count = int(draft_summary.get("final_count") or 0)
            total_rows = int(draft_summary.get("row_count") or 0)
            
            status_label = ""
            type_label = ""
            badge_class = ""
            
            if suggested_count == 0:
                status_label = "Draft Saved"
                type_label = "Draft"
                badge_class = "status-draft"
            elif final_count < total_rows:
                status_label = f"Categorised ({final_count}/{total_rows})"
                type_label = "Draft Categorised"
                badge_class = "status-categorised"
            else:
                status_label = "Ready to Commit"
                type_label = "Draft Finalised"
                badge_class = "status-committed"
            
            saved_items.append({
                "id": f"draft_{client_id}_{bank_id}_{period}",
                "type": type_label,
                "status": status_label,
                "badge_class": badge_class,
                "row_count": total_rows,
                "suggested_rows": suggested_count,
                "final_rows": final_count,
                "min_date": draft_summary.get("min_date"),
                "max_date": draft_summary.get("max_date"),
                "last_updated": draft_summary.get("last_saved") or "N/A",
            })
        
        if commit_summary:
            saved_items.append({
                "id": f"committed_{commit_summary.get('commit_id')}",
                "type": "Committed",
                "status": "Committed",
                "badge_class": "status-committed",
                "row_count": int(commit_summary.get("row_count") or 0),
                "min_date": commit_summary.get("min_date"),
                "max_date": commit_summary.get("max_date"),
                "last_updated": commit_summary.get("committed_at") or "N/A",
            })
        
        # Display saved items
        if saved_items:
            selected_item_id = st.session_state.categorisation_selected_item
            
            for item in saved_items:
                is_selected = (selected_item_id == item["id"])
                
                col1, col2, col3 = st.columns([2, 4, 2])
                with col1:
                    st.write(f"**{item['type']}**")
                    st.write(f"Rows: {item['row_count']}")
                with col2:
                    st.markdown(f'<span class="status-badge {item["badge_class"]}">{item["status"]}</span>', unsafe_allow_html=True)
                    if item.get("min_date") and item.get("max_date"):
                        st.caption(f"{item['min_date']} to {item['max_date']}")
                with col3:
                    if is_selected:
                        if st.button("✖ Deselect", key=f"deselect_{item['id']}", type="secondary", use_container_width=True):
                            st.session_state.categorisation_selected_item = None
                            st.rerun()
                    else:
                        if st.button("👉 Select", key=f"select_{item['id']}", type="primary", use_container_width=True):
                            st.session_state.categorisation_selected_item = item["id"]
                            st.rerun()
                
                if not is_selected:
                    st.markdown("---")
        else:
            st.info("No saved items yet for this bank + period.")
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Check if item is selected ---
    selected_item_id = st.session_state.categorisation_selected_item
    has_selected_item = bool(selected_item_id)
    
    # --- Step 5: Main View Table ---
    if has_selected_item:
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown("### 5. Transaction Review")
            
            if selected_item_id and selected_item_id.startswith("draft_"):
                try:
                    draft_rows = crud.load_draft_rows(client_id, bank_id, period)
                    if draft_rows:
                        df_d = pd.DataFrame(draft_rows)
                        
                        categories = cached_categories(client_id)
                        category_names = []
                        
                        for c in categories:
                            if c.get("is_active", True):
                                cat_name = c.get("category_name", "")
                                category_names.append(cat_name)
                        
                        edited_df = st.data_editor(
                            df_d,
                            column_config={
                                "id": st.column_config.NumberColumn("ID", disabled=True),
                                "tx_date": st.column_config.DateColumn("Date", disabled=True),
                                "description": st.column_config.TextColumn("Description", disabled=True),
                                "debit": st.column_config.NumberColumn("Debit", format="%.2f", disabled=True),
                                "credit": st.column_config.NumberColumn("Credit", format="%.2f", disabled=True),
                                "balance": st.column_config.NumberColumn("Balance", format="%.2f", disabled=True),
                                "suggested_category": st.column_config.TextColumn("AI Category", disabled=True),
                                "suggested_vendor": st.column_config.TextColumn("AI Vendor", disabled=True),
                                "confidence": st.column_config.NumberColumn("Confidence", format="%.1f%%", disabled=True),
                                "final_category": st.column_config.SelectboxColumn(
                                    "Final Category",
                                    options=category_names,
                                    required=False
                                ),
                                "final_vendor": st.column_config.TextColumn(
                                    "Final Vendor",
                                    required=False
                                ),
                            },
                            column_order=[
                                "tx_date", "description", "debit", "credit", 
                                "suggested_category", "suggested_vendor", "confidence",
                                "final_category", "final_vendor"
                            ],
                            use_container_width=True,
                            hide_index=True,
                            key="draft_editor"
                        )
                        
                        if "draft_editor" in st.session_state:
                            edited_data = st.session_state.draft_editor.get("edited_rows", {})
                            if edited_data:
                                for row_idx in edited_data.keys():
                                    st.session_state.last_edited_row = int(row_idx)
                                    st.session_state.last_edit_time = time.time()
                        
                    else:
                        st.info("No draft rows found.")
                except Exception as e:
                    show_error_message(f"Unable to load draft rows: {_format_exc(e)}")
            
            elif selected_item_id and selected_item_id.startswith("committed"):
                try:
                    committed_rows = crud.load_committed_rows(client_id, bank_id, period)
                    if committed_rows:
                        df_c = pd.DataFrame(committed_rows)
                        st.dataframe(df_c, use_container_width=True, hide_index=True)
                    else:
                        st.info("No committed rows found.")
                except Exception as e:
                    show_error_message(f"Unable to load committed rows: {_format_exc(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Step 6: Progress Summary ---
    if has_selected_item and draft_summary and selected_item_id.startswith("draft_"):
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown("### 6. Progress Summary")
            
            total_rows = int(draft_summary.get("row_count") or 0)
            suggested_count = 0
            if draft_summary:
                suggested_count = int(draft_summary.get("suggested_count") or 0)
            final_count = int(draft_summary.get("final_count") or 0)
            pending_rows = total_rows - final_count
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Rows", total_rows)
            
            with col2:
                suggested_pct = (suggested_count / total_rows * 100) if total_rows > 0 else 0
                st.metric("AI Suggested", suggested_count, f"{suggested_pct:.1f}%")
            
            with col3:
                final_pct = (final_count / total_rows * 100) if total_rows > 0 else 0
                st.metric("User Finalised", final_count, f"{final_pct:.1f}%")
            
            with col4:
                pending_pct = (pending_rows / total_rows * 100) if total_rows > 0 else 0
                delta_color = "inverse" if pending_rows > 0 else "normal"
                st.metric("Pending Review", pending_rows, f"{pending_pct:.1f}%", delta_color=delta_color)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Step 7: Action Buttons ---
    if has_selected_item:
        with st.container():
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown("### 7. Actions")
            
            has_draft = bool(draft_summary)
            has_commit = bool(commit_summary)
            
            if selected_item_id.startswith("draft_"):
                suggested_count = 0
                if draft_summary:
                    suggested_count = int(draft_summary.get("suggested_count") or 0)
                final_count = int(draft_summary.get("final_count") or 0)
                total_rows = int(draft_summary.get("row_count") or 0)
                
                action_cols = st.columns(3)
                
                with action_cols[0]:
                    if suggested_count == 0:
                        if st.button("🤖 Suggest Categories", type="primary", use_container_width=True, 
                                   disabled=st.session_state.processing_suggestions):
                            if not st.session_state.processing_suggestions:
                                st.session_state.processing_suggestions = True
                                
                                with st.spinner("😺 Cat is analyzing transactions..."):
                                    try:
                                        n = crud.process_suggestions(client_id, bank_id, period, 
                                                                    bank_account_type=bank_obj.get("account_type"))
                                        
                                        show_success_message(f"✅ Suggested {n} categories!")
                                        
                                        cache_data.clear()
                                        st.session_state.processing_suggestions = False
                                        st.rerun()
                                    except Exception as e:
                                        show_error_message(f"❌ Suggestion failed: {_format_exc(e)}")
                                        st.session_state.processing_suggestions = False
                    else:
                        if st.button("🔄 Re-suggest Categories", type="secondary", use_container_width=True,
                                   disabled=st.session_state.processing_suggestions):
                            show_info_message("Already suggested. Edit categories in the table above.")
                
                with action_cols[1]:
                    if st.button("💾 Save Draft Changes", type="primary", use_container_width=True, key="save_draft_changes"):
                        if "draft_editor" in st.session_state and st.session_state.draft_editor:
                            edited_data = st.session_state.draft_editor.get("edited_rows", {})
                            
                            if edited_data:
                                with st.spinner("😺 Cat is saving your changes..."):
                                    rows_to_save = []
                                    for row_idx, changes in edited_data.items():
                                        row_idx = int(row_idx)
                                        if row_idx < len(draft_rows):
                                            original_row = draft_rows[row_idx]
                                            final_cat = changes.get("final_category")
                                            final_ven = changes.get("final_vendor")
                                            
                                            if final_cat is None or final_cat == "":
                                                final_cat = original_row.get("final_category", "")
                                            if final_ven is None or final_ven == "":
                                                final_ven = original_row.get("final_vendor", "")
                                            
                                            rows_to_save.append({
                                                "id": original_row["id"],
                                                "final_category": final_cat,
                                                "final_vendor": final_ven
                                            })
                                    
                                    if rows_to_save:
                                        try:
                                            updated = crud.save_review_changes(rows_to_save)
                                            show_success_message(f"✅ Saved {updated} changes!")
                                            cache_data.clear()
                                            st.rerun()
                                        except Exception as e:
                                            show_error_message(f"❌ Save failed: {_format_exc(e)}")
                                    else:
                                        show_warning_message("No valid changes to save")
                            else:
                                show_info_message("No changes detected to save. Make edits in the table first.")
                        else:
                            show_info_message("Make changes in the table above first, then save.")
                
                with action_cols[2]:
                    if final_count >= total_rows and total_rows > 0:
                        # COMMIT SECTION
                        if st.button("🔒 Commit Final Now", type="primary", use_container_width=True,
                                   disabled=st.session_state.processing_commit, key="commit_final_button"):
                            
                            if not st.session_state.processing_commit:
                                st.session_state.processing_commit = True
                                
                                with st.spinner("😺 Cat is locking transactions..."):
                                    try:
                                        result = crud.commit_period(client_id, bank_id, period, 
                                                                  committed_by="Accountant")
                                        
                                        if result.get("ok"):
                                            show_success_message(f"✅ Successfully committed {result.get('rows', 0)} rows!")
                                            st.balloons()
                                            
                                            # Clear states
                                            st.session_state.categorisation_selected_item = None
                                            st.session_state.standardized_rows = []
                                            st.session_state.df_raw = None
                                            st.session_state.processing_commit = False
                                            cache_data.clear()
                                            
                                            # Wait and refresh
                                            time.sleep(2)
                                            st.rerun()
                                        else:
                                            show_error_message(f"❌ Commit failed: {result.get('msg', 'Unknown error')}")
                                            st.session_state.processing_commit = False
                                    except Exception as e:
                                        show_error_message(f"❌ Commit error: {_format_exc(e)}")
                                        st.session_state.processing_commit = False
                    else:
                        pending = total_rows - final_count
                        st.info(f"📝 **Finalise {pending} more rows to commit**")
            
            elif selected_item_id.startswith("committed"):
                st.success("✅ **Committed & Locked** - This data is now available in Reports")
                
                commit_info = crud.list_commit_metrics(
                    client_id=client_id,
                    bank_id=bank_id,
                    period=period,
                    date_from=date_from,
                    date_to=date_to
                )
                
                if commit_info:
                    info = commit_info[0]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Rows Committed", info.get("rows_committed", 0))
                    with col2:
                        st.metric("Accuracy", f"{info.get('accuracy', 0)*100:.1f}%")
                    with col3:
                        st.metric("Committed By", info.get("committed_by", "N/A"))
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Show special message for upload state ---
    elif not has_selected_item and not draft_summary and not commit_summary:
        if st.session_state.standardized_rows and len(st.session_state.standardized_rows) > 0:
            with st.container():
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("### 5. Mapped Data Preview")
                df_uploaded = pd.DataFrame(st.session_state.standardized_rows)
                st.info(f"📄 **Mapped Data ({len(df_uploaded)} rows)** - Ready to save as draft")
                st.dataframe(df_uploaded, use_container_width=True, hide_index=True)
                
                st.markdown("### 6. Save Draft")
                if st.button("💾 Save Draft", type="primary", use_container_width=True):
                    with st.spinner("😺 Cat is saving draft..."):
                        try:
                            n = crud.insert_draft_rows(client_id, bank_id, period, 
                                                      st.session_state.standardized_rows, replace=True)
                            show_success_message(f"✅ Draft saved ({n} rows)!")
                            
                            st.session_state.standardized_rows = []
                            st.session_state.df_raw = None
                            cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            show_error_message(f"❌ Save failed: {_format_exc(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
                

# ---------------- Main Page Router ----------------
def main():
    page = st.session_state.active_page
    
    st.markdown('<div class="fade-in-content">', unsafe_allow_html=True)
    
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
        # Call the categorisation function (not shown here for brevity)
        render_categorisation()
    elif page == "Settings":
        render_settings()
    else:
        render_home()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Highlight recently edited row (if any)
    if (st.session_state.last_edited_row is not None and 
        time.time() - st.session_state.last_edit_time < 1.5):
        st.markdown(f"""
        <script>
        setTimeout(function() {{
            var rows = document.querySelectorAll('[data-testid="stDataFrame"] tbody tr');
            if (rows.length > {st.session_state.last_edited_row}) {{
                rows[{st.session_state.last_edited_row}].classList.add('highlight-row');
            }}
        }}, 100);
        </script>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
