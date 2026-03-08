from __future__ import annotations

import asyncio
import json
import unittest

from main import crawl_url, read_health, read_root


class AppSmokeTest(unittest.TestCase):
    def test_root_renders_html_ui(self) -> None:
        response = asyncio.run(read_root())
        body = response.body.decode("utf-8")

        self.assertIn("<form id=\"crawlForm\"", body)
        self.assertIn("Run crawl", body)
        self.assertIn("Discovered URLs", body)

    def test_health_endpoint(self) -> None:
        self.assertEqual(asyncio.run(read_health()), {"status": "ok"})

    def test_crawl_endpoint_returns_json(self) -> None:
        response = asyncio.run(
            crawl_url(root_url="https://example.com", max_depth=1, domain_lock=True)
        )
        payload = json.loads(response.body.decode("utf-8"))

        self.assertEqual(payload["root_url"], "https://example.com")
        self.assertIn("links", payload)
        self.assertGreaterEqual(payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
