# src/crud.py
from collections import Counter
import re
from sqlalchemy import text
from src.db import get_engine


def _q(sql: str, params=None):
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in res.fetchall()]


def _exec(sql: str, params=None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def list_vendor_memory(client_id: int):
    return _q("""
        SELECT vendor_name, category_name, confidence
        FROM vendor_memory
        WHERE client_id=:cid
        ORDER BY vendor_name;
    """, {"cid": client_id})


def list_categories(client_id: int):
    return _q("""
        SELECT id, category_name, type, nature, is_active
        FROM categories
        WHERE client_id=:cid AND is_active=true
        ORDER BY category_name;
    """, {"cid": client_id})


def list_draft_rows(client_id: int, bank_id: int, period: str):
    return _q("""
        SELECT id, tx_date, description, debit, credit, balance,
               suggested_category, suggested_vendor, confidence, reason,
               final_category, final_vendor
        FROM transactions_draft
        WHERE client_id=:cid AND bank_id=:bid AND period=:p
        ORDER BY tx_date, id;
    """, {"cid": client_id, "bid": bank_id, "p": period})


def committed_sample(client_id: int, bank_id: int, period: str, limit: int = 200):
    return _q("""
        SELECT tx_date, description, debit, credit, balance,
               category, vendor, confidence, reason
        FROM transactions_committed
        WHERE client_id=:cid AND bank_id=:bid AND period=:p
        ORDER BY tx_date, id
        LIMIT :lim;
    """, {"cid": client_id, "bid": bank_id, "p": period, "lim": limit})


def _tokenize(desc: str):
    if not desc:
        return []
    s = desc.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    toks = [t for t in s.split() if len(t) >= 3 and not t.isdigit()]
    return toks[:30]  # cap tokens


def _upsert_keyword_weight(client_id: int, token: str, category: str, delta: float):
    # Requires UNIQUE (client_id, token, category_name)
    _exec("""
      INSERT INTO keyword_model(client_id, token, category, weight)
VALUES (:cid, :t, :c, :w)
ON CONFLICT (client_id, token, category)
DO UPDATE SET weight = keyword_model.weight + EXCLUDED.weight;
    """, {"cid": client_id, "t": token, "c": category, "w": delta})


def _upsert_vendor_memory(client_id: int, vendor: str, category: str, conf_bump: float = 0.05):
    if not vendor:
        return
    _exec("""
        INSERT INTO vendor_memory(client_id, vendor_name, category_name, confidence)
        VALUES (:cid, :v, :c, 0.50)
        ON CONFLICT (client_id, vendor_name)
        DO UPDATE SET category_name = EXCLUDED.category_name,
                      confidence = LEAST(0.99, vendor_memory.confidence + :b),
                      updated_at = now();
    """, {"cid": client_id, "v": vendor.strip(), "c": category.strip(), "b": conf_bump})


def commit_period(client_id: int, bank_id: int, period: str, committed_by: str | None = None):
    """
    Commit all draft rows for a period where final_category is filled.
    Writes:
      - commits row
      - transactions_committed rows
      - learning updates (vendor_memory + keyword_model)
    """
    rows = list_draft_rows(client_id, bank_id, period)
    if not rows:
        return "Nothing to commit (no draft rows)."

    missing = [r for r in rows if not (r.get("final_category") or "").strip()]
    if missing:
        return f"Commit blocked: {len(missing)} rows missing Final Category."

    # accuracy vs suggested (simple)
    total = len(rows)
    matched = 0
    for r in rows:
        sc = (r.get("suggested_category") or "").strip()
        fc = (r.get("final_category") or "").strip()
        if sc and fc and sc.lower() == fc.lower():
            matched += 1
    accuracy = (matched / total) if total else None

    engine = get_engine()
    with engine.begin() as conn:
        # 1) Create commit header
        res = conn.execute(text("""
            INSERT INTO commits(client_id, bank_id, period, committed_by, rows_committed, accuracy)
            VALUES (:cid,:bid,:p,:by,:n,:acc)
            RETURNING id;
        """), {"cid": client_id, "bid": bank_id, "p": period, "by": committed_by, "n": total, "acc": accuracy})
        commit_id = res.fetchone()[0]

        # 2) Copy rows into committed table
        for r in rows:
            conn.execute(text("""
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
            """), {
                "cm": commit_id,
                "cid": client_id,
                "bid": bank_id,
                "p": period,
                "dt": r["tx_date"],
                "ds": r["description"],
                "dr": r.get("debit"),
                "cr": r.get("credit"),
                "bal": r.get("balance"),
                "cat": (r.get("final_category") or "").strip(),
                "ven": (r.get("final_vendor") or None),
                "sc": r.get("suggested_category"),
                "sv": r.get("suggested_vendor"),
                "cf": r.get("confidence"),
                "rs": r.get("reason"),
            })

        # 3) Update batch status
        conn.execute(text("""
            UPDATE draft_batches
            SET status='Committed', updated_at=now()
            WHERE client_id=:cid AND bank_id=:bid AND period=:p;
        """), {"cid": client_id, "bid": bank_id, "p": period})

    # 4) Learning updates (DEMO-SAFE: do not fail commit)
    try:
        for r in rows:
            cat = (r.get("final_category") or "").strip()
            ven = (r.get("final_vendor") or "").strip() or (r.get("suggested_vendor") or "").strip()
            if cat:
                if ven:
                    _upsert_vendor_memory(client_id, ven, cat, conf_bump=0.05)
                toks = _tokenize(r.get("description") or "")
                if toks:
                    freq = Counter(toks)
                    for t, c in freq.items():
                        _upsert_keyword_weight(client_id, t, cat, delta=0.10 * min(3, c))
    except Exception:
        # Demo: ignore learning failures, never block commit
        pass

    return f"Committed ✅ rows={total} accuracy={accuracy:.2%}" if accuracy is not None else f"Committed ✅ rows={total}"
