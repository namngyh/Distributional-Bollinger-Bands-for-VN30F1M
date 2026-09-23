"""Paired development-OOS diagnostics for past-only Phase 7B PIT calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baseline import _atomic_json, _normalized_text_sha256
from .data import sha256_file
from .phase7a_report import _model_stats
from .phase7b import Phase7BConfig, _load_state, _signature, _source
from .selection import SelectionConfig, _bootstrap


def build_report(timeframe: str, config_path: Path, source_dir: Path,
                 source_report: Path, output_dir: Path) -> dict:
    config = Phase7BConfig.from_json(config_path)
    source_state, days = _source(config, timeframe, source_dir, source_report)
    signature = _signature(config_path, config, timeframe, source_dir, source_report)
    state = _load_state(output_dir, signature, days, config.warmup_days,
                        config.bootstrap_seed, create=False)
    if not state["complete"] or state["completed_days"] != len(days):
        raise ValueError("Phase 7B trial must be complete before reporting")
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    if (metrics["signature"] != signature or not metrics["complete"]
            or metrics["calibrated_days"] != len(days) - config.warmup_days):
        raise ValueError("Phase 7B metrics differ from completed checkpoint")
    mixture = config.shortlist[timeframe]
    calibrated = f"{mixture}_pit_calibrated"
    baseline_label = f"{config.baseline_model}_hl30"
    mixture_label = f"{mixture}_hl30"
    calibrated_label = f"{calibrated}_hl30"
    rows = []
    for day in days[config.warmup_days:]:
        source_path = source_dir / "daily" / f"{day}.json"
        if sha256_file(source_path) != source_state["daily_sha256"][str(day)]:
            raise ValueError(f"Corrupt Phase 7A daily source for {day}")
        source = json.loads(source_path.read_text(encoding="utf-8"))
        adjusted = json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
        if (source["day"] != day or adjusted["day"] != day or not adjusted["calibrated"]
                or source["n"] != adjusted["n"]
                or any(model not in source["models"] for model in (config.baseline_model, mixture))
                or calibrated not in adjusted["models"]):
            raise ValueError(f"Phase 7A/7B daily alignment failed for {day}")
        rows.append({"day": day, "n": source["n"], "paired": True, "models": {
            baseline_label: source["models"][config.baseline_model],
            mixture_label: source["models"][mixture],
            calibrated_label: adjusted["models"][calibrated],
        }})
    periods = {
        "tuning_2022_2023": [row for row in rows if row["day"] <= config.tuning_end_date],
        "retrospective_2024": [row for row in rows if row["day"] > config.tuning_end_date],
        "all_scored_development": rows,
    }
    labels = (baseline_label, mixture_label, calibrated_label)
    scores = {period: {label: _model_stats(part, label, config.central_coverages)
                       for label in labels} for period, part in periods.items()}
    ranking = sorted(labels, key=lambda label:
                     scores["tuning_2022_2023"][label]["mean_pinball_equal_weight"])
    bootstrap_config = SelectionConfig(config.experiment_id, config.baseline_model,
                                       config.bootstrap_block_days, config.bootstrap_replicates,
                                       config.bootstrap_seed, 10, config.final_test_start)
    versus_empirical = _bootstrap(periods["tuning_2022_2023"],
                                  (mixture_label, calibrated_label), baseline_label,
                                  bootstrap_config)
    versus_empirical["method"] = ("circular five-trading-day block bootstrap; "
                                   "Holm correction across two Mixture comparisons")
    versus_raw = _bootstrap(periods["tuning_2022_2023"],
                            (calibrated_label,), mixture_label, bootstrap_config)
    versus_raw["method"] = ("exploratory direct calibrated-minus-raw comparison; "
                             "unadjusted day-block bootstrap")
    report_signature = {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}-REPORT",
        "config_sha256": _normalized_text_sha256(config_path),
        "report_code_sha256": _normalized_text_sha256(Path(__file__)),
        "phase7a_checkpoint_sha256": sha256_file(source_dir / "latest.json"),
        "phase7a_report_sha256": sha256_file(source_report),
        "phase7b_checkpoint_sha256": sha256_file(output_dir / "latest.json"),
    }
    return {
        "signature": report_signature, "complete": True, "timeframe": timeframe,
        "warmup_days": config.warmup_days, "scored_days": len(rows),
        "first_scored_day": rows[0]["day"], "last_scored_day": rows[-1]["day"],
        "periods": scores, "tuning_rank_by_mean_pinball": ranking,
        "tuning_comparison_vs_empirical_hl30": versus_empirical,
        "tuning_calibrated_vs_raw_mixture": versus_raw,
        "notes": [
            "All three candidates use identical bars after a 60-day past-PIT warmup.",
            "Calibration uses only strictly prior development days; no 2025+ observations are read.",
            "2024 is retrospective stability, not a fresh holdout; Phase 7A selection used 2022-2024.",
            "Empirical-CDF calibrated PIT is discrete and is only an approximate diagnostic.",
            "Serial dependence means rolling PIT calibration does not guarantee coverage.",
            "No model or calibration correction is selected automatically.",
        ],
    }


def run(timeframe: str, config_path: Path, source_dir: Path,
        source_report: Path, output_dir: Path, *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, source_dir, source_report, output_dir)
    path = output_dir / "report.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != report:
        raise ValueError("Existing Phase 7B report differs from input checkpoints")
    if not check_only and not path.exists():
        _atomic_json(path, report)
    print(f"{report['signature']['run_id']}: verified {report['scored_days']} scored days; "
          f"report {'checked' if check_only else 'ready'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase7b_v1.json"))
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.timeframe, args.config, args.source_dir, args.source_report,
        args.output_dir, check_only=args.check_only)


if __name__ == "__main__":
    main()
