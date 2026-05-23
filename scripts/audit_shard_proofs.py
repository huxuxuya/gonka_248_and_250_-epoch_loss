#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, getcontext
from pathlib import Path
from typing import Any

getcontext().prec = 50

DEFAULT_NODES = (
    "http://node1.gonka.ai:8000",
    "http://node2.gonka.ai:8000",
    "http://node3.gonka.ai:8000",
)


@dataclass(frozen=True)
class FetchResult:
    node: str
    endpoint: str
    epoch: int | None
    model_id: str
    label: str
    status: str
    path: str
    sha256: str
    size_bytes: int
    fetched_at_utc: str
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preserve and analyze Gonka shard proof data.")
    parser.add_argument("--nodes", nargs="+", default=list(DEFAULT_NODES), help="Node base URLs to audit")
    parser.add_argument("--epochs", nargs="+", type=int, help="Epochs to preserve and analyze")
    parser.add_argument("--latest-window", type=int, default=4, help="Epoch count to audit when --epochs is omitted")
    parser.add_argument("--timeout-sec", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--reuse-manifest", help="Rebuild analysis files from an existing manifest.json without refetching")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) if args.out_dir else Path("outputs") / "shard_proof_audit" / run_id
    raw_dir = out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.reuse_manifest:
        manifest_payload = load_json(Path(args.reuse_manifest))
        manifest = [FetchResult(**item) for item in manifest_payload.get("files", [])]
        nodes = manifest_payload.get("nodes", [])
        epochs = manifest_payload.get("epochs", [])
        latest_by_node = manifest_payload.get("latest_by_node", {})
        rebuild_analysis(out_dir, run_id, nodes, epochs, latest_by_node, manifest)
        print(f"rebuilt audit package: {out_dir}", flush=True)
        return 0

    nodes = [node.rstrip("/") for node in args.nodes]
    latest_by_node = {}
    for node in nodes:
        try:
            latest_by_node[node] = detect_latest_epoch(node, args.timeout_sec, args.retries)
        except RuntimeError as exc:
            print(f"latest detection failed node={node}: {exc}", flush=True)
            latest_by_node[node] = None
    latest_candidates = [item for item in latest_by_node.values() if item is not None]
    if not latest_candidates and not args.epochs:
        raise SystemExit("could not detect latest epoch from any node; pass --epochs explicitly")

    if args.epochs:
        epochs = sorted(set(args.epochs))
    else:
        latest_epoch = max(latest_candidates)
        finalized_epoch = latest_epoch - 1 if latest_epoch > 0 else latest_epoch
        start_epoch = max(0, finalized_epoch - args.latest_window + 1)
        epochs = list(range(start_epoch, finalized_epoch + 1))

    manifest: list[FetchResult] = []
    for node in nodes:
        print(f"preserving node={node} epochs={epochs}", flush=True)
        node_slug = slugify_node(node)
        node_dir = raw_dir / node_slug
        params_result = fetch_and_save(
            node=node,
            endpoint="/chain-api/productscience/inference/inference/params",
            params={},
            epoch=None,
            model_id="",
            label="params",
            out_path=node_dir / "params.json",
            timeout_sec=args.timeout_sec,
            retries=args.retries,
        )
        manifest.append(params_result)

        for epoch in epochs:
            epoch_dir = node_dir / f"epoch_{epoch}"
            base_result = fetch_and_save(
                node=node,
                endpoint=f"/chain-api/productscience/inference/inference/epoch_group_data/{epoch}",
                params={},
                epoch=epoch,
                model_id="",
                label="epoch_group_data",
                out_path=epoch_dir / "epoch_group_data.json",
                timeout_sec=args.timeout_sec,
                retries=args.retries,
            )
            manifest.append(base_result)

            payload = load_json_if_ok(base_result)
            subgroup_models = (
                payload.get("epoch_group_data", {}).get("sub_group_models", []) if isinstance(payload, dict) else []
            )
            for model_id in subgroup_models:
                subgroup_result = fetch_and_save(
                    node=node,
                    endpoint=f"/chain-api/productscience/inference/inference/epoch_group_data/{epoch}",
                    params={"model_id": model_id},
                    epoch=epoch,
                    model_id=model_id,
                    label="epoch_group_data_model",
                    out_path=epoch_dir / f"epoch_group_data__{slugify_model(model_id)}.json",
                    timeout_sec=args.timeout_sec,
                    retries=args.retries,
                )
                manifest.append(subgroup_result)

            for label, endpoint in (
                ("epoch_performance_summary", f"/chain-api/productscience/inference/inference/epoch_performance_summary/{epoch}"),
                ("excluded_participants", f"/chain-api/productscience/inference/inference/excluded_participants/{epoch}"),
                ("confirmation_poc_events", f"/chain-api/productscience/inference/inference/confirmation_poc_events/{epoch}"),
            ):
                result = fetch_and_save(
                    node=node,
                    endpoint=endpoint,
                    params={},
                    epoch=epoch,
                    model_id="",
                    label=label,
                    out_path=epoch_dir / f"{label}.json",
                    timeout_sec=args.timeout_sec,
                    retries=args.retries,
                )
                manifest.append(result)

    manifest_rows = [result.__dict__ for result in manifest]
    write_json(out_dir / "manifest.json", {"run_id": run_id, "nodes": nodes, "epochs": epochs, "latest_by_node": latest_by_node, "files": manifest_rows})
    write_csv(out_dir / "manifest.csv", manifest_rows, list(FetchResult.__dataclass_fields__))

    rebuild_analysis(out_dir, run_id, nodes, epochs, latest_by_node, manifest)

    print(f"wrote audit package: {out_dir}", flush=True)
    return 0


def rebuild_analysis(
    out_dir: Path,
    run_id: str,
    nodes: list[str],
    epochs: list[int],
    latest_by_node: dict[str, int | None],
    manifest: list[FetchResult],
) -> None:
    node_consensus = build_node_consensus(manifest)
    signature_coverage = build_signature_coverage(manifest)
    participant_rows, anomaly_rows = build_participant_tables(manifest)

    write_csv(out_dir / "node_consensus.csv", node_consensus, [
        "epoch", "label", "model_id", "node_count", "ok_count", "hash_count", "consensus", "sha256_values", "errors",
    ])
    write_csv(out_dir / "signature_coverage.csv", signature_coverage, [
        "node", "epoch", "label", "model_id", "epoch_group_id", "number_of_requests", "previous_epoch_requests",
        "validation_weights_count", "signature_count", "nonempty_signature_count", "signed_weight_address_count",
        "signature_only_count", "weight_only_count", "validation_binom_test_p0", "validation_miss_percentage_cutoff",
    ])
    write_csv(out_dir / "participant_proof_table.csv", participant_rows, [
        "node", "epoch", "address", "has_performance_summary", "signed_base", "signed_models", "validation_models", "weight",
        "confirmation_weight", "subgroup_voting_power", "model_raw_weight", "model_coefficient_weight",
        "expected_weight", "expected_weight_reason", "inference_count", "missed_requests",
        "total_requests", "miss_rate", "p_value", "passes_downtime_test", "exclusion_reason",
        "exclusion_block_height", "earned_coins", "rewarded_coins", "burned_coins", "claimed",
        "expected_reward_base_units", "reward_gap_base_units", "classification",
    ])
    write_csv(out_dir / "settlement_anomalies.csv", anomaly_rows, [
        "node", "epoch", "address", "has_performance_summary", "signed_base", "signed_models", "validation_models", "weight",
        "confirmation_weight", "subgroup_voting_power", "model_raw_weight", "model_coefficient_weight",
        "expected_weight", "expected_weight_reason", "inference_count", "missed_requests",
        "total_requests", "miss_rate", "p_value", "passes_downtime_test", "exclusion_reason",
        "exclusion_block_height", "earned_coins", "rewarded_coins", "burned_coins", "claimed",
        "expected_reward_base_units", "reward_gap_base_units", "classification",
    ])
    write_report(out_dir, run_id, nodes, epochs, latest_by_node, manifest, node_consensus, signature_coverage, participant_rows, anomaly_rows)


def detect_latest_epoch(node: str, timeout_sec: int, retries: int) -> int | None:
    payload = fetch_json(
        node,
        "/chain-api/productscience/inference/inference/epoch_group_data",
        {"pagination.limit": "1", "pagination.reverse": "true"},
        timeout_sec,
        retries,
    )
    items = payload.get("epoch_group_data") if isinstance(payload, dict) else None
    if not items:
        return None
    try:
        return int(items[0].get("epoch_index", "0"))
    except (TypeError, ValueError):
        return None


def fetch_and_save(
    *,
    node: str,
    endpoint: str,
    params: dict[str, str],
    epoch: int | None,
    model_id: str,
    label: str,
    out_path: Path,
    timeout_sec: int,
    retries: int,
) -> FetchResult:
    fetched_at = utc_now_iso()
    try:
        payload = fetch_json(node, endpoint, params, timeout_sec, retries)
        write_json(out_path, payload)
        digest = sha256_file(out_path)
        return FetchResult(
            node=node,
            endpoint=endpoint_with_params(endpoint, params),
            epoch=epoch,
            model_id=model_id,
            label=label,
            status="ok",
            path=str(out_path),
            sha256=digest,
            size_bytes=out_path.stat().st_size,
            fetched_at_utc=fetched_at,
        )
    except Exception as exc:
        error_path = out_path.with_suffix(".error.json")
        write_json(error_path, {"error": str(exc), "node": node, "endpoint": endpoint_with_params(endpoint, params), "fetched_at_utc": fetched_at})
        return FetchResult(
            node=node,
            endpoint=endpoint_with_params(endpoint, params),
            epoch=epoch,
            model_id=model_id,
            label=label,
            status="error",
            path=str(error_path),
            sha256=sha256_file(error_path),
            size_bytes=error_path.stat().st_size,
            fetched_at_utc=fetched_at,
            error=str(exc),
        )


def fetch_json(node: str, endpoint: str, params: dict[str, str], timeout_sec: int, retries: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{node}{endpoint}"
    if query:
        url = f"{url}?{query}"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "gonka-shard-proof-audit/1.0"})
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 + attempt, 5))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def build_node_consensus(manifest: list[FetchResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int | None, str, str], list[FetchResult]] = defaultdict(list)
    for result in manifest:
        if result.epoch is None:
            continue
        grouped[(result.epoch, result.label, result.model_id)].append(result)

    rows: list[dict[str, Any]] = []
    for (epoch, label, model_id), results in sorted(grouped.items(), key=lambda item: (item[0][0] or -1, item[0][1], item[0][2])):
        ok_results = [result for result in results if result.status == "ok"]
        hashes = sorted({result.sha256 for result in ok_results})
        errors = [f"{result.node}: {result.error}" for result in results if result.status != "ok"]
        rows.append({
            "epoch": epoch,
            "label": label,
            "model_id": model_id,
            "node_count": len(results),
            "ok_count": len(ok_results),
            "hash_count": len(hashes),
            "consensus": len(ok_results) >= 2 and len(hashes) == 1,
            "sha256_values": ";".join(hashes),
            "errors": " | ".join(errors),
        })
    return rows


def build_signature_coverage(manifest: list[FetchResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in manifest:
        if result.status != "ok" or result.label not in {"epoch_group_data", "epoch_group_data_model"}:
            continue
        payload = load_json(Path(result.path))
        group = payload.get("epoch_group_data", {})
        signatures = group.get("member_seed_signatures", []) or []
        weights = group.get("validation_weights", []) or []
        signer_addresses = {item.get("member_address", "") for item in signatures if item.get("member_address")}
        nonempty_signer_addresses = {item.get("member_address", "") for item in signatures if item.get("member_address") and item.get("signature")}
        weight_addresses = {item.get("member_address", "") for item in weights if item.get("member_address")}
        validation_params = group.get("validation_params") or {}
        rows.append({
            "node": result.node,
            "epoch": result.epoch,
            "label": result.label,
            "model_id": result.model_id or group.get("model_id", ""),
            "epoch_group_id": group.get("epoch_group_id", ""),
            "number_of_requests": group.get("number_of_requests", ""),
            "previous_epoch_requests": group.get("previous_epoch_requests", ""),
            "validation_weights_count": len(weights),
            "signature_count": len(signatures),
            "nonempty_signature_count": sum(1 for item in signatures if item.get("signature")),
            "signed_weight_address_count": len(nonempty_signer_addresses & weight_addresses),
            "signature_only_count": len(signer_addresses - weight_addresses),
            "weight_only_count": len(weight_addresses - signer_addresses),
            "validation_binom_test_p0": legacy_decimal_to_text(validation_params.get("binom_test_p0")),
            "validation_miss_percentage_cutoff": legacy_decimal_to_text(validation_params.get("miss_percentage_cutoff")),
        })
    return rows


def build_participant_tables(manifest: list[FetchResult]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[tuple[str, int], dict[str, FetchResult]] = defaultdict(dict)
    model_results: dict[tuple[str, int], list[FetchResult]] = defaultdict(list)
    params_by_node: dict[str, FetchResult] = {}
    for result in manifest:
        if result.label == "params" and result.status == "ok":
            params_by_node[result.node] = result
        if result.epoch is None:
            continue
        key = (result.node, result.epoch)
        if result.label == "epoch_group_data_model":
            model_results[key].append(result)
        else:
            by_key[key][result.label] = result

    rows: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for key, results in sorted(by_key.items(), key=lambda item: (item[0][0], item[0][1])):
        node, epoch = key
        group_result = results.get("epoch_group_data")
        perf_result = results.get("epoch_performance_summary")
        if not group_result or group_result.status != "ok":
            continue
        group_payload = load_json(Path(group_result.path))
        group = group_payload.get("epoch_group_data", {})
        params_payload = load_json(Path(params_by_node[node].path)) if node in params_by_node else {}
        fixed_reward = compute_fixed_epoch_reward(params_payload, epoch)
        coefficients = model_coefficients(params_payload)
        validation_params = group.get("validation_params") or {}
        p0_permille = decimal_to_permille(validation_params.get("binom_test_p0"), default=100)

        base_weights = parse_weights(group.get("validation_weights", []) or [])
        base_signed = signed_addresses(group)
        model_signed: dict[str, set[str]] = defaultdict(set)
        model_weights: dict[str, set[str]] = defaultdict(set)
        subgroup_voting_power: dict[str, int] = defaultdict(int)
        subgroup_confirmation_weight: dict[str, int] = defaultdict(int)
        model_raw_weight: dict[str, int] = defaultdict(int)
        model_coefficient_weight: dict[str, int] = defaultdict(int)
        for model_result in model_results.get(key, []):
            if model_result.status != "ok":
                continue
            model_payload = load_json(Path(model_result.path))
            model_group = model_payload.get("epoch_group_data", {})
            model_id = model_result.model_id or model_group.get("model_id", "")
            model_signed[model_id] = signed_addresses(model_group)
            model_weight_rows = model_group.get("validation_weights", []) or []
            model_weights[model_id] = {item.get("member_address", "") for item in model_weight_rows if item.get("member_address")}
            for item in model_weight_rows:
                address = item.get("member_address", "")
                if not address:
                    continue
                subgroup_voting_power[address] += safe_int(item.get("voting_power"))
                subgroup_confirmation_weight[address] += safe_int(item.get("confirmation_weight"))
                raw_weight = sum(max(0, safe_int(node.get("poc_weight"))) for node in item.get("ml_nodes", []) or [])
                model_raw_weight[address] += raw_weight
                model_coefficient_weight[address] += coefficient_adjusted_weight(raw_weight, coefficients.get(model_id, Decimal(1)))

        has_performance_summary = bool(perf_result and perf_result.status == "ok")
        perf_map = parse_perf(load_json(Path(perf_result.path)) if has_performance_summary else {})
        excluded_map = parse_excluded(load_json(Path(results["excluded_participants"].path)) if results.get("excluded_participants") and results["excluded_participants"].status == "ok" else {})
        addresses = sorted(set(base_weights) | set(base_signed) | set(perf_map) | set(excluded_map) | set(subgroup_voting_power))
        total_full_weight = sum(item["weight"] for item in base_weights.values())
        for address in addresses:
            weights = base_weights.get(address, {"weight": 0, "confirmation_weight": 0})
            perf = perf_map.get(address, {})
            exclusion = excluded_map.get(address, {})
            signed_models = sorted(model_id for model_id, addresses_for_model in model_signed.items() if address in addresses_for_model)
            validation_models = sorted(model_id for model_id, addresses_for_model in model_weights.items() if address in addresses_for_model)
            confirmation_weight = weights["confirmation_weight"]
            voting_power = subgroup_voting_power.get(address, 0)
            expected_weight, expected_weight_reason = select_expected_weight(
                weights["weight"],
                confirmation_weight,
                voting_power,
                subgroup_confirmation_weight.get(address, 0),
                exclusion.get("reason", ""),
                model_coefficient_weight.get(address, 0),
            )
            expected_reward = floor_reward(expected_weight, fixed_reward, total_full_weight)
            rewarded = safe_int(perf.get("rewarded_coins"))
            inference_count = safe_int(perf.get("inference_count"))
            missed_requests = safe_int(perf.get("missed_requests"))
            total_requests = inference_count + missed_requests
            miss_rate = Decimal(missed_requests) / Decimal(total_requests) if total_requests else Decimal(0)
            p_value = binomial_tail_probability(missed_requests, total_requests, Decimal(p0_permille) / Decimal(1000))
            passes_downtime = p_value >= Decimal("0.05")
            reward_gap = max(0, expected_reward - rewarded)
            classification = classify_row(
                has_performance_summary=has_performance_summary,
                signed=address in base_signed or bool(signed_models),
                total_requests=total_requests,
                reward_gap=reward_gap,
                exclusion_reason=exclusion.get("reason", ""),
                passes_downtime=passes_downtime,
                expected_weight=expected_weight,
            )
            row = {
                "node": node,
                "epoch": epoch,
                "address": address,
                "has_performance_summary": has_performance_summary,
                "signed_base": address in base_signed,
                "signed_models": ";".join(signed_models),
                "validation_models": ";".join(validation_models),
                "weight": weights["weight"],
                "confirmation_weight": confirmation_weight,
                "subgroup_voting_power": voting_power,
                "model_raw_weight": model_raw_weight.get(address, 0),
                "model_coefficient_weight": model_coefficient_weight.get(address, 0),
                "expected_weight": expected_weight,
                "expected_weight_reason": expected_weight_reason,
                "inference_count": inference_count,
                "missed_requests": missed_requests,
                "total_requests": total_requests,
                "miss_rate": format_decimal(miss_rate),
                "p_value": format_decimal(p_value),
                "passes_downtime_test": passes_downtime,
                "exclusion_reason": exclusion.get("reason", ""),
                "exclusion_block_height": exclusion.get("exclusion_block_height", ""),
                "earned_coins": safe_int(perf.get("earned_coins")),
                "rewarded_coins": rewarded,
                "burned_coins": safe_int(perf.get("burned_coins")),
                "claimed": perf.get("claimed", ""),
                "expected_reward_base_units": expected_reward,
                "reward_gap_base_units": reward_gap,
                "classification": classification,
            }
            rows.append(row)
            if classification == "settlement_anomaly":
                anomalies.append(row)
    return rows, anomalies


def write_report(
    out_dir: Path,
    run_id: str,
    nodes: list[str],
    epochs: list[int],
    latest_by_node: dict[str, int | None],
    manifest: list[FetchResult],
    node_consensus: list[dict[str, Any]],
    signature_coverage: list[dict[str, Any]],
    participant_rows: list[dict[str, Any]],
    anomaly_rows: list[dict[str, Any]],
) -> None:
    ok_count = sum(1 for result in manifest if result.status == "ok")
    error_count = len(manifest) - ok_count
    consensus_ok = sum(1 for row in node_consensus if row["consensus"])
    consensus_total = len(node_consensus)
    miss_by_epoch: dict[int, tuple[int, int]] = {}
    for epoch in epochs:
        rows = [row for row in participant_rows if int(row["epoch"]) == epoch]
        missed = sum(int(row["missed_requests"]) for row in rows)
        total = sum(int(row["total_requests"]) for row in rows)
        miss_by_epoch[epoch] = (missed, total)

    lines = [
        "# Shard Proof Audit",
        "",
        f"- Run id: `{run_id}`",
        f"- Nodes: {', '.join(f'`{node}`' for node in nodes)}",
        f"- Epochs: {', '.join(str(epoch) for epoch in epochs)}",
        f"- Latest by node: `{json.dumps(latest_by_node, sort_keys=True)}`",
        f"- Preserved files: {ok_count} ok, {error_count} error",
        f"- Consensus groups: {consensus_ok}/{consensus_total}",
        f"- Participant rows: {len(participant_rows)}",
        f"- Settlement anomalies: {len(anomaly_rows)}",
        "",
        "## Retention Note",
        "",
        "Raw snapshots were saved before analysis. Failed endpoints are recorded as `.error.json` files in the manifest so partial availability is explicit.",
        "",
        "## Miss Rate",
        "",
        "| epoch | missed | total | miss_rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for epoch, (missed, total) in miss_by_epoch.items():
        rate = Decimal(missed) / Decimal(total) if total else Decimal(0)
        lines.append(f"| {epoch} | {missed} | {total} | {format_decimal(rate)} |")

    lines.extend([
        "",
        "## Signature Coverage",
        "",
        "| node | epoch | model_id | signatures | nonempty | weights |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ])
    for row in signature_coverage[:30]:
        lines.append(
            f"| {row['node']} | {row['epoch']} | {row['model_id']} | {row['signature_count']} | "
            f"{row['nonempty_signature_count']} | {row['validation_weights_count']} |"
        )
    if len(signature_coverage) > 30:
        lines.append(f"| ... | ... | ... | ... | ... | ... |")

    lines.extend([
        "",
        "## Output Files",
        "",
        "- `manifest.json` / `manifest.csv`",
        "- `node_consensus.csv`",
        "- `signature_coverage.csv`",
        "- `participant_proof_table.csv`",
        "- `settlement_anomalies.csv`",
    ])
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_weights(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for item in items:
        address = item.get("member_address", "")
        if not address:
            continue
        weight = max(0, safe_int(item.get("weight")))
        confirmation_weight = max(0, safe_int(item.get("confirmation_weight")))
        result[address] = {"weight": weight, "confirmation_weight": min(weight, confirmation_weight)}
    return result


def parse_perf(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row.get("participant_id", ""): row for row in payload.get("epochPerformanceSummary", []) if row.get("participant_id")}


def parse_excluded(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
        address = item.get("address") or item.get("participant_id") or item.get("participant")
        if address:
            result[address] = item
    return result


def signed_addresses(group: dict[str, Any]) -> set[str]:
    return {
        item.get("member_address", "")
        for item in group.get("member_seed_signatures", []) or []
        if item.get("member_address") and item.get("signature")
    }


def select_expected_weight(
    full_weight: int,
    confirmation_weight: int,
    subgroup_voting_power: int,
    subgroup_confirmation_weight: int,
    exclusion_reason: str,
    coefficient_weight: int,
) -> tuple[int, str]:
    if full_weight > 0 and confirmation_weight > 0 and exclusion_reason == "failed_confirmation_poc":
        return full_weight, "failed_confirmation_poc_full_weight"
    if confirmation_weight == 0:
        return full_weight, "zero_confirmation_uses_full_weight"
    if coefficient_weight > 0 and full_weight > 0 and full_weight < coefficient_weight:
        scaled = Decimal(confirmation_weight) * Decimal(full_weight) / Decimal(coefficient_weight)
        return min(int(scaled.to_integral_value(rounding=ROUND_FLOOR)), full_weight), "chain_rescaled_confirmation_by_parent_weight"
    if subgroup_voting_power > 0:
        return min(confirmation_weight, subgroup_voting_power), "confirmation_capped_by_subgroup_voting_power"
    return confirmation_weight, "confirmation_weight"


def model_coefficients(params_payload: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for config in params_payload.get("params", {}).get("poc_params", {}).get("models", []) or []:
        model_id = config.get("model_id", "")
        if model_id:
            result[model_id] = legacy_decimal(config.get("weight_scale_factor")) or Decimal(1)
    return result


def coefficient_adjusted_weight(raw_weight: int, coefficient: Decimal) -> int:
    if raw_weight <= 0:
        return 0
    return int((Decimal(raw_weight) * coefficient).to_integral_value(rounding=ROUND_FLOOR))


def classify_row(
    *,
    has_performance_summary: bool,
    signed: bool,
    total_requests: int,
    reward_gap: int,
    exclusion_reason: str,
    passes_downtime: bool,
    expected_weight: int,
) -> str:
    if not has_performance_summary:
        return "missing_performance_summary"
    if reward_gap <= 0:
        return "no_reward_gap"
    if expected_weight <= 0:
        return "zero_expected_weight"
    if exclusion_reason:
        return f"explained_by_exclusion:{exclusion_reason}"
    if not passes_downtime:
        return "explained_by_downtime_test"
    if signed or total_requests > 0:
        return "settlement_anomaly"
    return "reward_gap_without_work_proof"


def compute_fixed_epoch_reward(params_payload: dict[str, Any], epoch: int) -> int:
    reward_params = params_payload.get("params", {}).get("bitcoin_reward_params", {})
    initial_reward = Decimal(str(reward_params.get("initial_epoch_reward", "0") or "0"))
    decay_fraction = legacy_decimal(reward_params.get("decay_rate"))
    genesis_epoch = safe_int(reward_params.get("genesis_epoch"), default=1)
    if initial_reward <= 0:
        return 0
    exponent = Decimal("0.9995251127946402") if decay_fraction == Decimal("-0.000475") else Decimal("1") + decay_fraction
    return int((initial_reward * (exponent ** max(epoch - genesis_epoch, 0))).to_integral_value(rounding=ROUND_FLOOR))


def floor_reward(weight: int, fixed_epoch_reward: int, total_weight: int) -> int:
    if weight <= 0 or fixed_epoch_reward <= 0 or total_weight <= 0:
        return 0
    return int((Decimal(weight) * Decimal(fixed_epoch_reward) / Decimal(total_weight)).to_integral_value(rounding=ROUND_FLOOR))


def binomial_tail_probability(k: int, n: int, p0: Decimal) -> Decimal:
    if n == 0:
        return Decimal(1)
    if k < 0 or k > n:
        return Decimal(0)
    if k == 0:
        return Decimal(1)
    q0 = Decimal(1) - p0
    if p0 <= 0:
        return Decimal(0)
    if q0 <= 0:
        return Decimal(1)
    probability = q0**n
    if k - 1 <= n - k:
        cdf = probability
        for i in range(0, k - 1):
            probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
            cdf += probability
        return max(Decimal(0), min(Decimal(1), Decimal(1) - cdf))
    for i in range(0, k):
        probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
    tail = probability
    for i in range(k, n):
        probability = probability * Decimal(n - i) * p0 / (Decimal(i + 1) * q0)
        tail += probability
    return max(Decimal(0), min(Decimal(1), tail))


def legacy_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    if isinstance(value, dict) and "value" in value and "exponent" in value:
        return Decimal(str(value["value"])) * (Decimal(10) ** int(value["exponent"]))
    return Decimal(str(value))


def decimal_to_permille(value: Any, default: int) -> int:
    decimal = legacy_decimal(value)
    if decimal <= 0:
        return default
    return int((decimal * Decimal(1000)).to_integral_value(rounding=ROUND_FLOOR))


def legacy_decimal_to_text(value: Any) -> str:
    return format_decimal(legacy_decimal(value)) if value is not None else ""


def endpoint_with_params(endpoint: str, params: dict[str, str]) -> str:
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{endpoint}?{query}" if query else endpoint


def load_json_if_ok(result: FetchResult) -> dict[str, Any]:
    if result.status != "ok":
        return {}
    return load_json(Path(result.path))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify_node(value: str) -> str:
    return value.replace("http://", "").replace("https://", "").replace(":", "_").replace("/", "_")


def slugify_model(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("_") or "model"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000000001"), rounding=ROUND_FLOOR), "f")


if __name__ == "__main__":
    raise SystemExit(main())
