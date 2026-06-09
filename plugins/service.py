from __future__ import annotations

import os
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from plugins.tradingagents import create_adapter as create_tradingagents_adapter
from plugins.tradingagents_cn import create_adapter as create_tradingagents_cn_adapter
from sea_core.models import EvaluationTask, Market, PluginManifest, PluginType


class PluginEvaluateRequest(BaseModel):
    ticker: str
    eval_date: date = Field(default_factory=date.today)
    config: dict[str, Any] = Field(default_factory=dict)


PLUGIN_ID = os.getenv("SEA_PLUGIN_SERVICE_ID", "")


def _manifest_for(plugin_id: str) -> PluginManifest:
    if plugin_id == "tradingagents_cn":
        return PluginManifest(
            plugin_id="tradingagents_cn",
            name="TradingAgents-CN",
            plugin_type=PluginType.REALTIME,
            transport="adapter",
            markets=[Market.A_SHARE],
            timeout_seconds=float(os.getenv("SEA_TRADINGAGENTS_CN_TIMEOUT_SECONDS", "300")),
        )
    if plugin_id == "tradingagents":
        return PluginManifest(
            plugin_id="tradingagents",
            name="TradingAgents",
            plugin_type=PluginType.REALTIME,
            transport="adapter",
            markets=[Market.US, Market.HK],
            timeout_seconds=float(os.getenv("SEA_TRADINGAGENTS_TIMEOUT_SECONDS", "300")),
        )
    raise ValueError(f"unsupported plugin service id: {plugin_id}")


def _adapter_for(manifest: PluginManifest):
    if manifest.plugin_id == "tradingagents_cn":
        return create_tradingagents_cn_adapter(manifest)
    if manifest.plugin_id == "tradingagents":
        return create_tradingagents_adapter(manifest)
    raise ValueError(f"unsupported plugin service id: {manifest.plugin_id}")


app = FastAPI(title=f"SEA Plugin Service: {PLUGIN_ID or 'unconfigured'}")


@app.get("/health")
async def health():
    manifest = _current_manifest()
    adapter = _adapter_for(manifest)
    return await adapter.health()


@app.post("/evaluate")
async def evaluate(request: PluginEvaluateRequest):
    manifest = _current_manifest()
    adapter = _adapter_for(manifest)
    task = EvaluationTask(
        ticker=request.ticker,
        eval_date=request.eval_date,
        config_overrides={manifest.plugin_id: request.config},
    )
    return await adapter.evaluate(task)


def _current_manifest() -> PluginManifest:
    try:
        return _manifest_for(PLUGIN_ID)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
