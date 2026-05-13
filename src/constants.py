from __future__ import annotations

from pathlib import Path

BASE_UNITS_PER_GNK = 10**9
DECIMAL_GNK_SCALE = "0.000000001"
DEFAULT_SETTINGS_PATH = Path("config/settings.yaml")
RAW_DATA_DIR = Path("data/raw")
PROCESSED_DATA_DIR = Path("data/processed")
OUTPUTS_DIR = Path("outputs")
CACHE_INDEX_PATH = Path("data/cache_index.json")

REQUIRED_RAW_FILES = (
    "params.json",
    "epoch_group_data_full.json",
    "metadata.json",
)

OPTIONAL_RAW_FILES = (
    "confirmation_poc_events_{epoch}.json",
    "participant_snapshot_pages.jsonl",
)
