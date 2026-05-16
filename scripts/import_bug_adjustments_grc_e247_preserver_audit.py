#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
BUG_ADJUSTMENTS_PATH = ROOT / "docs" / "bug_weight_adjustments.json"
SOURCE_NAME = "GRC-e247-preserver-audit:stuck-0.35x"
SOURCE_URL = "https://github.com/gonkalabs/GRC-e247-preserver-audit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import 0.35x stuck weight bug adjustments.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/private/tmp/GRC-e247-preserver-audit"),
        help="Local checkout of https://github.com/gonkalabs/GRC-e247-preserver-audit",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=BUG_ADJUSTMENTS_PATH,
        help="Target bug weight adjustments JSON used by the GitHub Pages build.",
    )
    args = parser.parse_args()

    source_csv = args.source_dir / "output" / "issue2_per_node.csv"
    summary_json = args.source_dir / "output" / "issue2_summary.json"
    if not source_csv.exists():
        raise SystemExit(f"Missing source CSV: {source_csv}")

    wsf = read_weight_scale_factor(summary_json)
    existing = load_json(args.target) if args.target.exists() else []
    existing = [
        item
        for item in existing
        if item.get("address") != "gonka..." and item.get("source") != SOURCE_NAME
    ]
    imported = read_bug_rows(source_csv, wsf, source_urls(args.source_dir))
    dump_json(args.target, sorted(existing + imported, key=lambda item: (int(item["epoch"]), item["address"], item["source"])))
    print(f"Imported {len(imported)} bug adjustment rows into {args.target}")
    return 0


def read_bug_rows(path: Path, wsf: Decimal, urls: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], dict[str, Any]] = defaultdict(
        lambda: {
            "adjusted_weight_delta": 0,
            "nodes": [],
            "details_parts": [],
        }
    )
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            address = raw["participant_address"]
            pw_baseline = int(raw["pw_baseline"])
            chain_bug_weight = int((Decimal(pw_baseline) * wsf).to_integral_value(rounding=ROUND_FLOOR))
            weight_delta = pw_baseline - chain_bug_weight
            for epoch in parse_epochs(raw["stuck_epochs"]):
                key = (epoch, address)
                item = grouped[key]
                item["address"] = address
                item["epoch"] = epoch
                item["adjusted_weight_delta"] += weight_delta
                item["nodes"].append(raw["node_id"])
                item["details_parts"].append(
                    (
                        f"node={raw['node_id']}; pw_baseline={pw_baseline}; "
                        f"chain_bug_weight=floor({wsf}*{pw_baseline})={chain_bug_weight}; "
                        f"weight_delta={weight_delta}"
                    )
                )

    rows: list[dict[str, Any]] = []
    for item in grouped.values():
        rows.append(
            {
                "address": item["address"],
                "epoch": item["epoch"],
                "source": SOURCE_NAME,
                "source_url": urls["report"],
                "source_data_url": urls["csv"],
                "adjusted_weight_delta": item["adjusted_weight_delta"],
                "reason": "corrected stuck 0.35x preserver weight bug",
                "details": (
                    "0.35x stuck weight fix: adjusted_weight = current_effective_weight + "
                    "sum(pw_baseline - floor(weight_scale_factor * pw_baseline)). "
                    + " | ".join(item["details_parts"])
                ),
            }
        )
    return rows


def parse_epochs(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def read_weight_scale_factor(path: Path) -> Decimal:
    if not path.exists():
        return Decimal("0.3593")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Decimal(str(data.get("weight_scale_factor", "0.3593")))


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


if __name__ == "__main__":
    raise SystemExit(main())
