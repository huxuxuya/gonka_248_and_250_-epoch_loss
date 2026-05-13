#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import CACHE_INDEX_PATH, DEFAULT_SETTINGS_PATH, OUTPUTS_DIR, PROCESSED_DATA_DIR
from src.io_utils import load_json, load_settings, write_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Gonka compensation CSV and Markdown reports.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(Path(args.settings))
    epochs = settings.package_policy.get("include_epochs", settings.epochs)

    detailed_rows = []
    epoch_totals = []
    by_address: dict[str, dict[str, int]] = defaultdict(lambda: {
        "actual_rewarded_coins": 0,
        "expected_reward_base_units": 0,
        "compensation_base_units": 0,
    })
    excluded_reasons: dict[str, int] = defaultdict(int)
    zero_comp_rows = []
    approximation_used = False

    for epoch in epochs:
        processed = load_json(PROCESSED_DATA_DIR / f"epoch_{epoch}_compensation.json")
        approximation_used = approximation_used or bool(processed.get("approximation_used"))
        rows = processed["rows"]
        rows.sort(key=lambda item: item["address"])
        write_csv(
            OUTPUTS_DIR / f"epoch_{epoch}" / f"compensation_{epoch}.csv",
            rows,
            list(rows[0].keys()) if rows else [],
        )

        total_actual = 0
        total_expected = 0
        total_comp = 0
        total_weight = int(processed.get("total_epoch_weight", "0"))
        fixed_reward = int(processed.get("fixed_epoch_reward", "0"))

        for row in rows:
            detailed_rows.append(row)
            total_actual += int(row["actual_rewarded_coins"])
            total_expected += int(row["expected_reward_base_units"])
            total_comp += int(row["compensation_base_units"])

            address_summary = by_address[row["address"]]
            address_summary["actual_rewarded_coins"] += int(row["actual_rewarded_coins"])
            address_summary["expected_reward_base_units"] += int(row["expected_reward_base_units"])
            address_summary["compensation_base_units"] += int(row["compensation_base_units"])

            reason = row.get("exclusion_reason", "")
            if reason:
                excluded_reasons[reason] += 1
            if int(row["compensation_base_units"]) == 0:
                zero_comp_rows.append(row)

        epoch_totals.append(
            {
                "epoch": epoch,
                "fixed_epoch_reward": fixed_reward,
                "total_epoch_weight": total_weight,
                "actual_rewarded_coins": total_actual,
                "expected_reward_base_units": total_expected,
                "compensation_base_units": total_comp,
                "approximation_used": processed.get("approximation_used", False),
            }
        )

    detailed_rows.sort(key=lambda item: (int(item["epoch"]), item["address"]))
    write_csv(
        OUTPUTS_DIR / "combined" / "compensation_detailed.csv",
        detailed_rows,
        list(detailed_rows[0].keys()) if detailed_rows else [],
    )

    summary_by_address = []
    for address in sorted(by_address):
        row = {"address": address, **by_address[address]}
        summary_by_address.append(row)
    write_csv(
        OUTPUTS_DIR / "combined" / "compensation_summary_by_address.csv",
        summary_by_address,
        ["address", "actual_rewarded_coins", "expected_reward_base_units", "compensation_base_units"],
    )
    write_csv(
        OUTPUTS_DIR / "combined" / "compensation_summary_by_epoch.csv",
        epoch_totals,
        [
            "epoch",
            "fixed_epoch_reward",
            "total_epoch_weight",
            "actual_rewarded_coins",
            "expected_reward_base_units",
            "compensation_base_units",
            "approximation_used",
        ],
    )

    cache_index = load_json(CACHE_INDEX_PATH) if CACHE_INDEX_PATH.exists() else {"epochs": {}}
    run_manifest = (
        load_json(PROCESSED_DATA_DIR / "run_manifest.json")
        if (PROCESSED_DATA_DIR / "run_manifest.json").exists()
        else {}
    )
    report_path = OUTPUTS_DIR / "combined" / "REPORT.md"
    report_path.write_text(
        build_report(
            settings.node_url,
            cache_index,
            epoch_totals,
            summary_by_address,
            zero_comp_rows,
            excluded_reasons,
            run_manifest.get("run_mode", "cache-only" if not settings.use_live_chain else "live-or-cache"),
            approximation_used,
        ),
        encoding="utf-8",
    )
    print(f"Built reports under {OUTPUTS_DIR}")
    return 0


def build_report(
    node_url: str,
    cache_index: dict,
    epoch_totals: list[dict],
    summary_by_address: list[dict],
    zero_comp_rows: list[dict],
    excluded_reasons: dict[str, int],
    run_mode: str,
    approximation_used: bool,
) -> str:
    lines = [
        "# Compensation Report",
        "",
        f"- Node: `{node_url}`",
        f"- Run mode: `{run_mode}`",
        f"- Approximation used: `{str(approximation_used).lower()}`",
        "",
        "## Raw Cache",
    ]
    for epoch, metadata in sorted(cache_index.get("epochs", {}).items(), key=lambda item: int(item[0])):
        lines.append(f"- Epoch {epoch}: fetched_at_utc=`{metadata.get('fetched_at_utc', 'unknown')}`")

    lines.extend(
        [
            "",
            "## Totals By Epoch",
            "",
            "| epoch | fixed_epoch_reward | total_epoch_weight | actual_rewarded_coins | expected_reward_base_units | compensation_base_units | approximation_used |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in epoch_totals:
        lines.append(
            f"| {row['epoch']} | {row['fixed_epoch_reward']} | {row['total_epoch_weight']} | {row['actual_rewarded_coins']} | {row['expected_reward_base_units']} | {row['compensation_base_units']} | {row['approximation_used']} |"
        )

    lines.extend(
        [
            "",
            "## Totals By Address",
            "",
            "| address | actual_rewarded_coins | expected_reward_base_units | compensation_base_units |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in summary_by_address:
        lines.append(
            f"| {row['address']} | {row['actual_rewarded_coins']} | {row['expected_reward_base_units']} | {row['compensation_base_units']} |"
        )

    lines.extend(
        [
            "",
            "## Zero Compensation Rows",
            "",
            "| address | epoch | exclusion_reason | actual_rewarded_coins | expected_reward_base_units | compensation_base_units |",
            "| --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for row in zero_comp_rows:
        lines.append(
            f"| {row['address']} | {row['epoch']} | {row.get('exclusion_reason', '')} | {row['actual_rewarded_coins']} | {row['expected_reward_base_units']} | {row['compensation_base_units']} |"
        )

    lines.extend(
        [
            "",
            "## Excluded Reason Distribution",
            "",
            "| exclusion_reason | count |",
            "| --- | ---: |",
        ]
    )
    for reason, count in sorted(excluded_reasons.items()):
        lines.append(f"| {reason} | {count} |")

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
