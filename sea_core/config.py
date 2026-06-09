from __future__ import annotations

from sea_core.models import Market, PluginManifest, PluginType


DEFAULT_PLUGINS: list[PluginManifest] = [
    PluginManifest(
        plugin_id="tradingagents_cn",
        name="TradingAgents-CN",
        plugin_type=PluginType.REALTIME,
        transport="adapter",
        markets=[Market.A_SHARE],
        timeout_seconds=300,
        weight=1.0,
    ),
    PluginManifest(
        plugin_id="tradingagents",
        name="TradingAgents",
        plugin_type=PluginType.REALTIME,
        transport="adapter",
        markets=[Market.US, Market.HK],
        timeout_seconds=300,
        weight=1.0,
    ),
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
