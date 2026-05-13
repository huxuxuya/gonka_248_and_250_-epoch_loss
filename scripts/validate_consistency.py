#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import CACHE_INDEX_PATH, DEFAULT_SETTINGS_PATH, RAW_DATA_DIR
from src.io_utils import load_json, load_settings, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate raw cache consistency.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH))
    parser.add_argument("--epochs", nargs="+", type=int, help="Epochs to validate")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(Path(args.settings))
    epochs = args.epochs or settings.epochs
    cache_index = load_json(CACHE_INDEX_PATH) if CACHE_INDEX_PATH.exists() else {"epochs": {}}

    failures = []
    for epoch in epochs:
        epoch_dir = RAW_DATA_DIR / f"epoch_{epoch}"
        metadata_path = epoch_dir / "metadata.json"
        if not metadata_path.exists():
            failures.append(f"epoch {epoch}: missing metadata.json")
            continue

        metadata = load_json(metadata_path)
        required_files = [
            "params.json",
            "epoch_group_data_full.json",
            f"epoch_group_data_{epoch}.json",
            f"epoch_performance_summary_{epoch}.json",
            f"excluded_participants_{epoch}.json",
        ]
        for filename in required_files:
            path = epoch_dir / filename
            if not path.exists():
                failures.append(f"epoch {epoch}: missing {filename}")
                continue

        for filename, record in metadata.get("files", {}).items():
            path = epoch_dir / filename
            if not path.exists():
                failures.append(f"epoch {epoch}: metadata references missing {filename}")
                continue
            actual_hash = sha256_file(path)
            if actual_hash != record.get("sha256"):
                failures.append(f"epoch {epoch}: sha mismatch for {filename}")

        indexed = cache_index.get("epochs", {}).get(str(epoch), {})
        for filename, record in indexed.get("files", {}).items():
            path = epoch_dir / filename
            if path.exists() and sha256_file(path) != record.get("sha256"):
                failures.append(f"epoch {epoch}: cache_index sha mismatch for {filename}")

        schema_checks = [
            (epoch_dir / "params.json", ["params"]),
            (epoch_dir / "epoch_group_data_full.json", ["pages", "items"]),
            (epoch_dir / f"epoch_group_data_{epoch}.json", ["epoch_group_data"]),
            (epoch_dir / f"epoch_performance_summary_{epoch}.json", ["epochPerformanceSummary"]),
            (epoch_dir / f"excluded_participants_{epoch}.json", []),
        ]
        for path, required_keys in schema_checks:
            if not path.exists():
                continue
            payload = load_json(path)
            for key in required_keys:
                if key not in payload:
                    failures.append(f"epoch {epoch}: {path.name} missing required key {key}")

    if failures:
        print("Consistency validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Consistency validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
