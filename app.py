# app.py
import io
import sys
import calendar
import datetime as dt
import urllib.parse
import base64
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import init_db
from src import crud

def _logo_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"svg"}:
        svg_text = path.read_text(encoding="utf-8")
        encoded = urllib.parse.quote(svg_text)
        return f"data:image/svg+xml;utf8,{encoded}"
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
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


# ---------------- Sidebar Navigation ----------------
logo_path = ROOT / "assets" / "bankcat-logo.jpeg"
if "active_page" not in st.session_state:
    st.session_state.active_page = st.session_state.get("nav_page", "Home")
if "active_subpage" not in st.session_state:
    legacy_subpage = None
    if st.session_state.active_page == "Companies":
        legacy_subpage = st.session_state.get("companies_tab", "List")
    elif st.session_state.active_page == "Setup":
        legacy_subpage = st.session_state.get("setup_tab", "Banks")
    st.session_state.active_subpage = legacy_subpage
if st.session_state.active_page == "Companies" and not st.session_state.active_subpage:
    st.session_state.active_subpage = "List"
if st.session_state.active_page == "Setup" and not st.session_state.active_subpage:
    st.session_state.active_subpage = "Banks"

active_page = st.session_state.active_page
active_subpage = st.session_state.active_subpage
page_title = active_page
if active_page == "Companies" and active_subpage:
    page_title = f"Companies > {active_subpage}"
elif active_page == "Setup" and active_subpage:
    page_title = f"Setup > {active_subpage}"

logo_uri = _logo_data_uri(logo_path)

# Restore original header block but add localStorage toggle for persistence
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
(function() {{
  const STORAGE_KEY = 'bankcat.sidebarCollapsed';
  const bodyClass = 'bankcat-sidebar-collapsed';
  const read = () => {{
    try {{ return localStorage.getItem(STORAGE_KEY) === '1'; }} catch(e) {{ return false; }}
  }};
  const write = (val) => {{
    try {{ localStorage.setItem(STORAGE_KEY, val ? '1' : '0'); }} catch(e) {{ /* ignore */ }}
  }};
  const applyState = (collapsed) => {{
    if (collapsed) document.body.classList.add(bodyClass);
    else document.body.classList.remove(bodyClass);
  }};

  // Initialize state from storage on load
  document.addEventListener('DOMContentLoaded', () => {{
    applyState(read());
  }});

  // Toggle handler
  const toggleBtn = document.getElementById('sidebar-toggle');
  toggleBtn?.addEventListener('click', () => {{
    const currently = read();
    write(!currently);
    applyState(!currently);
  }});

  // Fullscreen
  const fsBtn = document.getElementById('fullscreen-toggle');
  fsBtn?.addEventListener('click', () => {{
    if (!document.fullscreenElement) {{
      document.documentElement.requestFullscreen();
    }} else {{
      document.exitFullscreen();
    }}
  }});
}})();
</script>
    """,
    unsafe_allow_html=True,
)