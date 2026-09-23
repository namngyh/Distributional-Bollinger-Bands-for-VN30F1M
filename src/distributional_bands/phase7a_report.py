"""Read-only comparison of completed Phase 7A trials and the verified 60m anchor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baseline import _atomic_json, _normalized_text_sha256
from .data import sha256_file
from .distributions import FitConfig
from .phase7a import Phase7AConfig, _signature as trial_signature
from .selection import SelectionConfig, _bootstrap, _independence


def _read_days(directory: Path, expected_signature: dict | None = None,
               expected_count: int | None = None) -> tuple[dict, list[dict]]:
    state = json.loads((directory / "latest.json").read_text(encoding="utf-8"))
    if not state["complete"] or (expected_signature is not None and state["signature"] != expected_signature):
        raise ValueError(f"Incomplete or incompatible input run: {directory}")
    days = sorted(state["daily_sha256"], key=int)
    if (not days or state.get("completed_days", len(days)) != len(days)
            or (expected_count is not None and len(days) != expected_count)):
        raise ValueError(f"Unexpected completed development day count: {directory}")
    records = []
    for day in days:
        path = directory / "daily" / f"{day}.json"
        if sha256_file(path) != state["daily_sha256"][day]:
            raise ValueError(f"Daily checksum mismatch: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["day"] != int(day):
            raise ValueError(f"Daily date mismatch: {path}")
        records.append(record)
    return state, records


def _model_stats(rows: list[dict], key: str, coverages: tuple[float, ...]) -> dict:
    available = [r for r in rows if key in r["models"]]
    n = sum(r["n"] for r in available)
    if not n:
        return {"n": 0}
    result = {"n": n, "days": len(available),
              "mean_pinball_equal_weight": sum(r["models"][key]["score_sum"] for r in available) / n,
              "levels": {}}
    for level in coverages:
        tag = str(round(level * 1000))
        values = [r["models"][key]["levels"][tag] for r in available]
        lower = sum(x["lower_exceed"] for x in values)
        upper = sum(x["upper_exceed"] for x in values)
        low_trans = [sum(x["lower_transitions"][i] for x in values) for i in range(4)]
        high_trans = [sum(x["upper_transitions"][i] for x in values) for i in range(4)]
        result["levels"][tag] = {
            "nominal_coverage": level,
            "observed_coverage": 1 - (lower + upper) / n,
            "lower_exceedance": lower / n,
            "upper_exceedance": upper / n,
            "mean_width_log_return": sum(x["width_sum"] for x in values) / n,
            "mean_pinball": sum(x["pinball_sum"] for x in values) / n,
            "lower_independence": _independence(low_trans),
            "upper_independence": _independence(high_trans),
        }
    if "pit_histogram" in available[0]["models"][key]:
        bins = len(available[0]["models"][key]["pit_histogram"])
        result["pit"] = {
            "histogram": [sum(r["models"][key]["pit_histogram"][i] for r in available)
                          for i in range(bins)],
            "mean": sum(r["models"][key]["pit_sum"] for r in available) / n,
            "expected_per_bin": n / bins,
        }
    return result


def build_report(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
                 data_manifest: Path, selection_dir: Path, output_root: Path) -> dict:
    config = Phase7AConfig.from_json(config_path)
    if timeframe not in config.shortlist:
        raise ValueError("Unknown timeframe")
    mixture = config.shortlist[timeframe]
    selection_report = json.loads((selection_dir / "report.json").read_text(encoding="utf-8"))
    if not selection_report["complete"]:
        raise ValueError("Selection anchor report is incomplete")
    anchor_state, anchor_days = _read_days(selection_dir, expected_count=selection_report["days"])
    if (selection_report["signature"] != anchor_state["signature"]
            or selection_report["first_day"] != anchor_days[0]["day"]
            or selection_report["last_day"] != anchor_days[-1]["day"]
            or anchor_days[0]["day"] < config.prediction_start
            or anchor_days[-1]["day"] > config.last_development_date):
        raise ValueError("Selection report does not match anchor checkpoint")
    fit = FitConfig.from_json(fit_path)
    if mixture not in fit.models:
        raise ValueError("Shortlisted mixture absent from fit config")
    trial_rows = {}
    signatures = {}
    failures = {}
    for half_life in (30, 120):
        directory = output_root / timeframe / f"hl{half_life}"
        signature = trial_signature(config_path, fit_path, sample_path, data_manifest,
                                    timeframe, half_life, config)
        state, rows = _read_days(directory, signature, expected_count=len(anchor_days))
        manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if manifest["signature"] != signature or metrics["signature"] != signature or not metrics["complete"]:
            raise ValueError(f"Trial manifest/metrics mismatch: {directory}")
        if (metrics["completed_days"] != len(rows)
                or metrics["fit_attempts"] != len(state["fit_history"])
                or metrics["fit_failures"] != sum(x["status"] == "failed" for x in state["fit_history"])):
            raise ValueError(f"Trial metrics disagree with checkpoint: {directory}")
        failures[str(half_life)] = metrics["fit_failures"]
        trial_rows[half_life] = rows
        signatures[str(half_life)] = sha256_file(directory / "latest.json")
    combined = []
    labels = [f"{model}_hl{half_life}" for half_life in config.half_lives_minutes
              for model in (config.baseline_model, mixture)]
    for index, anchor in enumerate(anchor_days):
        day = anchor["day"]
        entry = {"day": day, "n": anchor["n"], "paired": True, "models": {}}
        for half_life in config.half_lives_minutes:
            row = anchor if half_life == 60 else trial_rows[half_life][index]
            if row["day"] != day or row["n"] != anchor["n"]:
                raise ValueError("Trial and anchor trading days/bars are misaligned")
            for model in (config.baseline_model, mixture):
                if model not in row["models"]:
                    if model == config.baseline_model:
                        raise ValueError(f"Missing empirical baseline on {day}")
                    entry["paired"] = False
                    continue
                entry["models"][f"{model}_hl{half_life}"] = row["models"][model]
        combined.append(entry)
    periods = {
        "tuning_2022_2023": [r for r in combined if r["day"] <= config.tuning_end_date],
        "retrospective_2024": [r for r in combined if r["day"] > config.tuning_end_date],
        "all_development": combined,
    }
    scores = {period: {key: _model_stats(rows, key, config.central_coverages)
                       for key in labels} for period, rows in periods.items()}
    ranking = (sorted(labels, key=lambda key: scores["tuning_2022_2023"][key]["mean_pinball_equal_weight"])
               if all(row["paired"] for row in periods["tuning_2022_2023"]) else [])
    bootstrap_config = SelectionConfig(config.experiment_id, config.baseline_model,
                                       config.bootstrap_block_days, config.bootstrap_replicates,
                                       config.bootstrap_seed, 10, config.final_test_start)
    reference = f"{config.baseline_model}_hl60"
    candidates = tuple(key for key in labels if key != reference)
    uncertainty = _bootstrap(periods["tuning_2022_2023"], candidates, reference,
                             bootstrap_config)
    uncertainty["method"] = (f"circular {config.bootstrap_block_days}-trading-day block bootstrap; "
                             "two-sided centered test; Holm across five Phase 7A alternatives")
    signature = {
        "experiment_id": config.experiment_id,
        "run_id": f"{config.experiment_id}-{timeframe}-REPORT",
        "config_sha256": _normalized_text_sha256(config_path),
        "report_code_sha256": _normalized_text_sha256(Path(__file__)),
        "selection_checkpoint_sha256": sha256_file(selection_dir / "latest.json"),
        "selection_report_sha256": sha256_file(selection_dir / "report.json"),
        "trial_checkpoint_sha256": signatures,
    }
    return {
        "signature": signature, "complete": True, "timeframe": timeframe,
        "model_shortlist": [config.baseline_model, mixture],
        "days": len(combined), "first_day": combined[0]["day"],
        "last_day": combined[-1]["day"], "periods": scores,
        "trial_fit_failures": failures,
        "tuning_rank_by_mean_pinball": ranking,
        "tuning_comparison_vs_empirical_hl60": uncertainty,
        "notes": [
            "Tuning ranking uses 2022-2023 only; 2024 is a retrospective stability check, not an untouched holdout.",
            "The model shortlist was informed by all 2022-2024 Phase 6 results; significance is exploratory.",
            "The 60-minute anchor reuses verified Phase 5-6 artifacts. No final-test observations enter fits or scores.",
            "No winner or calibration correction is selected automatically.",
            "If fit failures remove any tuning day, common-day ranking and inference are withheld.",
        ],
    }


def run(timeframe: str, config_path: Path, fit_path: Path, sample_path: Path,
        data_manifest: Path, selection_dir: Path, output_root: Path,
        *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, fit_path, sample_path,
                          data_manifest, selection_dir, output_root)
    path = output_root / timeframe / "report.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != report:
        raise ValueError("Existing Phase 7A report differs from input checkpoints")
    if not check_only and not path.exists():
        _atomic_json(path, report)
    print(f"{report['signature']['run_id']}: verified {report['days']} days; "
          f"report {'checked' if check_only else 'ready'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase7a_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/phase7a_v1"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.timeframe, args.config, args.fit_config, args.input, args.data_manifest,
        args.selection_dir, args.output_root, check_only=args.check_only)


if __name__ == "__main__":
    main()
