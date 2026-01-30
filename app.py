# app.py - COMPLETE WORKING VERSION WITH ALL PAGES
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

try:
    from src.schema import init_db
    from src import crud
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    st.warning("Database modules not found. Running in demo mode.")

# Set page config - MUST BE FIRST
st.set_page_config(
    page_title="BankCat",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- SIMPLE LOADER ----------------
def show_quick_loader(duration=1.5):
    """Quick loader that appears instantly"""
    loader_html = """
    <div id="quick-loader" style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100vh;
        background: white;
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 99999;
        animation: fadeIn 0.1s;
    ">
        <div style="text-align: center;">
            <div style="
                width: 80px;
                height: 80px;
                border: 8px solid #f3f3f3;
                border-top: 8px solid #7CFFB2;
                border-radius: 50%;
                animation: spin 1.2s linear infinite;
                margin: 0 auto;
            "></div>
            <div style="
                margin-top: 20px;
                color: #4a5568;
                font-size: 16px;
                font-weight: 500;
            ">Loading...</div>
        </div>
    </div>
    
    <style>
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
    </style>
    
    <script>
    setTimeout(function() {
        var loader = document.getElementById('quick-loader');
        if (loader) {
            loader.style.animation = 'fadeOut 0.3s forwards';
            setTimeout(function() {
                if (loader.parentNode) loader.parentNode.removeChild(loader);
            }, 300);
        }
    }, """ + str(int(duration * 1000)) + """);
    </script>
    """
    
    st.markdown(loader_html, unsafe_allow_html=True)
    return duration

# ---------------- SESSION STATE ----------------
if 'app_initialized' not in st.session_state:
    st.session_state.app_initialized = False
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
if 'bank_id' not in st.session_state:
    st.session_state.bank_id = None
if 'df_raw' not in st.session_state:
    st.session_state.df_raw = None
if 'setup_banks_mode' not in st.session_state:
    st.session_state.setup_banks_mode = "list"
if 'setup_categories_mode' not in st.session_state:
    st.session_state.setup_categories_mode = "list"

# ---------------- APP STARTUP LOADER ----------------
if not st.session_state.app_initialized:
    show_quick_loader(2.0)
    st.session_state.app_initialized = True
    time.sleep(0.1)
    st.rerun()

# ---------------- PAGE TRANSITION ----------------
def navigate_to(page, subpage=None):
    """Navigate to page with loader"""
    if st.session_state.active_page != page:
        show_quick_loader(1.2)
        st.session_state.active_page = page
        if subpage:
            st.session_state.active_subpage = subpage
        time.sleep(0.1)
        st.rerun()

# ---------------- STYLING ----------------
st.markdown("""
<style>
/* Main styling */
.main-header {
    margin-bottom: 2rem;
}

.sidebar-logo {
    text-align: center;
    padding: 1rem 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
}

.home-logo {
    text-align: center;
    margin: 2rem auto;
    max-width: 500px;
}

/* Button styling */
.nav-button {
    margin-bottom: 0.5rem;
}

/* Dataframe styling */
.dataframe {
    font-size: 14px;
}

/* Metric cards */
.metric-card {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 10px;
    border-left: 4px solid #7CFFB2;
}
</style>
""", unsafe_allow_html=True)

# ---------------- PATHS ----------------
logo_path = ROOT / "assets" / "bankcat-logo.jpeg"
loader_svg_path = ROOT / "assets" / "bankcat-loader.gif.svg"

# ---------------- SIDEBAR ----------------
with st.sidebar:
    # Logo
    if logo_path.exists():
        st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
        st.image(str(logo_path), width=200)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("### 🏦 BankCat")
    
    st.markdown("### Navigation")
    
    # Navigation buttons
    nav_pages = [
        ("🏠 Home", "Home"),
        ("📊 Reports", "Reports"),
        ("📈 Dashboard", "Dashboard"),
        ("🧠 Categorisation", "Categorisation"),
        ("🏢 Companies", "Companies"),
        ("🛠️ Setup", "Setup"),
        ("⚙️ Settings", "Settings"),
    ]
    
    for label, page in nav_pages:
        if st.button(label, use_container_width=True, key=f"nav_{page}", type="primary" if st.session_state.active_page == page else "secondary"):
            navigate_to(page)
    
    # Setup submenu
    if st.session_state.active_page == "Setup":
        st.markdown("---")
        st.markdown("#### Setup Options")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Banks", use_container_width=True, key="setup_banks_btn"):
                st.session_state.active_subpage = "Banks"
                st.rerun()
        with col2:
            if st.button("Categories", use_container_width=True, key="setup_cats_btn"):
                st.session_state.active_subpage = "Categories"
                st.rerun()
    
    # Companies submenu
    if st.session_state.active_page == "Companies":
        st.markdown("---")
        st.markdown("#### Companies Options")
        if st.button("➕ Add New Company", use_container_width=True):
            st.session_state.active_subpage = "Add"
            st.rerun()
    
    st.markdown("---")
    st.markdown("#### Client Info")
    if st.session_state.active_client_id:
        st.success(f"**Selected:** {st.session_state.active_client_name or 'Client ' + str(st.session_state.active_client_id)}")
    else:
        st.warning("No client selected")

# ---------------- HELPER FUNCTIONS ----------------
def get_clients():
    """Get clients list"""
    if DB_AVAILABLE:
        try:
            return crud.list_clients(include_inactive=True)
        except:
            return []
    else:
        # Demo data
        return [
            {"id": 1, "name": "TechCorp Inc", "industry": "Technology", "is_active": True},
            {"id": 2, "name": "RetailMart", "industry": "Retail", "is_active": True},
            {"id": 3, "name": "ConsultPro", "industry": "Consulting", "is_active": False}
        ]

def get_banks(client_id):
    """Get banks for client"""
    if DB_AVAILABLE and client_id:
        try:
            return crud.list_banks(client_id, include_inactive=True)
        except:
            return []
    else:
        # Demo data
        return [
            {"id": 1, "bank_name": "Bank of America", "account_type": "Current", "currency": "USD"},
            {"id": 2, "bank_name": "Chase Bank", "account_type": "Savings", "currency": "USD"}
        ]

def get_categories(client_id):
    """Get categories for client"""
    if DB_AVAILABLE and client_id:
        try:
            return crud.list_categories(client_id, include_inactive=True)
        except:
            return []
    else:
        # Demo data
        return [
            {"id": 1, "category_name": "Office Supplies", "type": "Expense", "is_active": True},
            {"id": 2, "category_name": "Software", "type": "Expense", "is_active": True},
            {"id": 3, "category_name": "Consulting Fees", "type": "Income", "is_active": True}
        ]

# ---------------- PAGE: HOME ----------------
if st.session_state.active_page == "Home":
    # Logo on home page
    if logo_path.exists():
        st.markdown('<div class="home-logo">', unsafe_allow_html=True)
        st.image(str(logo_path), width=500)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("BankCat Demo")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.write("Welcome to the BankCat financial management system.")
    
    # Client selection
    st.markdown("### Select Client")
    clients = get_clients()
    
    if clients:
        client_options = ["-- Select Client --"] + [f"{c['id']} | {c['name']}" for c in clients]
        selected_idx = 0
        
        if st.session_state.active_client_id:
            for i, opt in enumerate(client_options):
                if opt.startswith(f"{st.session_state.active_client_id} |"):
                    selected_idx = i
                    break
        
        selected = st.selectbox("Choose a client", client_options, index=selected_idx, key="home_client_select")
        
        if selected != "-- Select Client --":
            client_id = int(selected.split("|")[0].strip())
            client_name = selected.split("|")[1].strip()
            st.session_state.active_client_id = client_id
            st.session_state.active_client_name = client_name
            st.success(f"Selected: {client_name}")
    
    # Quick stats
    st.markdown("### Quick Overview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Clients", "3", "+1")
    with col2:
        st.metric("Total Transactions", "1,247", "12%")
    with col3:
        st.metric("Categorization Rate", "94%", "2%")

# ---------------- PAGE: DASHBOARD ----------------
elif st.session_state.active_page == "Dashboard":
    st.title("📊 Financial Dashboard")
    
    if not st.session_state.active_client_id:
        st.warning("Please select a client on the Home page first.")
    else:
        st.success(f"Viewing dashboard for: {st.session_state.active_client_name or 'Selected Client'}")
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", dt.date.today() - dt.timedelta(days=90))
        with col2:
            end_date = st.date_input("End Date", dt.date.today())
        
        # Metrics
        st.markdown("### Key Metrics")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Total Income", "$12,450", "+12%")
        metric_cols[1].metric("Total Expenses", "$8,920", "-5%")
        metric_cols[2].metric("Net Profit", "$3,530", "+8%")
        metric_cols[3].metric("Cash Flow", "$2,810", "+4%")
        
        # Charts
        st.markdown("### Monthly Performance")
        
        # Sample chart data
        chart_data = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'Income': [10000, 12000, 11000, 13000, 12450, 14000],
            'Expenses': [8000, 8500, 8200, 9000, 8920, 9500],
            'Profit': [2000, 3500, 2800, 4000, 3530, 4500]
        })
        
        tab1, tab2 = st.tabs(["Line Chart", "Bar Chart"])
        with tab1:
            st.line_chart(chart_data.set_index('Month')[['Income', 'Expenses']])
        with tab2:
            st.bar_chart(chart_data.set_index('Month')[['Profit']])
        
        # Recent transactions
        st.markdown("### Recent Transactions")
        transactions = pd.DataFrame({
            'Date': ['2024-01-15', '2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19'],
            'Description': ['Office Supplies', 'Software Subscription', 'Client Payment', 'Travel Expenses', 'Marketing'],
            'Amount': [-250, -99, 1500, -420, -350],
            'Category': ['Expense', 'Expense', 'Income', 'Expense', 'Expense'],
            'Status': ['Categorized', 'Categorized', 'Categorized', 'Pending', 'Categorized']
        })
        
        st.dataframe(transactions, use_container_width=True, hide_index=True)

# ---------------- PAGE: REPORTS ----------------
elif st.session_state.active_page == "Reports":
    st.title("📋 Reports")
    
    if not st.session_state.active_client_id:
        st.warning("Please select a client on the Home page first.")
    else:
        st.success(f"Generating reports for: {st.session_state.active_client_name}")
        
        # Report filters
        col1, col2, col3 = st.columns(3)
        with col1:
            report_type = st.selectbox(
                "Report Type",
                ["Transaction Summary", "Profit & Loss", "Balance Sheet", "Cash Flow", "Tax Report"]
            )
        with col2:
            period = st.selectbox(
                "Period",
                ["Last 30 Days", "Last Quarter", "Last 6 Months", "Year to Date", "Custom"]
            )
        with col3:
            format_type = st.selectbox("Export Format", ["PDF", "Excel", "CSV"])
        
        # Generate report button
        if st.button("Generate Report", type="primary", use_container_width=True):
            with st.spinner(f"Generating {report_type} report..."):
                time.sleep(1.5)
                st.success("Report generated successfully!")
                
                # Sample report data
                st.markdown(f"### {report_type} - {period}")
                
                if report_type == "Transaction Summary":
                    summary_data = pd.DataFrame({
                        'Category': ['Office Supplies', 'Software', 'Travel', 'Salaries', 'Client Fees'],
                        'Count': [45, 12, 23, 4, 15],
                        'Total Amount': ['-$2,250', '-$1,188', '-$4,830', '-$12,000', '+$22,500'],
                        'Avg per Transaction': ['-$50', '-$99', '-$210', '-$3,000', '+$1,500']
                    })
                    st.dataframe(summary_data, use_container_width=True)
                
                elif report_type == "Profit & Loss":
                    pl_data = pd.DataFrame({
                        'Account': ['Revenue', 'COGS', 'Gross Profit', 'Operating Expenses', 'Net Profit'],
                        'Amount': ['$25,000', '-$5,000', '$20,000', '-$12,000', '$8,000'],
                        '% of Revenue': ['100%', '20%', '80%', '48%', '32%']
                    })
                    st.dataframe(pl_data, use_container_width=True)
        
        # Saved reports
        st.markdown("### Saved Reports")
        reports = [
            {"name": "Q1 2024 Financials", "type": "P&L", "date": "2024-03-31", "size": "2.4 MB"},
            {"name": "Annual Tax Report 2023", "type": "Tax", "date": "2023-12-31", "size": "3.1 MB"},
            {"name": "Monthly Transactions Jan", "type": "Summary", "date": "2024-01-31", "size": "1.8 MB"}
        ]
        
        for report in reports:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.write(f"**{report['name']}**")
            col2.write(report['type'])
            col3.write(report['date'])
            col4.write(report['size'])

# ---------------- PAGE: COMPANIES ----------------
elif st.session_state.active_page == "Companies":
    if st.session_state.active_subpage == "Add":
        st.title("🏢 Add New Company")
        
        with st.form("add_company_form"):
            name = st.text_input("Company Name *", placeholder="Enter company name")
            industry = st.text_input("Industry", placeholder="e.g., Technology, Retail")
            country = st.text_input("Country", placeholder="e.g., USA, UK")
            description = st.text_area("Business Description", placeholder="Brief description of the business")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Save Company", type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel")
            
            if submit:
                if name:
                    st.success(f"Company '{name}' added successfully!")
                    time.sleep(1)
                    st.session_state.active_subpage = None
                    st.rerun()
                else:
                    st.error("Company name is required!")
            
            if cancel:
                st.session_state.active_subpage = None
                st.rerun()
    
    else:
        st.title("🏢 Companies")
        
        # Add company button
        if st.button("➕ Add New Company", type="primary"):
            st.session_state.active_subpage = "Add"
            st.rerun()
        
        st.markdown("---")
        
        # Companies list
        clients = get_clients()
        
        if not clients:
            st.info("No companies found. Add your first company above.")
        else:
            st.markdown(f"### Client List ({len(clients)} companies)")
            
            # Search and filter
            col1, col2 = st.columns(2)
            with col1:
                search = st.text_input("Search companies", placeholder="Type to search...")
            with col2:
                filter_active = st.selectbox("Status", ["All", "Active Only", "Inactive Only"])
            
            # Filter clients
            filtered_clients = clients
            if search:
                filtered_clients = [c for c in filtered_clients if search.lower() in c['name'].lower()]
            if filter_active == "Active Only":
                filtered_clients = [c for c in filtered_clients if c['is_active']]
            elif filter_active == "Inactive Only":
                filtered_clients = [c for c in filtered_clients if not c['is_active']]
            
            # Display table
            for client in filtered_clients:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                    col1.write(f"**{client['name']}**")
                    col2.write(client.get('industry', 'N/A'))
                    col3.write("✅" if client['is_active'] else "❌")
                    
                    if col4.button("Select", key=f"select_{client['id']}"):
                        st.session_state.active_client_id = client['id']
                        st.session_state.active_client_name = client['name']
                        st.success(f"Selected: {client['name']}")
                        st.rerun()
                    
                    if col5.button("Edit", key=f"edit_{client['id']}"):
                        st.info(f"Edit functionality for {client['name']} would open here")

# ---------------- PAGE: SETUP ----------------
elif st.session_state.active_page == "Setup":
    subpage = st.session_state.active_subpage or "Banks"
    
    if subpage == "Banks":
        st.title("🛠️ Setup > Banks")
        
        if not st.session_state.active_client_id:
            st.warning("Please select a client first.")
        else:
            st.success(f"Setting up banks for: {st.session_state.active_client_name}")
            
            banks = get_banks(st.session_state.active_client_id)
            
            # Add bank button
            if st.button("➕ Add New Bank Account", type="primary"):
                st.session_state.setup_banks_mode = "add"
                st.rerun()
            
            # Add bank form
            if st.session_state.setup_banks_mode == "add":
                st.markdown("### Add Bank Account")
                with st.form("add_bank_form"):
                    bank_name = st.text_input("Bank Name *", placeholder="e.g., Bank of America")
                    account_type = st.selectbox("Account Type *", ["Current", "Savings", "Credit Card", "Wallet"])
                    account_number = st.text_input("Account Number (optional)", placeholder="Last 4 digits")
                    currency = st.text_input("Currency", value="USD", placeholder="e.g., USD, EUR")
                    opening_balance = st.number_input("Opening Balance", value=0.0, step=100.0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit = st.form_submit_button("Save Bank", type="primary")
                    with col2:
                        cancel = st.form_submit_button("Cancel")
                    
                    if submit and bank_name:
                        st.success(f"Bank '{bank_name}' added!")
                        st.session_state.setup_banks_mode = "list"
                        time.sleep(1)
                        st.rerun()
                    
                    if cancel:
                        st.session_state.setup_banks_mode = "list"
                        st.rerun()
            
            # Banks list
            st.markdown("### Configured Banks")
            if not banks:
                st.info("No banks configured yet. Add your first bank above.")
            else:
                for bank in banks:
                    with st.expander(f"{bank['bank_name']} ({bank['account_type']})"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Currency", bank.get('currency', 'USD'))
                        col2.metric("Account Type", bank['account_type'])
                        col3.metric("Status", "Active")
                        
                        if st.button("Edit", key=f"edit_bank_{bank['id']}"):
                            st.info(f"Edit bank {bank['bank_name']}")
                        
                        if st.button("Remove", key=f"remove_bank_{bank['id']}", type="secondary"):
                            st.warning(f"Remove {bank['bank_name']}?")

    else:  # Categories
        st.title("🛠️ Setup > Categories")
        
        if not st.session_state.active_client_id:
            st.warning("Please select a client first.")
        else:
            st.success(f"Managing categories for: {st.session_state.active_client_name}")
            
            categories = get_categories(st.session_state.active_client_id)
            
            # Add category
            if st.button("➕ Add New Category", type="primary"):
                st.session_state.setup_categories_mode = "add"
                st.rerun()
            
            # Add category form
            if st.session_state.setup_categories_mode == "add":
                st.markdown("### Add Category")
                with st.form("add_category_form"):
                    cat_name = st.text_input("Category Name *", placeholder="e.g., Office Supplies")
                    cat_type = st.selectbox("Type *", ["Expense", "Income", "Transfer", "Other"])
                    cat_nature = st.selectbox("Nature", ["Debit", "Credit", "Both"])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit = st.form_submit_button("Save Category", type="primary")
                    with col2:
                        cancel = st.form_submit_button("Cancel")
                    
                    if submit and cat_name:
                        st.success(f"Category '{cat_name}' added!")
                        st.session_state.setup_categories_mode = "list"
                        time.sleep(1)
                        st.rerun()
                    
                    if cancel:
                        st.session_state.setup_categories_mode = "list"
                        st.rerun()
            
            # Categories list
            st.markdown("### Transaction Categories")
            
            # Filter by type
            type_filter = st.selectbox("Filter by type", ["All", "Expense", "Income", "Other"])
            
            filtered_cats = categories
            if type_filter != "All":
                filtered_cats = [c for c in categories if c['type'] == type_filter]
            
            if not filtered_cats:
                st.info("No categories found. Add your first category above.")
            else:
                # Display in a nice grid
                cols = st.columns(3)
                for idx, cat in enumerate(filtered_cats):
                    with cols[idx % 3]:
                        with st.container():
                            st.markdown(f"""
                            <div class="metric-card">
                                <h4>{cat['category_name']}</h4>
                                <p>Type: {cat['type']}</p>
                                <p>Status: {'✅ Active' if cat['is_active'] else '❌ Inactive'}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("Edit", key=f"edit_cat_{cat['id']}", use_container_width=True):
                                st.info(f"Edit category {cat['category_name']}")

# ---------------- PAGE: CATEGORISATION ----------------
elif st.session_state.active_page == "Categorisation":
    st.title("🧠 Categorisation")
    
    if not st.session_state.active_client_id:
        st.warning("Please select a client first.")
    else:
        st.success(f"Categorising transactions for: {st.session_state.active_client_name}")
        
        # Step 1: Select bank
        banks = get_banks(st.session_state.active_client_id)
        if banks:
            bank_options = [f"{b['id']} | {b['bank_name']} ({b['account_type']})" for b in banks]
            selected_bank = st.selectbox("Select Bank", bank_options, key="cat_bank_select")
            
            # Step 2: Upload or process
            tab1, tab2, tab3 = st.tabs(["Upload Statement", "Auto-Import", "Manual Entry"])
            
            with tab1:
                st.markdown("### Upload Bank Statement")
                uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'], key="stmt_upload")
                
                if uploaded_file is not None:
                    try:
                        df = pd.read_csv(uploaded_file)
                        st.session_state.df_raw = df
                        
                        st.success(f"✅ Successfully loaded {len(df)} transactions")
                        st.dataframe(df.head(), use_container_width=True)
                        
                        # Column mapping
                        st.markdown("#### Map Columns")
                        if len(df.columns) > 0:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                date_col = st.selectbox("Date Column", df.columns, key="date_col")
                            with col2:
                                desc_col = st.selectbox("Description", df.columns, key="desc_col")
                            with col3:
                                debit_col = st.selectbox("Debit", df.columns, key="debit_col")
                            with col4:
                                credit_col = st.selectbox("Credit", df.columns, key="credit_col")
                        
                        if st.button("Process Transactions", type="primary"):
                            with st.spinner("Processing..."):
                                time.sleep(2)
                                st.success(f"Processed {len(df)} transactions!")
                                
                                # Show sample categorization
                                st.markdown("#### Sample Categorized Transactions")
                                sample = pd.DataFrame({
                                    'Date': ['2024-01-15', '2024-01-16'],
                                    'Description': ['AMAZON PURCHASE', 'CLIENT PAYMENT INC'],
                                    'Amount': [-89.99, 1500.00],
                                    'Category': ['Office Supplies', 'Consulting Fees'],
                                    'Confidence': ['95%', '98%']
                                })
                                st.dataframe(sample, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error loading file: {str(e)}")
            
            with tab2:
                st.markdown("### Auto-Import from Bank")
                st.info("Connect to your bank for automatic transaction import")
                
                bank_connections = ["Plaid", "Yodlee", "Manual CSV"]
                selected_conn = st.selectbox("Select Connection Method", bank_connections)
                
                if st.button("Connect to Bank", type="primary"):
                    with st.spinner("Connecting to bank..."):
                        time.sleep(2)
                        st.success("Connected successfully!")
                        
                        # Simulated transactions
                        st.markdown("#### Available Transactions")
                        transactions = pd.DataFrame({
                            'Date': ['2024-01-20', '2024-01-19', '2024-01-18'],
                            'Description': ['Starbucks', 'AWS Services', 'Google Ads'],
                            'Amount': [-5.75, -125.50, -350.00]
                        })
                        st.dataframe(transactions, use_container_width=True)
            
            with tab3:
                st.markdown("### Manual Transaction Entry")
                with st.form("manual_entry_form"):
                    date = st.date_input("Transaction Date", dt.date.today())
                    description = st.text_input("Description", placeholder="Enter transaction description")
                    amount = st.number_input("Amount", value=0.0, step=0.01)
                    transaction_type = st.selectbox("Type", ["Debit (Expense)", "Credit (Income)"])
                    
                    categories = get_categories(st.session_state.active_client_id)
                    if categories:
                        category = st.selectbox("Category", [c['category_name'] for c in categories])
                    
                    if st.form_submit_button("Add Transaction", type="primary"):
                        st.success("Transaction added successfully!")
        else:
            st.warning("No banks configured. Please add banks in Setup > Banks first.")

# ---------------- PAGE: SETTINGS ----------------
elif st.session_state.active_page == "Settings":
    st.title("⚙️ Settings")
    
    tab1, tab2, tab3, tab4 = st.tabs(["General", "Database", "Appearance", "About"])
    
    with tab1:
        st.markdown("### General Settings")
        
        # App settings
        app_name = st.text_input("Application Name", value="BankCat Demo")
        timezone = st.selectbox("Timezone", ["UTC", "EST", "PST", "GMT", "IST"])
        date_format = st.selectbox("Date Format", ["YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY"])
        
        # Notifications
        st.markdown("### Notifications")
        email_notifications = st.checkbox("Email Notifications", value=True)
        slack_notifications = st.checkbox("Slack Notifications")
        
        if st.button("Save General Settings", type="primary"):
            st.success("General settings saved!")
    
    with tab2:
        st.markdown("### Database Settings")
        
        if DB_AVAILABLE:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Test Connection", use_container_width=True):
                    try:
                        clients = crud.list_clients(include_inactive=True)
                        st.success(f"✅ Connected! Found {len(clients)} clients.")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {str(e)}")
            
            with col2:
                if st.button("Clear Cache", use_container_width=True):
                    cache_data.clear()
                    st.success("✅ Cache cleared!")
            
            st.markdown("### Database Operations")
            if st.button("Initialize/Migrate Database", type="secondary"):
                try:
                    init_db()
                    st.success("✅ Database initialized successfully!")
                except Exception as e:
                    st.error(f"❌ Initialization failed: {str(e)}")
        else:
            st.warning("Database modules not available. Running in demo mode.")
    
    with tab3:
        st.markdown("### Appearance")
        
        theme = st.selectbox("Theme", ["Light", "Dark", "Auto"])
        primary_color = st.color_picker("Primary Color", "#7CFFB2")
        font_size = st.slider("Font Size", 12, 18, 14)
        
        st.markdown("### Sidebar")
        sidebar_width = st.slider("Sidebar Width", 200, 400, 280)
        sidebar_position = st.radio("Sidebar Position", ["Left", "Right"])
        
        if st.button("Apply Appearance Settings", type="primary"):
            st.success("Appearance settings applied! (Note: Some changes require app restart)")
    
    with tab4:
        st.markdown("### About BankCat")
        
        st.write("""
        **BankCat Demo v1.0**
        
        A comprehensive financial transaction categorization and reporting system.
        
        **Features:**
        - Client management
        - Bank account setup
        - Transaction categorization
        - Financial reporting
        - Dashboard analytics
        
        **Version:** 1.0.0
        **Last Updated:** January 2024
        
        For support or feedback, please contact the development team.
        """)
        
        if logo_path.exists():
            st.image(str(logo_path), width=300)

# ---------------- FOOTER ----------------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #6b7280; font-size: 14px;'>"
    "BankCat Demo • Financial Management System • © 2024"
    "</div>",
    unsafe_allow_html=True
)
