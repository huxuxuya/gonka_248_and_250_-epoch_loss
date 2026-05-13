from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from src.constants import RAW_DATA_DIR
from src.io_utils import format_gnk, load_json
from src.models import EpochComputationResult, RewardComputation, Settings
from src.reward_logic import (
    build_participant_weight,
    compute_confirmation_weights,
    compute_fixed_epoch_reward,
    determine_epoch_model_scale,
    floor_reward,
    parse_exclusion_map,
)


def calculate_epoch_compensation(
    settings: Settings,
    epoch: int,
    raw_dir: Path | None = None,
) -> EpochComputationResult:
    base_dir = (raw_dir or RAW_DATA_DIR) / f"epoch_{epoch}"
    params_payload = load_json(base_dir / "params.json")
    perf_payload = load_json(base_dir / f"epoch_performance_summary_{epoch}.json")
    group_payload = load_json(base_dir / f"epoch_group_data_{epoch}.json")
    excluded_payload = load_json(base_dir / f"excluded_participants_{epoch}.json")

    confirmation_path = base_dir / f"confirmation_poc_events_{epoch}.json"
    confirmation_payload: dict[str, Any] = {"events": []}
    if confirmation_path.exists():
        confirmation_payload = load_json(confirmation_path)

    fixed_epoch_reward, reward_notes, reward_approx = compute_fixed_epoch_reward(params_payload, epoch)
    model_scale, model_notes, model_approx = determine_epoch_model_scale(params_payload, group_payload)
    exclusion_map, exclusion_notes = parse_exclusion_map(excluded_payload)
    confirmation_weights, confirmation_notes, confirmation_approx = compute_confirmation_weights(confirmation_payload)

    applied_steps = reward_notes + model_notes + exclusion_notes + confirmation_notes
    approximation_used = reward_approx or model_approx or confirmation_approx
    limitations: list[str] = []
    if reward_approx:
        limitations.append("fixed epoch reward approximated from params payload")
    if model_approx:
        limitations.append("model scaling was partial or defaulted")
    if confirmation_approx:
        limitations.append("confirmation weights were unavailable or partially reconstructable")

    perf_rows = perf_payload.get("epochPerformanceSummary", [])
    participants: list[dict[str, Any]] = []
    for perf_row in perf_rows:
        address = perf_row.get("participant_id", "")
        weight, weight_notes, weight_approx = build_participant_weight(perf_row, model_scale)
        approximation_used = approximation_used or weight_approx
        if weight_approx:
            limitations.append("base weight used scaled earned_coins approximation")

        confirmation_weight = confirmation_weights.get(address, 0)
        exclusion_reason = exclusion_map.get(address, "")
        effective_weight = 0 if exclusion_reason else weight + confirmation_weight
        notes = list(weight_notes)
        if exclusion_reason:
            notes.append("effective weight set to 0 because participant is excluded in raw endpoint")
        if confirmation_weight:
            notes.append("confirmation weight added from confirmation_poc_events")

        participants.append(
            {
                "address": address,
                "weight": weight,
                "confirmation_weight": confirmation_weight,
                "effective_weight": effective_weight,
                "actual_rewarded_coins": int(perf_row.get("rewarded_coins", "0")),
                "exclusion_reason": exclusion_reason,
                "notes": "; ".join(notes),
            }
        )

    participants.sort(key=lambda item: item["address"])
    total_epoch_weight = sum(item["effective_weight"] for item in participants)
    reward_rate = (
        Decimal(fixed_epoch_reward) / Decimal(total_epoch_weight)
        if total_epoch_weight > 0
        else Decimal("0")
    )

    rows: list[RewardComputation] = []
    for participant in participants:
        expected_reward = floor_reward(
            participant["effective_weight"],
            fixed_epoch_reward,
            total_epoch_weight,
        )
        actual_reward = participant["actual_rewarded_coins"]
        compensation = max(0, expected_reward - actual_reward)

        row = RewardComputation(
            address=participant["address"],
            epoch=epoch,
            exclusion_reason=participant["exclusion_reason"],
            weight=participant["weight"],
            confirmation_weight=participant["confirmation_weight"],
            effective_weight=participant["effective_weight"],
            fixed_epoch_reward=fixed_epoch_reward,
            total_epoch_weight=total_epoch_weight,
            reward_rate_base_units_per_weight=reward_rate,
            actual_rewarded_coins=actual_reward,
            expected_reward_base_units=expected_reward,
            compensation_base_units=compensation,
            expected_reward_gnk=format_gnk(expected_reward, settings.output_precision_gnk),
            actual_reward_gnk=format_gnk(actual_reward, settings.output_precision_gnk),
            compensation_gnk=format_gnk(compensation, settings.output_precision_gnk),
            notes=participant["notes"],
        )
        rows.append(row)

    return EpochComputationResult(
        epoch=epoch,
        rows=rows,
        approximation_used=approximation_used,
        applied_steps=_dedupe(applied_steps),
        limitations=_dedupe(limitations),
        fixed_epoch_reward=fixed_epoch_reward,
        total_epoch_weight=total_epoch_weight,
    )


def load_processed_epoch(path: Path) -> dict[str, Any]:
    return load_json(path)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
