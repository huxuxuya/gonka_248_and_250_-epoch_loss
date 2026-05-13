# Gonka: Unreceived Reward For Epochs 248 And 250

Этот репозиторий фиксирует расчет недополученной награды за epochs `248` и `250`.

Под "недополученной наградой" здесь понимается разница между:

- ожидаемой наградой по расчету reward distribution
- фактически `rewarded_coins`, отраженными в chain raw data

Итоговая разница рассматривается как сумма, которая не была получена участниками и была отправлена в `gov` module.

Источник данных:

- raw snapshots из chain API сохранены локально в `data/raw/epoch_248/` и `data/raw/epoch_250/`
- итоговые расчеты сохранены в `outputs/`

Формула расчета:

`expected_reward_base_units = floor(effective_weight * fixed_epoch_reward / total_epoch_weight)`

`unreceived_reward_base_units = max(0, expected_reward_base_units - actual_rewarded_coins)`

`1 GNK = 1e9` base units.

В таблицах ниже показаны только участники с положительной рассчитанной потерей.

## Epoch 248

| address | unreceived_reward_base_units | unreceived_reward_gnk | loss_reason |
| --- | ---: | ---: | --- |
| gonka1umvyh0rz5fdmk9qhxurshhchennajced6f4s89 | 38635393450804 | 38635.393450804 | underpaid_vs_expected_reward |
| gonka17gpuntq09zsaqtmpe544gc32tk4424dwv5t34f | 23456534517645 | 23456.534517645 | underpaid_vs_expected_reward |
| gonka1hwvel7n3zuk6wruefuzc356l9myske9stckwnz | 16773380705218 | 16773.380705218 | underpaid_vs_expected_reward |
| gonka1pllyukkeymx3hfd9mts3pryr9y6efs9eshty87 | 13913658375295 | 13913.658375295 | underpaid_vs_expected_reward |
| gonka12pcu9mcrpa4w4sjd9y3dsksnvu495ss6f9r4ra | 13613755252922 | 13613.755252922 | underpaid_vs_expected_reward |
| gonka1ym3np7guxart483yfdxnlztuazx22cjt0e4a2p | 13041953627205 | 13041.953627205 | underpaid_vs_expected_reward |
| gonka168rtjfkszuhcggg4dfyse4yh7xn9zwfglnkns2 | 11640262821457 | 11640.262821457 | underpaid_vs_expected_reward |
| gonka1uzk2scggfzghr9a5j92l00gzw4jx4adc66977y | 7499583411321 | 7499.583411321 | underpaid_vs_expected_reward |
| gonka1zktn8j65wlys8a8e38hqhf4y3x6m4x04zskkrx | 5012099745753 | 5012.099745753 | underpaid_vs_expected_reward |
| gonka1tlvg4kjx7ljd5thgd5fkgh39q6lu8cmxupktgg | 4785035885253 | 4785.035885253 | underpaid_vs_expected_reward |
| gonka187tn9y92ur6tu0zf69u94hwl0q77m47y0k36hv | 3462203461266 | 3462.203461266 | underpaid_vs_expected_reward |
| gonka1wthc28t25pg63hzvl07rl8e8r6km6hesl6jhsz | 2604610676885 | 2604.610676885 | underpaid_vs_expected_reward |
| gonka15munkmx6x7k6rqqeexjet4556p7at39ks9qgr5 | 1979361230602 | 1979.361230602 | underpaid_vs_expected_reward |
| gonka1lswsj2x7u4606wqpunmm07skgf76r3dyz4v0d8 | 1791647658411 | 1791.647658411 | underpaid_vs_expected_reward |
| gonka1myu058axjs62mc3e7na9krwvqpfl9z3gtcw9es | 1424408669684 | 1424.408669684 | underpaid_vs_expected_reward |
| gonka1tja3g2da45efhe2p83gk3whtussmgmtsdlgprt | 1374244664994 | 1374.244664994 | underpaid_vs_expected_reward |
| gonka1r5hdy9q5v783ef7td98k4c68cxl6a58h5sytfq | 1033122569920 | 1033.122569920 | underpaid_vs_expected_reward |
| gonka1u4zxypjgcr8khlzefwjr0vwdaj2uzruw2cehj3 | 862224552997 | 862.224552997 | underpaid_vs_expected_reward |
| gonka16k03ze5ynkprsd4n6e5uzhthvu9jjk553rauqy | 624350364175 | 624.350364175 | underpaid_vs_expected_reward |
| gonka10mmdjau4dnj8krs7sh7t7635ttnmq9u3vqgz09 | 615567362106 | 615.567362106 | underpaid_vs_expected_reward |
| gonka1l0qv64xdu3dk2zzm5vk97j0drcmkus95u50gqk | 614183149784 | 614.183149784 | underpaid_vs_expected_reward |
| gonka1zpw8tml8xl4fm6zm8zpf2u4pq4tehmd9e2vgq7 | 485700907167 | 485.700907167 | underpaid_vs_expected_reward |
| gonka1tmk2tzdneht6smu34pkmqdvu7p34qavvmwtwq2 | 340330118679 | 340.330118679 | underpaid_vs_expected_reward |
| gonka188c86f9mrlt4nlcg89f82nnfm9jzq9gtjafj50 | 310319464971 | 310.319464971 | underpaid_vs_expected_reward |
| gonka1y2a9p56kv044327uycmqdexl7zs82fs5ryv5le | 294453367429 | 294.453367429 | underpaid_vs_expected_reward |
| gonka125n6kr5gvdup0lndfkps7t6rd6592panhrg3np | 215274096192 | 215.274096192 | underpaid_vs_expected_reward |
| gonka1kx9mca3xm8u8ypzfuhmxey66u0ufxhs7nm6wc5 | 204514462595 | 204.514462595 | underpaid_vs_expected_reward |
| gonka1ujnc662v6g69jm6fgxnr79a2m7ehzeut059239 | 131697631230 | 131.697631230 | underpaid_vs_expected_reward |
| gonka1lr9mj6dgkv0h76c8y8w0l3esztyg9v2q8d6d8d | 125660888375 | 125.660888375 | underpaid_vs_expected_reward |
| gonka1slndy4rsmld579628302rj5gz8z9qf4v6ppmc4 | 117467379572 | 117.467379572 | underpaid_vs_expected_reward |
| gonka1ccdm8j6sjyhq4qask049dwgaczs7f3pxte6zmp | 89403831163 | 89.403831163 | underpaid_vs_expected_reward |
| gonka1043d00lu0v3fz53cut34twtcanalqg9u8vehp2 | 42643045152 | 42.643045152 | underpaid_vs_expected_reward |
| gonka1x7zh2277spp7jfqjhv0g5mnezg290xdr4kpfnk | 32244004681 | 32.244004681 | underpaid_vs_expected_reward |
| gonka1d7p03cu2y2yt3vytq9wlfm6tlz0lfhlgv9h82p | 16587283793 | 16.587283793 | underpaid_vs_expected_reward |
| gonka1p60lruhxmwcsa9taa28cp4k4f6kv2kvyu5h5ep | 7921416734 | 7.921416734 | underpaid_vs_expected_reward |
| gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m | 5804386124 | 5.804386124 | underpaid_vs_expected_reward |
| gonka1uf5cg7ef0ns6877nl27y0s6rt06cdmn40k5a88 | 721186251 | 0.721186251 | underpaid_vs_expected_reward |

## Epoch 250

| address | unreceived_reward_base_units | unreceived_reward_gnk | loss_reason |
| --- | ---: | ---: | --- |
| gonka17gpuntq09zsaqtmpe544gc32tk4424dwv5t34f | 10405651007890 | 10405.651007890 | underpaid_vs_expected_reward |
| gonka1famtxh54kad6ylwtm60j6d7h6unpc08d4vdqnk | 5985572171061 | 5985.572171061 | underpaid_vs_expected_reward |
| gonka14ljarev2nlzu4ej50vx7ylj2rvg4n20fnq2ysc | 4014579494817 | 4014.579494817 | underpaid_vs_expected_reward |
| gonka1tja3g2da45efhe2p83gk3whtussmgmtsdlgprt | 2827217797774 | 2827.217797774 | underpaid_vs_expected_reward |
| gonka1pllyukkeymx3hfd9mts3pryr9y6efs9eshty87 | 2047233290311 | 2047.233290311 | underpaid_vs_expected_reward |
| gonka187tn9y92ur6tu0zf69u94hwl0q77m47y0k36hv | 1672001877718 | 1672.001877718 | underpaid_vs_expected_reward |
| gonka12pcu9mcrpa4w4sjd9y3dsksnvu495ss6f9r4ra | 1542035953846 | 1542.035953846 | underpaid_vs_expected_reward |
| gonka1hwvel7n3zuk6wruefuzc356l9myske9stckwnz | 1359555598432 | 1359.555598432 | underpaid_vs_expected_reward |
| gonka1wvv656pt2d8x2khcvytqeessck5uzjnxzsa8f6 | 1006491455052 | 1006.491455052 | underpaid_vs_expected_reward |
| gonka1zsvl7ujlc8z3a35v2q6e3nml7ftyk23v76jqgl | 885265631074 | 885.265631074 | underpaid_vs_expected_reward |
| gonka17pw6099q758qwzewtrqmqpf5c2lrhr97fwqexu | 814654259270 | 814.654259270 | underpaid_vs_expected_reward |
| gonka1wthc28t25pg63hzvl07rl8e8r6km6hesl6jhsz | 800827449490 | 800.827449490 | underpaid_vs_expected_reward |
| gonka1qu9mna5xlvlnw9455ygtjq92wuzkzm237w8l08 | 558240952171 | 558.240952171 | underpaid_vs_expected_reward |
| gonka1zpw8tml8xl4fm6zm8zpf2u4pq4tehmd9e2vgq7 | 556778074778 | 556.778074778 | underpaid_vs_expected_reward |
| gonka1u4zxypjgcr8khlzefwjr0vwdaj2uzruw2cehj3 | 508630420488 | 508.630420488 | underpaid_vs_expected_reward |
| gonka1q5xt54wncgzk7dxv9x64uln68455g83wu9tugg | 401010776815 | 401.010776815 | underpaid_vs_expected_reward |
| gonka1rcpc45n6zch9qlkn4m3cwngekad89xu8mcr09v | 394939993044 | 394.939993044 | underpaid_vs_expected_reward |
| gonka16k03ze5ynkprsd4n6e5uzhthvu9jjk553rauqy | 384259227082 | 384.259227082 | underpaid_vs_expected_reward |
| gonka1zktn8j65wlys8a8e38hqhf4y3x6m4x04zskkrx | 320991907654 | 320.991907654 | underpaid_vs_expected_reward |
| gonka1ym3np7guxart483yfdxnlztuazx22cjt0e4a2p | 304099569088 | 304.099569088 | underpaid_vs_expected_reward |
| gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m | 281886506509 | 281.886506509 | underpaid_vs_expected_reward |
| gonka1vcvn2p5gczr5pynqq0ca0933tdrf5w64sjgtdg | 225113881111 | 225.113881111 | underpaid_vs_expected_reward |
| gonka1u9a7r4w76gult5n9ysadnual9fghkc6yda60wj | 202272181955 | 202.272181955 | underpaid_vs_expected_reward |
| gonka1830lqug50lse998x2lakk4pj5ypfumz5pasz0y | 182661027405 | 182.661027405 | underpaid_vs_expected_reward |
| gonka1kx9mca3xm8u8ypzfuhmxey66u0ufxhs7nm6wc5 | 139108408363 | 139.108408363 | underpaid_vs_expected_reward |
| gonka1d7p03cu2y2yt3vytq9wlfm6tlz0lfhlgv9h82p | 109224580669 | 109.224580669 | underpaid_vs_expected_reward |
| gonka1amlmhjym02shahjv8ldmupg4cx0qc66q6f85rj | 99075257098 | 99.075257098 | underpaid_vs_expected_reward |
| gonka1fkrsesmn2hdj30fhwyam6h4f2e77un36xalhvl | 95621708176 | 95.621708176 | underpaid_vs_expected_reward |
| gonka1ujnc662v6g69jm6fgxnr79a2m7ehzeut059239 | 87459326268 | 87.459326268 | underpaid_vs_expected_reward |
| gonka1slndy4rsmld579628302rj5gz8z9qf4v6ppmc4 | 77903152114 | 77.903152114 | underpaid_vs_expected_reward |
| gonka1lr9mj6dgkv0h76c8y8w0l3esztyg9v2q8d6d8d | 77101076575 | 77.101076575 | underpaid_vs_expected_reward |
| gonka1vjz8csqsr0ph0lv0yylc4auypnzrld7y6l2feu | 63446806435 | 63.446806435 | underpaid_vs_expected_reward |
| gonka1ccdm8j6sjyhq4qask049dwgaczs7f3pxte6zmp | 36210830730 | 36.210830730 | underpaid_vs_expected_reward |
| gonka1qwfrtz9c7kcrfkrrlne2pkcye74mj6ce33xdkl | 36084095791 | 36.084095791 | underpaid_vs_expected_reward |
| gonka1x7zh2277spp7jfqjhv0g5mnezg290xdr4kpfnk | 36047456738 | 36.047456738 | underpaid_vs_expected_reward |
| gonka1gyk0aahvr3qeju4zx0nplfreej6cy4jjk8svc5 | 25358764054 | 25.358764054 | underpaid_vs_expected_reward |
| gonka1tmk2tzdneht6smu34pkmqdvu7p34qavvmwtwq2 | 17695017982 | 17.695017982 | underpaid_vs_expected_reward |
| gonka1tlvg4kjx7ljd5thgd5fkgh39q6lu8cmxupktgg | 1655809871 | 1.655809871 | underpaid_vs_expected_reward |

## Итоговые Артефакты

- `outputs/epoch_248/compensation_248.csv`
- `outputs/epoch_250/compensation_250.csv`
- `outputs/combined/compensation_detailed.csv`
- `outputs/combined/compensation_summary_by_epoch.csv`
- `outputs/combined/compensation_summary_by_address.csv`
- `outputs/combined/REPORT.md`

## Замечание

Причина потери в текущем README выводится из расчетного результата:

- `underpaid_vs_expected_reward` означает, что рассчитанная ожидаемая награда выше фактически отраженной в `rewarded_coins`

Если нужно, следующим шагом могу заменить `loss_reason` на более детальную нормализованную причину из `exclusion_reason` и `notes`, где это различимо по raw данным.
