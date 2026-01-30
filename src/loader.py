# src/loader.py
import streamlit as st
import time
from pathlib import Path
import base64

def get_svg_content():
    """Get SVG content with embedded animations"""
    svg_path = Path(__file__).parent.parent / "assets" / "bankcat-loader.gif.svg"
    
    if not svg_path.exists():
        # Fallback loader if SVG not found
        return """
        <div style="text-align: center;">
            <div style="width: 80px; height: 80px; margin: 0 auto; 
                border: 6px solid #f3f3f3; border-top: 6px solid #7CFFB2; 
                border-radius: 50%; animation: spin 1.5s linear infinite;">
            </div>
            <p style="color: #4a5568; margin-top: 20px;">Loading...</p>
        </div>
        """
    
    # Read and encode SVG
    svg_bytes = svg_path.read_bytes()
    svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
    
    return f"""
    <div style="text-align: center;">
        <img src="data:image/svg+xml;base64,{svg_base64}" 
             class="svg-loader" 
             alt="Loading..."
             style="width: 180px; height: 180px;"/>
        <div class="loading-text">LOADING BANKCAT...</div>
    </div>
    """

def show_full_page_loader():
    """Show full page loader on app startup"""
    # Create a container for loader
    loader_container = st.empty()
    
    with loader_container.container():
        # Hide Streamlit's default UI
        st.markdown("""
        <style>
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }
        .stApp > header:first-child { display: none; }
        </style>
        """, unsafe_allow_html=True)
        
        # Show loader
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown(
                f"""
                <div class="full-page-loader">
                    {get_svg_content()}
                </div>
                """,
                unsafe_allow_html=True
            )
    
    return loader_container

def show_page_transition_loader():
    """Show loader during page transitions"""
    loader_placeholder = st.empty()
    
    with loader_placeholder.container():
        # Clear the main area
        st.markdown(
            f"""
            <div class="page-loader">
                {get_svg_content()}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    return loader_placeholder

def simulate_data_loading(duration=1.5):
    """Simulate data loading with progress"""
    import streamlit as st
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(100):
        # Update progress bar
        progress_bar.progress(i + 1)
        
        # Update status text
        if i < 30:
            status_text.text("Loading data...")
        elif i < 60:
            status_text.text("Processing transactions...")
        elif i < 90:
            status_text.text("Finalizing...")
        else:
            status_text.text("Almost done...")
        
        # Small delay
        time.sleep(duration / 100)
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
