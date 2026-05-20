#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_pages_data import SOURCE_OVERRIDES_PATH  # noqa: E402
from src.io_utils import dump_json, load_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "grc-e247-preserver-audit-remaining"
SOURCE_URL = (
    "https://github.com/huxuxuya/gonka_248_and_250_-epoch_loss/blob/main/"
    "outputs/grc_e247_preserver_audit_remaining/README.md"
)
DEFAULT_SOURCE_FILE = (
    ROOT
    / "outputs"
    / "grc_e247_preserver_audit_remaining"
    / "compensation_grc_e247_remaining.csv"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import GRC-e247 remaining delta payout rows as a dashboard source layer."
    )
    parser.add_argument("--source-file", type=Path, default=DEFAULT_SOURCE_FILE)
    parser.add_argument("--target", type=Path, default=SOURCE_OVERRIDES_PATH)
    args = parser.parse_args()

    if not args.source_file.exists():
        raise SystemExit(f"missing source file: {args.source_file}")

    existing = [
        item
        for item in load_json(args.target)
        if item.get("address") != "gonka..." and item.get("source") != SOURCE_NAME
    ]
    generated = read_rows(args.source_file)
    output = sorted(
        existing + generated,
        key=lambda item: (int(item["epoch"]), item["address"], item["source"]),
    )
    dump_json(args.target, output)
    print(f"Imported {len(generated)} {SOURCE_NAME} rows into {args.target}")
    return 0


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            amount = int(row["payout_to_make_base_units"])
            if amount <= 0:
                continue
            rows.append(
                {
                    "address": row["address"],
                    "epoch": int(row["epoch"]),
                    "source": SOURCE_NAME,
                    "source_compensation_base_units": amount,
                    "source_compensation_gnk": format_gnk(amount),
                    "source_match_tolerance_base_units": 2400,
                    "source_url": SOURCE_URL,
                    "status": "package_payout",
                    "details": (
                        "Supplemental payout from outputs/grc_e247_preserver_audit_remaining. "
                        "This source covers rows where GRC-e247-preserver-audit exists but "
                        "FINAL REWARD DELTA remained positive after all imported sources."
                    ),
                }
            )
    return rows


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal("1000000000")).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
