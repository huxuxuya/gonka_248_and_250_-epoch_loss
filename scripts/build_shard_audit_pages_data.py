#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build browser data for shard proof audit dashboard.")
    parser.add_argument("--audit-dir", help="Audit package directory. Defaults to latest outputs/shard_proof_audit/*")
    parser.add_argument("--target", default="docs/audit_data.js")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit_dir = Path(args.audit_dir) if args.audit_dir else latest_audit_dir(Path("outputs/shard_proof_audit"))
    manifest = load_json(audit_dir / "manifest.json")
    participant_rows = read_csv(audit_dir / "participant_proof_table.csv")
    anomalies = read_csv(audit_dir / "settlement_anomalies.csv")
    consensus = read_csv(audit_dir / "node_consensus.csv")
    signatures = read_csv(audit_dir / "signature_coverage.csv")

    data = {
        "run_id": manifest.get("run_id", audit_dir.name),
        "audit_dir": str(audit_dir),
        "nodes": manifest.get("nodes", []),
        "epochs": manifest.get("epochs", []),
        "latest_by_node": manifest.get("latest_by_node", {}),
        "preserved": {
            "files": len(manifest.get("files", [])),
            "ok": sum(1 for item in manifest.get("files", []) if item.get("status") == "ok"),
            "errors": sum(1 for item in manifest.get("files", []) if item.get("status") == "error"),
        },
        "summary": build_summary(participant_rows, anomalies, consensus, signatures),
        "consensus": consensus,
        "signatures": signatures,
        "anomalies": anomalies,
        "participant_rows": participant_rows,
        "errors": [
            {
                "node": item.get("node", ""),
                "epoch": item.get("epoch", ""),
                "label": item.get("label", ""),
                "model_id": item.get("model_id", ""),
                "error": item.get("error", ""),
            }
            for item in manifest.get("files", [])
            if item.get("status") == "error"
        ],
    }

    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "window.__GONKA_SHARD_AUDIT_DATA__ = "
        + json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {target} from {audit_dir}")
    return 0


def latest_audit_dir(root: Path) -> Path:
    candidates = sorted(path for path in root.iterdir() if path.is_dir())
    if not candidates:
        raise SystemExit(f"no audit package directories under {root}")
    return candidates[-1]


def build_summary(
    participant_rows: list[dict[str, str]],
    anomalies: list[dict[str, str]],
    consensus: list[dict[str, str]],
    signatures: list[dict[str, str]],
) -> dict[str, Any]:
    classification_counts = Counter(row.get("classification", "") for row in participant_rows)
    node_counts = Counter(row.get("node", "") for row in participant_rows)
    miss_by_epoch: dict[str, dict[str, int]] = defaultdict(lambda: {"missed": 0, "total": 0})
    for row in participant_rows:
        if row.get("has_performance_summary") != "True":
            continue
        epoch = row.get("epoch", "")
        miss_by_epoch[epoch]["missed"] += parse_int(row.get("missed_requests"))
        miss_by_epoch[epoch]["total"] += parse_int(row.get("total_requests"))

    signature_totals = {
        "groups": len(signatures),
        "signatures": sum(parse_int(row.get("signature_count")) for row in signatures),
        "nonempty": sum(parse_int(row.get("nonempty_signature_count")) for row in signatures),
        "weights": sum(parse_int(row.get("validation_weights_count")) for row in signatures),
    }
    return {
        "participant_rows": len(participant_rows),
        "anomalies": len(anomalies),
        "classification_counts": dict(sorted(classification_counts.items())),
        "node_counts": dict(sorted(node_counts.items())),
        "consensus_ok": sum(1 for row in consensus if row.get("consensus") == "True"),
        "consensus_total": len(consensus),
        "signature_totals": signature_totals,
        "miss_by_epoch": {
            epoch: {
                "missed": item["missed"],
                "total": item["total"],
                "miss_rate": item["missed"] / item["total"] if item["total"] else 0,
            }
            for epoch, item in sorted(miss_by_epoch.items(), key=lambda pair: int(pair[0] or 0))
        },
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_int(value: Any) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
