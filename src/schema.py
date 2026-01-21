from sqlalchemy import text
from src.db import get_engine

DDL_STATEMENTS = [
    # 1) clients
    """
    create table if not exists clients (
        id bigserial primary key,
        name text not null,
        business_description text,
        industry text,
        country text,
        created_at timestamptz not null default now()
    );
    """,

    # 2) banks
    """
    create table if not exists banks (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        bank_name text not null,
        account_masked text,
        account_type text not null,
        currency text,
        opening_balance numeric(18,2),
        created_at timestamptz not null default now()
    );
    """,

    # 3) categories
    """
    create table if not exists categories (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        category_code text,
        category_name text not null,
        type text not null,          -- Income / Expense / Other
        nature text not null,        -- Dr / Cr / Any
        created_at timestamptz not null default now()
    );
    """,

    # 4) transactions_draft
    """
    create table if not exists transactions_draft (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        bank_id bigint not null references banks(id) on delete cascade,
        period text not null,          -- YYYY-MM
        tx_date date not null,
        description text not null,
        debit numeric(18,2),
        credit numeric(18,2),
        balance numeric(18,2),
        suggested_category text,
        suggested_vendor text,
        reason text,
        confidence numeric(5,2),
        final_category text,
        final_vendor text,
        status text not null default 'Draft',
        created_at timestamptz not null default now()
    );
    """,

    # 5) transactions_committed
    """
    create table if not exists transactions_committed (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        bank_id bigint not null references banks(id) on delete cascade,
        commit_id bigint,
        period text not null,
        tx_date date not null,
        description text not null,
        debit numeric(18,2),
        credit numeric(18,2),
        balance numeric(18,2),
        category text not null,
        vendor text,
        created_at timestamptz not null default now()
    );
    """,

    # 6) vendor_memory
    """
    create table if not exists vendor_memory (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        vendor_key text not null,
        category text not null,
        confidence numeric(5,2) not null default 0,
        times_confirmed int not null default 0,
        last_seen date,
        unique (client_id, vendor_key)
    );
    """,

    # 7) keyword_model
    """
    create table if not exists keyword_model (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        token text not null,
        category text not null,
        weight numeric(10,4) not null default 0,
        times_used int not null default 0,
        unique (client_id, token, category)
    );
    """,

    # 8) commits
    """
    create table if not exists commits (
        id bigserial primary key,
        client_id bigint not null references clients(id) on delete cascade,
        bank_id bigint not null references banks(id) on delete cascade,
        period text not null,
        from_date date,
        to_date date,
        row_count int not null default 0,
        accuracy_percent numeric(5,2),
        created_at timestamptz not null default now()
    );
    """,
]

def init_db() -> str:
    engine = get_engine()
    with engine.begin() as conn:
        for ddl in DDL_STATEMENTS:
            conn.execute(text(ddl))
    return "DB schema initialized (tables created/verified)."
