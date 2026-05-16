#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import BASE_UNITS_PER_GNK
from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OVERRIDES_PATH = ROOT / "docs" / "source_overrides.json"
SOURCE_NAME = "GRC-e254-api-issue"
SOURCE_URL = "https://github.com/votkon/GRC-e254-api-issue"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import epoch 254 compensation source from GRC-e254-api-issue.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/private/tmp/GRC-e254-api-issue"),
        help="Local checkout of https://github.com/votkon/GRC-e254-api-issue",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=SOURCE_OVERRIDES_PATH,
        help="Target source overrides JSON used by the GitHub Pages build.",
    )
    args = parser.parse_args()

    source_csv = args.source_dir / "compensation.csv"
    if not source_csv.exists():
        raise SystemExit(f"Missing source CSV: {source_csv}")

    existing = load_json(args.target) if args.target.exists() else []
    existing = [
        item
        for item in existing
        if item.get("address") != "gonka..." and not (item.get("epoch") == 254 and item.get("source") == SOURCE_NAME)
    ]
    imported = read_source_rows(source_csv, source_url(args.source_dir))
    dump_json(args.target, sorted(existing + imported, key=lambda item: (int(item["epoch"]), item["address"], item["source"])))
    print(f"Imported {len(imported)} rows into {args.target}")
    return 0


def read_source_rows(path: Path, resolved_source_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            base_units = int(raw["compensation_ngonka"])
            rows.append(
                {
                    "address": raw["address"],
                    "epoch": 254,
                    "source": SOURCE_NAME,
                    "source_url": resolved_source_url,
                    "source_weight": int(raw["weight"]),
                    "source_compensation_base_units": base_units,
                    "source_compensation_gnk": format_gnk(base_units),
                    "cpoc1_ratio": format_decimal(raw["cpoc1_ratio"], "0.000000001"),
                    "final_ratio": format_decimal(raw["final_ratio"], "0.000000001"),
                    "status": "external_proposed",
                    "details": (
                        "Epoch 254 API issue source: CPoC1 passed, later CPoC failed/dropped "
                        "or final confirmation ratio below 45.5%, actual reward was zero."
                    ),
                }
            )
    return rows


def source_url(source_dir: Path) -> str:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return SOURCE_URL
    if not commit:
        return SOURCE_URL
    return f"{SOURCE_URL}/blob/{commit}/compensation.csv"


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)).quantize(Decimal("0.000000001")), "f")


def format_decimal(value: str, quantum: str) -> str:
    return format(Decimal(value).quantize(Decimal(quantum), rounding=ROUND_FLOOR), "f")


if __name__ == "__main__":
    raise SystemExit(main())
