from __future__ import annotations

from collections.abc import Mapping
import importlib
import inspect
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
            graph_cls, config_obj = self._load_graph_types()
            self._create_config(config_obj, {})
        except Exception as exc:
            return self._health("unavailable", f"dependency unavailable: {exc}")

        return self._health("ready", "ready")

    async def evaluate(self, task: EvaluationTask) -> PluginResult:
        started = time.perf_counter()
        overrides = task.config_overrides.get(self.manifest.plugin_id, {})
        gate = self._live_gate_message(overrides)
        if gate:
            return self._unavailable(task, gate, started)

        try:
            graph_cls, config_obj = self._load_graph_types()
            config = self._create_config(config_obj, overrides)
            graph = graph_cls(debug=False, config=config)
            state, decision = self._propagate(graph, task.ticker, task.eval_date.isoformat())
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
            import traceback
            error_detail = traceback.format_exc()
            return PluginResult(
                plugin_id=self.manifest.plugin_id,
                plugin_name=self.manifest.name,
                ticker=task.ticker,
                eval_date=task.eval_date,
                status=PluginStatus.FAILED,
                error=f"{str(exc)}\n\n{error_detail}",
                latency_ms=_elapsed_ms(started),
            )

    def _live_gate_message(self, overrides: dict[str, Any] | None = None) -> str | None:
        if os.getenv("SEA_ENABLE_LIVE_TRADINGAGENTS", "").lower() not in {"1", "true", "yes"}:
            return "live TradingAgents calls are disabled; set SEA_ENABLE_LIVE_TRADINGAGENTS=true"
        if not _has_llm_config(self.manifest.plugin_id, overrides):
            return "missing LLM provider config; set an API key or local provider config"
        return None

    def _load_graph_types(self):
        graph_module = importlib.import_module("tradingagents.graph.trading_graph")
        graph_cls = getattr(graph_module, "TradingAgentsGraph")

        if self.variant == "tradingagents_cn":
            # CN version uses DEFAULT_CONFIG dict from tradingagents.default_config
            config_module = importlib.import_module("tradingagents.default_config")
            default_config = getattr(config_module, "DEFAULT_CONFIG", {})
            return graph_cls, default_config.copy() if hasattr(default_config, "copy") else {}
        else:
            # Original version uses TradingAgentsConfig class from tradingagents.config
            config_module = importlib.import_module("tradingagents.config")
            config_cls = getattr(config_module, "TradingAgentsConfig")
            return graph_cls, config_cls

    def _create_config(self, config_obj: Any, overrides: dict[str, Any] | None = None) -> Any:
        config_values = build_tradingagents_config(
            config_obj if isinstance(config_obj, dict) else {},
            self.manifest.plugin_id,
            overrides,
        )

        if isinstance(config_obj, dict):
            # CN version: return dict directly
            return config_values
        else:
            # Original version: instantiate TradingAgentsConfig class
            return config_obj(**_filter_config_values(config_obj, config_values))

    def _propagate(self, graph: Any, ticker: str, eval_date: str) -> tuple[Any, Any]:
        if self.variant != "tradingagents_cn":
            return graph.propagate(ticker, eval_date)

        compiled_graph = getattr(graph, "graph", None)
        stream = getattr(compiled_graph, "stream", None)
        if not callable(stream):
            return graph.propagate(ticker, eval_date)

        def compatible_stream(*args: Any, **kwargs: Any):
            for chunk in stream(*args, **kwargs):
                yield _normalize_cn_stream_chunk(chunk)

        try:
            setattr(compiled_graph, "stream", compatible_stream)
        except (AttributeError, TypeError):
            return graph.propagate(ticker, eval_date)

        try:
            return graph.propagate(ticker, eval_date)
        finally:
            try:
                setattr(compiled_graph, "stream", stream)
            except (AttributeError, TypeError):
                pass

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


def build_tradingagents_config(
    default_config: dict[str, Any],
    plugin_id: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge upstream defaults, SEA env config, and request-level overrides.

    SEA intentionally treats upstream TradingAgents config as opaque. Any key
    accepted by TradingAgentsGraph can be passed through either JSON env config,
    double-underscore env config, or EvaluationTask.config_overrides.
    """

    config = _deep_copy_mapping(default_config)
    _deep_update(config, _env_config_for(plugin_id))
    _deep_update(config, overrides or {})
    return config


def _normalize_cn_stream_chunk(chunk: Any) -> Any:
    if not isinstance(chunk, Mapping):
        return chunk

    node_updates = [
        value for key, value in chunk.items() if not str(key).startswith("__")
    ]
    if not node_updates:
        return chunk

    if all(isinstance(value, Mapping) for value in node_updates):
        return chunk

    return {"sea_state": dict(chunk)}


def _filter_config_values(config_cls: type, config: dict[str, Any]) -> dict[str, Any]:
    fields = _config_fields(config_cls)
    if fields is None:
        return config
    return {key: value for key, value in config.items() if key in fields}


def _config_fields(config_cls: type) -> set[str] | None:
    model_fields = getattr(config_cls, "model_fields", None)
    if isinstance(model_fields, dict):
        return set(model_fields)

    dataclass_fields = getattr(config_cls, "__dataclass_fields__", None)
    if isinstance(dataclass_fields, dict):
        return set(dataclass_fields)

    annotations = getattr(config_cls, "__annotations__", None)
    if isinstance(annotations, dict) and annotations:
        return set(annotations)

    try:
        signature = inspect.signature(config_cls)
    except (TypeError, ValueError):
        return None

    fields = {
        name
        for name, parameter in signature.parameters.items()
        if name != "self"
        and parameter.kind in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}
    }
    return fields or None


def _env_config_for(plugin_id: str) -> dict[str, Any]:
    config: dict[str, Any] = {}
    prefixes = ["SEA_TRADINGAGENTS_ALL_CONFIG", _plugin_env_prefix(plugin_id)]

    for prefix in prefixes:
        _deep_update(config, _json_env_config(prefix))
        _deep_update(config, _double_underscore_env_config(prefix))

    return config


def _plugin_env_prefix(plugin_id: str) -> str:
    return f"SEA_{plugin_id.upper()}_CONFIG"


def _json_env_config(prefix: str) -> dict[str, Any]:
    raw = os.getenv(prefix) or os.getenv(f"{prefix}_JSON")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{prefix}_JSON must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{prefix}_JSON must decode to an object")
    return parsed


def _double_underscore_env_config(prefix: str) -> dict[str, Any]:
    marker = f"{prefix}__"
    config: dict[str, Any] = {}
    for key, raw_value in os.environ.items():
        if not key.startswith(marker):
            continue
        path = [_env_key_to_config_key(part) for part in key[len(marker) :].split("__") if part]
        if not path:
            continue
        _set_nested(config, path, _parse_env_value(raw_value))
    return config


def _env_key_to_config_key(value: str) -> str:
    return value.lower()


def _parse_env_value(value: str) -> Any:
    stripped = value.strip()
    if stripped == "":
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _set_nested(target: dict[str, Any], path: list[str], value: Any) -> None:
    current = target
    for key in path[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[path[-1]] = value


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = _deep_copy(value)


def _deep_copy_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return {key: _deep_copy(item) for key, item in value.items()}


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return _deep_copy_mapping(value)
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


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


def _has_llm_config(plugin_id: str, overrides: dict[str, Any] | None = None) -> bool:
    merged_config = _env_config_for(plugin_id)
    _deep_update(merged_config, overrides or {})
    if _contains_llm_connection_hint(merged_config):
        return True

    provider_keys = [
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "QWEN_API_KEY",
        "GOOGLE_API_KEY",
        "DASHSCOPE_API_KEY",
    ]
    return any(os.getenv(key) for key in provider_keys) or bool(os.getenv("OLLAMA_BASE_URL"))


def _contains_llm_connection_hint(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key, item in value.items():
        normalized = str(key).lower()
        if item and (
            normalized.endswith("api_key")
            or normalized in {"api_key", "base_url", "backend_url", "api_base", "backend"}
        ):
            return True
        if _contains_llm_connection_hint(item):
            return True
    return False


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
