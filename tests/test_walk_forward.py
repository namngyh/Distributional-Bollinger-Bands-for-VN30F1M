"""Synthetic chronological/checkpoint checks; never run the full dataset."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.distributions import FitError
from distributional_bands.walk_forward import (
    WalkForwardConfig, _ewma_sigma, _training_residuals, run,
)


def _fixture(root: Path, timeframe: str) -> tuple[Path, Path, Path, Path]:
    minutes = 1 if timeframe == "1m" else 5
    rng = np.random.default_rng(308)
    records = []
    for date in list(pd.bdate_range("2021-12-27", periods=9)) + [pd.Timestamp("2025-01-02")]:
        start = date + pd.Timedelta(hours=9)
        current_close = 1000.0
        for slot in range(12):
            timestamp = start + pd.Timedelta(minutes=slot * minutes)
            actual = float(rng.normal(0, 0.001 * np.sqrt(minutes)))
            records.append({
                "TRADING_DATE": int(date.strftime("%Y%m%d")),
                "session": "morning",
                "timestamp": timestamp,
                "CLOSE_PX": current_close,
                "available_at": timestamp + pd.Timedelta(minutes=minutes),
                "target_timestamp": timestamp + pd.Timedelta(minutes=minutes),
                "target_log_return": actual,
            })
            current_close *= np.exp(actual)
    input_path = root / f"samples_{timeframe}.csv"
    pd.DataFrame.from_records(records).to_csv(input_path, index=False)
    data_manifest = root / "manifest.json"
    data_manifest.write_text(json.dumps({"output_sha256": {input_path.name: sha256_file(input_path)}}),
                             encoding="utf-8")
    config = root / "walk.json"
    config.write_text(json.dumps({
        "experiment_id": "TEST-WF", "prediction_start": 20220103,
        "last_development_date": 20241231,
        "ewma_half_life_minutes": 20, "rolling_window_minutes": 20,
        "fit_window_days": 3, "refit_every_days": 2,
        "central_coverages": [0.9, 0.99],
        "primary_metric": "mean_pinball_equal_weight_over_coverages",
        "failed_fit_policy": "record_failure_and_skip_model_until_next_refit",
    }), encoding="utf-8")
    fit_config = root / "fit.json"
    fit_config.write_text(json.dumps({
        "experiment_id": "TEST-FIT", "models": ["normal", "student_t"],
        "min_observations": 20, "mle_max_iter": 70, "mle_starts": 2,
        "mixture_max_iter": 50, "mixture_starts": 2,
        "mixture_tolerance": 1e-5, "mixture_variance_floor": 1e-4,
        "mixture_weight_floor": 0.01, "seed": 301,
    }), encoding="utf-8")
    return config, fit_config, input_path, data_manifest


class WalkForwardTests(unittest.TestCase):
    def test_current_target_does_not_change_its_forecast_sigma(self) -> None:
        config = WalkForwardConfig(
            "TEST", 20220103, 20241231, 20, 20, 3, 2,
            (0.9,), "mean_pinball_equal_weight_over_coverages",
            "record_failure_and_skip_model_until_next_refit",
        )
        actual = np.array([0.1, -0.2, 0.3, 0.2, -0.1, 0.05, 0.03])
        before = _ewma_sigma(actual, 5, config)
        changed = actual.copy()
        changed[5] = 100.0
        after = _ewma_sigma(changed, 5, config)
        np.testing.assert_allclose(before[:6], after[:6], equal_nan=True)
        self.assertNotEqual(before[6], after[6])

    def test_training_window_excludes_forecast_day(self) -> None:
        frames = [(i, pd.DataFrame(index=[i * 2, i * 2 + 1])) for i in range(5)]
        residuals = np.arange(10, dtype=float)
        np.testing.assert_array_equal(_training_residuals(frames, 3, residuals, 2), [2, 3, 4, 5])
        changed = residuals.copy()
        changed[6:] = 1000
        np.testing.assert_array_equal(_training_residuals(frames, 3, changed, 2), [2, 3, 4, 5])

    def test_check_only_resume_and_completion_match_uninterrupted(self) -> None:
        for timeframe in ("1m", "5m"):
            with self.subTest(timeframe=timeframe), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                config, fit, sample, manifest = _fixture(root, timeframe)
                resumed = root / "resumed"
                untouched = run(config, fit, sample, manifest, resumed, timeframe, check_only=True)
                self.assertEqual(untouched["completed_days"], 0)
                self.assertFalse(resumed.exists())
                first = run(config, fit, sample, manifest, resumed, timeframe, max_days=1)
                self.assertEqual(first["completed_days"], 1)
                checkpoint = json.loads((resumed / "latest.json").read_text(encoding="utf-8"))
                self.assertEqual(checkpoint["fit_history"][0]["train_last"], 20211231)
                self.assertEqual(checkpoint["completed_days"], 1)
                completed = run(config, fit, sample, manifest, resumed, timeframe)
                continuous = run(config, fit, sample, manifest, root / "continuous", timeframe)
                self.assertTrue(completed["complete"])
                self.assertEqual(completed["completed_days"], 4)
                self.assertEqual(completed["scores"], continuous["scores"])
                self.assertEqual(completed["paired_scores"], completed["scores"])
                self.assertEqual(len(completed["paired_pinball_ranking"]), 2)
                self.assertEqual(completed["last_day"], 20220106)
                self.assertEqual(run(config, fit, sample, manifest, resumed, timeframe)["scores"],
                                 completed["scores"])
                self.assertEqual(len(list((resumed / "predictions").glob("*.csv"))), 4)
                self.assertTrue((resumed / "fit_history.json").exists())
                history = json.loads((resumed / "fit_history.json").read_text(encoding="utf-8"))
                self.assertIn("parameters", history["fit_history"][0]["fit"])

    def test_fit_failure_is_recorded_without_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config, fit, sample, manifest = _fixture(root, "1m")
            from distributional_bands.walk_forward import fit_distribution as original_fit

            def selected_failure(model, residuals, settings):
                if model == "student_t":
                    raise FitError("forced numerical failure")
                return original_fit(model, residuals, settings)

            with patch("distributional_bands.walk_forward.fit_distribution", side_effect=selected_failure):
                summary = run(config, fit, sample, manifest, root / "out", "1m", max_days=1)
            self.assertEqual(summary["fit_failures"]["student_t"], 1)
            self.assertIn("normal:900", summary["scores"])
            self.assertNotIn("student_t:900", summary["scores"])
            self.assertEqual(summary["paired_scores"], {})
            latest = json.loads((root / "out" / "latest.json").read_text(encoding="utf-8"))
            self.assertIn("forced numerical failure", latest["fit_status"]["student_t"]["reason"])

    def test_corrupt_prediction_and_changed_config_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config, fit, sample, manifest = _fixture(root, "1m")
            output = root / "out"
            run(config, fit, sample, manifest, output, "1m", max_days=1)
            file_path = next((output / "predictions").glob("*.csv"))
            file_path.write_text("corrupt", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corrupt"):
                run(config, fit, sample, manifest, output, "1m", check_only=True)
            changed = json.loads(config.read_text(encoding="utf-8"))
            changed["fit_window_days"] = 2
            config.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different dataset, config or source"):
                run(config, fit, sample, manifest, output, "1m", check_only=True)

    def test_mid_refit_checkpoint_and_orphan_day_resume(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config, fit, sample, manifest = _fixture(root, "1m")
            output = root / "interrupted"
            from distributional_bands.walk_forward import fit_distribution as original_fit

            def stop_during_fit(model, residuals, settings):
                if model == "student_t":
                    raise KeyboardInterrupt()
                return original_fit(model, residuals, settings)

            with patch("distributional_bands.walk_forward.fit_distribution", side_effect=stop_during_fit):
                with self.assertRaises(KeyboardInterrupt):
                    run(config, fit, sample, manifest, output, "1m", max_days=1)
            checkpoint = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(checkpoint["fit_status"]), {"normal"})
            self.assertEqual(checkpoint["completed_days"], 0)
            with patch("distributional_bands.walk_forward.fit_distribution", wraps=original_fit) as fitting:
                run(config, fit, sample, manifest, output, "1m", max_days=1)
                self.assertEqual([call.args[0] for call in fitting.call_args_list], ["student_t"])

            complete_output = root / "complete"
            run(config, fit, sample, manifest, complete_output, "1m")
            orphan = complete_output / "predictions" / "20220104.csv"
            shutil.copyfile(orphan, output / "predictions" / orphan.name)
            resumed = run(config, fit, sample, manifest, output, "1m")
            self.assertTrue(resumed["complete"])
            self.assertEqual(resumed["scores"],
                             json.loads((complete_output / "metrics.json").read_text(encoding="utf-8"))["scores"])


if __name__ == "__main__":
    unittest.main()
