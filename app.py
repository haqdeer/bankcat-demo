# app.py - PROFESSIONAL UI/UX IMPROVEMENTS
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

# ---------------- PROFESSIONAL UI/UX STYLING ----------------
st.markdown(
    """
<style>
/* ========== PROFESSIONAL COLOR SYSTEM ========== */
:root {
    --primary-50: #f0fdf4;
    --primary-100: #dcfce7;
    --primary-200: #bbf7d0;
    --primary-300: #86efac;
    --primary-400: #4ade80;
    --primary-500: #10b981;  /* Main brand green */
    --primary-600: #059669;
    --primary-700: #047857;
    --primary-800: #065f46;
    --primary-900: #064e3b;
    
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
    --info: #3b82f6;
    
    --shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

/* ========== PROFESSIONAL TYPOGRAPHY ========== */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

h1 {
    font-size: 2.25rem !important;  /* 36px */
    font-weight: 700 !important;
    line-height: 1.2 !important;
    color: var(--gray-900) !important;
    margin-bottom: 1.5rem !important;
}

h2 {
    font-size: 1.875rem !important;  /* 30px */
    font-weight: 600 !important;
    line-height: 1.25 !important;
    color: var(--gray-900) !important;
    margin-bottom: 1.25rem !important;
}

h3 {
    font-size: 1.5rem !important;  /* 24px */
    font-weight: 600 !important;
    line-height: 1.3 !important;
    color: var(--gray-800) !important;
    margin-bottom: 1rem !important;
}

.body-large {
    font-size: 1.125rem !important;  /* 18px */
    line-height: 1.6 !important;
    color: var(--gray-700) !important;
}

.body {
    font-size: 1rem !important;  /* 16px */
    line-height: 1.5 !important;
    color: var(--gray-700) !important;
}

.caption {
    font-size: 0.875rem !important;  /* 14px */
    line-height: 1.4 !important;
    color: var(--gray-500) !important;
}

.label {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--gray-700) !important;
    margin-bottom: 0.375rem !important;
    display: block !important;
}

/* ========== GREEN HEADER ========== */
.css-1d391kg {
    background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%) !important;
    border-bottom: none !important;
    box-shadow: var(--shadow-sm) !important;
}

.css-1v0mbdj, .css-1v3fvcr, .css-1oe5cao {
    color: white !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
}

/* ========== FIXED HEADER & APP LAYOUT ========== */
.stApp {
    background-color: var(--gray-50) !important;
    padding-top: 0 !important;
}

/* ========== PROFESSIONAL BUTTONS ========== */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    line-height: 1.25 !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    padding: 0.625rem 1.25rem !important;
    border: 1px solid transparent !important;
    position: relative !important;
    overflow: hidden !important;
}

/* Primary Buttons - Enhanced */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.25) !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-700) 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3) !important;
}

.stButton > button[kind="primary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(16, 185, 129, 0.25) !important;
}

/* Secondary Buttons - Enhanced */
.stButton > button[kind="secondary"] {
    background: white !important;
    color: var(--gray-700) !important;
    border: 1px solid var(--gray-300) !important;
    box-shadow: var(--shadow-xs) !important;
}

.stButton > button[kind="secondary"]:hover {
    background: var(--gray-50) !important;
    border-color: var(--gray-400) !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* Button Focus States */
.stButton > button:focus {
    outline: 2px solid var(--primary-500) !important;
    outline-offset: 2px !important;
}

/* ========== PROFESSIONAL CARD STYLING ========== */
.professional-card {
    background: white !important;
    border-radius: 12px !important;
    padding: 2rem !important;
    margin-bottom: 1.5rem !important;
    border: 1px solid var(--gray-200) !important;
    box-shadow: var(--shadow-sm) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.professional-card:hover {
    box-shadow: var(--shadow-lg) !important;
    transform: translateY(-2px) !important;
    border-color: var(--gray-300) !important;
}

.card-header {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    margin-bottom: 1.5rem !important;
    padding-bottom: 1rem !important;
    border-bottom: 2px solid var(--gray-100) !important;
}

/* ========== ENHANCED FORM ELEMENTS ========== */
.stSelectbox > div, .stTextInput > div, .stDateInput > div, .stTextArea > div {
    border-radius: 8px !important;
    border: 1px solid var(--gray-300) !important;
    transition: all 0.2s ease !important;
    background: white !important;
}

.stSelectbox > div:focus-within, 
.stTextInput > div:focus-within, 
.stDateInput > div:focus-within,
.stTextArea > div:focus-within {
    border-color: var(--primary-500) !important;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1) !important;
    transform: translateY(-1px) !important;
}

.stSelectbox > div:hover, 
.stTextInput > div:hover, 
.stDateInput > div:hover,
.stTextArea > div:hover {
    border-color: var(--gray-400) !important;
}

/* Enhanced Labels */
.css-1qg05tj {
    font-weight: 500 !important;
    color: var(--gray-700) !important;
    margin-bottom: 0.5rem !important;
}

/* ========== PROFESSIONAL TABLES ========== */
.stDataFrame {
    border-radius: 8px !important;
    border: 1px solid var(--gray-200) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow-sm) !important;
}

.stDataFrame table {
    border-collapse: separate !important;
    border-spacing: 0 !important;
}

.stDataFrame thead tr {
    background: var(--gray-50) !important;
}

.stDataFrame th {
    font-weight: 600 !important;
    color: var(--gray-700) !important;
    padding: 0.875rem 1rem !important;
    border-bottom: 2px solid var(--gray-200) !important;
}

.stDataFrame td {
    padding: 0.75rem 1rem !important;
    border-bottom: 1px solid var(--gray-100) !important;
}

.stDataFrame tbody tr:hover {
    background: var(--gray-50) !important;
}

/* Zebra striping for better readability */
.stDataFrame tbody tr:nth-child(even) {
    background: var(--gray-50) !important;
}

/* ========== ENHANCED STATUS BADGES ========== */
.status-badge {
    padding: 0.375rem 0.875rem !important;
    border-radius: 20px !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.25rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    border: 1px solid transparent !important;
}

.status-badge::before {
    content: '' !important;
    display: inline-block !important;
    width: 6px !important;
    height: 6px !important;
    border-radius: 50% !important;
    margin-right: 4px !important;
}

.status-draft {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
    color: #1e40af !important;
    border-color: #93c5fd !important;
}

.status-draft::before {
    background: #3b82f6 !important;
}

.status-categorised {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
    color: #92400e !important;
    border-color: #fcd34d !important;
}

.status-categorised::before {
    background: #f59e0b !important;
}

.status-committed {
    background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%) !important;
    color: #065f46 !important;
    border-color: #86efac !important;
}

.status-committed::before {
    background: #10b981 !important;
}

/* ========== PROFESSIONAL ALERTS ========== */
.stAlert {
    border-radius: 8px !important;
    border: 1px solid transparent !important;
    border-left-width: 4px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: var(--shadow-sm) !important;
}

.stAlert[data-baseweb="notification"] {
    border-left-color: var(--info) !important;
}

.stAlert[data-baseweb="notification"].st-emotion-cache-1c7j2y7 {
    border-left-color: var(--success) !important;
}

.stAlert[data-baseweb="notification"].st-emotion-cache-1vzeuhh {
    border-left-color: var(--error) !important;
}

.stAlert[data-baseweb="notification"].st-emotion-cache-1yf0qjw {
    border-left-color: var(--warning) !important;
}

/* ========== PROFESSIONAL SIDEBAR ========== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%) !important;
    border-right: 1px solid var(--gray-200) !important;
    box-shadow: var(--shadow-sm) !important;
}

.sidebar-section {
    color: var(--gray-500) !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.75rem !important;
    padding-left: 1rem !important;
}

/* Sidebar logo */
.sidebar-logo {
    padding: 1.5rem 1rem 1rem !important;
    text-align: center !important;
    border-bottom: 1px solid var(--gray-200) !important;
    margin-bottom: 1rem !important;
}

/* ========== METRIC CARDS ========== */
.metric-card {
    background: white !important;
    border-radius: 8px !important;
    padding: 1.25rem !important;
    border: 1px solid var(--gray-200) !important;
    text-align: center !important;
    box-shadow: var(--shadow-xs) !important;
    transition: all 0.2s ease !important;
}

.metric-card:hover {
    transform: translateY(-2px) !important;
    box-shadow: var(--shadow-md) !important;
    border-color: var(--primary-300) !important;
}

.metric-value {
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: var(--gray-900) !important;
    line-height: 1.2 !important;
}

.metric-label {
    font-size: 0.875rem !important;
    color: var(--gray-600) !important;
    margin-top: 0.25rem !important;
    font-weight: 500 !important;
}

/* ========== PROFESSIONAL DIVIDERS ========== */
.section-divider {
    border-top: 1px solid var(--gray-200) !important;
    margin: 2rem 0 !important;
}

.green-divider {
    border-top: 2px solid var(--primary-300) !important;
    margin: 2rem 0 !important;
}

/* ========== LOADING & SKELETON STATES ========== */
.skeleton {
    background: linear-gradient(90deg, 
                var(--gray-100) 25%, 
                var(--gray-200) 50%, 
                var(--gray-100) 75%) !important;
    background-size: 200% 100% !important;
    animation: skeleton-loading 1.5s infinite !important;
    border-radius: 6px !important;
}

@keyframes skeleton-loading {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Professional spinner */
.stSpinner > div {
    border-top-color: var(--primary-500) !important;
}

/* ========== PAGE TRANSITIONS ========== */
.fade-in-content {
    animation: fadeIn 0.3s ease-in-out !important;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* ========== HIGHLIGHT ANIMATIONS ========== */
@keyframes highlightRow {
    0% { 
        background-color: rgba(124, 255, 178, 0.4) !important;
        box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.3) !important;
    }
    70% { 
        background-color: rgba(124, 255, 178, 0.1) !important;
        box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.1) !important;
    }
    100% { 
        background-color: transparent !important;
        box-shadow: none !important;
    }
}

.highlight-row {
    animation: highlightRow 2s ease-out !important;
}

/* ========== PAGE TITLE WITH ACCENT ========== */
.page-title {
    color: var(--gray-900) !important;
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    margin-bottom: 1.5rem !important;
    padding-bottom: 1rem !important;
    border-bottom: 3px solid var(--primary-500) !important;
    position: relative !important;
}

.page-title::after {
    content: '' !important;
    position: absolute !important;
    bottom: -3px !important;
    left: 0 !important;
    width: 100px !important;
    height: 3px !important;
    background: linear-gradient(90deg, var(--primary-500), var(--primary-300)) !important;
    border-radius: 0 0 3px 3px !important;
}

/* ========== EMPTY STATES ========== */
.empty-state {
    text-align: center !important;
    padding: 3rem 2rem !important;
    background: var(--gray-50) !important;
    border-radius: 12px !important;
    border: 2px dashed var(--gray-300) !important;
}

.empty-state-icon {
    font-size: 3rem !important;
    color: var(--gray-400) !important;
    margin-bottom: 1rem !important;
}

/* ========== TABS ENHANCEMENT ========== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem !important;
    background: var(--gray-100) !important;
    padding: 0.5rem !important;
    border-radius: 8px !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease !important;
}

.stTabs [data-baseweb="tab"]:hover {
    background: var(--gray-200) !important;
}

.stTabs [aria-selected="true"] {
    background: white !important;
    color: var(--primary-600) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ========== TOOLTIPS & HELP TEXT ========== */
.stTooltip {
    background: var(--gray-800) !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 0.5rem 0.75rem !important;
    font-size: 0.75rem !important;
    box-shadow: var(--shadow-lg) !important;
}

/* ========== MOBILE RESPONSIVENESS ========== */
@media (max-width: 768px) {
    .professional-card {
        padding: 1.25rem !important;
        margin-bottom: 1rem !important;
    }
    
    .page-title {
        font-size: 1.75rem !important;
        margin-bottom: 1.25rem !important;
    }
    
    .stButton > button {
        width: 100% !important;
        margin-bottom: 0.5rem !important;
    }
    
    section[data-testid="stSidebar"] {
        min-width: 250px !important;
    }
}

/* ========== CUSTOM SCROLLBAR ========== */
::-webkit-scrollbar {
    width: 8px !important;
    height: 8px !important;
}

::-webkit-scrollbar-track {
    background: var(--gray-100) !important;
    border-radius: 4px !important;
}

::-webkit-scrollbar-thumb {
    background: var(--gray-400) !important;
    border-radius: 4px !important;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--gray-500) !important;
}

/* ========== REMOVE EMPTY CONTAINERS ========== */
.empty-container {
    display: none !important;
}

/* ========== STEP INDICATORS ========== */
.step-indicator {
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
    margin-bottom: 1.5rem !important;
}

.step {
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
}

.step-number {
    width: 28px !important;
    height: 28px !important;
    border-radius: 50% !important;
    background: var(--gray-200) !important;
    color: var(--gray-600) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
}

.step.active .step-number {
    background: var(--primary-500) !important;
    color: white !important;
}

.step.completed .step-number {
    background: var(--primary-100) !important;
    color: var(--primary-700) !important;
}

.step-line {
    flex: 1 !important;
    height: 2px !important;
    background: var(--gray-200) !important;
    margin: 0 0.5rem !important;
}

/* ========== CHIP/TAG STYLES ========== */
.chip {
    display: inline-flex !important;
    align-items: center !important;
    padding: 0.25rem 0.75rem !important;
    border-radius: 16px !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    background: var(--gray-100) !important;
    color: var(--gray-700) !important;
    border: 1px solid var(--gray-200) !important;
}

.chip-primary {
    background: var(--primary-50) !important;
    color: var(--primary-700) !important;
    border-color: var(--primary-200) !important;
}

/* ========== GRID SYSTEM ========== */
.grid-2 {
    display: grid !important;
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 1rem !important;
}

.grid-3 {
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 1rem !important;
}

.grid-4 {
    display: grid !important;
    grid-template-columns: repeat(4, 1fr) !important;
    gap: 1rem !important;
}

@media (max-width: 768px) {
    .grid-2, .grid-3, .grid-4 {
        grid-template-columns: 1fr !important;
    }
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
    st.markdown('<div class="fade-in-content">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(str(logo_path), width=420)
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
        st.image(str(logo_path), width=160)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-section">Main Navigation</div>', unsafe_allow_html=True)
    
    # Main navigation buttons
    nav_items = [
        {"label": "🏠 Home", "page": "Home", "icon": "🏠"},
        {"label": "📊 Reports", "page": "Reports", "icon": "📊"},
        {"label": "📈 Dashboard", "page": "Dashboard", "icon": "📈"},
        {"label": "🧠 Categorisation", "page": "Categorisation", "icon": "🧠"},
        {"label": "🏢 Companies", "page": "Companies", "icon": "🏢"},
        {"label": "⚙️ Settings", "page": "Settings", "icon": "⚙️"},
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
    setup_subpage = st.session_state.active_subpage
    
    if st.button(
        "🏦 Banks",
        use_container_width=True,
        key="nav_banks",
        type="primary" if (setup_active and setup_subpage == "Banks") else "secondary",
    ):
        handle_page_transition("Setup", "Banks")
    
    if st.button(
        "🗂️ Categories",
        use_container_width=True,
        key="nav_categories",
        type="primary" if (setup_active and setup_subpage == "Categories") else "secondary",
    ):
        handle_page_transition("Setup", "Categories")
    
    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    
    # Quick Actions
    st.markdown('<div class="sidebar-section">Quick Actions</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export", use_container_width=True, type="secondary"):
            if st.session_state.active_client_id:
                show_success_message("Export feature coming soon!")
            else:
                show_warning_message("Select a company first")
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
            cache_data.clear()
            st.rerun()
    
    # Footer
    st.markdown('<div class="sidebar-section"></div>', unsafe_allow_html=True)
    st.caption("BankCat AI v1.0 • Professional Edition")

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
    st.markdown('<p class="body-large">AI-powered bank statement categorization for accountants.</p>', unsafe_allow_html=True)
    
    # Add professional divider
    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    
    # Client selector in a professional card
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Select Company")
            st.markdown('<p class="caption">Choose a company to manage or create a new one</p>', unsafe_allow_html=True)
        with col2:
            if st.button("➕ New Company", type="primary", use_container_width=True):
                handle_page_transition("Companies", "List")
        
        client_pick = _select_active_client(clients)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.active_client_id:
        # Metrics section
        st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            # Header with client name
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### 📋 {st.session_state.active_client_name}")
                st.markdown('<p class="caption">Overview and quick actions</p>', unsafe_allow_html=True)
            with col2:
                if st.button("✏️ Edit Company", type="secondary", use_container_width=True):
                    st.session_state.edit_client_id = st.session_state.active_client_id
                    handle_page_transition("Companies", "Edit")
            
            # Quick stats in metric cards
            st.markdown('<div class="grid-3">', unsafe_allow_html=True)
            
            banks = cached_banks(st.session_state.active_client_id)
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-value">{len(banks) if banks else 0}</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Banks</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            cats = cached_categories(st.session_state.active_client_id)
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-value">{len(cats) if cats else 0}</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Categories</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            try:
                drafts = crud.drafts_summary(st.session_state.active_client_id, None)
                with st.container():
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">{len(drafts) if drafts else 0}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Drafts</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            except:
                with st.container():
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">0</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Drafts</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)  # Close grid
            
            # Quick actions
            st.markdown("### Quick Actions")
            st.markdown('<p class="caption">Common workflows for this company</p>', unsafe_allow_html=True)
            
            action_cols = st.columns(3)
            
            with action_cols[0]:
                if st.button("🧠 Start Categorising", use_container_width=True, type="primary"):
                    handle_page_transition("Categorisation")
            
            with action_cols[1]:
                if st.button("📊 View Reports", use_container_width=True, type="secondary"):
                    handle_page_transition("Reports")
            
            with action_cols[2]:
                if st.button("🏦 Manage Banks", use_container_width=True, type="secondary"):
                    handle_page_transition("Setup", "Banks")
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### Getting Started")
            st.markdown("""
            <div class="body">
            1. **Select or create a company** - Manage multiple clients<br>
            2. **Add bank accounts** - Connect financial institutions<br>
            3. **Define categories** - Customize income/expense categories<br>
            4. **Process statements** - Upload and categorize transactions
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 Create Your First Company", type="primary", use_container_width=True):
                handle_page_transition("Companies", "List")
            
            st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard():
    st.markdown("## 📊 Financial Dashboard")
    st.markdown('<p class="caption">Real-time financial insights and analytics</p>', unsafe_allow_html=True)
    
    client_id = _require_active_client()
    if not client_id:
        return
    
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("### Date Range")
            start_date = st.date_input("Start Date", dt.date.today() - dt.timedelta(days=90), 
                                     label_visibility="collapsed")
        with col2:
            st.markdown("### &nbsp;")  # Spacer
            end_date = st.date_input("End Date", dt.date.today(), label_visibility="collapsed")
        
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
            
            # Income vs Expense metrics in professional cards
            with st.container():
                st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                st.markdown("### 💰 Income vs Expense")
                st.markdown('<p class="caption">Summary of financial performance</p>', unsafe_allow_html=True)
                
                df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
                df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
                
                total_income = df['credit'].sum()
                total_expense = df['debit'].sum()
                net = total_income - total_expense
                
                st.markdown('<div class="grid-3">', unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">${total_income:,.2f}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Total Income</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">${total_expense:,.2f}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Total Expense</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="metric-value">${net:,.2f}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="metric-label">Net Profit</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)  # Close grid
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Transactions table
            with st.container():
                st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("### 📋 Recent Transactions")
                    st.markdown('<p class="caption">Latest financial activity</p>', unsafe_allow_html=True)
                with col2:
                    if st.button("Export CSV", type="secondary", use_container_width=True):
                        show_success_message("Export feature coming soon!")
                
                st.dataframe(df[['tx_date', 'description', 'debit', 'credit', 'category', 'vendor']].head(20), 
                           use_container_width=True, hide_index=True)
                
                if len(df) > 20:
                    st.caption(f"Showing 20 of {len(df)} transactions. Use Reports for full view.")
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            with st.container():
                st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                
                st.markdown("### No Data Available")
                st.markdown('<p class="body">No committed transactions found for the selected period. Start by categorising some transactions.</p>', unsafe_allow_html=True)
                
                if st.button("🧠 Start Categorising", type="primary", use_container_width=True):
                    handle_page_transition("Categorisation")
                
                st.markdown('</div>', unsafe_allow_html=True)
            
    except Exception as e:
        show_error_message(f"Unable to load dashboard data: {_format_exc(e)}")

def render_reports():
    st.markdown("## 📊 Reports")
    st.markdown('<p class="caption">Generate and analyze financial reports</p>', unsafe_allow_html=True)
    
    client_id = _require_active_client()
    if not client_id:
        return
    
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### Report Configuration")
        st.markdown('<p class="caption">Select filters and report type</p>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<p class="label">Date Range</p>', unsafe_allow_html=True)
            start_date = st.date_input("From", dt.date.today() - dt.timedelta(days=30), 
                                     label_visibility="collapsed")
        with col2:
            st.markdown('<p class="label">&nbsp;</p>', unsafe_allow_html=True)
            end_date = st.date_input("To", dt.date.today(), label_visibility="collapsed")
        with col3:
            st.markdown('<p class="label">Bank Filter</p>', unsafe_allow_html=True)
            banks = cached_banks(client_id)
            bank_options = ["All Banks"] + [f"{b['id']} | {b['bank_name']}" for b in banks]
            bank_filter = st.selectbox("Bank", bank_options, label_visibility="collapsed")
        
        # Report type selection
        st.markdown('<p class="label">Report Type</p>', unsafe_allow_html=True)
        report_type = st.radio(
            "Report Type",
            ["P&L Summary", "Category Details", "Vendor Analysis"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Generate Report", type="primary", use_container_width=True):
                with st.spinner("Generating professional report..."):
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
                                
                                with st.container():
                                    st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                                    st.markdown("### 📈 Profit & Loss Summary")
                                    st.markdown('<p class="caption">Income and expenses by category</p>', unsafe_allow_html=True)
                                    st.dataframe(df_summary, use_container_width=True)
                                    st.markdown('</div>', unsafe_allow_html=True)
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
                                
                                with st.container():
                                    st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                                    st.markdown("### 📋 Transaction Details")
                                    st.markdown('<p class="caption">Detailed transaction listing</p>', unsafe_allow_html=True)
                                    st.dataframe(df_tx, use_container_width=True)
                                    st.markdown('</div>', unsafe_allow_html=True)
                            else:
                                st.info("No transactions found.")
                        
                        else:
                            st.info("Vendor Analysis report coming soon!")
                    
                    except Exception as e:
                        show_error_message(f"Error generating report: {_format_exc(e)}")
        
        with col2:
            if st.button("Export to Excel", type="secondary", use_container_width=True):
                show_success_message("Export feature coming soon!")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_settings():
    st.markdown("## ⚙️ Settings")
    st.markdown('<p class="caption">System configuration and database utilities</p>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### Database Utilities")
        st.markdown('<p class="caption">Manage database connection and schema</p>', unsafe_allow_html=True)
        
        tab1, tab2, tab3, tab4 = st.tabs(["Connection", "Initialize", "Schema Check", "Data Cleanup"])
        
        with tab1:
            st.markdown("#### Test Database Connection")
            st.markdown('<p class="caption">Verify connection to the database</p>', unsafe_allow_html=True)
            
            if st.button("Test Connection", type="primary", use_container_width=True):
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
            st.markdown('<p class="caption">Create all necessary tables if they don\'t exist</p>', unsafe_allow_html=True)
            
            st.warning("⚠️ This will create all necessary tables if they don't exist.")
            
            if st.button("Initialize Database", type="primary", use_container_width=True):
                try:
                    init_db()
                    show_success_message("✅ Database initialized successfully!")
                    cache_data.clear()
                except Exception as e:
                    show_error_message(f"❌ Initialization failed: {_format_exc(e)}")
        
        with tab3:
            st.markdown("#### Verify Database Schema")
            st.markdown('<p class="caption">Compare current database schema with expected schema</p>', unsafe_allow_html=True)
            
            if st.button("Run Schema Check", type="primary", use_container_width=True):
                result = _run_schema_check()
                if "error" in result:
                    show_error_message(result["error"])
                elif result.get("issues"):
                    with st.container():
                        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                        st.markdown("### ⚠️ Schema Issues Found")
                        issues_df = pd.DataFrame(result["issues"])
                        st.dataframe(issues_df, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    show_success_message("✅ Schema matches perfectly!")
        
        with tab4:
            st.markdown("#### 🗑️ Data Cleanup & Deletion")
            st.markdown('<p class="caption">⚠️ **DANGER ZONE** - Permanently delete data</p>', unsafe_allow_html=True)
            
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
                    
                    # Data type selection in grid
                    st.markdown('<div class="grid-2">', unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown("**Transaction Data:**")
                        delete_drafts = st.checkbox("Draft Transactions", value=True, 
                                                  help="Uncategorised/unsaved transaction data")
                        delete_committed = st.checkbox("Committed Transactions", value=False,
                                                     help="Finalised/committed transaction history")
                    
                    with st.container():
                        st.markdown("**Setup Data:**")
                        delete_banks = st.checkbox("Bank Accounts", value=False,
                                                 help="Bank account definitions")
                        delete_categories = st.checkbox("Categories", value=False,
                                                      help="Category definitions")
                    
                    with st.container():
                        st.markdown("**Learning Data:**")
                        delete_vendors = st.checkbox("Vendor Memory", value=False,
                                                   help="Learned vendor→category mappings")
                        delete_keywords = st.checkbox("Keyword Models", value=False,
                                                    help="Learned keyword→category patterns")
                    
                    with st.container():
                        st.markdown("**System Data:**")
                        delete_commits = st.checkbox("Commit History", value=False,
                                                   help="Commit records and accuracy metrics")
                        delete_client = st.checkbox("Company Itself", value=False,
                                                  help="Delete the entire company profile")
                    
                    st.markdown('</div>', unsafe_allow_html=True)  # Close grid
                    
                    # Warning message based on selection
                    selected_count = sum([
                        delete_drafts, delete_committed, delete_banks, 
                        delete_categories, delete_vendors, delete_keywords,
                        delete_commits, delete_client
                    ])
                    
                    if selected_count > 0:
                        st.error(f"⚠️ **WARNING:** You are about to delete {selected_count} type(s) of data!")
                        
                        # Confirmation
                        confirmation = st.text_input("Type 'DELETE' to confirm", 
                                                   placeholder="Type DELETE to confirm",
                                                   type="password")
                        
                        if st.button("🚨 Execute Data Deletion", type="primary", 
                                   disabled=(confirmation != "DELETE"), use_container_width=True):
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

def render_companies():
    st.markdown("## 🏢 Companies")
    st.markdown('<p class="caption">Manage client companies and organizations</p>', unsafe_allow_html=True)
    
    # Subpage navigation
    subpages = ["List", "Create", "Edit"]
    active_subpage = st.session_state.get("active_subpage", "List")
    
    # Professional tab-like navigation
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
    
    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    
    if active_subpage == "List":
        render_companies_list()
    elif active_subpage == "Create":
        render_companies_create()
    elif active_subpage == "Edit":
        render_companies_edit()

def render_companies_list():
    clients = cached_clients()
    
    if not clients:
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### No Companies Found")
            st.markdown('<p class="body">Create your first company to get started with BankCat AI.</p>', unsafe_allow_html=True)
            
            if st.button("➕ Create First Company", type="primary", use_container_width=True):
                st.session_state.active_subpage = "Create"
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        return
    
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Company List")
            st.markdown('<p class="caption">All companies in your system</p>', unsafe_allow_html=True)
        with col2:
            if st.button("➕ New Company", type="primary", use_container_width=True):
                st.session_state.active_subpage = "Create"
                st.rerun()
        
        for client in clients:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.markdown(f"**{client['name']}**")
                st.markdown(f'<p class="caption">{client.get("industry", "N/A")} • {client.get("country", "N/A")}</p>', unsafe_allow_html=True)
            with col2:
                if client.get('is_active', True):
                    st.markdown('<span class="status-badge status-committed">Active</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="status-badge status-draft">Inactive</span>', unsafe_allow_html=True)
            with col3:
                if st.button("✏️ Edit", key=f"edit_{client['id']}", type="secondary", use_container_width=True):
                    st.session_state.edit_client_id = client['id']
                    st.session_state.active_subpage = "Edit"
                    st.rerun()
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{client['id']}", type="secondary", use_container_width=True):
                    if st.session_state.active_client_id == client['id']:
                        st.session_state.active_client_id = None
                    crud.set_client_active(client['id'], False)
                    cache_data.clear()
                    show_success_message(f"Company '{client['name']}' deactivated")
                    time.sleep(1)
                    st.rerun()
            st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_companies_create():
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### Create New Company")
        st.markdown('<p class="caption">Add a new client company to the system</p>', unsafe_allow_html=True)
        
        with st.form("create_company_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Company Name *", placeholder="Enter company name")
                industry = st.text_input("Industry", placeholder="e.g., Retail, Services, Manufacturing")
            with col2:
                country = st.text_input("Country", placeholder="e.g., USA, UK, UAE")
                description = st.text_area("Business Description", placeholder="Brief description of the business")
            
            submitted = st.form_submit_button("Create Company", type="primary", use_container_width=True)
            
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.active_subpage = "List"
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_companies_edit():
    client_id = st.session_state.get("edit_client_id")
    if not client_id:
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            st.warning("No company selected for editing.")
            
            if st.button("← Back to List", type="primary", use_container_width=True):
                st.session_state.active_subpage = "List"
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        return
    
    clients = cached_clients()
    client = next((c for c in clients if c['id'] == client_id), None)
    
    if not client:
        show_error_message("Company not found")
        st.session_state.active_subpage = "List"
        st.rerun()
        return
    
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown(f"### Edit Company: {client['name']}")
        st.markdown('<p class="caption">Update company information</p>', unsafe_allow_html=True)
        
        with st.form("edit_company_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Company Name *", value=client.get('name', ''))
                industry = st.text_input("Industry", value=client.get('industry', ''))
            with col2:
                country = st.text_input("Country", value=client.get('country', ''))
                description = st.text_area("Business Description", value=client.get('business_description', ''))
            
            is_active = st.checkbox("Active", value=client.get('is_active', True))
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Cancel", type="secondary"):
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.active_subpage = "List"
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_setup():
    active_subpage = st.session_state.get("active_subpage", "Banks")
    
    st.markdown("## ⚙️ Setup")
    st.markdown('<p class="caption">Configure banks and categories for the selected company</p>', unsafe_allow_html=True)
    
    # Subpage navigation with icons
    subpages = ["Banks", "Categories"]
    cols = st.columns(len(subpages))
    for idx, subpage in enumerate(subpages):
        with cols[idx]:
            btn_text = "🏦 Banks" if subpage == "Banks" else "🗂️ Categories"
            if st.button(
                btn_text,
                use_container_width=True,
                type="primary" if subpage == active_subpage else "secondary",
                key=f"setup_{subpage}"
            ):
                st.session_state.active_subpage = subpage
                st.rerun()
    
    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 🏦 Bank Accounts")
            st.markdown('<p class="caption">Manage bank accounts for this company</p>', unsafe_allow_html=True)
        with col2:
            if st.button("➕ Add Bank", type="primary", use_container_width=True):
                st.session_state.setup_banks_mode = "create"
                st.rerun()
        
        if not banks:
            st.markdown('<div class="empty-state">', unsafe_allow_html=True)
            st.markdown('<div class="empty-state-icon">🏦</div>', unsafe_allow_html=True)
            st.markdown("### No Bank Accounts")
            st.markdown('<p class="body">Add your first bank account to start processing statements.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            for bank in banks:
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.markdown(f"**{bank['bank_name']}**")
                    st.markdown(f'<p class="caption">{bank.get("account_type", "Current")} • {bank.get("account_masked", "N/A")} • {bank.get("currency", "USD")}</p>', unsafe_allow_html=True)
                with col2:
                    if bank.get('is_active', True):
                        st.markdown('<span class="status-badge status-committed">Active</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="status-badge status-draft">Inactive</span>', unsafe_allow_html=True)
                with col3:
                    if st.button("✏️ Edit", key=f"edit_bank_{bank['id']}", type="secondary", use_container_width=True):
                        st.session_state.setup_bank_edit_id = bank['id']
                        st.session_state.setup_banks_mode = "edit"
                        st.rerun()
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_bank_{bank['id']}", type="secondary", use_container_width=True):
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### Add Bank Account")
        st.markdown('<p class="caption">Configure a new bank account</p>', unsafe_allow_html=True)
        
        with st.form("create_bank_form"):
            col1, col2 = st.columns(2)
            with col1:
                bank_name = st.text_input("Bank Name *", placeholder="e.g., Chase Bank, HSBC")
                account_type = st.selectbox("Account Type *", 
                                           ["Current", "Credit Card", "Savings", "Investment", "Wallet"])
            with col2:
                account_masked = st.text_input("Account Number (masked)", 
                                              placeholder="e.g., ****1234")
                currency = st.text_input("Currency", value="USD", placeholder="e.g., USD, EUR, GBP")
            
            opening_balance = st.number_input("Opening Balance", value=0.0, step=100.0, format="%.2f")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Create Bank", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Cancel", type="secondary"):
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.setup_banks_mode = "list"
            st.rerun()
        
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown(f"### Edit Bank: {bank['bank_name']}")
        st.markdown('<p class="caption">Update bank account details</p>', unsafe_allow_html=True)
        
        with st.form("edit_bank_form"):
            col1, col2 = st.columns(2)
            with col1:
                bank_name = st.text_input("Bank Name *", value=bank.get('bank_name', ''))
                account_type = st.selectbox("Account Type *", 
                                           ["Current", "Credit Card", "Savings", "Investment", "Wallet"],
                                           index=["Current", "Credit Card", "Savings", "Investment", "Wallet"]
                                           .index(bank.get('account_type', 'Current')))
            with col2:
                account_masked = st.text_input("Account Number (masked)", 
                                              value=bank.get('account_masked', ''))
                currency = st.text_input("Currency", value=bank.get('currency', 'USD'))
            
            opening_balance = st.number_input("Opening Balance", 
                                             value=float(bank.get('opening_balance', 0.0) or 0.0),
                                             step=100.0, format="%.2f")
            is_active = st.checkbox("Active", value=bank.get('is_active', True))
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Cancel", type="secondary"):
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.setup_banks_mode = "list"
            st.rerun()
        
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 🗂️ Categories")
            st.markdown('<p class="caption">Manage income and expense categories</p>', unsafe_allow_html=True)
        with col2:
            if st.button("➕ Add Category", type="primary", use_container_width=True):
                st.session_state.setup_categories_mode = "create"
                st.rerun()
        
        if not categories:
            st.markdown('<div class="empty-state">', unsafe_allow_html=True)
            st.markdown('<div class="empty-state-icon">🗂️</div>', unsafe_allow_html=True)
            st.markdown("### No Categories")
            st.markdown('<p class="body">Add your first category to start categorising transactions.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # Group by type
            for cat_type in ["Income", "Expense", "Other"]:
                type_cats = [c for c in categories if c.get('type') == cat_type and c.get('is_active', True)]
                if type_cats:
                    st.markdown(f"**{cat_type} Categories**")
                    for cat in type_cats:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.markdown(f"• **{cat['category_name']}**")
                            st.markdown(f'<p class="caption">Nature: {cat.get("nature", "Any")}</p>', unsafe_allow_html=True)
                        with col2:
                            if cat.get('is_active', True):
                                st.markdown('<span class="chip chip-primary">Active</span>', unsafe_allow_html=True)
                            else:
                                st.markdown('<span class="chip">Inactive</span>', unsafe_allow_html=True)
                        with col3:
                            if st.button("✏️ Edit", key=f"edit_cat_{cat['id']}", type="secondary", use_container_width=True):
                                st.session_state.setup_category_edit_id = cat['id']
                                st.session_state.setup_categories_mode = "edit"
                                st.rerun()
                    st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_categories_create(client_id):
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### Add Category")
        st.markdown('<p class="caption">Create a new transaction category</p>', unsafe_allow_html=True)
        
        with st.form("create_category_form"):
            name = st.text_input("Category Name *", placeholder="e.g., Sales, Rent, Office Supplies")
            cat_type = st.selectbox("Type *", ["Income", "Expense", "Other"])
            nature = st.selectbox("Nature", ["Any", "Dr", "Cr"], 
                                 help="Dr for Debit (usually expenses), Cr for Credit (usually income)")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Create Category", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Cancel", type="secondary"):
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.setup_categories_mode = "list"
            st.rerun()
        
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown(f"### Edit Category: {category['category_name']}")
        st.markdown('<p class="caption">Update category details</p>', unsafe_allow_html=True)
        
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
                submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Cancel", type="secondary"):
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
        
        if st.button("← Back to List", type="secondary", use_container_width=True):
            st.session_state.setup_categories_mode = "list"
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_categorisation():
    st.markdown("## 🧠 Categorisation")
    st.markdown('<p class="caption">Upload, categorize, and commit bank statement transactions</p>', unsafe_allow_html=True)
    
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
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### No Active Banks")
            st.markdown('<p class="body">Add at least one active bank account to start categorising transactions.</p>', unsafe_allow_html=True)
            
            if st.button("🏦 Add Bank Account", type="primary", use_container_width=True):
                handle_page_transition("Setup", "Banks")
            
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # --- Step 1: Bank Selection ---
    with st.container():
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### 1. Select Bank")
        st.markdown('<p class="caption">Choose a bank account to work with</p>', unsafe_allow_html=True)
        
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### 2. Period Selection")
        st.markdown('<p class="caption">Choose the time period for transactions</p>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        
        with col1:
            st.markdown('<p class="label">Year</p>', unsafe_allow_html=True)
            year_range = list(range(2020, 2031))
            year = st.selectbox("Year", year_range, index=year_range.index(st.session_state.year), label_visibility="collapsed")
            st.session_state.year = year
        
        with col2:
            st.markdown('<p class="label">Month</p>', unsafe_allow_html=True)
            month = st.selectbox("Month", month_names, index=month_names.index(st.session_state.month), label_visibility="collapsed")
            st.session_state.month = month
        
        with col3:
            st.markdown('<p class="label">Period</p>', unsafe_allow_html=True)
            period = f"{year}-{month_names.index(month)+1:02d}"
            st.text_input("Period", value=period, disabled=True, label_visibility="collapsed")
            st.session_state.period = period
        
        with col4:
            st.markdown('<p class="label">Date Range</p>', unsafe_allow_html=True)
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
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### 3. Upload Statement")
            st.markdown('<p class="caption">Upload CSV bank statement or use template</p>', unsafe_allow_html=True)
            
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
                    use_container_width=True,
                    type="secondary"
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
                st.markdown('<p class="caption">Map CSV columns to transaction fields</p>', unsafe_allow_html=True)
                
                cols = ["(blank)"] + list(df_raw.columns)
                
                st.markdown('<div class="grid-5">', unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<p class="label">Date *</p>', unsafe_allow_html=True)
                    map_date = st.selectbox("Date", cols, index=cols.index("Date") if "Date" in cols else 0, label_visibility="collapsed", key="map_date")
                
                with st.container():
                    st.markdown('<p class="label">Description *</p>', unsafe_allow_html=True)
                    map_desc = st.selectbox("Description", cols, index=cols.index("Description") if "Description" in cols else 0, label_visibility="collapsed", key="map_desc")
                
                with st.container():
                    st.markdown('<p class="label">Debit (Dr)</p>', unsafe_allow_html=True)
                    map_dr = st.selectbox("Debit", cols, index=cols.index("Dr") if "Dr" in cols else 0, label_visibility="collapsed", key="map_dr")
                
                with st.container():
                    st.markdown('<p class="label">Credit (Cr)</p>', unsafe_allow_html=True)
                    map_cr = st.selectbox("Credit", cols, index=cols.index("Cr") if "Cr" in cols else 0, label_visibility="collapsed", key="map_cr")
                
                with st.container():
                    st.markdown('<p class="label">Closing Balance</p>', unsafe_allow_html=True)
                    map_bal = st.selectbox("Closing", cols, index=cols.index("Closing") if "Closing" in cols else 0, label_visibility="collapsed", key="map_bal")
                
                st.markdown('</div>', unsafe_allow_html=True)
                
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
                col1, col2 = st.columns([1, 4])
                with col1:
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
        st.markdown('<div class="professional-card">', unsafe_allow_html=True)
        
        st.markdown("### 4. Saved Items")
        st.markdown('<p class="caption">Select a draft or committed dataset to work with</p>', unsafe_allow_html=True)
        
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
                    st.markdown(f"**{item['type']}**")
                    st.markdown(f'<p class="caption">{item["row_count"]} rows</p>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<span class="status-badge {item["badge_class"]}">{item["status"]}</span>', unsafe_allow_html=True)
                    if item.get("min_date") and item.get("max_date"):
                        st.markdown(f'<p class="caption">{item["min_date"]} to {item["max_date"]}</p>', unsafe_allow_html=True)
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
                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">', unsafe_allow_html=True)
            st.markdown('<div class="empty-state-icon">📄</div>', unsafe_allow_html=True)
            st.markdown("### No Saved Items")
            st.markdown('<p class="body">Upload a statement or select a period with existing data.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Check if item is selected ---
    selected_item_id = st.session_state.categorisation_selected_item
    has_selected_item = bool(selected_item_id)
    
    # --- Step 5: Main View Table ---
    if has_selected_item:
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### 5. Transaction Review")
            st.markdown('<p class="caption">Review and edit transaction categorizations</p>', unsafe_allow_html=True)
            
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
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### 6. Progress Summary")
            st.markdown('<p class="caption">Track your categorization progress</p>', unsafe_allow_html=True)
            
            total_rows = int(draft_summary.get("row_count") or 0)
            suggested_count = 0
            if draft_summary:
                suggested_count = int(draft_summary.get("suggested_count") or 0)
            final_count = int(draft_summary.get("final_count") or 0)
            pending_rows = total_rows - final_count
            
            st.markdown('<div class="grid-4">', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-value">{total_rows}</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Total Rows</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                suggested_pct = (suggested_count / total_rows * 100) if total_rows > 0 else 0
                st.markdown(f'<div class="metric-value">{suggested_count}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-label">AI Suggested ({suggested_pct:.0f}%)</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                final_pct = (final_count / total_rows * 100) if total_rows > 0 else 0
                st.markdown(f'<div class="metric-value">{final_count}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-label">User Finalised ({final_pct:.0f}%)</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                pending_pct = (pending_rows / total_rows * 100) if total_rows > 0 else 0
                st.markdown(f'<div class="metric-value">{pending_rows}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-label">Pending Review ({pending_pct:.0f}%)</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)  # Close grid
            st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Step 7: Action Buttons ---
    if has_selected_item:
        with st.container():
            st.markdown('<div class="professional-card">', unsafe_allow_html=True)
            
            st.markdown("### 7. Actions")
            st.markdown('<p class="caption">Available actions for the selected dataset</p>', unsafe_allow_html=True)
            
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
                    st.markdown('<div class="grid-3">', unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.markdown(f'<div class="metric-value">{info.get("rows_committed", 0)}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="metric-label">Rows Committed</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.markdown(f'<div class="metric-value">{info.get("accuracy", 0)*100:.1f}%</div>', unsafe_allow_html=True)
                        st.markdown('<div class="metric-label">Accuracy</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.markdown(f'<div class="metric-value">{info.get("committed_by", "N/A")}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="metric-label">Committed By</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)  # Close grid
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Show special message for upload state ---
    elif not has_selected_item and not draft_summary and not commit_summary:
        if st.session_state.standardized_rows and len(st.session_state.standardized_rows) > 0:
            with st.container():
                st.markdown('<div class="professional-card">', unsafe_allow_html=True)
                
                st.markdown("### 5. Mapped Data Preview")
                st.markdown('<p class="caption">Review mapped data before saving as draft</p>', unsafe_allow_html=True)
                
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
