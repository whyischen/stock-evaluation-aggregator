from __future__ import annotations

from sea_core.models import PluginManifest
from plugins.tradingagents_common import TradingAgentsAdapter


def create_adapter(manifest: PluginManifest) -> TradingAgentsAdapter:
    return TradingAgentsAdapter(manifest, variant="tradingagents_cn")
