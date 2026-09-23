"""Bounded synthetic checks for phase 4A; no full historical fitting."""

from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from scipy.stats import genhyperbolic, norm

from distributional_bands.distributions import (
    FitConfig, FitError, FittedDistribution, fit_distribution,
)


class DistributionFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = FitConfig.from_json(Path("configs/distribution_fit_v1.json"))
        rng = np.random.default_rng(712)
        cls.sample = np.concatenate((rng.normal(-0.6, 0.45, 100),
                                     rng.normal(0.7, 0.55, 100)))

    def test_configuration_and_input_are_strict(self) -> None:
        self.assertEqual(len(self.config.models), 6)
        with self.assertRaises(FitError):
            fit_distribution("normal", np.ones(100), self.config)
        with self.assertRaises(FitError):
            fit_distribution("normal", np.array([0.0, math.nan] * 50), self.config)
        with self.assertRaises(FitError):
            fit_distribution("normal", self.sample[:20], self.config)
        with self.assertRaises(ValueError):
            fit_distribution("skewed_t", self.sample, self.config)

    def test_normal_is_standardized_and_serializable(self) -> None:
        fitted = fit_distribution("normal", self.sample, self.config)
        probabilities = np.array([0.0025, 0.025, 0.5, 0.975, 0.9975])
        np.testing.assert_allclose(fitted.ppf(probabilities), norm.ppf(probabilities), atol=1e-10)
        np.testing.assert_allclose(fitted.cdf(fitted.ppf(probabilities)), probabilities, atol=1e-10)
        self.assertTrue(math.isfinite(fitted.log_likelihood))
        restored = FittedDistribution(**json.loads(json.dumps(fitted.as_dict(), allow_nan=False)))
        np.testing.assert_allclose(restored.ppf(probabilities), fitted.ppf(probabilities))

    def test_student_t_and_ged_fit_and_invert_tail_quantiles(self) -> None:
        for model in ("student_t", "ged"):
            with self.subTest(model=model):
                fitted = fit_distribution(model, self.sample, self.config)
                probabilities = np.array([0.0025, 0.025, 0.5, 0.975, 0.9975])
                quantiles = fitted.ppf(probabilities)
                self.assertTrue(np.all(np.diff(quantiles) > 0))
                np.testing.assert_allclose(fitted.cdf(quantiles), probabilities, atol=1e-7)
                self.assertGreater(fitted.diagnostics["converged_starts"], 0)
                json.dumps(fitted.as_dict(), allow_nan=False)

    def test_mixture_em_is_reproducible_and_standardized(self) -> None:
        first = fit_distribution("normal_mixture_2", self.sample, self.config)
        second = fit_distribution("normal_mixture_2", self.sample, self.config)
        self.assertEqual(first.as_dict(), second.as_dict())
        p = first.parameters
        self.assertAlmostEqual(p["weight_1"] + p["weight_2"], 1)
        self.assertLess(p["mean_1"], p["mean_2"])
        self.assertGreaterEqual(min(p["sigma_1"] ** 2, p["sigma_2"] ** 2),
                                self.config.mixture_variance_floor)
        probabilities = np.array([0.0025, 0.025, 0.5, 0.975, 0.9975])
        np.testing.assert_allclose(first.cdf(first.ppf(probabilities)), probabilities, atol=1e-8)
        self.assertGreater(first.diagnostics["converged_starts"], 0)
        with self.assertRaises(FitError):
            fit_distribution("normal_mixture_2", self.sample,
                             replace(self.config, mixture_max_iter=1))

    def test_gh_quantile_interface_and_failed_fit_are_explicit(self) -> None:
        raw = genhyperbolic(-0.5, 2.0, 0.3, loc=0.1, scale=0.8)
        mean, variance = (float(x) for x in raw.stats(moments="mv"))
        law = FittedDistribution(
            "gh", {"p": -0.5, "a": 2.0, "b": 0.3, "loc": 0.1, "scale": 0.8},
            mean, math.sqrt(variance), 100, -100.0, {},
        )
        probabilities = np.array([0.0025, 0.025, 0.5, 0.975, 0.9975])
        np.testing.assert_allclose(law.cdf(law.ppf(probabilities)), probabilities, atol=1e-6)
        with self.assertRaises(ValueError):
            law.ppf([0, 0.5])
        with patch("distributional_bands.distributions.minimize",
                   return_value=SimpleNamespace(success=False, message="forced failure")) as optimizer:
            with self.assertRaisesRegex(FitError, "no converged MLE start"):
                fit_distribution("gh", self.sample, self.config)
            self.assertEqual(optimizer.call_count, self.config.mle_starts)

    def test_nig_and_gh_actual_small_sample_fit(self) -> None:
        small = self.sample[:100]
        for model in ("nig", "gh"):
            with self.subTest(model=model):
                fitted = fit_distribution(model, small, self.config)
                self.assertGreater(fitted.diagnostics["converged_starts"], 0)
                self.assertEqual(fitted.diagnostics["starts_attempted"], self.config.mle_starts)
                q = fitted.ppf([0.025, 0.975])
                self.assertLess(q[0], q[1])
                np.testing.assert_allclose(fitted.cdf(q), [0.025, 0.975], atol=1e-5)
                json.dumps(fitted.as_dict(), allow_nan=False)

    def test_all_candidates_have_unit_population_moments_after_normalization(self) -> None:
        for model in self.config.models:
            with self.subTest(model=model):
                fitted = fit_distribution(model, self.sample[:100], self.config)
                if model == "normal_mixture_2":
                    p = fitted.parameters
                    mean = sum(p[f"weight_{i}"] * p[f"mean_{i}"] for i in (1, 2))
                    second = sum(p[f"weight_{i}"] *
                                 (p[f"sigma_{i}"] ** 2 + p[f"mean_{i}"] ** 2)
                                 for i in (1, 2))
                    variance = second - mean ** 2
                else:
                    mean, variance = fitted._frozen().stats(moments="mv")
                self.assertAlmostEqual((float(mean) - fitted.center) / fitted.spread, 0, places=8)
                self.assertAlmostEqual(float(variance) / fitted.spread ** 2, 1, places=8)


if __name__ == "__main__":
    unittest.main()
