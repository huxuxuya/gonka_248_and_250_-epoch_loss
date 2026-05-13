from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
from typing import Any


def compute_fixed_epoch_reward(params_payload: dict[str, Any], epoch: int) -> tuple[int, list[str], bool]:
    notes: list[str] = []
    approximation_used = False

    candidates = _find_integer_candidates(
        params_payload,
        {
            "fixed_epoch_reward",
            "epoch_reward",
            "reward_per_epoch",
            "total_epoch_reward",
        },
    )
    if candidates:
        notes.append("used fixed epoch reward found directly in raw payload")
        return candidates[0], notes, approximation_used

    reward_params = params_payload.get("params", {}).get("bitcoin_reward_params", {})
    initial_reward = Decimal(reward_params.get("initial_epoch_reward", "0"))
    decay_fraction = _legacy_decimal_to_decimal(reward_params.get("decay_rate"))
    genesis_epoch = int(reward_params.get("genesis_epoch", "1"))

    if initial_reward <= 0:
        notes.append("missing bitcoin_reward_params.initial_epoch_reward; fixed reward set to 0")
        return 0, notes, True

    multiplier = Decimal("1") + decay_fraction
    exponent = max(epoch - genesis_epoch, 0)
    reward = initial_reward * (multiplier ** exponent)
    fixed_reward = int(reward.to_integral_value(rounding=ROUND_FLOOR))
    notes.append("approximated fixed epoch reward from bitcoin_reward_params exponential decay")
    approximation_used = True
    return fixed_reward, notes, approximation_used


def determine_epoch_model_scale(
    params_payload: dict[str, Any],
    epoch_group_payload: dict[str, Any],
) -> tuple[Decimal, list[str], bool]:
    model_id = _find_first_string(epoch_group_payload, {"model_id"})
    if not model_id:
        model_id = (
            params_payload.get("params", {})
            .get("delegation_params", {})
            .get("initial_model_id", "")
        )

    models = params_payload.get("params", {}).get("poc_params", {}).get("models", [])
    for model in models:
        if model.get("model_id") != model_id:
            continue
        factor = _legacy_decimal_to_decimal(model.get("weight_scale_factor"))
        if factor > 0:
            return factor, [f"applied model weight_scale_factor for model_id={model_id}"], False

    if model_id:
        return Decimal("1"), [f"model_id={model_id} present but no weight_scale_factor found"], True
    return Decimal("1"), ["model_id not reconstructable; weight_scale_factor defaulted to 1"], True


def parse_exclusion_map(payload: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return {}, ["excluded participant payload had no items list"]

    exclusion_map: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        address = _find_first_string(item, {"participant_id", "participant", "address", "participant_address"})
        reason = _find_first_string(item, {"reason", "exclusion_reason", "status", "message"}) or "excluded"
        if address:
            exclusion_map[address] = reason

    return exclusion_map, [f"parsed {len(exclusion_map)} excluded participants"]


def compute_confirmation_weights(payload: dict[str, Any]) -> tuple[dict[str, int], list[str], bool]:
    events = payload.get("events")
    if not isinstance(events, list):
        return {}, ["confirmation events payload had no events list"], True

    weights: dict[str, int] = {}
    unresolved_events = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        address = _find_first_string(event, {"participant_id", "participant", "address", "participant_address"})
        amount = _find_first_int(event, {"weight", "confirmation_weight", "earned_coins", "value"})
        if address:
            weights[address] = weights.get(address, 0) + max(amount, 1)
        else:
            unresolved_events += 1

    notes = [f"parsed confirmation weights for {len(weights)} participants"]
    approximation_used = unresolved_events > 0
    if unresolved_events:
        notes.append(f"{unresolved_events} confirmation events could not be mapped to participants")
    return weights, notes, approximation_used


def build_participant_weight(
    perf_row: dict[str, Any],
    model_scale_factor: Decimal,
) -> tuple[int, list[str], bool]:
    earned_coins = int(perf_row.get("earned_coins", "0"))
    if earned_coins < 0:
        earned_coins = 0

    if model_scale_factor == Decimal("1"):
        return earned_coins, ["base weight uses earned_coins"], False

    scaled_weight = int(
        (Decimal(earned_coins) * model_scale_factor).to_integral_value(rounding=ROUND_FLOOR)
    )
    return scaled_weight, ["base weight uses earned_coins scaled by model weight_scale_factor"], True


def floor_reward(weight: int, fixed_epoch_reward: int, total_weight: int) -> int:
    if total_weight <= 0 or weight <= 0 or fixed_epoch_reward <= 0:
        return 0
    return int((Decimal(weight) * Decimal(fixed_epoch_reward) / Decimal(total_weight)).to_integral_value(rounding=ROUND_FLOOR))


def _legacy_decimal_to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("1")
    if isinstance(value, dict) and "value" in value and "exponent" in value:
        return Decimal(str(value["value"])) * (Decimal(10) ** int(value["exponent"]))
    return Decimal(str(value))


def _find_integer_candidates(payload: Any, target_keys: set[str]) -> list[int]:
    found: list[int] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in target_keys and isinstance(value, (str, int)) and str(value).lstrip("-").isdigit():
                found.append(int(value))
            found.extend(_find_integer_candidates(value, target_keys))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_find_integer_candidates(item, target_keys))
    return found


def _find_first_string(payload: Any, target_keys: set[str]) -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in target_keys and isinstance(value, str) and value:
                return value
            found = _find_first_string(value, target_keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_string(item, target_keys)
            if found:
                return found
    return ""


def _find_first_int(payload: Any, target_keys: set[str]) -> int:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in target_keys and isinstance(value, (str, int)) and str(value).lstrip("-").isdigit():
                return int(value)
            found = _find_first_int(value, target_keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_int(item, target_keys)
            if found:
                return found
    return 0
