"""is_person heuristic (Layer 1 fallback).

Three-tier logic per design.md §"个人股东" 判定:
- prefer `holder_nature` from top10_free_holders ('个人' → True, others → False)
- fall back to institution-keyword blacklist
- manual overrides live in entities.user_annotation (applied separately)
"""
from __future__ import annotations

INSTITUTION_KEYWORDS: tuple[str, ...] = (
    "公司", "集团", "银行", "基金", "委员会", "中心", "合伙", "有限",
    "股份", "控股", "投资", "资本", "资管", "管理", "信托", "保险",
    "证券", "财险", "财产", "人寿", "财务", "局", "部", "协会", "工会",
    "LIMITED", "NOMINEES", "HKSCC",
)


def is_person_heuristic(name: str, nature: str | None) -> bool:
    if nature == "个人":
        return True
    if nature and nature != "个人":
        return False
    upper = name.upper()
    return not any(k in name or k in upper for k in INSTITUTION_KEYWORDS)


def market_prefix(code: str) -> str:
    """Map a raw 6-digit stock code to its prefixed form."""
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8", "92")):
        return f"bj{code}"
    return f"sz{code}"
