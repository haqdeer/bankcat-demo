import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime


def _normalize_text(s: str) -> str:
    """Normalize text for matching"""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _contains_any(desc: str, words: List[str]) -> bool:
    """Check if description contains any of the words"""
    d = _normalize_text(desc)
    return any(f" {w} " in f" {d} " for w in words)


def _extract_vendor(desc: str) -> str:
    """
    Smart vendor extraction from transaction description
    Removes common prefixes and extracts merchant name
    """
    desc = (desc or "").strip()
    if not desc:
        return ""
    
    # Common prefixes to remove
    prefixes = [
        r"^pos\s+purchase\s*",
        r"^pos\s*",
        r"^purchase\s*", 
        r"^payment\s+to\s+",
        r"^payment\s*",
        r"^paid\s+to\s+",
        r"^to\s+",
        r"^from\s+",
        r"^eft\s+",
        r"^transfer\s+",
        r"^trf\s+",
        r"^card\s+purchase\s*",
        r"^debit\s+card\s+",
        r"^credit\s+card\s+",
    ]
    
    # Remove prefixes
    cleaned = desc.lower()
    for prefix in prefixes:
        cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE)
    
    # Remove trailing numbers, IDs, amounts
    cleaned = re.sub(r"\s+\d{4,}.*$", "", cleaned)  # Long IDs
    cleaned = re.sub(r"\s+\d+\.\d{2}.*$", "", cleaned)  # Amounts like 123.45
    cleaned = re.sub(r"\s+ref\s*.*$", "", cleaned, flags=re.IGNORECASE)  # Ref numbers
    cleaned = re.sub(r"\s+id\s*.*$", "", cleaned, flags=re.IGNORECASE)  # IDs
    
    # Extract first meaningful chunk (2-4 words)
    words = cleaned.strip().split()
    meaningful_words = []
    
    for word in words[:6]:  # Limit to first 6 words
        if len(word) >= 2 and not word.isdigit():
            # Skip common filler words
            if word not in ["at", "on", "the", "and", "or", "for", "via", "by"]:
                meaningful_words.append(word)
    
    vendor = " ".join(meaningful_words[:4])  # Max 4 words
    
    # Capitalize each word for display
    return vendor.title() if vendor else ""


def _calculate_base_confidence(match_type: str, factors: Dict) -> float:
    """
    Calculate confidence score based on multiple factors
    """
    base_scores = {
        "vendor_memory": 0.85,
        "keyword_match": 0.75,
        "rule_match": 0.80,
        "nature_heuristic": 0.60,
        "account_type_heuristic": 0.55,
        "fallback": 0.40
    }
    
    confidence = base_scores.get(match_type, 0.50)
    
    # Boost factors
    if factors.get("exact_vendor_match"):
        confidence += 0.10
    if factors.get("multiple_keywords"):
        confidence += 0.08
    if factors.get("historical_high_accuracy"):
        confidence += 0.07
    if factors.get("consistent_dr_cr"):
        confidence += 0.05
    
    # Penalty factors
    if factors.get("ambiguous_description"):
        confidence -= 0.15
    if factors.get("first_time_vendor"):
        confidence -= 0.10
    if factors.get("contradicts_nature"):
        confidence -= 0.20
    
    # Clamp between 0.30 and 0.95
    return max(0.30, min(0.95, confidence))


def _get_category_nature_score(category_nature: str, is_debit: bool, is_credit: bool) -> float:
    """
    Score how well category nature matches transaction type
    Returns: 1.0 = perfect match, 0.5 = neutral, 0.0 = contradiction
    """
    nature = (category_nature or "").lower().strip()
    
    if nature in ["any", ""]:
        return 0.5
    
    if nature in ["dr", "debit"]:
        return 1.0 if is_debit else 0.0
    
    if nature in ["cr", "credit"]:
        return 1.0 if is_credit else 0.0
    
    return 0.5


def _get_account_type_context(bank_account_type: str) -> Dict:
    """
    Get context hints based on bank account type
    """
    atype = (bank_account_type or "").lower()
    
    context = {
        "likely_expense": False,
        "likely_income": False,
        "likely_transfer": False,
        "common_keywords": []
    }
    
    if "credit" in atype or "card" in atype:
        context["likely_expense"] = True
        context["common_keywords"] = ["purchase", "payment", "charge", "fee", "interest"]
    
    elif "current" in atype or "checking" in atype:
        context["likely_expense"] = True
        context["likely_income"] = True
        context["common_keywords"] = ["deposit", "withdrawal", "transfer", "fee"]
    
    elif "savings" in atype:
        context["likely_transfer"] = True
        context["common_keywords"] = ["interest", "transfer", "dividend"]
    
    elif "investment" in atype:
        context["likely_income"] = True
        context["common_keywords"] = ["dividend", "interest", "profit", "sale"]
    
    return context


def suggest_one(
    desc: str,
    debit: Optional[float],
    credit: Optional[float],
    bank_account_type: str,
    categories: List[Dict],
    vendor_memory: List[Dict],
    keyword_weights: List[Dict],
) -> Tuple[Optional[str], Optional[str], float, str]:
    """
    Enhanced suggestion engine with multiple factors
    
    Returns: (suggested_category_name, suggested_vendor, confidence, reason)
    """
    
    # Normalize inputs
    desc = (desc or "").strip()
    is_debit = (debit or 0) > 0 and (credit or 0) in (0, None)
    is_credit = (credit or 0) > 0 and (debit or 0) in (0, None)
    
    # Extract vendor
    vendor = _extract_vendor(desc)
    normalized_vendor = _normalize_text(vendor)
    normalized_desc = _normalize_text(desc)
    
    # Get account type context
    account_context = _get_account_type_context(bank_account_type)
    
    # Prepare categories with scores
    category_scores = []
    
    for cat in categories:
        cat_name = cat.get("category_name", "")
        cat_type = cat.get("type", "").lower()  # income/expense/other
        cat_nature = cat.get("nature", "Any")  # Dr/Cr/Any
        
        # Skip if not active
        if not cat.get("is_active", True):
            continue
        
        # Initialize score
        score = 0.0
        reasons = []
        match_type = "none"
        
        # 1. Vendor Memory Match (highest priority)
        for vm in vendor_memory:
            vm_vendor = _normalize_text(vm.get("vendor_key", ""))
            vm_category = vm.get("category", "")
            
            if vm_vendor and vm_vendor in normalized_desc and vm_category == cat_name:
                score += 0.8
                reasons.append(f"Vendor memory: {vm_vendor}")
                match_type = "vendor_memory"
                break
        
        # 2. Keyword Weight Match
        if match_type == "none" and keyword_weights:
            for kw in keyword_weights:
                token = _normalize_text(kw.get("token", ""))
                kw_category = kw.get("category", "")
                weight = float(kw.get("weight", 0))
                
                if (token and len(token) >= 3 and 
                    token in normalized_desc and 
                    kw_category == cat_name):
                    score += min(0.6, weight / 10.0)
                    reasons.append(f"Keyword: {token}")
                    if match_type != "vendor_memory":
                        match_type = "keyword_match"
        
        # 3. Nature Match Score
        nature_score = _get_category_nature_score(cat_nature, is_debit, is_credit)
        if nature_score > 0:
            score += nature_score * 0.3
            reasons.append(f"Nature: {cat_nature}")
            if match_type == "none":
                match_type = "nature_heuristic"
        
        # 4. Account Type Context
        if cat_type == "expense" and account_context.get("likely_expense"):
            score += 0.2
            reasons.append("Account type: likely expense")
        elif cat_type == "income" and account_context.get("likely_income"):
            score += 0.2
            reasons.append("Account type: likely income")
        
        # 5. Rule-based keywords (common patterns)
        rule_keywords = {
            "Bank Charges": ["bank charge", "service fee", "monthly fee", "commission"],
            "Cash Withdrawal": ["atm", "cash withdrawal", "cashwd"],
            "Consulting Fee": ["consulting", "advisor", "professional fee"],
            "Software Subscriptions": ["software", "saas", "subscription", "hosting"],
            "Office Supplies": ["stationery", "office supplies", "printing"],
            "Travel Expenses": ["travel", "hotel", "flight", "uber", "transport"],
            "Meals & Entertainment": ["restaurant", "cafe", "coffee", "food", "dinner"],
            "Internal Transfer": ["transfer", "eft", "trf", "to savings", "from savings"],
        }
        
        for rule_cat, keywords in rule_keywords.items():
            if cat_name == rule_cat and _contains_any(desc, keywords):
                score += 0.4
                reasons.append(f"Rule match: {keywords[0]}")
                if match_type in ["none", "nature_heuristic"]:
                    match_type = "rule_match"
        
        # Store category with score and reasons
        if score > 0:
            category_scores.append({
                "category": cat_name,
                "score": score,
                "reasons": reasons,
                "match_type": match_type,
                "type": cat_type,
                "nature": cat_nature
            })
    
    # Sort categories by score (highest first)
    category_scores.sort(key=lambda x: x["score"], reverse=True)
    
    # Select best category
    suggested_category = None
    suggested_vendor = vendor
    confidence = 0.40
    reason = "Default fallback"
    
    if category_scores:
        best = category_scores[0]
        suggested_category = best["category"]
        
        # Calculate confidence
        factors = {
            "exact_vendor_match": best["match_type"] == "vendor_memory",
            "multiple_keywords": len([r for r in best["reasons"] if "Keyword" in r]) > 1,
            "ambiguous_description": len(desc.split()) < 3,
            "first_time_vendor": not normalized_vendor,
            "contradicts_nature": False,  # Would be calculated from nature_score
            "consistent_dr_cr": _get_category_nature_score(best["nature"], is_debit, is_credit) > 0.5
        }
        
        confidence = _calculate_base_confidence(best["match_type"], factors)
        reason = ", ".join(best["reasons"][:2])  # Show top 2 reasons
        
        # Special handling for low confidence
        if confidence < 0.50:
            reason += " (Low confidence)"
    
    # Fallback if no category found
    if not suggested_category and categories:
        # Get default based on transaction type
        if is_credit:
            # Look for income categories
            income_cats = [c for c in categories if c.get("type", "").lower() == "income"]
            if income_cats:
                suggested_category = income_cats[0].get("category_name")
                reason = "Fallback: Credit transaction → Income"
                confidence = 0.45
        else:
            # Default to first expense category
            expense_cats = [c for c in categories if c.get("type", "").lower() == "expense"]
            if expense_cats:
                suggested_category = expense_cats[0].get("category_name")
                reason = "Fallback: Debit transaction → Expense"
                confidence = 0.45
        
        # Ultimate fallback
        if not suggested_category:
            suggested_category = categories[0].get("category_name")
            reason = "Fallback: First available category"
            confidence = 0.40
    
    return suggested_category, suggested_vendor, confidence, reason


# Helper function for crud.py integration
def get_keyword_weights_for_client(keyword_weights: List[Dict]) -> Dict[str, Tuple[str, float]]:
    """
    Convert keyword weights to token->(category, weight) mapping
    """
    token_best: Dict[str, Tuple[str, float]] = {}
    for r in keyword_weights:
        t = _normalize_text(r.get("token", ""))
        c = r.get("category", "")
        w = float(r.get("weight", 0))
        
        if t and len(t) >= 3 and c:
            if t not in token_best or w > token_best[t][1]:
                token_best[t] = (c, w)
    
    return token_best
