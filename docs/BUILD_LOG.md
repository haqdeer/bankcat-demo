## 2026-01-26
### What we built
- Hid Streamlit default chrome, removed in-page page titles, and aligned sidebar toggling to the custom header only.
- Redesigned the Categorisation page into the requested single-list + single-table workflow with unified status/actions.
- Added draft/commit summary helpers for bank+period scoped views.

### Why
- Match the updated UI requirements and keep categorisation flow consistent and stable for a selected bank/period.

### Files changed
- app.py
- src/crud.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Fixed the persistent header/ sidebar overlap and made the header show the active page title in a full-height green center section.
- Switched sidebar navigation to immediate, clickable buttons with active styling driven by session state.
- Made DB schema verification deterministic and stable between clicks, allowing known extras like updated_at.

### Why
- Ensure the header is always visible, navigation highlights correctly, and schema checks do not fluctuate.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Fixed logo loading to support JPEG assets without UnicodeDecodeError.

### Why
- Ensure the header and Home logo render when using a JPEG asset in assets/.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Added a fixed three-section top header and refreshed sidebar styling with icons and active states.

### Why
- Deliver the requested layout with a persistent header, search/theme/fullscreen controls, and branded sidebar styling.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Stabilized navigation, inline Setup/Companies forms, and schema verification expectations.

### Why
- Resolve form reliability issues, remove dialog errors, and align schema checks with DB reality.

### Files changed
- app.py
- docs/DB_SCHEMA_TRUTH.md
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Reworked navigation into standalone pages with inline setup forms and safer edit prefill logic.

### Why
- Fix navigation reliability issues and remove modal/dialog errors while keeping workflows intact.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Updated sidebar navigation with Settings subpages and inline setup forms to avoid dialog errors.

### Why
- Fix navigation flow and remove modal/dialog issues while keeping existing workflows intact.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Refreshed CRUD helpers for navigation workflows and schema verification.

### Why
- Ensure Companies/Setup flows and schema checks work correctly after the navigation update.

### Files changed
- src/crud.py
- docs/BUILD_LOG.md

### Tests done
- Not run (helper updates only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Refreshed CRUD helpers needed for grouped navigation and schema verification screens.

### Why
- Ensure Companies/Setup workflows and schema checks work correctly after the navigation update.

### Files changed
- src/crud.py
- docs/BUILD_LOG.md

### Tests done
- Not run (helper updates only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Sidebar navigation restructured + Setup modal CRUD + client selector moved to Home + Mapping tab removed + Reports placeholder.

### Why
- Align navigation cleanup with grouped sidebar and placeholder Reports screen.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Sidebar navigation restructured + Setup modal CRUD + client selector moved to Home + Mapping tab removed + Reports placeholder.

### Why
- Provide grouped navigation, keep workflows together, and simplify client selection across screens.

### Files changed
- app.py
- src/crud.py
- docs/DB_SCHEMA_TRUTH.md
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Added sidebar navigation tabs and reorganized screens (no feature change).

### Why
- Make navigation simpler and keep utilities under Settings without removing any functionality.

### Files changed
- app.py
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Fix ambiguous period query in dashboard.

### Why
- Resolve Postgres ambiguity error when loading committed periods with joined tables.

### Files changed
- src/crud.py
- docs/BUILD_LOG.md

### Tests done
- Not run (requires DB connection).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Updated vendor_memory unique constraint to use vendor_key consistently in schema and migrations.

### Why
- Align constraint with the canonical vendor_key column and avoid incorrect vendor/vendor_name checks.

### Files changed
- src/schema.py
- docs/migrations/20260126_commit_dedupe.sql
- docs/DATA_MODEL.md
- docs/BUILD_LOG.md

### Tests done
- Not run (schema change only).

### Result
- Pending manual verification after migration.

## 2026-01-26
### What we built
- Added commit de-duplication using commits.is_active and updated reporting queries to only show active commits.
- Fixed vendor_memory unique constraint to target the correct vendor column and added a migration.

### Why
- Prevent multiple commits for the same client/bank/period and ensure vendor_memory uniqueness matches the real schema.

### Files changed
- src/schema.py
- src/crud.py
- docs/migrations/20260126_commit_dedupe.sql
- docs/DATA_MODEL.md
- docs/BUILD_LOG.md

### Tests done
- Not run (requires DB migration and committed data).

### Result
- Pending manual verification after migration.

## 2026-01-23
### What we built
- Added Step-8 committed dashboard with bank/date/period filters, committed tables, P&L summary, and commit metrics.

### Why
- Provide reporting views over committed transactions for review and accuracy tracking.

### Files changed
- app.py
- src/crud.py
- docs/BUILD_LOG.md
- docs/SOP.md

### Tests done
- Not run (requires a DB with committed data in Streamlit).

### Result
- Pending manual verification in the app UI.

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
### Step-7: Commit / Lock
- User reviews draft and clicks Commit
- Draft rows are copied to committed table (read-only)
- System learns:
  - Vendor → Category (vendor_memory)
  - Keywords → Category (keyword_model)
- Accuracy metrics updated per commit
## 2026-01-22
### What we built
- Step-7 Commit/Lock workflow + learning
- Draft status tracking via draft_batches (Imported → System Categorised → User Completed → Committed)

### Files changed
- app.py
- src/crud.py
- src/schema.py

### Tests done
- Commit blocked when final_category missing
- Commit succeeded after completing review; committed sample visible

### Next
- Dashboard: P&L + Accuracy metrics from commits + committed data
## 2026-01-26
### What we built
- Centered and enlarged the BankCat logo on the Home page.

### Why
- Match the updated branding placement request for the landing experience.

### Files changed
- app.py
- assets/bankcat-logo.svg
- docs/BUILD_LOG.md

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.

## 2026-01-26
### What we built
- Simplified sidebar navigation to a single accordion-style Companies/Setup section and restored bank masked account handling.
- Updated schema verification to compare doc truth vs live tables/columns, and aligned schema docs with Supabase columns.
- Added the BankCat logo to the Home page.

### Why
- Remove duplicated navigation, fix bank editing/display regressions, and eliminate false schema mismatch warnings.

### Files changed
- app.py
- src/crud.py
- src/engine.py
- src/schema.py
- docs/DB_SCHEMA_TRUTH.md
- docs/BUILD_LOG.md
- assets/bankcat-logo.svg

### Tests done
- Not run (UI change only).

### Result
- Pending manual verification.
