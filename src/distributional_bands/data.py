"""Auditable, deterministic preparation of contiguous 1m and 5m bars."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "SYMBOL", "TRADING_DATE", "OPEN_PX", "HIGH_PX", "LOW_PX", "CLOSE_PX",
    "VOL", "TRADING_TIME", "BUY_VOL", "BUY_VAL", "SELL_VOL", "SELL_VAL",
)


@dataclass(frozen=True)
class Session:
    name: str
    start: str
    end: str


@dataclass(frozen=True)
class DataPolicy:
    policy_id: str
    symbol: str
    timezone: str
    timestamp_convention: str
    rollover_status: str
    sessions: tuple[Session, ...]

    @classmethod
    def from_json(cls, path: Path) -> "DataPolicy":
        raw = json.loads(path.read_text(encoding="utf-8"))
        sessions = tuple(Session(**item) for item in raw["sessions"])
        if not sessions or len({item.name for item in sessions}) != len(sessions):
            raise ValueError("Sessions must be nonempty and uniquely named")
        for item in sessions:
            start = pd.to_timedelta(item.start)
            end = pd.to_timedelta(item.end)
            duration = int((end - start).total_seconds() / 60) + 1
            if end < start or duration % 5:
                raise ValueError(f"Session {item.name} must contain a whole number of 5m bars")
        ordered = sorted(sessions, key=lambda item: item.start)
        if any(left.end >= right.start for left, right in zip(ordered, ordered[1:])):
            raise ValueError("Sessions must not overlap")
        return cls(
            policy_id=raw["policy_id"],
            symbol=raw["symbol"],
            timezone=raw["timezone"],
            timestamp_convention=raw["timestamp_convention"],
            rollover_status=raw["rollover_status"],
            sessions=sessions,
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_raw(path: Path, policy: DataPolicy) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if frame.empty or frame[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Raw data is empty or has missing required values")
    if frame["SYMBOL"].nunique() != 1 or frame["SYMBOL"].iat[0] != policy.symbol:
        raise ValueError(f"Expected only symbol {policy.symbol}")
    try:
        frame["timestamp"] = pd.to_datetime(
            frame["TRADING_DATE"].astype(str) + " " + frame["TRADING_TIME"],
            format="%Y%m%d %H:%M:%S",
            errors="raise",
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid date or time in raw data") from exc
    if not frame["timestamp"].is_monotonic_increasing or frame["timestamp"].duplicated().any():
        raise ValueError("Timestamps must be strictly increasing and unique")
    prices = frame[["OPEN_PX", "HIGH_PX", "LOW_PX", "CLOSE_PX"]].to_numpy()
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("OHLC prices must be positive and finite")
    if (
        (frame["HIGH_PX"] < frame[["OPEN_PX", "CLOSE_PX", "LOW_PX"]].max(axis=1)).any()
        or (frame["LOW_PX"] > frame[["OPEN_PX", "CLOSE_PX", "HIGH_PX"]].min(axis=1)).any()
    ):
        raise ValueError("OHLC ordering is invalid")
    if (frame[["VOL", "BUY_VOL", "SELL_VOL"]] < 0).any().any():
        raise ValueError("Volumes must be nonnegative")
    return frame


def continuous_bars(raw: pd.DataFrame, policy: DataPolicy) -> pd.DataFrame:
    """Select policy sessions; preserve original rows and source timestamps."""
    times = raw["TRADING_TIME"]
    labels = np.select(
        [(times >= s.start) & (times <= s.end) for s in policy.sessions],
        [s.name for s in policy.sessions],
        default="excluded",
    )
    bars = raw.loc[labels != "excluded", [
        "TRADING_DATE", "timestamp", "OPEN_PX", "HIGH_PX", "LOW_PX", "CLOSE_PX", "VOL",
    ]].copy()
    bars.insert(1, "session", labels[labels != "excluded"])
    return bars.reset_index(drop=True)


def five_minute_bars(one_minute: pd.DataFrame, policy: DataPolicy) -> tuple[pd.DataFrame, int]:
    """Aggregate only complete five-minute buckets within each session."""
    bars = one_minute.copy()
    start_by_session = {session.name: pd.to_timedelta(session.start) for session in policy.sessions}
    session_start = pd.to_datetime(bars["TRADING_DATE"].astype(str), format="%Y%m%d")
    session_start += bars["session"].map(start_by_session)
    elapsed = (bars["timestamp"] - session_start).dt.total_seconds() / 60
    if (elapsed < 0).any() or (elapsed % 1 != 0).any():
        raise ValueError("Source timestamps are outside whole-minute session slots")
    bars["bucket"] = (elapsed // 5).astype(int)
    grouped = bars.groupby(["TRADING_DATE", "session", "bucket"], sort=False)
    result = grouped.agg(
        timestamp=("timestamp", "min"),
        last_timestamp=("timestamp", "max"),
        source_bars=("timestamp", "size"),
        OPEN_PX=("OPEN_PX", "first"),
        HIGH_PX=("HIGH_PX", "max"),
        LOW_PX=("LOW_PX", "min"),
        CLOSE_PX=("CLOSE_PX", "last"),
        VOL=("VOL", "sum"),
    ).reset_index()
    expected_start = pd.to_datetime(result["TRADING_DATE"].astype(str), format="%Y%m%d")
    expected_start += result["session"].map(start_by_session)
    expected_start += pd.to_timedelta(result["bucket"] * 5, unit="min")
    complete = (
        result["source_bars"].eq(5)
        & result["timestamp"].eq(expected_start)
        & result["last_timestamp"].eq(expected_start + pd.Timedelta(minutes=4))
    )
    incomplete_count = int((~complete).sum())
    result = result.loc[complete, [
        "TRADING_DATE", "session", "timestamp", "OPEN_PX", "HIGH_PX", "LOW_PX", "CLOSE_PX", "VOL",
    ]].reset_index(drop=True)
    return result, incomplete_count


def forecast_samples(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Attach next-bar outcome only when the next bar is contiguous in-session."""
    result = bars.copy()
    grouped = result.groupby(["TRADING_DATE", "session"], sort=False)
    next_timestamp = grouped["timestamp"].shift(-1)
    next_close = grouped["CLOSE_PX"].shift(-1)
    contiguous = next_timestamp.sub(result["timestamp"]).eq(pd.Timedelta(minutes=minutes))
    result = result.loc[contiguous].copy()
    result["available_at"] = result["timestamp"] + pd.Timedelta(minutes=minutes)
    result["target_timestamp"] = next_timestamp.loc[contiguous].to_numpy()
    result["target_log_return"] = np.log(
        next_close.loc[contiguous].to_numpy() / result["CLOSE_PX"].to_numpy()
    )
    return result.reset_index(drop=True)


def prepare(raw: pd.DataFrame, policy: DataPolicy) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    one_minute = continuous_bars(raw, policy)
    five_minute, incomplete = five_minute_bars(one_minute, policy)
    one_samples = forecast_samples(one_minute, 1)
    five_samples = forecast_samples(five_minute, 5)
    report = {
        "policy_id": policy.policy_id,
        "raw_rows": int(len(raw)),
        "trading_days": int(raw["TRADING_DATE"].nunique()),
        "first_timestamp": str(raw["timestamp"].iat[0]),
        "last_timestamp": str(raw["timestamp"].iat[-1]),
        "continuous_1m_bars": int(len(one_minute)),
        "excluded_non_continuous_rows": int(len(raw) - len(one_minute)),
        "non_contiguous_or_session_end_1m_bars": int(len(one_minute) - len(one_samples)),
        "complete_5m_bars": int(len(five_minute)),
        "incomplete_5m_buckets": incomplete,
        "forecast_samples_1m": int(len(one_samples)),
        "forecast_samples_5m": int(len(five_samples)),
        "buy_sell_volume_mismatch_rows": int(
            (raw["BUY_VOL"] + raw["SELL_VOL"] != raw["VOL"]).sum()
        ),
        "timestamp_convention": policy.timestamp_convention,
        "timezone": policy.timezone,
        "rollover_status": policy.rollover_status,
    }
    return one_samples, five_samples, report
