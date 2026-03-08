from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse

from crawler import CrawlConfig, crawl


OUTPUT_FILE = Path("links.txt")


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def main() -> None:
    config = CrawlConfig(
        root_url="https://example.com",
        max_depth=1,
        domain_lock=True,
        output_file=OUTPUT_FILE,
    )
    links = await crawl(config)

    if not OUTPUT_FILE.exists():
        raise RuntimeError("links.txt was not created")

    file_links = [line.strip() for line in OUTPUT_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not file_links:
        raise RuntimeError("links.txt is empty")

    invalid_links = [link for link in file_links if not is_valid_url(link)]
    if invalid_links:
        raise RuntimeError(f"links.txt contains invalid URLs: {invalid_links}")

    if links != file_links:
        raise RuntimeError("Returned links do not match the contents of links.txt")

    print(f"Verified {len(file_links)} URL(s) in links.txt")


if __name__ == "__main__":
    asyncio.run(main())
