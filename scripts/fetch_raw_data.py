#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api_client import ApiClient, fetch_paginated_endpoint, save_json_payload, save_jsonl_payload
from src.constants import CACHE_INDEX_PATH, DEFAULT_SETTINGS_PATH, RAW_DATA_DIR
from src.io_utils import build_file_record, dump_json, load_settings, update_cache_index, utc_now_iso
from src.models import EpochMetadata


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("_") or "model"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Gonka raw data for compensation calculations.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH))
    parser.add_argument("--epochs", nargs="+", type=int, help="Epochs to fetch")
    parser.add_argument(
        "--include-participant-snapshots",
        action="store_true",
        help="Also fetch paginated participant snapshot pages for diagnostics",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(Path(args.settings))
    epochs = args.epochs or settings.epochs

    if not settings.use_live_chain:
        print("use_live_chain=false; fetch_raw_data.py will not make network calls")
        return 0

    client = ApiClient(settings)
    params_payload = client.get_json("/chain-api/productscience/inference/inference/params")
    full_group_payload = fetch_paginated_endpoint(
        client,
        "/chain-api/productscience/inference/inference/epoch_group_data",
        response_key_hint="epoch_group_data",
        allow_partial=True,
    )

    participant_snapshot_rows = []
    if args.include_participant_snapshots:
        participant_snapshot_rows = fetch_paginated_endpoint(
            client,
            "/chain-api/productscience/inference/inference/participant",
            response_key_hint="participant",
        )["pages"]

    fetched_at = utc_now_iso()
    for epoch in epochs:
        epoch_dir = RAW_DATA_DIR / f"epoch_{epoch}"
        epoch_dir.mkdir(parents=True, exist_ok=True)

        file_records = {}
        endpoints = []

        raw_files = {
            "params.json": params_payload,
            "epoch_group_data_full.json": full_group_payload,
            f"epoch_group_data_{epoch}.json": client.get_json(
                f"/chain-api/productscience/inference/inference/epoch_group_data/{epoch}"
            ),
            f"epoch_performance_summary_{epoch}.json": client.get_json(
                f"/chain-api/productscience/inference/inference/epoch_performance_summary/{epoch}"
            ),
            f"excluded_participants_{epoch}.json": client.get_json(
                f"/chain-api/productscience/inference/inference/excluded_participants/{epoch}"
            ),
        }

        subgroup_models = (
            raw_files[f"epoch_group_data_{epoch}.json"]
            .get("epoch_group_data", {})
            .get("sub_group_models", [])
        )
        for model_id in subgroup_models:
            subgroup_payload = client.get_json(
                f"/chain-api/productscience/inference/inference/epoch_group_data/{epoch}",
                params={"model_id": model_id},
            )
            subgroup_filename = f"epoch_group_data_{epoch}__{slugify(model_id)}.json"
            raw_files[subgroup_filename] = subgroup_payload

        confirmation_ok, confirmation_payload = client.fetch_optional_json(
            f"/chain-api/productscience/inference/inference/confirmation_poc_events/{epoch}"
        )
        if confirmation_ok:
            raw_files[f"confirmation_poc_events_{epoch}.json"] = confirmation_payload

        for filename, payload in raw_files.items():
            path = epoch_dir / filename
            save_json_payload(path, payload)
            file_records[filename] = build_file_record(path)
            endpoints.append({"file": filename, "status": "ok"})

        if participant_snapshot_rows:
            snapshot_path = epoch_dir / "participant_snapshot_pages.jsonl"
            save_jsonl_payload(snapshot_path, participant_snapshot_rows)
            file_records[snapshot_path.name] = build_file_record(snapshot_path)
            endpoints.append({"file": snapshot_path.name, "status": "ok"})

        metadata = EpochMetadata(
            epoch=epoch,
            fetched_at_utc=fetched_at,
            node_url=settings.node_url,
            mode="live",
            endpoints=endpoints,
            files=file_records,
        )
        metadata_path = epoch_dir / "metadata.json"
        dump_json(metadata_path, metadata.to_dict())
        update_cache_index(CACHE_INDEX_PATH, metadata)
        print(f"Fetched raw data for epoch {epoch} into {epoch_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
