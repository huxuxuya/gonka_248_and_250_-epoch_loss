from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class Settings:
    node_url: str
    epochs: list[int]
    timeout_sec: int
    retries: int
    use_live_chain: bool
    strict_validation: bool
    output_precision_gnk: int
    package_policy: dict[str, Any]


@dataclass
class RawFileRecord:
    path: str
    sha256: str
    size_bytes: int


@dataclass
class EpochMetadata:
    epoch: int
    fetched_at_utc: str
    node_url: str
    mode: str
    endpoints: list[dict[str, Any]]
    files: dict[str, RawFileRecord]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["files"] = {
            key: asdict(value) for key, value in self.files.items()
        }
        return payload


@dataclass
class RewardComputation:
    address: str
    epoch: int
    exclusion_reason: str
    weight: int
    confirmation_weight: int
    effective_weight: int
    fixed_epoch_reward: int
    total_epoch_weight: int
    reward_rate_base_units_per_weight: Decimal
    actual_rewarded_coins: int
    expected_reward_base_units: int
    compensation_base_units: int
    expected_reward_gnk: str
    actual_reward_gnk: str
    compensation_gnk: str
    notes: str


@dataclass
class EpochComputationResult:
    epoch: int
    rows: list[RewardComputation]
    approximation_used: bool
    applied_steps: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    fixed_epoch_reward: int = 0
    total_epoch_weight: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "approximation_used": self.approximation_used,
            "applied_steps": self.applied_steps,
            "limitations": self.limitations,
            "fixed_epoch_reward": str(self.fixed_epoch_reward),
            "total_epoch_weight": str(self.total_epoch_weight),
            "rows": [asdict(row) for row in self.rows],
        }
