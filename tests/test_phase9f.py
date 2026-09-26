"""Phase 9F: refit mapping and raw-scale re-scoring."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.phase9d import Phase9DConfig
from distributional_bands.phase9f import _active_fits, _holm, raw_day_scores

CONFIG = Phase9DConfig.from_json(Path(__file__).resolve().parents[1] / "configs/phase9d_v1.json")


def _fit(center: float, spread: float) -> dict:
    quantiles = {"900": [-1.645, 1.645], "950": [-1.96, 1.96], "975": [-2.24, 2.24],
                 "990": [-2.576, 2.576], "995": [-2.807, 2.807]}
    return {"status": "success", "quantiles": quantiles,
            "fit": {"center": center, "spread": spread}}


class Phase9FTests(unittest.TestCase):
    def test_active_fit_is_latest_refit_on_or_before_day(self) -> None:
        history = [{"refit_day": 1, "model": "normal"}, {"refit_day": 6, "model": "normal"}]
        active = _active_fits(history, [1, 5, 6, 9])
        self.assertEqual([active[d]["normal"]["refit_day"] for d in (1, 5, 6, 9)], [1, 1, 6, 6])
        with self.assertRaises(ValueError):
            _active_fits(history, [0])

    def test_raw_scale_bands_use_fitted_location_and_scale(self) -> None:
        sigma = np.array([0.001, 0.002])
        prediction = pd.DataFrame({"target_log_return": [0.0005, -0.004], "sigma_ewma": sigma,
                                   "session": ["morning", "morning"], "bucket": ["09:00", "09:15"]})
        fits = {"normal": _fit(0.1, 2.0)}
        for tag, (low, high) in fits["normal"]["quantiles"].items():
            prediction[f"normal_q_low_{tag}"] = sigma * low
            prediction[f"normal_q_high_{tag}"] = sigma * high
        scores = raw_day_scores(prediction, fits, CONFIG, 1e-9)["normal"]
        low = sigma * (0.1 + 2.0 * -1.96)
        high = sigma * (0.1 + 2.0 * 1.96)
        expected_width = float((high - low).sum())
        self.assertAlmostEqual(scores["levels"]["950"]["width_sum"], expected_width)
        self.assertEqual(scores["levels"]["950"]["lower_exceed"], 0)
        prediction.loc[0, "normal_q_low_900"] += 1e-4
        with self.assertRaisesRegex(ValueError, "do not match"):
            raw_day_scores(prediction, fits, CONFIG, 1e-9)

    def test_holm_is_monotone_and_capped(self) -> None:
        adjusted = _holm({"a": 0.01, "b": 0.04, "c": 0.5})
        self.assertAlmostEqual(adjusted["a"], 0.03)
        self.assertAlmostEqual(adjusted["b"], 0.08)
        self.assertAlmostEqual(adjusted["c"], 0.5)


if __name__ == "__main__":
    unittest.main()
