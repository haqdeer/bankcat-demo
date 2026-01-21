## 2026-01-21
### What we built
- Initial Streamlit app deployed on Streamlit Community Cloud

### Why
- To establish a working web app before adding business logic

### Files changed
- app.py
- requirements.txt

### Tests done
- Opened live app, UI loaded successfully

### Next step
- Connect Postgres database (Supabase or Neon)
## 2026-01-21
### What we built
- Connected Streamlit app to Supabase Postgres using DATABASE_URL secret
- Added DB ping test button

### Why
- Persistent storage is required for multi-client usage (4–5 clients)

### Files changed
- app.py
- src/db.py

### Tests done
- Clicked “Test DB Connection” → success

### Next step
- Create core tables (clients, banks, categories, draft/committed, commits)
