#!/usr/bin/env python3
"""
Web search module — безкоштовний пошук в інтернеті через DuckDuckGo + Wikipedia.

Не потребує API ключів. Використовується Жасмін для отримання актуальної
інформації коли її немає в локальній базі знань.
"""

from __future__ import annotations

import re
import html
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# --- Тригери ---
_SEARCH_KEYWORDS = [
    "пошукай", "знайди", "загугли", "погугли", "глянь в інтернет",
    "глянь в інтернеті", "перевір в інтернеті", "що пишуть", "що нового про",
    "новини про", "актуальн", "сьогодні", "вчора", "цього тижня",
    "пошук", "search", "google", "знайди в мережі",
]

_FACT_KEYWORDS = [
    "хто такий", "хто така", "що таке", "коли народив", "коли помер",
    "де знаходиться", "столиця", "населення", "біографія", "wikipedia",
    "вікіпедія",
]


def should_search(text: str) -> Optional[str]:
    """Повертає 'web' / 'wiki' / None залежно від типу запиту."""
    t = text.lower()
    if any(kw in t for kw in _FACT_KEYWORDS):
        return "wiki"
    if any(kw in t for kw in _SEARCH_KEYWORDS):
        return "web"
    return None


# --- DuckDuckGo ---
_DDG_LINK_RE = re.compile(
    r'<a\s+rel="nofollow"\s+href="([^"]+)"\s+class=[\'"]result-link[\'"][^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_DDG_SNIPPET_RE = re.compile(
    r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def duckduckgo_search(query: str, max_results: int = 5, timeout: int = 10) -> List[Dict[str, str]]:
    """
    Безкоштовний DuckDuckGo пошук без API ключа.
    Використовує бібліотеку ddgs (надійніше за прямий парсинг).
    """
    # Primary: ddgs library
    try:
        from ddgs import DDGS  # type: ignore
        with DDGS(timeout=timeout) as ddgs:
            raw = list(ddgs.text(query, max_results=max_results, region="wt-wt"))
        results = []
        for item in raw:
            results.append({
                "url": item.get("href") or item.get("url") or "",
                "title": item.get("title", "") or "",
                "snippet": item.get("body") or item.get("snippet") or "",
            })
        if results:
            return results
    except Exception as exc:
        print(f"[WebSearch] ddgs error: {exc}")

    # Fallback: direct HTTP scraping
    try:
        resp = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query, "kl": ""},
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "uk,en;q=0.9",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text
        links = _DDG_LINK_RE.findall(text)
        snippets = _DDG_SNIPPET_RE.findall(text)
        results = []
        for i, (url_, title) in enumerate(links):
            if len(results) >= max_results:
                break
            if url_.startswith("/"):
                continue
            snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
            results.append({
                "url": url_,
                "title": _strip_tags(title),
                "snippet": snippet,
            })
        return results
    except Exception as exc:
        print(f"[WebSearch] DuckDuckGo HTTP fallback error: {exc}")
        return []


# --- Wikipedia ---
def wikipedia_search(
    query: str,
    lang: str = "uk",
    max_results: int = 3,
    timeout: int = 10,
) -> List[Dict[str, str]]:
    """
    Wikipedia REST API — безкоштовно, без ключа.
    Спочатку шукає сторінки, потім бере summary найкращої.
    """
    try:
        # 1. Search
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        resp = requests.get(
            search_url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("query", {}).get("search", [])

        results = []
        for item in data[:max_results]:
            title = item.get("title", "")
            if not title:
                continue
            # 2. Summary
            try:
                sresp = requests.get(
                    f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}",
                    headers={"User-Agent": _USER_AGENT},
                    timeout=timeout,
                )
                if sresp.ok:
                    sdata = sresp.json()
                    extract = sdata.get("extract", "")
                    page_url = (
                        sdata.get("content_urls", {}).get("desktop", {}).get("page")
                        or f"https://{lang}.wikipedia.org/wiki/{quote_plus(title)}"
                    )
                else:
                    extract = _strip_tags(item.get("snippet", ""))
                    page_url = f"https://{lang}.wikipedia.org/wiki/{quote_plus(title)}"
            except Exception:
                extract = _strip_tags(item.get("snippet", ""))
                page_url = f"https://{lang}.wikipedia.org/wiki/{quote_plus(title)}"

            results.append({
                "title": title,
                "url": page_url,
                "snippet": extract,
            })
        return results
    except Exception as exc:
        print(f"[WebSearch] Wikipedia error: {exc}")
        # Fallback на англійську Вікіпедію
        if lang != "en":
            return wikipedia_search(query, lang="en", max_results=max_results, timeout=timeout)
        return []


# --- Orchestrator ---
def web_search(
    query: str,
    source: str = "auto",
    max_results: int = 5,
) -> List[Dict[str, str]]:
    """
    Універсальний пошук. source: 'auto' | 'web' | 'wiki' | 'both'.
    """
    if source == "auto":
        source = should_search(query) or "web"

    if source == "wiki":
        results = wikipedia_search(query, max_results=max_results)
        if not results:
            results = duckduckgo_search(query, max_results=max_results)
        return results

    if source == "both":
        wiki = wikipedia_search(query, max_results=max(2, max_results // 2))
        web = duckduckgo_search(query, max_results=max_results - len(wiki))
        return wiki + web

    return duckduckgo_search(query, max_results=max_results)


def format_search_context(results: List[Dict[str, str]], max_chars: int = 2000) -> str:
    """Форматує результати пошуку у текстовий контекст для LLM."""
    if not results:
        return ""
    lines = ["Результати пошуку в інтернеті:"]
    used = 0
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        snippet = r.get("snippet", "").strip()
        url = r.get("url", "").strip()
        chunk = f"\n{i}. {title}\n   {snippet}\n   Джерело: {url}"
        if used + len(chunk) > max_chars:
            break
        lines.append(chunk)
        used += len(chunk)
    return "".join(lines) if len(lines) > 1 else ""


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "Київ столиця України"
    print(f"=== Query: {q} ===\n")
    print("--- DuckDuckGo ---")
    for r in duckduckgo_search(q, max_results=3):
        print(f"• {r['title']}\n  {r['snippet'][:150]}\n  {r['url']}\n")
    print("--- Wikipedia ---")
    for r in wikipedia_search(q, max_results=2):
        print(f"• {r['title']}\n  {r['snippet'][:200]}\n  {r['url']}\n")
