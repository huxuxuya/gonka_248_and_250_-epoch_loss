#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import BASE_UNITS_PER_GNK
from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OVERRIDES_PATH = ROOT / "docs" / "source_overrides.json"
SOURCE_NAME = "GRC-e247-preserver-audit"
SOURCE_URL = "https://github.com/gonkalabs/GRC-e247-preserver-audit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import stuck 0.35x preserver audit restitution source.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/private/tmp/GRC-e247-preserver-audit"),
        help="Local checkout of https://github.com/gonkalabs/GRC-e247-preserver-audit",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=SOURCE_OVERRIDES_PATH,
        help="Target source overrides JSON used by the GitHub Pages build.",
    )
    args = parser.parse_args()

    source_csv = args.source_dir / "output" / "issue2_per_node.csv"
    if not source_csv.exists():
        raise SystemExit(f"Missing source CSV: {source_csv}")

    existing = load_json(args.target) if args.target.exists() else []
    existing = [
        item
        for item in existing
        if item.get("address") != "gonka..." and item.get("source") != SOURCE_NAME
    ]
    imported = read_source_rows(source_csv, source_urls(args.source_dir))
    dump_json(args.target, sorted(existing + imported, key=lambda item: (int(item["epoch"]), item["address"], item["source"])))
    print(f"Imported {len(imported)} rows into {args.target}")
    return 0


def read_source_rows(path: Path, urls: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], dict[str, Any]] = defaultdict(
        lambda: {
            "source_compensation_base_units": 0,
            "source_weight": 0,
            "nodes": [],
            "details_parts": [],
        }
    )
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            address = raw["participant_address"]
            pw_baseline = int(raw["pw_baseline"])
            epoch_losses = parse_epoch_losses_base_units(raw["lost_by_epoch_gonka"])
            exact_total = int(raw["lost_ngonka"])
            rounding_delta = exact_total - sum(epoch_losses.values())
            if rounding_delta and epoch_losses:
                epoch_losses[max(epoch_losses)] += rounding_delta
            for epoch, lost_base_units in epoch_losses.items():
                key = (epoch, address)
                item = grouped[key]
                item["address"] = address
                item["epoch"] = epoch
                item["source_compensation_base_units"] += lost_base_units
                item["source_weight"] += pw_baseline
                item["nodes"].append(raw["node_id"])
                item["details_parts"].append(
                    (
                        f"node={raw['node_id']}; pw_baseline={pw_baseline}; "
                        f"stuck_epochs={raw['stuck_epochs']}; denominator={raw['denominator_mode']}"
                    )
                )

    rows: list[dict[str, Any]] = []
    for item in grouped.values():
        base_units = item["source_compensation_base_units"]
        rows.append(
            {
                "address": item["address"],
                "epoch": item["epoch"],
                "source": SOURCE_NAME,
                "source_url": urls["report"],
                "source_data_url": urls["csv"],
                "source_weight": item["source_weight"],
                "source_weight_basis": "sum of affected node pw_baseline from audit, not full participant epoch weight",
                "source_compensation_base_units": base_units,
                "source_compensation_gnk": format_gnk(base_units),
                "status": "external_proposed",
                "details": (
                    "Stuck 0.35x preserver audit restitution. Per-epoch loss imported from "
                    "output/issue2_per_node.csv. "
                    + " | ".join(item["details_parts"])
                ),
            }
        )
    return rows


def parse_epoch_losses_base_units(value: str) -> dict[int, int]:
    result: dict[int, int] = {}
    for part in value.split(";"):
        if not part:
            continue
        epoch, lost_gnk = part.split(":", 1)
        result[int(epoch)] = gnk_to_base_units(lost_gnk)
    return result


def source_urls(source_dir: Path) -> dict[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    if not commit:
        return {
            "report": f"{SOURCE_URL}/blob/main/RESTITUTION_REPORT.md",
            "csv": f"{SOURCE_URL}/blob/main/output/issue2_per_node.csv",
        }
    return {
        "report": f"{SOURCE_URL}/blob/{commit}/RESTITUTION_REPORT.md",
        "csv": f"{SOURCE_URL}/blob/{commit}/output/issue2_per_node.csv",
    }


def gnk_to_base_units(value: str) -> int:
    return int((Decimal(value.replace(",", "")) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR))


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
