"""Phase 9E: Monte Carlo accuracy and misspecification study of the nine families.

Data-generating laws ("phân phối sinh mẫu") are, per timeframe, the representative
Phase 9D fit of each family (the refit whose ten standardized quantiles are closest
to the median across refits) plus an i.i.d. bootstrap of the standardized real z.
Each case draws n observations (median Phase 9D training size), refits all nine
families with the Phase 5 policy and computes the empirical quantiles. Every case
is written to its own file, so the study resumes and runs in parallel. The report
compares estimates with the true quantiles and the true CDF of the generating law.

Stages: setup (generating laws, true quantiles, CDF grid), run (cases), report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gennorm, genhyperbolic, norm, norminvgauss, t

from .baseline import _normalized_text_sha256
from .data import sha256_file
from .distributions import FitConfig, FitError, FittedDistribution, fit_distribution
from .skewed import TwoPieceLaw
from .win_retry import retrying_replace

TIMEFRAME_CODES = {"1m": 1, "5m": 5}
BOOTSTRAP = "bootstrap_real_z"


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    retrying_replace(temporary, path)


def probabilities(coverages: list[float]) -> list[float]:
    return sorted({(1 - c) / 2 for c in coverages} | {(1 + c) / 2 for c in coverages})


def _quantile_vector(item: dict, coverages: list[float]) -> np.ndarray:
    tags = [str(round(c * 1000)) for c in sorted(coverages)]
    lows = [item["quantiles"][tag][0] for tag in tags]
    highs = [item["quantiles"][tag][1] for tag in tags]
    return np.array(sorted(lows) + sorted(highs))


def representative_fits(fit_history: list[dict], families: list[str], coverages: list[float]) -> dict:
    """For each family, the successful refit closest (L2) to the median quantile vector."""
    chosen = {}
    for family in families:
        fits = [item for item in fit_history if item["model"] == family and item["status"] == "success"]
        if not fits:
            raise ValueError(f"No successful Phase 9D fit for {family}")
        vectors = np.array([_quantile_vector(item, coverages) for item in fits])
        median = np.median(vectors, axis=0)
        best = int(np.argmin(((vectors - median) ** 2).sum(axis=1)))
        chosen[family] = {"refit_day": fits[best]["refit_day"], "fit": fits[best]["fit"]}
    return chosen


def _cdf_grid(law: FittedDistribution, grid: np.ndarray) -> np.ndarray:
    """CDF on the grid by integrating the density from the first grid point."""
    density = np.exp(np.asarray(law.logpdf(grid), dtype=float))
    steps = np.concatenate([[0.0], np.cumsum((density[1:] + density[:-1]) / 2 * np.diff(grid))])
    values = float(law.cdf(float(grid[0]))) + steps
    return np.clip(np.maximum.accumulate(values), 0.0, 1.0)


def setup(timeframe: str, config_path: Path, fit_path: Path, root: Path, output_root: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    fit_config = FitConfig.from_json(fit_path)
    families = list(fit_config.models)
    source = root / config["sources"][timeframe]
    state = json.loads((source / "latest.json").read_text(encoding="utf-8"))
    if not state["complete"]:
        raise ValueError(f"Source run incomplete: {source}")
    directory = output_root / timeframe / "dgp"
    spec_path = directory / "spec.json"
    source_hash = sha256_file(source / "latest.json")
    if spec_path.exists():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if spec["source_checkpoint_sha256"] != source_hash or spec["config_sha256"] != _normalized_text_sha256(config_path):
            raise ValueError("Existing Phase 9E setup differs from its source or config")
        for name, expected in spec["file_sha256"].items():
            if sha256_file(directory / name) != expected:
                raise ValueError(f"Phase 9E setup file changed: {name}")
        print(f"PHASE9E {timeframe}: setup already present and verified")
        return spec
    directory.mkdir(parents=True, exist_ok=True)
    coverages = config["central_coverages"]
    probs = probabilities(coverages)
    n = int(np.median([item["n_train"] for item in state["fit_history"]]))
    laws = {family: value for family, value in representative_fits(state["fit_history"], families, coverages).items()}
    grid = np.linspace(-config["grid_limit"], config["grid_limit"], config["grid_points"])
    cdf, truth = {}, {}
    for family, value in laws.items():
        law = FittedDistribution(**value["fit"])
        cdf[family] = _cdf_grid(law, grid)
        truth[family] = [float(x) for x in law.ppf(probs)]
    files = {}
    if config["include_bootstrap_dgp"]:
        pieces = []
        for day, expected in sorted(state["prediction_sha256"].items()):
            path = source / "predictions" / f"{day}.csv"
            if sha256_file(path) != expected:
                raise ValueError(f"Source prediction differs from checkpoint: {path}")
            frame = pd.read_csv(path, usecols=["target_log_return", "sigma_ewma"])
            pieces.append((frame["target_log_return"] / frame["sigma_ewma"]).to_numpy())
        pool = np.concatenate(pieces)
        pool = np.sort((pool - pool.mean()) / pool.std())
        np.save(directory / "pool.npy", pool)
        cdf[BOOTSTRAP] = np.searchsorted(pool, grid, side="right") / len(pool)
        truth[BOOTSTRAP] = [float(x) for x in np.quantile(pool, probs)]
    np.savez(directory / "grid.npz", grid=grid, **{f"cdf_{k}": v for k, v in cdf.items()})
    for name in ("grid.npz", "pool.npy"):
        if (directory / name).exists():
            files[name] = sha256_file(directory / name)
    spec = {"timeframe": timeframe, "n": n, "probabilities": probs, "coverages": coverages,
            "families": families, "dgps": families + ([BOOTSTRAP] if config["include_bootstrap_dgp"] else []),
            "laws": laws, "true_quantiles": truth,
            "source": config["sources"][timeframe], "source_checkpoint_sha256": source_hash,
            "config_sha256": _normalized_text_sha256(config_path),
            "fit_config_sha256": _normalized_text_sha256(fit_path), "file_sha256": files}
    _write_json(spec_path, spec)
    print(f"PHASE9E {timeframe}: setup written; n={n}; {len(spec['dgps'])} generating laws")
    return spec


def signature_hash(spec: dict, config_path: Path, fit_path: Path) -> str:
    sources = ("phase9e.py", "distributions.py", "skewed.py")
    value = {"spec_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
             "config_sha256": _normalized_text_sha256(config_path),
             "fit_config_sha256": _normalized_text_sha256(fit_path),
             "source_sha256": {name: _normalized_text_sha256(Path(__file__).with_name(name)) for name in sources}}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def draw(dgp: str, spec: dict, pool: np.ndarray | None, rng: np.random.Generator) -> np.ndarray:
    """n standardized observations from the generating law."""
    n = spec["n"]
    if dgp == BOOTSTRAP:
        return rng.choice(pool, size=n, replace=True)
    fit = spec["laws"][dgp]["fit"]
    p, model = fit["parameters"], fit["model"]
    if model == "normal":
        raw = norm.rvs(p["loc"], p["scale"], size=n, random_state=rng)
    elif model == "student_t":
        raw = t.rvs(p["df"], loc=p["loc"], scale=p["scale"], size=n, random_state=rng)
    elif model == "ged":
        raw = gennorm.rvs(p["beta"], loc=p["loc"], scale=p["scale"], size=n, random_state=rng)
    elif model == "nig":
        raw = norminvgauss.rvs(p["a"], p["b"], loc=p["loc"], scale=p["scale"], size=n, random_state=rng)
    elif model == "gh":
        raw = genhyperbolic.rvs(p["p"], p["a"], p["b"], loc=p["loc"], scale=p["scale"], size=n, random_state=rng)
    elif model in ("skewed_t", "skewed_ged"):
        parent = "student_t" if model == "skewed_t" else "ged"
        shape = p["df"] if model == "skewed_t" else p["beta"]
        law = TwoPieceLaw(parent, shape, p["skew"], p["loc"], p["scale"])
        raw = law.ppf(np.clip(rng.random(n), 1e-15, 1 - 1e-15))
    else:
        count = int(model.rsplit("_", 1)[1])
        weights = np.array([p[f"weight_{i}"] for i in range(1, count + 1)])
        component = rng.choice(count, size=n, p=weights / weights.sum())
        means = np.array([p[f"mean_{i}"] for i in range(1, count + 1)])
        sigmas = np.array([p[f"sigma_{i}"] for i in range(1, count + 1)])
        raw = rng.normal(means[component], sigmas[component])
    return (np.asarray(raw, dtype=float) - fit["center"]) / fit["spread"]


_WORKER: dict = {}


def _init_worker(spec_path: str, pool_path: str | None, fit_path: str, case_dir: str, signature: str) -> None:
    _WORKER["spec"] = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    _WORKER["pool"] = np.load(pool_path) if pool_path else None
    _WORKER["fit_config"] = FitConfig.from_json(Path(fit_path))
    _WORKER["case_dir"] = Path(case_dir)
    _WORKER["signature"] = signature


def run_case(dgp_index: int, replication: int, seed: int) -> str:
    spec, fit_config = _WORKER["spec"], _WORKER["fit_config"]
    dgp = spec["dgps"][dgp_index]
    rng = np.random.default_rng(np.random.SeedSequence(
        [seed, TIMEFRAME_CODES[spec["timeframe"]], dgp_index, replication]))
    started = time.perf_counter()
    sample = draw(dgp, spec, _WORKER["pool"], rng)
    probs = spec["probabilities"]
    models = {"empirical": {"status": "success", "quantiles": [float(x) for x in np.quantile(sample, probs)]}}
    for family in spec["families"]:
        begun = time.perf_counter()
        try:
            fitted = fit_distribution(family, sample, fit_config)
            models[family] = {"status": "success", "quantiles": [float(x) for x in fitted.ppf(probs)],
                              "parameters": fitted.parameters, "center": fitted.center,
                              "spread": fitted.spread,
                              "at_bound": int(fitted.diagnostics.get("parameters_at_bound", 0)),
                              "seconds": time.perf_counter() - begun}
        except FitError as exc:
            models[family] = {"status": "failed", "reason": str(exc)[:200],
                              "seconds": time.perf_counter() - begun}
    record = {"signature": _WORKER["signature"], "dgp": dgp, "replication": replication,
              "n": len(sample), "sample_mean": float(sample.mean()), "sample_std": float(sample.std()),
              "seconds": time.perf_counter() - started, "models": models}
    path = _WORKER["case_dir"] / dgp / f"{replication:04d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, record)
    return str(path)


def _case_done(path: Path, signature: str) -> bool:
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8"))["signature"] == signature
    except (ValueError, KeyError):
        return False


def run(timeframe: str, config_path: Path, fit_path: Path, output_root: Path,
        *, workers: int | None = None, max_cases: int | None = None, check_only: bool = False) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    directory = output_root / timeframe
    spec_path = directory / "dgp" / "spec.json"
    if not spec_path.exists():
        raise ValueError("Run the setup stage first")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for name, expected in spec["file_sha256"].items():
        if sha256_file(directory / "dgp" / name) != expected:
            raise ValueError(f"Phase 9E setup file changed: {name}")
    signature = signature_hash(spec, config_path, fit_path)
    case_dir = directory / "cases"
    cases = [(d, r) for d in range(len(spec["dgps"])) for r in range(config["replications"])]
    pending = [(d, r) for d, r in cases
               if not _case_done(case_dir / spec["dgps"][d] / f"{r:04d}.json", signature)]
    done = len(cases) - len(pending)
    print(f"PHASE9E {timeframe}: {done}/{len(cases)} cases complete", flush=True)
    if check_only or not pending:
        return {"complete": done, "total": len(cases)}
    if max_cases is not None:
        pending = pending[:max_cases]
    count = workers if workers is not None else int(config.get("workers") or 0)
    count = count or max(1, (os.cpu_count() or 2) - 2)
    init_args = (str(spec_path), str(directory / "dgp" / "pool.npy") if "pool.npy" in spec["file_sha256"] else None,
                 str(fit_path), str(case_dir), signature)
    started = time.perf_counter()
    finished = 0
    if count == 1:
        _init_worker(*init_args)
        for d, r in pending:
            run_case(d, r, config["seed"])
            finished += 1
            _progress(timeframe, done + finished, len(cases), finished, len(pending), started)
    else:
        with ProcessPoolExecutor(max_workers=count, initializer=_init_worker, initargs=init_args) as pool:
            futures = [pool.submit(run_case, d, r, config["seed"]) for d, r in pending]
            for future in as_completed(futures):
                future.result()
                finished += 1
                _progress(timeframe, done + finished, len(cases), finished, len(pending), started)
    print(f"PHASE9E {timeframe}: {done + finished}/{len(cases)} cases complete ({count} workers)", flush=True)
    return {"complete": done + finished, "total": len(cases)}


def _progress(timeframe: str, total_done: int, total: int, finished: int, pending: int, started: float) -> None:
    step = max(1, pending // 100)
    if finished % step == 0 or finished == pending:
        elapsed = time.perf_counter() - started
        remaining = elapsed / finished * (pending - finished)
        print(f"PHASE9E {timeframe}: {total_done}/{total} cases; "
              f"elapsed {elapsed / 60:.1f} min; remaining ~{remaining / 60:.1f} min", flush=True)


def _sorted_mixture(parameters: dict) -> dict:
    """Order mixture components by standard deviation to remove label switching."""
    count = sum(1 for key in parameters if key.startswith("weight_"))
    if not count:
        return parameters
    order = sorted(range(1, count + 1), key=lambda i: parameters[f"sigma_{i}"])
    result = {}
    for new, old in enumerate(order, start=1):
        for name in ("weight", "mean", "sigma"):
            result[f"{name}_{new}"] = parameters[f"{name}_{old}"]
    return result


def build_report(timeframe: str, config_path: Path, fit_path: Path, output_root: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    directory = output_root / timeframe
    spec = json.loads((directory / "dgp" / "spec.json").read_text(encoding="utf-8"))
    signature = signature_hash(spec, config_path, fit_path)
    data = np.load(directory / "dgp" / "grid.npz")
    grid = data["grid"]
    probs = np.array(spec["probabilities"])
    coverages = spec["coverages"]
    models = ["empirical"] + spec["families"]
    matrix, recovery = {}, {}
    for dgp in spec["dgps"]:
        cdf = data[f"cdf_{dgp}"]
        integral = np.concatenate([[0.0], np.cumsum((cdf[1:] + cdf[:-1]) / 2 * np.diff(grid))])
        truth = np.array(spec["true_quantiles"][dgp])

        def expected_loss(q: np.ndarray) -> np.ndarray:
            return -probs * q + np.interp(q, grid, integral)

        oracle = expected_loss(truth)
        records = []
        for replication in range(config["replications"]):
            path = directory / "cases" / dgp / f"{replication:04d}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["signature"] != signature or record["dgp"] != dgp or record["replication"] != replication:
                raise ValueError(f"Case file does not belong to this run: {path}")
            records.append(record)
        empirical_rmse = None
        matrix[dgp] = {}
        for model in models:
            fitted = [r["models"][model] for r in records if r["models"][model]["status"] == "success"]
            failures = len(records) - len(fitted)
            if not fitted:
                matrix[dgp][model] = {"failures": failures}
                continue
            q = np.array([item["quantiles"] for item in fitted])
            error = q - truth
            rmse = np.sqrt((error ** 2).mean(axis=0))
            if model == "empirical":
                empirical_rmse = rmse
            excess = np.array([expected_loss(row) - oracle for row in q])
            coverage = {}
            for level in coverages:
                low, high = np.searchsorted(probs, (1 - level) / 2), np.searchsorted(probs, (1 + level) / 2)
                true_cover = np.interp(q[:, high], grid, cdf) - np.interp(q[:, low], grid, cdf)
                coverage[str(round(level * 1000))] = {"mean": float(true_cover.mean()),
                                                      "rmse_vs_nominal": float(np.sqrt(((true_cover - level) ** 2).mean()))}
            matrix[dgp][model] = {
                "failures": failures, "replications": len(records),
                "quantile_bias": error.mean(axis=0).tolist(), "quantile_rmse": rmse.tolist(),
                "mean_quantile_rmse": float(rmse.mean()),
                "excess_loss_percent": float(100 * excess.sum(axis=1).mean() / oracle.sum()),
                "excess_loss_percent_se": float(100 * excess.sum(axis=1).std(ddof=1) / oracle.sum() / np.sqrt(len(q)))
                if len(q) > 1 else None,
                "true_coverage": coverage,
                "at_bound_rate": float(np.mean([item.get("at_bound", 0) > 0 for item in fitted])) if model != "empirical" else 0.0,
                "median_seconds": float(np.median([item.get("seconds", 0.0) for item in fitted])) if model != "empirical" else 0.0,
            }
        for model in spec["families"]:
            entry = matrix[dgp].get(model, {})
            if "quantile_rmse" in entry and empirical_rmse is not None:
                entry["efficiency_vs_empirical"] = (np.array(entry["quantile_rmse"]) / empirical_rmse).tolist()
                entry["mean_efficiency_vs_empirical"] = float(np.mean(entry["efficiency_vs_empirical"]))
        if dgp in spec["families"]:
            true = _sorted_mixture(spec["laws"][dgp]["fit"]["parameters"])
            estimates = [_sorted_mixture(r["models"][dgp]["parameters"]) for r in records
                         if r["models"][dgp]["status"] == "success"]
            recovery[dgp] = {name: {"true": float(value),
                                    "bias": float(np.mean([e[name] for e in estimates]) - value),
                                    "rmse": float(np.sqrt(np.mean([(e[name] - value) ** 2 for e in estimates])))}
                             for name, value in true.items()} if estimates else {}
        ranking = sorted((m for m in models if "excess_loss_percent" in matrix[dgp][m]),
                         key=lambda m: matrix[dgp][m]["excess_loss_percent"])
        matrix[dgp]["_ranking_by_excess_loss"] = ranking
    return {"signature": {"experiment_id": config["experiment_id"], "run_id": f"{config['experiment_id']}-{timeframe}",
                          "case_signature": signature, "spec_sha256": sha256_file(directory / "dgp" / "spec.json"),
                          "report_code_sha256": _normalized_text_sha256(Path(__file__))},
            "timeframe": timeframe, "n": spec["n"], "replications": config["replications"],
            "generating_laws": spec["dgps"], "probabilities": spec["probabilities"],
            "true_quantiles": spec["true_quantiles"], "results": matrix, "parameter_recovery": recovery,
            "notes": ["Simulation only; no market data beyond the Phase 9D fits and the bootstrap pool.",
                      "excess_loss_percent: expected quantile loss above the true-quantile loss, % of the latter,",
                      "summed over the ten probabilities; true coverage uses the generating law's CDF.",
                      "Mixture parameters are ordered by component standard deviation before comparison."]}


def report(timeframe: str, config_path: Path, fit_path: Path, output_root: Path, *, check_only: bool = False) -> dict:
    result = build_report(timeframe, config_path, fit_path, output_root)
    path = output_root / timeframe / "report.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(result)):
            raise ValueError("Existing Phase 9E report differs from case files")
        status = "checked"
    elif check_only:
        raise ValueError("No Phase 9E report to check")
    else:
        _write_json(path, result)
        status = "ready"
    print(f"{result['signature']['run_id']}: report {status}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAME_CODES), required=True)
    parser.add_argument("--stage", choices=("setup", "run", "report"), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase9e_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/phase9e_v1"))
    parser.add_argument("--workers", type=int)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.stage == "setup":
        setup(args.timeframe, args.config, args.fit_config, args.root, args.output_root)
    elif args.stage == "run":
        run(args.timeframe, args.config, args.fit_config, args.output_root,
            workers=args.workers, max_cases=args.max_cases, check_only=args.check_only)
    else:
        report(args.timeframe, args.config, args.fit_config, args.output_root, check_only=args.check_only)


if __name__ == "__main__":
    main()
