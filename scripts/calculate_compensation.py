#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.compensation_logic import calculate_epoch_compensation
from src.constants import DEFAULT_SETTINGS_PATH, OUTPUTS_DIR, PROCESSED_DATA_DIR
from src.io_utils import dump_json, load_settings, write_csv


DETAILED_FIELDS = [
    "address",
    "epoch",
    "exclusion_reason",
    "weight",
    "confirmation_weight",
    "effective_weight",
    "fixed_epoch_reward",
    "total_epoch_weight",
    "reward_rate_base_units_per_weight",
    "actual_rewarded_coins",
    "expected_reward_base_units",
    "compensation_base_units",
    "expected_reward_gnk",
    "actual_reward_gnk",
    "compensation_gnk",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate Gonka compensation packages.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH))
    parser.add_argument("--epochs", nargs="+", type=int, help="Epochs to calculate")
    parser.add_argument("--cache-only", action="store_true", help="Read only local raw data")
    parser.add_argument("--refresh-cache", action="store_true", help="Refresh raw cache before calculating")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(Path(args.settings))
    epochs = args.epochs or settings.epochs

    if args.refresh_cache and args.cache_only:
        raise SystemExit("Choose either --cache-only or --refresh-cache, not both")

    if args.refresh_cache:
        if not settings.use_live_chain:
            raise SystemExit("settings.use_live_chain=false, cannot refresh cache")
        from scripts.fetch_raw_data import main as fetch_main

        original_argv = sys.argv[:]
        try:
            sys.argv = ["fetch_raw_data.py", "--settings", args.settings, "--epochs", *map(str, epochs)]
            fetch_main()
        finally:
            sys.argv = original_argv

    run_mode = "cache-only" if args.cache_only or not settings.use_live_chain else "live+cache"
    detailed_rows = []
    for epoch in epochs:
        result = calculate_epoch_compensation(settings, epoch)
        processed_path = PROCESSED_DATA_DIR / f"epoch_{epoch}_compensation.json"
        dump_json(processed_path, result.to_dict())

        epoch_rows = []
        for row in result.rows:
            row_dict = {
                "address": row.address,
                "epoch": row.epoch,
                "exclusion_reason": row.exclusion_reason,
                "weight": row.weight,
                "confirmation_weight": row.confirmation_weight,
                "effective_weight": row.effective_weight,
                "fixed_epoch_reward": row.fixed_epoch_reward,
                "total_epoch_weight": row.total_epoch_weight,
                "reward_rate_base_units_per_weight": str(row.reward_rate_base_units_per_weight),
                "actual_rewarded_coins": row.actual_rewarded_coins,
                "expected_reward_base_units": row.expected_reward_base_units,
                "compensation_base_units": row.compensation_base_units,
                "expected_reward_gnk": row.expected_reward_gnk,
                "actual_reward_gnk": row.actual_reward_gnk,
                "compensation_gnk": row.compensation_gnk,
                "notes": row.notes,
            }
            epoch_rows.append(row_dict)
            detailed_rows.append(row_dict)

        epoch_rows.sort(key=lambda item: item["address"])
        write_csv(OUTPUTS_DIR / f"epoch_{epoch}" / f"compensation_{epoch}.csv", epoch_rows, DETAILED_FIELDS)
        print(f"Calculated compensation for epoch {epoch}")

    detailed_rows.sort(key=lambda item: (int(item["epoch"]), item["address"]))
    write_csv(OUTPUTS_DIR / "combined" / "compensation_detailed.csv", detailed_rows, DETAILED_FIELDS)
    dump_json(
        PROCESSED_DATA_DIR / "run_manifest.json",
        {
            "epochs": epochs,
            "run_mode": run_mode,
            "settings_path": args.settings,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
