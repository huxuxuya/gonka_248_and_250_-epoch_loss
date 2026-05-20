# GRC-e247 preserver audit remaining compensation

This folder contains a supplemental payout list for participants that already have a `GRC-e247-preserver-audit` compensation source, but still have a non-zero `FINAL REWARD DELTA` after all currently imported sources are applied.

The goal is not to replace the original audit. This report pays only the remaining delta that is still visible in the repository calculation.

Source document: [GRC-e247-preserver-audit](https://github.com/gonkalabs/GRC-e247-preserver-audit/blob/1b8a26704dcddea0de2f55cabf48fee3d9b100d4/RESTITUTION_REPORT.md)

## Summary

| metric | value |
|---|---:|
| rows with remaining delta | 14 |
| GRC-e247 source amount on these rows GNK | 7313.407760197 |
| payout to make GNK | 24597.786583224 |

## By Epoch

| epoch | rows | payout to make GNK |
|---:|---:|---:|
| 249 | 10 | 22620.322396344 |
| 251 | 3 | 1781.643070812 |
| 252 | 1 | 195.821116068 |

## Reproduce This Report

Run from the repository root:

```bash
python3 scripts/build_pages_data.py
python3 scripts/build_grc_e247_remaining_package.py
```

The script reads `docs/data/compensation_rows.json`, filters rows where:

```text
source == GRC-e247-preserver-audit
reward_delta_after_sources_base_units > 0
```

and writes:

```text
outputs/grc_e247_preserver_audit_remaining/compensation_grc_e247_remaining.csv
outputs/grc_e247_preserver_audit_remaining/README.md
```

## Participant Payouts

| epoch | address | loss reason | weight | expected GNK | actual GNK | calculated compensation GNK | GRC-e247 source GNK | all sources GNK | payout to make GNK |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 249 | `gonka1umvyh0rz5fdmk9qhxurshhchennajced6f4s89` | failed_confirmation_poc | 49939 | 19372.942551045 | 0.000000000 | 19853.590457906 | 480.647906861 | 480.647906861 | 19372.942551045 |
| 249 | `gonka1r5hdy9q5v783ef7td98k4c68cxl6a58h5sytfq` | failed_confirmation_poc | 2299 | 891.855962771 | 0.000000000 | 2482.377688462 | 1590.521725691 | 1590.521725691 | 891.855962771 |
| 249 | `gonka1dpt9zx2dqcky6yjjwrd8xz2w7lq6vffy9mhvgs` | failed_confirmation_poc | 915 | 354.957897318 | 0.000000000 | 988.838994825 | 633.881097507 | 633.881097507 | 354.957897318 |
| 249 | `gonka1lswsj2x7u4606wqpunmm07skgf76r3dyz4v0d8` | failed_confirmation_poc | 908 | 352.242372421 | 0.000000000 | 981.080352261 | 628.837979840 | 628.837979840 | 352.242372421 |
| 249 | `gonka1ge9amk4ymld27d35akj3ky9uph4gyz6rdpepjj` | failed_confirmation_poc | 881 | 341.768204959 | 0.000000000 | 951.209578388 | 609.441373429 | 609.441373429 | 341.768204959 |
| 249 | `gonka1llgg3kvg9sc6xz09jtkcrucrppxgn78xe4xlv0` | failed_confirmation_poc | 859 | 333.233698138 | 0.000000000 | 927.545718566 | 594.312020429 | 594.312020429 | 333.233698137 |
| 249 | `gonka145666cll76ptcyy9ceymtalr8gnvv73ne99p32` | failed_confirmation_poc | 839 | 325.475055574 | 0.000000000 | 906.597383643 | 581.122328070 | 581.122328070 | 325.475055573 |
| 249 | `gonka1043d00lu0v3fz53cut34twtcanalqg9u8vehp2` | failed_confirmation_poc | 735 | 285.130114239 | 0.000000000 | 793.709134331 | 508.579020093 | 508.579020093 | 285.130114238 |
| 249 | `gonka16q0zaetd6hq6d8zj48ur0v967xrrwh566kcazc` | failed_confirmation_poc | 557 | 216.078195417 | 0.000000000 | 602.458595121 | 386.380399704 | 386.380399704 | 216.078195417 |
| 249 | `gonka1p60lruhxmwcsa9taa28cp4k4f6kv2kvyu5h5ep` | failed_confirmation_poc | 378 | 146.638344466 | 0.000000000 | 408.492531012 | 261.854186547 | 261.854186547 | 146.638344465 |
| 251 | `gonka1d694r00czmq75txghwjcuk07lxvc8d4ekgsha0` | failed_confirmation_poc | 3570 | 1443.264299005 | 0.000000000 | 1561.312807495 | 118.048508760 | 118.048508760 | 1443.264298735 |
| 251 | `gonka1u9a7r4w76gult5n9ysadnual9fghkc6yda60wj` | failed_confirmation_poc | 542 | 219.117436991 | 0.000000000 | 610.860603863 | 391.743167000 | 391.743167000 | 219.117436863 |
| 251 | `gonka168rtjfkszuhcggg4dfyse4yh7xn9zwfglnkns2` | missed_requests | 1073 | 119.261335632 | 0.000000000 | 235.692741266 | 116.431406052 | 116.431406052 | 119.261335214 |
| 252 | `gonka1u9a7r4w76gult5n9ysadnual9fghkc6yda60wj` | failed_confirmation_poc | 461 | 195.821115836 | 0.000000000 | 607.427756282 | 411.606640214 | 411.606640214 | 195.821116068 |
