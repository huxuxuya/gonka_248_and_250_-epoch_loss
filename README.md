# Gonka epoch 248 and 250 compensation package

After comprehensive analysis of cached chain data and external compensation sources, this repository treats epochs `248` and `250` as epochs that must be compensated in full for participants that lost rewards.

The package is reproducible: raw chain snapshots are stored under `data/raw`, calculations are derived from those snapshots, and the GitHub Pages review table is generated from the same CSV/JSON outputs.

## Where to see payouts

- [Epoch 248 payout list](outputs/epoch_248/README.md) - participant table with the amount to pay for epoch 248.
- [Epoch 250 payout list](outputs/epoch_250/README.md) - participant table with the amount to pay for epoch 250.
- [GRC-e247 preserver audit remaining compensation](outputs/grc_e247_preserver_audit_remaining/README.md) - supplemental rows where the GRC-e247 audit source exists but `FINAL REWARD DELTA` is still non-zero.
- [GitHub Pages review table](docs/index.html) - interactive view with source toggles and detailed per-cell cards.

The epoch README files are payout documents and source-of-truth inputs for the package source layers. They are imported into the review table as `epoch-248-compensation-package` and `epoch-250-compensation-package`, but they are not subtracted from themselves when these README payout totals are built.

## Compensation scope

| epoch | rows with calculated loss | calculated base GNK | bug adjustment GNK | already covered by external sources GNK | payout to make GNK | epoch report |
|---|---:|---:|---:|---:|---:|---|
| 248 | 63 | 118204.036062177 | 0.000000000 | 0.000000000 | 118204.036062177 | [epoch 248](outputs/epoch_248/README.md) |
| 250 | 34 | 30160.582484914 | 6728.678966320 | 25469.854153328 | 11419.407297906 | [epoch 250](outputs/epoch_250/README.md) |

## Rule used for the package

```text
expected_reward = floor(expected_reward_weight * fixed_epoch_reward / total_epoch_weight)
calculated_loss = max(0, expected_reward - actual_rewarded_coins)
payout_to_make = max(0, calculated_loss + adjustment_layers - covered_by_external_sources)
```

Money is handled in base units with `Decimal` and floor rounding. `1 GNK = 1e9` base units.

For confirmation failures that zeroed effective weight, the expected reward is calculated from the original chain weight. For subgroup/model capped weights, the effective reward weight follows the reconstructed chain logic, including scaled subgroup voting power.

## Source Handling

External source rows live in `docs/source_overrides.json` and are included in `docs/data/compensation_rows.json`. If an independent source has already calculated a non-zero compensation for the same address and epoch, that amount is shown as `already covered by external sources GNK` and subtracted from `payout to make GNK`.

Package payout sources are generated from the epoch README payout lists after independent external sources are subtracted. They let the GitHub Pages table show the final package compensation as a source layer without changing the README payout totals.

The GRC-e247 remaining-delta package is also imported as `grc-e247-preserver-audit-remaining`. It closes the residual `FINAL REWARD DELTA` for rows that already had `GRC-e247-preserver-audit` but were not fully covered by that original source.

Current sources used by the review table include:

- `GRC-e247-preserver-audit`
- `GRC-e254-api-issue`
- `SegovChik-grc-case-1`
- `consensus_failure_restriction`
- `epoch-248-compensation-package`
- `epoch-250-compensation-package`

## Important Files

- `outputs/epoch_248/README.md` - participant-level epoch 248 payout table and package source of truth.
- `outputs/epoch_250/README.md` - participant-level epoch 250 payout table and package source of truth.
- `outputs/grc_e247_preserver_audit_remaining/README.md` - supplemental remaining-delta payout table for GRC-e247 preserver audit rows.
- `outputs/combined/compensation_detailed.csv` - detailed calculated rows for all cached epochs.
- `docs/index.html` - GitHub Pages review table.
- `docs/source_overrides.json` - imported independent source rows plus package payout source rows.
- `docs/data/compensation_rows.json` - generated browser data with source layers applied.

## Rebuild

```bash
python3 scripts/calculate_compensation.py --epochs 247 248 249 250 251 252 253 254 255 --cache-only
python3 scripts/build_reports.py
python3 scripts/build_compensation_readmes.py --epochs 248 250
python3 scripts/import_source_epoch_compensation_package.py --epochs 248 250
python3 scripts/build_pages_data.py
python3 scripts/build_grc_e247_remaining_package.py
python3 scripts/import_source_grc_e247_remaining_package.py
python3 scripts/build_pages_data.py
python3 scripts/validate_consistency.py --epochs 247 248 249 250 251 252 253 254 255
```
