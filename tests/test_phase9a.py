"""Phase 9A z_t diagnostics: pairing, clustering, seasonality, source integrity, report."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from distributional_bands.data import sha256_file
from distributional_bands.phase9a import (Phase9AConfig, _lagged_abs_z_labels, clustered_mean,
                                          diagnose, load_source, run, within_session_acf)

CONFIG = Path("configs/phase9a_v1.json")
MODELS = ["empirical_ewma", "normal_mixture_2"]


def _days(count: int) -> list[int]:
    return [int(day.strftime("%Y%m%d")) for day in pd.bdate_range("2022-01-03", periods=count)]


def _day_frame(day: int, rng: np.random.Generator, bar: int = 5, high_open: bool = True) -> pd.DataFrame:
    rows = []
    for session, start, count in (("morning", 9 * 60, 30), ("afternoon", 13 * 60, 18)):
        for i in range(count):
            minute = start + i * bar
            scale = 2.0 if high_open and session == "morning" and minute < 9 * 60 + 15 else 1.0
            sigma = 0.001
            target = float(rng.normal(0, scale * sigma))
            row = {"TRADING_DATE": day, "session": session,
                   "timestamp": f"{str(day)[:4]}-{str(day)[4:6]}-{str(day)[6:]} {minute // 60:02d}:{minute % 60:02d}:00",
                   "target_log_return": target, "sigma_ewma": sigma}
            for model in MODELS:
                for tag, q in (("900", 1.645), ("950", 1.96), ("975", 2.24), ("990", 2.576), ("995", 2.807)):
                    row[f"{model}_q_low_{tag}"] = -q * sigma
                    row[f"{model}_q_high_{tag}"] = q * sigma
            rows.append(row)
    return pd.DataFrame(rows)


def _write_source(directory: Path, days: list[int], seed: int) -> None:
    (directory / "predictions").mkdir(parents=True)
    rng = np.random.default_rng(seed)
    hashes = {}
    for day in days:
        path = directory / "predictions" / f"{day}.csv"
        _day_frame(day, rng).to_csv(path, index=False)
        hashes[str(day)] = sha256_file(path)
    (directory / "latest.json").write_text(json.dumps({"complete": True, "prediction_sha256": hashes}),
                                           encoding="utf-8")


def _config(root: Path) -> Path:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["sources"] = {"hl30": {"directory": "s30/{timeframe}", "models": {"5m": MODELS, "1m": MODELS}},
                      "hl60": {"directory": "s60/{timeframe}", "models": {"5m": [], "1m": []}}}
    path = root / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class Phase9ATests(unittest.TestCase):
    def test_acf_never_pairs_across_sessions_or_gaps(self) -> None:
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        group = np.array([1, 1, 1, 2, 2, 2])
        minute = np.array([0, 1, 2, 0, 1, 5])
        rows = within_session_acf(values, group, minute, 1, 3)
        self.assertEqual([row["pairs"] for row in rows], [3, 1, 0])
        self.assertIsNone(rows[2]["acf"])

    def test_clustered_mean_matches_manual_formula(self) -> None:
        values = np.array([1.0, 3.0, 2.0, 6.0])
        clusters = np.array([1, 1, 2, 2])
        result = clustered_mean(values, clusters)
        mean = 3.0
        sums = np.array([(1 - mean) + (3 - mean), (2 - mean) + (6 - mean)])
        expected = np.sqrt(2 / 1 * np.sum(sums ** 2)) / 4
        self.assertAlmostEqual(result["mean"], mean)
        self.assertAlmostEqual(result["se"], expected)
        self.assertEqual(result["clusters"], 2)

    def test_lagged_labels_mark_session_starts(self) -> None:
        frame = pd.DataFrame({"z": [0.5, 2.5, 0.1, 4.0], "group": [1, 1, 1, 2],
                              "minute": [0, 5, 10, 0]})
        labels, order = _lagged_abs_z_labels(frame, 5, (1.0, 2.0, 3.0))
        self.assertEqual(labels.tolist(), ["first_or_gap", "<1", "2-3", "first_or_gap"])
        self.assertEqual(order[0], "first_or_gap")

    def test_seasonality_is_detected_and_removed(self) -> None:
        rng = np.random.default_rng(3)
        days = _days(60)
        frame = pd.concat([_day_frame(day, rng) for day in days], ignore_index=True)
        frame["z"] = frame["target_log_return"] / frame["sigma_ewma"]
        stamp = pd.to_datetime(frame["timestamp"])
        frame["minute"] = stamp.dt.hour * 60 + stamp.dt.minute
        frame["group"] = frame["TRADING_DATE"] * 10 + frame["session"].map({"morning": 0, "afternoon": 1})
        result = diagnose(frame, MODELS, Phase9AConfig.from_json(CONFIG), "5m")
        buckets = {row["group"]: row["z2"]["mean"] for row in result["intraday"]}
        self.assertGreater(buckets["09:00"], 3.0)
        self.assertLess(abs(buckets["10:00"] - 1.0), 0.4)
        raw = result["acf"]["z2"][0]["acf"]
        adjusted = result["acf"]["z2_seasonally_adjusted"][0]["acf"]
        self.assertGreater(raw, 0.05)
        self.assertLess(abs(adjusted), raw / 2)

    def test_source_integrity_and_development_guard(self) -> None:
        config = Phase9AConfig.from_json(CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            _write_source(source, [20220104, 20220105], 1)
            frame, _ = load_source(source, MODELS, config)
            self.assertEqual(len(frame), 96)
            (source / "predictions" / "20220105.csv").write_text("corrupt", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_source(source, MODELS, config)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            _write_source(source, [20241231, 20250102], 1)
            with self.assertRaises(ValueError):
                load_source(source, MODELS, config)

    def test_report_is_written_once_and_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            days = _days(12)
            _write_source(root / "s30" / "5m", days, 7)
            _write_source(root / "s60" / "5m", days, 7)
            config = _config(root)
            output = root / "out"
            with self.assertRaises(ValueError):
                run("5m", config, root, output, check_only=True)
            report = run("5m", config, root, output)
            self.assertTrue((output / "intraday.csv").exists())
            self.assertEqual(report["sources"]["hl30"]["summary"]["days"], 12)
            run("5m", config, root, output, check_only=True)
            stored = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stored["timeframe"] = "tampered"
            (output / "report.json").write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaises(ValueError):
                run("5m", config, root, output, check_only=True)


if __name__ == "__main__":
    unittest.main()
