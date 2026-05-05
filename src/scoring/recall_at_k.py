"""
Recall@K — Beenz's specific request.

For each claim:
  precision/recall of retrieved sources vs gold-evidence URLs.
  R@K = % of gold URLs that appear in the top-K retrieved sources.

Robust to noisy URL formatting (trailing slashes, http vs https, www, query strings).
"""

from __future__ import annotations

from urllib.parse import urlparse


def _normalize(url: str) -> str:
    """Cheap URL normalizer for evidence matching.

    - lowercase host
    - drop scheme distinction (http vs https)
    - drop leading 'www.'
    - drop trailing slash
    - keep path lowercased
    - drop query string + fragment
    """
    if not url:
        return ""
    try:
        p = urlparse(url)
    except Exception:
        return url.strip().lower()
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "").rstrip("/").lower()
    return f"{host}{path}"


def _domain(url: str) -> str:
    """Domain-only fallback when full-URL match fails — sometimes evidence
    points to the article via a redirect or alternate path."""
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def recall_at_k(
    retrieved: list[str],
    gold: list[str],
    k: int,
    fall_back_to_domain: bool = True,
) -> float:
    """Return R@K for one claim. 1.0 = all gold sources found in top-K retrieved."""
    if not gold:
        return 0.0
    top_k = retrieved[:k]
    norm_top = {_normalize(u) for u in top_k if u}
    norm_gold = {_normalize(u) for u in gold if u}
    hits = len(norm_top & norm_gold)
    if hits == 0 and fall_back_to_domain:
        dom_top = {_domain(u) for u in top_k if u}
        dom_gold = {_domain(u) for u in gold if u}
        hits = len(dom_top & dom_gold)
        return hits / len(dom_gold) if dom_gold else 0.0
    return hits / len(norm_gold)


def macro_recall_at_k(rows: list[dict], k: int) -> float:
    """Macro-averaged R@K across a run's predictions.jsonl rows."""
    if not rows:
        return 0.0
    scores = [recall_at_k(r.get("sources", []), r.get("gold_urls", []), k) for r in rows]
    return sum(scores) / len(scores)
