"""Phase 4B two-piece and three-component mixture checks."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import gennorm, t

from distributional_bands.distributions import FitConfig, fit_distribution
from distributional_bands.skewed import TwoPieceLaw


class SkewedDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = FitConfig.from_json(Path("configs/distribution_fit_v2.json"))

    def test_zero_skew_matches_symmetric_parent(self) -> None:
        grid = np.array([-2.5, -0.3, 0.0, 0.4, 2.2])
        for family, shape, parent in (("student_t", 6.0, t(6.0)),
                                      ("ged", 1.4, gennorm(1.4))):
            with self.subTest(family=family):
                law = TwoPieceLaw(family, shape, 0.0)
                np.testing.assert_allclose(law.logpdf(grid), parent.logpdf(grid), atol=1e-12)
                np.testing.assert_allclose(law.cdf(grid), parent.cdf(grid), atol=1e-12)
                np.testing.assert_allclose(law.ppf(parent.cdf(grid)), grid, atol=1e-9)

    def test_skewed_quantiles_and_moments(self) -> None:
        probabilities = np.array([0.0025, 0.025, 0.25, 0.5, 0.75, 0.975, 0.9975])
        for family, shape in (("student_t", 7.0), ("ged", 1.25)):
            with self.subTest(family=family):
                law = TwoPieceLaw(family, shape, 0.45, loc=0.2, scale=0.8)
                values = law.ppf(probabilities)
                self.assertTrue(np.all(np.diff(values) > 0))
                np.testing.assert_allclose(law.cdf(values), probabilities, atol=1e-9)
                mean, variance = law.stats()
                self.assertTrue(math.isfinite(mean) and variance > 0)
                self.assertGreater(mean, 0.2)

    def test_skewed_models_fit_and_invert_tail_quantiles(self) -> None:
        rng = np.random.default_rng(743)
        sample = TwoPieceLaw("student_t", 6, 0.35).ppf(rng.uniform(0.01, 0.99, 140))
        for model in ("skewed_t", "skewed_ged"):
            with self.subTest(model=model):
                fitted = fit_distribution(model, sample, self.config)
                probabilities = np.array([0.0025, 0.025, 0.5, 0.975, 0.9975])
                np.testing.assert_allclose(fitted.cdf(fitted.ppf(probabilities)),
                                           probabilities, atol=1e-7)
                self.assertEqual(fitted.diagnostics["starts_attempted"], 3)

    def test_three_component_mixture_is_deterministic(self) -> None:
        rng = np.random.default_rng(331)
        sample = np.concatenate((rng.normal(-2, 0.3, 100),
                                 rng.normal(0, 0.4, 100),
                                 rng.normal(2, 0.5, 100)))
        a = fit_distribution("normal_mixture_3", sample, self.config)
        b = fit_distribution("normal_mixture_3", sample, self.config)
        self.assertEqual(a.as_dict(), b.as_dict())
        p = a.parameters
        self.assertAlmostEqual(sum(p[f"weight_{i}"] for i in (1, 2, 3)), 1)
        self.assertLess(p["mean_1"], p["mean_2"])
        self.assertLess(p["mean_2"], p["mean_3"])
        probabilities = np.array([0.0025, 0.5, 0.9975])
        np.testing.assert_allclose(a.cdf(a.ppf(probabilities)), probabilities, atol=1e-8)


if __name__ == "__main__":
    unittest.main()
