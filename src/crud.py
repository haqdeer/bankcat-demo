import re
from collections import Counter, defaultdict
from sqlalchemy import text
from src.db import get_engine

# ---------------- internal helpers ----------------
def _q(sql: str, params: dict | None = None):
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        try:
            rows = res.mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

def _exec(sql: str, params: dict | None = None) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        try:
            return res.rowcount or 0
        except Exception:
            return 0

def _one(sql: str, params: dict | None = None):
    rows = _q(sql, params)
    return rows[0] if rows else None

def _tokenize(desc: str) -> list[str]:
    if not desc:
        return []
    s = desc.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    parts = [p for p in s.split() if len(p) >= 3]
    # remove ultra-generic tokens
    stop = {"pos","purchase","payment","transfer","from","to","ref","invoice","card","online","app"}
    return [p for p in parts if p not in stop]

# ---------------- Clients ----------------
def list_clients(include_inactive: bool = True):
    if include_inactive:
        return _q("select * from clients order by id asc;")
    return _q("select * from clients where is_active=true order by id asc;")

def add_client(name: str, business_description: str, industry: str, country: str):
    _exec("""
        insert into clients(name, business_description, industry, country)
        values (:n,:bd,:ind,:cty);
    """, {"n": name, "bd": business_description, "ind": industry, "cty": country})

# ---------------- Banks ----------------
def list_banks(client_id: int, include_inactive: bool = True):
    if include_inactive:
        return _q("select * from banks where client_id=:cid order by id asc;", {"cid": client_id})
    return _q("select * from banks where client_id=:cid and is_active=true order by id asc;", {"cid": client_id})

def add_bank(client_id: int, bank_name: str, account_masked: str, account_type: str, currency: str, opening_balance: float):
    _exec("""
        insert into banks(client_id, bank_name, account_masked, account_type, currency, opening_balance)
        values (:cid,:bn,:am,:at,:cur,:ob);
    """, {"cid": client_id, "bn": bank_name, "am": account_masked, "at": account_type, "cur": currency, "ob": opening_balance})

def update_bank(bank_id: int, bank_name: str, account_masked: str, account_type: str, currency: str, opening_balance: float):
    _exec("""
        update banks set bank_name=:bn, account_masked=:am, account_type=:at, currency=:cur, opening_balance=:ob
        where id=:id;
    """, {"id": bank_id, "bn": bank_name, "am": account_masked, "at": account_type, "cur": currency, "ob": opening_balance})

def set_bank_active(bank_id: int, is_active: bool):
    _exec("update banks set is_active=:a where id=:id;", {"id": bank_id, "a": is_active})

def can_delete_bank(bank_id: int) -> bool:
    x = _one("select count(*)::int as c from transactions_draft where bank_id=:id;", {"id": bank_id})
    y = _one("select count(*)::int as c from transactions_committed where bank_id=:id;", {"id": bank_id})
    return (x["c"] if x else 0) == 0 and (y["c"] if y else 0) == 0

def delete_bank(bank_id: int) -> bool:
    r = _exec("delete from banks where id=:id;", {"id": bank_id})
    return r > 0

# ---------------- Categories ----------------
def list_categories(client_id: int, include_inactive: bool = True):
    if include_inactive:
        return _q("select * from categories where client_id=:cid order by id asc;", {"cid": client_id})
    return _q("select * from categories where client_id=:cid and is_active=true order by id asc;", {"cid": client_id})

def add_category(client_id: int, category_name: str, type_: str, nature: str):
    code = "CAT-" + re.sub(r"[^A-Z0-9]+", "-", category_name.upper()).strip("-")[:40]
    _exec("""
        insert into categories(client_id, category_code, category_name, type, nature)
        values (:cid,:cc,:cn,:tp,:nt);
    """, {"cid": client_id, "cc": code, "cn": category_name, "tp": type_, "nt": nature})

def bulk_add_categories(client_id: int, rows: list[tuple]):
    inserted, skipped = 0, 0
    for (nm, tp, nt, _) in rows:
        exists = _one("""
            select 1 from categories where client_id=:cid and lower(category_name)=lower(:nm) limit 1;
        """, {"cid": client_id, "nm": nm})
        if exists:
            skipped += 1
            continue
        add_category(client_id, nm, tp, nt)
        inserted += 1
    return {"inserted": inserted, "skipped": skipped}

# ---------------- Draft batches (Status) ----------------
def upsert_draft_batch(client_id: int, bank_id: int, period: str, status: str):
    _exec("""
        insert into draft_batches(client_id, bank_id, period, status)
        values (:cid,:bid,:p,:s)
        on conflict (client_id, bank_id, period)
        do update set status=excluded.status, updated_at=now();
    """, {"cid": client_id, "bid": bank_id, "p": period, "s": status})

def list_draft_periods(client_id: int, bank_id: int):
    return _q("""
        select b.period,
               (select count(*)::int from transactions_draft d
                where d.client_id=:cid and d.bank_id=:bid and d.period=b.period) as row_count,
               (select min(tx_date) from transactions_draft d
                where d.client_id=:cid and d.bank_id=:bid and d.period=b.period) as min_date,
               (select max(tx_date) from transactions_draft d
                where d.client_id=:cid and d.bank_id=:bid and d.period=b.period) as max_date,
               b.status,
               b.updated_at as last_saved
        from draft_batches b
        where b.client_id=:cid and b.bank_id=:bid
        order by b.period desc;
    """, {"cid": client_id, "bid": bank_id})

def delete_draft_period(client_id: int, bank_id: int, period: str) -> int:
    _exec("delete from draft_batches where client_id=:cid and bank_id=:bid and period=:p;", {"cid": client_id, "bid": bank_id, "p": period})
    return _exec("delete from transactions_draft where client_id=:cid and bank_id=:bid and period=:p;", {"cid": client_id, "bid": bank_id, "p": period})

# ---------------- Draft transactions ----------------
def insert_draft_bulk(client_id: int, bank_id: int, period: str, rows: list[dict]) -> int:
    upsert_draft_batch(client_id, bank_id, period, "Imported")
    engine = get_engine()
    ins = 0
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                insert into transactions_draft(
                    client_id, bank_id, period, tx_date, description, debit, credit, balance,
                    suggested_category, suggested_vendor, confidence, reason,
                    final_category, final_vendor
                )
                values (:cid,:bid,:p,:dt,:ds,:dr,:cr,:bal,:sc,:sv,:cf,:rs,:fc,:fv);
            """), {
                "cid": client_id, "bid": bank_id, "p": period,
                "dt": r["tx_date"], "ds": r["description"],
                "dr": r.get("debit"), "cr": r.get("credit"), "bal": r.get("balance"),
                "sc": r.get("suggested_category"), "sv": r.get("suggested_vendor"),
                "cf": r.get("confidence"), "rs": r.get("reason"),
                "fc": r.get("final_category"), "fv": r.get("final_vendor")
            })
            ins += 1
    return ins

def get_draft_rows(client_id: int, bank_id: int, period: str, limit: int = 500):
    return _q("""
        select * from transactions_draft
        where client_id=:cid and bank_id=:bid and period=:p
        order by tx_date asc, id asc
        limit :lim;
    """, {"cid": client_id, "bid": bank_id, "p": period, "lim": limit})

def get_draft_sample(client_id: int, bank_id: int, period: str, limit: int = 200):
    return get_draft_rows(client_id, bank_id, period, limit)

def update_suggestions_bulk(updates: list[dict]) -> int:
    engine = get_engine()
    n = 0
    with engine.begin() as conn:
        for u in updates:
            conn.execute(text("""
                update transactions_draft
                set suggested_category=:sc,
                    suggested_vendor=:sv,
                    confidence=:cf,
                    reason=:rs
                where id=:id;
            """), {"id": u["id"], "sc": u.get("suggested_category"), "sv": u.get("suggested_vendor"),
                  "cf": u.get("confidence"), "rs": u.get("reason")})
            n += 1
    # status bump is handled in app (we’ll set after process)
    return n

def save_review_bulk(changes: list[dict]) -> int:
    engine = get_engine()
    n = 0
    with engine.begin() as conn:
        for c in changes:
            conn.execute(text("""
                update transactions_draft
                set final_category=:fc,
                    final_vendor=:fv
                where id=:id;
            """), {"id": c["id"], "fc": c.get("final_category"), "fv": c.get("final_vendor")})
            n += 1
    return n

# ---------------- Vendor memory (learning) ----------------
def list_vendor_memory(client_id: int):
    return _q("""
        select vendor_name, category_name, confidence
        from vendor_memory
        where client_id=:cid
        order by confidence desc, vendor_name asc;
    """, {"cid": client_id})

def _upsert_vendor_memory(client_id: int, vendor: str, category: str):
    _exec("""
        insert into vendor_memory(client_id, vendor_name, category_name, confidence)
        values (:cid,:v,:c,0.55)
        on conflict (client_id, vendor_name)
        do update set category_name=excluded.category_name,
                     confidence=LEAST(0.99, vendor_memory.confidence + 0.05),
                     updated_at=now();
    """, {"cid": client_id, "v": vendor, "c": category})

# ---------------- Keyword model (learning) ----------------
def _upsert_keyword_weight(client_id: int, token: str, category: str, delta: float):
    _exec("""
        insert into keyword_model(client_id, token, category_name, weight)
        values (:cid,:t,:c,:w)
        on conflict (client_id, token, category_name)
        do update set weight = keyword_model.weight + :w,
                     updated_at=now();
    """, {"cid": client_id, "t": token, "c": category, "w": delta})

# ---------------- Step-7 Commit / Lock / Learn ----------------
def commit_period(client_id: int, bank_id: int, period: str, committed_by: str | None = None) -> dict:
    """
    Copies draft -> committed (LOCK), logs commit, updates learning tables.
    Returns commit stats.
    """
    # 1) Load full draft
    rows = _q("""
        select * from transactions_draft
        where client_id=:cid and bank_id=:bid and period=:p
        order by tx_date asc, id asc;
    """, {"cid": client_id, "bid": bank_id, "p": period})

    if not rows:
        return {"ok": False, "msg": "No draft rows found for this bank+period."}

    # 2) Validate final categories exist
    missing = [r for r in rows if not (r.get("final_category") and str(r.get("final_category")).strip())]
    if missing:
        return {"ok": False, "msg": f"Commit blocked: {len(missing)} rows missing final_category. Fill review first."}

    # 3) Compute accuracy vs suggested (if suggestions exist)
    total = len(rows)
    match = 0
    for r in rows:
        sc = (r.get("suggested_category") or "").strip()
        fc = (r.get("final_category") or "").strip()
        if sc and fc and sc.lower() == fc.lower():
            match += 1
    accuracy = round(match / total, 4) if total else None

    engine = get_engine()
    with engine.begin() as conn:
        # 4) Create commit record
        res = conn.execute(text("""
            insert into commits(client_id, bank_id, period, committed_by, rows_committed, accuracy)
            values (:cid,:bid,:p,:by,:n,:acc)
            returning id;
        """), {"cid": client_id, "bid": bank_id, "p": period, "by": committed_by, "n": total, "acc": accuracy})
        commit_id = res.scalar()

        # 5) Copy to committed table
        for r in rows:
            conn.execute(text("""
                insert into transactions_committed(
                    commit_id, client_id, bank_id, period,
                    tx_date, description, debit, credit, balance,
                    category, vendor
                    , suggested_category, suggested_vendor, confidence, reason
                )
                values (
                    :cm,:cid,:bid,:p,
                    :dt,:ds,:dr,:cr,:bal,
                    :cat,:ven,
                    :sc,:sv,:cf,:rs
                );
            """), {
                "cm": commit_id, "cid": client_id, "bid": bank_id, "p": period,
                "dt": r["tx_date"], "ds": r["description"], "dr": r.get("debit"), "cr": r.get("credit"), "bal": r.get("balance"),
                "cat": r.get("final_category"), "ven": r.get("final_vendor"),
                "sc": r.get("suggested_category"), "sv": r.get("suggested_vendor"),
                "cf": r.get("confidence"), "rs": r.get("reason")
            })

    # 6) Learning updates (outside the transaction is ok, but still safe)
    # Vendor memory
    for r in rows:
        ven = (r.get("final_vendor") or "").strip()
        cat = (r.get("final_category") or "").strip()
        if ven and cat:
            _upsert_vendor_memory(client_id, ven, cat)

    # Keyword model (token -> category weight)
    for r in rows:
        cat = (r.get("final_category") or "").strip()
        toks = _tokenize(r.get("description") or "")
        if cat and toks:
            freq = Counter(toks)
            for t, c in freq.items():
                _upsert_keyword_weight(client_id, t, cat, delta=0.10 * min(3, c))  # cap token impact

    # 7) Mark batch status
    upsert_draft_batch(client_id, bank_id, period, "Committed")

    return {
        "ok": True,
        "msg": f"Committed ✅ rows={total}, accuracy={accuracy}",
        "rows": total,
        "accuracy": accuracy
    }

def list_commits(client_id: int, bank_id: int):
    return _q("""
        select * from commits
        where client_id=:cid and bank_id=:bid
        order by committed_at desc;
    """, {"cid": client_id, "bid": bank_id})

def committed_sample(client_id: int, bank_id: int, period: str, limit: int = 200):
    return _q("""
        select tx_date, description, debit, credit, balance, category, vendor, confidence, reason
        from transactions_committed
        where client_id=:cid and bank_id=:bid and period=:p
        order by tx_date asc, id asc
        limit :lim;
    """, {"cid": client_id, "bid": bank_id, "p": period, "lim": limit})
