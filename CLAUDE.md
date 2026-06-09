# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Stock Evaluation Aggregator (SEA)** — an open-source capability orchestration platform for personal investors and quant researchers. SEA is NOT an evaluation engine itself. It acts as a "commander" that dispatches evaluation tasks to existing open-source projects (TradingAgents, TradingAgents-CN, Qlib, RD-Agent), collects their conclusions, and presents a unified cross-validation view.

Core design rule: **SEA holds no evaluation logic.** All evaluation judgments come from plugins (the open-source projects). SEA only does dispatch, aggregation, and display.

## Tech Stack

- Python 3.11+, `asyncio` for concurrent plugin dispatch
- `Typer` + `Rich` for CLI
- `Pydantic v2` for all data models (PluginResult, EvalReport, config)
- `pydantic-settings` + YAML for configuration management
- SQLite for result persistence, JSON Lines as fallback
- `uv` + `pyproject.toml` for packaging
- Plugin system: `importlib` + `entry_points` (Python standard plugin mechanism)

## Architecture

```
User (CLI / Python API / REST API)
        │
┌───────▼──────────────────────────────────────┐
│            SEA Orchestration Core             │
│                                               │
│  EvaluationTask ──► PluginRegistry             │
│  (ticker/date/     (install/enable/disable)    │
│   config)           │                          │
│       │             │                          │
│       └──────┬──────┘                          │
│              ▼                                 │
│         Dispatcher                             │
│         (concurrent, timeout, graceful degrade) │
│              │                                 │
│              ▼                                 │
│         Aggregator                             │
│         (weighted score, consensus level)       │
│              │                                 │
│              ▼                                 │
│         EvalReport (unified output)            │
└───────────────────────────────────────────────┘
         │ dispatches to plugins
    ┌────┴────┬──────────┬─────────┐
    ▼         ▼          ▼         ▼
 TradingAgents  CN    Qlib    RD-Agent
 (adapter layers wrapping native libs)
```

### Core Modules

- **EvaluationTask**: A user evaluation request — tickers, date, enabled plugins, per-plugin config overrides
- **PluginRegistry**: Plugin lifecycle management (install, enable, disable, uninstall), persists to `plugins.yaml`
- **Dispatcher**: Concurrent plugin execution via `asyncio.gather()`, per-plugin timeout, graceful degradation on failure
- **Aggregator**: Merges `PluginResult` list → `EvalReport` with weighted scoring, consensus classification (strong/moderate/diverged)
- **Adapter Plugins**: Each wraps a third-party open-source library, translating its native output into the standard `PluginResult`

## Plugin Interface (Critical — all plugins implement this)

Every evaluation plugin must implement `BaseEvaluatorPlugin` (see requirements doc section 7.1):

```python
class BaseEvaluatorPlugin(ABC):
    plugin_id: str           # unique ID, e.g. "tradingagents", "qlib"
    display_name: str        # human-readable name
    supported_markets: list[str]  # ["US", "A_SHARE", "ALL"]

    def is_available(self) -> bool: ...         # health check
    async def evaluate(self, ticker, eval_date, **kwargs) -> PluginResult: ...
```

`PluginResult` is the standardized return type with fields: `plugin_id`, `ticker`, `eval_date`, `direction` (BUY=+1/HOLD=0/SELL=-1), `confidence` [0.0-1.0], `summary` (≤200 chars), `detail` (plugin-specific dict), `latency_ms`, `error` (None = success).

Each plugin ships a `plugin.yaml` declaring its id, version, Python class path, dependencies, and config schema.

## Planned CLI Commands (from FRs)

```bash
sea evaluate --ticker 600519.SS --date 2026-06-01
sea evaluate --ticker AAPL,MSFT --plugins trading_agents,qlib
sea plugin list
sea plugin enable/disable <id>
sea plugin new <name>        # scaffold a new plugin
sea plugin install ./path    # install a third-party plugin
```

Output formats: terminal table (Rich), JSON, Markdown report.

## Aggregation Logic

- **Weighted score** = Σ(direction × confidence × weight) / Σ(weight), clamped to [-1.0, 1.0]
- **Consensus**: all same → "strong", >60% same → "moderate", no majority → "diverged"
- Failed plugins excluded from aggregation; partial failures noted in report

## Milestone Plan

### Phase 1: Core Framework (MVP — current focus)
- `BaseEvaluatorPlugin` + `PluginResult` + `Direction` enum
- `PluginRegistry` (register/enable/disable)
- `Dispatcher` (serial first, concurrent later)
- Basic `Aggregator` (simple majority vote)
- `TradingAgentsPlugin` adapter
- CLI: `sea evaluate`, `sea plugin list`
- Output: terminal table + JSON

### Phase 2: Full Plugin Matrix
- Remaining 3 plugins (TradingAgents-CN, Qlib, RD-Agent)
- Concurrent Dispatcher with timeout/degradation
- Weighted aggregation algorithm

### Phase 3: Ecosystem
- LangChain Tool / LangGraph Node wrappers
- SQLite persistence for evaluation history
- Plugin scaffolding tool
- Markdown report export

## Design Constraints

- SEA holds no evaluation logic — all judgments from plugins
- SEA does NOT execute trades or provide trading capabilities
- Plugin failures never block other plugins
- API keys read from environment variables, never hardcoded or logged
- A-share tickers (`.SS`/`.SZ`) should prefer TradingAgents-CN when both it and regular TradingAgents are enabled
