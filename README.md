# Stock Evaluation Aggregator

SEA is a lightweight Web First orchestration layer for connecting open-source stock evaluation projects and presenting their results side by side.

SEA does not implement stock evaluation logic. It calls plugins, collects standardized results, and renders comparison reports.

## Run

```bash
uvicorn sea_api.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## TradingAgents plugins

SEA registers two real adapter slots by default:

- `tradingagents_cn` for A-share tickers such as `600519.SS`
- `tradingagents` for US/HK tickers such as `AAPL`

Live calls are disabled by default to avoid accidental LLM cost. To enable them, install the corresponding upstream project in the runtime environment, configure an LLM provider, and set:

```bash
export SEA_ENABLE_LIVE_TRADINGAGENTS=true
export OPENAI_API_KEY=...
```

The adapters expect the upstream project to expose:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

graph = TradingAgentsGraph(debug=False, config=DEFAULT_CONFIG)
state, decision = graph.propagate("AAPL", "2026-06-09")
```
