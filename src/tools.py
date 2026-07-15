"""Search tools used by researcher branches.

Prefers Tavily (LLM-optimized results) when `TAVILY_API_KEY` is set, and
falls back to DuckDuckGo (no API key required) so the project runs
out of the box with zero paid or keyed services.
"""

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.logging_config import get_logger
from src.state import SourceSnippet

logger = get_logger(__name__)


def _search_tavily(query: str, max_results: int, api_key: str) -> list[SourceSnippet]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=max_results, search_depth="basic")
    results = []
    for item in response.get("results", []):
        results.append(
            SourceSnippet(
                url=item.get("url", ""),
                title=item.get("title", "Untitled"),
                snippet=(item.get("content", "") or "")[:800],
            )
        )
    return results


def _search_duckduckgo(query: str, max_results: int) -> list[SourceSnippet]:
    from duckduckgo_search import DDGS

    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append(
                SourceSnippet(
                    url=item.get("href", ""),
                    title=item.get("title", "Untitled"),
                    snippet=(item.get("body", "") or "")[:800],
                )
            )
    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def search_web(query: str, max_results: int | None = None) -> list[SourceSnippet]:
    """Search the web and return a list of source snippets.

    Tries Tavily first if configured, otherwise DuckDuckGo. Raises if both
    fail so the caller's own error-handling wraps the branch as failed
    rather than silently returning no evidence.
    """
    settings = get_settings()
    limit = max_results or settings.max_search_results

    if settings.tavily_api_key:
        try:
            logger.info("Searching via Tavily: %s", query)
            return _search_tavily(query, limit, settings.tavily_api_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily search failed (%s), falling back to DuckDuckGo", exc)

    logger.info("Searching via DuckDuckGo: %s", query)
    return _search_duckduckgo(query, limit)
