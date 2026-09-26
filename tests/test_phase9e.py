"""Phase 9E: representative laws, standardized sampling, CDF grid, setup/run/report."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from distributional_bands.data import sha256_file
from distributional_bands.distributions import FitConfig, fit_distribution
from distributional_bands.phase9e import (_cdf_grid, draw, report, representative_fits, run, setup)
from distributional_bands.walk_forward import _quantiles

ROOT = Path(__file__).resolve().parents[1]
FIT_CONFIG = ROOT / "configs/distribution_fit_v2.json"
COVERAGES = [0.9, 0.95, 0.975, 0.99, 0.995]


def _source(root: Path, fit_path: Path) -> Path:
    """Fake Phase 9D trial: fit history from synthetic windows and prediction files for the pool."""
    fit_config = FitConfig.from_json(fit_path)
    rng = np.random.default_rng(5)
    source = root / "source"
    (source / "predictions").mkdir(parents=True)
    history, hashes = [], {}
    for index in range(3):
        sample = rng.standard_t(5, 400)
        for model in fit_config.models:
            fitted = fit_distribution(model, sample, fit_config)
            history.append({"refit_day": 20220103 + index, "model": model, "n_train": 300,
                            "status": "success", "fit": fitted.as_dict(),
                            "quantiles": _quantiles(fitted, tuple(COVERAGES))})
        path = source / "predictions" / f"{20220103 + index}.csv"
        pd.DataFrame({"target_log_return": rng.standard_t(5, 200) * 0.001,
                      "sigma_ewma": np.full(200, 0.001)}).to_csv(path, index=False)
        hashes[str(20220103 + index)] = sha256_file(path)
    (source / "latest.json").write_text(json.dumps({"complete": True, "fit_history": history,
                                                     "prediction_sha256": hashes}), encoding="utf-8")
    return source


class Phase9ETests(unittest.TestCase):
    def test_representative_fit_is_closest_to_median(self) -> None:
        def item(shift: float) -> dict:
            return {"model": "normal", "status": "success", "refit_day": shift, "fit": {"x": shift},
                    "quantiles": {str(round(c * 1000)): [-1 - shift, 1 + shift] for c in COVERAGES}}
        chosen = representative_fits([item(0.0), item(0.1), item(0.5)], ["normal"], COVERAGES)
        self.assertEqual(chosen["normal"]["refit_day"], 0.1)

    def test_cdf_grid_matches_exact_normal(self) -> None:
        sample = np.random.default_rng(1).normal(size=500)
        law = fit_distribution("normal", sample, FitConfig.from_json(FIT_CONFIG))
        grid = np.linspace(-10, 10, 4001)
        np.testing.assert_allclose(_cdf_grid(law, grid), norm.cdf(grid), atol=1e-6)

    def test_draws_are_standardized_for_every_family(self) -> None:
        fit_config = FitConfig.from_json(FIT_CONFIG)
        data = np.random.default_rng(2).standard_t(5, 3000)
        for model in fit_config.models:
            with self.subTest(model=model):
                fitted = fit_distribution(model, data, fit_config)
                spec = {"n": 40000, "laws": {model: {"fit": fitted.as_dict()}}}
                sample = draw(model, spec, None, np.random.default_rng(3))
                self.assertLess(abs(sample.mean()), 0.03)
                self.assertLess(abs(sample.std() - 1), 0.05)

    def test_setup_run_resume_report_and_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fit_path = root / "fit.json"
            raw = json.loads(FIT_CONFIG.read_text(encoding="utf-8"))
            fit_path.write_text(json.dumps(dict(raw, models=["normal", "student_t"])), encoding="utf-8")
            source = _source(root, fit_path)
            config = root / "config.json"
            config.write_text(json.dumps({"experiment_id": "TEST-9E", "sources": {"5m": "source"},
                                          "replications": 3, "include_bootstrap_dgp": True,
                                          "central_coverages": COVERAGES, "grid_limit": 20.0,
                                          "grid_points": 4001, "seed": 7, "workers": 1}), encoding="utf-8")
            output = root / "out"
            spec = setup("5m", config, fit_path, root, output)
            self.assertEqual(spec["dgps"], ["normal", "student_t", "bootstrap_real_z"])
            self.assertEqual(spec["n"], 300)
            self.assertEqual(setup("5m", config, fit_path, root, output)["n"], 300)
            self.assertEqual(run("5m", config, fit_path, output, workers=1, max_cases=4)["complete"], 4)
            self.assertEqual(run("5m", config, fit_path, output, workers=1)["complete"], 9)
            first = json.loads((output / "5m/cases/normal/0000.json").read_text(encoding="utf-8"))
            self.assertEqual(run("5m", config, fit_path, output, workers=1)["complete"], 9)
            self.assertEqual(first, json.loads((output / "5m/cases/normal/0000.json").read_text(encoding="utf-8")))
            result = report("5m", config, fit_path, output)
            normal = result["results"]["normal"]
            self.assertAlmostEqual(normal["normal"]["excess_loss_percent"], 0.0, places=6)
            self.assertGreaterEqual(normal["empirical"]["excess_loss_percent"], 0.0)
            self.assertIn("df", result["parameter_recovery"]["student_t"])
            report("5m", config, fit_path, output, check_only=True)
            case = output / "5m/cases/student_t/0001.json"
            record = json.loads(case.read_text(encoding="utf-8"))
            record["signature"] = "tampered"
            case.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                report("5m", config, fit_path, output, check_only=True)
            (source / "latest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises((ValueError, KeyError)):
                setup("5m", config, fit_path, root, output)


if __name__ == "__main__":
    unittest.main()
