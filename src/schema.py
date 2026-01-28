# src/schema.py
from sqlalchemy import text
from src.crud import get_engine


def _do(conn, sql: str):
    conn.execute(text(sql))


def init_db():
    """
    Idempotent schema initializer + migrator.
    Safe to run multiple times.
    """
    engine = get_engine()
    with engine.begin() as conn:
        # --- clients
        _do(conn, """
        CREATE TABLE IF NOT EXISTS clients (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT,
            country TEXT,
            business_description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        # --- banks
        _do(conn, """
        CREATE TABLE IF NOT EXISTS banks (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_name TEXT NOT NULL,
            account_masked TEXT,
            account_type TEXT NOT NULL DEFAULT 'Current',
            currency TEXT,
            opening_balance NUMERIC(18,2),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        # --- categories
        _do(conn, """
        CREATE TABLE IF NOT EXISTS categories (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            category_code TEXT,
            category_name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('Income','Expense','Other')),
            nature TEXT NOT NULL DEFAULT 'Any',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        # --- transactions_draft
        _do(conn, """
        CREATE TABLE IF NOT EXISTS transactions_draft (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id BIGINT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL, -- YYYY-MM
            tx_date DATE NOT NULL,
            description TEXT NOT NULL,
            debit NUMERIC(18,2) DEFAULT 0,
            credit NUMERIC(18,2) DEFAULT 0,
            balance NUMERIC(18,2),
            final_category TEXT,
            final_vendor TEXT,
            suggested_category TEXT,
            suggested_vendor TEXT,
            confidence NUMERIC(5,4),
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'NOT_CATEGORISED', -- NOT_CATEGORISED|SYSTEM_SUGGESTED|USER_FINALISED
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        _do(conn, """
        CREATE INDEX IF NOT EXISTS idx_draft_lookup
        ON transactions_draft (client_id, bank_id, period);
        """)

        # --- commits
        _do(conn, """
        CREATE TABLE IF NOT EXISTS commits (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id BIGINT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            committed_by TEXT,
            rows_committed INT NOT NULL DEFAULT 0,
            accuracy NUMERIC(6,4),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        _do(conn, """
        CREATE INDEX IF NOT EXISTS idx_commits_lookup
        ON commits (client_id, bank_id, period);
        """)

        # --- transactions_committed
        _do(conn, """
        CREATE TABLE IF NOT EXISTS transactions_committed (
            id BIGSERIAL PRIMARY KEY,
            commit_id BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            bank_id BIGINT NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            tx_date DATE NOT NULL,
            description TEXT NOT NULL,
            debit NUMERIC(18,2) DEFAULT 0,
            credit NUMERIC(18,2) DEFAULT 0,
            balance NUMERIC(18,2),
            category TEXT NOT NULL,
            vendor TEXT,
            suggested_category TEXT,
            suggested_vendor TEXT,
            confidence NUMERIC(5,4),
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        _do(conn, """
        CREATE INDEX IF NOT EXISTS idx_committed_lookup
        ON transactions_committed (client_id, bank_id, period);
        """)

        # --- vendor_memory
        _do(conn, """
        CREATE TABLE IF NOT EXISTS vendor_memory (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            vendor_key TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence NUMERIC(6,4) NOT NULL DEFAULT 0.70,
            times_confirmed INT NOT NULL DEFAULT 1,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        # Unique (client + vendor_key)
        _do(conn, "ALTER TABLE public.vendor_memory DROP CONSTRAINT IF EXISTS vendor_memory_client_vendor_uniq;")
        _do(conn, """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'vendor_memory_client_vendor_uniq'
            ) THEN
                ALTER TABLE public.vendor_memory
                ADD CONSTRAINT vendor_memory_client_vendor_uniq
                UNIQUE (client_id, vendor_key);
            END IF;
        END $$;
        """)

        # --- keyword_model (IMPORTANT: uses column name 'category' in your current DB)
        _do(conn, """
        CREATE TABLE IF NOT EXISTS keyword_model (
            id BIGSERIAL PRIMARY KEY,
            client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            token TEXT NOT NULL,
            category TEXT NOT NULL,
            weight NUMERIC(10,4) NOT NULL DEFAULT 0,
            times_used INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)

        # Unique (client + token + category)
        _do(conn, """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'keyword_model_client_token_cat_uniq'
            ) THEN
                ALTER TABLE public.keyword_model
                ADD CONSTRAINT keyword_model_client_token_cat_uniq
                UNIQUE (client_id, token, category);
            END IF;
        END $$;
        """)

        # --- migrations for older DBs (safe adds)
        _do(conn, "ALTER TABLE public.commits ADD COLUMN IF NOT EXISTS committed_by TEXT;")
        _do(conn, "ALTER TABLE public.commits ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;")
        _do(conn, "ALTER TABLE public.transactions_committed ADD COLUMN IF NOT EXISTS suggested_category TEXT;")
        _do(conn, "ALTER TABLE public.transactions_committed ADD COLUMN IF NOT EXISTS suggested_vendor TEXT;")
        _do(conn, "ALTER TABLE public.transactions_committed ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,4);")
        _do(conn, "ALTER TABLE public.transactions_committed ADD COLUMN IF NOT EXISTS reason TEXT;")

        _do(conn, "ALTER TABLE public.keyword_model ADD COLUMN IF NOT EXISTS times_used INT NOT NULL DEFAULT 0;")
        _do(conn, "ALTER TABLE public.keyword_model ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();")
        _do(conn, "ALTER TABLE public.banks ADD COLUMN IF NOT EXISTS account_masked TEXT;")
        _do(conn, "ALTER TABLE public.vendor_memory ADD COLUMN IF NOT EXISTS vendor_key TEXT;")
        _do(conn, "ALTER TABLE public.vendor_memory ADD COLUMN IF NOT EXISTS category TEXT;")
        _do(conn, "ALTER TABLE public.vendor_memory ADD COLUMN IF NOT EXISTS times_confirmed INT NOT NULL DEFAULT 1;")
        _do(conn, "ALTER TABLE public.vendor_memory ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ NOT NULL DEFAULT now();")

    return True
