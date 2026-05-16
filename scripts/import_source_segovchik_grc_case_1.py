#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import BASE_UNITS_PER_GNK
from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OVERRIDES_PATH = ROOT / "docs" / "source_overrides.json"
DEFAULT_SOURCE_FILE = ROOT / "data" / "raw" / "sources" / "segovchik_script_result_247_grc_case_1.txt"
SOURCE_NAME = "SegovChik-grc-case-1"
SOURCE_URL = "https://gist.github.com/SegovChik/19043f13d4f811ae70b4c469903f053c"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import SegovChik epoch 247 GRC case #1 compensation source.")
    parser.add_argument(
        "--source-file",
        type=Path,
        default=DEFAULT_SOURCE_FILE,
        help="Local raw text snapshot from the gist.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=SOURCE_OVERRIDES_PATH,
        help="Target source overrides JSON used by the GitHub Pages build.",
    )
    args = parser.parse_args()

    if not args.source_file.exists():
        raise SystemExit(f"Missing source file: {args.source_file}")

    existing = load_json(args.target) if args.target.exists() else []
    existing = [
        item
        for item in existing
        if item.get("address") != "gonka..." and item.get("source") != SOURCE_NAME
    ]
    imported = read_source_rows(args.source_file)
    dump_json(args.target, sorted(existing + imported, key=lambda item: (int(item["epoch"]), item["address"], item["source"])))
    print(f"Imported {len(imported)} rows into {args.target}")
    return 0


def read_source_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^\s*\d+\s+(gonka[0-9a-z]+)\s+"
            r"(?P<weight>\d+)\s+(?P<poc_weight>\d+)\s+(?P<cw>\d+)\s+"
            r"(?P<inferences>\d+)\s+(?P<missed>\d+)\s+(?P<invalid>\d+)\s+"
            r"(?P<rewarded>[0-9.]+)\s+(?P<expected>[0-9.]+)\s+(?P<compensate>[0-9.]+)\s*$",
            line,
        )
        if not match:
            continue
        base_units = gnk_to_base_units(match.group("compensate"))
        rows.append(
            {
                "address": match.group(1),
                "epoch": 247,
                "source": SOURCE_NAME,
                "source_url": SOURCE_URL,
                "source_weight": int(match.group("weight")),
                "source_compensation_base_units": base_units,
                "source_compensation_gnk": format_gnk(base_units),
                "source_match_tolerance_base_units": 5_000_000,
                "status": "external_proposed",
                "details": (
                    "SegovChik GRC case #1 gist. "
                    "Amounts are rounded to 2 decimals, so matching uses 0.005 GNK tolerance. "
                    f"weight={match.group('weight')}; poc_weight={match.group('poc_weight')}; "
                    f"cw={match.group('cw')}; inferences={match.group('inferences')}; "
                    f"missed={match.group('missed')}; invalid={match.group('invalid')}; "
                    f"rewarded={match.group('rewarded')} GNK; expected={match.group('expected')} GNK."
                ),
            }
        )
    return rows


def gnk_to_base_units(value: str) -> int:
    return int((Decimal(value) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR))


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
