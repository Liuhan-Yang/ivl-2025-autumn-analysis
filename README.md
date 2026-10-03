# Identity V Research Website

The current GitHub Pages site is served from **main /docs**:
https://liuhan-yang.github.io/ivl-2025-autumn-analysis/

The bilingual website includes Project, Dataset, Models, and BP / GAN sections. English is
the default. Charts use CMasher `voltage`. Site files and all runtime data are
self-contained in `docs/`.

This website was synchronized from `Liuhan-Yang/ESports_codex`, commit
`247ef2c65921f425ed79b98d3a84250fa46d3f4b`. Its recorded multi-season and secondary
benchmarks are included in `docs/data.json`, together with source provenance.
They are not recalculated from this repository's original single-season CSV.
The original analysis has different reconstructed labels and results; keep the
two snapshots separate when interpreting or reproducing experiments.

Local preview: `python3 -m http.server 8766 --bind 127.0.0.1 --directory docs`

Validation: `node --test tests/test_site.cjs tests/test_bp.cjs`

## Conditional GAN lineup generation

Open `docs/bp.html` for browser inference with the actual trained generator.
Inputs are map, round, supplied bans, and a random seed. Outputs contain one
hunter and four distinct survivors. Bans are inputs, not generated actions;
this is not a complete sequential BP policy or an outcome predictor.

Reproduce from the repository root:

```sh
python3 -m pip install -r experiments/bp/requirements.txt
python3 experiments/bp/train.py
node --test tests/test_site.cjs tests/test_bp.cjs
```

The committed compact input snapshot is `experiments/bp/data.json`; its source
provenance and cleaning audit are recorded in the experiment outputs.
Training uses 4,952 games from 2020 Summer through 2024 Autumn. Validation is
2025 Summer; test is 2025 Autumn. Full-match groups never cross splits.
Train-only vocabularies support just 177/501 validation games and 106/484 test
games (21.9% test coverage). Excluded unseen-character/map games are not scored.

Two 60-epoch candidates compare pure cGAN and cGAN with supervised cross-entropy.
Validation selects the hybrid checkpoint at epoch 40. On 106 supported test
contexts, mean marginal Jensen–Shannon divergence is 0.0972 versus 0.2007 for
map-frequency sampling (lower is better). This is distribution similarity, not
win probability or tactical quality. One seed is exploratory evidence only.
Both methods have zero violations after hard masking; this is a decoder
guarantee, not learned tournament legality. Unmasked GAN violations are 77.1%.

- `experiments/bp/train.py`: preprocessing, training, selection and evaluation.
- `experiments/bp/results.json`: metrics, coverage, losses and runtime versions.
- `experiments/bp/generator.pt`: selected PyTorch checkpoint.
- `docs/bp.json`: exported generator weights, metrics and context examples.
- `docs/bp-engine.js`: deterministic seeded inference, tested against PyTorch.
- `docs/bp-section.tex`: English paper section with formulas and results.

The GAN snapshot and protocol are separate from the original single-season
archive below. Patch availability, full action order, player ability, and
optimal or causal win-rate improvements are not modeled.

The upstream repository contains `scripts/build_site_data.py` and its input
requirements for rebuilding the website dataset. Existing root-level files,
data, charts, and experiments below remain unchanged as the original archive.

## Original single-season archive

### 2025 IVL 秋季赛 CSV 输出

打开 index.html 浏览七类图表，全部可离线使用。

- charts/：HTML 图表页面，包括 Logistic Regression 独立测试评估。
- chart_sources/：本次生成的相同 HTML 源文件，方便修改。
- Data/：原始 CSV 副本；Expanded/ 内有 Excel、整理后的 CSV 与 JSON。
- experiments/：可复现脚本、报告、逐场预测、指标、标签差异及特征解释。

仅使用本包 CSV；没有沿用参考包的多赛季数据或模型成绩。
大场优先按回合胜数、再按总分判定，尚未逐场核对官方赛果。
二分类模型评估排除平局，不提供三分类平局概率。
详细方法、限制与复现步骤见 experiments/研究报告.md。
