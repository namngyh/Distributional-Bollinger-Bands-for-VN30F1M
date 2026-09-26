"""Read-only Phase 9D report: seasonal-sigma families versus the unadjusted HL30 reference."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from .baseline import _atomic_json, _normalized_text_sha256
from .data import sha256_file
from .distributions import FitConfig
from .phase7a_report import _model_stats, _read_days
from .phase9d import Phase9DConfig, _signature
from .selection import SelectionConfig, _bootstrap


def _label(model: str, half_life: int) -> str:
    return f"{model}_hl{half_life}_seasonal"


def _bucket_coverage(rows: list[dict], half_life: int, model: str, tag: str, buckets: int) -> list[float | None]:
    counts, exceed = [0] * buckets, [0] * buckets
    for row in rows:
        record = row["trials"][half_life]
        if model not in record["models"]:
            continue
        for i in range(buckets):
            counts[i] += record["bucket_n"][i]
            exceed[i] += record["models"][model]["bucket_exceed"][tag][i]
    return [1 - exceed[i] / counts[i] if counts[i] else None for i in range(buckets)]


def build_report(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
                 data_manifest: Path, root: Path, output_root: Path) -> dict:
    config = Phase9DConfig.from_json(config_path)
    fit = FitConfig.from_json(fit_path)
    models = (config.baseline_model,) + tuple(fit.models)
    reference_dir = root / config.reference["directory"].format(timeframe=timeframe)
    reference_state, reference_days = _read_days(reference_dir)
    trials, trial_hashes, failures = {}, {}, {}
    for half_life in config.half_lives_minutes:
        directory = output_root / timeframe / f"hl{half_life}"
        signature = _signature(config_path, fit_path, sample_path, data_manifest,
                               timeframe, half_life, config)
        state, rows = _read_days(directory, signature, expected_count=len(reference_days))
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if metrics["signature"] != signature or not metrics["complete"]:
            raise ValueError(f"Phase 9D metrics mismatch: {directory}")
        trials[half_life] = rows
        trial_hashes[str(half_life)] = sha256_file(directory / "latest.json")
        failures[str(half_life)] = {m: sum(1 for x in state["fit_history"]
                                           if x["model"] == m and x["status"] == "failed")
                                    for m in fit.models}
    combined = []
    reference_label = config.reference["label"]
    for index, reference in enumerate(reference_days):
        day = reference["day"]
        entry = {"day": day, "n": reference["n"], "paired": True,
                 "models": {reference_label: reference["models"][config.reference["model"]]},
                 "trials": {}}
        for half_life, rows in trials.items():
            record = rows[index]
            if record["day"] != day or record["n"] != reference["n"]:
                raise ValueError("Phase 9D trial and reference days/bars are misaligned")
            entry["trials"][half_life] = record
            for model in models:
                if model in record["models"]:
                    entry["models"][_label(model, half_life)] = record["models"][model]
                else:
                    entry["paired"] = False
        combined.append(entry)
    if combined[0]["day"] < config.prediction_start or combined[-1]["day"] > config.last_development_date:
        raise ValueError("Phase 9D report must stay inside the development period")
    labels = [reference_label] + [_label(m, h) for h in config.half_lives_minutes for m in models]
    periods = {
        "tuning_2022_2023": [r for r in combined if r["day"] <= config.tuning_end_date],
        "retrospective_2024": [r for r in combined if r["day"] > config.tuning_end_date],
        "all_development": combined,
    }
    scores = {period: {key: _model_stats(rows, key, config.central_coverages) for key in labels}
              for period, rows in periods.items()}
    tuning = periods["tuning_2022_2023"]
    ranking = (sorted(labels, key=lambda key: scores["tuning_2022_2023"][key]["mean_pinball_equal_weight"])
               if all(row["paired"] for row in tuning) else [])
    bootstrap_config = SelectionConfig(config.experiment_id, config.baseline_model,
                                       config.bootstrap_block_days, config.bootstrap_replicates,
                                       config.bootstrap_seed, 10, config.final_test_start)
    versus_reference = _bootstrap(tuning, tuple(labels[1:]), reference_label, bootstrap_config)
    versus_reference["method"] = ("circular day-block bootstrap; Holm across all seasonal "
                                  "configurations versus unadjusted empirical HL30")
    within = {}
    for half_life in config.half_lives_minutes:
        result = _bootstrap(tuning, tuple(_label(m, half_life) for m in fit.models),
                            _label(config.baseline_model, half_life), bootstrap_config)
        result["method"] = ("circular day-block bootstrap; Holm across nine families "
                            "versus the seasonal empirical law at the same half-life")
        within[str(half_life)] = result
    buckets = len(config.bucket_labels)
    bucket_coverage = {tag: {_label(m, h): _bucket_coverage(combined, h, m, tag, buckets)
                             for h in config.half_lives_minutes for m in models}
                       for tag in config.bucket_coverage_tags}
    factors = {"first_day": combined[0]["trials"][config.half_lives_minutes[0]]["seasonal_factors"],
               "last_day": combined[-1]["trials"][config.half_lives_minutes[0]]["seasonal_factors"]}
    signature = {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}-REPORT",
        "config_sha256": _normalized_text_sha256(config_path),
        "report_code_sha256": _normalized_text_sha256(Path(__file__)),
        "reference_checkpoint_sha256": sha256_file(reference_dir / "latest.json"),
        "trial_checkpoint_sha256": trial_hashes,
    }
    return {
        "signature": signature, "complete": True, "timeframe": timeframe,
        "days": len(combined), "first_day": combined[0]["day"], "last_day": combined[-1]["day"],
        "bucket_labels": list(config.bucket_labels), "seasonal_factors": factors,
        "periods": scores, "fit_failures": failures,
        "tuning_rank_by_mean_pinball": ranking,
        "tuning_comparison_vs_unadjusted_reference": versus_reference,
        "tuning_comparison_within_seasonal": within,
        "bucket_coverage_all_development": bucket_coverage,
        "notes": [
            "Exploratory: the final test was used in Phase 8; claims need data after 2026-07-17.",
            "Ranking uses 2022-2023; 2024 is retrospective because Phase 9A inspected all development data.",
            "Seasonal factors use only trading days strictly before each forecast day.",
            "If fit failures remove any tuning day, common-day ranking and inference are withheld.",
        ],
    }


def _bucket_table(report: dict) -> pd.DataFrame:
    table = pd.DataFrame({"index": range(len(report["bucket_labels"])), "group": report["bucket_labels"]})
    for tag, values in report["bucket_coverage_all_development"].items():
        for label, coverage in values.items():
            table[f"{label}_cov{tag}"] = coverage
    return table


def run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
        data_manifest: Path, root: Path, output_root: Path, *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, fit_path, sample_path, data_manifest,
                          root, output_root)
    path = output_root / timeframe / "report.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(report)):
            raise ValueError("Existing Phase 9D report differs from input checkpoints")
    elif not check_only:
        _atomic_json(path, report)
        table_path = output_root / timeframe / "bucket_coverage.csv"
        temporary = table_path.with_name(table_path.name + ".tmp")
        _bucket_table(report).to_csv(temporary, index=False, float_format="%.8g", lineterminator="\n")
        os.replace(temporary, table_path)
    print(f"{report['signature']['run_id']}: verified {report['days']} days; "
          f"report {'checked' if check_only else 'ready'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9d_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/phase9d_v1"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
        args.root, args.output_root, check_only=args.check_only)


if __name__ == "__main__":
    main()
