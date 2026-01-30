# src/loader.py
import streamlit as st
from streamlit.components.v1 import html
import base64
from pathlib import Path

def get_animated_svg_html(svg_path: Path) -> str:
    """Read SVG file and return HTML with embedded animations"""
    if not svg_path.exists():
        return "<div>Loader SVG not found</div>"
    
    # Read SVG content
    svg_content = svg_path.read_text(encoding='utf-8')
    
    # Create animated HTML
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @keyframes eyeBlink {{
                0%, 100% {{ 
                    opacity: 0.3; 
                    transform: scale(0.8); 
                    filter: drop-shadow(0 0 2px rgba(124, 255, 178, 0.3));
                }}
                50% {{ 
                    opacity: 1; 
                    transform: scale(1); 
                    filter: drop-shadow(0 0 10px rgba(124, 255, 178, 0.8));
                }}
            }}
            
            @keyframes faceRotate {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            @keyframes containerPulse {{
                0%, 100% {{ transform: scale(1); }}
                50% {{ transform: scale(1.02); }}
            }}
            
            .loader-container {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
                height: 100vh;
                animation: containerPulse 3s ease-in-out infinite;
            }}
            
            .face-wrapper {{
                position: relative;
                width: 200px;
                height: 200px;
                animation: faceRotate 4s linear infinite;
                animation-delay: 1s;
            }}
            
            .face-svg {{
                width: 100%;
                height: 100%;
                filter: drop-shadow(0 0 15px rgba(0, 0, 0, 0.1));
            }}
            
            .eye-glow {{
                position: absolute;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: radial-gradient(circle, #7CFFB2 0%, #00FF7A 70%, transparent 100%);
                animation: eyeBlink 2s ease-in-out infinite;
                box-shadow: 0 0 15px rgba(124, 255, 178, 0.7);
            }}
            
            .eye-left {{
                top: 38%;
                left: 33%;
            }}
            
            .eye-right {{
                top: 38%;
                right: 33%;
            }}
            
            .loader-text {{
                position: absolute;
                bottom: -50px;
                width: 100%;
                text-align: center;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #4a5568;
                font-size: 14px;
                letter-spacing: 2px;
                animation: eyeBlink 2.5s ease-in-out infinite;
            }}
        </style>
    </head>
    <body>
        <div class="loader-container">
            <div class="face-wrapper">
                <!-- Original SVG face -->
                <div class="face-svg">
                    {svg_content}
                </div>
                <!-- Animated eye glows -->
                <div class="eye-glow eye-left"></div>
                <div class="eye-glow eye-right"></div>
                <div class="loader-text">LOADING...</div>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return html_content


def show_loader(duration_ms=1200, location="full"):
    """
    Show animated loader
    
    Parameters:
    -----------
    duration_ms : int
        Duration to show loader in milliseconds
    location : str
        "full" - full page loader (for app startup)
        "main" - main area loader (for page transitions)
    """
    
    # Set up container based on location
    if location == "full":
        container = st.container()
        with container:
            # Clear everything and show full page loader
            st.markdown(
                """
                <style>
                .stApp { 
                    display: flex; 
                    justify-content: center; 
                    align-items: center; 
                    height: 100vh;
                }
                #MainMenu { visibility: hidden; }
                footer { visibility: hidden; }
                </style>
                """,
                unsafe_allow_html=True
            )
            
            svg_path = Path(__file__).parent.parent / "assets" / "bankcat-loader.gif.svg"
            html_content = get_animated_svg_html(svg_path)
            
            # Use html component to render animated SVG
            html(html_content, height=400)
            
            # Add script to auto-remove after duration
            html(
                f"""
                <script>
                setTimeout(function() {{
                    window.frameElement.parentElement.style.display = 'none';
                }}, {duration_ms});
                </script>
                """,
                height=0
            )
            
            return container
            
    elif location == "main":
        # Create a placeholder in main area
        placeholder = st.empty()
        with placeholder.container():
            st.markdown(
                """
                <style>
                .main-loader { 
                    display: flex; 
                    justify-content: center; 
                    align-items: center; 
                    height: 70vh;
                    width: 100%;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                svg_path = Path(__file__).parent.parent / "assets" / "bankcat-loader.gif.svg"
                html_content = get_animated_svg_html(svg_path)
                html(html_content, height=300)
        
        return placeholder


def simulate_loading(duration_ms=800):
    """Simulate loading with a progress bar"""
    import time
    
    progress_text = "Loading..."
    progress_bar = st.progress(0, text=progress_text)
    
    for percent_complete in range(100):
        time.sleep(duration_ms / 1000 / 100)  # Convert to seconds
        progress_bar.progress(percent_complete + 1, text=progress_text)
    
    time.sleep(0.2)
    progress_bar.empty()


# Alternative simpler loader using CSS only
def show_simple_loader():
    """Show a simple CSS-based loader"""
    st.markdown("""
    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }
    
    .simple-loader {
        border: 8px solid #f3f3f3;
        border-top: 8px solid #7CFFB2;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        animation: spin 1.5s linear infinite, pulse 2s ease-in-out infinite;
        margin: 100px auto;
    }
    </style>
    
    <div class="simple-loader"></div>
    """, unsafe_allow_html=True)
