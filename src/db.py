import os
from sqlalchemy import create_engine, text

def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set. Add it in Streamlit Secrets.")
    return create_engine(db_url, pool_pre_ping=True)

def ping_db():
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(text("select 1")).scalar()
