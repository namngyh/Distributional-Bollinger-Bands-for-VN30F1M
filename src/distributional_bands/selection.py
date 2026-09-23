"""Checkpointed, development-only diagnostics for completed band forecasts.

No fitting or model selection is performed here. A report is descriptive evidence
for a subsequent, explicit decision before the untouched final test is opened.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import chi2

from .baseline import (_atomic_json, _normalized_text_sha256,
                       _signature as baseline_signature,
                       _summary as baseline_summary)
from .data import sha256_file
from .distributions import FitConfig, FittedDistribution
from .walk_forward import (WalkForwardConfig, _signature as wf_signature,
                           _summary as wf_summary, _git_commit)

BASELINES = ("normal_ewma", "normal_rolling", "empirical_ewma")
KEY_COLUMNS = ("TRADING_DATE", "session", "timestamp", "available_at",
               "target_timestamp", "CLOSE_PX", "target_log_return")


@dataclass(frozen=True)
class SelectionConfig:
    experiment_id: str
    reference_model: str
    block_days: int
    bootstrap_replicates: int
    bootstrap_seed: int
    pit_bins: int
    final_test_start: int

    @classmethod
    def from_json(cls, path: Path) -> "SelectionConfig":
        value = cls(**json.loads(path.read_text(encoding="utf-8")))
        if not value.experiment_id or value.reference_model not in BASELINES:
            raise ValueError("Invalid selection experiment or reference model")
        if (value.block_days < 1 or value.bootstrap_replicates < 100
                or value.bootstrap_seed < 0 or value.pit_bins < 2
                or value.final_test_start <= 20241231):
            raise ValueError("Invalid selection diagnostics policy")
        return value


def _load_verified_inputs(timeframe: str, baseline_dir: Path, wf_dir: Path,
                          baseline_config: Path, wf_config: Path, fit_config: Path,
                          sample: Path, data_manifest: Path) -> tuple[dict, dict, list[int], tuple[float, ...], tuple[str, ...]]:
    from .baseline import BaselineConfig

    bc = BaselineConfig.from_json(baseline_config)
    wc = WalkForwardConfig.from_json(wf_config)
    fc = FitConfig.from_json(fit_config)
    if (bc.central_coverages != wc.central_coverages
            or bc.prediction_start != wc.prediction_start
            or bc.last_development_date != wc.last_development_date
            or bc.last_development_date >= 20250101):
        raise ValueError("Baseline and distribution development policies differ")
    b_sig = baseline_signature(baseline_config, sample, data_manifest, timeframe, bc)
    w_sig = wf_signature(wf_config, fit_config, sample, data_manifest, timeframe, wc, fc)
    states = []
    for directory, signature, kind in ((baseline_dir, b_sig, "baseline"),
                                       (wf_dir, w_sig, "distribution")):
        manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
        state = json.loads((directory / "latest.json").read_text(encoding="utf-8"))
        summary = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if manifest["signature"] != signature or state["signature"] != signature or not state["complete"]:
            raise ValueError(f"{kind} run is incomplete or has a signature mismatch")
        expected = baseline_summary(state) if kind == "baseline" else wf_summary(state, fc, state["completed_days"])
        if summary != expected:
            raise ValueError(f"{kind} metrics differ from checkpoint")
        states.append(state)
    baseline, distribution = states
    days = sorted(int(day) for day in distribution["prediction_sha256"])
    if (days != sorted(int(day) for day in baseline["prediction_sha256"])
            or len(days) != distribution["completed_days"]
            or any(not wc.prediction_start <= day <= wc.last_development_date for day in days)):
        raise ValueError("Development prediction dates are incomplete or misaligned")
    for directory, state in ((baseline_dir, baseline), (wf_dir, distribution)):
        actual = {path.stem for path in (directory / "predictions").glob("*.csv")}
        if actual != set(state["prediction_sha256"]):
            raise ValueError(f"Unexpected or missing prediction file in {directory}")
    return baseline, distribution, days, wc.central_coverages, fc.models


def _fit_lookup(history: list[dict], models: tuple[str, ...]) -> dict[str, list[dict]]:
    result = {model: [] for model in models}
    for item in history:
        result[item["model"]].append(item)
    for model in models:
        result[model].sort(key=lambda item: item["refit_day"])
    return result


def _recent_fit(items: list[dict], day: int) -> FittedDistribution | None:
    relevant = next((item for item in reversed(items) if item["refit_day"] <= day), None)
    if relevant is None or relevant["status"] != "success":
        return None
    return FittedDistribution(**relevant["fit"])


def _transitions(event: np.ndarray, session: np.ndarray) -> list[int]:
    if len(event) < 2:
        return [0, 0, 0, 0]
    same = session[1:] == session[:-1]
    code = event[:-1].astype(int) * 2 + event[1:].astype(int)
    return np.bincount(code[same], minlength=4).astype(int).tolist()


def _day_record(day: int, baseline_csv: Path, wf_csv: Path, levels: tuple[float, ...],
                models: tuple[str, ...], fit_lookup: dict[str, list[dict]],
                pit_bins: int) -> dict:
    all_models = BASELINES + models
    tags = [str(round(level * 1000)) for level in levels]
    columns = list(KEY_COLUMNS) + ["sigma_ewma"]
    b_cols = columns + [f"{model}_q_{side}_{tag}" for model in BASELINES
                        for tag in tags for side in ("low", "high")]
    w_cols = columns + [f"{model}_q_{side}_{tag}" for model in models
                        for tag in tags for side in ("low", "high")]
    b = pd.read_csv(baseline_csv, usecols=lambda name: name in b_cols)
    w = pd.read_csv(wf_csv, usecols=lambda name: name in w_cols)
    if len(b) != len(w) or not len(w):
        raise ValueError(f"Prediction row count mismatch on {day}")
    for name in KEY_COLUMNS + ("sigma_ewma",):
        if name in ("CLOSE_PX", "target_log_return", "sigma_ewma"):
            if not np.allclose(b[name].to_numpy(), w[name].to_numpy(), rtol=0, atol=1e-12):
                raise ValueError(f"Prediction alignment mismatch for {name} on {day}")
        elif not b[name].equals(w[name]):
            raise ValueError(f"Prediction alignment mismatch for {name} on {day}")
    if not (w["TRADING_DATE"] == day).all():
        raise ValueError("Daily file includes a different trading date")
    actual = w["target_log_return"].to_numpy(dtype=float)
    sigma = w["sigma_ewma"].to_numpy(dtype=float)
    session = w["session"].to_numpy()
    if not np.isfinite(actual).all() or not np.isfinite(sigma).all() or (sigma <= 0).any():
        raise ValueError("Nonfinite targets or predictive volatility")
    record = {"day": day, "n": len(w), "models": {}, "paired": True}
    for model in all_models:
        frame = b if model in BASELINES else w
        wanted = [f"{model}_q_{side}_{tag}" for tag in tags for side in ("low", "high")]
        present = [name in frame.columns for name in wanted]
        if any(present) and not all(present):
            raise ValueError(f"Partial quantile columns for {model} on {day}")
        if not all(present):
            record["paired"] = False
            continue
        score = np.zeros(len(w), dtype=float)
        by_level = {}
        for level, tag in zip(levels, tags):
            low = frame[f"{model}_q_low_{tag}"].to_numpy(dtype=float)
            high = frame[f"{model}_q_high_{tag}"].to_numpy(dtype=float)
            if not np.isfinite(low).all() or not np.isfinite(high).all() or (low >= high).any():
                raise ValueError(f"Invalid band for {model}:{tag} on {day}")
            alpha = (1 - level) / 2
            lower = (alpha - (actual < low).astype(float)) * (actual - low)
            upper = (1 - alpha - (actual < high).astype(float)) * (actual - high)
            loss = (lower + upper) / 2
            score += loss / len(levels)
            below = actual < low
            above = actual > high
            by_level[tag] = {
                "n": len(w), "pinball_sum": float(loss.sum()),
                "width_sum": float((high - low).sum()),
                "lower_exceed": int(below.sum()), "upper_exceed": int(above.sum()),
                "lower_transitions": _transitions(below, session),
                "upper_transitions": _transitions(above, session),
            }
        result = {"score_sum": float(score.sum()), "levels": by_level}
        if model in models:
            fitted = _recent_fit(fit_lookup[model], day)
            if fitted is None:
                raise ValueError(f"Forecast exists without successful fit: {model} on {day}")
            pit = np.asarray(fitted.cdf(actual / sigma), dtype=float)
            if not np.isfinite(pit).all() or (pit < 0).any() or (pit > 1).any():
                raise ValueError(f"Invalid PIT for {model} on {day}")
            result["pit_histogram"] = np.histogram(pit, bins=np.linspace(0, 1, pit_bins + 1))[0].tolist()
            result["pit_sum"] = float(pit.sum())
        record["models"][model] = result
    return record


def _independence(counts: list[int]) -> dict:
    n00, n01, n10, n11 = counts
    table = np.array([[n00, n01], [n10, n11]], dtype=float)
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / max(table.sum(), 1)
    if (expected < 5).any():
        return {"transitions": counts, "p_value": None, "note": "expected cell count below five"}
    statistic = float(2 * np.sum(table[table > 0] * np.log(table[table > 0] / expected[table > 0])))
    return {"transitions": counts, "lr_statistic": statistic,
            "p_value": float(chi2.sf(statistic, 1))}


def _bootstrap(records: list[dict], models: tuple[str, ...], reference: str,
               config: SelectionConfig) -> dict:
    paired = [r for r in records if r["paired"]]
    if len(paired) != len(records):
        return {"paired_days": len(paired), "comparisons": {},
                "note": "some days lack all candidates; inference is withheld until a common-day policy is approved"}
    if len(paired) < 2 * config.block_days:
        return {"paired_days": len(paired), "comparisons": {}, "note": "insufficient paired days"}
    n = np.array([r["n"] for r in paired], dtype=float)
    diff = np.array([[r["models"][model]["score_sum"] - r["models"][reference]["score_sum"]
                      for model in models] for r in paired], dtype=float)
    observed = diff.sum(axis=0) / n.sum()
    rng = np.random.default_rng(config.bootstrap_seed)
    reps = np.empty((config.bootstrap_replicates, len(models)), dtype=float)
    blocks = math.ceil(len(paired) / config.block_days)
    offsets = np.arange(config.block_days)
    for i in range(config.bootstrap_replicates):
        starts = rng.integers(0, len(paired), size=blocks)
        indices = ((starts[:, None] + offsets) % len(paired)).reshape(-1)[:len(paired)]
        reps[i] = diff[indices].sum(axis=0) / n[indices].sum()
    p = (1 + (np.abs(reps - observed) >= np.abs(observed)).sum(axis=0)) / (config.bootstrap_replicates + 1)
    order = np.argsort(p)
    adjusted = np.empty(len(models))
    current = 0.0
    for rank, index in enumerate(order):
        current = max(current, min(1.0, float(p[index]) * (len(models) - rank)))
        adjusted[index] = current
    return {"paired_days": len(paired), "paired_bars": int(n.sum()),
            "method": f"circular {config.block_days}-trading-day block bootstrap; two-sided centered test; Holm across distribution candidates",
            "bootstrap_replicates": config.bootstrap_replicates,
            "bootstrap_seed": config.bootstrap_seed,
            "comparisons": {model: {
                "mean_loss_difference_model_minus_reference": float(observed[j]),
                "ci95_unadjusted": np.quantile(reps[:, j], [0.025, 0.975]).tolist(),
                "p_two_sided": float(p[j]), "p_holm": float(adjusted[j]),
            } for j, model in enumerate(models)}}


def _report(records: list[dict], levels: tuple[float, ...], models: tuple[str, ...],
            config: SelectionConfig, signature: dict, fit_failures: dict) -> dict:
    rows = {}
    all_models = BASELINES + models
    for model in all_models:
        available = [r for r in records if model in r["models"]]
        n = sum(r["n"] for r in available)
        if not n:
            rows[model] = {"n": 0}
            continue
        result = {"n": n, "mean_pinball_equal_weight": sum(r["models"][model]["score_sum"]
                                                         for r in available) / n,
                  "year_scores": {}}
        for year in sorted({r["day"] // 10000 for r in available}):
            subset = [r for r in available if r["day"] // 10000 == year]
            result["year_scores"][str(year)] = sum(r["models"][model]["score_sum"]
                                                      for r in subset) / sum(r["n"] for r in subset)
        result["levels"] = {}
        for level in levels:
            tag = str(round(level * 1000))
            groups = [r["models"][model]["levels"][tag] for r in available]
            lower = sum(x["lower_exceed"] for x in groups)
            upper = sum(x["upper_exceed"] for x in groups)
            low_trans = [sum(x["lower_transitions"][j] for x in groups) for j in range(4)]
            high_trans = [sum(x["upper_transitions"][j] for x in groups) for j in range(4)]
            result["levels"][tag] = {
                "nominal_coverage": level, "observed_coverage": 1 - (lower + upper) / n,
                "lower_exceedance": lower / n, "upper_exceedance": upper / n,
                "mean_interval_width_log_return": sum(x["width_sum"] for x in groups) / n,
                "mean_pinball": sum(x["pinball_sum"] for x in groups) / n,
                "lower_independence": _independence(low_trans),
                "upper_independence": _independence(high_trans),
            }
        if model in models:
            hist = [sum(r["models"][model]["pit_histogram"][j] for r in available)
                    for j in range(config.pit_bins)]
            result["pit"] = {"histogram": hist, "mean": sum(r["models"][model]["pit_sum"]
                                                               for r in available) / n,
                             "expected_per_bin": n / config.pit_bins}
        rows[model] = result
    return {"signature": signature, "complete": True,
            "reference_model": config.reference_model,
            "central_coverages": list(levels), "days": len(records),
            "first_day": records[0]["day"], "last_day": records[-1]["day"],
            "models": rows, "fit_failures": fit_failures,
            "block_bootstrap": _bootstrap(records, models, config.reference_model, config),
            "notes": ["Development OOS only; final test is excluded.",
                      "Ranking, PIT and exceedance tests are diagnostics, not automatic winner selection.",
                      "Intraday transitions exclude session boundaries; asymptotic p-values omitted when expected counts are small.",
                      "Bootstrap uncertainty depends on the predeclared day-block length; multiple comparisons use Holm correction."]}


def run(timeframe: str, config_path: Path, baseline_config: Path, wf_config: Path,
        fit_config: Path, sample: Path, data_manifest: Path, baseline_dir: Path,
        wf_dir: Path, output_dir: Path, *, check_only: bool = False,
        max_days: int | None = None) -> dict:
    if timeframe not in ("1m", "5m") or (max_days is not None and max_days <= 0):
        raise ValueError("Invalid timeframe or max-days")
    config = SelectionConfig.from_json(config_path)
    baseline, distribution, days, levels, models = _load_verified_inputs(
        timeframe, baseline_dir, wf_dir, baseline_config, wf_config, fit_config,
        sample, data_manifest)
    if max(days) >= config.final_test_start:
        raise ValueError("Final test dates must remain excluded")
    signature = {"experiment_id": config.experiment_id,
                 "run_id": f"{config.experiment_id}-{timeframe}",
                 "selection_config_sha256": _normalized_text_sha256(config_path),
                 "selection_code_sha256": _normalized_text_sha256(Path(__file__)),
                 "baseline_signature": baseline["signature"],
                 "distribution_signature": distribution["signature"],
                 "baseline_checkpoint_sha256": sha256_file(baseline_dir / "latest.json"),
                 "distribution_checkpoint_sha256": sha256_file(wf_dir / "latest.json")}
    latest = output_dir / "latest.json"
    manifest_path = output_dir / "run_manifest.json"
    if latest.exists():
        state = json.loads(latest.read_text(encoding="utf-8"))
        if state["signature"] != signature:
            raise ValueError("Selection checkpoint signature mismatch")
        if (not manifest_path.exists()
                or json.loads(manifest_path.read_text(encoding="utf-8"))["signature"] != signature):
            raise ValueError("Selection run manifest is missing or mismatched")
    else:
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError("Nonempty selection output has no checkpoint")
        state = {"signature": signature, "daily_sha256": {}, "complete": False}
    if (not set(state["daily_sha256"]).issubset({str(day) for day in days})
            or (state["complete"] and len(state["daily_sha256"]) != len(days))):
        raise ValueError("Selection checkpoint day progress is inconsistent")
    if check_only:
        for day, expected in state["daily_sha256"].items():
            daily = output_dir / "daily" / f"{day}.json"
            if not daily.exists() or sha256_file(daily) != expected:
                raise ValueError(f"Selection daily artifact missing or corrupt: {day}")
        print(f"{signature['run_id']}: inputs and checkpoint checked; "
              f"{len(state['daily_sha256'])}/{len(days)} days")
        return {"completed_days": len(state["daily_sha256"]), "total_days": len(days)}
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = output_dir / "daily"
    daily_dir.mkdir(exist_ok=True)
    if not latest.exists():
        _atomic_json(manifest_path, {
            "signature": signature,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "bootstrap_seed": config.bootstrap_seed,
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "numpy": np.__version__, "pandas": pd.__version__,
                            "scipy": scipy.__version__},
            "checkpoint_policy": "atomic daily JSON and latest.json after each development day",
            "output_path": str(output_dir.resolve()),
        })
        _atomic_json(latest, state)
    fit_lookup = _fit_lookup(distribution["fit_history"], models)
    processed = 0
    records = []
    for day in days:
        key = str(day)
        daily = daily_dir / f"{day}.json"
        b_path = baseline_dir / "predictions" / f"{day}.csv"
        w_path = wf_dir / "predictions" / f"{day}.csv"
        for path, parent in ((b_path, baseline), (w_path, distribution)):
            if sha256_file(path) != parent["prediction_sha256"][key]:
                raise ValueError(f"Source prediction hash mismatch: {path}")
        if key in state["daily_sha256"]:
            if not daily.exists() or sha256_file(daily) != state["daily_sha256"][key]:
                raise ValueError(f"Selection daily artifact missing or corrupt: {day}")
            record = json.loads(daily.read_text(encoding="utf-8"))
        else:
            record = _day_record(day, b_path, w_path, levels, models, fit_lookup, config.pit_bins)
            if daily.exists():
                if json.loads(daily.read_text(encoding="utf-8")) != record:
                    raise ValueError(f"Orphan daily artifact differs on {day}")
            else:
                _atomic_json(daily, record)
            state["daily_sha256"][key] = sha256_file(daily)
            _atomic_json(latest, state)
            processed += 1
            if processed % 20 == 0 or max_days is not None:
                print(f"{signature['run_id']}: {len(state['daily_sha256'])}/{len(days)} days", flush=True)
        if record["day"] != day:
            raise ValueError(f"Daily record date mismatch: {day}")
        records.append(record)
        if max_days is not None and processed >= max_days:
            return {"completed_days": len(state["daily_sha256"]), "total_days": len(days)}
    report = _report(records, levels, models, config, signature,
                     json.loads((wf_dir / "metrics.json").read_text(encoding="utf-8"))["fit_failures"])
    report_path = output_dir / "report.json"
    if report_path.exists() and json.loads(report_path.read_text(encoding="utf-8")) != report:
        raise ValueError("Existing selection report differs from recomputed results")
    if not report_path.exists():
        _atomic_json(report_path, report)
    state["complete"] = True
    _atomic_json(latest, state)
    print(f"{signature['run_id']}: complete; {len(days)} development days analyzed")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/selection_v1.json"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_v1.json"))
    parser.add_argument("--wf-config", type=Path, default=Path("configs/walk_forward_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--wf-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--max-days", type=int)
    args = parser.parse_args()
    run(args.timeframe, args.config, args.baseline_config, args.wf_config,
        args.fit_config, args.sample, args.data_manifest, args.baseline_dir,
        args.wf_dir, args.output_dir, check_only=args.check_only, max_days=args.max_days)


if __name__ == "__main__":
    main()
