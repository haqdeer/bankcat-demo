# src/db.py - COMPLETE FILE
import os
from sqlalchemy import create_engine, text
import streamlit as st

def get_engine():
    """Get database engine with retry logic"""
    # Try multiple possible secret names
    secret_names = ["DATABASE_URL", "db_url", "DB_URL", "database_url"]
    db_url = None
    
    for secret_name in secret_names:
        try:
            db_url = st.secrets.get(secret_name)
            if db_url:
                break
        except:
            pass
    
    if not db_url:
        # Fallback to environment variable
        db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL not found in Streamlit secrets or environment variables. "
            "Please add it to .streamlit/secrets.toml"
        )
    
    # Ensure proper connection string
    if "postgresql://" not in db_url and "postgres://" in db_url:
        db_url = db_url.replace("postgres://", "postgresql://")
    
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)

def ping_db():
    """Test database connection"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            return result.scalar() == 1
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return False
