from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sea_core.models import EvaluationTask
from sea_core.orchestrator import Orchestrator

app = FastAPI(title="SEA Core API", version="0.1.0")
orchestrator = Orchestrator()

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
    return await orchestrator.evaluate(task)


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

