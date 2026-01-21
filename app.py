import streamlit as st

# Local imports
from src.db import ping_db

st.set_page_config(page_title="BankCat Demo", layout="wide")

st.title("BankCat Demo ✅")
st.write("Step-2: Persistent database connection test (Supabase/Neon Postgres).")

st.divider()

with st.expander("Database Status", expanded=True):
    st.caption("This checks whether DATABASE_URL is set in Streamlit Secrets and whether the DB is reachable.")
    if st.button("Test DB Connection"):
        try:
            val = ping_db()
            st.success(f"DB Connected ✅  (select 1 = {val})")
        except Exception as e:
            st.error("DB connection failed ❌")
            st.code(str(e))

st.divider()

st.info("Next: We will create tables (clients, banks, categories, draft/committed, commits) and build the Intro screen.")
