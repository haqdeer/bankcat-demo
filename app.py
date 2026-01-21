import streamlit as st

from src.db import ping_db
from src.schema import init_db

st.set_page_config(page_title="BankCat Demo", layout="wide")

st.title("BankCat Demo ✅")
st.write("MVP: DB connect + schema init (tables).")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Step A: Test DB")
    if st.button("Test DB Connection"):
        try:
            val = ping_db()
            st.success(f"DB Connected ✅ (select 1 = {val})")
        except Exception as e:
            st.error(f"DB connection failed ❌\n\n{e}")

with col2:
    st.subheader("Step B: Initialize DB (Create Tables)")
    if st.button("Initialize Database (Create Tables)"):
        try:
            msg = init_db()
            st.success(msg)
        except Exception as e:
            st.error(f"DB init failed ❌\n\n{e}")

st.divider()
st.info("Next: We'll build the Intro screen to add Clients, Banks, Categories.")
