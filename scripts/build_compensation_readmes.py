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
    build_summaries,
    index_by_key,
)
from src.io_utils import load_json  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE_NAMES = {
    "epoch-248-compensation-package",
    "epoch-250-compensation-package",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build README payout documents for epochs 248 and 250.")
    parser.add_argument("--epochs", nargs="+", type=int, default=[248, 250])
    args = parser.parse_args()

    rows = build_external_only_rows()
    summaries = {int(item["epoch"]): item for item in build_summaries(rows)}
    for epoch in args.epochs:
        build_epoch_readme(epoch, rows, summaries[epoch])
    build_root_readme(args.epochs, summaries)
    print("Updated README.md and epoch payout README files")
    return 0


def build_external_only_rows() -> list[dict[str, Any]]:
    source_overrides = [
        item
        for item in load_json(SOURCE_OVERRIDES_PATH)
        if item.get("source") not in PACKAGE_SOURCE_NAMES
    ]
    bug_adjustments = load_json(BUG_ADJUSTMENTS_PATH)
    return build_rows(index_by_key(bug_adjustments), index_by_key(source_overrides))


def build_epoch_readme(epoch: int, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    path = ROOT / "outputs" / f"epoch_{epoch}" / "README.md"
    payout_by_address = reconciled_payouts(epoch, rows)
    payout_total = sum(payout_by_address.values())
    total_calculated = (
        Decimal(summary["compensation_gnk"]) + Decimal(summary["bug_compensation_gnk"])
    ).quantize(Decimal("0.000000001"))
    text = f"""# Epoch {epoch} compensation payout

This file is the source of truth for epoch `{epoch}` compensation payouts. The rows below are also exported as the `{package_source_name(epoch)}` source layer for the GitHub Pages review table.

`calculated compensation GNK` is the reward loss calculated from cached chain data. `already covered by external sources GNK` subtracts only independent external source calculations imported into `docs/source_overrides.json`. `payout to make GNK` is the remaining amount that should be paid from this package.

## Summary

| metric | value |
|---|---:|
| rows with calculated loss | {summary['rows_with_loss']} |
| calculated base compensation GNK | {summary['compensation_gnk']} |
| bug adjustment compensation GNK | {summary['bug_compensation_gnk']} |
| calculated compensation total GNK | {format(total_calculated, 'f')} |
| already covered by external sources GNK | {summary['source_compensation_gnk']} |
| payout to make GNK | {format_gnk(payout_total)} |

## Participant Payouts

{participant_table(epoch, rows, payout_by_address)}
"""
    path.write_text(text, encoding="utf-8")


def build_root_readme(epochs: list[int], summaries: dict[int, dict[str, Any]]) -> None:
    sources = sorted(
        {
            item.get("source")
            for item in load_json(SOURCE_OVERRIDES_PATH)
            if item.get("source") and item.get("address") != "gonka..."
        }
    )
    source_lines = "\n".join(f"- `{source}`" for source in sources)
    scope_rows = []
    for epoch in epochs:
        summary = summaries[epoch]
        payout_total = sum(reconciled_payouts(epoch, build_external_only_rows()).values())
        scope_rows.append(
            f"| {epoch} | {summary['rows_with_loss']} | {summary['compensation_gnk']} | "
            f"{summary['bug_compensation_gnk']} | {summary['source_compensation_gnk']} | "
            f"{format_gnk(payout_total)} | [epoch {epoch}](outputs/epoch_{epoch}/README.md) |"
        )

    text = f"""# Gonka epoch 248 and 250 compensation package

After comprehensive analysis of cached chain data and external compensation sources, this repository treats epochs `248` and `250` as epochs that must be compensated in full for participants that lost rewards.

The package is reproducible: raw chain snapshots are stored under `data/raw`, calculations are derived from those snapshots, and the GitHub Pages review table is generated from the same CSV/JSON outputs.

## Where to see payouts

- [Epoch 248 payout list](outputs/epoch_248/README.md) - participant table with the amount to pay for epoch 248.
- [Epoch 250 payout list](outputs/epoch_250/README.md) - participant table with the amount to pay for epoch 250.
- [GRC-e247 preserver audit remaining compensation](outputs/grc_e247_preserver_audit_remaining/README.md) - supplemental rows where the GRC-e247 audit source exists but `FINAL REWARD DELTA` is still non-zero.
- [GitHub Pages review table](docs/index.html) - interactive view with source toggles and detailed per-cell cards.

The epoch README files are payout documents and source-of-truth inputs for the package source layers. They are imported into the review table as `epoch-248-compensation-package` and `epoch-250-compensation-package`, but they are not subtracted from themselves when these README payout totals are built.

## Compensation scope

| epoch | rows with calculated loss | calculated base GNK | bug adjustment GNK | already covered by external sources GNK | payout to make GNK | epoch report |
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(scope_rows)}

## Rule used for the package

```text
expected_reward = floor(expected_reward_weight * fixed_epoch_reward / total_epoch_weight)
calculated_loss = max(0, expected_reward - actual_rewarded_coins)
payout_to_make = max(0, calculated_loss + adjustment_layers - covered_by_external_sources)
```

Money is handled in base units with `Decimal` and floor rounding. `1 GNK = 1e9` base units.

For confirmation failures that zeroed effective weight, the expected reward is calculated from the original chain weight. For subgroup/model capped weights, the effective reward weight follows the reconstructed chain logic, including scaled subgroup voting power.

## Source Handling

External source rows live in `docs/source_overrides.json` and are included in `docs/data/compensation_rows.json`. If an independent source has already calculated a non-zero compensation for the same address and epoch, that amount is shown as `already covered by external sources GNK` and subtracted from `payout to make GNK`.

Package payout sources are generated from the epoch README payout lists after independent external sources are subtracted. They let the GitHub Pages table show the final package compensation as a source layer without changing the README payout totals.

The GRC-e247 remaining-delta package is also imported as `grc-e247-preserver-audit-remaining`. It closes the residual `FINAL REWARD DELTA` for rows that already had `GRC-e247-preserver-audit` but were not fully covered by that original source.

Current sources used by the review table include:

{source_lines}

## Important Files

- `outputs/epoch_248/README.md` - participant-level epoch 248 payout table and package source of truth.
- `outputs/epoch_250/README.md` - participant-level epoch 250 payout table and package source of truth.
- `outputs/grc_e247_preserver_audit_remaining/README.md` - supplemental remaining-delta payout table for GRC-e247 preserver audit rows.
- `outputs/combined/compensation_detailed.csv` - detailed calculated rows for all cached epochs.
- `docs/index.html` - GitHub Pages review table.
- `docs/source_overrides.json` - imported independent source rows plus package payout source rows.
- `docs/data/compensation_rows.json` - generated browser data with source layers applied.

## Rebuild

```bash
python3 scripts/calculate_compensation.py --epochs 247 248 249 250 251 252 253 254 255 --cache-only
python3 scripts/build_reports.py
python3 scripts/build_compensation_readmes.py --epochs 248 250
python3 scripts/import_source_epoch_compensation_package.py --epochs 248 250
python3 scripts/build_pages_data.py
python3 scripts/build_grc_e247_remaining_package.py
python3 scripts/import_source_grc_e247_remaining_package.py
python3 scripts/build_pages_data.py
python3 scripts/validate_consistency.py --epochs 247 248 249 250 251 252 253 254 255
```
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def participant_table(epoch: int, rows: list[dict[str, Any]], payout_by_address: dict[str, int]) -> str:
    selected = [
        row
        for row in rows
        if int(row["epoch"]) == epoch and int(row.get("calculated_layers_base_units") or 0) > 0
    ]
    selected.sort(
        key=lambda row: (
            int(row.get("remaining_after_sources_base_units") or 0),
            int(row.get("calculated_layers_base_units") or 0),
            row["address"],
        ),
        reverse=True,
    )
    lines = [
        "| address | loss reason | weight | expected GNK | actual GNK | calculated compensation GNK | already covered by external sources GNK | external source | payout to make GNK |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in selected:
        lines.append(
            "| `{address}` | {reason} | {weight} | {expected} | {actual} | {calculated} | {covered} | {source} | {payout} |".format(
                address=row["address"],
                reason=row.get("reason") or "",
                weight=row.get("weight") or 0,
                expected=gnk(row.get("expected_reward_gnk")),
                actual=gnk(row.get("actual_reward_gnk")),
                calculated=gnk(row.get("calculated_layers_gnk")),
                covered=gnk(row.get("source_compensation_gnk")),
                source=source_links(row),
                payout=format_gnk(payout_by_address.get(row["address"], 0)),
            )
        )
    return "\n".join(lines)


def reconciled_payouts(epoch: int, rows: list[dict[str, Any]]) -> dict[str, int]:
    epoch_rows = [row for row in rows if int(row["epoch"]) == epoch]
    payouts = {
        row["address"]: int(row.get("remaining_after_sources_base_units") or 0)
        for row in epoch_rows
        if int(row.get("remaining_after_sources_base_units") or 0) > 0
    }
    target = sum(int(row.get("calculated_layers_base_units") or 0) for row in epoch_rows)
    target -= sum(int(row.get("source_compensation_base_units") or 0) for row in epoch_rows)
    target = max(0, target)
    actual = sum(payouts.values())
    diff = actual - target
    if diff and payouts:
        address = max(payouts, key=payouts.get)
        payouts[address] -= diff
        if payouts[address] < 0:
            raise SystemExit(f"cannot reconcile README payout total for epoch {epoch}: diff={diff}")
    return payouts


def source_links(row: dict[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for item in row.get("sources") or []:
        name = str(item.get("source") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        url = str(item.get("source_url") or "").strip()
        parts.append(f"[{name}]({url})" if url else name)
    return ", ".join(parts)


def package_source_name(epoch: int) -> str:
    return f"epoch-{epoch}-compensation-package"


def gnk(value: Any) -> str:
    if value in (None, ""):
        return "0.000000000"
    return str(value)


def format_gnk(base_units: int) -> str:
    return format((Decimal(base_units) / Decimal("1000000000")).quantize(Decimal("0.000000001")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
