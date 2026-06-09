from __future__ import annotations

from __future__ import annotations

import os

from sea_core.models import Market, PluginManifest, PluginType


def build_default_plugins() -> list[PluginManifest]:
    plugins = [
        PluginManifest(
            plugin_id="tradingagents_cn",
            name="TradingAgents-CN",
            plugin_type=PluginType.REALTIME,
            transport=_transport_for("SEA_TRADINGAGENTS_CN_URL"),
            endpoint=_env_optional("SEA_TRADINGAGENTS_CN_URL"),
            markets=[Market.A_SHARE],
            timeout_seconds=_env_float("SEA_TRADINGAGENTS_CN_TIMEOUT_SECONDS", 300),
            weight=_env_float("SEA_TRADINGAGENTS_CN_WEIGHT", 1.0),
        ),
        PluginManifest(
            plugin_id="tradingagents",
            name="TradingAgents",
            plugin_type=PluginType.REALTIME,
            transport=_transport_for("SEA_TRADINGAGENTS_URL"),
            endpoint=_env_optional("SEA_TRADINGAGENTS_URL"),
            markets=[Market.US, Market.HK],
            timeout_seconds=_env_float("SEA_TRADINGAGENTS_TIMEOUT_SECONDS", 300),
            weight=_env_float("SEA_TRADINGAGENTS_WEIGHT", 1.0),
        ),
    ]

    if os.getenv("SEA_ENABLE_MOCK_PLUGINS", "true").lower() in {"1", "true", "yes"}:
        plugins.extend(
            [
                PluginManifest(
                    plugin_id="mock_bullish",
                    name="Mock Bullish Analyst",
                    plugin_type=PluginType.MOCK,
                    transport="mock",
                    markets=[Market.UNKNOWN],
                    timeout_seconds=2,
                    weight=1.0,
                ),
                PluginManifest(
                    plugin_id="mock_cautious",
                    name="Mock Cautious Quant",
                    plugin_type=PluginType.MOCK,
                    transport="mock",
                    markets=[Market.UNKNOWN],
                    timeout_seconds=2,
                    weight=1.0,
                ),
                PluginManifest(
                    plugin_id="mock_failure",
                    name="Mock Unavailable Source",
                    plugin_type=PluginType.MOCK,
                    transport="mock",
                    markets=[Market.UNKNOWN],
                    timeout_seconds=1,
                    weight=1.0,
                ),
            ]
        )

    return plugins


def _transport_for(url_env: str) -> str:
    return "http" if _env_optional(url_env) else "adapter"


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


DEFAULT_PLUGINS: list[PluginManifest] = build_default_plugins()
