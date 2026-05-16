#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
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
SOURCE_NAME = "consensus_failure_restriction"
SOURCE_URL = "https://github.com/huxuxuya/-consensus_failure_restriction"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import consensus failure restriction compensation source.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/private/tmp/-consensus_failure_restriction"),
        help="Local checkout of https://github.com/huxuxuya/-consensus_failure_restriction",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=SOURCE_OVERRIDES_PATH,
        help="Target source overrides JSON used by the GitHub Pages build.",
    )
    args = parser.parse_args()

    readme = args.source_dir / "README.md"
    if not readme.exists():
        raise SystemExit(f"Missing source README: {readme}")

    existing = load_json(args.target) if args.target.exists() else []
    existing = [
        item
        for item in existing
        if item.get("address") != "gonka..." and item.get("source") != SOURCE_NAME
    ]
    imported = read_final_table(readme, source_url(args.source_dir))
    dump_json(args.target, sorted(existing + imported, key=lambda item: (int(item["epoch"]), item["address"], item["source"])))
    print(f"Imported {len(imported)} rows into {args.target}")
    return 0


def read_final_table(path: Path, resolved_source_url: str) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "Final compensation table for this package:":
            start = idx
            break
    if start is None:
        raise SystemExit("Could not find final compensation table in README.md")

    rows: list[dict[str, Any]] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0] in {"Address", "---"} or cells[0].startswith("---"):
            continue
        if len(cells) < 10 or not cells[0].startswith("gonka"):
            continue
        base_units = gnk_to_base_units(cells[8])
        rows.append(
            {
                "address": cells[0],
                "epoch": int(cells[1]),
                "source": SOURCE_NAME,
                "source_url": resolved_source_url,
                "source_weight": int(cells[3]),
                "source_compensation_base_units": base_units,
                "source_compensation_gnk": format_gnk(base_units),
                "status": "external_proposed",
                "details": (
                    f"Consensus failure restriction package. exclusion_reason={cells[2]}; "
                    f"confirmation_weight={cells[4]}; effective_weight={cells[5]}; "
                    f"expected={cells[6]} GNK; actual={cells[7]} GNK; comment={cells[9]}"
                ),
            }
        )
    return rows


def clean_cell(value: str) -> str:
    value = value.strip()
    value = value.replace("`", "").replace("**", "")
    return re.sub(r"\s+", " ", value)


def source_url(source_dir: Path) -> str:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return f"{SOURCE_URL}/blob/main/README.md"
    if not commit:
        return f"{SOURCE_URL}/blob/main/README.md"
    return f"{SOURCE_URL}/blob/{commit}/README.md"


def gnk_to_base_units(value: str) -> int:
    return int((Decimal(value.replace(",", "")) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR))


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
