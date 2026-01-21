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
### Fix applied
- Switched Supabase direct host (IPv6) to Supavisor/pooler connection string (IPv4 compatible)
- Added sslmode=require in DATABASE_URL

### Why
- Streamlit Community Cloud had IPv6 connectivity issue causing psycopg2 “Cannot assign requested address”
## 2026-01-21
### What we built
- Added DB schema initializer (core MVP tables)
- Added “Initialize Database” button in Streamlit UI

### Why
- Required to persist multi-client masters and transactions for demo usage

### Files changed
- src/schema.py
- app.py

### Tests done
- Clicked “Initialize Database (Create Tables)” → success message

### Next step
- Build Intro screen UI to add Clients, Banks, Categories into DB
