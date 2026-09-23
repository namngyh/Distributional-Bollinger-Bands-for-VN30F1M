"""Bounded tests for Phase 6 diagnostics; no full-history job."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.selection import (_bootstrap, _day_record, _report,
                                             _independence, _transitions,
                                             SelectionConfig)


class SelectionTests(unittest.TestCase):
    def test_session_boundary_is_not_an_exceedance_transition(self) -> None:
        events = np.array([False, True, True, False])
        sessions = np.array(["morning", "morning", "afternoon", "afternoon"])
        self.assertEqual(_transitions(events, sessions), [0, 1, 1, 0])
        self.assertIsNone(_independence([9, 0, 0, 0])["p_value"])

    def test_day_record_reconciles_paired_quantiles_and_pit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = pd.DataFrame({
                "TRADING_DATE": [20220104] * 3,
                "session": ["morning", "morning", "afternoon"],
                "timestamp": ["2022-01-04 09:00:00", "2022-01-04 09:01:00", "2022-01-04 13:00:00"],
                "available_at": ["2022-01-04 09:01:00", "2022-01-04 09:02:00", "2022-01-04 13:01:00"],
                "target_timestamp": ["2022-01-04 09:01:00", "2022-01-04 09:02:00", "2022-01-04 13:01:00"],
                "CLOSE_PX": [100.0] * 3,
                "target_log_return": [-2.0, 0.0, 2.0],
                "sigma_ewma": [1.0] * 3,
            })
            for model in ("normal_ewma", "normal_rolling", "empirical_ewma"):
                base[f"{model}_q_low_900"] = -1.0
                base[f"{model}_q_high_900"] = 1.0
            wf = base[list(("TRADING_DATE", "session", "timestamp", "available_at",
                            "target_timestamp", "CLOSE_PX", "target_log_return", "sigma_ewma"))].copy()
            wf["normal_q_low_900"] = -1.0
            wf["normal_q_high_900"] = 1.0
            base_path, wf_path = root / "b.csv", root / "w.csv"
            base.to_csv(base_path, index=False)
            wf.to_csv(wf_path, index=False)
            history = {"normal": [{"refit_day": 20220104, "model": "normal",
                                   "status": "success", "fit": {
                                       "model": "normal", "parameters": {"loc": 0.0, "scale": 1.0},
                                       "center": 0.0, "spread": 1.0, "n_observations": 30,
                                       "log_likelihood": -10.0, "diagnostics": {}}}]}
            result = _day_record(20220104, base_path, wf_path, (0.9,), ("normal",), history, 10)
            self.assertTrue(result["paired"])
            self.assertEqual(result["models"]["normal"]["levels"]["900"]["lower_exceed"], 1)
            self.assertEqual(result["models"]["normal"]["levels"]["900"]["upper_exceed"], 1)
            self.assertEqual(sum(result["models"]["normal"]["pit_histogram"]), 3)
            self.assertAlmostEqual(result["models"]["normal"]["score_sum"],
                                   result["models"]["empirical_ewma"]["score_sum"])
            config = SelectionConfig("TEST", "empirical_ewma", 2, 200, 42, 10, 20250101)
            records = [{**result, "day": 20220104 + index} for index in range(4)]
            report = _report(records, (0.9,), ("normal",), config, {"run_id": "TEST"},
                             {"normal": 0})
            self.assertEqual(report["days"], 4)
            self.assertEqual(report["models"]["normal"]["n"], 12)
            self.assertAlmostEqual(report["models"]["normal"]["levels"]["900"]["observed_coverage"], 1 / 3)
            self.assertEqual(report["block_bootstrap"]["paired_days"], 4)
            wf.loc[1, "target_log_return"] = 9.0
            wf.to_csv(wf_path, index=False)
            with self.assertRaisesRegex(ValueError, "alignment mismatch"):
                _day_record(20220104, base_path, wf_path, (0.9,), ("normal",), history, 10)

    def test_block_bootstrap_is_deterministic_and_holm_adjusted(self) -> None:
        config = SelectionConfig("TEST", "empirical_ewma", 2, 200, 42, 10, 20250101)
        records = [{"day": 20220104 + i, "n": 10, "paired": True,
                    "models": {"empirical_ewma": {"score_sum": 10.0},
                               "normal": {"score_sum": 9.0 + (i % 2) * 0.1},
                               "gh": {"score_sum": 10.0 + (i % 2) * 0.1}}}
                   for i in range(10)]
        first = _bootstrap(records, ("normal", "gh"), "empirical_ewma", config)
        self.assertEqual(first, _bootstrap(records, ("normal", "gh"), "empirical_ewma", config))
        self.assertEqual(first["paired_days"], 10)
        for item in first["comparisons"].values():
            self.assertGreaterEqual(item["p_holm"], item["p_two_sided"])


if __name__ == "__main__":
    unittest.main()
