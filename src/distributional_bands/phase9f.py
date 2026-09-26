"""Phase 9F: sensitivity of Phase 9D forecasts to the scale normalisation (no refit).

Phase 9D turns each fitted raw law into a variance-one law with its own
theoretical moments, q_std = (F_raw^{-1}(p) - m) / s, and forecasts sigma * q_std.
The alternative keeps the fitted location and scale, q_raw = m + s * q_std, and
forecasts sigma * q_raw. Both variants share the identical fit and sigma, so the
comparison isolates the normalisation. Read-only: every Phase 9D prediction and
daily file is verified against its complete checkpoint.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .baseline import _atomic_json, _normalized_text_sha256
from .data import sha256_file
from .phase7a_report import _model_stats
from .phase9d import Phase9DConfig, _score
from .selection import SelectionConfig, _bootstrap, _transitions


def _holm(p_values: dict[str, float]) -> dict[str, float]:
    order = sorted(p_values, key=p_values.get)
    adjusted, current = {}, 0.0
    for rank, key in enumerate(order):
        current = max(current, min(1.0, p_values[key] * (len(order) - rank)))
        adjusted[key] = current
    return adjusted


def _active_fits(fit_history: list[dict], days: list[int]) -> dict[int, dict]:
    """Map each forecast day to the model fits of the latest refit on or before it."""
    by_refit: dict[int, dict] = {}
    for item in fit_history:
        by_refit.setdefault(int(item["refit_day"]), {})[item["model"]] = item
    refits = sorted(by_refit)
    active, pointer = {}, -1
    for day in days:
        while pointer + 1 < len(refits) and refits[pointer + 1] <= day:
            pointer += 1
        if pointer < 0:
            raise ValueError(f"No refit precedes forecast day {day}")
        active[day] = by_refit[refits[pointer]]
    return active


def raw_day_scores(prediction: pd.DataFrame, fits: dict, config: Phase9DConfig,
                   tolerance: float) -> dict:
    """Score sigma * (m + s * q_std) for every successful family on one day."""
    actual = prediction["target_log_return"].to_numpy(dtype=float)
    sigma = prediction["sigma_ewma"].to_numpy(dtype=float)
    session = prediction["session"].to_numpy()
    lookup = {label: i for i, label in enumerate(config.bucket_labels)}
    bucket = prediction["bucket"].map(lookup).to_numpy(dtype=int)
    result = {}
    for model, item in fits.items():
        if item["status"] != "success":
            continue
        center, spread = float(item["fit"]["center"]), float(item["fit"]["spread"])
        score = np.zeros(len(prediction))
        levels, bucket_exceed = {}, {}
        for level in config.central_coverages:
            tag = str(round(level * 1000))
            low_std, high_std = item["quantiles"][tag]
            stored_low = prediction[f"{model}_q_low_{tag}"].to_numpy(dtype=float)
            if np.max(np.abs(stored_low - sigma * low_std)) > tolerance * np.max(sigma):
                raise ValueError(f"Stored {model} quantiles do not match the active fit")
            low, high = sigma * (center + spread * low_std), sigma * (center + spread * high_std)
            loss = _score(actual, low, high, level)
            score += loss / len(config.central_coverages)
            below, above = actual < low, actual > high
            levels[tag] = {"n": len(prediction), "pinball_sum": float(loss.sum()),
                           "width_sum": float((high - low).sum()),
                           "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                           "lower_transitions": _transitions(below, session),
                           "upper_transitions": _transitions(above, session)}
            if tag in config.bucket_coverage_tags:
                bucket_exceed[tag] = np.bincount(bucket[below | above],
                                                 minlength=len(config.bucket_labels)).tolist()
        result[model] = {"score_sum": float(score.sum()), "levels": levels,
                         "bucket_exceed": bucket_exceed, "center": center, "spread": spread}
    return result


def _trial_rows(directory: Path, config: Phase9DConfig, tolerance: float) -> tuple[list[dict], str, dict]:
    state = json.loads((directory / "latest.json").read_text(encoding="utf-8"))
    history = json.loads((directory / "fit_history.json").read_text(encoding="utf-8"))
    if not state["complete"] or history["signature"] != state["signature"]:
        raise ValueError(f"Phase 9D trial incomplete or inconsistent: {directory}")
    if history["fit_history"] != state["fit_history"]:
        raise ValueError(f"Phase 9D fit history differs from checkpoint: {directory}")
    days = sorted(int(day) for day in state["prediction_sha256"])
    if days[-1] > config.last_development_date:
        raise ValueError("Phase 9F must stay inside the development period")
    active = _active_fits(state["fit_history"], days)
    rows, spreads = [], {}
    for day in days:
        prediction_path = directory / "predictions" / f"{day}.csv"
        daily_path = directory / "daily" / f"{day}.json"
        if (sha256_file(prediction_path) != state["prediction_sha256"][str(day)]
                or sha256_file(daily_path) != state["daily_sha256"][str(day)]):
            raise ValueError(f"Phase 9D artifact differs from checkpoint on {day}")
        daily = json.loads(daily_path.read_text(encoding="utf-8"))
        raw = raw_day_scores(pd.read_csv(prediction_path), active[day], config, tolerance)
        models = {f"{model}_std": value for model, value in daily["models"].items()}
        models.update({f"{model}_raw": value for model, value in raw.items()})
        for model, value in raw.items():
            spreads.setdefault(model, []).append((value["center"], value["spread"]))
        rows.append({"day": day, "n": daily["n"], "paired": True, "models": models,
                     "bucket_n": daily["bucket_n"]})
    summary = {model: {"median_center": float(np.median([c for c, _ in values])),
                       "median_spread": float(np.median([s for _, s in values]))}
               for model, values in spreads.items()}
    return rows, sha256_file(directory / "latest.json"), summary


def build_report(timeframe: str, config_path: Path, root: Path) -> dict:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    source_config_path = root / raw["source_config"]
    source = Phase9DConfig.from_json(source_config_path)
    if tuple(raw["half_lives_minutes"]) != source.half_lives_minutes:
        raise ValueError("Phase 9F half-lives must match Phase 9D")
    bootstrap_config = SelectionConfig(raw["experiment_id"], source.baseline_model,
                                       source.bootstrap_block_days, source.bootstrap_replicates,
                                       source.bootstrap_seed, 10, source.final_test_start)
    result, hashes = {}, {}
    for half_life in source.half_lives_minutes:
        directory = root / raw["source_root"] / timeframe / f"hl{half_life}"
        rows, checkpoint_hash, normalisation = _trial_rows(directory, source, float(raw["quantile_tolerance"]))
        hashes[str(half_life)] = checkpoint_hash
        families = sorted({key[:-4] for row in rows for key in row["models"] if key.endswith("_raw")})
        labels = [f"{source.baseline_model}_std"] + [f"{m}_{v}" for m in families for v in ("std", "raw")]
        periods = {"tuning_2022_2023": [r for r in rows if r["day"] <= raw["tuning_end_date"]],
                   "retrospective_2024": [r for r in rows if r["day"] > raw["tuning_end_date"]],
                   "all_development": rows}
        scores = {period: {label: _model_stats(part, label, source.central_coverages) for label in labels}
                  for period, part in periods.items()}
        p_values, comparisons = {}, {}
        for model in families:
            paired = [{"day": r["day"], "n": r["n"], "paired": True,
                       "models": {k: r["models"][k] for k in (f"{model}_std", f"{model}_raw")}}
                      for r in periods["tuning_2022_2023"] if f"{model}_raw" in r["models"]]
            test = _bootstrap(paired, (f"{model}_raw",), f"{model}_std", bootstrap_config)
            comparison = test["comparisons"][f"{model}_raw"]
            comparisons[model] = {"paired_days": test["paired_days"], **comparison}
            p_values[model] = comparison["p_two_sided"]
        for model, adjusted in _holm(p_values).items():
            comparisons[model]["p_holm_across_families"] = adjusted
        buckets = len(source.bucket_labels)
        bucket_coverage = {}
        for label in labels:
            counts, exceed = [0] * buckets, [0] * buckets
            for row in rows:
                if label in row["models"]:
                    for i in range(buckets):
                        counts[i] += row["bucket_n"][i]
                        exceed[i] += row["models"][label]["bucket_exceed"]["950"][i]
            bucket_coverage[label] = [1 - e / c if c else None for e, c in zip(exceed, counts)]
        result[str(half_life)] = {"periods": scores, "raw_minus_std_tuning": comparisons,
                                  "fitted_location_scale": normalisation,
                                  "bucket_coverage_950": bucket_coverage}
    return {"signature": {"experiment_id": raw["experiment_id"], "run_id": f"{raw['experiment_id']}-{timeframe}",
                          "config_sha256": _normalized_text_sha256(config_path),
                          "source_config_sha256": _normalized_text_sha256(source_config_path),
                          "code_sha256": _normalized_text_sha256(Path(__file__)),
                          "phase9d_checkpoint_sha256": hashes},
            "timeframe": timeframe, "half_lives": result,
            "notes": ["Exploratory; development 2022-2024 only; no refit, Phase 9D fits and sigma reused.",
                      "raw = keep fitted location and scale; std = Phase 9D variance-one normalisation.",
                      "Paired bootstrap per family on its own available days; Holm across families."]}


def run(timeframe: str, config_path: Path, root: Path, output_dir: Path, *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, root)
    path = output_dir / "report.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(report)):
            raise ValueError("Existing Phase 9F report differs from recomputation")
        status = "checked"
    elif check_only:
        raise ValueError("No Phase 9F report to check")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, report)
        status = "ready"
    print(f"{report['signature']['run_id']}: report {status}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9f_v1.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.timeframe, args.config, args.root, args.output_dir, check_only=args.check_only)


if __name__ == "__main__":
    main()
