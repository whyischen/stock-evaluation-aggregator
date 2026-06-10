from datetime import date

import pytest

from sea_core.models import EvaluationTask, WatchlistCreate
from sea_core.orchestrator import Orchestrator
from sea_core.storage import SQLiteStore


@pytest.mark.asyncio
async def test_store_saves_history_and_watchlist(tmp_path):
    store = SQLiteStore(tmp_path / "sea.sqlite3")
    report = await Orchestrator().evaluate(EvaluationTask(ticker="AAPL", eval_date=date(2026, 6, 10)))

    history_id = store.save_report(report)
    history = store.list_history()
    detail = store.get_history_detail(history_id)

    assert history[0].ticker == "AAPL"
    assert detail is not None
    assert detail.report.ticker == "AAPL"

    item = store.upsert_watchlist(WatchlistCreate(ticker="600519.SS", name="贵州茅台"))
    watchlist = store.list_watchlist()

    assert item.market.value == "A_SHARE"
    assert watchlist[0].ticker == "600519.SS"
    assert store.delete_watchlist("600519.SS") is True
    assert store.list_watchlist() == []
