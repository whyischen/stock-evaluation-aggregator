from __future__ import annotations

import os
from datetime import date

import pytest

from plugins.tradingagents_common import TradingAgentsAdapter, build_tradingagents_config
from sea_core.models import Direction, EvaluationTask, Market, PluginManifest, PluginType


@pytest.fixture(autouse=True)
def clean_tradingagents_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("SEA_TRADINGAGENTS_CONFIG", "SEA_TRADINGAGENTS_CN_CONFIG", "SEA_TRADINGAGENTS_ALL_CONFIG")):
            monkeypatch.delenv(key, raising=False)


def _manifest(plugin_id: str = "tradingagents") -> PluginManifest:
    return PluginManifest(
        plugin_id=plugin_id,
        name="TradingAgents",
        plugin_type=PluginType.REALTIME,
        transport="adapter",
        markets=[Market.US],
    )


def test_build_tradingagents_config_merges_env_and_task_overrides(monkeypatch):
    monkeypatch.setenv("SEA_TRADINGAGENTS_ALL_CONFIG__LLM_PROVIDER", "openai")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__BACKEND_URL", "https://api.openai.example/v1")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__DEEP_THINK_LLM", "gpt-4.1")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__ONLINE_TOOLS", "true")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__MODEL_KWARGS__TEMPERATURE", "0.2")

    config = build_tradingagents_config(
        {
            "llm_provider": "default-provider",
            "backend_url": "https://default.example/v1",
            "quick_think_llm": "default-quick",
            "model_kwargs": {"max_tokens": 1000, "temperature": 0.7},
        },
        "tradingagents",
        {
            "quick_think_llm": "gpt-4.1-mini",
            "model_kwargs": {"max_tokens": 2000},
        },
    )

    assert config["llm_provider"] == "openai"
    assert config["backend_url"] == "https://api.openai.example/v1"
    assert config["deep_think_llm"] == "gpt-4.1"
    assert config["quick_think_llm"] == "gpt-4.1-mini"
    assert config["online_tools"] is True
    assert config["model_kwargs"] == {"max_tokens": 2000, "temperature": 0.2}


def test_build_tradingagents_config_supports_plugin_json_env(monkeypatch):
    monkeypatch.setenv(
        "SEA_TRADINGAGENTS_CN_CONFIG_JSON",
        '{"quick_provider":"dashscope","quick_api_key":"env-key","max_debate_rounds":2}',
    )

    config = build_tradingagents_config(
        {"quick_provider": "openai", "deep_provider": "openai"},
        "tradingagents_cn",
        {"deep_provider": "dashscope"},
    )

    assert config["quick_provider"] == "dashscope"
    assert config["quick_api_key"] == "env-key"
    assert config["deep_provider"] == "dashscope"
    assert config["max_debate_rounds"] == 2


@pytest.mark.asyncio
async def test_adapter_passes_llm_config_to_tradingagents_graph(monkeypatch):
    captured: dict[str, object] = {}

    class FakeConfig:
        llm_provider: str
        deep_think_llm: str
        quick_think_llm: str

        def __init__(
            self,
            llm_provider: str = "default-provider",
            deep_think_llm: str = "default-deep",
            quick_think_llm: str = "default-quick",
        ):
            self.llm_provider = llm_provider
            self.deep_think_llm = deep_think_llm
            self.quick_think_llm = quick_think_llm

    class FakeGraph:
        def __init__(self, debug: bool, config: FakeConfig):
            captured["debug"] = debug
            captured["config"] = config

        def propagate(self, ticker: str, eval_date: str):
            captured["ticker"] = ticker
            captured["eval_date"] = eval_date
            return {"ok": True}, {"decision": "BUY with 80% confidence"}

    def fake_load_graph_types(self):
        return FakeGraph, FakeConfig

    monkeypatch.setenv("SEA_ENABLE_LIVE_TRADINGAGENTS", "true")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__LLM_PROVIDER", "openai")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CONFIG__BACKEND_URL", "https://api.openai.example/v1")
    monkeypatch.setattr(TradingAgentsAdapter, "_load_graph_types", fake_load_graph_types)

    adapter = TradingAgentsAdapter(_manifest(), variant="tradingagents")
    task = EvaluationTask(
        ticker="AAPL",
        eval_date=date(2026, 6, 1),
        config_overrides={
            "tradingagents": {
                "quick_think_llm": "gpt-4.1-mini",
                "api_key": "task-key",
            }
        },
    )

    result = await adapter.evaluate(task)

    assert result.direction == Direction.BUY
    assert result.confidence == 0.8
    assert captured["debug"] is False
    assert captured["ticker"] == "AAPL"
    assert captured["eval_date"] == "2026-06-01"
    config = captured["config"]
    assert isinstance(config, FakeConfig)
    assert config.llm_provider == "openai"
    assert config.deep_think_llm == "default-deep"
    assert config.quick_think_llm == "gpt-4.1-mini"
    assert not hasattr(config, "backend_url")
    assert not hasattr(config, "api_key")


@pytest.mark.asyncio
async def test_tradingagents_cn_normalizes_langgraph_state_stream_chunks(monkeypatch):
    class FakeCompiledGraph:
        def __init__(self):
            self.stream_restored = False
            self.original_stream = self.stream

        def stream(self, *_args, **_kwargs):
            yield {
                "ticker": "600519.SS",
                "market_report": "看多贵州茅台",
                "messages": ["analyst message"],
                "__metadata__": {"step": 1},
            }

    class FakeGraph:
        compiled_graph: FakeCompiledGraph | None = None

        def __init__(self, debug: bool, config: dict[str, object]):
            self.graph = FakeCompiledGraph()
            FakeGraph.compiled_graph = self.graph

        def propagate(self, ticker: str, eval_date: str):
            final_state = {}
            for chunk in self.graph.stream({"ticker": ticker, "trade_date": eval_date}):
                for node_name, node_update in chunk.items():
                    if not node_name.startswith("__"):
                        final_state.update(node_update)
            return final_state, {"decision": "买入，置信度 80%"}

    def fake_load_graph_types(self):
        return FakeGraph, {"quick_provider": "dashscope"}

    monkeypatch.setenv("SEA_ENABLE_LIVE_TRADINGAGENTS", "true")
    monkeypatch.setenv("SEA_TRADINGAGENTS_CN_CONFIG__QUICK_API_KEY", "task-key")
    monkeypatch.setattr(TradingAgentsAdapter, "_load_graph_types", fake_load_graph_types)

    adapter = TradingAgentsAdapter(_manifest("tradingagents_cn"), variant="tradingagents_cn")
    task = EvaluationTask(ticker="600519.SS", eval_date=date(2026, 6, 9))

    result = await adapter.evaluate(task)

    assert result.direction == Direction.BUY
    assert result.confidence == 0.8
    assert result.summary
    assert result.detail["state"]["ticker"] == "600519.SS"
    assert result.detail["state"]["market_report"] == "看多贵州茅台"
    assert FakeGraph.compiled_graph is not None
    assert FakeGraph.compiled_graph.stream == FakeGraph.compiled_graph.original_stream
