"""Exploratory Phase 9A diagnostics of standardized residuals z_t on development data.

Read-only: verifies every source prediction file against its completed checkpoint,
never reads final-test dates, and writes a report plus small CSV tables for figures.
Seasonal and regime groupings are estimated in-sample and are descriptive only.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2, kurtosis, skew

from .baseline import _atomic_json, _normalized_text_sha256
from .data import sha256_file

SESSION_CODES = {"morning": 0, "afternoon": 1}


@dataclass(frozen=True)
class Phase9AConfig:
    experiment_id: str
    development_first_date: int
    development_last_date: int
    final_test_start: int
    bar_minutes: dict[str, int]
    acf_max_lag: dict[str, int]
    bucket_minutes: int
    sigma_groups: int
    lagged_abs_z_edges: tuple[float, ...]
    central_coverages: tuple[float, ...]
    sources: dict[str, dict]

    @classmethod
    def from_json(cls, path: Path) -> "Phase9AConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = cls(
            experiment_id=str(raw["experiment_id"]),
            development_first_date=int(raw["development_first_date"]),
            development_last_date=int(raw["development_last_date"]),
            final_test_start=int(raw["final_test_start"]),
            bar_minutes={k: int(v) for k, v in raw["bar_minutes"].items()},
            acf_max_lag={k: int(v) for k, v in raw["acf_max_lag"].items()},
            bucket_minutes=int(raw["bucket_minutes"]),
            sigma_groups=int(raw["sigma_groups"]),
            lagged_abs_z_edges=tuple(float(v) for v in raw["lagged_abs_z_edges"]),
            central_coverages=tuple(float(v) for v in raw["central_coverages"]),
            sources=raw["sources"],
        )
        if config.development_last_date >= config.final_test_start:
            raise ValueError("Phase 9A must stay inside the development period")
        if config.bucket_minutes <= 0 or config.sigma_groups < 2:
            raise ValueError("Invalid grouping configuration")
        if list(config.lagged_abs_z_edges) != sorted(config.lagged_abs_z_edges):
            raise ValueError("Lagged |z| edges must be increasing")
        return config


def _tag(level: float) -> str:
    return str(round(level * 1000))


def _value(number: float) -> float | None:
    """JSON-safe statistic: undefined values (empty group, no pairs) become null."""
    return float(number) if np.isfinite(number) else None


def load_source(directory: Path, models: list[str], config: Phase9AConfig) -> tuple[pd.DataFrame, str]:
    """Concatenate verified development predictions; z uses the causal predictive sigma."""
    checkpoint = directory / "latest.json"
    state = json.loads(checkpoint.read_text(encoding="utf-8"))
    if not state.get("complete"):
        raise ValueError(f"Source checkpoint is incomplete: {directory}")
    days = sorted(int(day) for day in state["prediction_sha256"])
    if (days[0] < config.development_first_date or days[-1] > config.development_last_date):
        raise ValueError("Source predictions extend outside the development period")
    columns = ["TRADING_DATE", "session", "timestamp", "target_log_return", "sigma_ewma"]
    for model in models:
        for level in config.central_coverages:
            columns += [f"{model}_q_low_{_tag(level)}", f"{model}_q_high_{_tag(level)}"]
    frames = []
    for day in days:
        path = directory / "predictions" / f"{day}.csv"
        if sha256_file(path) != state["prediction_sha256"][str(day)]:
            raise ValueError(f"Prediction file differs from checkpoint: {path}")
        frames.append(pd.read_csv(path, usecols=columns))
    frame = pd.concat(frames, ignore_index=True)
    if (frame["TRADING_DATE"] >= config.final_test_start).any():
        raise ValueError("Final-test rows found in development source")
    if not (np.isfinite(frame["sigma_ewma"]).all() and (frame["sigma_ewma"] > 0).all()):
        raise ValueError("Invalid predictive sigma")
    stamp = pd.to_datetime(frame["timestamp"])
    frame["minute"] = stamp.dt.hour * 60 + stamp.dt.minute
    frame["group"] = frame["TRADING_DATE"] * 10 + frame["session"].map(SESSION_CODES)
    if frame["group"].isna().any():
        raise ValueError("Unknown session label")
    frame["z"] = frame["target_log_return"] / frame["sigma_ewma"]
    frame = frame.sort_values(["TRADING_DATE", "minute"], kind="stable").reset_index(drop=True)
    return frame, sha256_file(checkpoint)


def within_session_acf(values: np.ndarray, group: np.ndarray, minute: np.ndarray,
                       bar_minutes: int, max_lag: int) -> list[dict]:
    """Autocorrelation using only pairs k bars apart inside one session, no gap crossing."""
    centered = values - values.mean()
    variance = float(np.mean(centered ** 2))
    rows = []
    for lag in range(1, max_lag + 1):
        valid = (group[lag:] == group[:-lag]) & (minute[lag:] - minute[:-lag] == lag * bar_minutes)
        pairs = int(valid.sum())
        rho = float(np.mean(centered[lag:][valid] * centered[:-lag][valid]) / variance) if pairs else None
        rows.append({"lag": lag, "pairs": pairs, "acf": rho,
                     "band95": float(1.96 / np.sqrt(pairs)) if pairs else None})
    return rows


def portmanteau(rows: list[dict]) -> dict:
    """Box-Pierce style sum of pairs*acf^2; reference chi-square assumes independence."""
    used = [row for row in rows if row["acf"] is not None]
    statistic = float(sum(row["pairs"] * row["acf"] ** 2 for row in used))
    return {"statistic": statistic, "lags": len(used),
            "p_value_iid_reference": float(chi2.sf(statistic, len(used))) if used else None}


def clustered_mean(values: np.ndarray, clusters: np.ndarray) -> dict:
    """Mean with standard error clustered by trading day."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "se": None, "clusters": 0}
    mean = float(values.mean())
    _, index = np.unique(clusters, return_inverse=True)
    sums = np.bincount(index, weights=values - mean)
    groups = len(sums)
    se = float(np.sqrt(groups / (groups - 1) * np.sum(sums ** 2)) / n) if groups > 1 else None
    return {"n": n, "mean": mean, "se": se, "clusters": groups}


def _coverage(frame: pd.DataFrame, models: list[str], levels: tuple[float, ...]) -> dict:
    actual = frame["target_log_return"].to_numpy()
    result = {}
    for model in models:
        by_level = {}
        for level in levels:
            low = frame[f"{model}_q_low_{_tag(level)}"].to_numpy()
            high = frame[f"{model}_q_high_{_tag(level)}"].to_numpy()
            n = len(actual)
            below, above = int((actual < low).sum()), int((actual > high).sum())
            by_level[_tag(level)] = {"n": n, "coverage": 1 - (below + above) / n if n else None,
                                     "lower_exceedance": below / n if n else None,
                                     "upper_exceedance": above / n if n else None}
        result[model] = by_level
    return result


def _group_rows(frame: pd.DataFrame, labels: pd.Series, order: list[str], models: list[str],
                levels: tuple[float, ...]) -> list[dict]:
    rows = []
    for label in order:
        part = frame[labels == label]
        z = part["z"].to_numpy()
        rows.append({"group": label, "z2": clustered_mean(z ** 2, part["TRADING_DATE"].to_numpy()),
                     "std_z": _value(z.std()) if len(z) else None,
                     "mean_sigma": _value(part["sigma_ewma"].mean()) if len(z) else None,
                     "rms_return": _value(np.sqrt(np.mean(part["target_log_return"] ** 2))) if len(z) else None,
                     "coverage": _coverage(part, models, levels)})
    return rows


def _bucket_labels(frame: pd.DataFrame, bucket_minutes: int) -> pd.Series:
    start = frame["minute"] // bucket_minutes * bucket_minutes
    return (start // 60).astype(int).map("{:02d}".format) + ":" + (start % 60).astype(int).map("{:02d}".format)


def _lagged_abs_z_labels(frame: pd.DataFrame, bar_minutes: int, edges: tuple[float, ...]) -> tuple[pd.Series, list[str]]:
    previous = frame["z"].abs().shift(1)
    contiguous = (frame["group"] == frame["group"].shift(1)) & (frame["minute"] - frame["minute"].shift(1) == bar_minutes)
    names = [f"<{edges[0]:g}"] + [f"{a:g}-{b:g}" for a, b in zip(edges, edges[1:])] + [f">={edges[-1]:g}"]
    bins = np.digitize(previous.fillna(0).to_numpy(), edges)
    labels = pd.Series(np.array(names)[bins], index=frame.index)
    labels[~contiguous] = "first_or_gap"
    return labels, ["first_or_gap"] + names


def diagnose(frame: pd.DataFrame, models: list[str], config: Phase9AConfig, timeframe: str) -> dict:
    bar, max_lag = config.bar_minutes[timeframe], config.acf_max_lag[timeframe]
    z = frame["z"].to_numpy()
    group, minute = frame["group"].to_numpy(), frame["minute"].to_numpy()
    day = frame["TRADING_DATE"].to_numpy()
    abs_z = np.abs(z)
    probabilities = [0.9, 0.95, 0.975, 0.99, 0.995]
    summary = {"n": int(len(z)), "days": int(len(np.unique(day))), "mean": float(z.mean()),
               "std": float(z.std()), "skewness": float(skew(z)),
               "excess_kurtosis": float(kurtosis(z)), "max_abs": float(abs_z.max()),
               "abs_quantiles": {str(p): float(np.quantile(abs_z, p)) for p in probabilities},
               "share_abs_above_4": float(np.mean(abs_z > 4)),
               "share_abs_above_6": float(np.mean(abs_z > 6)),
               "mean_z2": clustered_mean(z ** 2, day)}
    bucket = _bucket_labels(frame, config.bucket_minutes)
    bucket_order = sorted(bucket.unique())
    seasonal = bucket.map({label: float(np.mean(z[bucket.to_numpy() == label] ** 2)) for label in bucket_order}).to_numpy()
    adjusted = z / np.sqrt(seasonal)
    abs_adjusted = np.abs(adjusted)
    summary["seasonally_adjusted"] = {
        "std": float(adjusted.std()), "skewness": float(skew(adjusted)),
        "excess_kurtosis": float(kurtosis(adjusted)), "max_abs": float(abs_adjusted.max()),
        "abs_quantiles": {str(p): float(np.quantile(abs_adjusted, p)) for p in probabilities},
        "share_abs_above_4": float(np.mean(abs_adjusted > 4))}
    acf = {"z": within_session_acf(z, group, minute, bar, max_lag),
           "z2": within_session_acf(z ** 2, group, minute, bar, max_lag),
           "z2_seasonally_adjusted": within_session_acf(adjusted ** 2, group, minute, bar, max_lag)}
    sigma_edges = np.quantile(frame["sigma_ewma"], np.linspace(0, 1, config.sigma_groups + 1)[1:-1])
    sigma_names = [f"Q{i + 1}" for i in range(config.sigma_groups)]
    sigma_labels = pd.Series(np.array(sigma_names)[np.digitize(frame["sigma_ewma"], sigma_edges)], index=frame.index)
    lag_labels, lag_order = _lagged_abs_z_labels(frame, bar, config.lagged_abs_z_edges)
    return {
        "summary": summary,
        "acf": acf,
        "portmanteau": {name: portmanteau(rows) for name, rows in acf.items()},
        "overall_coverage": _coverage(frame, models, config.central_coverages),
        "intraday": _group_rows(frame, bucket, bucket_order, models, config.central_coverages),
        "sigma_groups": {"edges": [float(v) for v in sigma_edges],
                         "rows": _group_rows(frame, sigma_labels, sigma_names, models, config.central_coverages)},
        "lagged_abs_z": _group_rows(frame, lag_labels, lag_order, models, config.central_coverages),
    }


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False, float_format="%.8g", lineterminator="\n")
    os.replace(temporary, path)


def _tables(report: dict) -> dict[str, pd.DataFrame]:
    """Flat tables consumed by the LaTeX figures."""
    sources = report["sources"]
    acf = pd.DataFrame({"lag": [row["lag"] for row in sources["hl30"]["acf"]["z"]]})
    for name, source in sources.items():
        for kind, rows in source["acf"].items():
            acf[f"{name}_{kind}"] = [row["acf"] for row in rows]
        acf[f"{name}_band95"] = [row["band95"] for row in source["acf"]["z"]]
    tables = {"acf": acf}
    for key, rows_of in (("intraday", lambda s: s["intraday"]),
                         ("sigma_groups", lambda s: s["sigma_groups"]["rows"]),
                         ("lagged_abs_z", lambda s: s["lagged_abs_z"])):
        base = rows_of(sources["hl30"])
        table = pd.DataFrame({"index": range(len(base)), "group": [row["group"] for row in base]})
        for name, source in sources.items():
            rows = {row["group"]: row for row in rows_of(source)}
            table[f"{name}_mean_z2"] = [rows[g]["z2"]["mean"] if g in rows else np.nan for g in table["group"]]
            table[f"{name}_se_z2"] = [rows[g]["z2"]["se"] if g in rows else np.nan for g in table["group"]]
            table[f"{name}_n"] = [rows[g]["z2"]["n"] if g in rows else 0 for g in table["group"]]
            table[f"{name}_mean_sigma"] = [rows[g]["mean_sigma"] if g in rows else np.nan for g in table["group"]]
            table[f"{name}_rms_return"] = [rows[g]["rms_return"] if g in rows else np.nan for g in table["group"]]
        for model in sources["hl30"]["models"]:
            for tag in ("950", "990"):
                table[f"{model}_cov{tag}"] = [row["coverage"][model][tag]["coverage"] for row in base]
        tables[key] = table
    return tables


def build_report(timeframe: str, config_path: Path, root: Path) -> dict:
    config = Phase9AConfig.from_json(config_path)
    sources, signature_sources = {}, {}
    for name, spec in config.sources.items():
        directory = root / spec["directory"].format(timeframe=timeframe)
        models = list(spec["models"][timeframe])
        frame, checkpoint_sha = load_source(directory, models, config)
        result = diagnose(frame, models, config, timeframe)
        result["models"] = models
        sources[name] = result
        signature_sources[name] = {"directory": spec["directory"].format(timeframe=timeframe),
                                   "checkpoint_sha256": checkpoint_sha}
    if sources["hl30"]["summary"]["n"] != sources["hl60"]["summary"]["n"]:
        raise ValueError("HL30 and HL60 sources cover different bars")
    return {"signature": {"experiment_id": config.experiment_id,
                          "run_id": f"{config.experiment_id}-{timeframe}",
                          "config_sha256": _normalized_text_sha256(config_path),
                          "code_sha256": _normalized_text_sha256(Path(__file__)),
                          "sources": signature_sources},
            "timeframe": timeframe,
            "status": "exploratory; development 2022-2024 only; in-sample groupings",
            "sources": sources}


def run(timeframe: str, config_path: Path, root: Path, output_dir: Path,
        *, check_only: bool = False) -> dict:
    report = build_report(timeframe, config_path, root)
    path = output_dir / "report.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(report)):
            raise ValueError("Existing Phase 9A report differs from recomputation")
        status = "checked"
    elif check_only:
        raise ValueError("No Phase 9A report to check")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, table in _tables(report).items():
            _write_csv(output_dir / f"{name}.csv", table)
        _atomic_json(path, report)
        status = "ready"
    print(f"{report['signature']['run_id']}: report {status}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9a_v1.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    run(args.timeframe, args.config, args.root, args.output_dir, check_only=args.check_only)


if __name__ == "__main__":
    main()
