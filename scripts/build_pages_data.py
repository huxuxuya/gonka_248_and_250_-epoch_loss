#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import BASE_UNITS_PER_GNK
from src.io_utils import dump_json, load_json


ROOT = Path(__file__).resolve().parents[1]
DETAILED_CSV = ROOT / "outputs" / "combined" / "compensation_detailed.csv"
SUMMARY_CSV = ROOT / "outputs" / "combined" / "compensation_summary_by_epoch.csv"
DOCS_DIR = ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"
BUG_ADJUSTMENTS_PATH = DOCS_DIR / "bug_weight_adjustments.json"
SOURCE_OVERRIDES_PATH = DOCS_DIR / "source_overrides.json"
SOURCE_MATCH_TOLERANCE_BASE_UNITS = 2400
FULL_LAYER_SOURCE_NAMES = {
    "epoch-248-compensation-package",
    "epoch-250-compensation-package",
    "grc-e247-preserver-audit-remaining",
}


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_placeholder_json()

    bug_adjustments = load_json(BUG_ADJUSTMENTS_PATH)
    source_overrides = load_json(SOURCE_OVERRIDES_PATH)
    rows = build_rows(index_by_key(bug_adjustments), index_by_key(source_overrides))
    summaries = build_summaries(rows)

    dump_json(DATA_DIR / "compensation_rows.json", rows)
    dump_json(DATA_DIR / "summary.json", summaries)
    dump_embedded_data(DOCS_DIR / "data.js", rows, summaries)
    print(f"Built GitHub Pages data under {DATA_DIR}")
    return 0


def ensure_placeholder_json() -> None:
    if not BUG_ADJUSTMENTS_PATH.exists():
        dump_json(
            BUG_ADJUSTMENTS_PATH,
            [
                {
                    "address": "gonka...",
                    "epoch": 254,
                    "adjusted_weight": "1288",
                    "reason": "example: corrected stuck 0.35 weight bug",
                    "details": "Set adjusted_weight to the weight that should be used for the bug scenario.",
                }
            ],
        )


def dump_embedded_data(path: Path, rows: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> None:
    payload = {
        "rows": rows,
        "summary": summaries,
    }
    path.write_text(
        "window.__GONKA_COMPENSATION_DATA__ = "
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        + ";\n",
        encoding="utf-8",
    )
    if not SOURCE_OVERRIDES_PATH.exists():
        dump_json(
            SOURCE_OVERRIDES_PATH,
            [
                {
                    "address": "gonka...",
                    "epoch": 254,
                    "source": "external-review-name",
                    "source_compensation_gnk": "358.796135671",
                    "status": "draft",
                    "details": "External calculation note. Matching cells are highlighted when this equals baseline or bug-adjusted compensation.",
                }
            ],
        )


def index_by_key(items: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        address = str(item.get("address", "")).strip()
        epoch = str(item.get("epoch", "")).strip()
        if not address or not epoch or address == "gonka...":
            continue
        result.setdefault((epoch, address), []).append(item)
    return result


def build_rows(
    bug_adjustments: dict[tuple[str, str], list[dict[str, Any]]],
    source_overrides: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with DETAILED_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            epoch = raw["epoch"]
            address = raw["address"]
            key = (epoch, address)
            bug_items = bug_adjustments.get(key, [])
            source_items = source_overrides.get(key, [])
            bug = bug_items[0] if bug_items else {}
            adjusted_weight = parse_int(bug.get("adjusted_weight"))
            adjusted_weight_delta = sum(parse_int(item.get("adjusted_weight_delta") or item.get("bug_weight_delta")) or 0 for item in bug_items)
            fixed_reward = parse_int(raw["fixed_epoch_reward"])
            total_weight = parse_int(raw["total_epoch_weight"])
            actual_reward = parse_int(raw["actual_rewarded_coins"])
            baseline_comp = parse_int(raw["compensation_base_units"])
            full_weight = parse_int(raw["weight"]) or 0
            effective_weight = parse_int(raw["effective_weight"]) or 0
            notes = raw.get("notes", "")

            if adjusted_weight is None and adjusted_weight_delta:
                adjusted_weight = full_weight + adjusted_weight_delta

            bug_expected = None
            bug_comp = None
            bug_reward_delta = None
            if adjusted_weight is not None:
                bug_expected = floor_reward(adjusted_weight, fixed_reward, total_weight)
                if adjusted_weight_delta:
                    bug_reward_delta = floor_reward(adjusted_weight_delta, fixed_reward, total_weight)
                    bug_comp = bug_reward_delta
                else:
                    bug_comp = max(0, bug_expected - actual_reward)

            calculated_layers_total = baseline_comp + (bug_comp or 0)
            source_total = sum(source_item_base_units(item) for item in source_items)
            bug_source_total = sum(
                source_item_base_units(item)
                for item in source_items
                if item.get("source") == "GRC-e247-preserver-audit"
            )
            non_bug_source_items = [
                item
                for item in source_items
                if item.get("source") != "GRC-e247-preserver-audit"
            ]
            comparable_calculated_total = comparable_total_for_sources(
                baseline_comp=baseline_comp,
                bug_comp=bug_comp,
                bug_source_total=bug_source_total,
                has_non_bug_source=bool(non_bug_source_items),
                has_source=bool(source_items),
                has_full_layer_source=has_full_layer_source(source_items),
            )
            source_weight = sum(parse_int(item.get("source_weight") or item.get("weight")) or 0 for item in source_items)
            source_weight_value = source_weight if source_weight else None
            source_weight_delta = (parse_int(raw["weight"]) or 0) - source_weight if source_weight else None
            source_tolerance = source_match_tolerance(source_items)
            raw_reward_delta_after_sources = calculated_layers_total - source_total
            reward_delta_after_sources = normalize_tiny_delta(raw_reward_delta_after_sources, source_tolerance)
            full_loss_weight = (effective_weight if effective_weight > 0 else full_weight) + adjusted_weight_delta
            full_lost_reward = floor_reward(full_loss_weight, fixed_reward, total_weight)
            full_lost_delta_after_sources = normalize_tiny_delta(full_lost_reward - actual_reward - source_total, source_tolerance)
            bug_base_weight = first_int_from_items(bug_items, "pw_baseline")
            bug_chain_weight = first_int_from_items(bug_items, "chain_bug_weight")
            remaining_after_sources = max(0, reward_delta_after_sources or 0)
            source_excess = max(0, -(reward_delta_after_sources or 0))
            best_match = match_status(baseline_comp, bug_comp, source_total, comparable_calculated_total, source_tolerance)
            source_state = classify_source_state(calculated_layers_total, source_total, bool(source_items), source_tolerance)

            rows.append(
                {
                    "epoch": int(epoch),
                    "address": address,
                    "reason": raw.get("exclusion_reason", ""),
                    "weight": full_weight,
                    "confirmation_weight": parse_int(raw["confirmation_weight"]),
                    "effective_weight": effective_weight,
                    "actual_reward_base_units": actual_reward,
                    "actual_reward_gnk": normalize_gnk(raw["actual_reward_gnk"]),
                    "expected_reward_base_units": parse_int(raw["expected_reward_base_units"]),
                    "expected_reward_gnk": normalize_gnk(raw["expected_reward_gnk"]),
                    "compensation_base_units": baseline_comp,
                    "compensation_gnk": normalize_gnk(raw["compensation_gnk"]),
                    "fixed_epoch_reward": fixed_reward,
                    "total_epoch_weight": total_weight,
                    "notes": notes,
                    "has_loss": baseline_comp > 0 or (bug_comp or 0) > 0 or source_total > 0,
                    "bug_weight_delta": adjusted_weight_delta if adjusted_weight_delta else None,
                    "bug_base_weight": bug_base_weight,
                    "bug_chain_weight": bug_chain_weight,
                    "bug_adjusted_weight": adjusted_weight,
                    "bug_expected_reward_base_units": bug_expected,
                    "bug_expected_reward_gnk": format_gnk(bug_expected) if bug_expected is not None else "",
                    "bug_reward_delta_base_units": bug_reward_delta,
                    "bug_reward_delta_gnk": format_gnk(bug_reward_delta) if bug_reward_delta is not None else "",
                    "bug_compensation_base_units": bug_comp,
                    "bug_compensation_gnk": format_gnk(bug_comp) if bug_comp is not None else "",
                    "bug_details": "; ".join(str(item.get("details") or item.get("reason") or "") for item in bug_items if item),
                    "sources": source_items,
                    "source_weight": source_weight_value,
                    "source_weight_delta": source_weight_delta,
                    "calculated_layers_base_units": calculated_layers_total,
                    "calculated_layers_gnk": format_gnk(calculated_layers_total),
                    "full_lost_reward_base_units": full_lost_reward,
                    "full_lost_reward_gnk": format_gnk(full_lost_reward),
                    "full_loss_weight": full_loss_weight,
                    "source_comparable_calculated_base_units": comparable_calculated_total,
                    "source_comparable_calculated_gnk": format_gnk(comparable_calculated_total) if source_items else "",
                    "source_compensation_base_units": source_total,
                    "source_compensation_gnk": format_gnk(source_total) if source_total else "",
                    "reward_delta_after_sources_base_units": reward_delta_after_sources,
                    "reward_delta_after_sources_gnk": format_gnk(reward_delta_after_sources) if reward_delta_after_sources is not None else "",
                    "full_lost_delta_after_sources_base_units": full_lost_delta_after_sources,
                    "full_lost_delta_after_sources_gnk": format_gnk(full_lost_delta_after_sources) if full_lost_delta_after_sources is not None else "",
                    "remaining_after_sources_base_units": remaining_after_sources,
                    "remaining_after_sources_gnk": format_gnk(remaining_after_sources) if remaining_after_sources else "",
                    "source_excess_base_units": source_excess,
                    "source_excess_gnk": format_gnk(source_excess) if source_excess else "",
                    "source_state": source_state,
                    "match_status": best_match,
                }
            )
    rows.sort(key=lambda item: (item["epoch"], item["address"]))
    return rows


def build_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_epoch: dict[int, dict[str, Any]] = {}
    with SUMMARY_CSV.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            epoch = int(raw["epoch"])
            by_epoch[epoch] = {
                "epoch": epoch,
                "actual_rewarded_coins": parse_int(raw["actual_rewarded_coins"]),
                "expected_reward_base_units": parse_int(raw["expected_reward_base_units"]),
                "compensation_base_units": parse_int(raw["compensation_base_units"]),
                "compensation_gnk": format_gnk(parse_int(raw["compensation_base_units"])),
                "rows_with_loss": 0,
                "source_compensation_base_units": 0,
                "bug_compensation_base_units": 0,
                "remaining_after_sources_base_units": 0,
                "source_excess_base_units": 0,
            }

    for row in rows:
        summary = by_epoch[row["epoch"]]
        if row["has_loss"]:
            summary["rows_with_loss"] += 1
        summary["source_compensation_base_units"] += row["source_compensation_base_units"]
        summary["bug_compensation_base_units"] += row["bug_compensation_base_units"] or 0
        summary["remaining_after_sources_base_units"] += row["remaining_after_sources_base_units"]
        summary["source_excess_base_units"] += row["source_excess_base_units"]

    for summary in by_epoch.values():
        summary["source_compensation_gnk"] = format_gnk(summary["source_compensation_base_units"])
        summary["bug_compensation_gnk"] = format_gnk(summary["bug_compensation_base_units"])
        summary["remaining_after_sources_gnk"] = format_gnk(summary["remaining_after_sources_base_units"])
        summary["source_excess_gnk"] = format_gnk(summary["source_excess_base_units"])
    return [by_epoch[epoch] for epoch in sorted(by_epoch)]


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(Decimal(str(value)))


def floor_reward(weight: int, fixed_reward: int, total_weight: int) -> int:
    if weight <= 0 or fixed_reward <= 0 or total_weight <= 0:
        return 0
    return int((Decimal(weight) * Decimal(fixed_reward) / Decimal(total_weight)).to_integral_value(rounding=ROUND_FLOOR))


def sum_base_units(values: Any) -> int:
    total = 0
    for value in values:
        if value is None or value == "":
            continue
        total += int((Decimal(str(value)) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR))
    return total


def source_item_base_units(item: dict[str, Any]) -> int:
    base_units = item.get("source_compensation_base_units")
    if base_units not in (None, ""):
        return parse_int(base_units) or 0
    value = item.get("source_compensation_gnk")
    if value in (None, ""):
        return 0
    return int((Decimal(str(value)) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR))


def format_gnk(base_units: int | None) -> str:
    if base_units is None:
        return ""
    return format((Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)).quantize(Decimal("0.000000001")), "f")


def normalize_gnk(value: str) -> str:
    return format_gnk(int((Decimal(value) * Decimal(BASE_UNITS_PER_GNK)).to_integral_value(rounding=ROUND_FLOOR)))


def first_int_from_items(items: list[dict[str, Any]], key: str) -> int | None:
    for item in items:
        for field in ("details", "reason"):
            value = str(item.get(field) or "")
            match = re.search(rf"{re.escape(key)}=(\d+)", value)
            if match:
                return int(match.group(1))
            match = re.search(rf"{re.escape(key)}=floor\([^)]*\)=(\d+)", value)
            if match:
                return int(match.group(1))
    return None


def comparable_total_for_sources(
    baseline_comp: int,
    bug_comp: int | None,
    bug_source_total: int,
    has_non_bug_source: bool,
    has_source: bool,
    has_full_layer_source: bool = False,
) -> int:
    if not has_source:
        return baseline_comp
    if has_full_layer_source:
        return baseline_comp + (bug_comp or 0)
    total = 0
    if has_non_bug_source:
        total += baseline_comp
    if bug_source_total:
        total += bug_comp or 0
    return total


def has_full_layer_source(source_items: list[dict[str, Any]]) -> bool:
    return any(item.get("source") in FULL_LAYER_SOURCE_NAMES for item in source_items)


def match_status(
    baseline: int,
    bug_comp: int | None,
    source_total: int,
    comparable_total: int,
    tolerance: int = SOURCE_MATCH_TOLERANCE_BASE_UNITS,
) -> str:
    if source_total <= 0:
        return "no_source"
    if same_base_units(source_total, comparable_total, tolerance):
        return "source_matches_calculated_layers"
    if same_base_units(source_total, baseline, tolerance):
        return "source_matches_baseline"
    if bug_comp is not None and same_base_units(source_total, bug_comp, tolerance):
        return "source_matches_bug_adjusted"
    return "source_differs"


def same_base_units(left: int, right: int, tolerance: int = SOURCE_MATCH_TOLERANCE_BASE_UNITS) -> bool:
    return abs(left - right) <= tolerance


def source_match_tolerance(source_items: list[dict[str, Any]]) -> int:
    tolerances = [
        parse_int(item.get("source_match_tolerance_base_units")) or 0
        for item in source_items
    ]
    return max([SOURCE_MATCH_TOLERANCE_BASE_UNITS, *tolerances])


def classify_source_state(
    baseline: int,
    source_total: int,
    has_source: bool,
    tolerance: int = SOURCE_MATCH_TOLERANCE_BASE_UNITS,
) -> str:
    if not has_source:
        return "no_source"
    if same_base_units(baseline, source_total, tolerance):
        return "collapsed_to_zero"
    if baseline > source_total:
        return "remaining_after_source"
    return "source_exceeds_calculated"


def normalize_tiny_delta(value: int, tolerance: int = SOURCE_MATCH_TOLERANCE_BASE_UNITS) -> int:
    return 0 if abs(value) <= tolerance else value


if __name__ == "__main__":
    raise SystemExit(main())
