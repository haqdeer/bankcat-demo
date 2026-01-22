import re
from typing import Dict, List, Tuple, Optional

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _contains(desc: str, words: List[str]) -> bool:
    d = _norm(desc)
    return any(w in d for w in words)

def _pick_vendor(desc: str) -> str:
    """
    Very simple vendor guess:
    - tries to take first 2-5 words after POS/Purchase/To/From etc.
    """
    d = (desc or "").strip()
    if not d:
        return ""

    # Remove obvious prefixes
    d2 = re.sub(r"^(pos\s+purchase|pos|purchase|payment|paid|to|from|eft|transfer)\s+", "", d, flags=re.I)
    d2 = re.sub(r"\s+\d{4,}.*$", "", d2)  # remove trailing long IDs
    d2 = re.sub(r"\s{2,}", " ", d2).strip()

    # Keep first chunk
    parts = d2.split(" ")
    return " ".join(parts[:5]).strip()

def suggest_one(
    desc: str,
    debit: Optional[float],
    credit: Optional[float],
    bank_account_type: str,
    categories: List[Dict],
    vendor_memory: List[Dict],
) -> Tuple[Optional[str], Optional[str], float, str]:
    """
    Returns: (suggested_category_name, suggested_vendor, confidence, reason)
    """

    d = _norm(desc)
    is_debit = (debit or 0) > 0 and (credit or 0) in (0, None)
    is_credit = (credit or 0) > 0 and (debit or 0) in (0, None)

    # --- Vendor memory match (client-specific) ---
    # vendor_memory rows: vendor_name, category_name, confidence
    for vm in vendor_memory:
        v = _norm(vm.get("vendor_name", ""))
        if v and v in d:
            return vm.get("category_name"), vm.get("vendor_name"), float(vm.get("confidence") or 0.92), "Vendor memory match"

    # --- Rule keywords (MVP starter pack) ---
    rules = [
        ("Bank charges", ["bank charge", "service fee", "fee", "charges", "commission", "monthly fee"], 0.85),
        ("Cash withdrawal", ["atm", "cash withdrawal", "cashwd", "withdrawal"], 0.82),
        ("Consulting fee", ["consulting", "advisor", "advisory", "professional fee"], 0.78),
        ("Computer expenses/website", ["hosting", "domain", "website", "aws", "google workspace", "microsoft", "saas", "software"], 0.78),
        ("Clothing", ["tailor", "clothing", "apparel"], 0.72),
        ("Depreciation", ["depreciation"], 0.70),
        ("Internal Transfer", ["transfer", "eft", "trf", "to savings", "from savings", "internal transfer"], 0.75),
    ]

    for cat_name, kws, conf in rules:
        if _contains(desc, kws):
            v = _pick_vendor(desc)
            reason = f"Keyword rule: {cat_name}"
            # light nature boost
            if cat_name.lower() in ("sales", "income") and is_credit:
                conf += 0.05
            if cat_name.lower() in ("bank charges", "cash withdrawal") and is_debit:
                conf += 0.05
            return cat_name, v, min(conf, 0.95), reason

    # --- Soft nature guidance using your category master ---
    # category row fields: category_name, type, nature (could be Dr/Cr/Any or Debit/Credit/Any)
    best = None
    best_score = 0.40
    for c in categories:
        nm = c.get("category_name")
        nat = _norm(c.get("nature", ""))

        # normalize nature
        if nat in ("dr", "debit"):
            nat = "dr"
        elif nat in ("cr", "credit"):
            nat = "cr"
        elif nat in ("any", ""):
            nat = "any"

        score = 0.45
        if nat == "dr" and is_debit:
            score += 0.15
        if nat == "cr" and is_credit:
            score += 0.15
        if nat == "any":
            score += 0.05

        # account type hint
        at = _norm(bank_account_type)
        if "credit card" in at and is_debit:
            score += 0.05
        if ("current" in at or "checking" in at) and (is_debit or is_credit):
            score += 0.03
        if ("savings" in at or "investment" in at) and _contains(desc, ["interest", "profit", "dividend"]):
            score += 0.08

        if score > best_score:
            best_score = score
            best = nm

    v = _pick_vendor(desc)
    return best, v, float(best_score), "Nature+account-type heuristic"
