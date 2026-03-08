from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from crawler import CrawlConfig, crawl


INDEX_HTML = Path(__file__).parent / "static" / "index.html"


app = FastAPI(
    title="Crawler Project",
    version="0.1.0",
    description="Recursive, domain-locked crawler exposed as a FastAPI app.",
)


@app.get("/", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/health")
async def read_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/crawl")
async def crawl_url(
    root_url: str = Query(..., description="Root URL to crawl"),
    max_depth: int = Query(1, ge=0, le=3, description="Maximum BFS depth"),
    domain_lock: bool = Query(True, description="Restrict crawling to the root domain"),
) -> JSONResponse:
    try:
        links = await crawl(
            CrawlConfig(
                root_url=root_url,
                max_depth=max_depth,
                domain_lock=domain_lock,
                output_file=None,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {exc}") from exc

    return JSONResponse(
        {
            "root_url": root_url,
            "max_depth": max_depth,
            "domain_lock": domain_lock,
            "count": len(links),
            "links": links,
        }
    )
