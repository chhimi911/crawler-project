# Crawler Spec: NotebookLM Ingestion Engine

## Goal
Build a recursive, domain-locked crawler to generate a clean list of URLs for RAG/Notebook ingestion.

## Stack
- **Engine:** OpenAI Codex (GPT-5.4) Execution Environment
- **Runtime:** Python 3.12+
- **Browser:** Playwright (Headless Chromium)
- **Architecture:** Asyncio BFS (Breadth-First Search)

## File Structure
- `crawler.py`       # Core logic
- `tests/test_crawler.py` # Verification suite
- `requirements.txt` # playwright, beautifulsoup4, tldextract
- `links.txt`        # Final flat-file output for Notebooks

## Logic Flow
1. **User Input:** Root URL + Max Depth (N).
2. **Safety:** Use `tldextract` to lock crawling to the root domain only.
3. **Execution:** - Level 0: Fetch Root.
   - Level 1..N: Extract <a> tags -> Normalize -> Filter Dupes -> Queue.
4. **Validation:** Script must run a 1-level deep test on `example.com` before finishing.