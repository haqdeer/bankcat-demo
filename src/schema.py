# src/schema.py
from sqlalchemy import text
from src.db import get_engine


def init_db() -> str:
    """
    Create/verify tables + upgrade-safe migrations.
    Safe to run multiple times.
    """
    engine = get_engine()

    with engine.begin() as conn:
        # ---------------------------
        # 1) Masters
        # ---------------------------
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

        # ---------------------------
        # 2) Draft Batches
        # ---------------------------
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

        # ---------------------------
        # 3) Draft Transactions
        # ---------------------------
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

        # ---------------------------
        # 4) Vendor Memory
        # ---------------------------
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

        # ---------------------------
        # 5) Keyword Model (IMPORTANT for commit learning)
        # ---------------------------
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

        # Upgrade-safe ensures (even if table existed before)
        conn.execute(text("ALTER TABLE keyword_model ADD COLUMN IF NOT EXISTS weight NUMERIC NOT NULL DEFAULT 0;"))
        conn.execute(text("ALTER TABLE keyword_model ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();"))

        # ---------------------------
        # 6) Commits (create minimal + alter missing cols)
        # ---------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS commits (
            id SERIAL PRIMARY KEY,
            client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id INT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL
        );
        """))

        conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS committed_by TEXT;"))
        conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS committed_at TIMESTAMPTZ DEFAULT now();"))
        conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS rows_committed INT NOT NULL DEFAULT 0;"))
        conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS accuracy NUMERIC;"))
        conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS notes TEXT;"))

        # ---------------------------
        # 7) Committed Transactions
        # ---------------------------
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

            created_at TIMESTAMPTZ DEFAULT now()
        );
        """))

        # Upgrade-safe: these were missing in your DB earlier
        conn.execute(text("ALTER TABLE transactions_committed ADD COLUMN IF NOT EXISTS suggested_category TEXT;"))
        conn.execute(text("ALTER TABLE transactions_committed ADD COLUMN IF NOT EXISTS suggested_vendor TEXT;"))
        conn.execute(text("ALTER TABLE transactions_committed ADD COLUMN IF NOT EXISTS confidence NUMERIC;"))
        conn.execute(text("ALTER TABLE transactions_committed ADD COLUMN IF NOT EXISTS reason TEXT;"))

        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_committed_client_bank_period
        ON transactions_committed(client_id, bank_id, period);
        """))

        # ---------------------------
        # 8) Backfill draft_batches (safe)
        # ---------------------------
        conn.execute(text("""
        INSERT INTO draft_batches (client_id, bank_id, period, status)
        SELECT DISTINCT client_id, bank_id, period, 'Imported'
        FROM transactions_draft
        ON CONFLICT (client_id, bank_id, period) DO NOTHING;
        """))

    return "DB schema initialized + migrated (tables created/verified + columns ensured)."
