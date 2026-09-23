"""Phase 7A causal half-life trials with per-refit/day checkpoints.

The verified 60-minute run is an external anchor, never rerun or overwritten.
Only the 30/120-minute shortlisted-mixture and empirical-quantile trials run here.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from .baseline import (_atomic_json, _normalized_text_sha256, _write_prediction_day,
                       load_samples, TIMEFRAME_MINUTES)
from .data import sha256_file
from .distributions import FitConfig, FitError, FittedDistribution, fit_distribution
from .selection import _independence, _transitions
from .walk_forward import (_ewma_sigma, _git_commit, _quantiles,
                           _training_residuals, WalkForwardConfig)


@dataclass(frozen=True)
class Phase7AConfig:
    experiment_id: str
    prediction_start: int
    tuning_end_date: int
    last_development_date: int
    final_test_start: int
    half_lives_minutes: tuple[int, ...]
    anchor_half_life_minutes: int
    rolling_window_minutes: int
    fit_window_days: int
    refit_every_days: int
    central_coverages: tuple[float, ...]
    shortlist: dict[str, str]
    baseline_model: str
    bootstrap_block_days: int
    bootstrap_replicates: int
    bootstrap_seed: int

    @classmethod
    def from_json(cls, path: Path) -> "Phase7AConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["half_lives_minutes"] = tuple(int(x) for x in raw["half_lives_minutes"])
        raw["central_coverages"] = tuple(float(x) for x in raw["central_coverages"])
        value = cls(**raw)
        if (not value.experiment_id
                or (value.prediction_start, value.tuning_end_date,
                    value.last_development_date, value.final_test_start)
                != (20220101, 20231231, 20241231, 20250101)
                or value.half_lives_minutes != (30, 60, 120)
                or value.anchor_half_life_minutes != 60
                or value.rolling_window_minutes != 240
                or value.fit_window_days != 60 or value.refit_every_days != 5
                or value.central_coverages != (0.9, 0.95, 0.975, 0.99, 0.995)
                or value.shortlist != {"1m": "normal_mixture_3", "5m": "normal_mixture_2"}
                or value.baseline_model != "empirical_ewma"
                or value.bootstrap_block_days < 1 or value.bootstrap_replicates < 100
                or value.bootstrap_seed < 0):
            raise ValueError("Phase 7A policy differs from the approved scope")
        return value


def _walk_config(config: Phase7AConfig, half_life: int) -> WalkForwardConfig:
    return WalkForwardConfig(config.experiment_id, config.prediction_start,
                             config.last_development_date, half_life,
                             config.rolling_window_minutes, config.fit_window_days,
                             config.refit_every_days, config.central_coverages,
                             "mean_pinball_equal_weight_over_coverages",
                             "record_failure_and_skip_model_until_next_refit")


def _signature(config_path: Path, fit_path: Path, sample_path: Path,
               data_manifest_path: Path, timeframe: str, half_life: int,
               config: Phase7AConfig) -> dict:
    upstream = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(sample_path)
    if actual != upstream["output_sha256"][f"samples_{timeframe}.csv"]:
        raise ValueError("Input samples differ from DATA-V1 manifest")
    sources = ("phase7a.py", "walk_forward.py", "baseline.py", "distributions.py",
               "skewed.py", "selection.py", "data.py")
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
            "refit_day": None, "fit_status": None, "fit_history": [],
            "prediction_sha256": {}, "daily_sha256": {}, "complete": False}


def _load_state(output_dir: Path, signature: dict, seed: int,
                *, create: bool) -> dict:
    manifest = output_dir / "run_manifest.json"
    latest = output_dir / "latest.json"
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
            "checkpoint_policy": "atomic latest.json after fit attempt and forecast day",
            "output_path": str(output_dir.resolve()),
        })
        _atomic_json(latest, _initial_state(signature))
    if not manifest.exists() or not latest.exists():
        raise ValueError("Incomplete Phase 7A output directory")
    if not (output_dir / "predictions").is_dir() or not (output_dir / "daily").is_dir():
        raise ValueError("Phase 7A artifact directories are missing")
    if json.loads(manifest.read_text(encoding="utf-8"))["signature"] != signature:
        raise ValueError("Phase 7A manifest signature mismatch")
    state = json.loads(latest.read_text(encoding="utf-8"))
    if state["signature"] != signature:
        raise ValueError("Phase 7A checkpoint signature mismatch")
    if state["completed_days"] != len(state["prediction_sha256"]) or state["completed_days"] != len(state["daily_sha256"]):
        raise ValueError("Phase 7A checkpoint progress is inconsistent")
    for folder, hashes, extension in (("predictions", state["prediction_sha256"], "csv"),
                                      ("daily", state["daily_sha256"], "json")):
        found = {path.stem for path in (output_dir / folder).glob(f"*.{extension}")}
        if not set(hashes).issubset(found):
            raise ValueError(f"Missing checkpointed {folder} artifact")
        for day, expected in hashes.items():
            path = output_dir / folder / f"{day}.{extension}"
            if sha256_file(path) != expected:
                raise ValueError(f"Corrupt {folder} artifact for {day}")
    return state


def _empirical_quantiles(grouped: list[tuple[int, pd.DataFrame]], position: int,
                         residuals: np.ndarray, config: Phase7AConfig) -> dict[str, list[float]]:
    if position < config.fit_window_days:
        raise ValueError("Empirical quantile window is not fully warm")
    past = _training_residuals(grouped, position, residuals, config.fit_window_days)
    past = past[np.isfinite(past)]
    if len(past) < 80:
        raise ValueError("Too few historical residuals for empirical quantiles")
    probs = sorted({(1 - level) / 2 for level in config.central_coverages}
                   | {(1 + level) / 2 for level in config.central_coverages})
    values = dict(zip(probs, np.quantile(past, probs)))
    return {str(round(level * 1000)):
            [float(values[(1 - level) / 2]), float(values[(1 + level) / 2])]
            for level in config.central_coverages}


def _forecast_day(day: int, frame: pd.DataFrame, sigma: np.ndarray,
                  empirical: dict[str, list[float]], status: dict,
                  config: Phase7AConfig, mixture: str) -> pd.DataFrame:
    rows = []
    for row in frame.itertuples(index=True):
        s = float(sigma[row.Index])
        if not math.isfinite(s) or s <= 0:
            raise ValueError(f"Invalid predictive sigma on {day}")
        item = {"TRADING_DATE": day, "session": row.session,
                "timestamp": row.timestamp, "available_at": row.available_at,
                "target_timestamp": row.target_timestamp, "CLOSE_PX": row.CLOSE_PX,
                "target_log_return": row.target_log_return, "sigma_ewma": s}
        quantile_sets = {"empirical_ewma": empirical}
        if status["status"] == "success":
            quantile_sets[mixture] = status["quantiles"]
        for model, quantiles in quantile_sets.items():
            for tag, (low_z, high_z) in quantiles.items():
                low, high = s * low_z, s * high_z
                item[f"{model}_q_low_{tag}"] = low
                item[f"{model}_q_high_{tag}"] = high
                item[f"{model}_price_low_{tag}"] = float(row.CLOSE_PX) * math.exp(low)
                item[f"{model}_price_high_{tag}"] = float(row.CLOSE_PX) * math.exp(high)
        rows.append(item)
    return pd.DataFrame.from_records(rows)


def _day_scores(day: int, prediction: pd.DataFrame, config: Phase7AConfig,
                mixture: str, status: dict) -> dict:
    actual = prediction["target_log_return"].to_numpy(dtype=float)
    session = prediction["session"].to_numpy()
    result = {"day": day, "n": len(prediction), "models": {}}
    for model in (config.baseline_model, mixture):
        if model == mixture and status["status"] != "success":
            continue
        score = np.zeros(len(prediction), dtype=float)
        by_level = {}
        for level in config.central_coverages:
            tag = str(round(level * 1000))
            low = prediction[f"{model}_q_low_{tag}"].to_numpy(dtype=float)
            high = prediction[f"{model}_q_high_{tag}"].to_numpy(dtype=float)
            if not np.isfinite(low).all() or not np.isfinite(high).all() or (low >= high).any():
                raise ValueError(f"Invalid {model}:{tag} forecast on {day}")
            alpha = (1 - level) / 2
            lower = (alpha - (actual < low).astype(float)) * (actual - low)
            upper = (1 - alpha - (actual < high).astype(float)) * (actual - high)
            loss = (lower + upper) / 2
            score += loss / len(config.central_coverages)
            below, above = actual < low, actual > high
            by_level[tag] = {
                "n": len(prediction), "pinball_sum": float(loss.sum()),
                "width_sum": float((high - low).sum()),
                "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                "lower_transitions": _transitions(below, session),
                "upper_transitions": _transitions(above, session),
            }
        model_result = {"score_sum": float(score.sum()), "levels": by_level}
        if model == mixture:
            fitted = FittedDistribution(**status["fit"])
            pit = np.asarray(fitted.cdf(actual / prediction["sigma_ewma"].to_numpy(dtype=float)))
            # EM weights can sum to 1 + a few ulps. Preserve genuine invalid CDFs.
            tolerance = 1e-12
            if (not np.isfinite(pit).all() or (pit < -tolerance).any()
                    or (pit > 1 + tolerance).any()):
                raise ValueError(f"Invalid PIT for {model} on {day}")
            pit = np.clip(pit, 0.0, 1.0)
            model_result["pit_histogram"] = np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist()
            model_result["pit_sum"] = float(pit.sum())
        result["models"][model] = model_result
    return result


def _trial_summary(state: dict, days: list[int], output_dir: Path,
                   config: Phase7AConfig, mixture: str) -> dict:
    records = [json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
               for day in days if str(day) in state["daily_sha256"]]
    scores = {}
    for model in (config.baseline_model, mixture):
        available = [row for row in records if model in row["models"]]
        count = sum(row["n"] for row in available)
        scores[model] = {"n": count,
                         "mean_pinball_equal_weight": (sum(row["models"][model]["score_sum"]
                                                           for row in available) / count if count else None)}
    return {"signature": state["signature"], "complete": state["complete"],
            "completed_days": state["completed_days"], "development_days": len(days),
            "last_day": state["last_day"], "fit_attempts": len(state["fit_history"]),
            "fit_failures": sum(item["status"] == "failed" for item in state["fit_history"]),
            "scores": scores,
            "note": "Development OOS only; 60-minute anchor is reused, not refitted."}


def run(timeframe: str, half_life: int, config_path: Path, fit_path: Path,
        sample_path: Path, data_manifest_path: Path, output_dir: Path,
        *, check_only: bool = False, max_days: int | None = None) -> dict:
    config = Phase7AConfig.from_json(config_path)
    if timeframe not in TIMEFRAME_MINUTES or half_life not in config.half_lives_minutes:
        raise ValueError("Invalid timeframe or half-life")
    if half_life == config.anchor_half_life_minutes:
        raise ValueError("60-minute anchor must be reused, not rerun")
    if max_days is not None and max_days <= 0:
        raise ValueError("max-days must be positive")
    fit_config = FitConfig.from_json(fit_path)
    mixture = config.shortlist[timeframe]
    if mixture not in fit_config.models:
        raise ValueError("Shortlisted mixture absent from fit policy")
    fit_config = replace(fit_config, models=(mixture,))
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
        summary = _trial_summary(state, days, output_dir, config, mixture)
        path = output_dir / "metrics.json"
        if not path.exists():
            _atomic_json(path, summary)
        elif json.loads(path.read_text(encoding="utf-8")) != summary:
            raise ValueError("Completed Phase 7A metrics differ from checkpoint")
        print(f"{signature['run_id']}: already complete; artifacts validated")
        return summary
    walk_config = _walk_config(config, half_life)
    returns = samples["target_log_return"].to_numpy(dtype=float)
    sigma = _ewma_sigma(returns, TIMEFRAME_MINUTES[timeframe], walk_config)
    residuals = np.divide(returns, sigma, out=np.full_like(returns, np.nan),
                          where=np.isfinite(sigma) & (sigma > 0))
    processed = 0
    for index, (position, day, frame) in enumerate(development):
        if state["last_day"] is not None and day <= state["last_day"]:
            continue
        if index % config.refit_every_days == 0:
            if state["refit_day"] != day:
                state["refit_day"] = day
                state["fit_status"] = None
                _atomic_json(output_dir / "latest.json", state)
            if state["fit_status"] is None:
                train = _training_residuals(grouped, position, residuals, config.fit_window_days)
                train = train[np.isfinite(train)]
                try:
                    fitted = fit_distribution(mixture, train, fit_config)
                    status = {"status": "success", "fit": fitted.as_dict(),
                              "quantiles": _quantiles(fitted, config.central_coverages)}
                except FitError as exc:
                    status = {"status": "failed", "reason": str(exc)}
                state["fit_status"] = status
                state["fit_history"].append({"refit_day": day, "train_first": grouped[position - config.fit_window_days][0],
                                             "train_last": grouped[position - 1][0],
                                             "n_train": len(train), "model": mixture, **status})
                _atomic_json(output_dir / "latest.json", state)
                print(f"{signature['run_id']}: {day} {mixture} fit {status['status']}", flush=True)
        if state["fit_status"] is None:
            raise ValueError("No fitted model state for forecast day")
        empirical = _empirical_quantiles(grouped, position, residuals, config)
        prediction = _forecast_day(day, frame, sigma, empirical, state["fit_status"], config, mixture)
        path = output_dir / "predictions" / f"{day}.csv"
        prediction_hash = _write_prediction_day(path, prediction.to_dict("records"))
        daily = _day_scores(day, prediction, config, mixture, state["fit_status"])
        daily_path = output_dir / "daily" / f"{day}.json"
        if daily_path.exists() and json.loads(daily_path.read_text(encoding="utf-8")) != daily:
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
            return _trial_summary(state, days, output_dir, config, mixture)
    state["complete"] = True
    _atomic_json(output_dir / "latest.json", state)
    summary = _trial_summary(state, days, output_dir, config, mixture)
    _atomic_json(output_dir / "metrics.json", summary)
    print(f"{signature['run_id']}: complete; {len(days)} development days")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_MINUTES), required=True)
    parser.add_argument("--half-life", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase7a_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    run(args.timeframe, args.half_life, args.config, args.fit_config, args.input,
        args.data_manifest, args.output_dir, check_only=args.check_only,
        max_days=args.max_days)


if __name__ == "__main__":
    main()
