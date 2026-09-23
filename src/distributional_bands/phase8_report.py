"""Read-only recomputable report for the frozen Phase 8 final test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baseline import _atomic_json, _normalized_text_sha256, load_samples
from .data import sha256_file
from .phase7a_report import _model_stats
from .phase8 import Phase8Config, _initial_state, _lineage, _load_state, _signature, _summary
from .selection import SelectionConfig, _bootstrap


def build_report(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
                 data_manifest: Path, phase7a_dir: Path, phase7a_report: Path,
                 phase7b_dir: Path, phase7b_report: Path, output_dir: Path) -> dict:
    config = Phase8Config.from_json(config_path)
    a_state, _, _ = _lineage(config, timeframe, phase7a_dir, phase7a_report,
                             phase7b_dir, phase7b_report)
    signature = _signature(config_path, fit_path, sample_path, data_manifest,
                           timeframe, phase7a_dir, phase7b_dir, phase7b_report)
    prior_fit = a_state["fit_history"][-1] if timeframe == "5m" else None
    initial = _initial_state(signature,
                             {"status": "success", "fit": prior_fit["fit"],
                              "quantiles": prior_fit["quantiles"]} if prior_fit else None,
                             prior_fit["refit_day"] if prior_fit else None)
    state_path = output_dir / "latest.json"
    samples = load_samples(sample_path, timeframe, config.final_test_end)
    days = sorted(int(day) for day in samples.loc[
        samples["TRADING_DATE"] >= config.final_test_start, "TRADING_DATE"].unique())
    state = _load_state(output_dir, signature, days, initial, create=False)
    if (not state["complete"] or not days or days[0] < config.final_test_start
            or days[-1] != config.final_test_end):
        raise ValueError("Phase 8 final test must be complete before reporting")
    summary = _summary(state, days, output_dir, config, timeframe)
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    if metrics != summary:
        raise ValueError("Phase 8 metrics differ from checkpoint")
    rows = [json.loads((output_dir / "daily" / f"{day}.json").read_text(encoding="utf-8"))
            for day in days]
    selected = config.locked_models[timeframe]
    labels = (selected,) if timeframe == "1m" else ("empirical_ewma", selected)
    if any(row["day"] != day or set(row["models"]) != set(labels) or row["n"] <= 0
           for row, day in zip(rows, days)):
        raise ValueError("Phase 8 daily model alignment failed")
    by_period = {"all_final": rows,
                 "calendar_2025": [row for row in rows if row["day"] < 20260101],
                 "calendar_2026_to_july_17": [row for row in rows if row["day"] >= 20260101]}
    scores = {period: {label: _model_stats(part, label, config.central_coverages)
                       for label in labels} for period, part in by_period.items()}
    comparison = None
    if timeframe == "5m":
        bootstrap_config = SelectionConfig(config.experiment_id, "empirical_ewma",
                                           config.bootstrap_block_days,
                                           config.bootstrap_replicates,
                                           config.bootstrap_seed, 10, config.final_test_start)
        comparison = _bootstrap([dict(row, paired=True) for row in rows],
                                (selected,), "empirical_ewma", bootstrap_config)
        comparison["method"] = "frozen selected-minus-Empirical; circular five-day block bootstrap"
    return {"signature": {
                "run_id": f"PHASE8-V1-{timeframe}-REPORT",
                "config_sha256": _normalized_text_sha256(config_path),
                "report_code_sha256": _normalized_text_sha256(Path(__file__)),
                "checkpoint_sha256": sha256_file(state_path),
                "phase7b_report_sha256": sha256_file(phase7b_report)},
            "complete": True, "timeframe": timeframe,
            "selected_model": selected, "first_day": days[0], "last_day": days[-1],
            "days": len(days), "bars": summary["scored_bars"],
            "fit_attempts": summary["fit_attempts"],
            "fit_failures": summary["fit_failures"],
            "periods": scores, "selected_vs_empirical": comparison,
            "notes": [
                "Model and parameters were locked before opening 2025–2026 final test.",
                "Final test is evaluated once; do not retune using these outcomes.",
                "2025 and 2026 partitions are descriptive, not additional holdouts.",
                "PIT calibration uses only outcomes from strictly prior trading dates.",
                "Source timezone and contract-roll adjustment remain unverified.",
            ]}


def run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
        data_manifest: Path, phase7a_dir: Path, phase7a_report: Path,
        phase7b_dir: Path, phase7b_report: Path, output_dir: Path,
        *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, fit_path, sample_path, data_manifest,
                          phase7a_dir, phase7a_report, phase7b_dir, phase7b_report,
                          output_dir)
    path = output_dir / "report.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != report:
        raise ValueError("Existing Phase 8 report differs from checkpoint")
    if not check_only and not path.exists():
        _atomic_json(path, report)
    print(f"{report['signature']['run_id']}: verified {report['days']} final days; "
          f"report {'checked' if check_only else 'ready'}")
    return report


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
    args = parser.parse_args()
    run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
        args.phase7a_dir, args.phase7a_report, args.phase7b_dir, args.phase7b_report,
        args.output_dir, check_only=args.check_only)


if __name__ == "__main__":
    main()
