"""One-time, auditable checkpoint migration for the Phase 7A PIT boundary fix.

Only the known original phase7a.py source hash may change. Forecasts, daily
scores, fit state and all upstream artifacts are left byte-for-byte intact.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .baseline import _atomic_json
from .data import sha256_file
from .phase7a import Phase7AConfig, _signature


LEGACY_PHASE7A_SHA256 = "57f602b95156c9994cea347d9975b87cfde635d2f66103265c59be631bfe57f5"
BACKUP_DIR = "pit_boundary_migration_v1"
RECORD_FILE = "pit_boundary_migration_v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_artifacts(output_dir: Path, state: dict) -> None:
    if (state["completed_days"] != len(state["prediction_sha256"])
            or state["completed_days"] != len(state["daily_sha256"])):
        raise ValueError("Phase 7A checkpoint progress is inconsistent")
    for folder, hashes, extension in (("predictions", state["prediction_sha256"], "csv"),
                                      ("daily", state["daily_sha256"], "json")):
        directory = output_dir / folder
        if not directory.is_dir():
            raise ValueError(f"Missing Phase 7A {folder} directory")
        for day, expected in hashes.items():
            path = directory / f"{day}.{extension}"
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"Corrupt {folder} artifact for {day}")


def migrate_trial(timeframe: str, half_life: int, config_path: Path, fit_path: Path,
                  sample_path: Path, data_manifest_path: Path, output_dir: Path,
                  *, check_only: bool = False) -> str:
    config = Phase7AConfig.from_json(config_path)
    if timeframe not in config.shortlist or half_life not in (30, 120):
        raise ValueError("Invalid Phase 7A trial")
    current = _signature(config_path, fit_path, sample_path, data_manifest_path,
                         timeframe, half_life, config)
    legacy = copy.deepcopy(current)
    legacy["source_sha256"]["phase7a.py"] = LEGACY_PHASE7A_SHA256
    if not output_dir.exists():
        print(f"{current['run_id']}: no checkpoint to migrate")
        return "absent"

    paths = {"run_manifest.json": output_dir / "run_manifest.json",
             "latest.json": output_dir / "latest.json"}
    metrics_path = output_dir / "metrics.json"
    if metrics_path.exists():
        paths["metrics.json"] = metrics_path
    if any(not path.is_file() for path in paths.values()):
        raise ValueError("Incomplete Phase 7A metadata; migration refused")
    documents = {name: _read_json(path) for name, path in paths.items()}
    signatures = {name: document.get("signature") for name, document in documents.items()}
    if any(signature not in (legacy, current) for signature in signatures.values()):
        raise ValueError("Checkpoint signature differs beyond the approved PIT fix")
    state = documents["latest.json"]
    _verify_artifacts(output_dir, state)
    if "metrics.json" in documents and not state["complete"]:
        raise ValueError("Incomplete trial unexpectedly has final metrics")
    if "metrics.json" in documents and documents["metrics.json"].get("completed_days") != state["completed_days"]:
        raise ValueError("Phase 7A metrics and checkpoint progress differ")

    record_path = output_dir / RECORD_FILE
    backup_dir = output_dir / BACKUP_DIR
    if record_path.exists():
        record = _read_json(record_path)
        if record.get("old_signature") != legacy or record.get("new_signature") != current:
            raise ValueError("PIT migration record does not match this trial")
        backed_up = set(record.get("backup_sha256", {}))
        if not {"run_manifest.json", "latest.json"}.issubset(backed_up) or not backed_up.issubset(paths):
            raise ValueError("PIT migration backup set differs from metadata")
        if any(signatures[name] != current for name in set(paths) - backed_up):
            raise ValueError("Post-migration metadata has a legacy signature")
        for name, expected in record["backup_sha256"].items():
            backup = backup_dir / name
            if not backup.is_file() or sha256_file(backup) != expected:
                raise ValueError(f"PIT migration backup is missing or corrupt: {name}")
    elif len(set(json.dumps(signature, sort_keys=True) for signature in signatures.values())) != 1:
        raise ValueError("Mixed signatures without a migration record")

    if all(signature == current for signature in signatures.values()):
        print(f"{current['run_id']}: checkpoint current; {state['completed_days']} days preserved")
        return "current"

    if check_only:
        print(f"{current['run_id']}: valid legacy checkpoint; migration required; "
              f"{state['completed_days']} days preserved")
        return "pending"

    if not record_path.exists():
        backup_dir.mkdir(exist_ok=True)
        backup_hashes = {}
        for name, path in paths.items():
            backup = backup_dir / name
            original_hash = sha256_file(path)
            if backup.exists():
                if sha256_file(backup) != original_hash:
                    raise ValueError(f"Existing PIT migration backup differs: {name}")
            else:
                temporary = backup.with_name(backup.name + ".tmp")
                shutil.copyfile(path, temporary)
                if sha256_file(temporary) != original_hash:
                    raise ValueError(f"PIT migration backup copy differs: {name}")
                os.replace(temporary, backup)
            backup_hashes[name] = original_hash
        _atomic_json(record_path, {
            "reason": "Clamp only CDF roundoff within 1e-12 at PIT boundaries",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "old_signature": legacy, "new_signature": current,
            "backup_sha256": backup_hashes,
            "migration_code_sha256": sha256_file(Path(__file__)),
        })

    for name, path in paths.items():
        document = documents[name]
        if document["signature"] == legacy:
            document["signature"] = current
            _atomic_json(path, document)
    print(f"{current['run_id']}: PIT metadata migrated; "
          f"{state['completed_days']} days and prediction/daily hashes preserved")
    return "migrated"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("1m", "5m"), required=True)
    parser.add_argument("--half-life", type=int, choices=(30, 120), required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/phase7a_v1.json"))
    parser.add_argument("--fit-config", type=Path, default=Path("configs/distribution_fit_v2.json"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, default=Path("outputs/data_v1/manifest.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    migrate_trial(args.timeframe, args.half_life, args.config, args.fit_config,
                  args.input, args.data_manifest, args.output_dir,
                  check_only=args.check_only)


if __name__ == "__main__":
    main()
