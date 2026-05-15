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


def recall_at_k_strict(
    retrieved: list[str],
    gold: list[str],
    k: int,
) -> float:
    """STRICT R@K: full-URL exact match (path-normalized).

    Denominator: |norm_gold|.

    Disclosed in RESULTS.md as the conservative variant. A wrong article on
    the right domain does NOT count as a hit. Use this when reviewers want
    a reproducibility-first reading that doesn't reward domain-level
    overlap on fact-check sites that publish many articles per topic
    (snopes, factcheck.org, politifact, etc.).
    """
    if not gold:
        return 0.0
    top_k = retrieved[:k]
    norm_top = {_normalize(u) for u in top_k if u}
    norm_gold = {_normalize(u) for u in gold if u}
    hits = len(norm_top & norm_gold)
    return hits / len(norm_gold) if norm_gold else 0.0


def recall_at_k_domain_fallback(
    retrieved: list[str],
    gold: list[str],
    k: int,
) -> float:
    """LENIENT R@K with domain fallback: if no full-URL hits, fall back to
    domain-only matching. Denominator switches to |dom_gold| when fallback
    fires — see RESULTS.md disclosure for why this can fire R@K=1.0 where
    strict produces 0.5 when gold cites two URLs on the same domain.

    Disclosed in RESULTS.md as the lenient variant. Useful when reviewers
    want to credit "retrieved the right source, just not the exact gold
    article URL" — a common case on fact-check sites that publish many
    articles per topic.
    """
    if not gold:
        return 0.0
    top_k = retrieved[:k]
    norm_top = {_normalize(u) for u in top_k if u}
    norm_gold = {_normalize(u) for u in gold if u}
    hits = len(norm_top & norm_gold)
    if hits == 0:
        dom_top = {_domain(u) for u in top_k if u}
        dom_gold = {_domain(u) for u in gold if u}
        hits = len(dom_top & dom_gold)
        return hits / len(dom_gold) if dom_gold else 0.0
    return hits / len(norm_gold)


def recall_at_k(
    retrieved: list[str],
    gold: list[str],
    k: int,
    fall_back_to_domain: bool = True,
) -> float:
    """Backwards-compatible single-value R@K.

    Kept for API stability; new code SHOULD prefer `recall_at_k_strict` and
    `recall_at_k_domain_fallback` and report both. Per @beenz on the v0.2
    review thread (2026-05-15): a single R@K value hides which variant a
    reviewer is reading.

    When `fall_back_to_domain=True` (legacy default): behaves identically to
    `recall_at_k_domain_fallback`.
    When `fall_back_to_domain=False`: behaves identically to `recall_at_k_strict`.
    """
    if fall_back_to_domain:
        return recall_at_k_domain_fallback(retrieved, gold, k)
    return recall_at_k_strict(retrieved, gold, k)


def macro_recall_at_k_both(rows: list[dict], k: int) -> dict:
    """Report BOTH strict and lenient macro-R@K for full reviewer transparency.

    Returns:
        {
            "k": int,
            "n_claims": int,
            "strict": float,                   # full-URL exact match only
            "domain_fallback": float,          # lenient with domain fallback
            "strict_minus_lenient": float,     # absolute delta (negative = lenient is higher)
            "fallback_fires_count": int,       # how many claims actually hit the domain-fallback path
            "fallback_fires_pct": float,       # fraction of claims that hit fallback
        }

    Per @beenz: lets readers compute both and see the gap.
    """
    if not rows:
        return {
            "k": k,
            "n_claims": 0,
            "strict": 0.0,
            "domain_fallback": 0.0,
            "strict_minus_lenient": 0.0,
            "fallback_fires_count": 0,
            "fallback_fires_pct": 0.0,
        }
    strict_scores = []
    lenient_scores = []
    fallback_fires = 0
    for r in rows:
        retrieved = r.get("sources", [])
        gold = r.get("gold_urls", [])
        s = recall_at_k_strict(retrieved, gold, k)
        l = recall_at_k_domain_fallback(retrieved, gold, k)
        strict_scores.append(s)
        lenient_scores.append(l)
        if s == 0.0 and l > 0.0:
            fallback_fires += 1
    strict_macro = sum(strict_scores) / len(strict_scores)
    lenient_macro = sum(lenient_scores) / len(lenient_scores)
    return {
        "k": k,
        "n_claims": len(rows),
        "strict": strict_macro,
        "domain_fallback": lenient_macro,
        "strict_minus_lenient": strict_macro - lenient_macro,
        "fallback_fires_count": fallback_fires,
        "fallback_fires_pct": fallback_fires / len(rows),
    }


def macro_recall_at_k(rows: list[dict], k: int) -> float:
    """Backwards-compatible macro-average. Returns the lenient (domain-fallback) value.

    Per @beenz: new code SHOULD call `macro_recall_at_k_both` instead so
    both variants ship in RESULTS.md.
    """
    if not rows:
        return 0.0
    scores = [recall_at_k_domain_fallback(r.get("sources", []), r.get("gold_urls", []), k) for r in rows]
    return sum(scores) / len(scores)
