"""
tools/web_search.py
L2 Tool — Web search stub. Returns structured placeholder.
Upgrade path: DuckDuckGo API, SerpAPI, or Playwright scraping.
"""


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web for a query. Currently a stub.

    Args:
        query:       Search query string.
        max_results: Maximum number of results to return.

    Returns:
        dict with keys:
            ok      (bool)         — success flag
            results (list[dict])   — list of {title, url, snippet}
            error   (str)          — error message or empty string
    """
    # ── Stub implementation ──────────────────────────────────────────
    # Replace this block with a real search backend when ready.
    # Options:
    #   pip install duckduckgo-search  → from duckduckgo_search import DDGS
    #   pip install googlesearch-python
    #   Playwright for full browser scraping
    # ─────────────────────────────────────────────────────────────────

    return {
        "ok": False,
        "results": [],
        "error": (
            "web_search is not yet implemented. "
            "To enable: install duckduckgo-search and replace this stub."
        ),
    }
