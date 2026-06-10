from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sea_core.models import (
    EvalReport,
    EvaluationHistoryDetail,
    EvaluationHistoryItem,
    EvaluationTask,
    Market,
    WatchlistCreate,
    WatchlistItem,
)


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("SEA_DB_PATH", "data/sea.sqlite3"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def save_report(self, report: EvalReport) -> int:
        payload = report.model_dump_json()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluation_history (
                    ticker, eval_date, market, weighted_score, consensus_level,
                    success_count, failed_count, report_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.ticker,
                    report.eval_date.isoformat(),
                    report.market.value,
                    report.weighted_score,
                    report.consensus_level,
                    report.success_count,
                    report.failed_count,
                    payload,
                    report.created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def list_history(self, ticker: str | None = None, limit: int = 20) -> list[EvaluationHistoryItem]:
        limit = max(1, min(limit, 100))
        sql = """
            SELECT id, ticker, eval_date, market, weighted_score, consensus_level,
                   success_count, failed_count, created_at
            FROM evaluation_history
        """
        params: list[object] = []
        if ticker:
            sql += " WHERE ticker = ?"
            params.append(ticker.upper())
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            EvaluationHistoryItem(
                id=row["id"],
                ticker=row["ticker"],
                eval_date=row["eval_date"],
                market=row["market"],
                weighted_score=row["weighted_score"],
                consensus_level=row["consensus_level"],
                success_count=row["success_count"],
                failed_count=row["failed_count"],
                created_at=_parse_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def get_history_detail(self, history_id: int) -> EvaluationHistoryDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, report_json FROM evaluation_history WHERE id = ?",
                (history_id,),
            ).fetchone()
        if row is None:
            return None
        return EvaluationHistoryDetail(id=row["id"], report=EvalReport(**json.loads(row["report_json"])))

    def list_watchlist(self) -> list[WatchlistItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ticker, name, market, created_at FROM watchlist ORDER BY created_at DESC"
            ).fetchall()
        return [
            WatchlistItem(
                ticker=row["ticker"],
                name=row["name"],
                market=row["market"],
                created_at=_parse_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def upsert_watchlist(self, item: WatchlistCreate) -> WatchlistItem:
        task = EvaluationTask(ticker=item.ticker, market=item.market)
        now = datetime.now().astimezone()
        market = task.resolved_market
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist (ticker, name, market, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    created_at = excluded.created_at
                """,
                (task.ticker, item.name, market.value, now.isoformat()),
            )
        return WatchlistItem(ticker=task.ticker, name=item.name, market=market, created_at=now)

    def delete_watchlist(self, ticker: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    eval_date TEXT NOT NULL,
                    market TEXT NOT NULL,
                    weighted_score REAL,
                    consensus_level TEXT NOT NULL,
                    success_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evaluation_history_ticker
                ON evaluation_history(ticker, id DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
