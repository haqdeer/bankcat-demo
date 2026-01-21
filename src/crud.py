import re
from typing import List, Dict, Optional
from sqlalchemy import text
from src.db import get_engine


def _q(sql: str, params: dict = None) -> List[Dict]:
    """Run a SELECT query and return list of dict rows."""
    engine = get_engine()
    with engine.connect() as conn:
        res = conn.execute(text(sql), params or {})
        cols = res.keys()
        return [dict(zip(cols, row)) for row in res.fetchall()]


def _exec(sql: str, params: dict = None) -> None:
    """Run an INSERT/UPDATE/DELETE query."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def normalize_code(prefix: str, name: str) -> str:
    """
    Create simple readable code from name. Example:
    prefix='CAT' name='Meals & Entertainment' -> 'CAT-MEALS-ENTERTAINMENT'
    """
    s = name.strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return f"{prefix}-{s[:30]}" if s else f"{prefix}-UNNAMED"


# ------------------ Clients ------------------

def list_clients() -> List[Dict]:
    return _q("select id, name, industry, country, created_at from clients order by id desc;")


def add_client(name: str, business_description: str, industry: str, country: str) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(
            text("""
                insert into clients (name, business_description, industry, country)
                values (:name, :bd, :industry, :country)
                returning id;
            """),
            {"name": name.strip(), "bd": business_description.strip(), "industry": industry.strip(), "country": country.strip()}
        )
        return int(res.scalar())


def get_client(client_id: int) -> Optional[Dict]:
    rows = _q("select * from clients where id=:id;", {"id": client_id})
    return rows[0] if rows else None


# ------------------ Banks ------------------

def list_banks(client_id: int) -> List[Dict]:
    return _q("""
        select id, bank_name, account_masked, account_type, currency, opening_balance, created_at
        from banks
        where client_id=:cid
        order by id desc;
    """, {"cid": client_id})


def add_bank(client_id: int, bank_name: str, account_masked: str, account_type: str, currency: str, opening_balance):
    _exec("""
        insert into banks (client_id, bank_name, account_masked, account_type, currency, opening_balance)
        values (:cid, :bn, :am, :at, :cur, :ob);
    """, {
        "cid": client_id,
        "bn": bank_name.strip(),
        "am": account_masked.strip(),
        "at": account_type.strip(),
        "cur": currency.strip(),
        "ob": opening_balance
    })


# ------------------ Categories ------------------

def list_categories(client_id: int) -> List[Dict]:
    return _q("""
        select id, category_code, category_name, type, nature, created_at
        from categories
        where client_id=:cid
        order by id desc;
    """, {"cid": client_id})


def add_category(client_id: int, category_name: str, type_: str, nature: str, category_code: Optional[str] = None):
    code = category_code.strip() if category_code and category_code.strip() else normalize_code("CAT", category_name)
    _exec("""
        insert into categories (client_id, category_code, category_name, type, nature)
        values (:cid, :cc, :cn, :tp, :nt);
    """, {"cid": client_id, "cc": code, "cn": category_name.strip(), "tp": type_.strip(), "nt": nature.strip()})
