from __future__ import annotations

from typing import Any, Dict, List, Tuple


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def clamp_int(x: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(x)
        return max(lo, min(hi, v))
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def monthly_interest(balance: float, apr_pct: float) -> float:
    if balance <= 0:
        return 0.0
    if apr_pct <= 0:
        return 0.0
    return balance * (apr_pct / 100.0) / 12.0


def validate_bill(b: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Returns (ok, errors, cleaned_bill)
    """
    errors: List[str] = []
    cleaned = dict(b)

    name = str(cleaned.get("name", "")).strip()
    if not name:
        errors.append("Missing name.")
    cleaned["name"] = name

    amount = safe_float(cleaned.get("amount", 0.0), 0.0)
    if amount <= 0:
        errors.append("Amount must be > 0.")
    cleaned["amount"] = amount

    cleaned["due_day"] = clamp_int(cleaned.get("due_day", 1), 1, 31, 1)
    cleaned["apr"] = max(0.0, safe_float(cleaned.get("apr", 0.0), 0.0))
    cleaned["min_payment"] = max(0.0, safe_float(cleaned.get("min_payment", 0.0), 0.0))

    planned = safe_float(cleaned.get("planned_payment", cleaned["min_payment"]), cleaned["min_payment"])
    cleaned["planned_payment"] = max(0.0, planned)

    cleaned["include_in_strategy"] = bool(cleaned.get("include_in_strategy", True))
    cleaned["status"] = str(cleaned.get("status", "Current") or "Current")
    cleaned["notes"] = str(cleaned.get("notes", "") or "").strip()

    try:
        cleaned["custom_order"] = int(cleaned.get("custom_order", 999999) or 999999)
    except Exception:
        cleaned["custom_order"] = 999999

    ov = cleaned.get("override", {}) or {}
    cleaned["override"] = ov if isinstance(ov, dict) else {}

    ok = len(errors) == 0
    return ok, errors, cleaned


def find_duplicates(bills: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """
    Returns mapping normalized_name -> list of row indices where it appears (only duplicates included)
    """
    seen: Dict[str, List[int]] = {}
    for i, b in enumerate(bills):
        key = normalize_name(str(b.get("name", "")))
        if not key:
            continue
        seen.setdefault(key, []).append(i)

    return {k: idxs for k, idxs in seen.items() if len(idxs) > 1}


def payoff_risk_flags(bills: List[Dict[str, Any]]) -> List[str]:
    """
    Returns human-friendly warnings for obvious payoff risks.
    """
    warnings: List[str] = []
    for b in bills:
        name = str(b.get("name", "Unnamed")).strip() or "Unnamed"
        bal = safe_float(b.get("amount", 0.0))
        apr = safe_float(b.get("apr", 0.0))
        pay = safe_float(b.get("planned_payment", b.get("min_payment", 0.0)))
        if bal > 0 and apr > 0 and pay > 0:
            mi = monthly_interest(bal, apr)
            if pay <= mi:
                warnings.append(
                    f"**{name}**: planned payment ${pay:,.2f} may not cover monthly interest (~${mi:,.2f})."
                )
    return warnings