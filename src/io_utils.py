from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.constants import BASE_UNITS_PER_GNK
from src.models import EpochMetadata, RawFileRecord, Settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_settings(path: Path) -> Settings:
    data = load_yaml(path)
    return Settings(**data)


def dump_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    serializable = _normalize(payload)
    path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_jsonl(path: Path, rows: Iterable[Any]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_normalize(row), ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
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


def build_file_record(path: Path) -> RawFileRecord:
    return RawFileRecord(
        path=str(path),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def load_cache_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"epochs": {}}
    return load_json(path)


def update_cache_index(path: Path, metadata: EpochMetadata) -> None:
    payload = load_cache_index(path)
    payload.setdefault("epochs", {})[str(metadata.epoch)] = metadata.to_dict()
    dump_json(path, payload)


def format_gnk(base_units: int | Decimal, precision: int) -> str:
    value = Decimal(base_units) / Decimal(BASE_UNITS_PER_GNK)
    quantum = Decimal("1").scaleb(-precision)
    return format(value.quantize(quantum, rounding=ROUND_DOWN), "f")


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    return value
