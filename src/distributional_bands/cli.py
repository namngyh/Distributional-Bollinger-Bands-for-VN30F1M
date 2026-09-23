"""Command line entry point for data audit and reproducible preparation."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy
import pandas

from .data import DataPolicy, load_raw, prepare, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "prepare"))
    parser.add_argument("--input", type=Path, default=Path("ohlc_export.csv"))
    parser.add_argument("--policy", type=Path, default=Path("configs/data_v1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/data_v1"))
    args = parser.parse_args()
    if args.command == "prepare" and args.output_dir.exists():
        raise SystemExit(f"Output directory already exists; refusing to overwrite: {args.output_dir}")

    policy = DataPolicy.from_json(args.policy)
    raw = load_raw(args.input, policy)
    one_minute, five_minute, report = prepare(raw, policy)
    report["raw_sha256"] = sha256_file(args.input)
    report["policy_sha256"] = sha256_file(args.policy)
    report["source_sha256"] = {
        "data.py": sha256_file(Path(__file__).with_name("data.py")),
        "cli.py": sha256_file(Path(__file__)),
    }
    report["environment"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command == "audit":
        return
    args.output_dir.mkdir(parents=True)
    one_path = args.output_dir / "samples_1m.csv"
    five_path = args.output_dir / "samples_5m.csv"
    one_minute.to_csv(one_path, index=False)
    five_minute.to_csv(five_path, index=False)
    report["output_sha256"] = {
        "samples_1m.csv": sha256_file(one_path),
        "samples_5m.csv": sha256_file(five_path),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Prepared datasets in {args.output_dir}")


if __name__ == "__main__":
    main()
