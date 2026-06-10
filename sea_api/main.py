from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sea_core.models import EvaluationTask, WatchlistCreate
from sea_core.orchestrator import Orchestrator
from sea_core.storage import SQLiteStore

app = FastAPI(title="SEA Core API", version="0.1.0")
orchestrator = Orchestrator()
store = SQLiteStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sea-core"}


@app.get("/api/plugins")
@app.get("/plugins")
async def list_plugins():
    return orchestrator.list_plugins()


@app.get("/api/system/status")
@app.get("/system/status")
async def system_status():
    return {"plugins": await orchestrator.health()}


@app.post("/api/evaluate")
@app.post("/evaluate")
async def evaluate(task: EvaluationTask):
    report = await orchestrator.evaluate(task)
    store.save_report(report)
    return report


@app.get("/api/history")
async def list_history(ticker: str | None = None, limit: int = Query(default=20, ge=1, le=100)):
    return store.list_history(ticker=ticker, limit=limit)


@app.get("/api/history/{history_id}")
async def history_detail(history_id: int):
    detail = store.get_history_detail(history_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="history item not found")
    return detail


@app.get("/api/watchlist")
async def list_watchlist():
    return store.list_watchlist()


@app.post("/api/watchlist")
async def add_watchlist(item: WatchlistCreate):
    return store.upsert_watchlist(item)


@app.delete("/api/watchlist/{ticker}")
async def delete_watchlist(ticker: str):
    return {"deleted": store.delete_watchlist(ticker)}


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
