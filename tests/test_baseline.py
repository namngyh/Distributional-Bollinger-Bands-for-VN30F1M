import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.baseline import run
from distributional_bands.data import sha256_file


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.input = self.root / "samples_1m.csv"
        self.config = self.root / "baseline.json"
        self.data_manifest = self.root / "data_manifest.json"
        rows = []
        for day_number, day in enumerate((20260102, 20260103, 20260104, 20260105)):
            for minute in range(6):
                timestamp = pd.Timestamp(str(day)) + pd.Timedelta(hours=9, minutes=minute)
                rows.append({
                    "TRADING_DATE": day,
                    "session": "morning",
                    "timestamp": timestamp,
                    "CLOSE_PX": 100 + day_number + minute / 10,
                    "available_at": timestamp + pd.Timedelta(minutes=1),
                    "target_timestamp": timestamp + pd.Timedelta(minutes=1),
                    "target_log_return": (minute + 1) * (1 if day_number % 2 else -1) / 1000,
                })
        self.samples = pd.DataFrame(rows)
        self._write_input()
        self.config.write_text(json.dumps({
            "experiment_id": "TEST-BASELINE",
            "prediction_start": 20260102,
            "last_development_date": 20260105,
            "ewma_half_life_minutes": 2,
            "rolling_window_minutes": 2,
            "empirical_window_days": 2,
            "empirical_min_days": 1,
            "central_coverages": [0.9, 0.95],
        }), encoding="utf-8")

    def _write_input(self):
        self.samples.to_csv(self.input, index=False)
        self.data_manifest.write_text(json.dumps({
            "output_sha256": {"samples_1m.csv": sha256_file(self.input)}
        }), encoding="utf-8")

    def _run(self, destination, max_days=None):
        with redirect_stdout(io.StringIO()):
            return run(self.config, self.input, self.data_manifest,
                       destination, "1m", max_days=max_days)

    def test_interrupted_resume_matches_uninterrupted_run(self):
        resumed = self.root / "resumed"
        full = self.root / "full"
        partial = self._run(resumed, max_days=2)
        self.assertEqual(partial["completed_days"], 2)
        self.assertFalse((resumed / "metrics.json").exists())
        final_resumed = self._run(resumed)
        final_full = self._run(full)
        self.assertEqual(final_resumed, final_full)
        self.assertTrue((resumed / "metrics.json").exists())
        self.assertEqual(
            json.loads((resumed / "latest.json").read_text(encoding="utf-8"))["prediction_sha256"],
            json.loads((full / "latest.json").read_text(encoding="utf-8"))["prediction_sha256"],
        )
        self.assertIn("normal_ewma:900", final_full["scores"])
        self.assertIn("empirical_ewma:900", final_full["scores"])
        forecast = pd.read_csv(full / "predictions" / "20260103.csv").iloc[0]
        self.assertAlmostEqual(
            forecast.normal_ewma_price_low_900,
            forecast.CLOSE_PX * np.exp(forecast.normal_ewma_q_low_900),
        )
        self.assertLess(forecast.normal_ewma_price_low_900,
                        forecast.normal_ewma_price_high_900)

    def test_current_target_cannot_change_its_own_forecast(self):
        original = self.root / "original"
        self._run(original, max_days=1)
        before = pd.read_csv(original / "predictions" / "20260102.csv")
        changed_index = self.samples.index[self.samples.TRADING_DATE.eq(20260102)][2]
        self.samples.loc[changed_index, "target_log_return"] = 0.5
        self._write_input()
        changed = self.root / "changed"
        self._run(changed, max_days=1)
        after = pd.read_csv(changed / "predictions" / "20260102.csv")
        self.assertEqual(before.loc[0, "normal_ewma_q_low_900"],
                         after.loc[0, "normal_ewma_q_low_900"])
        self.assertEqual(before.loc[0, "normal_rolling_q_high_950"],
                         after.loc[0, "normal_rolling_q_high_950"])
        self.assertNotEqual(before.loc[1, "normal_ewma_q_low_900"],
                            after.loc[1, "normal_ewma_q_low_900"])

    def test_changed_input_cannot_resume_existing_run(self):
        destination = self.root / "run"
        self._run(destination, max_days=1)
        self.samples.loc[0, "target_log_return"] = 0.2
        self._write_input()
        with self.assertRaisesRegex(ValueError, "different input, config or code"):
            self._run(destination)

    def test_resume_reuses_matching_orphan_day_and_rejects_corruption(self):
        destination = self.root / "orphan"
        self._run(destination, max_days=1)
        prior_checkpoint = (destination / "latest.json").read_bytes()
        self._run(destination, max_days=1)
        self.assertTrue((destination / "predictions" / "20260103.csv").exists())
        (destination / "latest.json").write_bytes(prior_checkpoint)
        self._run(destination, max_days=1)
        state = json.loads((destination / "latest.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_day"], 20260103)
        (destination / "predictions" / "20260103.csv").write_text("corrupt", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing or corrupt"):
            self._run(destination)

    def test_final_test_rows_are_excluded_by_config(self):
        self.samples.loc[self.samples.TRADING_DATE.eq(20260105), "target_log_return"] = 9.0
        self._write_input()
        raw = json.loads(self.config.read_text(encoding="utf-8"))
        raw["last_development_date"] = 20260104
        self.config.write_text(json.dumps(raw), encoding="utf-8")
        summary = self._run(self.root / "development")
        self.assertEqual(summary["last_day"], 20260104)
        self.assertFalse((self.root / "development" / "predictions" / "20260105.csv").exists())


if __name__ == "__main__":
    unittest.main()
