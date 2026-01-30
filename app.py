# app.py - WITH CLEAN LOADER
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

# ---------------- Custom CSS (FIRST THING) ----------------
st.markdown(
    """
<style>
/* Hide everything during loading */
.hide-during-load {
    display: none !important;
}

/* Full page loader - ABSOLUTELY CLEAN */
.full-page-loader {
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
}

/* Page transition loader - ABSOLUTELY CLEAN */
.page-transition-loader {
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
    z-index: 9999;
}

/* SVG Loader Animation */
@keyframes spin {
    0% { transform: rotate(0deg) scale(1); }
    50% { transform: rotate(180deg) scale(1.1); }
    100% { transform: rotate(360deg) scale(1); }
}

@keyframes eyeGlow {
    0%, 100% { 
        opacity: 0.3;
        filter: drop-shadow(0 0 8px rgba(124, 255, 178, 0.4));
    }
    50% { 
        opacity: 1;
        filter: drop-shadow(0 0 25px rgba(124, 255, 178, 0.9));
    }
}

@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; visibility: hidden; }
}

.loader-svg {
    animation: spin 1.8s ease-in-out infinite, eyeGlow 2s ease-in-out infinite;
    width: 180px;
    height: 180px;
    margin: 0 auto;
    display: block;
}

.loading-text {
    margin-top: 30px;
    color: #4a5568;
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 4px;
    animation: eyeGlow 2.5s ease-in-out infinite;
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
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Session State Initialization ----------------
if 'app_initialized' not in st.session_state:
    st.session_state.app_initialized = False
if 'show_page_loader' not in st.session_state:
    st.session_state.show_page_loader = False
if 'page_loader_start_time' not in st.session_state:
    st.session_state.page_loader_start_time = 0
if 'active_page' not in st.session_state:
    st.session_state.active_page = "Home"
if 'active_subpage' not in st.session_state:
    st.session_state.active_subpage = None
if 'active_client_id' not in st.session_state:
    st.session_state.active_client_id = None
if 'active_client_name' not in st.session_state:
    st.session_state.active_client_name = None
if 'sidebar_setup_open' not in st.session_state:
    st.session_state.sidebar_setup_open = False

# Rest of your imports and setup...
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

# ---------------- App Initialization Loader ----------------
if not st.session_state.app_initialized:
    # Add a script to hide everything except loader
    st.markdown("""
    <script>
    // Hide all Streamlit elements
    document.querySelectorAll('.stApp > *:not(.full-page-loader)').forEach(el => {
        if (!el.classList.contains('full-page-loader')) {
            el.style.display = 'none';
        }
    });
    </script>
    """, unsafe_allow_html=True)
    
    # Create loader container
    loader_container = st.empty()
    
    with loader_container.container():
        # Show clean animated loader
        st.markdown("""
        <div class="full-page-loader">
            <div style="text-align: center;">
        """, unsafe_allow_html=True)
        
        # Load SVG or use fallback
        loader_svg_path = ROOT / "assets" / "bankcat-loader.gif.svg"
        if loader_svg_path.exists():
            svg_bytes = loader_svg_path.read_bytes()
            svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
            st.markdown(f"""
            <img src="data:image/svg+xml;base64,{svg_base64}" 
                 class="loader-svg" 
                 alt="Loading BankCat"/>
            """, unsafe_allow_html=True)
        else:
            # Fallback animated circle
            st.markdown("""
            <div style="width: 120px; height: 120px; margin: 0 auto; 
                border: 10px solid #f3f3f3; 
                border-top: 10px solid #7CFFB2;
                border-radius: 50%; 
                animation: spin 1.5s ease-in-out infinite, eyeGlow 2s ease-in-out infinite;">
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("""
                <div class="loading-text">LOADING BANKCAT</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Minimum 2 seconds for clean loading
    time.sleep(2.0)
    
    # Mark as initialized
    st.session_state.app_initialized = True
    
    # Fade out loader
    st.markdown("""
    <script>
    setTimeout(function() {
        var loader = document.querySelector('.full-page-loader');
        if (loader) {
            loader.style.animation = 'fadeOut 0.5s forwards';
        }
    }, 300);
    
    setTimeout(function() {
        var loader = document.querySelector('.full-page-loader');
        if (loader && loader.parentNode) {
            loader.parentNode.removeChild(loader);
        }
        // Show all elements again
        document.querySelectorAll('.stApp > *').forEach(el => {
            el.style.display = '';
        });
    }, 800);
    </script>
    """, unsafe_allow_html=True)
    
    time.sleep(0.8)
    loader_container.empty()
    st.rerun()

# ---------------- Page Transition Handler ----------------
def handle_page_transition(new_page: str, subpage: str | None = None):
    """Handle page transitions with clean loader"""
    if st.session_state.active_page != new_page:
        # Store previous page
        st.session_state.previous_page = st.session_state.active_page
        
        # Set new page
        st.session_state.active_page = new_page
        if subpage:
            st.session_state.active_subpage = subpage
        
        # Show page transition loader
        st.session_state.show_page_loader = True
        st.session_state.page_loader_start_time = time.time()
        st.rerun()

# Show page transition loader if needed
if st.session_state.get('show_page_loader', False):
    # Add script to hide main content
    st.markdown("""
    <script>
    // Hide main content area during transition
    var mainBlock = document.querySelector('.main .block-container');
    if (mainBlock) {
        mainBlock.style.display = 'none';
    }
    </script>
    """, unsafe_allow_html=True)
    
    # Create loader placeholder
    loader_placeholder = st.empty()
    
    with loader_placeholder.container():
        # Show clean transition loader
        st.markdown("""
        <div class="page-transition-loader">
            <div style="text-align: center;">
        """, unsafe_allow_html=True)
        
        # Load SVG or use fallback
        loader_svg_path = ROOT / "assets" / "bankcat-loader.gif.svg"
        if loader_svg_path.exists():
            svg_bytes = loader_svg_path.read_bytes()
            svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
            st.markdown(f"""
            <img src="data:image/svg+xml;base64,{svg_base64}" 
                 class="loader-svg" 
                 alt="Loading..."/>
            """, unsafe_allow_html=True)
        else:
            # Fallback animated circle
            st.markdown("""
            <div style="width: 100px; height: 100px; margin: 0 auto; 
                border: 8px solid #f3f3f3; 
                border-top: 8px solid #7CFFB2;
                border-radius: 50%; 
                animation: spin 1.5s ease-in-out infinite, eyeGlow 2s ease-in-out infinite;">
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("""
                <div class="loading-text">LOADING PAGE</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Minimum 1.5 seconds for clean transition (at least 2 rotations)
    min_loading_time = 1.8
    elapsed_time = time.time() - st.session_state.get('page_loader_start_time', time.time())
    
    if elapsed_time < min_loading_time:
        time.sleep(min_loading_time - elapsed_time)
    
    # Fade out loader and show content
    st.markdown("""
    <script>
    setTimeout(function() {
        var loader = document.querySelector('.page-transition-loader');
        if (loader) {
            loader.style.animation = 'fadeOut 0.4s forwards';
        }
    }, 300);
    
    setTimeout(function() {
        var loader = document.querySelector('.page-transition-loader');
        if (loader && loader.parentNode) {
            loader.parentNode.removeChild(loader);
        }
        // Show main content again
        var mainBlock = document.querySelector('.main .block-container');
        if (mainBlock) {
            mainBlock.style.display = '';
        }
    }, 700);
    </script>
    """, unsafe_allow_html=True)
    
    time.sleep(0.7)
    loader_placeholder.empty()
    st.session_state.show_page_loader = False
    st.rerun()

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
else:
    # دیگر صفحات پر صرف ٹائٹل دکھائیں گے
    st.markdown(f'<h1 class="page-title">{page_title}</h1>', unsafe_allow_html=True)

# ---------------- Sidebar Content ----------------
with st.sidebar:
    # Add logo to sidebar top
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
# (All your existing page render functions remain exactly the same)
# I'm including just one as example, keep all your existing ones

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

# ... (All other page functions remain exactly as before)

# ---------------- Main Page Router ----------------
def main():
    page = st.session_state.active_page
    
    if page == "Home":
        render_home()
    elif page == "Dashboard":
        render_dashboard()
    elif page == "Reports":
        # Your render_reports() function
        st.markdown("## 📊 Reports")
        client_id = _require_active_client()
        if not client_id:
            return
        # ... rest of reports code
    elif page == "Companies":
        # Your companies logic
        subpage = st.session_state.active_subpage
        if subpage == "List":
            # render_companies_list()
            pass
        elif subpage == "Add Company":
            # render_companies_add()
            pass
    elif page == "Setup":
        # Your setup logic
        if st.session_state.active_subpage == "Banks":
            # render_setup_banks()
            pass
        else:
            # render_setup_categories()
            pass
    elif page == "Categorisation":
        # Your categorisation logic
        pass
    elif page == "Settings":
        # Your settings logic
        pass
    else:
        render_home()

if __name__ == "__main__":
    main()
