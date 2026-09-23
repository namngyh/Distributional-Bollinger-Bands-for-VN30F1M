"""Past-only expanding PIT recalibration of completed Phase 7A HL30 forecasts.

The first 60 development days supply prequential PIT history and are not scored
as calibrated forecasts. No distribution is refitted and no final-test data is read.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from .baseline import _atomic_json, _normalized_text_sha256, _write_prediction_day
from .data import sha256_file
from .distributions import FittedDistribution
from .selection import _transitions
from .walk_forward import _git_commit


@dataclass(frozen=True)
class Phase7BConfig:
    experiment_id: str
    development_last_date: int
    tuning_end_date: int
    final_test_start: int
    source_half_life_minutes: int
    warmup_days: int
    calibration_history: str
    probability_floor: float
    central_coverages: tuple[float, ...]
    baseline_model: str
    shortlist: dict[str, str]
    bootstrap_block_days: int
    bootstrap_replicates: int
    bootstrap_seed: int

    @classmethod
    def from_json(cls, path: Path) -> "Phase7BConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["central_coverages"] = tuple(float(x) for x in raw["central_coverages"])
        value = cls(**raw)
        if (value.experiment_id != "PHASE7B-V1"
                or (value.tuning_end_date, value.development_last_date, value.final_test_start)
                != (20231231, 20241231, 20250101)
                or value.source_half_life_minutes != 30
                or value.warmup_days != 60
                or value.calibration_history != "expanding_prior_development_days"
                or value.probability_floor != 1e-9
                or value.central_coverages != (0.9, 0.95, 0.975, 0.99, 0.995)
                or value.baseline_model != "empirical_ewma"
                or value.shortlist != {"1m": "normal_mixture_3", "5m": "normal_mixture_2"}
                or value.bootstrap_block_days != 5 or value.bootstrap_replicates != 2000
                or value.bootstrap_seed != 20260923):
            raise ValueError("Phase 7B policy differs from the approved experiment")
        return value


def _source(config: Phase7BConfig, timeframe: str, source_dir: Path,
            source_report: Path) -> tuple[dict, list[int]]:
    if timeframe not in config.shortlist:
        raise ValueError("Unknown timeframe")
    state_path = source_dir / "latest.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    manifest = json.loads((source_dir / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((source_dir / "metrics.json").read_text(encoding="utf-8"))
    report = json.loads(source_report.read_text(encoding="utf-8"))
    signature = state["signature"]
    days = sorted((int(day) for day in state["daily_sha256"]), key=int)
    if (not state["complete"] or state["completed_days"] != 748
            or len(state["prediction_sha256"]) != 748 or len(days) != 748
            or signature["run_id"] != f"PHASE7A-V1-{timeframe}-HL30"
            or signature["half_life_minutes"] != config.source_half_life_minutes
            or manifest["signature"] != signature or metrics["signature"] != signature
            or not metrics["complete"] or metrics["fit_failures"] != 0
            or not report["complete"] or report["timeframe"] != timeframe
            or report["days"] != 748 or report["last_day"] != config.development_last_date
            or report["signature"]["trial_checkpoint_sha256"]["30"] != sha256_file(state_path)
            or days[-1] != config.development_last_date or days[0] < 20220101
            or any(item["status"] != "success" or item["train_last"] >= item["refit_day"]
                   for item in state["fit_history"])):
        raise ValueError("Completed, causal Phase 7A HL30 source is required")
    return state, days


def _signature(config_path: Path, config: Phase7BConfig, timeframe: str,
               source_dir: Path, source_report: Path) -> dict:
    sources = ("phase7b.py", "distributions.py", "baseline.py", "selection.py",
               "data.py", "walk_forward.py")
    return {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}",
        "timeframe": timeframe,
        "source_half_life_minutes": config.source_half_life_minutes,
        "config_sha256": _normalized_text_sha256(config_path),
        "phase7a_checkpoint_sha256": sha256_file(source_dir / "latest.json"),
        "phase7a_report_sha256": sha256_file(source_report),
        "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name))
                          for name in sources},
    }


def _initial_state(signature: dict) -> dict:
    return {"signature": signature, "last_day": None, "completed_days": 0,
            "pit_sha256": {}, "prediction_sha256": {}, "daily_sha256": {},
            "complete": False}


def _load_state(output_dir: Path, signature: dict, days: list[int],
                warmup_days: int, seed: int, *, create: bool) -> dict:
    manifest = output_dir / "run_manifest.json"
    latest = output_dir / "latest.json"
    if not output_dir.exists():
        if not create:
            return _initial_state(signature)
        output_dir.mkdir(parents=True)
        for folder in ("pits", "predictions", "daily"):
            (output_dir / folder).mkdir()
        _atomic_json(manifest, {
            "signature": signature, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(), "seed": seed,
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "numpy": np.__version__, "pandas": pd.__version__,
                            "scipy": scipy.__version__},
            "checkpoint_policy": "atomic after each completed development day, including warmup",
            "output_path": str(output_dir.resolve()),
        })
        _atomic_json(latest, _initial_state(signature))
    if not manifest.is_file() or not latest.is_file():
        raise ValueError("Incomplete Phase 7B output directory")
    if json.loads(manifest.read_text(encoding="utf-8"))["signature"] != signature:
        raise ValueError("Phase 7B manifest signature mismatch")
    state = json.loads(latest.read_text(encoding="utf-8"))
    if state["signature"] != signature:
        raise ValueError("Phase 7B checkpoint signature mismatch")
    completed = state["completed_days"]
    if (completed > len(days) or state["last_day"] != (days[completed - 1] if completed else None)
            or set(state["pit_sha256"]) != {str(day) for day in days[:completed]}
            or set(state["daily_sha256"]) != {str(day) for day in days[:completed]}
            or set(state["prediction_sha256"]) !=
            {str(day) for day in days[warmup_days:completed]}):
        raise ValueError("Phase 7B checkpoint progress is inconsistent")
    for folder, hashes, extension in (("pits", state["pit_sha256"], "npy"),
                                      ("predictions", state["prediction_sha256"], "csv"),
                                      ("daily", state["daily_sha256"], "json")):
        if not (output_dir / folder).is_dir():
            raise ValueError(f"Missing Phase 7B {folder} directory")
        for day, expected in hashes.items():
            path = output_dir / folder / f"{day}.{extension}"
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"Corrupt Phase 7B {folder} artifact for {day}")
    return state


def _write_pits(path: Path, values: np.ndarray) -> str:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.save(stream, values, allow_pickle=False)
    digest = sha256_file(temporary)
    if path.exists():
        if sha256_file(path) != digest:
            raise ValueError(f"Existing PIT array differs from recomputation: {path}")
        temporary.unlink()
    else:
        os.replace(temporary, path)
    return digest


def _fit_for_day(day: int, history: list[dict], refit_days: list[int]) -> FittedDistribution:
    position = bisect_right(refit_days, day) - 1
    if position < 0 or history[position]["status"] != "success":
        raise ValueError(f"No successful past fit for {day}")
    return FittedDistribution(**history[position]["fit"])


def _raw_pit(fit: FittedDistribution, source: pd.DataFrame, day: int) -> np.ndarray:
    actual = source["target_log_return"].to_numpy(dtype=float)
    sigma = source["sigma_ewma"].to_numpy(dtype=float)
    if not np.isfinite(actual).all() or not np.isfinite(sigma).all() or (sigma <= 0).any():
        raise ValueError(f"Invalid actual/sigma on {day}")
    pit = np.asarray(fit.cdf(actual / sigma), dtype=float)
    if (not np.isfinite(pit).all() or (pit < -1e-12).any() or (pit > 1 + 1e-12).any()):
        raise ValueError(f"Invalid source PIT on {day}")
    return np.clip(pit, 0.0, 1.0)


def _calibration_map(past_pit: np.ndarray, fit: FittedDistribution,
                     config: Phase7BConfig) -> tuple[dict[str, tuple[float, float]], dict]:
    probabilities = sorted({(1 - level) / 2 for level in config.central_coverages}
                           | {(1 + level) / 2 for level in config.central_coverages})
    mapped = np.clip(np.quantile(past_pit, probabilities),
                     config.probability_floor, 1 - config.probability_floor)
    if not np.isfinite(mapped).all() or (np.diff(mapped) <= 0).any():
        raise ValueError("PIT calibration map is nonfinite or not strictly monotone")
    quantiles = np.asarray(fit.ppf(mapped), dtype=float)
    if not np.isfinite(quantiles).all() or (np.diff(quantiles) <= 0).any():
        raise ValueError("Calibrated quantiles are nonfinite or unordered")
    lookup = dict(zip(probabilities, quantiles))
    bands = {str(round(level * 1000)): (float(lookup[(1 - level) / 2]),
                                           float(lookup[(1 + level) / 2]))
             for level in config.central_coverages}
    return bands, {str(probability): float(value)
                   for probability, value in zip(probabilities, mapped)}


def _forecast(source: pd.DataFrame, bands: dict[str, tuple[float, float]],
              model: str) -> pd.DataFrame:
    columns = ("TRADING_DATE", "session", "timestamp", "available_at", "target_timestamp",
               "CLOSE_PX", "target_log_return", "sigma_ewma")
    result = source.loc[:, list(columns)].copy()
    sigma = result["sigma_ewma"].to_numpy(dtype=float)
    close = result["CLOSE_PX"].to_numpy(dtype=float)
    for tag, (low_z, high_z) in bands.items():
        low, high = sigma * low_z, sigma * high_z
        result[f"{model}_q_low_{tag}"] = low
        result[f"{model}_q_high_{tag}"] = high
        result[f"{model}_price_low_{tag}"] = close * np.exp(low)
        result[f"{model}_price_high_{tag}"] = close * np.exp(high)
    return result


def _day_scores(day: int, prediction: pd.DataFrame, calibrated_pit: np.ndarray,
                config: Phase7BConfig, model: str) -> dict:
    actual = prediction["target_log_return"].to_numpy(dtype=float)
    session = prediction["session"].to_numpy()
    score = np.zeros(len(prediction), dtype=float)
    by_level = {}
    for level in config.central_coverages:
        tag = str(round(level * 1000))
        low = prediction[f"{model}_q_low_{tag}"].to_numpy(dtype=float)
        high = prediction[f"{model}_q_high_{tag}"].to_numpy(dtype=float)
        if not np.isfinite(low).all() or not np.isfinite(high).all() or (low >= high).any():
            raise ValueError(f"Invalid calibrated band {tag} on {day}")
        alpha = (1 - level) / 2
        lower = (alpha - (actual < low).astype(float)) * (actual - low)
        upper = (1 - alpha - (actual < high).astype(float)) * (actual - high)
        loss = (lower + upper) / 2
        score += loss / len(config.central_coverages)
        below, above = actual < low, actual > high
        by_level[tag] = {"n": len(prediction), "pinball_sum": float(loss.sum()),
                         "width_sum": float((high - low).sum()),
                         "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                         "lower_transitions": _transitions(below, session),
                         "upper_transitions": _transitions(above, session)}
    return {"day": day, "n": len(prediction), "models": {model: {
        "score_sum": float(score.sum()), "levels": by_level,
        "pit_histogram": np.histogram(calibrated_pit, bins=np.linspace(0, 1, 11))[0].tolist(),
        "pit_sum": float(calibrated_pit.sum())}}}


def _summary(state: dict, days: list[int], output_dir: Path,
             config: Phase7BConfig, model: str) -> dict:
    calibrated_days = days[config.warmup_days:state["completed_days"]]
    rows = [json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
            for day in calibrated_days]
    count = sum(row["n"] for row in rows)
    return {"signature": state["signature"], "complete": state["complete"],
            "completed_days": state["completed_days"], "development_days": len(days),
            "calibrated_days": len(calibrated_days), "last_day": state["last_day"],
            "calibrated_bars": count,
            "mean_pinball_equal_weight": (sum(row["models"][model]["score_sum"]
                                               for row in rows) / count if count else None),
            "note": "Expanding past-only PIT calibration; first 60 days are warmup, not scored."}


def run(timeframe: str, config_path: Path, source_dir: Path, source_report: Path,
        output_dir: Path, *, check_only: bool = False,
        max_days: int | None = None) -> dict:
    config = Phase7BConfig.from_json(config_path)
    if max_days is not None and max_days <= 0:
        raise ValueError("max-days must be positive")
    source_state, days = _source(config, timeframe, source_dir, source_report)
    signature = _signature(config_path, config, timeframe, source_dir, source_report)
    state = _load_state(output_dir, signature, days, config.warmup_days,
                        config.bootstrap_seed, create=not check_only)
    if check_only:
        print(f"{signature['run_id']}: inputs/checkpoint valid; "
              f"{state['completed_days']}/{len(days)} days")
        return {"completed_days": state["completed_days"], "development_days": len(days)}
    model = f"{config.shortlist[timeframe]}_pit_calibrated"
    if state["complete"]:
        summary = _summary(state, days, output_dir, config, model)
        path = output_dir / "metrics.json"
        if not path.exists():
            _atomic_json(path, summary)
        elif json.loads(path.read_text(encoding="utf-8")) != summary:
            raise ValueError("Completed Phase 7B metrics differ from checkpoint")
        print(f"{signature['run_id']}: already complete; artifacts validated")
        return summary
    history = source_state["fit_history"]
    refit_days = [item["refit_day"] for item in history]
    if refit_days != sorted(set(refit_days)):
        raise ValueError("Invalid Phase 7A fit chronology")
    past_arrays = [np.load(output_dir / "pits" / f"{day}.npy", allow_pickle=False)
                   for day in days[:state["completed_days"]]]
    processed = 0
    for index in range(state["completed_days"], len(days)):
        day = days[index]
        source_path = source_dir / "predictions" / f"{day}.csv"
        if sha256_file(source_path) != source_state["prediction_sha256"][str(day)]:
            raise ValueError(f"Corrupt Phase 7A source forecast for {day}")
        source_daily_path = source_dir / "daily" / f"{day}.json"
        if sha256_file(source_daily_path) != source_state["daily_sha256"][str(day)]:
            raise ValueError(f"Corrupt Phase 7A daily source for {day}")
        source = pd.read_csv(source_path)
        if (not len(source) or not (source["TRADING_DATE"] == day).all()
                or len(source) != json.loads(source_daily_path.read_text(encoding="utf-8"))["n"]):
            raise ValueError(f"Misaligned Phase 7A source day {day}")
        fit = _fit_for_day(day, history, refit_days)
        raw_pit = _raw_pit(fit, source, day)
        daily = {"day": day, "n": len(source), "calibrated": False,
                 "history_days": index, "history_pit_count": sum(len(x) for x in past_arrays),
                 "models": {}}
        if index >= config.warmup_days:
            past = np.concatenate(past_arrays)
            bands, probability_map = _calibration_map(past, fit, config)
            prediction = _forecast(source, bands, model)
            prediction_path = output_dir / "predictions" / f"{day}.csv"
            prediction_hash = _write_prediction_day(prediction_path,
                                                    prediction.to_dict("records"))
            rank = np.searchsorted(np.sort(past), raw_pit, side="right")
            calibrated_pit = (rank + 0.5) / (len(past) + 1)
            daily = _day_scores(day, prediction, calibrated_pit, config, model)
            daily.update({"calibrated": True, "history_days": index,
                          "history_pit_count": len(past),
                          "probability_map": probability_map})
            state["prediction_sha256"][str(day)] = prediction_hash
        pit_path = output_dir / "pits" / f"{day}.npy"
        pit_hash = _write_pits(pit_path, raw_pit)
        daily_path = output_dir / "daily" / f"{day}.json"
        if daily_path.exists() and json.loads(daily_path.read_text(encoding="utf-8")) != daily:
            raise ValueError(f"Orphan Phase 7B daily summary differs on {day}")
        if not daily_path.exists():
            _atomic_json(daily_path, daily)
        state["pit_sha256"][str(day)] = pit_hash
        state["daily_sha256"][str(day)] = sha256_file(daily_path)
        state["last_day"] = day
        state["completed_days"] += 1
        _atomic_json(output_dir / "latest.json", state)
        past_arrays.append(raw_pit)
        processed += 1
        if processed % 20 == 0 or max_days is not None:
            print(f"{signature['run_id']}: {state['completed_days']}/{len(days)} days", flush=True)
        if max_days is not None and processed >= max_days:
            return _summary(state, days, output_dir, config, model)
    state["complete"] = True
    _atomic_json(output_dir / "latest.json", state)
    summary = _summary(state, days, output_dir, config, model)
    _atomic_json(output_dir / "metrics.json", summary)
    print(f"{signature['run_id']}: complete; {len(days)} development days, "
          f"{summary['calibrated_days']} calibrated days")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase7b_v1.json"))
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    run(args.timeframe, args.config, args.source_dir, args.source_report,
        args.output_dir, check_only=args.check_only, max_days=args.max_days)


if __name__ == "__main__":
    main()
