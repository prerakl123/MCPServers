"""Web search + page scraping.

Pipeline:
1. DuckDuckGo search via the `ddgs` library (more reliable than scraping HTML)
2. httpx fetch with browser-like headers and per-URL timeout
3. trafilatura main-content extraction (primary)
4. BeautifulSoup fallback when trafilatura returns <200 chars
5. Word-boundary truncation to max_chars_per_page

Iterates through URLs until `scrape_top` succeed or attempt cap is hit; one
slow/blocked site never sinks the call.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

import httpx
from bs4 import BeautifulSoup

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except Exception:  # pragma: no cover
    trafilatura = None  # type: ignore
    _HAS_TRAFILATURA = False

try:
    from ddgs import DDGS  # ddgs is the maintained successor of duckduckgo-search
    _HAS_DDGS = True
except Exception:  # pragma: no cover
    try:
        from duckduckgo_search import DDGS  # type: ignore
        _HAS_DDGS = True
    except Exception:
        DDGS = None  # type: ignore
        _HAS_DDGS = False

from ._logging import get_logger

log = get_logger("web_search")

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

_BROWSER_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_FETCH_TIMEOUT_S = 12
_MAX_BYTES_PER_PAGE = 4_000_000
_MAX_SCRAPE_ATTEMPTS = 10


def _ua_for(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc
    except Exception:
        host = ""
    return _USER_AGENTS[hash(host) % len(_USER_AGENTS)]


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(_FETCH_TIMEOUT_S, connect=6.0),
        follow_redirects=True,
        headers=_BROWSER_HEADERS,
        http2=False,
    )


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    if not _HAS_DDGS:
        log.error("ddgs library not available; install `ddgs` or `duckduckgo-search`")
        return []
    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)
            results: list[dict] = []
            for r in raw or []:
                # ddgs returns either {title, href, body} or {title, link, snippet}
                url = r.get("href") or r.get("link") or r.get("url") or ""
                title = r.get("title") or ""
                snippet = r.get("body") or r.get("snippet") or ""
                if url:
                    results.append({"title": title, "snippet": snippet, "url": url})
            return results
    except Exception as exc:
        log.warning("ddgs search failed: %s", exc)
        return []


def _fetch_page(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    if not url or not url.startswith(("http://", "https://")):
        return None, "invalid_url"
    try:
        resp = client.get(url, headers={"User-Agent": _ua_for(url)})
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.ConnectError as exc:
        return None, f"connect_error:{type(exc).__name__}"
    except httpx.HTTPError as exc:
        return None, f"http_error:{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return None, f"error:{type(exc).__name__}"

    if resp.status_code >= 400:
        return None, f"http_{resp.status_code}"

    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
        return None, f"non_text:{ctype.split(';')[0]}"

    raw = resp.content[:_MAX_BYTES_PER_PAGE]
    encoding = resp.encoding or "utf-8"
    try:
        return raw.decode(encoding, errors="replace"), None
    except LookupError:
        return raw.decode("utf-8", errors="replace"), None


def _extract_with_trafilatura(html_doc: str, url: str) -> str:
    if not _HAS_TRAFILATURA:
        return ""
    try:
        out = trafilatura.extract(
            html_doc,
            url=url,
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_recall=True,
            no_fallback=False,
        )
        return (out or "").strip()
    except Exception as exc:
        log.debug("trafilatura failed url=%s err=%s", url, exc)
        return ""


def _extract_with_bs4(html_doc: str) -> str:
    try:
        soup = BeautifulSoup(html_doc, "lxml")
    except Exception:
        soup = BeautifulSoup(html_doc, "html.parser")

    for tag in soup(["script", "style", "noscript", "template", "svg",
                     "head", "nav", "footer", "aside", "form", "iframe"]):
        tag.decompose()

    container = soup.find("main") or soup.find("article") or soup.body or soup
    text = container.get_text("\n", strip=True) if container else ""

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _scrape_one(client: httpx.Client, url: str, max_chars: int) -> dict:
    html_doc, err = _fetch_page(client, url)
    if err:
        return {"url": url, "ok": False, "error": err, "content": ""}

    text = _extract_with_trafilatura(html_doc or "", url)
    extractor = "trafilatura"
    if not text or len(text) < 200:
        bs_text = _extract_with_bs4(html_doc or "")
        if len(bs_text) > len(text):
            text = bs_text
            extractor = "bs4"

    if not text:
        return {"url": url, "ok": False, "error": "no_text_extracted", "content": ""}

    truncated = False
    if len(text) > max_chars:
        cut = text[:max_chars]
        sp = cut.rfind(" ")
        if sp > max_chars * 0.6:
            cut = cut[:sp]
        text = cut + "…"
        truncated = True

    return {
        "url": url,
        "ok": True,
        "extractor": extractor,
        "char_count": len(text),
        "truncated": truncated,
        "content": text,
    }


def search(
    query: str,
    max_results: int = 8,
    scrape: bool = True,
    scrape_top: int = 3,
    max_chars_per_page: int = 2000,
) -> dict[str, Any]:
    """Search the web, optionally scraping top results."""
    log.info(
        "web_search query=%r max_results=%d scrape=%s scrape_top=%d",
        query, max_results, scrape, scrape_top,
    )

    if not query:
        return {"error": "query is required", "results": []}

    max_results = max(1, min(int(max_results or 8), 15))
    scrape_top = max(0, min(int(scrape_top or 0), 5))
    max_chars_per_page = max(200, min(int(max_chars_per_page or 2000), 8000))

    results = _ddgs_search(query, max_results=max(max_results, scrape_top * 3, 8))

    if not results:
        return {
            "query": query,
            "result_count": 0,
            "scraped_count": 0,
            "scrape_attempts": 0,
            "results": [],
            "warning": "search returned no results (rate limit or transient failure)",
        }

    scraped_ok = 0
    attempts = 0
    scraped_urls: set[str] = set()

    if scrape and scrape_top > 0:
        with _client() as client:
            for r in results:
                if scraped_ok >= scrape_top:
                    break
                if attempts >= _MAX_SCRAPE_ATTEMPTS:
                    break
                url = r["url"]
                if url in scraped_urls:
                    continue
                scraped_urls.add(url)
                attempts += 1

                data = _scrape_one(client, url, max_chars=max_chars_per_page)
                if data["ok"]:
                    r["scrape_status"] = "ok"
                    r["scraped_content"] = data["content"]
                    r["extractor"] = data["extractor"]
                    r["char_count"] = data["char_count"]
                    r["truncated"] = data["truncated"]
                    scraped_ok += 1
                    log.info("scraped url=%s extractor=%s chars=%d",
                             url, data["extractor"], data["char_count"])
                else:
                    r["scrape_status"] = "failed"
                    r["scraped_content"] = None
                    r["scrape_error"] = data.get("error", "unknown")
                    log.warning("scrape failed url=%s err=%s", url, data.get("error"))

        for r in results:
            if "scrape_status" not in r:
                r["scrape_status"] = "skipped"
                r["scraped_content"] = None
    else:
        for r in results:
            r["scrape_status"] = "skipped"
            r["scraped_content"] = None

    successful = [r for r in results if r.get("scrape_status") == "ok"]
    others = [r for r in results if r.get("scrape_status") != "ok"]
    final = (successful + others)[:max(max_results, len(successful))]

    log.info("web_search done results=%d scraped_ok=%d attempts=%d",
             len(final), scraped_ok, attempts)

    return {
        "query": query,
        "result_count": len(final),
        "scraped_count": scraped_ok,
        "scrape_attempts": attempts,
        "results": final,
    }