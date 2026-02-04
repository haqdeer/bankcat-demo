# app.py - COMPLETE FIXED VERSION WITH ENHANCED POPUP ANIMATIONS
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
        "show_cat_popup": st.session_state.get("show_cat_popup", False),
        "cat_popup_message": st.session_state.get("cat_popup_message", ""),
        "cat_popup_type": st.session_state.get("cat_popup_type", "thinking"),
        "cat_popup_details": st.session_state.get("cat_popup_details", {}),
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    if st.session_state.active_page == "Companies" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "List"
    if st.session_state.active_page == "Setup" and not st.session_state.active_subpage:
        st.session_state.active_subpage = "Banks"


init_session_state()

# ---------------- ENHANCED: CAT ANIMATIONS AS POPUPS ----------------
def show_cat_popup():
    """Show cat animation as a fixed popup"""
    if not st.session_state.show_cat_popup:
        return ""
    
    popup_type = st.session_state.cat_popup_type
    message = st.session_state.cat_popup_message
    details = st.session_state.cat_popup_details
    
    if popup_type == "thinking":
        cat_faces = ["😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾"]
        current_cat = random.choice(cat_faces)
        
        popup_html = f"""
        <div id="cat-popup" style="
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px 35px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            z-index: 9999;
            border: 2px solid #e5e7eb;
            min-width: 320px;
            max-width: 420px;
            text-align: center;
            animation: popIn 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        ">
            <div style="font-size: 64px; margin-bottom: 20px; animation: bounce 1.2s infinite;">
                {current_cat}
            </div>
            <div style="color: #1f2937; font-weight: 700; font-size: 20px; margin-bottom: 12px;">
                {message}
            </div>
            <div style="color: #6b7280; font-size: 15px; margin-bottom: 25px; line-height: 1.5;">
                "Meow! Processing your request..."
            </div>
            <button onclick="document.getElementById('cat-popup').remove();" style="
                background: #ef4444;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            ">
                Close
            </button>
        </div>
        <style>
        @keyframes popIn {{
            0% {{ transform: translate(-50%, -50%) scale(0.7); opacity: 0; }}
            100% {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
        }}
        @keyframes bounce {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-12px); }}
        }}
        </style>
        """
    
    elif popup_type == "success":
        popup_html = f"""
        <div id="cat-popup" style="
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(135deg, #dcfce7, #bbf7d0);
            padding: 35px 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25);
            z-index: 9999;
            border: 3px solid #86efac;
            min-width: 320px;
            max-width: 420px;
            text-align: center;
            animation: popIn 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        ">
            <div style="font-size: 68px; margin-bottom: 20px; animation: celebrate 0.8s;">
                🎉😻
            </div>
            <div style="color: #065f46; font-weight: 800; font-size: 22px; margin-bottom: 12px;">
                {message}
            </div>
            <div style="color: #047857; font-size: 16px; margin-bottom: 25px; line-height: 1.5;">
                "Purrrrfect! All done!"
            </div>
            <button onclick="document.getElementById('cat-popup').remove();" style="
                background: #10b981;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            ">
                Awesome!
            </button>
        </div>
        <style>
        @keyframes popIn {{
            0% {{ transform: translate(-50%, -50%) scale(0.7); opacity: 0; }}
            100% {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
        }}
        @keyframes celebrate {{
            0% {{ transform: scale(0.5); opacity: 0; }}
            60% {{ transform: scale(1.1); }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        </style>
        """
    
    elif popup_type == "processing":
        row_num = details.get("row_num", 0)
        total_rows = details.get("total_rows", 0)
        category = details.get("category", "")
        vendor = details.get("vendor", "")
        
        progress_pct = (row_num / total_rows * 100) if total_rows > 0 else 0
        
        cat_actions = [
            "🔍 Sniffing transaction...",
            "🧠 Analyzing pattern...",
            "🏷️ Finding category...",
            "🏢 Identifying vendor...",
            "✅ Almost there..."
        ]
        
        if row_num <= total_rows:
            action_idx = min(row_num % len(cat_actions), len(cat_actions)-1)
            action = cat_actions[action_idx]
        else:
            action = "Finishing up..."
        
        popup_html = f"""
        <div id="cat-popup" style="
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px 35px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25);
            z-index: 9999;
            border: 2px solid #e5e7eb;
            min-width: 380px;
            max-width: 480px;
            animation: popIn 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        ">
            <div style="display: flex; align-items: center; margin-bottom: 25px;">
                <div style="font-size: 48px; margin-right: 20px; animation: bounce 1s infinite;">😼</div>
                <div style="flex-grow: 1;">
                    <div style="color: #1f2937; font-weight: 700; font-size: 18px; margin-bottom: 5px;">{action}</div>
                    <div style="color: #6b7280; font-size: 14px;">Row {row_num} of {total_rows}</div>
                </div>
                <div style="font-size: 28px; color: #9ca3af; margin: 0 15px;">→</div>
                <div style="text-align: right;">
                    <div style="color: #10b981; font-weight: 700; font-size: 16px;">{category}</div>
                    <div style="color: #6b7280; font-size: 13px;">{vendor}</div>
                </div>
            </div>
            
            <div style="width: 100%; height: 10px; background: #f3f4f6; border-radius: 5px; overflow: hidden; margin-bottom: 15px;">
                <div style="width: {progress_pct}%; height: 100%; background: linear-gradient(90deg, #7CFFB2, #10b981); 
                        border-radius: 5px; transition: width 0.5s ease-in-out;"></div>
            </div>
            
            <div style="display: flex; justify-content: space-between; margin-bottom: 25px; font-size: 12px; color: #6b7280;">
                <div>🐾 Cat is working hard...</div>
                <div><strong>{progress_pct:.1f}%</strong> complete</div>
            </div>
            
            <button onclick="document.getElementById('cat-popup').remove();" style="
                background: #ef4444;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
                width: 100%;
            ">
                Cancel Processing
            </button>
        </div>
        <style>
        @keyframes popIn {{
            0% {{ transform: translate(-50%, -50%) scale(0.7); opacity: 0; }}
            100% {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
        }}
        @keyframes bounce {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-8px); }}
        }}
        </style>
        """
    
    else:  # Default thinking
        popup_html = f"""
        <div id="cat-popup" style="
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            z-index: 9999;
            border: 2px solid #e5e7eb;
            min-width: 300px;
            text-align: center;
            animation: popIn 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        ">
            <div style="font-size: 64px; margin-bottom: 20px;">😺</div>
            <div style="color: #1f2937; font-weight: 700; font-size: 20px; margin-bottom: 10px;">
                {message}
            </div>
            <button onclick="document.getElementById('cat-popup').remove();" style="
                background: #ef4444;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
                margin-top: 20px;
            ">
                Close
            </button>
        </div>
        """
    
    return popup_html

def show_cat_thinking_popup(message="Cat is thinking..."):
    """Show cat thinking popup"""
    st.session_state.show_cat_popup = True
    st.session_state.cat_popup_message = message
    st.session_state.cat_popup_type = "thinking"
    st.rerun()

def show_cat_success_popup(message="Success!"):
    """Show cat success popup"""
    st.session_state.show_cat_popup = True
    st.session_state.cat_popup_message = message
    st.session_state.cat_popup_type = "success"
    st.rerun()

def show_cat_processing_popup(row_num=0, total_rows=0, category="", vendor=""):
    """Show cat processing popup"""
    st.session_state.show_cat_popup = True
    st.session_state.cat_popup_message = "Processing rows..."
    st.session_state.cat_popup_type = "processing"
    st.session_state.cat_popup_details = {
        "row_num": row_num,
        "total_rows": total_rows,
        "category": category,
        "vendor": vendor
    }
    st.rerun()

def close_cat_popup():
    """Close the cat popup"""
    st.session_state.show_cat_popup = False
    st.rerun()

# ---------------- Simple Loader ----------------
def show_simple_loader(message="Processing..."):
    """Simple progress bar loader"""
    progress_placeholder = st.empty()
    with progress_placeholder.container():
        st.markdown(f"""
        <div style="
            background: rgba(255, 255, 255, 0.95);
            padding: 25px 30px;
            border-radius: 12px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            text-align: center;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1000;
            border: 1px solid #e5e7eb;
            min-width: 250px;
        ">
            <div style="margin-bottom: 20px;">
                <div style="
                    width: 60px;
                    height: 60px;
                    margin: 0 auto;
                    border: 4px solid #f3f4f6;
                    border-top: 4px solid #7CFFB2;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
            </div>
            <div style="color: #4a5568; font-size: 15px; font-weight: 600; margin-bottom: 8px;">{message}</div>
            <div style="color: #718096; font-size: 13px;">Please wait...</div>
        </div>
        <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
        """, unsafe_allow_html=True)
    return progress_placeholder

# ---------------- App Startup ----------------
if not st.session_state.app_initialized:
    time.sleep(0.5)
    st.session_state.app_initialized = True
    st.rerun()

# ---------------- Enhanced Custom CSS ----------------
st.markdown(
    """
<style>
/* Main background */
.stApp {
    background-color: #f8fafc;
}

/* Sidebar styling */
.css-1d391kg, section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}

/* Sidebar logo styling */
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

/* Home page logo styling */
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
    color: #1f2937;
    font-weight: 700;
    border-bottom: 2px solid #7CFFB2;
    padding-bottom: 0.5rem;
}

/* Content spacing */
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
}

/* Categorisation specific styling */
.categorisation-container {
    padding: 1rem;
}

.section-card {
    background: white;
    border-radius: 10px;
    padding: 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #e5e7eb;
    transition: box-shadow 0.2s;
}

.section-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

/* Saved items table styling */
.saved-item-row {
    padding: 0.75rem;
    border-bottom: 1px solid #e5e7eb;
    cursor: pointer;
    transition: background-color 0.2s;
}

.saved-item-row:hover {
    background-color: #f9fafb;
}

.saved-item-row.selected {
    background-color: #f0fdf4;
    border-left: 4px solid #10b981;
    border-radius: 4px;
}

/* Status badges */
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
    background-color: #dbeafe;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
}

.status-categorised {
    background-color: #fef3c7;
    color: #d97706;
    border: 1px solid #fde68a;
}

.status-committed {
    background-color: #dcfce7;
    color: #047857;
    border: 1px solid #bbf7d0;
}

/* Data cleanup warning */
.cleanup-warning {
    background-color: #fff8e1;
    border-left: 4px solid #f59e0b;
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem 0;
}

/* Row highlight animation */
@keyframes highlightRow {
    0% { background-color: rgba(124, 255, 178, 0.4); }
    70% { background-color: rgba(124, 255, 178, 0.1); }
    100% { background-color: transparent; }
}

.highlight-row {
    animation: highlightRow 2s ease-out;
}

/* NEW: Cat popup overlay */
.cat-popup-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 9998;
    backdrop-filter: blur(3px);
    animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* Button improvements */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}

/* Green active buttons in sidebar */
.stButton > button[kind="secondary"] {
    background-color: #10b981 !important;
    color: white !important;
    border-color: #10b981 !important;
}

.stButton > button[kind="secondary"]:hover {
    background-color: #0da271 !important;
    border-color: #0da271 !important;
}

/* Override to ensure popup is on top */
div[data-testid="stAppViewContainer"] {
    position: relative;
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

if active_page == "Home" and logo_path.exists():
    st.markdown('<div class="home-logo-container fade-in-content">', unsafe_allow_html=True)
    st.image(str(logo_path), width=520)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<h1 class="page-title fade-in-content">{page_title}</h1>', unsafe_allow_html=True)

# ---------------- Show Cat Popup if Active ----------------
if st.session_state.show_cat_popup:
    # Add overlay
    st.markdown('<div class="cat-popup-overlay"></div>', unsafe_allow_html=True)
    # Show popup
    st.markdown(show_cat_popup(), unsafe_allow_html=True)

# ---------------- Page Transition Handler ----------------
def handle_page_transition(new_page: str, subpage: str | None = None):
    if st.session_state.active_page != new_page:
        st.session_state.active_page = new_page
        if subpage:
            st.session_state.active_subpage = subpage
        st.rerun()

# ---------------- Sidebar Content ----------------
with st.sidebar:
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
            if page != "Setup":
                st.session_state.sidebar_setup_open = False
            handle_page_transition(page)

    companies_active = st.session_state.active_page == "Companies"
    if st.button(
        "🏢 Companies",
        use_container_width=True,
        key="nav_companies",
        type=_button_type(companies_active),
    ):
        st.session_state.sidebar_setup_open = False
        handle_page_transition("Companies", "List")

    setup_chevron = "▾" if st.session_state.sidebar_setup_open else "▸"
    setup_active = st.session_state.active_page == "Setup"
    
    if st.button(
        f"{setup_chevron} 🛠️ Setup",
        use_container_width=True,
        key="toggle_setup",
        type=_button_type(setup_active),
    ):
        st.session_state.sidebar_setup_open = not st.session_state.sidebar_setup_open
        
        if st.session_state.sidebar_setup_open and not setup_active:
            handle_page_transition("Setup", None)
        else:
            st.rerun()
    
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
                st.session_state.active_page = "Setup"
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
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", dt.date.today() - dt.timedelta(days=90))
    with col2:
        end_date = st.date_input("End Date", dt.date.today())
    
    try:
        transactions = crud.list_committed_transactions(
            client_id, 
            date_from=start_date, 
            date_to=end_date
        )
        
        if transactions:
            df = pd.DataFrame(transactions)
            
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
        st.stop()

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
                crud.ensure_ask_client_category(cid)
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
    if st.session_state.active_subpage == "Banks":
        render_setup_banks()
    else:
        render_setup_categories()

# ---------------- Enhanced Categorisation Page ----------------
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

    # --- Row 1: Bank selector only ---
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
    
    # --- Row 2: Year + Month + Period(auto) + Date range ---
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
        
        # Initialize dates if None - FIXED DATE RANGE ERROR
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
            
            # Handle date input correctly
            if isinstance(dr, tuple) and len(dr) == 2:
                date_from, date_to = dr
            else:
                date_from = dr
                date_to = dr
            
            st.session_state.date_from = date_from
            st.session_state.date_to = date_to
            
        except Exception as e:
            # If error, set sensible defaults
            st.session_state.date_from = dt.date(year, month_idx, 1)
            st.session_state.date_to = dt.date(year, month_idx, last_day)
            date_from = st.session_state.date_from
            date_to = st.session_state.date_to

    # --- Get data summaries ---
    draft_summary = None
    commit_summary = None
    try:
        draft_summary = crud.get_draft_summary(client_id, bank_id, period)
        commit_summary = crud.get_commit_summary(client_id, bank_id, period)
    except Exception as e:
        st.error(f"Error loading summaries: {_format_exc(e)}")

    # --- Row 3: Upload & Mapping Section ---
    if not draft_summary and not commit_summary:
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
                    st.success(f"✅ Loaded {len(df_raw)} rows")
                except Exception as e:
                    st.error(f"❌ Upload failed: {_format_exc(e)}")
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
            
            # FIXED DATE PARSING FOR dd/mm/yyyy FORMAT
            def _to_date(x):
                if pd.isna(x):
                    return None
                try:
                    if isinstance(x, str):
                        x_str = str(x).strip()
                        
                        # Handle different date formats
                        formats_to_try = [
                            "%d/%m/%Y",  # 25/09/2025
                            "%d-%m-%Y",  # 25-09-2025
                            "%Y-%m-%d",  # 2025-09-25
                            "%Y/%m/%d",  # 2025/09/25
                            "%d %b %Y",  # 25 Sep 2025
                            "%d %B %Y",  # 25 September 2025
                        ]
                        
                        for fmt in formats_to_try:
                            try:
                                return dt.datetime.strptime(x_str, fmt).date()
                            except:
                                continue
                        
                        # If still not parsed, try dayfirst
                        try:
                            return pd.to_datetime(x_str, dayfirst=True).date()
                        except:
                            return None
                    
                    # If already a datetime or date
                    if isinstance(x, (dt.datetime, dt.date)):
                        return x.date() if isinstance(x, dt.datetime) else x
                    
                    return None
                except Exception:
                    return None
            
            # Process rows button
            if st.button("Apply Mapping", type="primary", key="apply_mapping"):
                standardized_rows = []
                dropped_missing_date = 0
                dropped_missing_desc = 0
                date_errors = []
                
                for idx, r in df_raw.iterrows():
                    d = _to_date(r[map_date]) if map_date != "(blank)" else None
                    ds = str(r[map_desc]).strip() if map_desc != "(blank)" else ""
                    
                    # If date missing or parsing failed
                    if not d:
                        if ds:  # If description exists, use period start date
                            d = dt.date(year, month_names.index(month) + 1, 1)
                            dropped_missing_date += 1
                        else:
                            dropped_missing_desc += 1
                            continue
                    
                    # Drop if description missing
                    if not ds:
                        dropped_missing_desc += 1
                        continue
                    
                    # Parse amounts
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
                
                st.success(f"✅ Mapped {len(standardized_rows)} rows")
                
                if date_errors:
                    st.warning(f"⚠️ {len(date_errors)} rows had date parsing issues")
                
                st.info(f"""
                **Mapping Summary:**
                - Original rows: {len(df_raw)}
                - Successfully mapped: {len(standardized_rows)}
                - Rows with missing/invalid date (used period default): {dropped_missing_date}
                - Rows dropped (missing description): {dropped_missing_desc}
                """)
                
                st.session_state.categorisation_selected_item = None
                st.rerun()

    # --- Row 4: Saved Items Display ---
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
        
        header_cols = st.columns([2, 1.5, 1, 1, 1.5, 1, 1])
        header_cols[0].markdown("**Type**")
        header_cols[1].markdown("**Status**")
        header_cols[2].markdown("**Rows**")
        header_cols[3].markdown("**Suggested**")
        header_cols[4].markdown("**Finalised**")
        header_cols[5].markdown("**Date Range**")
        header_cols[6].markdown("**Action**")
        
        st.markdown("---")
        
        for item in saved_items:
            is_selected = (selected_item_id == item["id"])
            
            date_range_display = "—"
            if item.get("min_date") and item.get("max_date"):
                date_range_display = f"{item['min_date']} to {item['max_date']}"
            
            last_updated_display = "N/A"
            if item.get("last_updated") and item["last_updated"] != "N/A":
                try:
                    last_updated_display = str(item["last_updated"])[:10]
                except:
                    last_updated_display = str(item["last_updated"])
            
            row_cols = st.columns([2, 1.5, 1, 1, 1.5, 1, 1])
            
            with row_cols[0]:
                st.write(f"**{item['type']}**")
            
            with row_cols[1]:
                st.markdown(f'<span class="status-badge {item["badge_class"]}">{item["status"]}</span>', unsafe_allow_html=True)
            
            with row_cols[2]:
                st.write(f"{item['row_count']}")
            
            with row_cols[3]:
                if "suggested_rows" in item:
                    st.write(f"{item['suggested_rows']}")
                else:
                    st.write("—")
            
            with row_cols[4]:
                if "final_rows" in item:
                    st.write(f"{item['final_rows']}")
                else:
                    st.write("—")
            
            with row_cols[5]:
                st.write(date_range_display)
            
            with row_cols[6]:
                if is_selected:
                    if st.button("✖ Deselect", key=f"deselect_{item['id']}", type="secondary"):
                        st.session_state.categorisation_selected_item = None
                        st.rerun()
                else:
                    if st.button("👉 Select", key=f"select_{item['id']}", type="primary"):
                        st.session_state.categorisation_selected_item = item["id"]
                        st.rerun()
            
            if not is_selected:
                st.markdown("---")
    else:
        st.info("No saved items yet for this bank + period.")

    # --- Check if item is selected ---
    selected_item_id = st.session_state.categorisation_selected_item
    has_selected_item = bool(selected_item_id)
    
    # --- Row 5: Main View Table ---
    if has_selected_item:
        st.markdown("### 5. Main View")
        
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
                st.error(f"Unable to load draft rows: {_format_exc(e)}")
        
        elif selected_item_id and selected_item_id.startswith("committed"):
            try:
                committed_rows = crud.load_committed_rows(client_id, bank_id, period)
                if committed_rows:
                    df_c = pd.DataFrame(committed_rows)
                    st.dataframe(df_c, use_container_width=True, hide_index=True)
                else:
                    st.info("No committed rows found.")
            except Exception as e:
                st.error(f"Unable to load committed rows: {_format_exc(e)}")
    
    # --- Row 6: Progress Summary ---
    if has_selected_item and draft_summary and selected_item_id.startswith("draft_"):
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
    
    # --- Row 7: Action Buttons (WITH ENHANCED POPUP ANIMATIONS) ---
    if has_selected_item:
        st.markdown("### 7. Actions")
        
        has_draft = bool(draft_summary)
        has_commit = bool(commit_summary)
        
        if selected_item_id.startswith("draft_"):
            suggested_count = 0
            if draft_summary:
                suggested_count = int(draft_summary.get("suggested_count") or 0)
            final_count = int(draft_summary.get("final_count") or 0)
            total_rows = int(draft_summary.get("row_count") or 0)
            
            action_cols = st.columns([1, 1, 1])
            
            with action_cols[0]:
                if suggested_count == 0:
                    if st.button("🤖 Suggest Categories", type="primary", use_container_width=True, 
                               disabled=st.session_state.processing_suggestions):
                        if not st.session_state.processing_suggestions:
                            st.session_state.processing_suggestions = True
                            
                            # Show cat animation POPUP
                            show_cat_thinking_popup("Cat is analyzing transactions...")
                            
                            try:
                                # Process suggestions
                                n = crud.process_suggestions(client_id, bank_id, period, 
                                                            bank_account_type=bank_obj.get("account_type"))
                                
                                # Close thinking popup and show success popup
                                time.sleep(0.5)
                                show_cat_success_popup(f"✅ Suggested {n} categories!")
                                
                                # Auto-close after 2 seconds
                                time.sleep(2)
                                close_cat_popup()
                                
                                cache_data.clear()
                                st.session_state.processing_suggestions = False
                                st.rerun()
                            except Exception as e:
                                close_cat_popup()
                                st.error(f"❌ Suggestion failed: {_format_exc(e)}")
                                st.session_state.processing_suggestions = False
                else:
                    if st.button("🔄 Re-suggest Categories", type="secondary", use_container_width=True,
                               disabled=st.session_state.processing_suggestions):
                        st.info("Already suggested. Edit categories in the table above.")
            
            with action_cols[1]:
                if st.button("💾 Save Draft Changes", type="primary", use_container_width=True, key="save_draft_changes"):
                    if "draft_editor" in st.session_state and st.session_state.draft_editor:
                        edited_data = st.session_state.draft_editor.get("edited_rows", {})
                        
                        if edited_data:
                            # Show cat saving popup
                            show_cat_thinking_popup("Cat is saving your changes...")
                            
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
                                    
                                    # Show success popup
                                    time.sleep(0.5)
                                    show_cat_success_popup(f"✅ Saved {updated} changes!")
                                    
                                    # Auto-close after 1.5 seconds
                                    time.sleep(1.5)
                                    close_cat_popup()
                                    
                                    cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    close_cat_popup()
                                    st.error(f"❌ Save failed: {_format_exc(e)}")
                            else:
                                close_cat_popup()
                                st.warning("No valid changes to save")
                        else:
                            st.info("No changes detected to save. Make edits in the table first.")
                    else:
                        st.info("Make changes in the table above first, then save.")
            
            with action_cols[2]:
                if final_count >= total_rows and total_rows > 0:
                    # COMMIT SECTION WITH CAT POPUP ANIMATION
                    st.markdown("**Commit Final**")
                    
                    # Commit button
                    if st.button("🔒 Commit Final Now", type="primary", use_container_width=True,
                               disabled=st.session_state.processing_commit, key="commit_final_button"):
                        
                        if not st.session_state.processing_commit:
                            st.session_state.processing_commit = True
                            
                            # Show cat committing popup
                            show_cat_thinking_popup("Cat is locking transactions...")
                            
                            try:
                                # Call commit function
                                result = crud.commit_period(client_id, bank_id, period, 
                                                          committed_by="Accountant")
                                
                                # Close thinking popup and show success popup
                                time.sleep(0.5)
                                
                                if result.get("ok"):
                                    # Show success popup with cat food
                                    st.session_state.show_cat_popup = True
                                    st.session_state.cat_popup_message = f"✅ Successfully committed {result.get('rows', 0)} rows!"
                                    st.session_state.cat_popup_type = "success"
                                    st.session_state.cat_popup_details = {"accuracy": result.get('accuracy', 0)*100}
                                    
                                    # Clear states and refresh
                                    st.session_state.categorisation_selected_item = None
                                    st.session_state.standardized_rows = []
                                    st.session_state.df_raw = None
                                    st.session_state.processing_commit = False
                                    cache_data.clear()
                                    
                                    # Auto refresh after 3 seconds
                                    time.sleep(3)
                                    close_cat_popup()
                                    st.rerun()
                                else:
                                    close_cat_popup()
                                    st.error(f"❌ Commit failed: {result.get('msg', 'Unknown error')}")
                                    st.session_state.processing_commit = False
                            except Exception as e:
                                close_cat_popup()
                                st.error(f"❌ Commit error: {_format_exc(e)}")
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
    
    # --- Show special message for upload state ---
    elif not has_selected_item and not draft_summary and not commit_summary:
        if st.session_state.standardized_rows and len(st.session_state.standardized_rows) > 0:
            st.markdown("### 5. Mapped Data Preview")
            df_uploaded = pd.DataFrame(st.session_state.standardized_rows)
            st.info(f"📄 **Mapped Data ({len(df_uploaded)} rows)** - Ready to save as draft")
            st.dataframe(df_uploaded, use_container_width=True, hide_index=True)
            
            st.markdown("### 6. Save Draft")
            if st.button("💾 Save Draft", type="primary", use_container_width=True):
                # Show cat popup
                show_cat_thinking_popup("Cat is saving draft...")
                
                try:
                    n = crud.insert_draft_rows(client_id, bank_id, period, 
                                              st.session_state.standardized_rows, replace=True)
                    
                    # Show success popup
                    time.sleep(0.5)
                    show_cat_success_popup(f"✅ Draft saved ({n} rows)!")
                    
                    # Auto-close after 1.5 seconds
                    time.sleep(1.5)
                    close_cat_popup()
                    
                    st.session_state.standardized_rows = []
                    st.session_state.df_raw = None
                    cache_data.clear()
                    st.rerun()
                except Exception as e:
                    close_cat_popup()
                    st.error(f"❌ Save failed: {_format_exc(e)}")

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
    
    st.markdown("---")
    st.markdown("### 🗑️ Data Cleanup (Client-wise)")
    
    clients = cached_clients()
    if not clients:
        st.warning("No clients found for cleanup.")
        return
    
    client_options = ["(Select Client)"] + [f"{c['id']} | {c['name']}" for c in clients]
    selected_client = st.selectbox("Select Client", client_options, key="cleanup_client_select")
    
    if selected_client != "(Select Client)":
        client_id = int(selected_client.split("|")[0].strip())
        client_name = selected_client.split("|")[1].strip()
        
        st.markdown(f"**Selected:** {client_name} (ID: {client_id})")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            delete_banks = st.checkbox("Banks", value=False, key="cleanup_banks")
            delete_categories = st.checkbox("Categories", value=False, key="cleanup_categories")
            delete_drafts = st.checkbox("Draft Transactions", value=False, key="cleanup_drafts")
            delete_committed = st.checkbox("Committed Transactions", value=False, key="cleanup_committed")
        
        with col2:
            delete_vendor_memory = st.checkbox("Vendor Memory", value=False, key="cleanup_vendor_memory")
            delete_keyword_model = st.checkbox("Keyword Model", value=False, key="cleanup_keyword_model")
            delete_commits = st.checkbox("Commits History", value=False, key="cleanup_commits")
            delete_client_itself = st.checkbox("Client Itself", value=False, key="cleanup_client")
        
        any_selected = (delete_banks or delete_categories or delete_drafts or 
                       delete_committed or delete_vendor_memory or 
                       delete_keyword_model or delete_commits or delete_client_itself)
        
        if any_selected:
            st.markdown('<div class="cleanup-warning">', unsafe_allow_html=True)
            st.warning("⚠️ **WARNING:** This action cannot be undone. Data will be permanently deleted.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            confirm_delete = st.checkbox("I understand this action is irreversible", value=False, key="confirm_delete")
            
            if confirm_delete:
                if st.button("🚨 DELETE SELECTED DATA", type="primary"):
                    with st.spinner("Deleting data..."):
                        result = crud.delete_client_data(
                            client_id=client_id,
                            delete_banks=delete_banks,
                            delete_categories=delete_categories,
                            delete_drafts=delete_drafts,
                            delete_committed=delete_committed,
                            delete_vendor_memory=delete_vendor_memory,
                            delete_keyword_model=delete_keyword_model,
                            delete_commits=delete_commits,
                            delete_client_itself=delete_client_itself,
                        )
                    
                    if result["ok"]:
                        st.success("✅ Data deleted successfully!")
                        if "deleted" in result:
                            st.markdown("**Deleted counts:**")
                            for table, count in result["deleted"].items():
                                st.write(f"- {table}: {count} rows")
                        
                        cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Delete failed: {result.get('error', 'Unknown error')}")
    else:
        st.info("Select a client to see cleanup options.")

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
