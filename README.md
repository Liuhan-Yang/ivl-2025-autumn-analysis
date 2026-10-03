# 2025 IVL 秋季赛 CSV 输出

打开 index.html 浏览七类图表，全部可离线使用。

- charts/：HTML 图表页面，包括 Logistic Regression 独立测试评估。
- chart_sources/：本次生成的相同 HTML 源文件，方便修改。
- Data/：原始 CSV 副本；Expanded/ 内有 Excel、整理后的 CSV 与 JSON。
- experiments/：可复现脚本、报告、逐场预测、指标、标签差异及特征解释。

仅使用本包 CSV；没有沿用参考包的多赛季数据或模型成绩。
大场优先按回合胜数、再按总分判定，尚未逐场核对官方赛果。
二分类模型评估排除平局，不提供三分类平局概率。
详细方法、限制与复现步骤见 experiments/研究报告.md。
