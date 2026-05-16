#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_pages_data import (  # noqa: E402
    BUG_ADJUSTMENTS_PATH,
    SOURCE_OVERRIDES_PATH,
    build_rows,
    index_by_key,
)
from src.io_utils import dump_json, load_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAMES = {
    248: "epoch-248-compensation-package",
    250: "epoch-250-compensation-package",
}
SOURCE_URLS = {
    248: "https://github.com/huxuxuya/gonka_248_and_250_-epoch_loss/blob/main/outputs/epoch_248/README.md",
    250: "https://github.com/huxuxuya/gonka_248_and_250_-epoch_loss/blob/main/outputs/epoch_250/README.md",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import epoch README payout rows as source layers for the review table."
    )
    parser.add_argument("--epochs", nargs="+", type=int, default=[248, 250])
    parser.add_argument("--target", type=Path, default=SOURCE_OVERRIDES_PATH)
    args = parser.parse_args()

    requested_epochs = set(args.epochs)
    unsupported = requested_epochs - set(SOURCE_NAMES)
    if unsupported:
        raise SystemExit(f"unsupported package source epochs: {sorted(unsupported)}")

    package_sources = {SOURCE_NAMES[epoch] for epoch in requested_epochs}
    existing_sources = load_json(args.target)
    base_sources = [
        item
        for item in existing_sources
        if item.get("address") != "gonka..." and item.get("source") not in package_sources
    ]
    bug_adjustments = load_json(BUG_ADJUSTMENTS_PATH)

    # Build with package sources removed so package amounts represent the final payout
    # after independent external source rows only.
    rows = build_rows(index_by_key(bug_adjustments), index_by_key(base_sources))
    generated: list[dict[str, Any]] = []
    for row in rows:
        epoch = int(row["epoch"])
        if epoch not in requested_epochs:
            continue
        remaining = int(row.get("remaining_after_sources_base_units") or 0)
        if remaining <= 0:
            continue
        generated.append(
            {
                "address": row["address"],
                "epoch": epoch,
                "source": SOURCE_NAMES[epoch],
                "source_compensation_base_units": remaining,
                "source_compensation_gnk": row["remaining_after_sources_gnk"],
                "source_match_tolerance_base_units": 2400,
                "source_url": SOURCE_URLS[epoch],
                "status": "package_payout",
                "details": (
                    f"Compensation payout from outputs/epoch_{epoch}/README.md. "
                    "This package source covers the remaining calculated loss after "
                    "independent external sources."
                ),
            }
        )
    reconcile_epoch_totals(rows, generated, requested_epochs)

    output = sorted(
        base_sources + generated,
        key=lambda item: (int(item["epoch"]), item["address"], item["source"]),
    )
    dump_json(args.target, output)
    print(f"Generated {len(generated)} package source rows into {args.target}")
    return 0


def reconcile_epoch_totals(
    rows: list[dict[str, Any]],
    generated: list[dict[str, Any]],
    epochs: set[int],
) -> None:
    for epoch in epochs:
        epoch_rows = [row for row in rows if int(row["epoch"]) == epoch]
        target = sum(int(row.get("calculated_layers_base_units") or 0) for row in epoch_rows)
        target -= sum(int(row.get("source_compensation_base_units") or 0) for row in epoch_rows)
        target = max(0, target)
        epoch_generated = [item for item in generated if int(item["epoch"]) == epoch]
        actual = sum(int(item["source_compensation_base_units"]) for item in epoch_generated)
        diff = actual - target
        if diff == 0 or not epoch_generated:
            continue
        adjustment_row = max(epoch_generated, key=lambda item: int(item["source_compensation_base_units"]))
        adjusted_amount = int(adjustment_row["source_compensation_base_units"]) - diff
        if adjusted_amount < 0:
            raise SystemExit(f"cannot reconcile package source total for epoch {epoch}: diff={diff}")
        adjustment_row["source_compensation_base_units"] = adjusted_amount
        adjustment_row["source_compensation_gnk"] = format_gnk(adjusted_amount)
        adjustment_row["details"] += f" Reconciled epoch total by {-diff} base units."


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal("1000000000")).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
