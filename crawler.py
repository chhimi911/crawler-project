from __future__ import annotations

import argparse
import asyncio
import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote, urljoin, urldefrag, urlparse, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
import tldextract


DEFAULT_OUTPUT = Path("links.txt")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
TLD_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=None,
    cache_dir=str(Path(".tldextract-cache")),
)


@dataclass(frozen=True)
class CrawlConfig:
    root_url: str
    max_depth: int
    domain_lock: bool = True
    output_file: Path | None = DEFAULT_OUTPUT


def normalize_url(candidate: str, base_url: str) -> str | None:
    sanitized_candidate = re.sub(r"[\x00-\x1f\x7f]+", "", candidate).strip()
    absolute = urljoin(base_url, sanitized_candidate)
    clean, _fragment = urldefrag(absolute)
    split = urlsplit(clean)
    sanitized_path = quote(split.path or "/", safe="/:@!$&'()*+,;=-._~")
    sanitized_query = quote(split.query, safe="=&/:?@!$'()*+,;%-._~")
    rebuilt = urlunsplit(
        (split.scheme, split.netloc, sanitized_path, sanitized_query, "")
    )
    parsed = urlparse(rebuilt)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    path = parsed.path or "/"
    normalized = parsed._replace(path=path, params="", query=parsed.query, fragment="")
    return normalized.geturl()


def same_registered_domain(first_url: str, second_url: str) -> bool:
    first = TLD_EXTRACTOR(first_url)
    second = TLD_EXTRACTOR(second_url)
    return bool(first.top_domain_under_public_suffix) and (
        first.top_domain_under_public_suffix == second.top_domain_under_public_suffix
    )


def filter_links(links: Iterable[str], root_url: str, domain_lock: bool) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()

    for link in links:
        if domain_lock and not same_registered_domain(link, root_url):
            continue
        if link in seen:
            continue
        seen.add(link)
        filtered.append(link)

    return filtered


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    candidates: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not href:
            continue
        normalized = normalize_url(href, base_url)
        if normalized:
            candidates.append(normalized)

    return candidates


async def fetch_links_from_page(page: Page, url: str) -> list[str]:
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    html = await page.content()
    return extract_links_from_html(html, url)


async def fetch_links(browser_context: BrowserContext, url: str) -> list[str]:
    page = await browser_context.new_page()
    try:
        return await fetch_links_from_page(page, url)
    except Exception:
        return []
    finally:
        await page.close()


def fetch_links_via_http_sync(url: str) -> list[str]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []

    return extract_links_from_html(html, url)


async def fetch_links_via_http(url: str) -> list[str]:
    return await asyncio.to_thread(fetch_links_via_http_sync, url)


def get_browser_launch_options() -> dict[str, object]:
    # Vercel's Python runtime is serverless and only supports headless Chromium.
    options: dict[str, object] = {
        "headless": True,
        "chromium_sandbox": False,
    }

    if os.getenv("VERCEL"):
        options["args"] = [
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-zygote",
        ]

    return options


def should_use_playwright() -> bool:
    if os.getenv("CRAWLER_USE_PLAYWRIGHT") == "1":
        return True
    if os.getenv("VERCEL"):
        return False
    return True


async def crawl_with_http(config: CrawlConfig, root_url: str) -> list[str]:
    visited: set[str] = {root_url}
    ordered_results: list[str] = [root_url]
    queue: deque[tuple[str, int]] = deque([(root_url, 0)])

    while queue:
        current_depth = queue[0][1]
        level_items: list[tuple[str, int]] = []

        while queue and queue[0][1] == current_depth:
            level_items.append(queue.popleft())

        if current_depth >= config.max_depth:
            continue

        tasks = [fetch_links_via_http(url) for url, _depth in level_items]
        results = await asyncio.gather(*tasks)

        for (_source_url, _depth), extracted_links in zip(level_items, results):
            for link in filter_links(extracted_links, root_url, config.domain_lock):
                if link in visited:
                    continue
                visited.add(link)
                ordered_results.append(link)
                queue.append((link, current_depth + 1))

    return ordered_results


async def crawl(config: CrawlConfig) -> list[str]:
    if config.max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    root_url = normalize_url(config.root_url, config.root_url)
    if not root_url:
        raise ValueError("root_url must be a valid http(s) URL")

    visited: set[str] = {root_url}
    ordered_results: list[str] = [root_url]
    queue: deque[tuple[str, int]] = deque([(root_url, 0)])

    if should_use_playwright():
        try:
            async with async_playwright() as playwright:
                browser: Browser = await playwright.chromium.launch(**get_browser_launch_options())
                context = await browser.new_context()

                try:
                    while queue:
                        current_depth = queue[0][1]
                        level_items: list[tuple[str, int]] = []

                        while queue and queue[0][1] == current_depth:
                            level_items.append(queue.popleft())

                        if current_depth >= config.max_depth:
                            continue

                        tasks = [fetch_links(context, url) for url, _depth in level_items]
                        results = await asyncio.gather(*tasks)

                        for (_source_url, _depth), extracted_links in zip(level_items, results):
                            for link in filter_links(extracted_links, root_url, config.domain_lock):
                                if link in visited:
                                    continue
                                visited.add(link)
                                ordered_results.append(link)
                                queue.append((link, current_depth + 1))
                finally:
                    await context.close()
                    await browser.close()
        except Exception:
            ordered_results = await crawl_with_http(config, root_url)
    else:
        ordered_results = await crawl_with_http(config, root_url)

    if config.output_file is not None:
        config.output_file.write_text("\n".join(ordered_results) + "\n", encoding="utf-8")
    return ordered_results


def parse_args() -> CrawlConfig:
    parser = argparse.ArgumentParser(description="Recursive domain-locked crawler")
    parser.add_argument("root_url", help="Root URL to start crawling from")
    parser.add_argument("--max-depth", type=int, default=1, help="Maximum BFS depth to crawl")
    parser.add_argument(
        "--domain-lock",
        dest="domain_lock",
        action="store_true",
        default=True,
        help="Restrict crawling to the root URL's registered domain",
    )
    parser.add_argument(
        "--no-domain-lock",
        dest="domain_lock",
        action="store_false",
        help="Allow crawls to follow links outside the root domain",
    )
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_OUTPUT),
        help="Path to write the discovered URLs",
    )
    args = parser.parse_args()
    return CrawlConfig(
        root_url=args.root_url,
        max_depth=args.max_depth,
        domain_lock=args.domain_lock,
        output_file=Path(args.output_file),
    )


def main() -> None:
    config = parse_args()
    links = asyncio.run(crawl(config))
    print(f"Crawled {len(links)} URL(s). Output written to {config.output_file}")


if __name__ == "__main__":
    main()
