# Shard Proof Audit

- Run id: `20260523T210210Z`
- Nodes: `http://node1.gonka.ai:8000`, `http://node2.gonka.ai:8000`, `http://node3.gonka.ai:8000`
- Epochs: 269, 270, 271, 272
- Latest by node: `{"http://node1.gonka.ai:8000": 273, "http://node2.gonka.ai:8000": 273, "http://node3.gonka.ai:8000": null}`
- Preserved files: 46 ok, 21 error
- Consensus groups: 20/24
- Participant rows: 412
- Settlement anomalies: 0

## Retention Note

Raw snapshots were saved before analysis. Failed endpoints are recorded as `.error.json` files in the manifest so partial availability is explicit.

## Miss Rate

| epoch | missed | total | miss_rate |
| --- | ---: | ---: | ---: |
| 269 | 1334 | 73772 | 0.018082741 |
| 270 | 863 | 328317 | 0.002628557 |
| 271 | 2822 | 126228 | 0.022356371 |
| 272 | 855 | 21260 | 0.040216368 |

## Signature Coverage

| node | epoch | model_id | signatures | nonempty | weights |
| --- | ---: | --- | ---: | ---: | ---: |
| http://node1.gonka.ai:8000 | 269 |  | 58 | 58 | 58 |
| http://node1.gonka.ai:8000 | 269 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 36 | 36 | 36 |
| http://node1.gonka.ai:8000 | 269 | moonshotai/Kimi-K2.6 | 30 | 30 | 30 |
| http://node1.gonka.ai:8000 | 270 |  | 49 | 49 | 49 |
| http://node1.gonka.ai:8000 | 270 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 32 | 32 | 32 |
| http://node1.gonka.ai:8000 | 270 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |
| http://node1.gonka.ai:8000 | 271 |  | 49 | 49 | 49 |
| http://node1.gonka.ai:8000 | 271 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 34 | 34 | 34 |
| http://node1.gonka.ai:8000 | 271 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |
| http://node1.gonka.ai:8000 | 272 |  | 50 | 50 | 50 |
| http://node1.gonka.ai:8000 | 272 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 35 | 35 | 35 |
| http://node1.gonka.ai:8000 | 272 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |
| http://node2.gonka.ai:8000 | 269 |  | 58 | 58 | 58 |
| http://node2.gonka.ai:8000 | 269 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 36 | 36 | 36 |
| http://node2.gonka.ai:8000 | 269 | moonshotai/Kimi-K2.6 | 30 | 30 | 30 |
| http://node2.gonka.ai:8000 | 270 |  | 49 | 49 | 49 |
| http://node2.gonka.ai:8000 | 270 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 32 | 32 | 32 |
| http://node2.gonka.ai:8000 | 270 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |
| http://node2.gonka.ai:8000 | 271 |  | 49 | 49 | 49 |
| http://node2.gonka.ai:8000 | 271 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 34 | 34 | 34 |
| http://node2.gonka.ai:8000 | 271 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |
| http://node2.gonka.ai:8000 | 272 |  | 50 | 50 | 50 |
| http://node2.gonka.ai:8000 | 272 | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | 35 | 35 | 35 |
| http://node2.gonka.ai:8000 | 272 | moonshotai/Kimi-K2.6 | 23 | 23 | 23 |

## Output Files

- `manifest.json` / `manifest.csv`
- `node_consensus.csv`
- `signature_coverage.csv`
- `participant_proof_table.csv`
- `settlement_anomalies.csv`
