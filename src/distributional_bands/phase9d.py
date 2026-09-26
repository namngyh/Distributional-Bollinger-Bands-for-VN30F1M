"""Phase 9D: past-only intraday-seasonal volatility and nine-family walk-forward.

The predictive scale is sigma_t = s_b(t) * sigma_tilde_t. The seasonal factor
s_b of a 15-minute bucket b is sqrt(mean r^2 in b / mean r^2 overall), measured
on the trading days strictly before the forecast day; sigma_tilde is the EWMA of
r / s_b over earlier bars. All nine families and the empirical quantile are then
refitted on z = r / sigma exactly as in Phase 5. Development only; exploratory
because the final test was already used in Phase 8.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from .baseline import (TIMEFRAME_MINUTES, _atomic_json, _normalized_text_sha256,
                       _write_prediction_day, load_samples)
from .data import sha256_file
from .distributions import FitConfig, FitError, FittedDistribution, fit_distribution
from .phase7a import _empirical_quantiles
from .selection import _transitions
from .walk_forward import (WalkForwardConfig, _ewma_sigma, _git_commit, _quantiles,
                           _training_residuals)


@dataclass(frozen=True)
class Phase9DConfig:
    experiment_id: str
    prediction_start: int
    tuning_end_date: int
    last_development_date: int
    final_test_start: int
    half_lives_minutes: tuple[int, ...]
    rolling_window_minutes: int
    seasonal_window_days: int
    seasonal_min_days: int
    seasonal_min_bucket_observations: int
    bucket_minutes: int
    bucket_labels: tuple[str, ...]
    fit_window_days: int
    refit_every_days: int
    central_coverages: tuple[float, ...]
    bucket_coverage_tags: tuple[str, ...]
    baseline_model: str
    reference: dict
    bootstrap_block_days: int
    bootstrap_replicates: int
    bootstrap_seed: int

    @classmethod
    def from_json(cls, path: Path) -> "Phase9DConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        for key in ("half_lives_minutes", "bucket_labels", "central_coverages", "bucket_coverage_tags"):
            raw[key] = tuple(raw[key])
        raw["half_lives_minutes"] = tuple(int(x) for x in raw["half_lives_minutes"])
        raw["central_coverages"] = tuple(float(x) for x in raw["central_coverages"])
        value = cls(**raw)
        if (not value.experiment_id
                or (value.prediction_start, value.tuning_end_date,
                    value.last_development_date, value.final_test_start)
                != (20220101, 20231231, 20241231, 20250101)
                or value.half_lives_minutes != (30, 60)
                or value.seasonal_window_days != 250
                or value.fit_window_days != 60 or value.refit_every_days != 5
                or value.rolling_window_minutes != 240
                or value.central_coverages != (0.9, 0.95, 0.975, 0.99, 0.995)
                or value.baseline_model != "empirical_ewma"
                or value.bucket_minutes <= 0 or value.seasonal_min_days < 1
                or value.seasonal_min_bucket_observations < 1
                or not set(value.bucket_coverage_tags) <= {str(round(c * 1000)) for c in value.central_coverages}
                or value.bootstrap_block_days < 1 or value.bootstrap_replicates < 100):
            raise ValueError("Phase 9D policy differs from the approved scope")
        return value


def bucket_index(timestamps: pd.Series, config: Phase9DConfig) -> np.ndarray:
    """Clock bucket of each target bar; unknown clock times are rejected."""
    minute = timestamps.dt.hour * 60 + timestamps.dt.minute
    start = minute // config.bucket_minutes * config.bucket_minutes
    labels = (start // 60).map("{:02d}".format) + ":" + (start % 60).map("{:02d}".format)
    lookup = {label: i for i, label in enumerate(config.bucket_labels)}
    index = labels.map(lookup)
    if index.isna().any():
        raise ValueError(f"Target bar outside configured buckets: {sorted(set(labels[index.isna()]))}")
    return index.to_numpy(dtype=int)


def seasonal_factors(days: np.ndarray, buckets: np.ndarray, returns: np.ndarray,
                     config: Phase9DConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-row factor from trading days strictly before the row's day.

    Returns the row factors, the day-by-bucket factor table and the ordered days.
    Days with fewer than seasonal_min_days of history, and buckets with too few
    observations or zero variance, use factor 1 (warm-up, never scored).
    """
    unique_days, day_position = np.unique(days, return_inverse=True)
    size = (len(unique_days), len(config.bucket_labels))
    sums, counts = np.zeros(size), np.zeros(size)
    np.add.at(sums, (day_position, buckets), returns ** 2)
    np.add.at(counts, (day_position, buckets), 1)
    cumulative_sums = np.vstack([np.zeros(size[1]), np.cumsum(sums, axis=0)])
    cumulative_counts = np.vstack([np.zeros(size[1]), np.cumsum(counts, axis=0)])
    table = np.ones(size)
    for position in range(size[0]):
        start = max(0, position - config.seasonal_window_days)
        if position - start < config.seasonal_min_days:
            continue
        window_sum = cumulative_sums[position] - cumulative_sums[start]
        window_count = cumulative_counts[position] - cumulative_counts[start]
        overall = window_sum.sum() / window_count.sum()
        usable = (window_count >= config.seasonal_min_bucket_observations) & (window_sum > 0)
        if overall > 0:
            table[position, usable] = np.sqrt(window_sum[usable] / window_count[usable] / overall)
    return table[day_position, buckets], table, unique_days


def seasonal_sigma(returns: np.ndarray, factors: np.ndarray, minutes: int,
                   half_life: int, config: Phase9DConfig) -> tuple[np.ndarray, np.ndarray]:
    """sigma_t = s_b(t) * EWMA sigma of r/s_b over bars strictly before t."""
    walk = WalkForwardConfig(config.experiment_id, config.prediction_start,
                             config.last_development_date, half_life,
                             config.rolling_window_minutes, config.fit_window_days,
                             config.refit_every_days, config.central_coverages,
                             "mean_pinball_equal_weight_over_coverages",
                             "record_failure_and_skip_model_until_next_refit")
    tilde = _ewma_sigma(returns / factors, minutes, walk)
    return factors * tilde, tilde


def _signature(config_path: Path, fit_path: Path, sample_path: Path,
               data_manifest_path: Path, timeframe: str, half_life: int,
               config: Phase9DConfig) -> dict:
    upstream = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(sample_path)
    if actual != upstream["output_sha256"][f"samples_{timeframe}.csv"]:
        raise ValueError("Input samples differ from DATA-V1 manifest")
    sources = ("phase9d.py", "phase7a.py", "walk_forward.py", "baseline.py",
               "distributions.py", "skewed.py", "selection.py", "data.py")
    return {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}-HL{half_life}",
        "timeframe": timeframe, "half_life_minutes": half_life,
        "input_sha256": actual, "data_manifest_sha256": sha256_file(data_manifest_path),
        "config_sha256": _normalized_text_sha256(config_path),
        "fit_config_sha256": _normalized_text_sha256(fit_path),
        "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name))
                          for name in sources},
    }


def _initial_state(signature: dict) -> dict:
    return {"signature": signature, "last_day": None, "completed_days": 0,
            "refit_day": None, "fit_status": {}, "fit_history": [],
            "prediction_sha256": {}, "daily_sha256": {}, "complete": False}


def _load_state(output_dir: Path, signature: dict, seed: int, *, create: bool) -> dict:
    manifest, latest = output_dir / "run_manifest.json", output_dir / "latest.json"
    if not output_dir.exists():
        if not create:
            return _initial_state(signature)
        output_dir.mkdir(parents=True)
        (output_dir / "predictions").mkdir()
        (output_dir / "daily").mkdir()
        _atomic_json(manifest, {
            "signature": signature, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(), "seed": seed,
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "numpy": np.__version__, "pandas": pd.__version__,
                            "scipy": scipy.__version__},
            "checkpoint_policy": "atomic latest.json after every model fit and forecast day",
            "output_path": str(output_dir.resolve()),
        })
        _atomic_json(latest, _initial_state(signature))
    if not manifest.exists() or not latest.exists():
        raise ValueError("Incomplete Phase 9D output directory")
    if not (output_dir / "predictions").is_dir() or not (output_dir / "daily").is_dir():
        raise ValueError("Phase 9D artifact directories are missing")
    if json.loads(manifest.read_text(encoding="utf-8"))["signature"] != signature:
        raise ValueError("Phase 9D manifest signature mismatch")
    state = json.loads(latest.read_text(encoding="utf-8"))
    if state["signature"] != signature:
        raise ValueError("Phase 9D checkpoint signature mismatch")
    if not state["completed_days"] == len(state["prediction_sha256"]) == len(state["daily_sha256"]):
        raise ValueError("Phase 9D checkpoint progress is inconsistent")
    for folder, hashes, extension in (("predictions", state["prediction_sha256"], "csv"),
                                      ("daily", state["daily_sha256"], "json")):
        for day, expected in hashes.items():
            path = output_dir / folder / f"{day}.{extension}"
            if not path.exists() or sha256_file(path) != expected:
                raise ValueError(f"Corrupt {folder} artifact for {day}")
    return state


def _score(actual: np.ndarray, low: np.ndarray, high: np.ndarray, level: float) -> np.ndarray:
    alpha = (1 - level) / 2
    lower = (alpha - (actual < low).astype(float)) * (actual - low)
    upper = (1 - alpha - (actual < high).astype(float)) * (actual - high)
    return (lower + upper) / 2


def forecast_day(day: int, frame: pd.DataFrame, sigma: np.ndarray, tilde: np.ndarray,
                 factors: np.ndarray, buckets: np.ndarray, empirical: dict,
                 fit_status: dict, config: Phase9DConfig, day_factors: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """Quantile forecasts and per-day scores for the empirical law and every successful fit."""
    rows = frame.index.to_numpy()
    s = sigma[rows]
    if not (np.isfinite(s).all() and (s > 0).all()):
        raise ValueError(f"Invalid predictive sigma on {day}")
    actual = frame["target_log_return"].to_numpy(dtype=float)
    session = frame["session"].to_numpy()
    bucket = buckets[rows]
    columns = {
        "TRADING_DATE": np.full(len(frame), day), "session": frame["session"].to_numpy(),
        "timestamp": frame["timestamp"].to_numpy(), "target_timestamp": frame["target_timestamp"].to_numpy(),
        "CLOSE_PX": frame["CLOSE_PX"].to_numpy(), "target_log_return": actual,
        "bucket": np.array(config.bucket_labels)[bucket], "seasonal_factor": factors[rows],
        "sigma_tilde": tilde[rows], "sigma_ewma": s}
    quantile_sets = {config.baseline_model: empirical}
    for model, status in fit_status.items():
        if status["status"] == "success":
            quantile_sets[model] = status["quantiles"]
    daily = {"day": day, "n": len(frame), "seasonal_factors": [float(x) for x in day_factors],
             "bucket_n": np.bincount(bucket, minlength=len(config.bucket_labels)).tolist(),
             "models": {}}
    for model, quantiles in quantile_sets.items():
        score = np.zeros(len(frame))
        levels, bucket_exceed = {}, {}
        for level in config.central_coverages:
            tag = str(round(level * 1000))
            low, high = s * quantiles[tag][0], s * quantiles[tag][1]
            if not (np.isfinite(low).all() and np.isfinite(high).all()) or (low >= high).any():
                raise ValueError(f"Invalid {model}:{tag} forecast on {day}")
            columns[f"{model}_q_low_{tag}"] = low
            columns[f"{model}_q_high_{tag}"] = high
            loss = _score(actual, low, high, level)
            score += loss / len(config.central_coverages)
            below, above = actual < low, actual > high
            levels[tag] = {"n": len(frame), "pinball_sum": float(loss.sum()),
                           "width_sum": float((high - low).sum()),
                           "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                           "lower_transitions": _transitions(below, session),
                           "upper_transitions": _transitions(above, session)}
            if tag in config.bucket_coverage_tags:
                bucket_exceed[tag] = np.bincount(bucket[below | above],
                                                 minlength=len(config.bucket_labels)).tolist()
        result = {"score_sum": float(score.sum()), "levels": levels, "bucket_exceed": bucket_exceed}
        if model != config.baseline_model:
            fitted = FittedDistribution(**fit_status[model]["fit"])
            pit = np.asarray(fitted.cdf(actual / s), dtype=float)
            tolerance = 1e-12
            if not np.isfinite(pit).all() or (pit < -tolerance).any() or (pit > 1 + tolerance).any():
                raise ValueError(f"Invalid PIT for {model} on {day}")
            pit = np.clip(pit, 0.0, 1.0)
            result["pit_histogram"] = np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist()
            result["pit_sum"] = float(pit.sum())
        daily["models"][model] = result
    return pd.DataFrame(columns), daily


def _summary(state: dict, days: list[int], output_dir: Path, models: tuple[str, ...]) -> dict:
    records = [json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
               for day in days if str(day) in state["daily_sha256"]]
    scores = {}
    for model in models:
        available = [row for row in records if model in row["models"]]
        count = sum(row["n"] for row in available)
        scores[model] = {"n": count, "mean_pinball_equal_weight":
                         sum(row["models"][model]["score_sum"] for row in available) / count if count else None}
    attempts = Counter(item["model"] for item in state["fit_history"])
    failures = Counter(item["model"] for item in state["fit_history"] if item["status"] == "failed")
    return {"signature": state["signature"], "complete": state["complete"],
            "completed_days": state["completed_days"], "development_days": len(days),
            "last_day": state["last_day"], "scores": scores,
            "fit_attempts": dict(attempts), "fit_failures": {m: failures[m] for m in attempts},
            "note": "Development OOS only; exploratory after the Phase 8 final test; no winner selected."}


def run(timeframe: str, half_life: int, config_path: Path, fit_path: Path,
        sample_path: Path, data_manifest_path: Path, output_dir: Path,
        *, check_only: bool = False, max_days: int | None = None) -> dict:
    config = Phase9DConfig.from_json(config_path)
    if timeframe not in TIMEFRAME_MINUTES or half_life not in config.half_lives_minutes:
        raise ValueError("Invalid timeframe or half-life")
    if max_days is not None and max_days <= 0:
        raise ValueError("max-days must be positive")
    fit_config = FitConfig.from_json(fit_path)
    models = (config.baseline_model,) + tuple(fit_config.models)
    signature = _signature(config_path, fit_path, sample_path, data_manifest_path,
                           timeframe, half_life, config)
    samples = load_samples(sample_path, timeframe, config.last_development_date)
    grouped = [(int(day), frame) for day, frame in samples.groupby("TRADING_DATE", sort=True)]
    development = [(position, day, frame) for position, (day, frame) in enumerate(grouped)
                   if day >= config.prediction_start]
    days = [day for _, day, _ in development]
    if not days or max(days) >= config.final_test_start:
        raise ValueError("Development period is empty or includes final test")
    state = _load_state(output_dir, signature, fit_config.seed, create=not check_only)
    if state["last_day"] is not None and state["last_day"] not in days:
        raise ValueError("Checkpoint day is outside development period")
    if check_only:
        print(f"{signature['run_id']}: inputs/checkpoint valid; {state['completed_days']}/{len(days)} days")
        return {"completed_days": state["completed_days"], "development_days": len(days)}
    if state["complete"]:
        summary = _summary(state, days, output_dir, models)
        for name, value in (("metrics.json", summary),
                            ("fit_history.json", {"signature": signature, "fit_history": state["fit_history"]})):
            path = output_dir / name
            if not path.exists():
                _atomic_json(path, value)
            elif json.loads(path.read_text(encoding="utf-8")) != value:
                raise ValueError(f"Completed Phase 9D {name} differs from checkpoint")
        print(f"{signature['run_id']}: already complete; artifacts validated")
        return summary
    returns = samples["target_log_return"].to_numpy(dtype=float)
    buckets = bucket_index(samples["target_timestamp"], config)
    factors, table, table_days = seasonal_factors(samples["TRADING_DATE"].to_numpy(), buckets,
                                                  returns, config)
    if development[0][0] < config.seasonal_window_days:
        raise ValueError("Seasonal window is not fully warm at the first development day")
    sigma, tilde = seasonal_sigma(returns, factors, TIMEFRAME_MINUTES[timeframe], half_life, config)
    residuals = np.divide(returns, sigma, out=np.full_like(returns, np.nan),
                          where=np.isfinite(sigma) & (sigma > 0))
    table_row = {int(day): i for i, day in enumerate(table_days)}
    processed = 0
    for index, (position, day, frame) in enumerate(development):
        if state["last_day"] is not None and day <= state["last_day"]:
            continue
        if index % config.refit_every_days == 0:
            train = _training_residuals(grouped, position, residuals, config.fit_window_days)
            train = train[np.isfinite(train)]
            if state["refit_day"] != day:
                state["refit_day"] = day
                state["fit_status"] = {}
                _atomic_json(output_dir / "latest.json", state)
            for model in fit_config.models:
                if model in state["fit_status"]:
                    continue
                try:
                    fitted = fit_distribution(model, train, fit_config)
                    status = {"status": "success", "fit": fitted.as_dict(),
                              "quantiles": _quantiles(fitted, config.central_coverages)}
                except FitError as exc:
                    status = {"status": "failed", "reason": str(exc)}
                state["fit_status"][model] = status
                state["fit_history"].append({
                    "refit_day": day, "model": model, "n_train": len(train),
                    "train_first": grouped[position - config.fit_window_days][0],
                    "train_last": grouped[position - 1][0], **status})
                _atomic_json(output_dir / "latest.json", state)
                print(f"{signature['run_id']}: {day} {model} {status['status']} "
                      f"({len(state['fit_status'])}/{len(fit_config.models)})", flush=True)
        if set(state["fit_status"]) != set(fit_config.models):
            raise ValueError("Checkpoint has incomplete fitted models for the forecast day")
        empirical = _empirical_quantiles(grouped, position, residuals, config)
        prediction, daily = forecast_day(day, frame, sigma, tilde, factors, buckets, empirical,
                                         state["fit_status"], config, table[table_row[day]])
        prediction_hash = _write_prediction_day(output_dir / "predictions" / f"{day}.csv",
                                                prediction.to_dict("records"))
        daily_path = output_dir / "daily" / f"{day}.json"
        if daily_path.exists() and json.loads(daily_path.read_text(encoding="utf-8")) != json.loads(json.dumps(daily)):
            raise ValueError(f"Orphan day summary differs on {day}")
        if not daily_path.exists():
            _atomic_json(daily_path, daily)
        state["prediction_sha256"][str(day)] = prediction_hash
        state["daily_sha256"][str(day)] = sha256_file(daily_path)
        state["last_day"] = day
        state["completed_days"] += 1
        _atomic_json(output_dir / "latest.json", state)
        processed += 1
        if processed % 20 == 0 or max_days is not None:
            print(f"{signature['run_id']}: {state['completed_days']}/{len(days)} days", flush=True)
        if max_days is not None and processed >= max_days:
            return _summary(state, days, output_dir, models)
    state["complete"] = True
    _atomic_json(output_dir / "latest.json", state)
    summary = _summary(state, days, output_dir, models)
    _atomic_json(output_dir / "metrics.json", summary)
    _atomic_json(output_dir / "fit_history.json", {"signature": signature,
                                                    "fit_history": state["fit_history"]})
    print(f"{signature['run_id']}: complete; {len(days)} development days")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_MINUTES), required=True)
    parser.add_argument("--half-life", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9d_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    run(args.timeframe, args.half_life, args.config, args.fit_config, args.input,
        args.data_manifest, args.output_dir, check_only=args.check_only, max_days=args.max_days)


if __name__ == "__main__":
    main()
