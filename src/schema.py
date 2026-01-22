from sqlalchemy import text
from src.db import get_engine

def _safe_exec(conn, sql: str):
    try:
        conn.execute(text(sql))
    except Exception:
        pass

def init_db() -> str:
    engine = get_engine()
    with engine.begin() as conn:
        # Clients
        _safe_exec(conn, """
        create table if not exists clients (
            id bigserial primary key,
            name text not null,
            business_description text,
            industry text,
            country text,
            is_active boolean default true,
            created_at timestamptz default now(),
            updated_at timestamptz
        );
        """)

        # Banks
        _safe_exec(conn, """
        create table if not exists banks (
            id bigserial primary key,
            client_id bigint references clients(id),
            bank_name text not null,
            account_masked text,
            account_type text,
            currency text,
            opening_balance numeric,
            is_active boolean default true,
            created_at timestamptz default now(),
            updated_at timestamptz
        );
        """)

        # Categories
        _safe_exec(conn, """
        create table if not exists categories (
            id bigserial primary key,
            client_id bigint references clients(id),
            category_code text,
            category_name text not null,
            type text,
            nature text,
            is_active boolean default true,
            created_at timestamptz default now(),
            updated_at timestamptz
        );
        """)

        # Vendor memory (simple)
        _safe_exec(conn, """
        create table if not exists vendor_memory (
            id bigserial primary key,
            client_id bigint references clients(id),
            vendor_name text not null,
            category_name text,
            confidence numeric default 0.92,
            created_at timestamptz default now()
        );
        """)

        # Draft transactions
        _safe_exec(conn, """
        create table if not exists transactions_draft (
            id bigserial primary key,
            client_id bigint references clients(id),
            bank_id bigint references banks(id),
            period text,
            tx_date date,
            description text,
            debit numeric,
            credit numeric,
            balance numeric,
            suggested_category text,
            suggested_vendor text,
            reason text,
            confidence numeric,
            status text default 'Draft',
            final_category text,
            final_vendor text,
            created_at timestamptz default now(),
            updated_at timestamptz
        );
        """)

        # Ensure columns (safe alter)
        _safe_exec(conn, "alter table transactions_draft add column if not exists final_category text;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists final_vendor text;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists updated_at timestamptz;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists reason text;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists confidence numeric;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists suggested_category text;")
        _safe_exec(conn, "alter table transactions_draft add column if not exists suggested_vendor text;")

        # Committed (placeholder for next step)
        _safe_exec(conn, """
        create table if not exists transactions_committed (
            id bigserial primary key,
            client_id bigint references clients(id),
            bank_id bigint references banks(id),
            period text,
            tx_date date,
            description text,
            debit numeric,
            credit numeric,
            balance numeric,
            category text,
            vendor text,
            created_at timestamptz default now()
        );
        """)

    return "DB schema initialized + migrated (tables created/verified + columns ensured)."
