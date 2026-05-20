#!/usr/bin/env python3
from __future__ import annotations

import csv
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
from src.io_utils import load_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "grc_e247_preserver_audit_remaining"
SOURCE_NAME = "GRC-e247-preserver-audit"
PACKAGE_SOURCE_NAME = "grc-e247-preserver-audit-remaining"
SOURCE_URL = (
    "https://github.com/gonkalabs/GRC-e247-preserver-audit/blob/"
    "1b8a26704dcddea0de2f55cabf48fee3d9b100d4/RESTITUTION_REPORT.md"
)


CSV_FIELDS = [
    "epoch",
    "address",
    "loss_reason",
    "weight",
    "confirmation_weight",
    "effective_weight",
    "expected_reward_gnk",
    "actual_reward_gnk",
    "calculated_compensation_gnk",
    "grc_e247_source_compensation_gnk",
    "all_sources_compensation_gnk",
    "final_reward_delta_gnk",
    "payout_to_make_base_units",
    "payout_to_make_gnk",
    "source_url",
    "notes",
]


def main() -> int:
    rows = selected_rows(build_rows_without_this_package_source())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows)
    write_readme(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_DIR}")
    return 0


def build_rows_without_this_package_source() -> list[dict[str, Any]]:
    # The dashboard imports this report back as a source layer. Excluding that
    # package source here keeps the report reproducible after it has been
    # imported, otherwise every row would already be closed and the report would
    # rebuild as empty.
    source_overrides = [
        item
        for item in load_json(SOURCE_OVERRIDES_PATH)
        if item.get("source") != PACKAGE_SOURCE_NAME
    ]
    bug_adjustments = load_json(BUG_ADJUSTMENTS_PATH)
    return build_rows(index_by_key(bug_adjustments), index_by_key(source_overrides))


def selected_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if has_source(row, SOURCE_NAME) and int(row.get("reward_delta_after_sources_base_units") or 0) > 0
    ]
    return sorted(
        selected,
        key=lambda row: (
            int(row["epoch"]),
            -int(row.get("reward_delta_after_sources_base_units") or 0),
            row["address"],
        ),
    )


def write_csv(rows: list[dict[str, Any]]) -> None:
    path = OUTPUT_DIR / "compensation_grc_e247_remaining.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_row(row))


def csv_row(row: dict[str, Any]) -> dict[str, Any]:
    source_total = sum(
        int(item.get("source_compensation_base_units") or 0)
        for item in row.get("sources") or []
        if item.get("source") == SOURCE_NAME
    )
    payout = int(row.get("reward_delta_after_sources_base_units") or 0)
    return {
        "epoch": row["epoch"],
        "address": row["address"],
        "loss_reason": row.get("reason") or "",
        "weight": row.get("weight") or 0,
        "confirmation_weight": row.get("confirmation_weight") or 0,
        "effective_weight": row.get("effective_weight") or 0,
        "expected_reward_gnk": gnk(row.get("expected_reward_gnk")),
        "actual_reward_gnk": gnk(row.get("actual_reward_gnk")),
        "calculated_compensation_gnk": gnk(row.get("calculated_layers_gnk")),
        "grc_e247_source_compensation_gnk": format_gnk(source_total),
        "all_sources_compensation_gnk": gnk(row.get("source_compensation_gnk")),
        "final_reward_delta_gnk": gnk(row.get("reward_delta_after_sources_gnk")),
        "payout_to_make_base_units": payout,
        "payout_to_make_gnk": format_gnk(payout),
        "source_url": SOURCE_URL,
        "notes": row.get("notes") or "",
    }


def write_readme(rows: list[dict[str, Any]]) -> None:
    total = sum(int(row.get("reward_delta_after_sources_base_units") or 0) for row in rows)
    source_total = sum(
        int(item.get("source_compensation_base_units") or 0)
        for row in rows
        for item in row.get("sources") or []
        if item.get("source") == SOURCE_NAME
    )
    epoch_lines = []
    for epoch in sorted({int(row["epoch"]) for row in rows}):
        epoch_rows = [row for row in rows if int(row["epoch"]) == epoch]
        epoch_total = sum(int(row.get("reward_delta_after_sources_base_units") or 0) for row in epoch_rows)
        epoch_lines.append(f"| {epoch} | {len(epoch_rows)} | {format_gnk(epoch_total)} |")

    text = f"""# GRC-e247 preserver audit remaining compensation

This folder contains a supplemental payout list for participants that already have a `{SOURCE_NAME}` compensation source, but still have a non-zero `FINAL REWARD DELTA` after all currently imported sources are applied.

The goal is not to replace the original audit. This report pays only the remaining delta that is still visible in the repository calculation.

Source document: [{SOURCE_NAME}]({SOURCE_URL})

## Summary

| metric | value |
|---|---:|
| rows with remaining delta | {len(rows)} |
| GRC-e247 source amount on these rows GNK | {format_gnk(source_total)} |
| payout to make GNK | {format_gnk(total)} |

## By Epoch

| epoch | rows | payout to make GNK |
|---:|---:|---:|
{chr(10).join(epoch_lines)}

## Calculation Algorithm

This report is a second-layer payout on top of the original `{SOURCE_NAME}` source.

In simple terms:

1. Rebuild the dashboard calculation from cached chain data and all imported sources, but remove this report's own source layer: `{PACKAGE_SOURCE_NAME}`.
2. Keep only rows where the participant already has `{SOURCE_NAME}`.
3. Keep only rows where the remaining `FINAL REWARD DELTA` is still positive.
4. Pay exactly that remaining positive delta.

The base reward loss is calculated by the repository chain-style logic:

```text
expected_reward = floor(expected_reward_weight * fixed_epoch_reward / total_epoch_weight)
base_loss = max(0, expected_reward - actual_rewarded_coins)
calculated_compensation = base_loss + adjustment_layers
```

For this report the payout is:

```text
payout_to_make = max(0, calculated_compensation - all_imported_sources_except_this_package)
```

`all_imported_sources_except_this_package` includes the original `{SOURCE_NAME}` rows and any other independent source rows already imported into `docs/source_overrides.json`. It deliberately excludes `{PACKAGE_SOURCE_NAME}` so the report can be rebuilt after it has been imported into the dashboard.

All money is calculated in base units and only formatted to GNK at the end:

```text
1 GNK = 1_000_000_000 base units
```

## Reproduce This Report

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/validate_consistency.py --epochs 249 251 252
python3 scripts/build_pages_data.py
python3 scripts/build_grc_e247_remaining_package.py
python3 scripts/import_source_grc_e247_remaining_package.py
python3 scripts/build_pages_data.py
python3 scripts/validate_consistency.py --epochs 249 251 252
```

The first `build_pages_data.py` run makes sure the local dashboard data exists. `build_grc_e247_remaining_package.py` then rebuilds rows while excluding its own package source, writes this README and CSV, and `import_source_grc_e247_remaining_package.py` imports the payout rows back into the dashboard as `{PACKAGE_SOURCE_NAME}`.

Expected total for this file:

```text
GRC-e247 remaining payout to make: {format_gnk(total)} GNK
```

The report filter is:

```text
source == {SOURCE_NAME}
reward_delta_after_sources_base_units > 0
```

and writes:

```text
outputs/grc_e247_preserver_audit_remaining/compensation_grc_e247_remaining.csv
outputs/grc_e247_preserver_audit_remaining/README.md
```

## Participant Payouts

{participant_table(rows)}
"""
    (OUTPUT_DIR / "README.md").write_text(text, encoding="utf-8")


def participant_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| epoch | address | loss reason | weight | expected GNK | actual GNK | calculated compensation GNK | GRC-e247 source GNK | all sources GNK | payout to make GNK |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        data = csv_row(row)
        lines.append(
            "| {epoch} | `{address}` | {reason} | {weight} | {expected} | {actual} | {calculated} | {source} | {all_sources} | {payout} |".format(
                epoch=data["epoch"],
                address=data["address"],
                reason=data["loss_reason"],
                weight=data["weight"],
                expected=data["expected_reward_gnk"],
                actual=data["actual_reward_gnk"],
                calculated=data["calculated_compensation_gnk"],
                source=data["grc_e247_source_compensation_gnk"],
                all_sources=data["all_sources_compensation_gnk"],
                payout=data["payout_to_make_gnk"],
            )
        )
    return "\n".join(lines)


def has_source(row: dict[str, Any], source_name: str) -> bool:
    return any(item.get("source") == source_name for item in row.get("sources") or [])


def gnk(value: Any) -> str:
    if value in (None, ""):
        return "0.000000000"
    return str(value)


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal("1000000000")).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
