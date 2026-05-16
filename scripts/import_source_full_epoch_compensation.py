#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_pages_data import build_rows, index_by_key
from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OVERRIDES_PATH = ROOT / "docs" / "source_overrides.json"
BUG_ADJUSTMENTS_PATH = ROOT / "docs" / "bug_weight_adjustments.json"
SOURCE_URLS = {
    248: "https://github.com/huxuxuya/gonka_248_and_250_-epoch_loss/blob/main/outputs/epoch_248/README.md",
    250: "https://github.com/huxuxuya/gonka_248_and_250_-epoch_loss/blob/main/outputs/epoch_250/README.md",
}
SOURCE_NAMES = {
    248: "epoch-248-full-compensation",
    250: "epoch-250-full-compensation",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate full epoch 248/250 compensation source layers.")
    parser.add_argument("--epochs", type=int, nargs="+", default=[248, 250])
    parser.add_argument("--target", type=Path, default=SOURCE_OVERRIDES_PATH)
    args = parser.parse_args()

    existing = load_json(args.target) if args.target.exists() else []
    generated_sources = {SOURCE_NAMES[epoch] for epoch in args.epochs}
    base_sources = [
        item
        for item in existing
        if item.get("address") != "gonka..." and item.get("source") not in generated_sources
    ]

    bug_adjustments = load_json(BUG_ADJUSTMENTS_PATH)
    rows = build_rows(index_by_key(bug_adjustments), index_by_key(base_sources))

    generated: list[dict[str, Any]] = []
    for epoch in args.epochs:
        epoch_rows = [row for row in rows if int(row["epoch"]) == epoch]
        epoch_generated: list[dict[str, Any]] = []
        for row in epoch_rows:
            remaining = int(row.get("remaining_after_sources_base_units") or 0)
            if remaining <= 0:
                continue
            epoch_generated.append(full_compensation_row(row, epoch, remaining))

        calculated_total = sum(int(row.get("calculated_layers_base_units") or 0) for row in epoch_rows)
        existing_source_total = sum(int(row.get("source_compensation_base_units") or 0) for row in epoch_rows)
        generated_total = sum(int(row["source_compensation_base_units"]) for row in epoch_generated)
        reconcile_delta = calculated_total - existing_source_total - generated_total
        if reconcile_delta and epoch_generated:
            epoch_generated[-1]["source_compensation_base_units"] += reconcile_delta
            epoch_generated[-1]["source_compensation_gnk"] = format_gnk(epoch_generated[-1]["source_compensation_base_units"])
            epoch_generated[-1]["details"] += f" Reconciled epoch total by {reconcile_delta} base units."

        generated.extend(epoch_generated)

    output = sorted(base_sources + generated, key=lambda item: (int(item["epoch"]), item["address"], item["source"]))
    dump_json(args.target, output)
    print(f"Generated {len(generated)} full-compensation rows into {args.target}")
    return 0


def full_compensation_row(row: dict[str, Any], epoch: int, remaining: int) -> dict[str, Any]:
    return {
        "address": row["address"],
        "epoch": epoch,
        "source": SOURCE_NAMES[epoch],
        "source_url": SOURCE_URLS[epoch],
        "source_weight": int(row.get("weight") or 0),
        "source_compensation_base_units": remaining,
        "source_compensation_gnk": row["remaining_after_sources_gnk"],
        "status": "package_full_compensation",
        "details": (
            f"Full epoch {epoch} compensation package. Covers the remaining calculated loss "
            "after previously imported source layers."
        ),
    }


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal(1_000_000_000)).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
