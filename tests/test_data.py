import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from distributional_bands.data import (
    DataPolicy,
    continuous_bars,
    five_minute_bars,
    forecast_samples,
    load_raw,
    prepare,
    sha256_file,
)
from distributional_bands.cli import main


class DataPipelineTests(unittest.TestCase):
    def setUp(self):
        self.policy = DataPolicy.from_json(Path("configs/data_v1.json"))
        times = (
            [f"09:{minute:02d}:00" for minute in list(range(5)) + list(range(6, 15))]
            + [f"13:{minute:02d}:00" for minute in range(10)]
            + ["14:45:00"]
        )
        rows = []
        for index, time in enumerate(times):
            price = 100.0 + index
            rows.append({
                "SYMBOL": "VN30F1M", "TRADING_DATE": 20260102,
                "TRADING_TIME": time, "OPEN_PX": price,
                "HIGH_PX": price + 0.5, "LOW_PX": price - 0.5,
                "CLOSE_PX": price + 0.2, "VOL": index + 1,
                "BUY_VOL": index + 1, "SELL_VOL": 0,
                "BUY_VAL": 0, "SELL_VAL": 0,
            })
        self.raw = pd.DataFrame(rows)
        self.raw["timestamp"] = pd.to_datetime(
            self.raw.TRADING_DATE.astype(str) + " " + self.raw.TRADING_TIME,
            format="%Y%m%d %H:%M:%S",
        )

    def test_sessions_gaps_and_auction_do_not_create_targets(self):
        one, five, report = prepare(self.raw, self.policy)
        self.assertEqual(report["excluded_non_continuous_rows"], 1)
        self.assertEqual(report["incomplete_5m_buckets"], 1)
        self.assertEqual(report["forecast_samples_1m"], 21)
        self.assertEqual(report["forecast_samples_5m"], 1)
        self.assertTrue((one.target_timestamp - one.timestamp).eq(pd.Timedelta(minutes=1)).all())
        self.assertTrue((five.target_timestamp - five.timestamp).eq(pd.Timedelta(minutes=5)).all())
        self.assertTrue((one.available_at == one.target_timestamp).all())
        self.assertTrue((five.available_at == five.target_timestamp).all())
        self.assertFalse(one.timestamp.dt.strftime("%H:%M:%S").isin(["09:04:00", "11:29:00", "14:45:00"]).any())

    def test_five_minute_ohlcv_uses_exactly_five_source_bars(self):
        bars = continuous_bars(self.raw, self.policy)
        five, incomplete = five_minute_bars(bars, self.policy)
        self.assertEqual(incomplete, 1)
        self.assertEqual(len(five), 4)
        source = bars[bars.timestamp.between("2026-01-02 13:00:00", "2026-01-02 13:04:00")]
        aggregate = five[five.timestamp.eq(pd.Timestamp("2026-01-02 13:00:00"))].iloc[0]
        self.assertEqual(aggregate.OPEN_PX, source.OPEN_PX.iloc[0])
        self.assertEqual(aggregate.HIGH_PX, source.HIGH_PX.max())
        self.assertEqual(aggregate.LOW_PX, source.LOW_PX.min())
        self.assertEqual(aggregate.CLOSE_PX, source.CLOSE_PX.iloc[-1])
        self.assertEqual(aggregate.VOL, source.VOL.sum())

    def test_target_is_next_close_and_is_not_a_feature_column(self):
        bars = continuous_bars(self.raw, self.policy)
        samples = forecast_samples(bars, 1)
        first = samples.iloc[0]
        expected = np.log(self.raw.CLOSE_PX.iloc[1] / self.raw.CLOSE_PX.iloc[0])
        self.assertAlmostEqual(first.target_log_return, expected)
        self.assertNotIn("next_close", samples.columns)

    def test_targets_never_cross_a_trading_day(self):
        second_day = self.raw.iloc[:5].copy()
        second_day["TRADING_DATE"] = 20260105
        second_day["timestamp"] = second_day["timestamp"] + pd.Timedelta(days=3)
        combined = pd.concat([self.raw, second_day], ignore_index=True)
        samples = forecast_samples(continuous_bars(combined, self.policy), 1)
        self.assertTrue(
            samples["timestamp"].dt.date.eq(samples["target_timestamp"].dt.date).all()
        )

    def test_raw_validation_rejects_duplicate_or_bad_ohlc(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.csv"
            self.raw.drop(columns="timestamp").to_csv(path, index=False)
            self.assertEqual(len(load_raw(path, self.policy)), len(self.raw))
            duplicate = pd.concat([self.raw, self.raw.iloc[[-1]]], ignore_index=True)
            duplicate.drop(columns="timestamp").to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                load_raw(path, self.policy)
            bad = self.raw.drop(columns="timestamp").copy()
            bad.loc[0, "HIGH_PX"] = 0
            bad.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "OHLC"):
                load_raw(path, self.policy)

    def test_cli_prepare_writes_manifest_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.csv"
            output = Path(directory) / "result"
            self.raw.drop(columns="timestamp").to_csv(source, index=False)
            args = ["distributional-bands", "prepare", "--input", str(source),
                    "--policy", "configs/data_v1.json", "--output-dir", str(output)]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                main()
            manifest = output / "manifest.json"
            self.assertTrue(manifest.exists())
            self.assertTrue((output / "samples_1m.csv").exists())
            self.assertTrue((output / "samples_5m.csv").exists())
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(
                metadata["output_sha256"]["samples_1m.csv"],
                sha256_file(output / "samples_1m.csv"),
            )
            with patch("sys.argv", args), self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                main()


if __name__ == "__main__":
    unittest.main()
