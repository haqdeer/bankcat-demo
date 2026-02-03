# src/loader.py
import streamlit as st
import time

def show_progress_loader(message="Processing..."):
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
                    border: 4px solid #f3f3f3;
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

def simulate_data_loading(duration=1.5):
    """Simulate data loading with progress"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(100):
        progress_bar.progress(i + 1)
        
        if i < 30:
            status_text.text("Loading data...")
        elif i < 60:
            status_text.text("Processing transactions...")
        elif i < 90:
            status_text.text("Finalizing...")
        else:
            status_text.text("Almost done...")
        
        time.sleep(duration / 100)
    
    progress_bar.empty()
    status_text.empty()
