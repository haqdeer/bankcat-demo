# app.py - INSTANT LOADER WITH SMOOTH ANIMATION
import io
import sys
import calendar
import datetime as dt
import urllib.parse
import base64
from pathlib import Path
import time
import threading

import pandas as pd
import streamlit as st
from streamlit import cache_data

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schema import init_db
from src import crud

# ---------------- GLOBAL VARIABLES ----------------
LOADER_SHOWING = False
LOADER_CONTAINER = None

# ---------------- INSTANT LOADER SYSTEM ----------------
def show_loader_instantly(location="full", duration=2.0):
    """Show loader immediately with smooth animation"""
    global LOADER_SHOWING, LOADER_CONTAINER
    
    if LOADER_SHOWING:
        return
    
    LOADER_SHOWING = True
    
    # Create loader HTML with instant show
    loader_html = """
    <div id="bankcat-loader" style="
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
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes smoothSpin {
            0% { transform: rotate(0deg); opacity: 0.8; }
            50% { transform: rotate(180deg); opacity: 1; filter: drop-shadow(0 0 20px rgba(124, 255, 178, 0.9)); }
            100% { transform: rotate(360deg); opacity: 0.8; }
        }
        
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; visibility: hidden; }
        }
        
        .loader-core {
            animation: smoothSpin 1.5s cubic-bezier(0.68, -0.55, 0.27, 1.55) infinite;
            width: 180px;
            height: 180px;
        }
        
        .loader-text {
            margin-top: 25px;
            color: #4a5568;
            font-size: 16px;
            font-weight: 500;
            letter-spacing: 3px;
            animation: smoothSpin 3s ease-in-out infinite;
            opacity: 0.7;
        }
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
    
    loader_html += """
        <div class="loader-text">LOADING</div>
    </div>
    
    <script>
    // Auto-remove after duration
    setTimeout(function() {
        var loader = document.getElementById('bankcat-loader');
        if (loader) {
            loader.style.animation = 'fadeOut 0.3s forwards';
            setTimeout(function() {
                if (loader.parentNode) {
                    loader.parentNode.removeChild(loader);
                }
            }, 300);
        }
    }, """ + str(int(duration * 1000)) + """);
    </script>
    """
    
    # Show loader
    if location == "full":
        st.markdown(loader_html, unsafe_allow_html=True)
    else:
        # For main area
        st.markdown(f"""
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 9999;">
            {loader_html}
        </div>
        """, unsafe_allow_html=True)
    
    return duration

def hide_loader():
    """Hide loader immediately"""
    global LOADER_SHOWING
    LOADER_SHOWING = False
    st.markdown("""
    <script>
    var loader = document.getElementById('bankcat-loader');
    if (loader && loader.parentNode) {
        loader.parentNode.removeChild(loader);
    }
    </script>
    """, unsafe_allow_html=True)

# ---------------- SESSION STATE ----------------
if 'app_initialized' not in st.session_state:
    st.session_state.app_initialized = False
if 'page_transition' not in st.session_state:
    st.session_state.page_transition = False
if 'active_page' not in st.session_state:
    st.session_state.active_page = "Home"
if 'active_subpage' not in st.session_state:
    st.session_state.active_subpage = None
if 'active_client_id' not in st.session_state:
    st.session_state.active_client_id = None
if 'sidebar_setup_open' not in st.session_state:
    st.session_state.sidebar_setup_open = False

# ---------------- APP STARTUP LOADER ----------------
if not st.session_state.app_initialized:
    # Show INSTANT loader
    show_loader_instantly("full", 2.5)
    
    # Mark as initialized in background
    st.session_state.app_initialized = True
    
    # Force rerun after loader duration
    time.sleep(2.5)
    st.rerun()

# ---------------- PAGE TRANSITION HANDLER ----------------
def switch_page_with_loader(new_page, subpage=None):
    """Switch page with instant loader"""
    if st.session_state.active_page != new_page:
        # Show loader INSTANTLY
        show_loader_instantly("main", 1.8)
        
        # Update page state
        st.session_state.active_page = new_page
        if subpage:
            st.session_state.active_subpage = subpage
        
        # Force rerun
        time.sleep(0.1)  # Tiny delay to ensure loader shows
        st.rerun()

# Check if we just did a page transition
if st.session_state.get('page_transition', False):
    time.sleep(0.1)  # Let loader appear
    st.session_state.page_transition = False

# ---------------- STYLING ----------------
st.markdown("""
<style>
/* Main styling */
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

.page-title {
    margin-top: 0.75rem;
}

/* Quick fade for any residual loader */
.loader-quick-exit {
    animation: fadeOut 0.2s forwards !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- PAGE TITLE ----------------
active_page = st.session_state.active_page
active_subpage = st.session_state.active_subpage
page_title = active_page
if active_page == "Companies" and active_subpage:
    page_title = f"Companies > {active_subpage}"
elif active_page == "Setup" and active_subpage:
    page_title = f"Setup > {active_subpage}"

logo_path = ROOT / "assets" / "bankcat-logo.jpeg"

# Home page logo
if active_page == "Home" and logo_path.exists():
    st.markdown('<div class="home-logo-container">', unsafe_allow_html=True)
    st.image(str(logo_path), width=520)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<h1 class="page-title">{page_title}</h1>', unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    if logo_path.exists():
        st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
        st.image(str(logo_path), width=220)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("### Navigation")
    
    def _button_type(is_active):
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
            switch_page_with_loader(page)
    
    # Companies
    companies_active = st.session_state.active_page == "Companies"
    if st.button(
        "🏢 Companies",
        use_container_width=True,
        key="nav_companies",
        type=_button_type(companies_active),
    ):
        switch_page_with_loader("Companies", "List")
    
    # Setup
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
            switch_page_with_loader("Setup", "Banks")
    
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

# ---------------- HELPER FUNCTIONS ----------------
def _require_active_client():
    client_id = st.session_state.active_client_id
    if not client_id:
        st.warning("Select a company on Home first.")
        return None
    return client_id

def _select_active_client(clients):
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

def _select_bank(banks_active):
    # درست:
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

# ---------------- CACHED DATA ----------------
@st.cache_data(ttl=30)
def cached_clients():
    try:
        return crud.list_clients(include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load clients: {e}")
        return []

@st.cache_data(ttl=30)
def cached_banks(client_id):
    try:
        return crud.list_banks(client_id, include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load banks: {e}")
        return []

@st.cache_data(ttl=30)
def cached_categories(client_id):
    try:
        return crud.list_categories(client_id, include_inactive=True)
    except Exception as e:
        st.error(f"Unable to load categories: {e}")
        return []

# ---------------- PAGE RENDER FUNCTIONS ----------------
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
            
            # Your dashboard content here...
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
        else:
            st.info("No committed transactions found.")
            
    except Exception as e:
        st.error(f"Unable to load dashboard data: {e}")

# ... (All your other page functions remain the same - Reports, Companies, Setup, etc.)

# ---------------- MAIN ROUTER ----------------
def main():
    page = st.session_state.active_page
    
    if page == "Home":
        render_home()
    elif page == "Dashboard":
        render_dashboard()
    elif page == "Reports":
        st.markdown("## 📊 Reports")
        # Your reports code
    elif page == "Companies":
        subpage = st.session_state.active_subpage
        if subpage == "List":
            # render_companies_list()
            pass
        elif subpage == "Add Company":
            # render_companies_add()
            pass
    elif page == "Setup":
        if st.session_state.active_subpage == "Banks":
            # render_setup_banks()
            pass
        else:
            # render_setup_categories()
            pass
    elif page == "Categorisation":
        # Your categorisation code
        pass
    elif page == "Settings":
        # Your settings code
        pass
    else:
        render_home()

if __name__ == "__main__":
    main()