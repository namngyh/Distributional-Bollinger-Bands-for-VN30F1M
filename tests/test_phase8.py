"""Synthetic final-test policy, causal continuation and checkpoint tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.baseline import _normalized_text_sha256
from distributional_bands.distributions import FitError, FittedDistribution
from distributional_bands.phase8 import Phase8Config, _score_day, run
from distributional_bands.phase8_report import run as report_run


def _fixture(root: Path, timeframe: str):
    minutes = 1 if timeframe == "1m" else 5
    development = [int(day.strftime("%Y%m%d"))
                   for day in pd.bdate_range(end="2024-12-31", periods=68)]
    final = [20250102, 20250103, 20250106, 20260717]
    rows = []
    for day_index, day in enumerate(development + final):
        start = pd.Timestamp(str(day)) + pd.Timedelta(hours=9)
        for slot in range(5):
            timestamp = start + pd.Timedelta(minutes=minutes * slot)
            rows.append({"TRADING_DATE": day, "session": "morning",
                         "timestamp": timestamp, "CLOSE_PX": 1000.0,
                         "available_at": timestamp + pd.Timedelta(minutes=minutes),
                         "target_timestamp": timestamp + pd.Timedelta(minutes=minutes),
                         "target_log_return": 0.0002 * (1 if (day_index + slot) % 2 else -1)
                                              + 0.00001 * slot})
    sample_path = root / f"samples_{timeframe}.csv"
    pd.DataFrame(rows).to_csv(sample_path, index=False)
    params = {"weight_1": 0.5, "weight_2": 0.5,
              "mean_1": -0.5, "mean_2": 0.5, "sigma_1": 1.0, "sigma_2": 1.0}
    fitted = FittedDistribution("normal_mixture_2", params, 0.0, 1.0, 100, -1.0, {})
    history = [{"status": "success", "refit_day": development[-2],
                "train_last": development[-3], "fit": fitted.as_dict(),
                "quantiles": {}}]
    source_dir = root / "phase7a"
    source_dir.mkdir()
    b_dir = root / "phase7b"
    (b_dir / "pits").mkdir(parents=True)
    for index, day in enumerate(development):
        np.save(b_dir / "pits" / f"{day}.npy",
                np.linspace(0.002, 0.998, len(development) * 5)[index * 5:(index + 1) * 5])
    return sample_path, source_dir, b_dir, {"fit_history": history}, development, final, fitted


class Phase8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.config_path = cls.repo / "configs/phase8_v1.json"
        cls.fit_path = cls.repo / "configs/distribution_fit_v2.json"

    def test_locked_policy_and_score(self):
        config = Phase8Config.from_json(self.config_path)
        self.assertEqual(config.locked_models["1m"], "empirical_ewma")
        self.assertEqual(config.locked_models["5m"], "normal_mixture_2_pit_calibrated")
        self.assertEqual(config.final_test_start, 20250101)
        frame = pd.DataFrame({"target_log_return": [0.0, 0.1], "session": ["a", "a"]})
        for level in config.central_coverages:
            tag = str(round(level * 1000))
            frame[f"empirical_ewma_q_low_{tag}"] = -0.05
            frame[f"empirical_ewma_q_high_{tag}"] = 0.05
        score = _score_day(20250102, frame, ("empirical_ewma",), config)
        self.assertEqual(score["models"]["empirical_ewma"]["levels"]["950"]["upper_exceed"], 1)
        self.assertGreater(score["models"]["empirical_ewma"]["score_sum"], 0)

    def test_one_minute_resume_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, a_dir, b_dir, a_state, dev, final, _ = _fixture(root, "1m")
            output = root / "out"
            args = ("1m", self.config_path, self.fit_path, sample, root / "manifest.json",
                    a_dir, root / "a_report.json", b_dir, root / "b_report.json", output)
            signature = {"experiment_id": "PHASE8-V1", "run_id": "PHASE8-V1-1m",
                         "timeframe": "1m"}
            a_state["signature"] = {"fit_config_sha256": _normalized_text_sha256(self.fit_path)}
            with (patch("distributional_bands.phase8._lineage",
                        return_value=(a_state, {}, dev)),
                  patch("distributional_bands.phase8._signature", return_value=signature)):
                first = run(*args, max_days=1)
                self.assertEqual(first["completed_days"], 1)
                first_hash = sha256_file(output / "predictions" / f"{final[0]}.csv")
                second = run(*args, max_days=1)
                self.assertEqual(second["completed_days"], 2)
                self.assertEqual(first_hash, sha256_file(output / "predictions" / f"{final[0]}.csv"))
                self.assertEqual(run(*args, check_only=True)["completed_days"], 2)
                result = run(*args)
                self.assertTrue(result["complete"])
                self.assertEqual(result["completed_days"], 4)
                (root / "b_report.json").write_text("{}", encoding="utf-8")
                with (patch("distributional_bands.phase8_report._lineage",
                            return_value=(a_state, {}, dev)),
                      patch("distributional_bands.phase8_report._signature",
                            return_value=signature)):
                    report = report_run(*args)
                    self.assertEqual(report["days"], 4)
                    self.assertEqual(report["selected_model"], "empirical_ewma")
                    report_run(*args, check_only=True)
                self.assertFalse((output / "pits" / f"{final[0]}.npy").exists())
                self.assertIn("empirical_ewma_q_low_950",
                              pd.read_csv(output / "predictions" / f"{final[0]}.csv"))
                (output / "daily" / f"{final[0]}.json").write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Corrupt Phase 8"):
                    run(*args, check_only=True)

    def test_five_minute_past_pit_and_continued_refit_cadence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, a_dir, b_dir, a_state, dev, final, fitted = _fixture(root, "5m")
            output = root / "out"
            args = ("5m", self.config_path, self.fit_path, sample, root / "manifest.json",
                    a_dir, root / "a_report.json", b_dir, root / "b_report.json", output)
            signature = {"experiment_id": "PHASE8-V1", "run_id": "PHASE8-V1-5m",
                         "timeframe": "5m"}
            a_state["signature"] = {"fit_config_sha256": _normalized_text_sha256(self.fit_path)}
            with (patch("distributional_bands.phase8._lineage",
                        return_value=(a_state, {}, dev)),
                  patch("distributional_bands.phase8._signature", return_value=signature),
                  patch("distributional_bands.phase8.fit_distribution",
                        return_value=fitted) as fit):
                run(*args, max_days=1)
                first_daily = json.loads((output / "daily" / f"{final[0]}.json").read_text())
                self.assertEqual(set(first_daily["models"]),
                                 {"empirical_ewma", "normal_mixture_2_pit_calibrated"})
                fit.assert_not_called()
                run(*args, max_days=1)
                fit.assert_not_called()
                result = run(*args, max_days=1)
                self.assertEqual(result["fit_attempts"], 1)
                fit.assert_called_once()
                checkpoint = json.loads((output / "latest.json").read_text())
                self.assertEqual(checkpoint["fit_history"][0]["refit_day"], final[2])
                self.assertEqual(checkpoint["fit_history"][0]["train_last"], final[1])
                self.assertEqual(len(checkpoint["pit_sha256"]), 3)
                self.assertEqual(run(*args, check_only=True)["completed_days"], 3)
                self.assertTrue(run(*args)["complete"])
                (root / "b_report.json").write_text("{}", encoding="utf-8")
                with (patch("distributional_bands.phase8_report._lineage",
                            return_value=(a_state, {}, dev)),
                      patch("distributional_bands.phase8_report._signature",
                            return_value=signature)):
                    report = report_run(*args)
                    self.assertEqual(report["days"], 4)
                    self.assertEqual(report["selected_model"],
                                     "normal_mixture_2_pit_calibrated")
                    self.assertIn("empirical_ewma", report["periods"]["all_final"])

    def test_five_minute_fit_failure_keeps_checkpoint_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, a_dir, b_dir, a_state, dev, final, _ = _fixture(root, "5m")
            a_state["signature"] = {"fit_config_sha256": _normalized_text_sha256(self.fit_path)}
            output = root / "out"
            args = ("5m", self.config_path, self.fit_path, sample, root / "manifest.json",
                    a_dir, root / "a_report.json", b_dir, root / "b_report.json", output)
            signature = {"experiment_id": "PHASE8-V1", "run_id": "PHASE8-V1-5m",
                         "timeframe": "5m"}
            with (patch("distributional_bands.phase8._lineage",
                        return_value=(a_state, {}, dev)),
                  patch("distributional_bands.phase8._signature", return_value=signature),
                  patch("distributional_bands.phase8.fit_distribution",
                        side_effect=FitError("synthetic failure"))):
                run(*args, max_days=2)
                with self.assertRaisesRegex(ValueError, "no fallback"):
                    run(*args, max_days=1)
                checkpoint = json.loads((output / "latest.json").read_text())
                self.assertEqual(checkpoint["completed_days"], 2)
                self.assertEqual(checkpoint["last_day"], final[1])
                self.assertEqual(checkpoint["refit_day"], final[2])
                self.assertEqual(checkpoint["fit_history"][0]["status"], "failed")
                self.assertFalse((output / "predictions" / f"{final[2]}.csv").exists())
                self.assertEqual(run(*args, check_only=True)["completed_days"], 2)


if __name__ == "__main__":
    unittest.main()
