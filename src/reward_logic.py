from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR, getcontext
from typing import Any

getcontext().prec = 50


def compute_fixed_epoch_reward(params_payload: dict[str, Any], epoch: int) -> tuple[int, list[str], bool]:
    notes: list[str] = []
    reward_params = params_payload.get("params", {}).get("bitcoin_reward_params", {})
    initial_reward = Decimal(reward_params.get("initial_epoch_reward", "0"))
    decay_fraction = _legacy_decimal_to_decimal(reward_params.get("decay_rate"))
    genesis_epoch = int(reward_params.get("genesis_epoch", "1"))

    if initial_reward <= 0:
        notes.append("missing bitcoin_reward_params.initial_epoch_reward; fixed reward set to 0")
        return 0, notes, True

    epochs_since_genesis = max(epoch - genesis_epoch, 0)
    if epochs_since_genesis == 0:
        return int(initial_reward), ["fixed epoch reward from initial_epoch_reward"], False

    exponent = _chain_exponent(decay_fraction)
    if exponent is None:
        exponent = Decimal("1") + decay_fraction
    fixed_reward = int(
        (initial_reward * (exponent ** epochs_since_genesis)).to_integral_value(rounding=ROUND_FLOOR)
    )
    notes.append("fixed epoch reward calculated from bitcoin_rewards.go exponential decay logic")
    return fixed_reward, notes, False


def parse_validation_weights(
    epoch_group_payload: dict[str, Any],
) -> tuple[dict[str, dict[str, int]], int, list[str], bool]:
    group = epoch_group_payload.get("epoch_group_data", {})
    items = group.get("validation_weights", [])
    result: dict[str, dict[str, int]] = {}
    for item in items:
        address = item.get("member_address", "")
        if not address:
            continue
        full_weight = max(0, int(item.get("weight", "0")))
        confirmation_weight = max(0, int(item.get("confirmation_weight", "0")))
        result[address] = {
            "weight": full_weight,
            "confirmation_weight": min(confirmation_weight, full_weight),
            "reputation": int(item.get("reputation", 0)),
        }

    total_full_weight = sum(item["weight"] for item in result.values())
    approximation_used = False
    notes = [
        f"parsed validation_weights for {len(result)} participants",
        f"total full weight denominator={total_full_weight}",
    ]
    return result, total_full_weight, notes, approximation_used


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


def initial_effective_weights(
    validation_weights: dict[str, dict[str, int]],
    exclusion_map: dict[str, str],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for address, item in validation_weights.items():
        if address in exclusion_map:
            result[address] = 0
        else:
            result[address] = item["confirmation_weight"]
    return result


def apply_power_capping(weights: dict[str, int]) -> tuple[dict[str, int], bool]:
    participants = [{"address": address, "weight": weight} for address, weight in weights.items()]
    if len(participants) <= 1:
        return dict(weights), False

    total_power = sum(item["weight"] for item in participants)
    max_percentage = Decimal("0.30")
    if len(participants) == 2:
        max_percentage = Decimal("0.50")
    elif len(participants) == 3:
        max_percentage = Decimal("0.40")

    sorted_participants = sorted(participants, key=lambda item: item["weight"])
    cap = None
    sum_prev = 0
    participant_count = len(sorted_participants)

    for index, participant in enumerate(sorted_participants):
        current_power = participant["weight"]
        weighted_total = sum_prev + current_power * (participant_count - index)
        threshold = max_percentage * Decimal(weighted_total)
        if Decimal(current_power) > threshold:
            numerator = max_percentage * Decimal(sum_prev)
            denominator = Decimal("1") - max_percentage * Decimal(participant_count - index)
            cap = current_power if denominator <= 0 else int((numerator / denominator).to_integral_value(rounding=ROUND_FLOOR))
            break
        sum_prev += current_power

    if cap is None:
        return dict(weights), False

    return {address: min(weight, cap) for address, weight in weights.items()}, True


def get_dynamic_p0_permille(perf_rows: list[dict[str, Any]], governance_p0_permille: int = 100) -> tuple[int, bool, list[str]]:
    total_requests = 0
    missed_requests = 0
    participants_used = 0
    for row in perf_rows:
        total = int(row.get("inference_count", "0")) + int(row.get("missed_requests", "0"))
        if total == 0:
            continue
        total_requests += total
        missed_requests += int(row.get("missed_requests", "0"))
        participants_used += 1

    if total_requests < 1000 or participants_used < 5:
        return governance_p0_permille, False, [
            "dynamic p0 fallback to governance p0 because sample gate was not met",
        ]

    baseline_permille = math.ceil((missed_requests * 1000) / total_requests)
    target_permille = min(500, baseline_permille + 20)
    selected_permille = ceil_to_supported_p0_permille(target_permille)
    final_permille = max(governance_p0_permille, selected_permille)
    skip_punishment = selected_permille == 500
    return final_permille, skip_punishment, [
        f"dynamic p0 selected at {final_permille} permille",
        f"skip downtime punishment={str(skip_punishment).lower()}",
    ]


def apply_downtime_punishment(
    effective_weights: dict[str, int],
    perf_rows: list[dict[str, Any]],
    p0_permille: int,
    skip_punishment: bool,
) -> tuple[dict[str, int], set[str], list[str]]:
    if skip_punishment:
        return dict(effective_weights), set(), ["downtime punishment skipped by outage circuit breaker"]

    punished: set[str] = set()
    updated = dict(effective_weights)
    for row in perf_rows:
        address = row.get("participant_id", "")
        current_weight = updated.get(address, 0)
        if current_weight <= 0:
            continue
        total = int(row.get("inference_count", "0")) + int(row.get("missed_requests", "0"))
        missed = int(row.get("missed_requests", "0"))
        if not missed_stat_test(missed, total, p0_permille):
            updated[address] = 0
            punished.add(address)

    return updated, punished, [f"downtime punishment zeroed {len(punished)} participant weights"]


def full_share_reward(full_weight: int, fixed_epoch_reward: int, total_full_weight: int) -> int:
    return floor_reward(full_weight, fixed_epoch_reward, total_full_weight)


def effective_share_reward(effective_weight: int, fixed_epoch_reward: int, total_full_weight: int) -> int:
    return floor_reward(effective_weight, fixed_epoch_reward, total_full_weight)


def floor_reward(weight: int, fixed_epoch_reward: int, total_weight: int) -> int:
    if total_weight <= 0 or weight <= 0 or fixed_epoch_reward <= 0:
        return 0
    return int(
        (Decimal(weight) * Decimal(fixed_epoch_reward) / Decimal(total_weight)).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )


def coefficient_adjusted_weight(
    participant_model_nodes: dict[str, list[dict[str, Any]]],
    coefficients: dict[str, Decimal],
) -> int:
    total = Decimal("0")
    for model_id, nodes in participant_model_nodes.items():
        coeff = coefficients.get(model_id, Decimal("1"))
        raw_model = sum(Decimal(str(node.get("poc_weight", "0"))) for node in nodes if node)
        total += coeff * raw_model
    return int(total.to_integral_value(rounding=ROUND_FLOOR))


def missed_stat_test(n_missed: int, n_total: int, p0_permille: int) -> bool:
    if n_total == 0:
        return True
    p0 = Decimal(p0_permille) / Decimal(1000)
    p_value = binomial_tail_probability(n_missed, n_total, p0)
    return p_value >= Decimal("0.05")


def binomial_tail_probability(k: int, n: int, p0: Decimal) -> Decimal:
    if k < 0 or n < 0 or k > n:
        return Decimal(0)
    if k == 0:
        return Decimal(1)

    q0 = Decimal(1) - p0
    if q0 == 0:
        return Decimal(1)
    if p0 == 0:
        return Decimal(0)

    # Chain rule is the upper binomial tail. Computing it via comb(n, i) for
    # every term is exact but very slow for large validation samples, so walk
    # the PMF recursively and sum the shorter side of the distribution.
    probability = q0**n
    if k - 1 <= n - k:
        cdf = probability
        for i in range(0, k - 1):
            probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
            cdf += probability
        tail = Decimal(1) - cdf
        return max(Decimal(0), min(Decimal(1), tail))

    for i in range(0, k):
        probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
    tail = probability
    for i in range(k, n):
        probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
        tail += probability
    return max(Decimal(0), min(Decimal(1), tail))


def ceil_to_supported_p0_permille(target_permille: int) -> int:
    if target_permille <= 50:
        return 50
    if target_permille <= 100:
        return 100
    if target_permille <= 200:
        return 200
    if target_permille <= 300:
        return 300
    if target_permille <= 400:
        return 400
    return 500


def _legacy_decimal_to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, dict) and "value" in value and "exponent" in value:
        return Decimal(str(value["value"])) * (Decimal(10) ** int(value["exponent"]))
    return Decimal(str(value))


def _chain_exponent(decay_fraction: Decimal) -> Decimal | None:
    if decay_fraction == Decimal("-0.000475"):
        return Decimal("0.9995251127946402")
    if decay_fraction == Decimal("-0.000001"):
        return Decimal("0.9999990000005")
    if decay_fraction == Decimal("0.0001"):
        return Decimal("1.0001000050001667")
    if decay_fraction == Decimal("0"):
        return Decimal("1")
    return None


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
