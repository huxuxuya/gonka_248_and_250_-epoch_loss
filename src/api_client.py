from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.io_utils import dump_json, dump_jsonl, load_json
from src.models import Settings


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.node_url.rstrip("/")

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{self.base_url}{endpoint}"
        if query:
            url = f"{url}?{query}"

        last_error: Exception | None = None
        max_attempts = max(self.settings.retries, 5)
        for attempt in range(1, max_attempts + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": "gonka-comp-tool/1.0"},
                )
                with urllib.request.urlopen(request, timeout=self.settings.timeout_sec) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if exc.code == 429 and attempt < max_attempts:
                    sleep_for = int(retry_after) if retry_after and retry_after.isdigit() else min(5 * attempt, 30)
                    time.sleep(sleep_for)
                    continue
                if attempt == max_attempts:
                    raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
                time.sleep(min(attempt, 3))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == max_attempts:
                    raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
                time.sleep(min(attempt, 3))

        raise RuntimeError(f"Failed to fetch {url}: {last_error}")

    def fetch_optional_json(self, endpoint: str) -> tuple[bool, Any]:
        try:
            return True, self.get_json(endpoint)
        except RuntimeError:
            return False, None


def fetch_paginated_endpoint(
    client: ApiClient,
    endpoint: str,
    response_key_hint: str | None = None,
    allow_partial: bool = False,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    aggregated_items: list[Any] = []
    next_key = ""
    page = 0

    while True:
        page += 1
        params = {"pagination.limit": "250"}
        if next_key:
            params["pagination.key"] = next_key
        try:
            payload = client.get_json(endpoint, params=params)
        except RuntimeError as exc:
            if not allow_partial:
                raise
            return {
                "endpoint": endpoint,
                "pages": pages,
                "page_count": page - 1,
                "item_count": len(aggregated_items),
                "items": aggregated_items,
                "complete": False,
                "error": str(exc),
            }
        pages.append(payload)

        items = _extract_items(payload, response_key_hint)
        aggregated_items.extend(items)

        pagination = payload.get("pagination") or {}
        next_key = (
            pagination.get("next_key")
            or pagination.get("nextKey")
            or pagination.get("next")
            or ""
        )
        if not next_key:
            break
        time.sleep(12)

    return {
        "endpoint": endpoint,
        "pages": pages,
        "page_count": page,
        "item_count": len(aggregated_items),
        "items": aggregated_items,
        "complete": True,
    }


def save_json_payload(path: Path, payload: Any) -> None:
    dump_json(path, payload)


def save_jsonl_payload(path: Path, rows: list[Any]) -> None:
    dump_jsonl(path, rows)


def load_cached_json(path: Path) -> Any:
    return load_json(path)


def _extract_items(payload: dict[str, Any], response_key_hint: str | None) -> list[Any]:
    if response_key_hint and isinstance(payload.get(response_key_hint), list):
        return payload[response_key_hint]

    for key in ("epoch_group_data", "participant", "participants", "items", "events"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []
