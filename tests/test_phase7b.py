"""Phase 7B causal calibration, source integrity, checkpoint and report tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.distributions import FittedDistribution
from distributional_bands.phase7a import Phase7AConfig, _day_scores as source_scores
from distributional_bands.phase7b import (Phase7BConfig, _calibration_map,
                                          _raw_pit, _source, run)
from distributional_bands.phase7b_report import run as report_run


def _fixture(root: Path, source_config: Path, *, changed_day: int | None = None):
    source_dir = root / "source"
    (source_dir / "predictions").mkdir(parents=True)
    (source_dir / "daily").mkdir()
    days = [20220103, 20220104, 20220105, 20220106, 20220107, 20220110]
    parameters = {f"weight_{i}": 1 / 3 for i in (1, 2, 3)}
    parameters.update({f"mean_{i}": 0.0 for i in (1, 2, 3)})
    parameters.update({f"sigma_{i}": 1.0 for i in (1, 2, 3)})
    fitted = FittedDistribution("normal_mixture_3", parameters, 0.0, 1.0, 80, -1.0, {})
    status = {"status": "success", "fit": fitted.as_dict()}
    source_policy = Phase7AConfig.from_json(source_config)
    prediction_hashes, daily_hashes = {}, {}
    for index, day in enumerate(days):
        date = pd.Timestamp(str(day))
        targets = [0.0001 * (index + 1), -0.0002 * (index + 1)]
        if day == changed_day:
            targets[0] = 0.01
        rows = []
        for slot in range(2):
            timestamp = date + pd.Timedelta(hours=9, minutes=slot)
            row = {"TRADING_DATE": day, "session": "morning", "timestamp": timestamp,
                   "available_at": timestamp + pd.Timedelta(minutes=1),
                   "target_timestamp": timestamp + pd.Timedelta(minutes=1),
                   "CLOSE_PX": 1000.0, "target_log_return": targets[slot],
                   "sigma_ewma": 0.001}
            for model in ("empirical_ewma", "normal_mixture_3"):
                for level in source_policy.central_coverages:
                    tag = str(round(level * 1000))
                    row[f"{model}_q_low_{tag}"] = -0.002
                    row[f"{model}_q_high_{tag}"] = 0.002
            rows.append(row)
        frame = pd.DataFrame(rows)
        prediction = source_dir / "predictions" / f"{day}.csv"
        frame.to_csv(prediction, index=False)
        daily = source_dir / "daily" / f"{day}.json"
        daily.write_text(json.dumps(source_scores(day, frame, source_policy,
                                                 "normal_mixture_3", status)), encoding="utf-8")
        prediction_hashes[str(day)] = sha256_file(prediction)
        daily_hashes[str(day)] = sha256_file(daily)
    state = {
        "signature": {"run_id": "PHASE7A-V1-1m-HL30", "half_life_minutes": 30},
        "complete": True, "completed_days": len(days),
        "prediction_sha256": prediction_hashes, "daily_sha256": daily_hashes,
        "fit_history": [{"refit_day": days[0], "train_last": 20211231,
                         "status": "success", "fit": fitted.as_dict()}],
    }
    (source_dir / "latest.json").write_text(json.dumps(state), encoding="utf-8")
    report = root / "source_report.json"
    report.write_text(json.dumps({"complete": True}), encoding="utf-8")
    return source_dir, report, state, days


class Phase7BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo = Path(__file__).resolve().parents[1]
        cls.config_path = repo / "configs/phase7b_v1.json"
        cls.source_config_path = repo / "configs/phase7a_v1.json"

    def test_policy_and_past_only_probability_map(self) -> None:
        config = Phase7BConfig.from_json(self.config_path)
        self.assertEqual(config.warmup_days, 60)
        self.assertEqual(config.final_test_start, 20250101)
        parameters = {f"weight_{i}": 1 / 3 for i in (1, 2, 3)}
        parameters.update({f"mean_{i}": 0.0 for i in (1, 2, 3)})
        parameters.update({f"sigma_{i}": 1.0 for i in (1, 2, 3)})
        fit = FittedDistribution("normal_mixture_3", parameters, 0.0, 1.0, 100, -1.0, {})
        past = np.linspace(0.01, 0.99, 200)
        bands, mapping = _calibration_map(past, fit, config)
        self.assertLess(bands["950"][0], bands["900"][0])
        self.assertGreater(bands["950"][1], bands["900"][1])
        self.assertEqual(len(mapping), 10)
        day = pd.DataFrame({"target_log_return": [0.0], "sigma_ewma": [1.0]})
        self.assertTrue(np.isfinite(_raw_pit(fit, day, 20220103)).all())

    def test_final_test_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source_dir = root / "source"
            source_dir.mkdir()
            signature = {"run_id": "PHASE7A-V1-1m-HL30", "half_life_minutes": 30}
            days = [20220101 + index for index in range(747)] + [20250102]
            hashes = {str(day): "synthetic" for day in days}
            state = {"signature": signature, "complete": True, "completed_days": 748,
                     "prediction_sha256": hashes, "daily_sha256": hashes,
                     "fit_history": [{"status": "success", "refit_day": 20220101,
                                      "train_last": 20211231}]}
            latest = source_dir / "latest.json"
            latest.write_text(json.dumps(state), encoding="utf-8")
            (source_dir / "run_manifest.json").write_text(
                json.dumps({"signature": signature}), encoding="utf-8")
            (source_dir / "metrics.json").write_text(
                json.dumps({"signature": signature, "complete": True, "fit_failures": 0}),
                encoding="utf-8")
            source_report = root / "report.json"
            source_report.write_text(json.dumps({
                "complete": True, "timeframe": "1m", "days": 748,
                "last_day": 20250102,
                "signature": {"trial_checkpoint_sha256": {"30": sha256_file(latest)}},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "causal Phase 7A"):
                _source(Phase7BConfig.from_json(self.config_path), "1m",
                        source_dir, source_report)

    def test_checkpoint_resume_report_and_corruption_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source_dir, source_report, state, days = _fixture(root, self.source_config_path)
            config = replace(Phase7BConfig.from_json(self.config_path), warmup_days=2)
            output = root / "calibrated"
            args = ("1m", self.config_path, source_dir, source_report, output)
            with patch("distributional_bands.phase7b.Phase7BConfig.from_json", return_value=config), \
                 patch("distributional_bands.phase7b._source", return_value=(state, days)):
                self.assertEqual(run(*args, check_only=True)["completed_days"], 0)
                self.assertFalse(output.exists())
                self.assertEqual(run(*args, max_days=3)["completed_days"], 3)
                first_prediction = output / "predictions" / "20220105.csv"
                saved_hash = sha256_file(first_prediction)
                self.assertTrue(run(*args)["complete"])
                self.assertEqual(sha256_file(first_prediction), saved_hash)
                self.assertEqual(run(*args)["calibrated_days"], 4)
                (output / "metrics.json").unlink()
                self.assertEqual(run(*args)["calibrated_days"], 4)
                self.assertTrue((output / "metrics.json").exists())
                self.assertEqual(run(*args, check_only=True)["completed_days"], 6)
                with patch("distributional_bands.phase7b_report._source",
                           return_value=(state, days)):
                    report = report_run(*args)
                    self.assertEqual(report["scored_days"], 4)
                    self.assertEqual(report, report_run(*args, check_only=True))
                with (output / "pits" / "20220103.npy").open("ab") as stream:
                    stream.write(b"x")
                with self.assertRaisesRegex(ValueError, "Corrupt Phase 7B pits"):
                    run(*args, check_only=True)

    def test_current_target_cannot_change_its_calibrated_band(self) -> None:
        q_columns = [f"normal_mixture_3_pit_calibrated_q_{side}_950"
                     for side in ("low", "high")]
        forecasts = []
        for change in (None, 20220105):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source_dir, source_report, state, days = _fixture(
                    root, self.source_config_path, changed_day=change)
                config = replace(Phase7BConfig.from_json(self.config_path), warmup_days=2)
                with patch("distributional_bands.phase7b.Phase7BConfig.from_json",
                           return_value=config), \
                     patch("distributional_bands.phase7b._source", return_value=(state, days)):
                    run("1m", self.config_path, source_dir, source_report,
                        root / "calibrated", max_days=3)
                forecasts.append(pd.read_csv(root / "calibrated/predictions/20220105.csv")
                                 [q_columns].to_numpy())
        np.testing.assert_array_equal(forecasts[0], forecasts[1])


if __name__ == "__main__":
    unittest.main()
