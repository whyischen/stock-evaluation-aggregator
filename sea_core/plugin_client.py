from __future__ import annotations

import asyncio
import importlib
import time
from typing import Protocol

import httpx

from sea_core.models import Direction, EvaluationTask, PluginHealth, PluginManifest, PluginResult, PluginStatus


class PluginClient(Protocol):
    async def health(self, manifest: PluginManifest) -> PluginHealth:
        ...

    async def evaluate(self, manifest: PluginManifest, task: EvaluationTask) -> PluginResult:
        ...


class HttpPluginClient:
    async def health(self, manifest: PluginManifest) -> PluginHealth:
        if not manifest.endpoint:
            return PluginHealth(
                plugin_id=manifest.plugin_id,
                name=manifest.name,
                status="unavailable",
                message="missing endpoint",
                plugin_type=manifest.plugin_type,
                markets=manifest.markets,
            )

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=manifest.timeout_seconds) as client:
                response = await client.get(f"{manifest.endpoint.rstrip('/')}/health")
                response.raise_for_status()
                payload = response.json()
            payload.setdefault("latency_ms", int((time.perf_counter() - started) * 1000))
            return PluginHealth(**payload)
        except Exception as exc:
            return PluginHealth(
                plugin_id=manifest.plugin_id,
                name=manifest.name,
                status="unavailable",
                message=str(exc),
                latency_ms=int((time.perf_counter() - started) * 1000),
                plugin_type=manifest.plugin_type,
                markets=manifest.markets,
            )

    async def evaluate(self, manifest: PluginManifest, task: EvaluationTask) -> PluginResult:
        if not manifest.endpoint:
            return unavailable_result(manifest, task, "missing endpoint")

        payload = {
            "ticker": task.ticker,
            "eval_date": task.eval_date.isoformat(),
            "config": task.config_overrides.get(manifest.plugin_id, {}),
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=manifest.timeout_seconds) as client:
                response = await client.post(f"{manifest.endpoint.rstrip('/')}/evaluate", json=payload)
                response.raise_for_status()
                data = response.json()
            data.setdefault("latency_ms", int((time.perf_counter() - started) * 1000))
            return PluginResult(**data)
        except httpx.TimeoutException:
            return timeout_result(manifest, task, int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return unavailable_result(manifest, task, str(exc), int((time.perf_counter() - started) * 1000))


class MockPluginClient:
    async def health(self, manifest: PluginManifest) -> PluginHealth:
        await asyncio.sleep(0.01)
        status = "unavailable" if manifest.plugin_id == "mock_failure" else "ready"
        message = "simulated dependency is unavailable" if status == "unavailable" else "ready"
        return PluginHealth(
            plugin_id=manifest.plugin_id,
            name=manifest.name,
            status=status,
            message=message,
            latency_ms=10,
            plugin_type=manifest.plugin_type,
            markets=manifest.markets,
        )

    async def evaluate(self, manifest: PluginManifest, task: EvaluationTask) -> PluginResult:
        started = time.perf_counter()
        await asyncio.sleep(0.05)

        if manifest.plugin_id == "mock_failure":
            return unavailable_result(
                manifest,
                task,
                "simulated upstream service unavailable",
                int((time.perf_counter() - started) * 1000),
            )

        if manifest.plugin_id == "mock_bullish":
            return PluginResult(
                plugin_id=manifest.plugin_id,
                plugin_name=manifest.name,
                ticker=task.ticker,
                eval_date=task.eval_date,
                direction=Direction.BUY,
                confidence=0.72,
                summary=f"{task.ticker} shows constructive multi-source signals in the mock adapter.",
                detail={
                    "source_type": "mock_llm",
                    "factors": [
                        {"name": "fundamental trend", "verdict": "positive"},
                        {"name": "sentiment", "verdict": "neutral"},
                    ],
                },
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        return PluginResult(
            plugin_id=manifest.plugin_id,
            plugin_name=manifest.name,
            ticker=task.ticker,
            eval_date=task.eval_date,
            direction=Direction.HOLD,
            confidence=0.58,
            summary=f"{task.ticker} has mixed signals; the mock quant adapter prefers waiting.",
            detail={
                "source_type": "mock_quant",
                "alpha_score": 0.04,
                "rank_percentile": 0.61,
            },
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class AdapterPluginClient:
    async def health(self, manifest: PluginManifest) -> PluginHealth:
        adapter = self._create_adapter(manifest)
        return await adapter.health()

    async def evaluate(self, manifest: PluginManifest, task: EvaluationTask) -> PluginResult:
        adapter = self._create_adapter(manifest)
        return await adapter.evaluate(task)

    def _create_adapter(self, manifest: PluginManifest):
        module_name = {
            "tradingagents_cn": "plugins.tradingagents_cn",
            "tradingagents": "plugins.tradingagents",
        }.get(manifest.plugin_id)
        if not module_name:
            raise ValueError(f"no adapter registered for plugin {manifest.plugin_id}")
        module = importlib.import_module(module_name)
        return module.create_adapter(manifest)


def timeout_result(manifest: PluginManifest, task: EvaluationTask, latency_ms: int) -> PluginResult:
    return PluginResult(
        plugin_id=manifest.plugin_id,
        plugin_name=manifest.name,
        ticker=task.ticker,
        eval_date=task.eval_date,
        status=PluginStatus.TIMEOUT,
        error=f"plugin timed out after {manifest.timeout_seconds}s",
        latency_ms=latency_ms,
    )


def unavailable_result(
    manifest: PluginManifest,
    task: EvaluationTask,
    error: str,
    latency_ms: int = 0,
) -> PluginResult:
    return PluginResult(
        plugin_id=manifest.plugin_id,
        plugin_name=manifest.name,
        ticker=task.ticker,
        eval_date=task.eval_date,
        status=PluginStatus.UNAVAILABLE,
        error=error,
        latency_ms=latency_ms,
    )
