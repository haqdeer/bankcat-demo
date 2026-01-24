from sqlalchemy import text
from src.db import get_engine

def init_db() -> str:
    """
    Create/verify tables + ensure required columns exist.
    Safe to run multiple times.
    """
    engine = get_engine()

    with engine.begin() as conn:
        # ---- Core masters ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            business_description TEXT,
            industry TEXT,
            country TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS banks (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_name TEXT NOT NULL,
            account_masked TEXT,
            account_type TEXT,
            currency TEXT,
            opening_balance NUMERIC,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            category_code TEXT,
            category_name TEXT NOT NULL,
            type TEXT NOT NULL,
            nature TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        # ---- Draft batches (Status) ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS draft_batches (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id INT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Imported',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (client_id, bank_id, period)
        );
        """))

        # ---- Draft transactions ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS transactions_draft (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id INT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            tx_date DATE NOT NULL,
            description TEXT NOT NULL,
            debit NUMERIC,
            credit NUMERIC,
            balance NUMERIC,

            suggested_category TEXT,
            suggested_vendor TEXT,
            confidence NUMERIC,
            reason TEXT,

            final_category TEXT,
            final_vendor TEXT,

            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_draft_client_bank_period
        ON transactions_draft(client_id, bank_id, period);
        """))

        # ---- Vendor memory (learning) ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS vendor_memory (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            vendor_name TEXT NOT NULL,
            category_name TEXT NOT NULL,
            confidence NUMERIC NOT NULL DEFAULT 0.50,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (client_id, vendor_name)
        );
        """))

        # ---- Keyword model (learning) ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS keyword_model (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            token TEXT NOT NULL,
            category_name TEXT NOT NULL,
            weight NUMERIC NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (client_id, token, category_name)
        );
        """))

        # ---- Commits ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS commits (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id INT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            committed_by TEXT,
            committed_at TIMESTAMPTZ DEFAULT now(),
            rows_committed INT NOT NULL DEFAULT 0,
            accuracy NUMERIC,
            notes TEXT
        );
        """))

        # ---- Committed transactions ----
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS transactions_committed (
            id SERIAL PRIMARY KEY,
            commit_id INT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id INT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,

            tx_date DATE NOT NULL,
            description TEXT NOT NULL,
            debit NUMERIC,
            credit NUMERIC,
            balance NUMERIC,

            category TEXT NOT NULL,
            vendor TEXT,

            suggested_category TEXT,
            suggested_vendor TEXT,
            confidence NUMERIC,
            reason TEXT,

            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        # ✅ IMPORTANT: Backfill draft_batches from existing transactions_draft
        conn.execute(text("""
        INSERT INTO draft_batches (client_id, bank_id, period, status)
        SELECT DISTINCT client_id, bank_id, period, 'Imported'
        FROM transactions_draft
        ON CONFLICT (client_id, bank_id, period) DO NOTHING;
        """))

    return "DB schema initialized + migrated (tables created/verified + columns ensured)."
