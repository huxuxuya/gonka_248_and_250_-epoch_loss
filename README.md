# Gonka epoch 248 and 250 compensation package

After comprehensive analysis of the cached chain data and external compensation sources, this repository treats epochs `248` and `250` as epochs that must be compensated in full for participants that lost rewards.

The package is reproducible: raw chain snapshots are stored under `data/raw`, calculations are derived from those snapshots, and the GitHub Pages review table is generated from the same CSV/JSON outputs.

## Epoch reports

- [Epoch 248 compensation report](outputs/epoch_248/README.md)
- [Epoch 250 compensation report](outputs/epoch_250/README.md)
- [GitHub Pages review table](docs/index.html)

## Compensation scope

| epoch | rows with calculated loss | calculated loss GNK | already covered by sources GNK | payout from this package GNK | epoch report |
|---|---:|---:|---:|---:|---|
| 248 | 63 | 118204.036062177 | 118204.036062177 | 0.000000000 | [epoch 248](outputs/epoch_248/README.md) |
| 250 | 34 | 36889.261451234 | 36889.261451234 | 0.000000000 | [epoch 250](outputs/epoch_250/README.md) |

`payout from this package` is the remaining amount after subtracting non-zero compensation amounts that were already calculated by external sources. After adding the full epoch compensation sources, epochs `248` and `250` are fully covered and the remaining payout is `0.000000000`.

## Rule used for the package

For each participant and epoch:

```text
expected_reward = floor(expected_reward_weight * fixed_epoch_reward / total_epoch_weight)
calculated_loss = max(0, expected_reward - actual_rewarded_coins)
payout_here = max(0, calculated_loss + adjustment_layers - covered_by_sources)
```

Money is handled in base units with `Decimal` and floor rounding. `1 GNK = 1e9` base units.

For confirmation failures that zeroed effective weight, the expected reward is calculated from the original chain weight. For subgroup/model capped weights, the effective reward weight follows the reconstructed chain logic, including scaled subgroup voting power.

## External source handling

External source rows live in `docs/source_overrides.json` and are included in `docs/data/compensation_rows.json`.

If a source has already calculated a non-zero compensation for the same address and epoch, that amount is shown as `covered by sources GNK` in the epoch README. When the source amount fully covers our calculated amount within the source tolerance, `payout here GNK` is zero.

Current sources used by the review table include:

- `GRC-e247-preserver-audit`
- `GRC-e254-api-issue`
- `consensus_failure_restriction`
- `SegovChik-grc-case-1`
- `epoch-248-full-compensation`
- `epoch-250-full-compensation`

## Important files

- `outputs/epoch_248/README.md` - participant-level epoch 248 payout table.
- `outputs/epoch_250/README.md` - participant-level epoch 250 payout table.
- `outputs/combined/compensation_detailed.csv` - detailed calculated rows for all cached epochs.
- `docs/index.html` - GitHub Pages review table.
- `docs/data/compensation_rows.json` - generated browser data with source layers applied.

## Rebuild

```bash
python3 scripts/calculate_compensation.py --epochs 247 248 249 250 251 252 253 254 255 --cache-only
python3 scripts/build_reports.py
python3 scripts/import_source_full_epoch_compensation.py --epochs 248 250
python3 scripts/build_pages_data.py
python3 scripts/validate_consistency.py --epochs 247 248 249 250 251 252 253 254 255
```
