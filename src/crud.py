import re
from typing import List, Dict, Optional, Tuple
from sqlalchemy import text
from src.db import get_engine


def _q(sql: str, params: dict = None) -> List[Dict]:
    engine = get_engine()
    with engine.connect() as conn:
        res = conn.execute(text(sql), params or {})
        cols = res.keys()
        return [dict(zip(cols, row)) for row in res.fetchall()]


def _scalar(sql: str, params: dict = None):
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).scalar()


def _exec(sql: str, params: dict = None) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def normalize_code(prefix: str, name: str) -> str:
    s = (name or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return f"{prefix}-{s[:30]}" if s else f"{prefix}-UNNAMED"


# ------------------ Clients ------------------

def list_clients(include_inactive: bool = True) -> List[Dict]:
    if include_inactive:
        return _q("select id, name, industry, country, business_description, is_active, created_at from clients order by id desc;")
    return _q("select id, name, industry, country, business_description, is_active, created_at from clients where is_active=true order by id desc;")


def add_client(name: str, business_description: str, industry: str, country: str) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(
            text("""
                insert into clients (name, business_description, industry, country, is_active)
                values (:name, :bd, :industry, :country, true)
                returning id;
            """),
            {
                "name": name.strip(),
                "bd": (business_description or "").strip(),
                "industry": (industry or "").strip(),
                "country": (country or "").strip()
            }
        )
        return int(res.scalar())


def update_client(client_id: int, name: str, business_description: str, industry: str, country: str):
    _exec("""
        update clients
        set name=:name, business_description=:bd, industry=:industry, country=:country, updated_at=now()
        where id=:id;
    """, {"id": client_id, "name": name.strip(), "bd": (business_description or "").strip(),
          "industry": (industry or "").strip(), "country": (country or "").strip()})


def set_client_active(client_id: int, is_active: bool):
    _exec("update clients set is_active=:a, updated_at=now() where id=:id;", {"id": client_id, "a": is_active})


def can_delete_client(client_id: int) -> bool:
    banks = _scalar("select count(*) from banks where client_id=:cid;", {"cid": client_id})
    cats = _scalar("select count(*) from categories where client_id=:cid;", {"cid": client_id})
    td = _scalar("select count(*) from transactions_draft where client_id=:cid;", {"cid": client_id})
    tc = _scalar("select count(*) from transactions_committed where client_id=:cid;", {"cid": client_id})
    return (banks == 0 and cats == 0 and td == 0 and tc == 0)


def delete_client(client_id: int) -> bool:
    if not can_delete_client(client_id):
        return False
    _exec("delete from clients where id=:id;", {"id": client_id})
    return True


# ------------------ Banks ------------------

def list_banks(client_id: int, include_inactive: bool = True) -> List[Dict]:
    if include_inactive:
        return _q("""
            select id, bank_name, account_masked, account_type, currency, opening_balance, is_active, created_at
            from banks
            where client_id=:cid
            order by id desc;
        """, {"cid": client_id})
    return _q("""
        select id, bank_name, account_masked, account_type, currency, opening_balance, is_active, created_at
        from banks
        where client_id=:cid and is_active=true
        order by id desc;
    """, {"cid": client_id})


def add_bank(client_id: int, bank_name: str, account_masked: str, account_type: str, currency: str, opening_balance):
    _exec("""
        insert into banks (client_id, bank_name, account_masked, account_type, currency, opening_balance, is_active)
        values (:cid, :bn, :am, :at, :cur, :ob, true);
    """, {
        "cid": client_id,
        "bn": (bank_name or "").strip(),
        "am": (account_masked or "").strip(),
        "at": (account_type or "").strip(),
        "cur": (currency or "").strip(),
        "ob": opening_balance
    })


def update_bank(bank_id: int, bank_name: str, account_masked: str, account_type: str, currency: str, opening_balance):
    _exec("""
        update banks
        set bank_name=:bn, account_masked=:am, account_type=:at, currency=:cur, opening_balance=:ob, updated_at=now()
        where id=:id;
    """, {"id": bank_id, "bn": bank_name.strip(), "am": (account_masked or "").strip(),
          "at": account_type.strip(), "cur": (currency or "").strip(), "ob": opening_balance})


def set_bank_active(bank_id: int, is_active: bool):
    _exec("update banks set is_active=:a, updated_at=now() where id=:id;", {"id": bank_id, "a": is_active})


def can_delete_bank(bank_id: int) -> bool:
    td = _scalar("select count(*) from transactions_draft where bank_id=:id;", {"id": bank_id})
    tc = _scalar("select count(*) from transactions_committed where bank_id=:id;", {"id": bank_id})
    return (td == 0 and tc == 0)


def delete_bank(bank_id: int) -> bool:
    if not can_delete_bank(bank_id):
        return False
    _exec("delete from banks where id=:id;", {"id": bank_id})
    return True


# ------------------ Categories ------------------

def list_categories(client_id: int, include_inactive: bool = True) -> List[Dict]:
    if include_inactive:
        return _q("""
            select id, category_code, category_name, type, nature, is_active, created_at
            from categories
            where client_id=:cid
            order by id desc;
        """, {"cid": client_id})
    return _q("""
        select id, category_code, category_name, type, nature, is_active, created_at
        from categories
        where client_id=:cid and is_active=true
        order by id desc;
    """, {"cid": client_id})


def add_category(client_id: int, category_name: str, type_: str, nature: str, category_code: Optional[str] = None):
    code = category_code.strip() if category_code and category_code.strip() else normalize_code("CAT", category_name)
    _exec("""
        insert into categories (client_id, category_code, category_name, type, nature, is_active)
        values (:cid, :cc, :cn, :tp, :nt, true);
    """, {"cid": client_id, "cc": code, "cn": (category_name or "").strip(),
          "tp": (type_ or "").strip(), "nt": (nature or "").strip()})


def bulk_add_categories(client_id: int, rows: List[Tuple[str, str, str, Optional[str]]]) -> Dict:
    existing = _q("select lower(category_name) as nm from categories where client_id=:cid;", {"cid": client_id})
    existing_names = {r["nm"] for r in existing if r.get("nm")}

    cleaned = []
    for (name, type_, nature, code) in rows:
        nm = (name or "").strip()
        if not nm:
            continue
        key = nm.lower()
        if key in existing_names:
            continue

        tp = (type_ or "Expense").strip()
        nt = (nature or "Dr").strip()
        cc = (code or "").strip() or normalize_code("CAT", nm)

        cleaned.append({"cid": client_id, "cc": cc, "cn": nm, "tp": tp, "nt": nt})
        existing_names.add(key)

    if not cleaned:
        return {"inserted": 0, "skipped": len(rows)}

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into categories (client_id, category_code, category_name, type, nature, is_active)
                values (:cid, :cc, :cn, :tp, :nt, true);
            """),
            cleaned
        )

    return {"inserted": len(cleaned), "skipped": len(rows) - len(cleaned)}


# ------------------ Vendor memory ------------------

def list_vendor_memory(client_id: int) -> List[Dict]:
    return _q("""
        select vendor_name, category_name, confidence
        from vendor_memory
        where client_id=:cid
        order by confidence desc, vendor_name asc;
    """, {"cid": client_id})


# ------------------ Draft Transactions ------------------

def list_draft_periods(client_id: int, bank_id: int) -> List[Dict]:
    return _q("""
        select period, count(*) as row_count, min(tx_date) as min_date, max(tx_date) as max_date, max(created_at) as last_saved
        from transactions_draft
        where client_id=:cid and bank_id=:bid
        group by period
        order by period desc;
    """, {"cid": client_id, "bid": bank_id})


def get_draft_rows(client_id: int, bank_id: int, period: str, limit: int = 1000) -> List[Dict]:
    return _q("""
        select id, tx_date, description, debit, credit, balance,
               suggested_category, suggested_vendor, confidence, reason,
               final_category, final_vendor
        from transactions_draft
        where client_id=:cid and bank_id=:bid and period=:p
        order by tx_date asc, id asc
        limit :lim;
    """, {"cid": client_id, "bid": bank_id, "p": period, "lim": limit})


def get_draft_sample(client_id: int, bank_id: int, period: str, limit: int = 200) -> List[Dict]:
    return get_draft_rows(client_id, bank_id, period, limit)


def delete_draft_period(client_id: int, bank_id: int, period: str) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text("""
            delete from transactions_draft
            where client_id=:cid and bank_id=:bid and period=:p;
        """), {"cid": client_id, "bid": bank_id, "p": period})
        return res.rowcount or 0


def insert_draft_bulk(client_id: int, bank_id: int, period: str, rows: List[Dict]) -> int:
    if not rows:
        return 0

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                insert into transactions_draft
                (client_id, bank_id, period, tx_date, description, debit, credit, balance,
                 suggested_category, suggested_vendor, reason, confidence, status,
                 final_category, final_vendor)
                values
                (:client_id, :bank_id, :period, :tx_date, :description, :debit, :credit, :balance,
                 :suggested_category, :suggested_vendor, :reason, :confidence, 'Draft',
                 :final_category, :final_vendor);
            """),
            [{
                "client_id": client_id,
                "bank_id": bank_id,
                "period": period,
                "tx_date": r["tx_date"],
                "description": r["description"],
                "debit": r.get("debit"),
                "credit": r.get("credit"),
                "balance": r.get("balance"),
                "suggested_category": r.get("suggested_category"),
                "suggested_vendor": r.get("suggested_vendor"),
                "reason": r.get("reason"),
                "confidence": r.get("confidence"),
                "final_category": None,
                "final_vendor": None,
            } for r in rows]
        )
    return len(rows)


def update_suggestions_bulk(rows: List[Dict]) -> int:
    """
    rows: [{id, suggested_category, suggested_vendor, confidence, reason}]
    """
    if not rows:
        return 0
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                update transactions_draft
                set suggested_category=:sc,
                    suggested_vendor=:sv,
                    confidence=:cf,
                    reason=:rs,
                    updated_at=now()
                where id=:id;
            """),
            [{"id": r["id"], "sc": r.get("suggested_category"), "sv": r.get("suggested_vendor"),
              "cf": r.get("confidence"), "rs": r.get("reason")} for r in rows]
        )
    return len(rows)


def save_review_bulk(rows: List[Dict]) -> int:
    """
    rows: [{id, final_category, final_vendor}]
    """
    if not rows:
        return 0
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                update transactions_draft
                set final_category=:fc,
                    final_vendor=:fv,
                    updated_at=now()
                where id=:id;
            """),
            [{"id": r["id"], "fc": r.get("final_category"), "fv": r.get("final_vendor")} for r in rows]
        )
    return len(rows)
