### What we built
- Added Edit + Disable/Enable + Safe Delete for Clients/Banks/Categories (soft-delete)
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
### What we built
- Intro UI: Create/list Clients, Banks, Categories (saved in Postgres)

### Files changed
- app.py
- src/crud.py

### Tests done
- Created 1 client, added 1 bank, added 3 categories via UI
## 2026-01-22
### What we built
- Step-6 Suggest + Review screen
- Added suggestion engine (rules + nature + account type)
- Added safe vendor_memory handling to prevent app crash

### Why
- Enable human-in-the-loop categorisation before commit

### Files changed
- app.py
- src/engine.py
- src/crud.py
- src/schema.py

### Tests done
- Loaded CSV draft and processed suggestions successfully
- Edited final_category and saved changes to draft

### Known issues / next step
- Restore full Step-5 Upload→Draft UI together with Step-6 on same page
- Add Step-7 Commit + Learning + Accuracy metrics
## 2026-01-22
### What we built
- Restored Step-5 Upload→Map→Standardize→Save Draft UI
- Kept Step-6 Suggest→Review UI together (single page, stable)

### Files changed
- app.py

### Tests done
- Uploaded CSV and saved draft successfully
- Processed suggestions and saved review (final_category/final_vendor)

### Next
- Step-7 Commit/Lock + Learning (vendor_memory + keyword_model) + Accuracy metrics
