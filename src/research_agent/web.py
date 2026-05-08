from __future__ import annotations

import html
import re
from typing import Any

import httpx


class DuckDuckGoSearchTool:
    def __init__(self, http_client: Any | None = None, *, timeout: float = 20.0) -> None:
        self.http_client = http_client or httpx.Client()
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        response = self.http_client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "research-agent/0.1"},
            follow_redirects=True,
            timeout=self.timeout,
        )
        response.raise_for_status()
        blocks = re.findall(r"<div[^>]*class=['\"]result['\"][^>]*>(.*?)</div>\s*</div>?", response.text, flags=re.S)
        if not blocks:
            blocks = re.findall(r"<div[^>]*class=['\"]result['\"][^>]*>(.*?)</div>", response.text, flags=re.S)
        results: list[dict[str, str]] = []
        for block in blocks:
            link_match = re.search(r"<a[^>]*class=['\"]result__a['\"][^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", block, flags=re.S)
            if not link_match:
                continue
            snippet_match = re.search(r"class=['\"]result__snippet['\"][^>]*>(.*?)</a?>", block, flags=re.S)
            results.append(
                {
                    "title": _clean_text(_strip_tags(link_match.group(2))),
                    "url": html.unescape(link_match.group(1)),
                    "snippet": _clean_text(_strip_tags(snippet_match.group(1))) if snippet_match else "",
                }
            )
            if len(results) >= max_results:
                break
        return results


class WebPageFetcher:
    def __init__(self, http_client: Any | None = None, *, timeout: float = 20.0, max_chars: int = 6000) -> None:
        self.http_client = http_client or httpx.Client()
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch(self, url: str) -> dict[str, str]:
        response = self.http_client.get(
            url,
            headers={"User-Agent": "research-agent/0.1"},
            follow_redirects=True,
            timeout=self.timeout,
        )
        response.raise_for_status()
        html_text = response.text
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.S | re.I)
        content_root = _extract_first(html_text, ["main", "article", "body"]) or html_text
        content_root = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", content_root, flags=re.S | re.I)
        content_root = re.sub(r"<(nav|header|footer|aside)(?:\s[^>]*)?>.*?</\1>", " ", content_root, flags=re.S | re.I)
        text = _clean_text(_strip_tags(content_root))
        if len(text) > self.max_chars:
            text = text[: self.max_chars].rsplit(" ", 1)[0] + "…"
        return {
            "title": _clean_text(_strip_tags(title_match.group(1))) if title_match else url,
            "url": str(getattr(response, "url", url)),
            "content": text,
        }


def _extract_first(html_text: str, tags: list[str]) -> str | None:
    for tag in tags:
        match = re.search(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", html_text, flags=re.S | re.I)
        if match:
            return match.group(1)
    return None


def _strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
