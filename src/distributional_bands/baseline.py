"""Chronological baseline forecasts with daily, resumable checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from .data import sha256_file


TIMEFRAME_MINUTES = {"1m": 1, "5m": 5}
MODELS = ("normal_ewma", "normal_rolling", "empirical_ewma")
SAMPLE_COLUMNS = (
    "TRADING_DATE", "session", "timestamp", "CLOSE_PX", "available_at",
    "target_timestamp", "target_log_return",
)


@dataclass(frozen=True)
class BaselineConfig:
    experiment_id: str
    prediction_start: int
    last_development_date: int
    ewma_half_life_minutes: int
    rolling_window_minutes: int
    empirical_window_days: int
    empirical_min_days: int
    central_coverages: tuple[float, ...]

    @classmethod
    def from_json(cls, path: Path) -> "BaselineConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = cls(
            experiment_id=raw["experiment_id"],
            prediction_start=int(raw["prediction_start"]),
            last_development_date=int(raw["last_development_date"]),
            ewma_half_life_minutes=int(raw["ewma_half_life_minutes"]),
            rolling_window_minutes=int(raw["rolling_window_minutes"]),
            empirical_window_days=int(raw["empirical_window_days"]),
            empirical_min_days=int(raw["empirical_min_days"]),
            central_coverages=tuple(float(value) for value in raw["central_coverages"]),
        )
        if not config.experiment_id or config.prediction_start > config.last_development_date:
            raise ValueError("Invalid experiment ID or development date range")
        if min(config.ewma_half_life_minutes, config.rolling_window_minutes,
               config.empirical_window_days, config.empirical_min_days) <= 0:
            raise ValueError("Windows and half-life must be positive")
        if config.empirical_min_days > config.empirical_window_days:
            raise ValueError("Minimum empirical days exceeds the available window")
        if not config.central_coverages or len(set(config.central_coverages)) != len(config.central_coverages):
            raise ValueError("Coverages must be nonempty and unique")
        if any(not 0 < level < 1 for level in config.central_coverages):
            raise ValueError("Central coverage must lie strictly between 0 and 1")
        return config


def load_samples(path: Path, timeframe: str, last_date: int) -> pd.DataFrame:
    minutes = TIMEFRAME_MINUTES[timeframe]
    frame = pd.read_csv(path)
    missing = set(SAMPLE_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing sample columns: {sorted(missing)}")
    frame = frame.loc[frame["TRADING_DATE"] <= last_date, list(SAMPLE_COLUMNS)].copy()
    if frame.empty or frame.isna().any().any():
        raise ValueError("Development samples are empty or incomplete")
    for name in ("timestamp", "available_at", "target_timestamp"):
        frame[name] = pd.to_datetime(frame[name], errors="raise")
    if not frame["timestamp"].is_monotonic_increasing or frame["timestamp"].duplicated().any():
        raise ValueError("Sample timestamps must be strictly increasing")
    if not np.isfinite(frame["target_log_return"]).all() or (frame["CLOSE_PX"] <= 0).any():
        raise ValueError("Samples contain invalid returns or close prices")
    duration = pd.Timedelta(minutes=minutes)
    if not frame["available_at"].eq(frame["timestamp"] + duration).all():
        raise ValueError("Sample availability timing is inconsistent")
    if not frame["target_timestamp"].eq(frame["available_at"]).all():
        raise ValueError("Targets must start no earlier than forecast availability")
    if not frame["timestamp"].dt.strftime("%Y%m%d").astype(int).eq(frame["TRADING_DATE"]).all():
        raise ValueError("Trading date and timestamp disagree")
    return frame.reset_index(drop=True)


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _normalized_text_sha256(path: Path) -> str:
    """Keep config/source identity stable across CRLF and LF checkouts."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _signature(config_path: Path, input_path: Path, data_manifest_path: Path,
               timeframe: str, config: BaselineConfig) -> dict:
    upstream = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    expected_hash = upstream["output_sha256"][f"samples_{timeframe}.csv"]
    actual_hash = sha256_file(input_path)
    if actual_hash != expected_hash:
        raise ValueError("Input samples do not match the data manifest")
    return {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}",
        "timeframe": timeframe,
        "input_sha256": actual_hash,
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "config_sha256": _normalized_text_sha256(config_path),
        "source_sha256": {
            "baseline.py": _normalized_text_sha256(Path(__file__)),
            "data.py": _normalized_text_sha256(Path(__file__).with_name("data.py")),
        },
    }


def _initial_state(signature: dict) -> dict:
    return {
        "signature": signature,
        "last_day": None,
        "variance_ewma": None,
        "rolling_squared_returns": [],
        "residual_days": [],
        "prediction_sha256": {},
        "metrics": {},
        "completed_days": 0,
        "complete": False,
    }


def _load_state(output_dir: Path, signature: dict) -> dict:
    manifest_path = output_dir / "run_manifest.json"
    checkpoint_path = output_dir / "latest.json"
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        (output_dir / "predictions").mkdir()
        _atomic_json(manifest_path, {
            "signature": signature,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
            },
            "checkpoint_policy": "atomic latest.json after each completed trading day; best not applicable",
        })
        return _initial_state(signature)
    if not manifest_path.exists():
        raise ValueError("Existing output directory has no run manifest")
    if not (output_dir / "predictions").is_dir():
        raise ValueError("Existing output directory has no predictions folder")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("signature") != signature:
        raise ValueError("Existing run has a different input, config or code signature")
    if not checkpoint_path.exists():
        if list((output_dir / "predictions").glob("*.csv")):
            raise ValueError("Predictions exist without a checkpoint")
        return _initial_state(signature)
    state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if state.get("signature") != signature:
        raise ValueError("Checkpoint signature mismatch")
    for day, expected in state["prediction_sha256"].items():
        prediction = output_dir / "predictions" / f"{day}.csv"
        if not prediction.exists() or sha256_file(prediction) != expected:
            raise ValueError(f"Prediction artifact is missing or corrupt: {day}")
    return state


def _record_metric(metrics: dict, model: str, tag: str, lower: float,
                   upper: float, actual: float, coverage: float) -> None:
    key = f"{model}:{tag}"
    state = metrics.setdefault(key, {
        "n": 0, "pinball_sum": 0.0, "lower_exceed": 0, "upper_exceed": 0,
    })
    alpha = (1 - coverage) / 2
    lower_loss = (alpha - float(actual < lower)) * (actual - lower)
    upper_loss = (1 - alpha - float(actual < upper)) * (actual - upper)
    state["n"] += 1
    state["pinball_sum"] += (lower_loss + upper_loss) / 2
    state["lower_exceed"] += int(actual < lower)
    state["upper_exceed"] += int(actual > upper)


def _write_prediction_day(path: Path, records: list[dict]) -> str:
    temporary = path.with_name(path.name + ".tmp")
    pd.DataFrame.from_records(records).to_csv(temporary, index=False)
    new_hash = sha256_file(temporary)
    if path.exists():
        if sha256_file(path) != new_hash:
            raise ValueError(f"Existing prediction differs from recomputed output: {path}")
        temporary.unlink()
    else:
        os.replace(temporary, path)
    return new_hash


def _summary(state: dict) -> dict:
    scores = {}
    for key, values in state["metrics"].items():
        n = values["n"]
        if n:
            scores[key] = {
                "n": n,
                "mean_pinball": values["pinball_sum"] / n,
                "lower_exceedance": values["lower_exceed"] / n,
                "upper_exceedance": values["upper_exceed"] / n,
                "coverage": 1 - (values["lower_exceed"] + values["upper_exceed"]) / n,
            }
    return {
        "signature": state["signature"],
        "completed_days": state["completed_days"],
        "last_day": state["last_day"],
        "scores": scores,
        "note": "Development walk-forward only. Final test is excluded; metrics are descriptive, not model selection.",
    }


def run(config_path: Path, input_path: Path, data_manifest_path: Path,
        output_dir: Path, timeframe: str, max_days: int | None = None) -> dict:
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError("Timeframe must be 1m or 5m")
    config = BaselineConfig.from_json(config_path)
    minutes = TIMEFRAME_MINUTES[timeframe]
    if config.rolling_window_minutes % minutes:
        raise ValueError("Rolling window must contain a whole number of bars")
    if max_days is not None and max_days <= 0:
        raise ValueError("max_days must be positive")
    signature = _signature(config_path, input_path, data_manifest_path, timeframe, config)
    samples = load_samples(input_path, timeframe, config.last_development_date)
    grouped = list(samples.groupby("TRADING_DATE", sort=True))
    state = _load_state(output_dir, signature)
    if state["complete"]:
        metrics_path = output_dir / "metrics.json"
        if not metrics_path.exists():
            _atomic_json(metrics_path, _summary(state))
        elif json.loads(metrics_path.read_text(encoding="utf-8")) != _summary(state):
            raise ValueError("Final metrics differ from the checkpoint")
        print(f"{signature['run_id']}: already complete; validated checkpoint and artifacts")
        return _summary(state)
    last_day = state["last_day"]
    if last_day is not None and last_day not in {int(day) for day, _ in grouped}:
        raise ValueError("Checkpoint day is not present in the input")
    window_bars = config.rolling_window_minutes // minutes
    decay = 2 ** (-minutes / config.ewma_half_life_minutes)
    normal = NormalDist()
    days_this_call = 0
    for day, day_frame in grouped:
        day = int(day)
        if last_day is not None and day <= last_day:
            continue
        residual_history = state["residual_days"]
        empirical = None
        if len(residual_history) >= config.empirical_min_days:
            past = np.concatenate([np.asarray(item["values"], dtype=float)
                                   for item in residual_history])
            probabilities = sorted({(1 - level) / 2 for level in config.central_coverages}
                                   | {(1 + level) / 2 for level in config.central_coverages})
            quantiles = np.quantile(past, probabilities)
            empirical = dict(zip(probabilities, quantiles))
        current_residuals = []
        predictions = []
        rolling = state["rolling_squared_returns"]
        rolling_sum = float(sum(rolling))
        for row in day_frame.itertuples(index=False):
            actual = float(row.target_log_return)
            previous_variance = state["variance_ewma"]
            if previous_variance is not None and len(rolling) == window_bars:
                sigma_ewma = math.sqrt(max(previous_variance, 1e-16))
                sigma_rolling = math.sqrt(max(rolling_sum / window_bars, 1e-16))
                if day >= config.prediction_start:
                    forecast = {
                        "TRADING_DATE": day,
                        "session": row.session,
                        "timestamp": row.timestamp,
                        "available_at": row.available_at,
                        "target_timestamp": row.target_timestamp,
                        "CLOSE_PX": row.CLOSE_PX,
                        "target_log_return": actual,
                        "sigma_ewma": sigma_ewma,
                        "sigma_rolling": sigma_rolling,
                    }
                    for level in config.central_coverages:
                        tag = str(round(level * 1000))
                        lower_probability = (1 - level) / 2
                        upper_probability = (1 + level) / 2
                        for model in MODELS:
                            if model == "empirical_ewma" and empirical is None:
                                continue
                            if model == "normal_rolling":
                                lower = normal.inv_cdf(lower_probability) * sigma_rolling
                                upper = normal.inv_cdf(upper_probability) * sigma_rolling
                            elif model == "normal_ewma":
                                lower = normal.inv_cdf(lower_probability) * sigma_ewma
                                upper = normal.inv_cdf(upper_probability) * sigma_ewma
                            else:
                                lower = float(empirical[lower_probability]) * sigma_ewma
                                upper = float(empirical[upper_probability]) * sigma_ewma
                            forecast[f"{model}_q_low_{tag}"] = lower
                            forecast[f"{model}_q_high_{tag}"] = upper
                            forecast[f"{model}_price_low_{tag}"] = float(row.CLOSE_PX) * math.exp(lower)
                            forecast[f"{model}_price_high_{tag}"] = float(row.CLOSE_PX) * math.exp(upper)
                            _record_metric(state["metrics"], model, tag, lower, upper,
                                           actual, level)
                    predictions.append(forecast)
                current_residuals.append(actual / sigma_ewma)
            squared = actual * actual
            if len(rolling) == window_bars:
                rolling_sum -= rolling.pop(0)
            rolling.append(squared)
            rolling_sum += squared
            if previous_variance is None:
                if len(rolling) == window_bars:
                    state["variance_ewma"] = rolling_sum / window_bars
            else:
                state["variance_ewma"] = decay * previous_variance + (1 - decay) * squared
        if current_residuals:
            residual_history.append({"day": day, "values": current_residuals})
            if len(residual_history) > config.empirical_window_days:
                residual_history.pop(0)
        if predictions:
            path = output_dir / "predictions" / f"{day}.csv"
            state["prediction_sha256"][str(day)] = _write_prediction_day(path, predictions)
        state["last_day"] = day
        state["completed_days"] += 1
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(output_dir / "latest.json", state)
        days_this_call += 1
        if days_this_call % 20 == 0 or max_days is not None:
            print(f"{signature['run_id']}: checkpoint after {day} "
                  f"({state['completed_days']}/{len(grouped)} days)", flush=True)
        if max_days is not None and days_this_call >= max_days:
            return _summary(state)
    state["complete"] = True
    if not state["metrics"]:
        raise ValueError("No forecasts were produced in the configured development period")
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _atomic_json(output_dir / "latest.json", state)
    summary = _summary(state)
    _atomic_json(output_dir / "metrics.json", summary)
    print(f"{signature['run_id']}: complete ({state['completed_days']} days)")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_MINUTES), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/baseline_v1.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-days", type=int, help="Bounded validation run; resumes on next call")
    args = parser.parse_args()
    run(args.config, args.input, args.data_manifest, args.output_dir,
        args.timeframe, args.max_days)


if __name__ == "__main__":
    main()
