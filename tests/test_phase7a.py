"""Bounded Phase 7A chronology, integrity and resume tests."""

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
from distributional_bands.distributions import FitError, FittedDistribution
from distributional_bands.phase7a import (Phase7AConfig, _day_scores,
                                          _empirical_quantiles, run)
from distributional_bands.phase7a_migrate import (LEGACY_PHASE7A_SHA256,
                                                  migrate_trial)
from distributional_bands import phase7a_migrate as migration_module
from distributional_bands.phase7a_report import _model_stats, run as report_run


def _fixture(root: Path, timeframe: str) -> tuple[Path, Path]:
    rng = np.random.default_rng(70)
    minutes = 1 if timeframe == "1m" else 5
    dates = list(pd.bdate_range(end="2021-12-31", periods=65))
    dates += list(pd.bdate_range("2022-01-03", periods=6))
    dates += [pd.Timestamp("2025-01-02")]
    rows = []
    for day in dates:
        close = 1000.0
        for slot in range(5):
            timestamp = day + pd.Timedelta(hours=9, minutes=slot * minutes)
            actual = float(rng.normal(0, 0.001))
            rows.append({
                "TRADING_DATE": int(day.strftime("%Y%m%d")), "session": "morning",
                "timestamp": timestamp, "available_at": timestamp + pd.Timedelta(minutes=minutes),
                "target_timestamp": timestamp + pd.Timedelta(minutes=minutes),
                "CLOSE_PX": close, "target_log_return": actual,
            })
            close *= np.exp(actual)
    sample = root / f"samples_{timeframe}.csv"
    pd.DataFrame(rows).to_csv(sample, index=False)
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"output_sha256": {sample.name: sha256_file(sample)}}),
                        encoding="utf-8")
    return sample, manifest


def _fake_fit(model: str, train: np.ndarray, _config) -> FittedDistribution:
    count = int(model.rsplit("_", 1)[1])
    parameters = {f"weight_{i}": 1 / count for i in range(1, count + 1)}
    parameters.update({f"mean_{i}": 0.0 for i in range(1, count + 1)})
    parameters.update({f"sigma_{i}": 1.0 for i in range(1, count + 1)})
    return FittedDistribution(model, parameters, 0.0, 1.0, len(train), -1.0, {})


class Phase7ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = Path(__file__).resolve().parents[1] / "configs/phase7a_v1.json"
        cls.fit_config = Path(__file__).resolve().parents[1] / "configs/distribution_fit_v2.json"

    def test_policy_is_locked_and_anchor_cannot_be_rerun(self) -> None:
        config = Phase7AConfig.from_json(self.config)
        self.assertEqual(config.half_lives_minutes, (30, 60, 120))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root, "1m")
            with self.assertRaisesRegex(ValueError, "anchor must be reused"):
                run("1m", 60, self.config, self.fit_config, sample, manifest,
                    Path(folder) / "out")
            changed = json.loads(self.config.read_text(encoding="utf-8"))
            changed["last_development_date"] = 20251231
            changed["final_test_start"] = 20260101
            path = root / "bad.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "approved scope"):
                Phase7AConfig.from_json(path)

    def test_empirical_quantile_uses_only_prior_days(self) -> None:
        config = Phase7AConfig.from_json(self.config)
        grouped = [(day, pd.DataFrame(index=[2 * day, 2 * day + 1])) for day in range(65)]
        residuals = np.arange(130, dtype=float)
        before = _empirical_quantiles(grouped, 60, residuals, config)
        changed = residuals.copy()
        changed[120:] = 10000
        self.assertEqual(before, _empirical_quantiles(grouped, 60, changed, config))

    def test_checkpoint_resume_and_final_test_exclusion(self) -> None:
        for tf, half_life in (("1m", 30), ("5m", 120)):
            with self.subTest(tf=tf), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                sample, manifest = _fixture(root, tf)
                output = root / "trial"
                with patch("distributional_bands.phase7a.fit_distribution", side_effect=_fake_fit):
                    self.assertEqual(run(tf, half_life, self.config, self.fit_config, sample,
                                         manifest, output, check_only=True)["completed_days"], 0)
                    self.assertFalse(output.exists())
                    first = run(tf, half_life, self.config, self.fit_config, sample,
                                manifest, output, max_days=1)
                    self.assertEqual(first["completed_days"], 1)
                    result = run(tf, half_life, self.config, self.fit_config, sample,
                                 manifest, output)
                    self.assertTrue(result["complete"])
                    self.assertEqual(result["completed_days"], 6)
                    self.assertEqual(result["last_day"], 20220110)
                    self.assertEqual(result, run(tf, half_life, self.config, self.fit_config,
                                                 sample, manifest, output))
                state = json.loads((output / "latest.json").read_text(encoding="utf-8"))
                self.assertEqual(len(state["fit_history"]), 2)
                self.assertEqual(len(state["daily_sha256"]), 6)
                self.assertFalse((output / "predictions/20250102.csv").exists())
                with (output / "daily/20220103.json").open("a", encoding="utf-8") as stream:
                    stream.write(" ")
                with self.assertRaisesRegex(ValueError, "Corrupt daily"):
                    run(tf, half_life, self.config, self.fit_config, sample, manifest,
                        output, check_only=True)

    def test_failed_fit_does_not_silently_replace_mixture(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root, "1m")
            with patch("distributional_bands.phase7a.fit_distribution",
                       side_effect=FitError("synthetic failure")):
                result = run("1m", 30, self.config, self.fit_config, sample,
                             manifest, root / "failed", max_days=1)
            self.assertEqual(result["fit_failures"], 1)
            daily = json.loads((root / "failed/daily/20220103.json").read_text(encoding="utf-8"))
            self.assertEqual(set(daily["models"]), {"empirical_ewma"})

    def test_pit_roundoff_is_clamped_but_large_error_is_rejected(self) -> None:
        config = Phase7AConfig.from_json(self.config)
        prediction = {"target_log_return": [19.0], "sigma_ewma": [1.0],
                      "session": ["morning"]}
        for model in ("empirical_ewma", "normal_mixture_3"):
            for level in config.central_coverages:
                tag = str(round(level * 1000))
                prediction[f"{model}_q_low_{tag}"] = [-1.0]
                prediction[f"{model}_q_high_{tag}"] = [1.0]
        frame = pd.DataFrame(prediction)
        fitted = _fake_fit("normal_mixture_3", np.ones(80), None)
        fitted.parameters["weight_1"] += 4e-15
        status = {"status": "success", "fit": fitted.as_dict()}
        daily = _day_scores(20221116, frame, config, "normal_mixture_3", status)
        self.assertEqual(daily["models"]["normal_mixture_3"]["pit_sum"], 1.0)
        self.assertEqual(sum(daily["models"]["normal_mixture_3"]["pit_histogram"]), 1)
        fitted.parameters["weight_1"] += 1e-8
        with self.assertRaisesRegex(ValueError, "Invalid PIT"):
            _day_scores(20221116, frame, config, "normal_mixture_3",
                        {"status": "success", "fit": fitted.as_dict()})

    def test_pit_migration_preserves_checkpoint_and_resumes(self) -> None:
        for complete in (False, True):
            with self.subTest(complete=complete), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                sample, manifest = _fixture(root, "1m")
                output = root / "trial"
                with patch("distributional_bands.phase7a.fit_distribution", side_effect=_fake_fit):
                    run("1m", 30, self.config, self.fit_config, sample,
                        manifest, output, max_days=None if complete else 1)
                paths = [output / "run_manifest.json", output / "latest.json"]
                if complete:
                    paths.append(output / "metrics.json")
                original = json.loads((output / "latest.json").read_text(encoding="utf-8"))
                for path in paths:
                    document = json.loads(path.read_text(encoding="utf-8"))
                    document["signature"]["source_sha256"]["phase7a.py"] = LEGACY_PHASE7A_SHA256
                    path.write_text(json.dumps(document), encoding="utf-8")
                before = {name: sha256_file(output / name)
                          for name in ("predictions/20220103.csv", "daily/20220103.json")}
                args = ("1m", 30, self.config, self.fit_config, sample, manifest, output)
                self.assertEqual(migrate_trial(*args, check_only=True), "pending")
                self.assertFalse((output / "pit_boundary_migration_v1.json").exists())
                if not complete:
                    original_atomic = migration_module._atomic_json

                    def interrupted_write(path: Path, document: dict) -> None:
                        if path.name == "latest.json":
                            raise RuntimeError("synthetic interruption during migration")
                        original_atomic(path, document)

                    with patch.object(migration_module, "_atomic_json",
                                      side_effect=interrupted_write):
                        with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                            migrate_trial(*args)
                    self.assertEqual(migrate_trial(*args, check_only=True), "pending")
                self.assertEqual(migrate_trial(*args), "migrated")
                self.assertEqual(migrate_trial(*args), "current")
                self.assertEqual({name: sha256_file(output / name) for name in before}, before)
                backup = output / "pit_boundary_migration_v1"
                self.assertEqual(json.loads((backup / "latest.json").read_text(encoding="utf-8"))
                                 ["signature"]["source_sha256"]["phase7a.py"],
                                 LEGACY_PHASE7A_SHA256)
                with patch("distributional_bands.phase7a.fit_distribution", side_effect=_fake_fit):
                    result = run("1m", 30, self.config, self.fit_config, sample,
                                 manifest, output, max_days=1)
                self.assertEqual(result["completed_days"], 6 if complete else 2)
                self.assertEqual(original["prediction_sha256"]["20220103"],
                                 json.loads((output / "latest.json").read_text(encoding="utf-8"))
                                 ["prediction_sha256"]["20220103"])
                if not complete:
                    with patch("distributional_bands.phase7a.fit_distribution",
                               side_effect=_fake_fit):
                        self.assertTrue(run("1m", 30, self.config, self.fit_config,
                                            sample, manifest, output)["complete"])
                    self.assertEqual(migrate_trial(*args, check_only=True), "current")

    def test_pit_migration_rejects_corrupt_artifacts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root, "1m")
            output = root / "trial"
            with patch("distributional_bands.phase7a.fit_distribution", side_effect=_fake_fit):
                run("1m", 30, self.config, self.fit_config, sample,
                    manifest, output, max_days=1)
            for name in ("run_manifest.json", "latest.json"):
                path = output / name
                document = json.loads(path.read_text(encoding="utf-8"))
                document["signature"]["source_sha256"]["phase7a.py"] = LEGACY_PHASE7A_SHA256
                path.write_text(json.dumps(document), encoding="utf-8")
            with (output / "daily/20220103.json").open("a", encoding="utf-8") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError, "Corrupt daily"):
                migrate_trial("1m", 30, self.config, self.fit_config,
                              sample, manifest, output)
            self.assertFalse((output / "pit_boundary_migration_v1.json").exists())

    def test_report_stats_keep_coverage_and_score_on_same_bars(self) -> None:
        row = {"day": 20220103, "n": 10, "models": {"candidate": {
            "score_sum": 2.0, "levels": {"950": {"lower_exceed": 1,
                "upper_exceed": 0, "width_sum": 4.0, "pinball_sum": 2.0,
                "lower_transitions": [7, 1, 1, 0],
                "upper_transitions": [9, 0, 0, 0]}}}}}
        stats = _model_stats([row], "candidate", (0.95,))
        self.assertEqual(stats["n"], 10)
        self.assertEqual(stats["mean_pinball_equal_weight"], 0.2)
        self.assertAlmostEqual(stats["levels"]["950"]["observed_coverage"], 0.9)

    def test_report_uses_completed_trials_and_existing_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample, manifest = _fixture(root, "1m")
            output_root = root / "phase7a"
            with patch("distributional_bands.phase7a.fit_distribution", side_effect=_fake_fit):
                for half_life in (30, 120):
                    result = run("1m", half_life, self.config, self.fit_config, sample,
                                 manifest, output_root / "1m" / f"hl{half_life}")
                    self.assertTrue(result["complete"])
            anchor = root / "selection"
            (anchor / "daily").mkdir(parents=True)
            source = output_root / "1m/hl30"
            for daily in (source / "daily").glob("*.json"):
                shutil.copy2(daily, anchor / "daily" / daily.name)
            state = json.loads((source / "latest.json").read_text(encoding="utf-8"))
            anchor_signature = {"run_id": "synthetic-selection"}
            (anchor / "latest.json").write_text(json.dumps({
                "signature": anchor_signature, "complete": True,
                "daily_sha256": state["daily_sha256"],
            }), encoding="utf-8")
            (anchor / "report.json").write_text(json.dumps({
                "signature": anchor_signature, "complete": True,
                "days": 6, "first_day": 20220103, "last_day": 20220110,
            }), encoding="utf-8")
            report = report_run("1m", self.config, self.fit_config, sample,
                                manifest, anchor, output_root)
            self.assertEqual(report["days"], 6)
            self.assertEqual(len(report["tuning_rank_by_mean_pinball"]), 6)
            self.assertEqual(report, report_run("1m", self.config, self.fit_config,
                                               sample, manifest, anchor, output_root,
                                               check_only=True))


if __name__ == "__main__":
    unittest.main()
