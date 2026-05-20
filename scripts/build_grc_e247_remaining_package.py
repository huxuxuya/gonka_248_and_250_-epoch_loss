#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.io_utils import load_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
ROWS_PATH = ROOT / "docs" / "data" / "compensation_rows.json"
OUTPUT_DIR = ROOT / "outputs" / "grc_e247_preserver_audit_remaining"
SOURCE_NAME = "GRC-e247-preserver-audit"
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
    rows = selected_rows(load_json(ROWS_PATH))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows)
    write_readme(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_DIR}")
    return 0


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

## Reproduce This Report

Run from the repository root:

```bash
python3 scripts/build_pages_data.py
python3 scripts/build_grc_e247_remaining_package.py
```

The script reads `docs/data/compensation_rows.json`, filters rows where:

```text
source == GRC-e247-preserver-audit
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
