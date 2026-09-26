"""Phase 9C: locked scope, exploratory-period run, resume and descriptive report."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.phase9c import Phase9CConfig, report_run, run

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/phase9c_v1.json"
FIT_CONFIG = ROOT / "configs/distribution_fit_v2.json"


def _fixture(root: Path) -> tuple[Path, Path]:
    rng = np.random.default_rng(91)
    dates = list(pd.bdate_range(end="2024-12-31", periods=255)) + list(pd.bdate_range("2025-01-02", periods=6))
    rows = []
    for day in dates:
        close = 1000.0
        for slot in range(5):
            timestamp = day + pd.Timedelta(hours=9, minutes=slot * 5)
            actual = float(rng.normal(0, 0.001))
            rows.append({"TRADING_DATE": int(day.strftime("%Y%m%d")), "session": "morning",
                         "timestamp": timestamp, "available_at": timestamp + pd.Timedelta(minutes=5),
                         "target_timestamp": timestamp + pd.Timedelta(minutes=5),
                         "CLOSE_PX": close, "target_log_return": actual})
            close *= np.exp(actual)
    sample = root / "samples_5m.csv"
    pd.DataFrame(rows).to_csv(sample, index=False)
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"output_sha256": {sample.name: sha256_file(sample)}}), encoding="utf-8")
    return sample, manifest


class Phase9CTests(unittest.TestCase):
    def test_scope_is_locked(self) -> None:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(dict(raw, half_life_by_timeframe={"1m": 60, "5m": 60})), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "approved scope"):
                Phase9CConfig.from_json(path)

    def test_run_resume_and_descriptive_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root)
            fit = root / "fit.json"
            raw = json.loads(FIT_CONFIG.read_text(encoding="utf-8"))
            fit.write_text(json.dumps(dict(raw, models=["normal", "student_t"])), encoding="utf-8")
            output = root / "outputs/phase9c_v1/5m"
            self.assertEqual(run("5m", CONFIG, fit, sample, manifest, output, max_days=2)["completed_days"], 2)
            result = run("5m", CONFIG, fit, sample, manifest, output)
            self.assertTrue(result["complete"])
            self.assertEqual(result["completed_days"], 6)
            self.assertIn("2025-2026", result["note"])
            reference = root / "outputs/phase8_v1/5m"
            shutil.copytree(output / "daily", reference / "daily")
            state = json.loads((output / "latest.json").read_text(encoding="utf-8"))
            (reference / "latest.json").write_text(json.dumps(
                {"complete": True, "completed_days": 6, "daily_sha256": state["daily_sha256"]}), encoding="utf-8")
            development = {"periods": {"all_development": {
                f"{m}_hl60_seasonal": {"mean_pinball_equal_weight": value}
                for m, value in (("empirical_ewma", 1.0), ("normal", 1.2), ("student_t", 0.9))}}}
            dev_path = root / "outputs/phase9d_v1/5m/report.json"
            dev_path.parent.mkdir(parents=True)
            dev_path.write_text(json.dumps(development), encoding="utf-8")
            report = report_run("5m", CONFIG, fit, sample, manifest, root, output)
            self.assertEqual(report["days"], 6)
            self.assertEqual(report["first_day"], 20250102)
            self.assertIsNotNone(report["development_vs_final_rank_correlation"])
            report_run("5m", CONFIG, fit, sample, manifest, root, output, check_only=True)


if __name__ == "__main__":
    unittest.main()
