from __future__ import annotations

import unittest

from crawler import extract_links_from_html, filter_links, normalize_url, same_registered_domain


class CrawlerHelpersTest(unittest.TestCase):
    def test_normalize_url_joins_relative_paths_and_drops_fragments(self) -> None:
        self.assertEqual(
            normalize_url("/docs#intro", "https://example.com/start"),
            "https://example.com/docs",
        )

    def test_normalize_url_encodes_spaces_in_cms_paths(self) -> None:
        self.assertEqual(
            normalize_url(
                "/-/media/dot-media/documents/simm-25B-web-accessibility-certificate_2025-caltrans- final-a11y",
                "https://dot.ca.gov/",
            ),
            "https://dot.ca.gov/-/media/dot-media/documents/simm-25B-web-accessibility-certificate_2025-caltrans-%20final-a11y",
        )

    def test_filter_links_enforces_domain_lock(self) -> None:
        filtered = filter_links(
            [
                "https://example.com/about",
                "https://www.example.com/contact",
                "https://iana.org/domains/example",
            ],
            root_url="https://example.com",
            domain_lock=True,
        )
        self.assertEqual(
            filtered,
            [
                "https://example.com/about",
                "https://www.example.com/contact",
            ],
        )

    def test_same_registered_domain_matches_subdomains(self) -> None:
        self.assertTrue(
            same_registered_domain("https://docs.example.com", "https://example.com")
        )

    def test_extract_links_from_html_normalizes_relative_and_absolute_links(self) -> None:
        html = """
        <html>
            <body>
                <a href="/docs">Docs</a>
                <a href="https://example.com/about#team">About</a>
                <a href="mailto:test@example.com">Ignore</a>
            </body>
        </html>
        """
        self.assertEqual(
            extract_links_from_html(html, "https://example.com/start"),
            [
                "https://example.com/docs",
                "https://example.com/about",
            ],
        )


if __name__ == "__main__":
    unittest.main()
