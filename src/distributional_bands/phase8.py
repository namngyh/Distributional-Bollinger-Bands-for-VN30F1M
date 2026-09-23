"""Frozen, one-shot 2025–2026 final-test forecasts; no model selection here.

The 5m fit cadence continues from Phase 7A. PIT calibration begins with the
completed Phase 7B development history and adds each final day only afterward.
"""

from __future__ import annotations

import argparse
import json
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
from .phase7a import _empirical_quantiles
from .phase7b import (Phase7BConfig, _calibration_map, _forecast,
                      _load_state as _load_phase7b, _raw_pit, _signature as _phase7b_signature,
                      _source as _phase7a_source, _write_pits)
from .selection import _transitions
from .walk_forward import (_ewma_sigma, _git_commit, _training_residuals,
                           _quantiles, WalkForwardConfig)


@dataclass(frozen=True)
class Phase8Config:
    experiment_id: str
    final_test_start: int
    final_test_end: int
    development_last_date: int
    development_start: int
    ewma_half_life_minutes: int
    rolling_window_minutes: int
    fit_window_days: int
    refit_every_days: int
    central_coverages: tuple[float, ...]
    probability_floor: float
    locked_models: dict[str, str]
    five_minute_reference: str
    phase7b_report_sha256: dict[str, str]
    bootstrap_block_days: int
    bootstrap_replicates: int
    bootstrap_seed: int

    @classmethod
    def from_json(cls, path: Path) -> "Phase8Config":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["central_coverages"] = tuple(float(x) for x in raw["central_coverages"])
        config = cls(**raw)
        if (config.experiment_id != "PHASE8-V1"
                or (config.development_start, config.development_last_date,
                    config.final_test_start, config.final_test_end)
                != (20220101, 20241231, 20250101, 20260717)
                or (config.ewma_half_life_minutes, config.rolling_window_minutes,
                    config.fit_window_days, config.refit_every_days) != (30, 240, 60, 5)
                or config.central_coverages != (0.9, 0.95, 0.975, 0.99, 0.995)
                or config.probability_floor != 1e-9
                or config.locked_models != {"1m": "empirical_ewma",
                                            "5m": "normal_mixture_2_pit_calibrated"}
                or config.five_minute_reference != "empirical_ewma"
                or set(config.phase7b_report_sha256) != {"1m", "5m"}
                or any(len(value) != 64 for value in config.phase7b_report_sha256.values())
                or (config.bootstrap_block_days, config.bootstrap_replicates,
                    config.bootstrap_seed) != (5, 2000, 20260923)):
            raise ValueError("Phase 8 policy differs from the approved frozen final test")
        return config


def _walk_config(config: Phase8Config) -> WalkForwardConfig:
    return WalkForwardConfig(config.experiment_id, config.final_test_start,
                             config.final_test_end, config.ewma_half_life_minutes,
                             config.rolling_window_minutes, config.fit_window_days,
                             config.refit_every_days, config.central_coverages,
                             "mean_pinball_equal_weight_over_coverages",
                             "record_failure_and_skip_model_until_next_refit")


def _lineage(config: Phase8Config, timeframe: str, phase7a_dir: Path,
             phase7a_report: Path, phase7b_dir: Path, phase7b_report: Path) -> tuple[dict, dict, list[int]]:
    if sha256_file(phase7b_report) != config.phase7b_report_sha256[timeframe]:
        raise ValueError("Phase 7B report differs from approved model-lock evidence")
    report = json.loads(phase7b_report.read_text(encoding="utf-8"))
    if (not report["complete"] or report["timeframe"] != timeframe
            or report["last_scored_day"] != config.development_last_date
            or report["scored_days"] != 688):
        raise ValueError("Phase 7B report is incomplete or outside development")
    b_config_path = Path("configs/phase7b_v1.json")
    b_config = Phase7BConfig.from_json(b_config_path)
    a_state, days = _phase7a_source(b_config, timeframe, phase7a_dir, phase7a_report)
    b_signature = _phase7b_signature(b_config_path, b_config, timeframe,
                                     phase7a_dir, phase7a_report)
    b_state = _load_phase7b(phase7b_dir, b_signature, days, b_config.warmup_days,
                            b_config.bootstrap_seed, create=False)
    if (not b_state["complete"] or b_state["completed_days"] != len(days)
            or report["signature"]["phase7b_checkpoint_sha256"]
            != sha256_file(phase7b_dir / "latest.json")):
        raise ValueError("Phase 7B checkpoint/report lineage mismatch")
    return a_state, b_state, days


def _signature(config_path: Path, fit_path: Path, sample_path: Path,
               data_manifest: Path, timeframe: str, phase7a_dir: Path,
               phase7b_dir: Path, phase7b_report: Path) -> dict:
    upstream = json.loads(data_manifest.read_text(encoding="utf-8"))
    input_hash = sha256_file(sample_path)
    if input_hash != upstream["output_sha256"][f"samples_{timeframe}.csv"]:
        raise ValueError("Phase 8 samples differ from DATA-V1 manifest")
    sources = ("phase8.py", "phase7a.py", "phase7b.py", "walk_forward.py",
               "baseline.py", "distributions.py", "skewed.py", "selection.py", "data.py")
    return {
        "experiment_id": "PHASE8-V1", "run_id": f"PHASE8-V1-{timeframe}",
        "timeframe": timeframe, "input_sha256": input_hash,
        "data_manifest_sha256": sha256_file(data_manifest),
        "config_sha256": _normalized_text_sha256(config_path),
        "fit_config_sha256": _normalized_text_sha256(fit_path),
        "phase7a_checkpoint_sha256": sha256_file(phase7a_dir / "latest.json"),
        "phase7b_checkpoint_sha256": sha256_file(phase7b_dir / "latest.json"),
        "phase7b_report_sha256": sha256_file(phase7b_report),
        "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name))
                          for name in sources},
    }


def _initial_state(signature: dict, source_fit: dict | None, source_refit_day: int | None) -> dict:
    return {"signature": signature, "last_day": None, "completed_days": 0,
            "refit_day": source_refit_day, "fit_status": source_fit,
            "fit_history": [], "prediction_sha256": {}, "daily_sha256": {},
            "pit_sha256": {}, "complete": False}


def _load_state(output_dir: Path, signature: dict, final_days: list[int],
                initial: dict, *, create: bool) -> dict:
    manifest_path, latest_path = output_dir / "run_manifest.json", output_dir / "latest.json"
    if not output_dir.exists():
        if not create:
            return initial
        output_dir.mkdir(parents=True)
        for folder in ("predictions", "daily", "pits"):
            (output_dir / folder).mkdir()
        _atomic_json(manifest_path, {
            "signature": signature, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(), "seed": 20260923,
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "numpy": np.__version__, "pandas": pd.__version__,
                            "scipy": scipy.__version__},
            "checkpoint_policy": "atomic after each fit attempt and final-test trading day",
            "output_path": str(output_dir.resolve()),
        })
        _atomic_json(latest_path, initial)
    if not manifest_path.is_file() or not latest_path.is_file():
        raise ValueError("Incomplete Phase 8 output directory")
    if json.loads(manifest_path.read_text(encoding="utf-8"))["signature"] != signature:
        raise ValueError("Phase 8 manifest signature mismatch")
    state = json.loads(latest_path.read_text(encoding="utf-8"))
    if state["signature"] != signature:
        raise ValueError("Phase 8 checkpoint signature mismatch")
    count = state["completed_days"]
    expected_days = {str(day) for day in final_days[:count]}
    if (count > len(final_days) or state["last_day"] != (final_days[count - 1] if count else None)
            or set(state["prediction_sha256"]) != expected_days
            or set(state["daily_sha256"]) != expected_days
            or set(state["pit_sha256"]) != (expected_days if signature["timeframe"] == "5m" else set())):
        raise ValueError("Phase 8 checkpoint progress is inconsistent")
    for folder, hashes, suffix in (("predictions", state["prediction_sha256"], "csv"),
                                   ("daily", state["daily_sha256"], "json"),
                                   ("pits", state["pit_sha256"], "npy")):
        if not (output_dir / folder).is_dir():
            raise ValueError(f"Missing Phase 8 {folder} directory")
        for day, expected in hashes.items():
            path = output_dir / folder / f"{day}.{suffix}"
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"Corrupt Phase 8 {folder} artifact for {day}")
    return state


def _empirical_forecast(frame: pd.DataFrame, sigma: np.ndarray,
                        empirical: dict[str, list[float]]) -> pd.DataFrame:
    columns = ("TRADING_DATE", "session", "timestamp", "available_at",
               "target_timestamp", "CLOSE_PX", "target_log_return")
    prediction = frame.loc[:, columns].copy().reset_index(drop=True)
    prediction["sigma_ewma"] = sigma[frame.index.to_numpy()]
    s = prediction["sigma_ewma"].to_numpy(dtype=float)
    if not np.isfinite(s).all() or (s <= 0).any():
        raise ValueError("Invalid predictive EWMA sigma")
    close = prediction["CLOSE_PX"].to_numpy(dtype=float)
    for tag, (low_z, high_z) in empirical.items():
        low, high = s * low_z, s * high_z
        prediction[f"empirical_ewma_q_low_{tag}"] = low
        prediction[f"empirical_ewma_q_high_{tag}"] = high
        prediction[f"empirical_ewma_price_low_{tag}"] = close * np.exp(low)
        prediction[f"empirical_ewma_price_high_{tag}"] = close * np.exp(high)
    return prediction


def _score_day(day: int, prediction: pd.DataFrame, models: tuple[str, ...],
               config: Phase8Config, calibrated_pit: np.ndarray | None = None) -> dict:
    actual = prediction["target_log_return"].to_numpy(dtype=float)
    session = prediction["session"].to_numpy()
    result = {"day": day, "n": len(prediction), "models": {}}
    for model in models:
        score = np.zeros(len(prediction), dtype=float)
        levels = {}
        for coverage in config.central_coverages:
            tag = str(round(coverage * 1000))
            low = prediction[f"{model}_q_low_{tag}"].to_numpy(dtype=float)
            high = prediction[f"{model}_q_high_{tag}"].to_numpy(dtype=float)
            if (not np.isfinite(low).all() or not np.isfinite(high).all()
                    or (low >= high).any()):
                raise ValueError(f"Invalid Phase 8 {model}:{tag} band on {day}")
            alpha = (1 - coverage) / 2
            lower_loss = (alpha - (actual < low).astype(float)) * (actual - low)
            upper_loss = (1 - alpha - (actual < high).astype(float)) * (actual - high)
            loss = (lower_loss + upper_loss) / 2
            score += loss / len(config.central_coverages)
            below, above = actual < low, actual > high
            levels[tag] = {"n": len(actual), "pinball_sum": float(loss.sum()),
                           "width_sum": float((high - low).sum()),
                           "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                           "lower_transitions": _transitions(below, session),
                           "upper_transitions": _transitions(above, session)}
        item = {"score_sum": float(score.sum()), "levels": levels}
        if calibrated_pit is not None and model == config.locked_models["5m"]:
            item["pit_histogram"] = np.histogram(calibrated_pit,
                                                  bins=np.linspace(0, 1, 11))[0].tolist()
            item["pit_sum"] = float(calibrated_pit.sum())
        result["models"][model] = item
    return result


def _summary(state: dict, final_days: list[int], output_dir: Path,
             config: Phase8Config, timeframe: str) -> dict:
    selected = config.locked_models[timeframe]
    rows = [json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
            for day in final_days[:state["completed_days"]]]
    n = sum(row["n"] for row in rows)
    return {"signature": state["signature"], "complete": state["complete"],
            "completed_days": state["completed_days"], "final_days": len(final_days),
            "last_day": state["last_day"], "selected_model": selected,
            "scored_bars": n, "fit_attempts": len(state["fit_history"]),
            "fit_failures": sum(x["status"] == "failed" for x in state["fit_history"]),
            "mean_pinball_equal_weight": (sum(row["models"][selected]["score_sum"]
                                              for row in rows) / n if n else None)}


def run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
        data_manifest: Path, phase7a_dir: Path, phase7a_report: Path,
        phase7b_dir: Path, phase7b_report: Path, output_dir: Path,
        *, check_only: bool = False, max_days: int | None = None) -> dict:
    config = Phase8Config.from_json(config_path)
    if timeframe not in TIMEFRAME_MINUTES or (max_days is not None and max_days <= 0):
        raise ValueError("Invalid Phase 8 timeframe or max-days")
    fit_config = FitConfig.from_json(fit_path)
    if "normal_mixture_2" not in fit_config.models:
        raise ValueError("Approved 5m Mixture 2 missing from fit policy")
    fit_config = replace(fit_config, models=("normal_mixture_2",))
    a_state, _, development_days = _lineage(
        config, timeframe, phase7a_dir, phase7a_report, phase7b_dir, phase7b_report)
    if _normalized_text_sha256(fit_path) != a_state["signature"]["fit_config_sha256"]:
        raise ValueError("Phase 8 fit policy differs from the completed Phase 7A fit policy")
    signature = _signature(config_path, fit_path, sample_path, data_manifest,
                           timeframe, phase7a_dir, phase7b_dir, phase7b_report)
    samples = load_samples(sample_path, timeframe, config.final_test_end)
    grouped = [(int(day), frame) for day, frame in samples.groupby("TRADING_DATE", sort=True)]
    development = [(position, day, frame) for position, (day, frame) in enumerate(grouped)
                   if config.development_start <= day <= config.development_last_date]
    final = [(position, day, frame) for position, (day, frame) in enumerate(grouped)
             if config.final_test_start <= day <= config.final_test_end]
    days = [day for _, day, _ in final]
    if (not final or days[-1] != config.final_test_end
            or [day for _, day, _ in development] != development_days
            or len(set(days)) != len(days) or days[0] < config.final_test_start):
        raise ValueError("Phase 8 data period or development chronology mismatch")
    prior_fit = a_state["fit_history"][-1] if timeframe == "5m" else None
    if timeframe == "5m" and (prior_fit["status"] != "success"
                               or prior_fit["refit_day"] > config.development_last_date):
        raise ValueError("No valid development fit to continue into final test")
    initial = _initial_state(signature,
                             {"status": "success", "fit": prior_fit["fit"],
                              "quantiles": prior_fit["quantiles"]} if prior_fit else None,
                             prior_fit["refit_day"] if prior_fit else None)
    state = _load_state(output_dir, signature, days, initial, create=not check_only)
    if check_only:
        print(f"{signature['run_id']}: lineage/checkpoint valid; "
              f"{state['completed_days']}/{len(days)} final days")
        return {"completed_days": state["completed_days"], "final_days": len(days)}
    if state["complete"]:
        summary = _summary(state, days, output_dir, config, timeframe)
        metrics_path = output_dir / "metrics.json"
        if not metrics_path.is_file() or json.loads(metrics_path.read_text(encoding="utf-8")) != summary:
            raise ValueError("Completed Phase 8 metrics differ from checkpoint")
        print(f"{signature['run_id']}: already complete; artifacts validated")
        return summary
    returns = samples["target_log_return"].to_numpy(dtype=float)
    sigma = _ewma_sigma(returns, TIMEFRAME_MINUTES[timeframe], _walk_config(config))
    residuals = np.divide(returns, sigma, out=np.full_like(returns, np.nan),
                          where=np.isfinite(sigma) & (sigma > 0))
    past_pit = []
    if timeframe == "5m":
        past_pit = [np.load(phase7b_dir / "pits" / f"{day}.npy", allow_pickle=False)
                    for day in development_days]
        past_pit += [np.load(output_dir / "pits" / f"{day}.npy", allow_pickle=False)
                     for day in days[:state["completed_days"]]]
    processed = 0
    for final_index in range(state["completed_days"], len(final)):
        position, day, frame = final[final_index]
        if timeframe == "5m" and (len(development_days) + final_index) % config.refit_every_days == 0:
            if state["refit_day"] != day:
                state["refit_day"] = day
                state["fit_status"] = None
                _atomic_json(output_dir / "latest.json", state)
            if state["fit_status"] is None:
                train = _training_residuals(grouped, position, residuals, config.fit_window_days)
                train = train[np.isfinite(train)]
                try:
                    fitted = fit_distribution("normal_mixture_2", train, fit_config)
                    status = {"status": "success", "fit": fitted.as_dict(),
                              "quantiles": _quantiles(fitted, config.central_coverages)}
                except FitError as exc:
                    status = {"status": "failed", "reason": str(exc)}
                state["fit_status"] = status
                state["fit_history"].append({"refit_day": day,
                    "train_first": grouped[position - config.fit_window_days][0],
                    "train_last": grouped[position - 1][0], "n_train": len(train),
                    "model": "normal_mixture_2", **status})
                _atomic_json(output_dir / "latest.json", state)
                print(f"{signature['run_id']}: {day} Mixture 2 fit {status['status']}", flush=True)
        if timeframe == "5m" and (state["fit_status"] is None
                                   or state["fit_status"]["status"] != "success"):
            raise ValueError(f"Selected 5m fit failed on {day}; checkpoint kept, no fallback")
        empirical = _empirical_quantiles(grouped, position, residuals, config)
        prediction = _empirical_forecast(frame, sigma, empirical)
        models = ("empirical_ewma",)
        raw_pit = calibrated_pit = None
        if timeframe == "5m":
            fit = FittedDistribution(**state["fit_status"]["fit"])
            past = np.concatenate(past_pit)
            bands, _ = _calibration_map(past, fit, config)
            selected = config.locked_models["5m"]
            adjusted = _forecast(prediction, bands, selected)
            for name in adjusted.columns:
                if name not in prediction.columns:
                    prediction[name] = adjusted[name]
            raw_pit = _raw_pit(fit, prediction, day)
            rank = np.searchsorted(np.sort(past), raw_pit, side="right")
            calibrated_pit = (rank + 0.5) / (len(past) + 1)
            models = ("empirical_ewma", selected)
        daily = _score_day(day, prediction, models, config, calibrated_pit)
        prediction_path = output_dir / "predictions" / f"{day}.csv"
        prediction_hash = _write_prediction_day(prediction_path, prediction.to_dict("records"))
        daily_path = output_dir / "daily" / f"{day}.json"
        if daily_path.exists() and json.loads(daily_path.read_text(encoding="utf-8")) != daily:
            raise ValueError(f"Orphan Phase 8 daily score differs on {day}")
        if not daily_path.exists():
            _atomic_json(daily_path, daily)
        if raw_pit is not None:
            state["pit_sha256"][str(day)] = _write_pits(output_dir / "pits" / f"{day}.npy", raw_pit)
        state["prediction_sha256"][str(day)] = prediction_hash
        state["daily_sha256"][str(day)] = sha256_file(daily_path)
        state["last_day"] = day
        state["completed_days"] += 1
        _atomic_json(output_dir / "latest.json", state)
        if raw_pit is not None:
            past_pit.append(raw_pit)
        processed += 1
        if processed % 20 == 0 or max_days is not None:
            print(f"{signature['run_id']}: {state['completed_days']}/{len(days)} final days", flush=True)
        if max_days is not None and processed >= max_days:
            return _summary(state, days, output_dir, config, timeframe)
    state["complete"] = True
    _atomic_json(output_dir / "latest.json", state)
    summary = _summary(state, days, output_dir, config, timeframe)
    _atomic_json(output_dir / "metrics.json", summary)
    print(f"{signature['run_id']}: complete; {len(days)} final days")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase8_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--phase7a-dir", type=Path, required=True)
    parser.add_argument("--phase7a-report", type=Path, required=True)
    parser.add_argument("--phase7b-dir", type=Path, required=True)
    parser.add_argument("--phase7b-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
        args.phase7a_dir, args.phase7a_report, args.phase7b_dir, args.phase7b_report,
        args.output_dir, check_only=args.check_only, max_days=args.max_days)


if __name__ == "__main__":
    main()
