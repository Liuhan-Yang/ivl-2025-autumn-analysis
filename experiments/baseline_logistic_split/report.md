# Logistic Regression baseline

|Model|Accuracy|Balanced Accuracy|Macro-F1|ROC-AUC|Log Loss|
|---|---:|---:|---:|---:|---:|
|Class-weight balanced|0.571|0.604|0.562|0.688|0.760|
|Unweighted|0.643|0.667|0.641|0.708|0.723|

Chronological split: 60 training / 15 validation / 15 test; binary counts 59 / 15 / 14. Validation selected ridge=30.0; test was used once after selection.
