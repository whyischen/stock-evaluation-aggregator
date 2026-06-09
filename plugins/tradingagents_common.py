from __future__ import annotations

import importlib
import json
import os
import re
import time
from typing import Any

from sea_core.models import Direction, EvaluationTask, PluginHealth, PluginManifest, PluginResult, PluginStatus


class TradingAgentsAdapter:
    """Thin adapter for TradingAgents-style projects.

    TradingAgents and TradingAgents-CN expose the same high-level Python API:
    TradingAgentsGraph(...).propagate(ticker, date) -> (state, decision).
    """

    def __init__(self, manifest: PluginManifest, *, variant: str) -> None:
        self.manifest = manifest
        self.variant = variant

    async def health(self) -> PluginHealth:
        gate = self._live_gate_message()
        if gate:
            return self._health("unavailable", gate)

        try:
            self._load_graph_types()
        except Exception as exc:
            return self._health("unavailable", f"dependency unavailable: {exc}")

        return self._health("ready", "ready")

    async def evaluate(self, task: EvaluationTask) -> PluginResult:
        started = time.perf_counter()
        gate = self._live_gate_message()
        if gate:
            return self._unavailable(task, gate, started)

        try:
            graph_cls, default_config = self._load_graph_types()
            config = dict(default_config)
            config.update(task.config_overrides.get(self.manifest.plugin_id, {}))
            graph = graph_cls(debug=False, config=config)
            state, decision = graph.propagate(task.ticker, task.eval_date.isoformat())
            parsed = parse_decision(decision)
            return PluginResult(
                plugin_id=self.manifest.plugin_id,
                plugin_name=self.manifest.name,
                ticker=task.ticker,
                eval_date=task.eval_date,
                direction=parsed["direction"],
                confidence=parsed["confidence"],
                summary=parsed["summary"],
                detail={
                    "variant": self.variant,
                    "decision": _jsonable(decision),
                    "state": _jsonable(state),
                },
                latency_ms=_elapsed_ms(started),
            )
        except Exception as exc:
            return PluginResult(
                plugin_id=self.manifest.plugin_id,
                plugin_name=self.manifest.name,
                ticker=task.ticker,
                eval_date=task.eval_date,
                status=PluginStatus.FAILED,
                error=str(exc),
                latency_ms=_elapsed_ms(started),
            )

    def _live_gate_message(self) -> str | None:
        if os.getenv("SEA_ENABLE_LIVE_TRADINGAGENTS", "").lower() not in {"1", "true", "yes"}:
            return "live TradingAgents calls are disabled; set SEA_ENABLE_LIVE_TRADINGAGENTS=true"
        if not _has_llm_config():
            return "missing LLM provider config; set an API key or local provider config"
        return None

    def _load_graph_types(self):
        graph_module = importlib.import_module("tradingagents.graph.trading_graph")
        config_module = importlib.import_module("tradingagents.default_config")
        graph_cls = getattr(graph_module, "TradingAgentsGraph")
        default_config = getattr(config_module, "DEFAULT_CONFIG", {})
        return graph_cls, default_config.copy() if hasattr(default_config, "copy") else {}

    def _health(self, status: str, message: str) -> PluginHealth:
        return PluginHealth(
            plugin_id=self.manifest.plugin_id,
            name=self.manifest.name,
            status=status,
            message=message,
            plugin_type=self.manifest.plugin_type,
            markets=self.manifest.markets,
        )

    def _unavailable(self, task: EvaluationTask, error: str, started: float) -> PluginResult:
        return PluginResult(
            plugin_id=self.manifest.plugin_id,
            plugin_name=self.manifest.name,
            ticker=task.ticker,
            eval_date=task.eval_date,
            status=PluginStatus.UNAVAILABLE,
            error=error,
            latency_ms=_elapsed_ms(started),
        )


def parse_decision(decision: Any) -> dict[str, Any]:
    text = _decision_text(decision)
    lower = text.lower()

    direction = Direction.UNKNOWN
    if any(token in lower for token in ["buy", "bullish", "long", "买入", "看多", "增持"]):
        direction = Direction.BUY
    elif any(token in lower for token in ["sell", "bearish", "short", "卖出", "看空", "减持"]):
        direction = Direction.SELL
    elif any(token in lower for token in ["hold", "neutral", "持有", "观望", "中性"]):
        direction = Direction.HOLD

    confidence = _parse_confidence(text)
    summary = _summarize(text)
    return {"direction": direction, "confidence": confidence, "summary": summary}


def _decision_text(decision: Any) -> str:
    if isinstance(decision, str):
        return decision
    if isinstance(decision, dict):
        preferred = [
            "decision",
            "recommendation",
            "action",
            "summary",
            "final_decision",
            "investment_decision",
        ]
        parts = [str(decision[key]) for key in preferred if key in decision and decision[key]]
        if parts:
            return "\n".join(parts)
    return json.dumps(_jsonable(decision), ensure_ascii=False)


def _parse_confidence(text: str) -> float:
    percent_match = re.search(r"(\d{1,3})\s*%", text)
    if percent_match:
        value = max(0, min(100, int(percent_match.group(1))))
        return value / 100

    decimal_match = re.search(r"(?:confidence|置信度)[^\d]*(0?\.\d+|1(?:\.0+)?)", text, re.IGNORECASE)
    if decimal_match:
        return max(0.0, min(1.0, float(decimal_match.group(1))))

    return 0.55


def _summarize(text: str) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "TradingAgents returned an empty decision."
    return compact[:200]


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_jsonable(item) for item in value]
        return str(value)


def _has_llm_config() -> bool:
    provider_keys = [
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "QWEN_API_KEY",
        "GOOGLE_API_KEY",
        "DASHSCOPE_API_KEY",
    ]
    return any(os.getenv(key) for key in provider_keys) or bool(os.getenv("OLLAMA_BASE_URL"))


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)

