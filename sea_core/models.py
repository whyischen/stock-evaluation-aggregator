from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator


class Direction(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"

    @property
    def score_value(self) -> int:
        return {
            Direction.BUY: 1,
            Direction.HOLD: 0,
            Direction.SELL: -1,
            Direction.UNKNOWN: 0,
        }[self]


class PluginStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


class Market(str, Enum):
    A_SHARE = "A_SHARE"
    US = "US"
    HK = "HK"
    UNKNOWN = "UNKNOWN"


class PluginType(str, Enum):
    REALTIME = "realtime"
    CACHED = "cached"
    RESEARCH = "research"
    MOCK = "mock"


class EvaluationTask(BaseModel):
    ticker: str = Field(..., min_length=1)
    eval_date: date = Field(default_factory=date.today)
    market: Market | None = None
    plugin_ids: list[str] | None = None
    config_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @computed_field
    @property
    def resolved_market(self) -> Market:
        if self.market:
            return self.market
        if self.ticker.endswith((".SS", ".SZ")):
            return Market.A_SHARE
        if self.ticker.endswith(".HK"):
            return Market.HK
        if "." not in self.ticker:
            return Market.US
        return Market.UNKNOWN


class PluginManifest(BaseModel):
    plugin_id: str
    name: str
    plugin_type: PluginType = PluginType.REALTIME
    transport: str = "mock"
    endpoint: str | None = None
    enabled: bool = True
    markets: list[Market] = Field(default_factory=lambda: [Market.UNKNOWN])
    timeout_seconds: float = 30.0
    weight: float = 1.0

    def supports_market(self, market: Market) -> bool:
        return Market.UNKNOWN in self.markets or market in self.markets


class PluginHealth(BaseModel):
    plugin_id: str
    name: str
    status: str
    message: str = "ready"
    latency_ms: int | None = None
    plugin_type: PluginType
    markets: list[Market]


class PluginResult(BaseModel):
    plugin_id: str
    plugin_name: str
    ticker: str
    eval_date: date
    direction: Direction = Direction.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    raw_output_ref: str | None = None
    latency_ms: int = 0
    status: PluginStatus = PluginStatus.SUCCESS
    error: str | None = None
    signal_age_days: int | None = None


class EvalReport(BaseModel):
    ticker: str
    eval_date: date
    market: Market
    results: list[PluginResult]
    success_count: int
    failed_count: int
    direction_counts: dict[str, int]
    consensus_level: str
    weighted_score: float | None
    divergence_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
