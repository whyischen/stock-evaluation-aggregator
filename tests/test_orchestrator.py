from datetime import date

import pytest

from sea_core.models import EvaluationTask, Market
from sea_core.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_returns_report_with_partial_failure(monkeypatch):
    monkeypatch.delenv("SEA_ENABLE_LIVE_TRADINGAGENTS", raising=False)
    orchestrator = Orchestrator()
    task = EvaluationTask(ticker="600519.SS", eval_date=date(2026, 6, 9))

    report = await orchestrator.evaluate(task)

    assert report.ticker == "600519.SS"
    assert report.market == Market.A_SHARE
    assert report.success_count == 2
    assert report.failed_count == 2
    assert report.weighted_score is not None
    assert "2 plugin(s) did not return a successful result." in report.divergence_notes
    assert {result.plugin_id for result in report.results} == {
        "tradingagents_cn",
        "mock_bullish",
        "mock_cautious",
        "mock_failure",
    }


@pytest.mark.asyncio
async def test_orchestrator_supports_plugin_filtering():
    orchestrator = Orchestrator()
    task = EvaluationTask(ticker="AAPL", plugin_ids=["mock_bullish"])

    report = await orchestrator.evaluate(task)

    assert len(report.results) == 1
    assert report.results[0].plugin_id == "mock_bullish"
    assert report.success_count == 1
    assert report.consensus_level == "strong"


@pytest.mark.asyncio
async def test_us_market_routes_to_tradingagents(monkeypatch):
    monkeypatch.delenv("SEA_ENABLE_LIVE_TRADINGAGENTS", raising=False)
    orchestrator = Orchestrator()
    task = EvaluationTask(ticker="AAPL")

    report = await orchestrator.evaluate(task)

    assert report.market == Market.US
    assert "tradingagents" in {result.plugin_id for result in report.results}
    assert "tradingagents_cn" not in {result.plugin_id for result in report.results}
