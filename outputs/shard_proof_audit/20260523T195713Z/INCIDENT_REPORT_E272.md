# Epoch 272 Shard Proof Incident Review

## Short Conclusion

The audit data supports Gleb Morgachev's chat assessment: the listed participants did have high miss rate on-chain in epoch `272`. They were not "absent" from the epoch: they had validation weights, signatures, model participation, and non-zero completed inference work. However, their `rewarded_coins` were zero because their miss statistics failed the downtime/binomial test.

This is not enough to prove a chain bug. The missing piece is shard-level proof from the affected nodes: `/v1/devshard/stats/shards` and `/v1/devshard/stats/shards/<DEVSHARD_ID>` for epoch `272`, while retained data is still available.

## What The Audit Does

`scripts/audit_shard_proofs.py` preserves and analyzes these chain/API endpoints for recent epochs:

- `params`
- `epoch_group_data`
- per-model `epoch_group_data`
- `epoch_performance_summary`
- `excluded_participants`
- `confirmation_poc_events`

For each preserved payload it stores raw JSON, SHA-256 hashes, fetch status, and a manifest. It then builds:

- `node_consensus.csv`: whether node responses match by hash.
- `signature_coverage.csv`: whether validation weights have matching member seed signatures.
- `participant_proof_table.csv`: per-address weights, signatures, miss stats, rewards, exclusions, and classification.
- `settlement_anomalies.csv`: heuristic reward-gap rows.

Important limitation: `settlement_anomaly` is an audit heuristic, not a final chain verdict. The script reconstructs expected rewards approximately and does not preserve historical devshard slot-level stats.

## Data Quality

Run: `20260523T195713Z`

- Epochs checked: `269`, `270`, `271`, `272`.
- Node1 and node2 agree on epoch group data, per-model groups, excluded participants, and confirmation PoC events for epoch `272`.
- Node3 was unavailable: connection refused.
- Node2 returned `500` for `epoch_performance_summary`, so reward/miss conclusions rely on node1's performance summary.
- Signature coverage for epoch `272` is complete:
  - base group: `50/50`
  - Qwen model group: `35/35`
  - Kimi model group: `23/23`

## Addresses From Chat

All six addresses from the chat are present in epoch `272`, have signatures/model participation, and have `rewarded_coins=0`.

| address | models | inference | missed | miss_rate | p_value | audit classification |
|---|---|---:|---:|---:|---:|---|
| `gonka1wt8sr9jxzpec65j7zkxsgh6edk3m6r8nlf5za4` | Kimi | 309 | 90 | 22.56% | 0.000000000 | downtime test failed |
| `gonka10079cnl3nuh2k82mhkm04dj0slhtw9kmjewwau` | Qwen, Kimi | 308 | 59 | 16.08% | 0.000195951 | downtime test failed |
| `gonka1007g0ut3u4wjkay9hegqfev4pj90qgexwskmcw` | Kimi | 416 | 72 | 14.75% | 0.000585697 | downtime test failed |
| `gonka1007dchuqgdnute4qam70kmn56j2vfw38mhyrqv` | Kimi | 406 | 60 | 12.88% | 0.026292990 | downtime test failed |
| `gonka15munkmx6x7k6rqqeexjet4556p7at39ks9qgr5` | Kimi | 185 | 50 | 21.28% | 0.000000241 | downtime test failed |
| `gonka1ce02jjduga8jvwj8jx39mxn0jr345vgkx7lk2n` | Kimi | 63 | 35 | 35.71% | 0.000000000 | downtime test failed |

Epoch `272` aggregate from the audit: `855` missed out of `21260` total requests, miss rate `4.02%`.

## What Likely Happened

The observed pattern matches this chain-level flow:

1. Participants were included in validation/model groups and signed shard/epoch data.
2. They completed some inference work, so this was not a simple "node offline for whole epoch" case.
3. Their miss rates crossed the statistical downtime threshold.
4. Chain/API performance summary recorded `rewarded_coins=0`.

This aligns with Gleb's chat comments:

- "Вроде у всех miss rate высокий из списка, по данным на чейне."
- "Было зассетлено очень мало шардов при этом."
- Need to inspect retained devshard proof data from each node.

## Other Epochs Check

Within the shard audit window `269-272`, the same mass pattern appears only in epoch `272`.

| epoch | participants | zero reward | zero due downtime | aggregate miss rate |
|---:|---:|---:|---:|---:|
| 269 | 58 | 12 | 1 | 1.81% |
| 270 | 49 | 5 | 0 | 0.26% |
| 271 | 49 | 7 | 0 | 2.24% |
| 272 | 50 | 14 | 7 | 4.02% |

For the six chat addresses specifically, prior shard-audit epochs do not show the same zero-reward downtime outcome. Five of them had rewards in their earlier observed epochs; `gonka1ce02jjduga8jvwj8jx39mxn0jr345vgkx7lk2n` only appears in this audit in epoch `272`.

Older cached epochs `247-255` do contain other participants with the same general symptom: non-zero or attempted work, high missed request rate, and zero reward after the downtime/binomial test. Those are not the same incident unless shard-level data links them.

| epoch | zero due downtime, raw performance check |
|---:|---:|
| 247 | 17 |
| 248 | 19 |
| 249 | 12 |
| 250 | 3 |
| 251 | 2 |
| 252 | 2 |
| 253 | 1 |
| 254 | 0 |
| 255 | 2 |

So the short answer is: yes, this mechanism existed in other epochs, but the epoch `272` case is unusual inside the shard-audit window because several Kimi-heavy participants from the same chat list fail the downtime test together.

## Hypotheses To Check

1. Affected node/API issue: public API, nginx, binary version, or `*-post2` vs `*-post3` mismatch caused the node to miss shard requests while appearing operational to the operator.
2. Late shard settlement visibility: because shards were settled near epoch end, dashboards did not show the bad miss rate early enough to react.
3. Bad or unrepresentative shard set: a small number of settled shards may have produced disproportionate misses for these participants.
4. Operator monitoring gap: trackers did not expose real-time devshard miss stats, so operators could not detect the issue from ordinary monitoring.

## Next Data To Collect

From each affected node, collect and preserve:

```bash
curl "<PUBLIC_URL>/v1/devshard/stats/shards" | jq
curl "<PUBLIC_URL>/v1/devshard/stats/shards/<DEVSHARD_ID>" | jq
```

For a useful case review, the devshard dump must show per-slot stats, shard IDs, escrow IDs, success/miss counts, and participant addresses. These data should be compared against `participant_proof_table.csv` and `epoch_performance_summary/272`.

## Practical Position

Current evidence justifies investigation and shard-level proof collection. It does not yet justify saying the chain calculated rewards incorrectly. If shard-level proofs show the nodes processed work correctly but misses were assigned because of settlement/shard accounting behavior, then this becomes a compensation/review candidate. If shard-level proofs confirm the misses, the zero reward outcome is consistent with the current chain data.
