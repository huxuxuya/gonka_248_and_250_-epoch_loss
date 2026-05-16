# Gonka reward compensation for epochs 247-255

Этот репозиторий считает недополученную награду за epochs `247-255`.
Разница между ожидаемой и фактически выданной наградой фиксируется как сумма, которая не дошла до участника и была отправлена в `gov` module.

## Что считается

Текущий replay разделяет две величины:

- `effective_weight = min(confirmation_weight, subgroup_voting_power)`
- `actual chain reward = floor(effective_weight * fixed_epoch_reward / total_full_weight)`
- `expected_reward_base_units = floor(expected_reward_weight * fixed_epoch_reward / total_full_weight)`
- `compensation_base_units = max(0, expected_reward_base_units - actual_rewarded_coins)`

Если `confirmation_weight = 0`, то `expected_reward_weight` берется как исходный `weight`. Иначе используется `pre_exclusion_effective_weight`.
То есть компенсация считается по той выплате, которую chain посчитал бы участнику при том же confirmed weight, если бы вес не был занулен exclusion/downtime.
`weight` и `effective_weight` остаются в CSV как диагностика: `weight` показывает полный denominator-вклад, `effective_weight` показывает фактический payout weight после занулений.

`1 GNK = 1e9` base units.

## Где лежат данные

- Raw cache: `data/raw/epoch_<N>`
- Processed cache: `data/processed`
- Final CSV: `outputs/epoch_<N>`, `outputs/combined`
- Полный markdown-отчет с таблицами по участникам: `outputs/combined/REPORT.md`

## On-chain updates around epochs

| epoch | epoch block range | applied height | update | proposal |
| --- | ---: | ---: | --- | --- |
| 248 | `3828323-3844113` | `3834200` | Software upgrade `v0.2.12` | `#44`, `Upgrade Proposal: v0.2.12` |
| 250 | `3859105-3874895` | - | No passed proposal update applied inside this epoch range | - |

Notes:

- Proposal `#44` passed at height `3830442` and scheduled `v0.2.12` for height `3834200`, which is inside epoch `248`.
- Proposal `#45` ended near epoch `250` at height `3858370`, but it was rejected and did not apply changes.
- Proposal `#46` passed at height `3893763`, inside epoch `252`, and was a historical compensation payout for epochs `132-247`, not an epoch `250` protocol update.
- Proposal `#48` passed at height `3919916`, inside epoch `253`, and lowered the direct participation threshold to `10%`; it was not applied during epoch `250`.

## Итоги по эпохам

| epoch | total actual rewarded coins | total expected reward | total compensation |
| --- | ---: | ---: | ---: |
| 247 | 253848231982387 | 36014151534353 | 15021814821939 |
| 248 | 129460782401156 | 247008523545220 | 117547741144064 |
| 249 | 190086354894340 | 263159578158118 | 73073223263778 |
| 250 | 252497917148785 | 282179535946778 | 29681618797993 |
| 251 | 275283461938874 | 283000681043552 | 7717219104678 |
| 252 | 273630912317725 | 281740285251423 | 8109372933698 |
| 253 | 275402940510685 | 278207656634221 | 2804716123536 |
| 254 | 219006319815693 | 229359036885622 | 10352717069929 |
| 255 | 245807020349245 | 250076583451537 | 4269563102292 |

## Кто потерял награду

Полный participant-level список находится в `outputs/combined/compensation_detailed.csv` и `outputs/combined/REPORT.md`.
В README оставлена компактная сводка по количеству строк с ненулевой потерей.

| epoch | rows with loss | total lost GNK |
| --- | ---: | ---: |
| 247 | 25 | 15021.814821939 |
| 248 | 63 | 117547.741144064 |
| 249 | 18 | 73073.223263778 |
| 250 | 19 | 29681.618797993 |
| 251 | 23 | 7717.219104678 |
| 252 | 32 | 8109.372933698 |
| 253 | 28 | 2804.716123536 |
| 254 | 51 | 10352.717069929 |
| 255 | 29 | 4269.563102292 |

## Формат итоговых файлов

- `outputs/combined/compensation_detailed.csv` - строка на участника и epoch
- `outputs/combined/compensation_summary_by_address.csv` - агрегация по адресу
- `outputs/combined/compensation_summary_by_epoch.csv` - агрегация по epoch
- `outputs/combined/REPORT.md` - человекочитаемый отчет
- `docs/` - статическая таблица для GitHub Pages

В `compensation_detailed.csv` важные колонки:

- `address`
- `epoch`
- `weight`
- `confirmation_weight`
- `effective_weight`
- `actual_reward_gnk`
- `expected_reward_base_units`
- `compensation_base_units`
- `compensation_gnk`
- `exclusion_reason`

## Как запускать

```bash
python scripts/fetch_raw_data.py --epochs 247 248 249 250 251 252 253 254 255
python scripts/calculate_compensation.py --epochs 247 248 249 250 251 252 253 254 255 --cache-only
python scripts/build_reports.py
python scripts/build_pages_data.py
python scripts/validate_consistency.py
```

## GitHub Pages table

Статическая страница лежит в `docs/index.html`. Для публикации в GitHub Pages включи Pages source: `Deploy from branch`, folder `/docs`.

Функции таблицы:

- Таблица сделана как pivot: строки - участники, колонки - epochs.
- По умолчанию показываются только строки с потерей награды.
- Можно включать/выключать отображение веса, lost reward, bug-adjusted расчета и внешних источников.
- Ячейки lost reward подсвечиваются красным, bug-adjusted слой - синим, source слой - фиолетовым.
- Если внешний source совпадает с baseline или bug-adjusted расчетом, match-cell подсвечивается зеленым.
- По клику `open` показываются notes, bug details и source details.

Данные для дополнительных слоев:

- `docs/bug_weight_adjustments.json` - ручные исправления веса из-за бага. Для строки укажи `epoch`, `address`, `adjusted_weight`, `reason`, `details`.
- `docs/source_overrides.json` - внешние расчеты компенсаций. Для строки укажи `epoch`, `address`, `source`, `source_compensation_gnk`, `status`, `details`.

После изменения этих JSON запусти `python scripts/build_pages_data.py`, чтобы обновить `docs/data/compensation_rows.json`.

## Округление

Все денежные расчеты идут через `Decimal` и `floor`. Float для base units не используется.

## Ограничения

- Если raw cache неполный, replay упадет в validation.
- `REPORT.md` содержит полный participant-level список и причины потерь.
- Логика рассчитана под уже зафетченные `247-255` epoch cache snapshots.
