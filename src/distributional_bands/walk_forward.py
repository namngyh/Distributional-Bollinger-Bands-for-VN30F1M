"""Development-only distributional walk-forward with per-fit/day checkpoints."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from .baseline import (
    TIMEFRAME_MINUTES, _atomic_json, _normalized_text_sha256,
    _record_metric, _write_prediction_day, load_samples,
)
from .data import sha256_file
from .distributions import FitConfig, FitError, FittedDistribution, fit_distribution


@dataclass(frozen=True)
class WalkForwardConfig:
    experiment_id: str
    prediction_start: int
    last_development_date: int
    ewma_half_life_minutes: int
    rolling_window_minutes: int
    fit_window_days: int
    refit_every_days: int
    central_coverages: tuple[float, ...]
    primary_metric: str
    failed_fit_policy: str

    @classmethod
    def from_json(cls, path: Path) -> "WalkForwardConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = cls(
            experiment_id=str(raw["experiment_id"]),
            prediction_start=int(raw["prediction_start"]),
            last_development_date=int(raw["last_development_date"]),
            ewma_half_life_minutes=int(raw["ewma_half_life_minutes"]),
            rolling_window_minutes=int(raw["rolling_window_minutes"]),
            fit_window_days=int(raw["fit_window_days"]),
            refit_every_days=int(raw["refit_every_days"]),
            central_coverages=tuple(float(x) for x in raw["central_coverages"]),
            primary_metric=str(raw["primary_metric"]),
            failed_fit_policy=str(raw["failed_fit_policy"]),
        )
        if not config.experiment_id or config.prediction_start > config.last_development_date:
            raise ValueError("Invalid walk-forward ID or date range")
        if min(config.ewma_half_life_minutes, config.rolling_window_minutes,
               config.fit_window_days, config.refit_every_days) <= 0:
            raise ValueError("All volatility and fit windows must be positive")
        if not config.central_coverages or len(set(config.central_coverages)) != len(config.central_coverages):
            raise ValueError("Coverages must be nonempty and unique")
        if any(not 0 < x < 1 for x in config.central_coverages):
            raise ValueError("Invalid central coverage")
        if config.primary_metric != "mean_pinball_equal_weight_over_coverages":
            raise ValueError("Unknown primary metric")
        if config.failed_fit_policy != "record_failure_and_skip_model_until_next_refit":
            raise ValueError("Unknown fit failure policy")
        return config


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signature(config_path: Path, fit_config_path: Path, input_path: Path,
               data_manifest_path: Path, timeframe: str, config: WalkForwardConfig,
               fit_config: FitConfig) -> dict:
    upstream = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(input_path)
    if actual != upstream["output_sha256"][f"samples_{timeframe}.csv"]:
        raise ValueError("Input sample hash differs from DATA-V1 manifest")
    sources = ("walk_forward.py", "distributions.py", "skewed.py", "baseline.py", "data.py")
    return {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}",
        "timeframe": timeframe,
        "input_sha256": actual,
        "data_manifest_sha256": sha256_file(data_manifest_path),
        "config_sha256": _normalized_text_sha256(config_path),
        "fit_config_sha256": _normalized_text_sha256(fit_config_path),
        "fit_experiment_id": fit_config.experiment_id,
        "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name))
                          for name in sources},
    }


def _initial_state(signature: dict) -> dict:
    return {
        "signature": signature,
        "last_day": None,
        "completed_days": 0,
        "refit_day": None,
        "fit_status": {},
        "fit_history": [],
        "prediction_sha256": {},
        "metrics": {},
        "paired_metrics": {},
        "complete": False,
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
                                capture_output=True, text=True, check=True, timeout=10)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _load_state(output_dir: Path, signature: dict, seed: int,
                *, create: bool) -> dict:
    manifest_path = output_dir / "run_manifest.json"
    checkpoint_path = output_dir / "latest.json"
    if not output_dir.exists():
        if not create:
            return _initial_state(signature)
        output_dir.mkdir(parents=True)
        (output_dir / "predictions").mkdir()
        _atomic_json(manifest_path, {
            "signature": signature,
            "created_at_utc": _utc_now(),
            "git_commit": _git_commit(),
            "seed": seed,
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "processor": platform.processor(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scipy": scipy.__version__,
            },
            "checkpoint_policy": "atomic latest.json after every model fit and completed trading day",
            "output_path": str(output_dir.resolve()),
        })
        return _initial_state(signature)
    if not manifest_path.exists() or not (output_dir / "predictions").is_dir():
        raise ValueError("Existing output directory lacks a valid manifest or predictions folder")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("signature") != signature:
        raise ValueError("Existing run has different dataset, config or source code")
    if not checkpoint_path.exists():
        if list((output_dir / "predictions").glob("*.csv")):
            raise ValueError("Predictions exist without a checkpoint")
        return _initial_state(signature)
    state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if state.get("signature") != signature:
        raise ValueError("Checkpoint signature mismatch")
    for day, expected in state["prediction_sha256"].items():
        file_path = output_dir / "predictions" / f"{day}.csv"
        if not file_path.exists() or sha256_file(file_path) != expected:
            raise ValueError(f"Prediction artifact missing or corrupt: {day}")
    if state["completed_days"] != len(state["prediction_sha256"]):
        raise ValueError("Checkpoint progress is inconsistent with predictions")
    return state


def _ewma_sigma(target_returns: np.ndarray, minutes: int,
                config: WalkForwardConfig) -> np.ndarray:
    """Sigma at row i uses targets strictly before i, matching BASELINE-V1."""
    window = config.rolling_window_minutes // minutes
    if config.rolling_window_minutes % minutes:
        raise ValueError("Rolling window must be divisible by timeframe")
    decay = 2 ** (-minutes / config.ewma_half_life_minutes)
    variance = None
    rolling: list[float] = []
    rolling_sum = 0.0
    sigma = np.full(len(target_returns), np.nan)
    for i, actual in enumerate(target_returns):
        previous = variance
        if previous is not None and len(rolling) == window:
            sigma[i] = math.sqrt(max(previous, 1e-16))
        squared = float(actual) ** 2
        if len(rolling) == window:
            rolling_sum -= rolling.pop(0)
        rolling.append(squared)
        rolling_sum += squared
        if previous is None:
            if len(rolling) == window:
                variance = rolling_sum / window
        else:
            variance = decay * previous + (1 - decay) * squared
    return sigma


def _training_residuals(grouped: list[tuple[int, pd.DataFrame]],
                        day_position: int, residuals: np.ndarray,
                        window_days: int) -> np.ndarray:
    """Use only complete trading dates strictly before the forecast date."""
    history = grouped[max(0, day_position - window_days):day_position]
    pieces = [residuals[frame.index.to_numpy()] for _, frame in history]
    return np.concatenate(pieces) if pieces else np.array([], dtype=float)


def _quantiles(fitted: FittedDistribution, coverages: tuple[float, ...]) -> dict[str, list[float]]:
    answer = {}
    for level in coverages:
        tag = str(round(level * 1000))
        values = np.asarray(fitted.ppf([(1 - level) / 2, (1 + level) / 2]), dtype=float)
        if not np.isfinite(values).all() or values[0] >= values[1]:
            raise FitError(f"{fitted.model}: invalid forecast quantiles")
        answer[tag] = [float(values[0]), float(values[1])]
    return answer


def _forecast_day(day: int, frame: pd.DataFrame, sigma: np.ndarray,
                  fit_status: dict, coverages: tuple[float, ...],
                  metrics: dict, paired_metrics: dict) -> list[dict]:
    rows = []
    paired = all(item["status"] == "success" for item in fit_status.values())
    for row in frame.itertuples(index=True):
        volatility = float(sigma[row.Index])
        if not math.isfinite(volatility) or volatility <= 0:
            raise ValueError(f"Missing predictive EWMA sigma on {day}")
        actual = float(row.target_log_return)
        forecast = {
            "TRADING_DATE": day,
            "session": row.session,
            "timestamp": row.timestamp,
            "available_at": row.available_at,
            "target_timestamp": row.target_timestamp,
            "CLOSE_PX": row.CLOSE_PX,
            "target_log_return": actual,
            "sigma_ewma": volatility,
        }
        for model, status in fit_status.items():
            if status["status"] != "success":
                continue
            for level in coverages:
                tag = str(round(level * 1000))
                low_z, high_z = status["quantiles"][tag]
                lower, upper = volatility * low_z, volatility * high_z
                forecast[f"{model}_q_low_{tag}"] = lower
                forecast[f"{model}_q_high_{tag}"] = upper
                forecast[f"{model}_price_low_{tag}"] = float(row.CLOSE_PX) * math.exp(lower)
                forecast[f"{model}_price_high_{tag}"] = float(row.CLOSE_PX) * math.exp(upper)
                _record_metric(metrics, model, tag, lower, upper, actual, level)
                if paired:
                    _record_metric(paired_metrics, model, tag, lower, upper, actual, level)
        rows.append(forecast)
    return rows


def _score_summary(metrics: dict) -> dict:
    scores = {}
    for key, values in metrics.items():
        n = values["n"]
        if n:
            scores[key] = {
                "n": n,
                "mean_pinball": values["pinball_sum"] / n,
                "lower_exceedance": values["lower_exceed"] / n,
                "upper_exceedance": values["upper_exceed"] / n,
                "coverage": 1 - (values["lower_exceed"] + values["upper_exceed"]) / n,
            }
    return scores


def _summary(state: dict, fit_config: FitConfig, development_days: int) -> dict:
    failures = Counter(item["model"] for item in state["fit_history"] if item["status"] == "failed")
    attempts = Counter(item["model"] for item in state["fit_history"])
    paired = _score_summary(state["paired_metrics"])
    ranking = []
    if paired:
        for model in fit_config.models:
            levels = [value for key, value in paired.items() if key.startswith(f"{model}:")]
            if levels:
                ranking.append({
                    "model": model,
                    "mean_pinball_equal_weight": sum(x["mean_pinball"] for x in levels) / len(levels),
                    "paired_forecasts": min(x["n"] for x in levels),
                    "levels": len(levels),
                })
        ranking.sort(key=lambda item: item["mean_pinball_equal_weight"])
    return {
        "signature": state["signature"],
        "complete": state["complete"],
        "completed_days": state["completed_days"],
        "development_days": development_days,
        "last_day": state["last_day"],
        "scores": _score_summary(state["metrics"]),
        "paired_scores": paired,
        "paired_pinball_ranking": ranking,
        "fit_attempts": {name: attempts[name] for name in fit_config.models},
        "fit_failures": {name: failures[name] for name in fit_config.models},
        "note": "Development OOS only. Ranking is descriptive on bars where every candidate fit succeeded; no winner selected. Final test excluded.",
    }


def run(config_path: Path, fit_config_path: Path, input_path: Path,
        data_manifest_path: Path, output_dir: Path, timeframe: str,
        *, max_days: int | None = None, check_only: bool = False) -> dict:
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError("Timeframe must be 1m or 5m")
    if max_days is not None and max_days <= 0:
        raise ValueError("max_days must be positive")
    config = WalkForwardConfig.from_json(config_path)
    fit_config = FitConfig.from_json(fit_config_path)
    signature = _signature(config_path, fit_config_path, input_path, data_manifest_path,
                           timeframe, config, fit_config)
    samples = load_samples(input_path, timeframe, config.last_development_date)
    grouped = [(int(day), frame) for day, frame in samples.groupby("TRADING_DATE", sort=True)]
    development = [(position, day, frame) for position, (day, frame) in enumerate(grouped)
                   if day >= config.prediction_start]
    if not development:
        raise ValueError("No development days in the configured date range")
    state = _load_state(output_dir, signature, fit_config.seed, create=not check_only)
    if state["last_day"] is not None and state["last_day"] not in {day for _, day, _ in development}:
        raise ValueError("Checkpoint day is not a development day")
    if check_only:
        print(f"{signature['run_id']}: inputs and checkpoint validated; "
              f"{state['completed_days']}/{len(development)} days complete")
        return _summary(state, fit_config, len(development))
    if state["complete"]:
        summary = _summary(state, fit_config, len(development))
        metrics_path = output_dir / "metrics.json"
        if not metrics_path.exists():
            _atomic_json(metrics_path, summary)
        elif json.loads(metrics_path.read_text(encoding="utf-8")) != summary:
            raise ValueError("Completed metrics differ from checkpoint")
        history_path = output_dir / "fit_history.json"
        history = {"signature": signature, "fit_history": state["fit_history"]}
        if not history_path.exists():
            _atomic_json(history_path, history)
        elif json.loads(history_path.read_text(encoding="utf-8")) != history:
            raise ValueError("Completed fit history differs from checkpoint")
        print(f"{signature['run_id']}: already complete; checkpoint and artifacts validated")
        return summary

    returns = samples["target_log_return"].to_numpy(dtype=float)
    sigma = _ewma_sigma(returns, TIMEFRAME_MINUTES[timeframe], config)
    residuals = np.divide(returns, sigma, out=np.full_like(returns, np.nan),
                          where=np.isfinite(sigma) & (sigma > 0))
    days_this_call = 0
    for development_index, (position, day, frame) in enumerate(development):
        if state["last_day"] is not None and day <= state["last_day"]:
            continue
        if development_index % config.refit_every_days == 0:
            if position == 0:
                raise ValueError("A refit needs at least one strictly prior trading day")
            train = _training_residuals(grouped, position, residuals, config.fit_window_days)
            train = train[np.isfinite(train)]
            train_first = grouped[max(0, position - config.fit_window_days)][0]
            train_last = grouped[position - 1][0]
            if state["refit_day"] != day:
                state["refit_day"] = day
                state["fit_status"] = {}
                state["updated_at_utc"] = _utc_now()
                _atomic_json(output_dir / "latest.json", state)
            for model in fit_config.models:
                if model in state["fit_status"]:
                    continue
                try:
                    fitted = fit_distribution(model, train, fit_config)
                    status = {"status": "success", "fit": fitted.as_dict(),
                              "quantiles": _quantiles(fitted, config.central_coverages)}
                    history = {"refit_day": day, "model": model, "status": "success",
                               "train_first": train_first, "train_last": train_last,
                               "n_train": len(train), "fit": fitted.as_dict(),
                               "quantiles": status["quantiles"]}
                except FitError as exc:
                    status = {"status": "failed", "reason": str(exc)}
                    history = {"refit_day": day, "model": model, "status": "failed",
                               "train_first": train_first, "train_last": train_last,
                               "n_train": len(train), "reason": str(exc)}
                state["fit_status"][model] = status
                state["fit_history"].append(history)
                state["updated_at_utc"] = _utc_now()
                _atomic_json(output_dir / "latest.json", state)
                print(f"{signature['run_id']}: {day} {model} {status['status']} "
                      f"({len(state['fit_status'])}/{len(fit_config.models)})", flush=True)
        if set(state["fit_status"]) != set(fit_config.models):
            raise ValueError("Checkpoint has incomplete fitted models for the forecast day")
        if not any(item["status"] == "success" for item in state["fit_status"].values()):
            raise ValueError(f"All distribution fits failed for refit window {state['refit_day']}")
        predictions = _forecast_day(day, frame, sigma, state["fit_status"],
                                    config.central_coverages, state["metrics"],
                                    state["paired_metrics"])
        path = output_dir / "predictions" / f"{day}.csv"
        state["prediction_sha256"][str(day)] = _write_prediction_day(path, predictions)
        state["last_day"] = day
        state["completed_days"] += 1
        state["updated_at_utc"] = _utc_now()
        _atomic_json(output_dir / "latest.json", state)
        days_this_call += 1
        if days_this_call % 20 == 0 or max_days is not None:
            print(f"{signature['run_id']}: day {day} "
                  f"({state['completed_days']}/{len(development)} days)", flush=True)
        if max_days is not None and days_this_call >= max_days:
            return _summary(state, fit_config, len(development))
    state["complete"] = True
    state["updated_at_utc"] = _utc_now()
    _atomic_json(output_dir / "latest.json", state)
    summary = _summary(state, fit_config, len(development))
    _atomic_json(output_dir / "metrics.json", summary)
    _atomic_json(output_dir / "fit_history.json", {"signature": signature,
                                                    "fit_history": state["fit_history"]})
    print(f"{signature['run_id']}: complete ({state['completed_days']} days)")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_MINUTES), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/walk_forward_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-days", type=int)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.config, args.fit_config, args.input, args.data_manifest,
        args.output_dir, args.timeframe, max_days=args.max_days, check_only=args.check_only)


if __name__ == "__main__":
    main()
