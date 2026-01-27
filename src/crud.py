# src/crud.py
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, text
import streamlit as st


@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL") or st.secrets.get("db_url") or st.secrets.get("DB_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL missing in Streamlit secrets.")
    return create_engine(db_url, pool_pre_ping=True)


def _q(sql: str, params: Optional[dict] = None) -> List[dict]:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        rows = res.mappings().all()
        return [dict(r) for r in rows]


def _exec(sql: str, params: Optional[dict] = None) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        return res.rowcount if res.rowcount is not None else 0


# ---------------- Clients ----------------
def list_clients(include_inactive: bool = False) -> List[dict]:
    if include_inactive:
        return _q("SELECT * FROM clients ORDER BY created_at DESC;")
    return _q("SELECT * FROM clients WHERE is_active = TRUE ORDER BY created_at DESC;")


def create_client(name: str, industry: str, country: str, business_description: str = "") -> int:
    rows = _q("""
        INSERT INTO clients(name, industry, country, business_description)
        VALUES (:n,:i,:c,:bd)
        RETURNING id;
    """, {"n": name.strip(), "i": industry, "c": country, "bd": business_description})
    return int(rows[0]["id"])


def update_client(client_id: int, name: str, industry: str, country: str, business_description: str = "") -> None:
    _exec("""
        UPDATE clients
        SET name=:n,
            industry=:i,
            country=:c,
            business_description=:bd
        WHERE id=:cid;
    """, {"n": name.strip(), "i": industry, "c": country, "bd": business_description, "cid": client_id})


def set_client_active(client_id: int, is_active: bool) -> None:
    _exec("UPDATE clients SET is_active=:a WHERE id=:id;", {"a": is_active, "id": client_id})


# ---------------- Banks ----------------
def list_banks(client_id: int, include_inactive: bool = False) -> List[dict]:
    if include_inactive:
        return _q("SELECT * FROM banks WHERE client_id=:cid ORDER BY created_at DESC;", {"cid": client_id})
    return _q("SELECT * FROM banks WHERE client_id=:cid AND is_active=TRUE ORDER BY created_at DESC;", {"cid": client_id})


def add_bank(client_id: int, bank_name: str, account_type: str, currency: str = "", masked: str = "", opening_balance: Optional[float] = None) -> int:
    rows = _q("""
        INSERT INTO banks(client_id, bank_name, account_type, currency, account_number_masked, opening_balance)
        VALUES (:cid,:bn,:at,:cur,:m,:ob)
        RETURNING id;
    """, {"cid": client_id, "bn": bank_name, "at": account_type, "cur": currency, "m": masked, "ob": opening_balance})
    return int(rows[0]["id"])


def set_bank_active(bank_id: int, is_active: bool):
    _exec("UPDATE banks SET is_active=:a WHERE id=:id;", {"a": is_active, "id": bank_id})


def update_bank(
    bank_id: int,
    bank_name: str,
    masked: str,
    account_type: str,
    currency: str,
    opening_balance: Optional[float],
) -> None:
    _exec("""
        UPDATE banks
        SET bank_name=:bn,
            account_number_masked=:m,
            account_type=:at,
            currency=:cur,
            opening_balance=COALESCE(:ob, opening_balance)
        WHERE id=:id;
    """, {"bn": bank_name.strip(), "m": masked, "at": account_type, "cur": currency, "ob": opening_balance, "id": bank_id})


def bank_has_transactions(bank_id: int) -> bool:
    rows = _q("""
        SELECT 1 AS has_tx
        FROM transactions_draft
        WHERE bank_id=:bid
        UNION ALL
        SELECT 1 AS has_tx
        FROM transactions_committed
        WHERE bank_id=:bid
        LIMIT 1;
    """, {"bid": bank_id})
    return bool(rows)


# ---------------- Categories ----------------
def list_categories(client_id: int, include_inactive: bool = False) -> List[dict]:
    if include_inactive:
        return _q("SELECT * FROM categories WHERE client_id=:cid ORDER BY created_at DESC;", {"cid": client_id})
    return _q("SELECT * FROM categories WHERE client_id=:cid AND is_active=TRUE ORDER BY created_at DESC;", {"cid": client_id})


def add_category(client_id: int, name: str, typ: str, nature: str):
    # category_code auto
    code = "CAT-" + re.sub(r"[^A-Z0-9]+", "-", name.strip().upper()).strip("-")[:40]
    _exec("""
        INSERT INTO categories(client_id, category_code, category_name, type, nature)
        VALUES (:cid,:cc,:cn,:t,:n);
    """, {"cid": client_id, "cc": code, "cn": name.strip(), "t": typ, "n": nature})


def bulk_add_categories(client_id: int, rows: List[dict]) -> Tuple[int, int]:
    """
    rows: [{category_name,type,nature},...]
    """
    ok = 0
    bad = 0
    for r in rows:
        name = (r.get("category_name") or "").strip()
        typ = (r.get("type") or "").strip()
        nature = (r.get("nature") or "Any").strip()
        if not name or typ not in ("Income", "Expense", "Other"):
            bad += 1
            continue
        add_category(client_id, name, typ, nature or "Any")
        ok += 1
    return ok, bad


def set_category_active(cat_id: int, is_active: bool):
    _exec("UPDATE categories SET is_active=:a WHERE id=:id;", {"a": is_active, "id": cat_id})


def list_table_columns(table_name: str) -> List[str]:
    rows = _q("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=:tn
        ORDER BY ordinal_position;
    """, {"tn": table_name})
    return [r["column_name"] for r in rows]


def update_category(cat_id: int, name: str, typ: str, nature: str) -> None:
    _exec("""
        UPDATE categories
        SET category_name=:cn,
            type=:t,
            nature=:n
        WHERE id=:id;
    """, {"cn": name.strip(), "t": typ, "n": nature, "id": cat_id})


# ---------------- Vendor memory + Keyword model ----------------
def list_vendor_memory(client_id: int) -> List[dict]:
    return _q("""
        SELECT vendor_name, category_name, confidence, times_used
        FROM vendor_memory
        WHERE client_id=:cid
        ORDER BY confidence DESC, times_used DESC, vendor_name ASC;
    """, {"cid": client_id})


def _upsert_vendor_memory(client_id: int, vendor: str, category: str, delta_conf: float = 0.03):
    vendor = (vendor or "").strip()
    if not vendor:
        return
    _exec("""
        INSERT INTO vendor_memory(client_id, vendor_name, category_name, confidence, times_used)
        VALUES (:cid,:v,:c,0.70,1)
        ON CONFLICT (client_id, vendor_name)
        DO UPDATE SET
            category_name = EXCLUDED.category_name,
            times_used = vendor_memory.times_used + 1,
            confidence = LEAST(0.9999, vendor_memory.confidence + :dc),
            updated_at = now();
    """, {"cid": client_id, "v": vendor, "c": category, "dc": delta_conf})


def _upsert_keyword_weight(client_id: int, token: str, category: str, delta: float):
    token = (token or "").strip().lower()
    if not token or len(token) < 3:
        return
    _exec("""
        INSERT INTO keyword_model(client_id, token, category, weight, times_used)
        VALUES (:cid,:t,:c,:w,1)
        ON CONFLICT (client_id, token, category)
        DO UPDATE SET
            weight = keyword_model.weight + EXCLUDED.weight,
            times_used = keyword_model.times_used + 1;
    """, {"cid": client_id, "t": token, "c": category, "w": float(delta)})


def keyword_weights(client_id: int) -> List[dict]:
    return _q("""
        SELECT token, category, weight, times_used
        FROM keyword_model
        WHERE client_id=:cid
        ORDER BY weight DESC, times_used DESC
        LIMIT 5000;
    """, {"cid": client_id})


# ---------------- Drafts ----------------
def drafts_summary(client_id: int, bank_id: int) -> List[dict]:
    return _q("""
        SELECT period,
               COUNT(*) AS row_count,
               MIN(tx_date) AS min_date,
               MAX(tx_date) AS max_date,
               MAX(created_at) AS last_saved
        FROM transactions_draft
        WHERE client_id=:cid AND bank_id=:bid
        GROUP BY period
        ORDER BY period DESC;
    """, {"cid": client_id, "bid": bank_id})


def delete_draft_period(client_id: int, bank_id: int, period: str):
    _exec("""
        DELETE FROM transactions_draft
        WHERE client_id=:cid AND bank_id=:bid AND period=:p;
    """, {"cid": client_id, "bid": bank_id, "p": period})


def insert_draft_rows(client_id: int, bank_id: int, period: str, rows: List[dict], replace: bool = True) -> int:
    if replace:
        delete_draft_period(client_id, bank_id, period)

    n = 0
    for r in rows:
        _exec("""
            INSERT INTO transactions_draft(
                client_id, bank_id, period,
                tx_date, description, debit, credit, balance
            )
            VALUES (:cid,:bid,:p,:dt,:ds,:dr,:cr,:bal);
        """, {
            "cid": client_id, "bid": bank_id, "p": period,
            "dt": r["tx_date"], "ds": r["description"],
            "dr": r.get("debit", 0) or 0, "cr": r.get("credit", 0) or 0,
            "bal": r.get("balance", None),
        })
        n += 1
    return n


def load_draft(client_id: int, bank_id: int, period: str) -> List[dict]:
    return _q("""
        SELECT *
        FROM transactions_draft
        WHERE client_id=:cid AND bank_id=:bid AND period=:p
        ORDER BY tx_date ASC, id ASC;
    """, {"cid": client_id, "bid": bank_id, "p": period})


def save_review_changes(rows: List[dict]) -> int:
    """
    rows must contain id, final_category, final_vendor
    """
    updated = 0
    for r in rows:
        _exec("""
            UPDATE transactions_draft
            SET final_category=:c,
                final_vendor=:v,
                status='USER_FINALISED'
            WHERE id=:id;
        """, {"c": r.get("final_category"), "v": r.get("final_vendor"), "id": r["id"]})
        updated += 1
    return updated


# ---------------- Suggestion Engine ----------------
def _tokenize(desc: str) -> List[str]:
    desc = (desc or "").lower()
    desc = re.sub(r"[^a-z0-9\s]", " ", desc)
    toks = [t for t in desc.split() if len(t) >= 3 and not t.isdigit()]
    return toks[:25]


def process_suggestions(client_id: int, bank_id: int, period: str, bank_account_type: str = "Current") -> int:
    """
    Fill suggested_category/vendor/confidence/reason.
    Very simple rule engine:
      1) Vendor memory (if vendor extracted) else keyword weights
      2) Nature heuristic: credit tends to Income, debit tends to Expense
    """
    cats = list_categories(client_id, include_inactive=False)
    cat_names_income = [c["category_name"] for c in cats if c["type"] == "Income"]
    cat_names_exp = [c["category_name"] for c in cats if c["type"] == "Expense"]
    fallback_income = cat_names_income[0] if cat_names_income else "Income"
    fallback_exp = cat_names_exp[0] if cat_names_exp else "Expense"

    vm = {v["vendor_name"].lower(): v for v in list_vendor_memory(client_id)}
    kw = keyword_weights(client_id)
    # build token -> best category
    token_best: Dict[str, Tuple[str, float]] = {}
    for r in kw:
        t = r["token"]
        c = r["category"]
        w = float(r["weight"] or 0)
        if t not in token_best or w > token_best[t][1]:
            token_best[t] = (c, w)

    draft = load_draft(client_id, bank_id, period)
    updated = 0

    for row in draft:
        desc = row["description"] or ""
        debit = float(row.get("debit") or 0)
        credit = float(row.get("credit") or 0)

        # crude vendor extraction: take first 3-6 tokens as "vendor-ish"
        toks = _tokenize(desc)
        vendor_guess = " ".join(toks[:4]).title() if toks else None

        suggested_cat = None
        confidence = 0.40
        reason = "Heuristic"

        # 1) vendor memory match
        if vendor_guess and vendor_guess.lower() in vm:
            suggested_cat = vm[vendor_guess.lower()]["category_name"]
            confidence = float(vm[vendor_guess.lower()]["confidence"])
            reason = "Vendor memory"
        else:
            # 2) keyword weight
            best_cat = None
            best_score = 0.0
            for t in toks:
                if t in token_best:
                    c, w = token_best[t]
                    if w > best_score:
                        best_score = w
                        best_cat = c
            if best_cat:
                suggested_cat = best_cat
                confidence = max(0.55, min(0.95, 0.55 + (best_score / 10.0)))
                reason = "Keyword model"

        # 3) nature/account type fallback
        if not suggested_cat:
            if credit > 0 and debit == 0:
                suggested_cat = fallback_income
                confidence = 0.55
                reason = "Nature+account-type heuristic"
            else:
                suggested_cat = fallback_exp
                confidence = 0.55
                reason = "Nature+account-type heuristic"

        _exec("""
            UPDATE transactions_draft
            SET suggested_category=:sc,
                suggested_vendor=:sv,
                confidence=:cf,
                reason=:rs,
                status='SYSTEM_SUGGESTED'
            WHERE id=:id;
        """, {
            "sc": suggested_cat,
            "sv": vendor_guess,
            "cf": confidence,
            "rs": reason,
            "id": row["id"],
        })
        updated += 1

    return updated


# ---------------- Commit / Lock / Learn ----------------
def committed_sample(client_id: int, bank_id: int, period: str, limit: int = 200) -> List[dict]:
    return _q("""
        SELECT tx_date, description, debit, credit, balance,
               category, vendor, suggested_category, suggested_vendor, confidence, reason
        FROM transactions_committed
        WHERE client_id=:cid AND bank_id=:bid AND period=:p
        ORDER BY tx_date ASC, id ASC
        LIMIT :lim;
    """, {"cid": client_id, "bid": bank_id, "p": period, "lim": limit})


def commit_period(client_id: int, bank_id: int, period: str, committed_by: Optional[str] = None) -> dict:
    draft = load_draft(client_id, bank_id, period)
    if not draft:
        return {"ok": False, "msg": "No draft rows found for this bank+period."}

    # Validation: must have final_category for every row
    missing = [r for r in draft if not (r.get("final_category") or "").strip()]
    if missing:
        return {"ok": False, "msg": f"{len(missing)} rows missing Final Category. Please fill before Commit."}

    total = len(draft)
    matched = 0
    for r in draft:
        if (r.get("final_category") or "").strip() == (r.get("suggested_category") or "").strip():
            matched += 1
    accuracy = round(matched / total, 4) if total else None

    # Deactivate any prior commits for the same client+bank+period
    _exec("""
        UPDATE commits
        SET is_active=FALSE
        WHERE client_id=:cid AND bank_id=:bid AND period=:p AND is_active=TRUE;
    """, {"cid": client_id, "bid": bank_id, "p": period})

    # Insert commit row
    cm = _q("""
        INSERT INTO commits(client_id, bank_id, period, committed_by, rows_committed, accuracy, is_active)
        VALUES (:cid,:bid,:p,:by,:n,:acc,TRUE)
        RETURNING id;
    """, {"cid": client_id, "bid": bank_id, "p": period, "by": committed_by, "n": total, "acc": accuracy})
    commit_id = int(cm[0]["id"])

    # Insert committed transactions + learning updates
    for r in draft:
        cat = (r.get("final_category") or "").strip()
        ven = (r.get("final_vendor") or None)
        sc = (r.get("suggested_category") or None)
        sv = (r.get("suggested_vendor") or None)
        cf = r.get("confidence")
        rs = r.get("reason")

        _exec("""
            INSERT INTO transactions_committed(
                commit_id, client_id, bank_id, period,
                tx_date, description, debit, credit, balance,
                category, vendor,
                suggested_category, suggested_vendor, confidence, reason
            )
            VALUES (
                :cm,:cid,:bid,:p,
                :dt,:ds,:dr,:cr,:bal,
                :cat,:ven,
                :sc,:sv,:cf,:rs
            );
        """, {
            "cm": commit_id, "cid": client_id, "bid": bank_id, "p": period,
            "dt": r["tx_date"], "ds": r["description"],
            "dr": r.get("debit", 0) or 0, "cr": r.get("credit", 0) or 0, "bal": r.get("balance", None),
            "cat": cat, "ven": ven,
            "sc": sc, "sv": sv, "cf": cf, "rs": rs
        })

        # Learn: vendor -> category if vendor exists
        if ven:
            _upsert_vendor_memory(client_id, ven, cat, delta_conf=0.02)

        # Learn: tokens -> category
        toks = _tokenize(r.get("description") or "")
        # small capped learning
        for t in set(toks[:10]):
            _upsert_keyword_weight(client_id, t, cat, delta=0.10)

    # After commit: clear draft rows for that period (lock behavior)
    delete_draft_period(client_id, bank_id, period)

    return {"ok": True, "commit_id": commit_id, "rows": total, "accuracy": accuracy}


# ---------------- Committed Reporting ----------------
def list_committed_periods(client_id: int, bank_id: Optional[int] = None) -> List[str]:
    conditions = ["tc.client_id=:cid", "c.is_active=TRUE"]
    params: Dict[str, Any] = {"cid": client_id}
    if bank_id is not None:
        conditions.append("tc.bank_id=:bid")
        params["bid"] = bank_id

    sql = f"""
        SELECT DISTINCT tc.period
        FROM transactions_committed tc
        JOIN commits c ON c.id = tc.commit_id
        WHERE {" AND ".join(conditions)}
        ORDER BY tc.period DESC;
    """
    rows = _q(sql, params)
    return [r["period"] for r in rows]


def list_committed_transactions(
    client_id: int,
    bank_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period: Optional[str] = None,
) -> List[dict]:
    conditions = ["tc.client_id=:cid", "c.is_active=TRUE"]
    params: Dict[str, Any] = {"cid": client_id}
    if bank_id is not None:
        conditions.append("tc.bank_id=:bid")
        params["bid"] = bank_id
    if date_from is not None:
        conditions.append("tc.tx_date >= :dfrom")
        params["dfrom"] = date_from
    if date_to is not None:
        conditions.append("tc.tx_date <= :dto")
        params["dto"] = date_to
    if period is not None:
        conditions.append("tc.period = :p")
        params["p"] = period

    sql = f"""
        SELECT tc.tx_date, tc.description, tc.debit, tc.credit, tc.balance,
               tc.category, tc.vendor, tc.confidence, tc.reason,
               b.bank_name, tc.period
        FROM transactions_committed tc
        JOIN commits c ON c.id = tc.commit_id
        JOIN banks b ON b.id = tc.bank_id
        WHERE {" AND ".join(conditions)}
        ORDER BY tc.tx_date ASC, tc.id ASC;
    """
    return _q(sql, params)


def list_committed_pl_summary(
    client_id: int,
    bank_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period: Optional[str] = None,
) -> List[dict]:
    conditions = ["tc.client_id=:cid", "c.is_active=TRUE"]
    params: Dict[str, Any] = {"cid": client_id}
    if bank_id is not None:
        conditions.append("tc.bank_id=:bid")
        params["bid"] = bank_id
    if date_from is not None:
        conditions.append("tc.tx_date >= :dfrom")
        params["dfrom"] = date_from
    if date_to is not None:
        conditions.append("tc.tx_date <= :dto")
        params["dto"] = date_to
    if period is not None:
        conditions.append("tc.period = :p")
        params["p"] = period

    sql = f"""
        SELECT tc.category,
               cat.type AS category_type,
               SUM(tc.debit) AS total_debit,
               SUM(tc.credit) AS total_credit,
               SUM(tc.credit) - SUM(tc.debit) AS net_amount
        FROM transactions_committed tc
        JOIN commits c ON c.id = tc.commit_id
        LEFT JOIN categories cat
            ON cat.client_id = tc.client_id
           AND cat.category_name = tc.category
        WHERE {" AND ".join(conditions)}
        GROUP BY tc.category, cat.type
        ORDER BY tc.category ASC;
    """
    return _q(sql, params)


def list_commit_metrics(
    client_id: int,
    bank_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period: Optional[str] = None,
) -> List[dict]:
    conditions = ["c.client_id=:cid", "c.is_active=TRUE"]
    params: Dict[str, Any] = {"cid": client_id}
    if bank_id is not None:
        conditions.append("c.bank_id=:bid")
        params["bid"] = bank_id
    if period is not None:
        conditions.append("c.period = :p")
        params["p"] = period
    if date_from is not None:
        conditions.append("c.created_at::date >= :dfrom")
        params["dfrom"] = date_from
    if date_to is not None:
        conditions.append("c.created_at::date <= :dto")
        params["dto"] = date_to

    sql = f"""
        SELECT c.id AS commit_id,
               c.period,
               b.bank_name,
               c.rows_committed,
               c.accuracy,
               c.created_at AS committed_at,
               c.committed_by
        FROM commits c
        JOIN banks b ON b.id = c.bank_id
        WHERE {" AND ".join(conditions)}
        ORDER BY c.created_at DESC, c.id DESC;
    """
    return _q(sql, params)
