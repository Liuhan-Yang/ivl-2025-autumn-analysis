# Identity V Research Website

The current GitHub Pages site is served from **main /docs**:
https://liuhan-yang.github.io/ivl-2025-autumn-analysis/

The bilingual website includes Project, Dataset, and Models sections. English is
the default. Charts use CMasher `voltage`. Site files and all runtime data are
self-contained in `docs/`.

This website was synchronized from `Liuhan-Yang/ESports_codex`, commit
`247ef2c65921f425ed79b98d3a84250fa46d3f4b`. Its recorded multi-season and secondary
benchmarks are included in `docs/data.json`, together with source provenance.
They are not recalculated from this repository's original single-season CSV.
The original analysis has different reconstructed labels and results; keep the
two snapshots separate when interpreting or reproducing experiments.

Local preview: `python3 -m http.server 8766 --bind 127.0.0.1 --directory docs`

Validation: `node --test tests/test_site.cjs`

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
