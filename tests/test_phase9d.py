"""Phase 9D seasonal sigma: causality, factor recovery, locked scope, resume, report."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.phase9d import (Phase9DConfig, bucket_index, run, seasonal_factors,
                                          seasonal_sigma)
from distributional_bands.phase9d_report import run as report_run

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/phase9d_v1.json"
FIT_CONFIG = ROOT / "configs/distribution_fit_v2.json"


def _fixture(root: Path, timeframe: str) -> tuple[Path, Path]:
    rng = np.random.default_rng(90)
    minutes = 1 if timeframe == "1m" else 5
    dates = list(pd.bdate_range(end="2021-12-31", periods=255))
    dates += list(pd.bdate_range("2022-01-03", periods=6))
    dates += [pd.Timestamp("2025-01-02")]
    rows = []
    for day in dates:
        close = 1000.0
        for slot in range(5):
            timestamp = day + pd.Timedelta(hours=9, minutes=slot * minutes)
            actual = float(rng.normal(0, 0.001 * (2.0 if slot >= 3 else 1.0)))
            rows.append({"TRADING_DATE": int(day.strftime("%Y%m%d")), "session": "morning",
                         "timestamp": timestamp, "available_at": timestamp + pd.Timedelta(minutes=minutes),
                         "target_timestamp": timestamp + pd.Timedelta(minutes=minutes),
                         "CLOSE_PX": close, "target_log_return": actual})
            close *= np.exp(actual)
    sample = root / f"samples_{timeframe}.csv"
    pd.DataFrame(rows).to_csv(sample, index=False)
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"output_sha256": {sample.name: sha256_file(sample)}}), encoding="utf-8")
    return sample, manifest


def _small_fit_config(root: Path) -> Path:
    raw = json.loads(FIT_CONFIG.read_text(encoding="utf-8"))
    raw["models"] = ["normal", "student_t"]
    path = root / "fit.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class Phase9DTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Phase9DConfig.from_json(CONFIG)

    def test_scope_is_locked(self) -> None:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        for key, value in (("half_lives_minutes", [30]), ("seasonal_window_days", 60),
                           ("last_development_date", 20251231)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                changed = dict(raw, **{key: value})
                path = Path(folder) / "bad.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "approved scope"):
                    Phase9DConfig.from_json(path)

    def test_bucket_index_rejects_unknown_clock_time(self) -> None:
        times = pd.Series(pd.to_datetime(["2022-01-03 09:01", "2022-01-03 14:29"]))
        self.assertEqual(bucket_index(times, self.config).tolist(), [0, 15])
        with self.assertRaises(ValueError):
            bucket_index(pd.Series(pd.to_datetime(["2022-01-03 12:00"])), self.config)

    def test_seasonal_factors_are_causal_and_recover_ratio(self) -> None:
        rng = np.random.default_rng(1)
        days = np.repeat(np.arange(300), 200)
        buckets = np.tile(np.repeat([0, 1], 100), 300)
        returns = rng.normal(0, 1, len(days)) * np.where(buckets == 1, 2.0, 1.0)
        factors, table, _ = seasonal_factors(days, buckets, returns, self.config)
        self.assertTrue(np.allclose(table[:20], 1.0))
        self.assertAlmostEqual(table[280, 0], np.sqrt(1 / 2.5), delta=0.02)
        self.assertAlmostEqual(table[280, 1], np.sqrt(4 / 2.5), delta=0.02)
        changed = returns.copy()
        changed[days >= 280] *= 50
        _, changed_table, _ = seasonal_factors(days, buckets, changed, self.config)
        np.testing.assert_array_equal(table[:281], changed_table[:281])
        self.assertFalse(np.allclose(table[282], changed_table[282]))
        np.testing.assert_array_equal(factors, table[days, buckets])

    def test_seasonal_sigma_uses_only_prior_bars(self) -> None:
        rng = np.random.default_rng(2)
        returns = rng.normal(0, 0.001, 600)
        factors = np.where(np.arange(600) % 2 == 0, 0.5, 1.5)
        sigma, tilde = seasonal_sigma(returns, factors, 1, 30, self.config)
        np.testing.assert_allclose(sigma, factors * tilde)
        changed = returns.copy()
        changed[400:] = 1.0
        changed_sigma, _ = seasonal_sigma(changed, factors, 1, 30, self.config)
        np.testing.assert_array_equal(sigma[:401], changed_sigma[:401])

    def test_run_resume_report_and_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root, "5m")
            fit = _small_fit_config(root)
            output_root = root / "outputs/phase9d_v1"
            for half_life in (30, 60):
                output = output_root / "5m" / f"hl{half_life}"
                self.assertEqual(run("5m", half_life, CONFIG, fit, sample, manifest, output,
                                     check_only=True)["completed_days"], 0)
                self.assertFalse(output.exists())
                self.assertEqual(run("5m", half_life, CONFIG, fit, sample, manifest, output,
                                     max_days=2)["completed_days"], 2)
                result = run("5m", half_life, CONFIG, fit, sample, manifest, output)
                self.assertTrue(result["complete"])
                self.assertEqual(result["completed_days"], 6)
                self.assertEqual(result, run("5m", half_life, CONFIG, fit, sample, manifest, output))
                self.assertFalse((output / "predictions/20250102.csv").exists())
                prediction = pd.read_csv(output / "predictions/20220103.csv")
                np.testing.assert_allclose(prediction["sigma_ewma"],
                                           prediction["seasonal_factor"] * prediction["sigma_tilde"])
                self.assertGreater(prediction["seasonal_factor"].iloc[-1], prediction["seasonal_factor"].iloc[0])
            reference = root / "outputs/phase7a_v1/5m/hl30"
            shutil.copytree(output_root / "5m/hl30/daily", reference / "daily")
            state = json.loads((output_root / "5m/hl30/latest.json").read_text(encoding="utf-8"))
            (reference / "latest.json").write_text(json.dumps(
                {"complete": True, "completed_days": 6, "daily_sha256": state["daily_sha256"]}), encoding="utf-8")
            report = report_run("5m", CONFIG, fit, sample, manifest, root, output_root)
            self.assertEqual(report["days"], 6)
            self.assertEqual(len(report["tuning_rank_by_mean_pinball"]), 7)
            self.assertIn("30", report["tuning_comparison_within_seasonal"])
            self.assertTrue((output_root / "5m/bucket_coverage.csv").exists())
            report_run("5m", CONFIG, fit, sample, manifest, root, output_root, check_only=True)
            daily = output_root / "5m/hl60/daily/20220104.json"
            with daily.open("a", encoding="utf-8") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError, "Corrupt daily"):
                run("5m", 60, CONFIG, fit, sample, manifest, output_root / "5m/hl60", check_only=True)


class WinRetryTests(unittest.TestCase):
    def test_replace_retries_transient_lock_then_raises_persistent_one(self) -> None:
        from unittest.mock import patch
        from distributional_bands import win_retry
        calls = []

        def flaky(source, target, **_kwargs):
            calls.append((source, target))
            if len(calls) < 3:
                raise PermissionError("locked")

        with patch.object(win_retry, "_replace", flaky), patch.object(win_retry.time, "sleep"):
            win_retry.retrying_replace("a.tmp", "a")
            self.assertEqual(len(calls), 3)
        with patch.object(win_retry, "_replace", side_effect=PermissionError("locked")), \
                patch.object(win_retry.time, "sleep"):
            with self.assertRaises(PermissionError):
                win_retry.retrying_replace("a.tmp", "a")


if __name__ == "__main__":
    unittest.main()
