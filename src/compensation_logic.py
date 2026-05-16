from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from src.constants import RAW_DATA_DIR
from src.io_utils import format_gnk, load_json
from src.models import EpochComputationResult, RewardComputation, Settings
from src.reward_logic import (
    apply_downtime_punishment,
    compute_fixed_epoch_reward,
    effective_share_reward,
    full_share_reward,
    get_dynamic_p0_permille,
    parse_exclusion_map,
    parse_validation_weights,
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

    fixed_epoch_reward, reward_notes, reward_approx = compute_fixed_epoch_reward(params_payload, epoch)
    validation_weights, total_full_weight, weight_notes, weight_approx = parse_validation_weights(group_payload)
    exclusion_map, exclusion_notes = parse_exclusion_map(excluded_payload)
    subgroup_voting_power, subgroup_notes, subgroup_complete = load_participant_subgroup_voting_power(base_dir, epoch)

    expected_effective_weights = {
        address: min(
            validation_weights.get(address, {}).get("confirmation_weight", 0),
            subgroup_voting_power.get(address, validation_weights.get(address, {}).get("confirmation_weight", 0)),
        )
        for address in validation_weights
    }
    effective_candidates = {
        address: (
            0
            if address in exclusion_map
            else expected_effective_weights.get(address, 0)
        )
        for address in validation_weights
    }
    perf_rows = perf_payload.get("epochPerformanceSummary", [])
    governance_p0_permille = 100
    p0_permille, skip_punishment, p0_notes = get_dynamic_p0_permille(
        perf_rows,
        governance_p0_permille=governance_p0_permille,
    )
    effective_after_downtime, punished_addresses, downtime_notes = apply_downtime_punishment(
        effective_candidates,
        perf_rows,
        p0_permille,
        skip_punishment,
    )

    perf_map = {row.get("participant_id", ""): row for row in perf_rows}
    participant_addresses = sorted(
        set(validation_weights)
        | set(perf_map)
        | set(exclusion_map)
    )

    approximation_used = reward_approx or weight_approx
    limitations: list[str] = []
    if weight_approx or not subgroup_complete:
        approximation_used = True
        limitations.append("subgroup voting_power snapshots were not reconstructable from cached raw data")

    applied_steps = reward_notes + weight_notes + exclusion_notes + subgroup_notes + p0_notes + downtime_notes
    applied_steps.append("effective weight = min(confirmation_weight, subgroup_voting_power)")

    rows: list[RewardComputation] = []
    total_epoch_weight = total_full_weight

    for address in participant_addresses:
        perf_row = perf_map.get(address, {})
        full_weight = validation_weights.get(address, {}).get("weight", 0)
        confirmation_weight = validation_weights.get(address, {}).get("confirmation_weight", 0)
        effective_weight = effective_after_downtime.get(address, 0)
        expected_effective_weight = expected_effective_weights.get(address, 0)
        expected_reward_weight = full_weight if confirmation_weight == 0 else expected_effective_weight
        actual_reward = int(perf_row.get("rewarded_coins", "0") or 0)
        exclusion_reason = exclusion_map.get(address, "")
        full_share = full_share_reward(full_weight, fixed_epoch_reward, total_full_weight)
        effective_share = effective_share_reward(effective_weight, fixed_epoch_reward, total_full_weight)
        expected_share = effective_share_reward(expected_reward_weight, fixed_epoch_reward, total_full_weight)
        compensation = max(0, expected_share - actual_reward)

        notes: list[str] = []
        if exclusion_reason:
            notes.append("participant excluded from distribution")
        if address in punished_addresses:
            notes.append("downtime punishment reduced effective reward to zero")
        if confirmation_weight > effective_weight:
            notes.append("subgroup voting_power capped the confirmation weight")
        notes.append(f"chain_effective_reward_base_units={effective_share}")
        notes.append(f"full_weight_reward_base_units={full_share}")
        notes.append(f"expected_reward_weight={expected_reward_weight}")
        notes.append(f"expected_reward_base_units={expected_share}")

        row = RewardComputation(
            address=address,
            epoch=epoch,
            exclusion_reason=determine_loss_reason(
                address,
                exclusion_reason,
                full_weight,
                confirmation_weight,
                effective_weight,
                perf_row,
                punished_addresses,
            ),
            weight=full_weight,
            confirmation_weight=confirmation_weight,
            effective_weight=effective_weight,
            fixed_epoch_reward=fixed_epoch_reward,
            total_epoch_weight=total_epoch_weight,
            reward_rate_base_units_per_weight=(
                Decimal(fixed_epoch_reward) / Decimal(total_full_weight)
                if total_full_weight
                else Decimal("0")
            ),
            actual_rewarded_coins=actual_reward,
            expected_reward_base_units=expected_share,
            compensation_base_units=compensation,
            expected_reward_gnk=format_gnk(expected_share, settings.output_precision_gnk),
            actual_reward_gnk=format_gnk(actual_reward, settings.output_precision_gnk),
            compensation_gnk=format_gnk(compensation, settings.output_precision_gnk),
            notes="; ".join(notes),
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


def determine_loss_reason(
    address: str,
    exclusion_reason: str,
    full_weight: int,
    confirmation_weight: int,
    effective_weight: int,
    perf_row: dict[str, Any],
    punished_addresses: set[str],
) -> str:
    if exclusion_reason:
        return exclusion_reason
    if address in punished_addresses or (effective_weight == 0 and int(perf_row.get("missed_requests", "0") or 0) > 0):
        return "missed_requests"
    if full_weight > confirmation_weight:
        return "confirmation_weight_reduction"
    if confirmation_weight > effective_weight:
        return "subgroup_voting_power_reduction"
    return ""


def load_participant_subgroup_voting_power(
    base_dir: Path,
    epoch: int,
) -> tuple[dict[str, int], list[str], bool]:
    participant_voting_power: dict[str, int] = {}
    notes: list[str] = []
    subgroup_files = sorted(base_dir.glob(f"epoch_group_data_{epoch}__*.json"))
    if not subgroup_files:
        return participant_voting_power, [f"no model-specific subgroup files found for epoch {epoch}"], False

    complete = True
    for path in subgroup_files:
        payload = load_json(path)
        group = payload.get("epoch_group_data", {})
        model_id = group.get("model_id", "")
        if not model_id:
            continue
        validation_weights = group.get("validation_weights", [])
        notes.append(f"loaded subgroup {model_id} with {len(validation_weights)} validation weights")
        for item in validation_weights:
            address = item.get("member_address", "")
            if not address:
                continue
            participant_voting_power[address] = participant_voting_power.get(address, 0) + int(item.get("voting_power", "0") or 0)

    expected_models = set(
        item
        for item in (load_json(base_dir / f"epoch_group_data_{epoch}.json").get("epoch_group_data", {}).get("sub_group_models", []) or [])
        if item
    )
    found_models = {
        load_json(path).get("epoch_group_data", {}).get("model_id", "")
        for path in subgroup_files
        if load_json(path).get("epoch_group_data", {}).get("model_id", "")
    }
    if expected_models and expected_models != found_models:
        complete = False
        notes.append(f"expected subgroup models {sorted(expected_models)} but found {sorted(found_models)}")
    elif expected_models:
        notes.append(f"loaded all subgroup models {sorted(expected_models)}")

    return participant_voting_power, notes, complete


def _legacy_decimal_to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict) and "value" in value and "exponent" in value:
        return Decimal(str(value["value"])) * (Decimal(10) ** int(value["exponent"]))
    return Decimal(str(value))


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
