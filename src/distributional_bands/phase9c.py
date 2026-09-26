"""Phase 9C: descriptive nine-family table on 2025-01-01..2026-07-17 (exploratory).

The final period was already used once in Phase 8, so this run selects nothing:
it applies the Phase 9D seasonal-sigma protocol (half-life chosen on development:
30 for 1m, 60 for 5m) to the later period only to see whether the development
ordering of families persists. Reference is the unadjusted empirical HL30 law
from the verified Phase 8 run on the same bars. No p-values are reported.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .baseline import (TIMEFRAME_MINUTES, _atomic_json, _normalized_text_sha256,
                       _write_prediction_day, load_samples)
from .data import sha256_file
from .distributions import FitConfig, FitError, fit_distribution
from .phase7a import _empirical_quantiles
from .phase7a_report import _model_stats, _read_days
from .phase9d import _load_state, _summary as _development_summary, bucket_index, forecast_day, seasonal_factors, seasonal_sigma
from .walk_forward import _quantiles, _training_residuals


@dataclass(frozen=True)
class Phase9CConfig:
    experiment_id: str
    prediction_start: int
    last_development_date: int
    final_period_start: int
    half_life_by_timeframe: dict
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
    calendar_split_date: int
    reference: dict
    development_report: str

    @classmethod
    def from_json(cls, path: Path) -> "Phase9CConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        for key in ("bucket_labels", "bucket_coverage_tags"):
            raw[key] = tuple(raw[key])
        raw["central_coverages"] = tuple(float(x) for x in raw["central_coverages"])
        value = cls(**raw)
        if ((value.prediction_start, value.final_period_start, value.last_development_date)
                != (20250101, 20250101, 20260717)
                or value.half_life_by_timeframe != {"1m": 30, "5m": 60}
                or value.seasonal_window_days != 250 or value.fit_window_days != 60
                or value.refit_every_days != 5 or value.rolling_window_minutes != 240
                or value.central_coverages != (0.9, 0.95, 0.975, 0.99, 0.995)
                or value.baseline_model != "empirical_ewma"):
            raise ValueError("Phase 9C policy differs from the approved scope")
        return value


def _summary(state: dict, days: list[int], output_dir: Path, models: tuple[str, ...]) -> dict:
    summary = _development_summary(state, days, output_dir, models)
    summary["note"] = ("2025-2026 exploratory period after the Phase 8 final test; "
                       "descriptive only; no model reselection.")
    return summary


def _signature(config_path: Path, fit_path: Path, sample_path: Path, data_manifest_path: Path,
               timeframe: str, config: Phase9CConfig) -> dict:
    upstream = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(sample_path)
    if actual != upstream["output_sha256"][f"samples_{timeframe}.csv"]:
        raise ValueError("Input samples differ from DATA-V1 manifest")
    sources = ("phase9c.py", "phase9d.py", "phase7a.py", "walk_forward.py", "baseline.py",
               "distributions.py", "skewed.py", "selection.py", "data.py")
    half_life = config.half_life_by_timeframe[timeframe]
    return {"experiment_id": config.experiment_id,
            "run_id": f"{config.experiment_id}-{timeframe}-HL{half_life}",
            "timeframe": timeframe, "half_life_minutes": half_life,
            "input_sha256": actual, "data_manifest_sha256": sha256_file(data_manifest_path),
            "config_sha256": _normalized_text_sha256(config_path),
            "fit_config_sha256": _normalized_text_sha256(fit_path),
            "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name))
                              for name in sources}}


def run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
        data_manifest_path: Path, output_dir: Path, *, check_only: bool = False,
        max_days: int | None = None) -> dict:
    config = Phase9CConfig.from_json(config_path)
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError("Invalid timeframe")
    fit_config = FitConfig.from_json(fit_path)
    models = (config.baseline_model,) + tuple(fit_config.models)
    half_life = config.half_life_by_timeframe[timeframe]
    signature = _signature(config_path, fit_path, sample_path, data_manifest_path, timeframe, config)
    samples = load_samples(sample_path, timeframe, config.last_development_date)
    grouped = [(int(day), frame) for day, frame in samples.groupby("TRADING_DATE", sort=True)]
    period = [(position, day, frame) for position, (day, frame) in enumerate(grouped)
              if day >= config.prediction_start]
    days = [day for _, day, _ in period]
    if not days or min(days) < config.final_period_start or max(days) > config.last_development_date:
        raise ValueError("Phase 9C must cover exactly the 2025-2026 exploratory period")
    state = _load_state(output_dir, signature, fit_config.seed, create=not check_only)
    if state["last_day"] is not None and state["last_day"] not in days:
        raise ValueError("Checkpoint day is outside the Phase 9C period")
    if check_only:
        print(f"{signature['run_id']}: inputs/checkpoint valid; {state['completed_days']}/{len(days)} days")
        return {"completed_days": state["completed_days"], "period_days": len(days)}
    if state["complete"]:
        summary = _summary(state, days, output_dir, models)
        path = output_dir / "metrics.json"
        if json.loads(path.read_text(encoding="utf-8")) != summary:
            raise ValueError("Completed Phase 9C metrics differ from checkpoint")
        print(f"{signature['run_id']}: already complete; artifacts validated")
        return summary
    returns = samples["target_log_return"].to_numpy(dtype=float)
    buckets = bucket_index(samples["target_timestamp"], config)
    factors, table, table_days = seasonal_factors(samples["TRADING_DATE"].to_numpy(), buckets, returns, config)
    sigma, tilde = seasonal_sigma(returns, factors, TIMEFRAME_MINUTES[timeframe], half_life, config)
    residuals = np.divide(returns, sigma, out=np.full_like(returns, np.nan),
                          where=np.isfinite(sigma) & (sigma > 0))
    table_row = {int(day): i for i, day in enumerate(table_days)}
    processed = 0
    for index, (position, day, frame) in enumerate(period):
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
                state["fit_history"].append({"refit_day": day, "model": model, "n_train": len(train),
                                             "train_first": grouped[position - config.fit_window_days][0],
                                             "train_last": grouped[position - 1][0], **status})
                _atomic_json(output_dir / "latest.json", state)
                print(f"{signature['run_id']}: {day} {model} {status['status']} "
                      f"({len(state['fit_status'])}/{len(fit_config.models)})", flush=True)
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
    _atomic_json(output_dir / "fit_history.json", {"signature": signature, "fit_history": state["fit_history"]})
    print(f"{signature['run_id']}: complete; {len(days)} days")
    return summary


def _rank_correlation(first: dict[str, float], second: dict[str, float]) -> float | None:
    keys = [k for k in first if k in second and first[k] is not None and second[k] is not None]
    if len(keys) < 3:
        return None
    a = pd.Series([first[k] for k in keys]).rank().to_numpy()
    b = pd.Series([second[k] for k in keys]).rank().to_numpy()
    return float(np.corrcoef(a, b)[0, 1])


def build_report(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
                 data_manifest: Path, root: Path, output_dir: Path) -> dict:
    config = Phase9CConfig.from_json(config_path)
    fit = FitConfig.from_json(fit_path)
    models = (config.baseline_model,) + tuple(fit.models)
    half_life = config.half_life_by_timeframe[timeframe]
    signature = _signature(config_path, fit_path, sample_path, data_manifest, timeframe, config)
    state, trial_rows = _read_days(output_dir, signature)
    reference_dir = root / config.reference["directory"].format(timeframe=timeframe)
    _, reference_rows = _read_days(reference_dir, expected_count=len(trial_rows))
    reference_label = config.reference["label"]
    combined = []
    for reference, record in zip(reference_rows, trial_rows):
        if reference["day"] != record["day"] or reference["n"] != record["n"]:
            raise ValueError("Phase 9C and Phase 8 reference days/bars are misaligned")
        entry = {"day": record["day"], "n": record["n"], "paired": all(m in record["models"] for m in models),
                 "models": {reference_label: reference["models"][config.reference["model"]]}, "record": record}
        entry["models"].update({f"{m}_seasonal": record["models"][m] for m in models if m in record["models"]})
        combined.append(entry)
    labels = [reference_label] + [f"{m}_seasonal" for m in models]
    periods = {"all_final": combined,
               "calendar_2025": [r for r in combined if r["day"] <= config.calendar_split_date],
               "calendar_2026_to_july_17": [r for r in combined if r["day"] > config.calendar_split_date]}
    scores = {period: {label: _model_stats(rows, label, config.central_coverages) for label in labels}
              for period, rows in periods.items()}
    development = json.loads((root / config.development_report.format(timeframe=timeframe)).read_text(encoding="utf-8"))
    dev_scores = {m: development["periods"]["all_development"][f"{m}_hl{half_life}_seasonal"]["mean_pinball_equal_weight"]
                  for m in models}
    final_scores = {m: scores["all_final"][f"{m}_seasonal"].get("mean_pinball_equal_weight") for m in models}
    buckets = len(config.bucket_labels)
    bucket_coverage = {}
    for model in models:
        counts, exceed = [0] * buckets, [0] * buckets
        for row in combined:
            record = row["record"]
            if model in record["models"]:
                for i in range(buckets):
                    counts[i] += record["bucket_n"][i]
                    exceed[i] += record["models"][model]["bucket_exceed"]["950"][i]
        bucket_coverage[f"{model}_seasonal"] = [1 - e / c if c else None for e, c in zip(exceed, counts)]
    failures = {m: sum(1 for x in state["fit_history"] if x["model"] == m and x["status"] == "failed")
                for m in fit.models}
    return {"signature": {"experiment_id": config.experiment_id,
                          "run_id": f"{config.experiment_id}-{timeframe}-REPORT",
                          "config_sha256": _normalized_text_sha256(config_path),
                          "report_code_sha256": _normalized_text_sha256(Path(__file__)),
                          "trial_checkpoint_sha256": sha256_file(output_dir / "latest.json"),
                          "reference_checkpoint_sha256": sha256_file(reference_dir / "latest.json")},
            "complete": True, "timeframe": timeframe, "half_life_minutes": half_life,
            "days": len(combined), "first_day": combined[0]["day"], "last_day": combined[-1]["day"],
            "all_days_paired": all(r["paired"] for r in combined),
            "periods": scores, "fit_failures": failures,
            "development_vs_final_rank_correlation": _rank_correlation(dev_scores, final_scores),
            "development_mean_loss": dev_scores, "final_mean_loss": final_scores,
            "bucket_labels": list(config.bucket_labels), "bucket_coverage_950": bucket_coverage,
            "notes": ["Exploratory and descriptive only: the final period was already used in Phase 8.",
                      "No p-values; no model or parameter is reselected from these results.",
                      "Half-life fixed from Phase 9D development results (1m: 30, 5m: 60).",
                      "Reference: unadjusted empirical HL30 from the verified Phase 8 run on the same bars."]}


def report_run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
               data_manifest: Path, root: Path, output_dir: Path, *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, fit_path, sample_path, data_manifest, root, output_dir)
    path = output_dir / "report.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(report)):
            raise ValueError("Existing Phase 9C report differs from checkpoints")
    elif not check_only:
        _atomic_json(path, report)
    print(f"{report['signature']['run_id']}: verified {report['days']} days; "
          f"report {'checked' if check_only else 'ready'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_MINUTES), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9c_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", action="store_true", help="build the descriptive report")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    if args.report:
        report_run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
                   args.root, args.output_dir, check_only=args.check_only)
    else:
        run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
            args.output_dir, check_only=args.check_only, max_days=args.max_days)


if __name__ == "__main__":
    main()
