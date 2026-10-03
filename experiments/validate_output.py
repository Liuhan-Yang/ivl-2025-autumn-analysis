"""Check exported data, model metrics, local links, and prefix causality."""
import hashlib, json, re, sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import build_output as builder
import match_prediction_experiment as base

root=Path(__file__).resolve().parents[1]
p=json.loads((root/'Data/Expanded/intermediate/ivl_single_season_dataset.json').read_text(encoding='utf-8'))
raw=pd.read_csv(root/'Data/Data_details_All_games_details.csv',header=1,encoding='utf-8-sig')
assert p['manifest']['sha256']==hashlib.sha256((root/'Data/Data_details_All_games_details.csv').read_bytes()).hexdigest()
assert len(p['small_games'])==len(raw)==486 and len(p['matches'])==len(p['features'])==90
assert len(p['small_games'][0])==len(raw.columns)==99
for file in [root/'index.html',*sorted((root/'charts').glob('*.html')),*sorted((root/'chart_sources').glob('*.html'))]:
    text=file.read_text(encoding='utf-8')
    for href in re.findall(r'href="([^"]+)"',text):
        if href.startswith('#'): continue
        assert (file.parent/href).exists(), f'Broken link: {file} {href}'
    assert '<svg' in text or file.name in ['index.html','feature-win-rate.html','raw-features.html']
assert len(list((root/'charts').glob('*.html')))>=8
raw_feature=json.loads((root/'experiments/results/raw_feature_outcome.json').read_text(encoding='utf-8'))
assert [item['label'] for item in raw_feature['categorical']]==['主队','客队','开赛时间','星期']
for item in raw_feature['categorical']:
    rates=[level['home_win_rate'] for level in item['levels']]
    assert rates==sorted(rates,reverse=True), f"Categorical levels not descending: {item['label']}"
assert len(raw_feature['categorical_pca']['points'])==90
assert len(raw_feature['categorical_pca']['explained_variance'])==2
split_dir=root/'experiments/baseline_logistic_split'
split=pd.read_csv(split_dir/'dataset_split.csv',encoding='utf-8-sig')
assert len(split)==90 and split.match_number.is_unique
assert split.split.value_counts().to_dict()=={'training':60,'validation':15,'test':15}
assert split.groupby('split').match_number.apply(list)['training']==list(range(1,61))
assert split.groupby('split').match_number.apply(list)['validation']==list(range(61,76))
assert split.groupby('split').match_number.apply(list)['test']==list(range(76,91))
baseline=json.loads((split_dir/'metrics.json').read_text(encoding='utf-8'))
pred=pd.read_csv(split_dir/'test_predictions.csv',encoding='utf-8-sig')
assert len(pred)==14 and set(pred.binary_target)=={0,1}
for key in ['balanced','unweighted']:
    prob=pred[f'p_home_win_{key}'].to_numpy(float); target=pred.binary_target.to_numpy(int)
    recomputed=np.mean((prob>=.5)==target)
    assert abs(recomputed-baseline['models'][key]['test_metrics']['accuracy'])<1e-12
    assert sum(map(sum,baseline['models'][key]['test_metrics']['confusion_matrix']))==14
for warmup in [20,30,40]:
    folder=root/f'experiments/results_warmup_{warmup}'
    pred=pd.read_csv(folder/'walk_forward_predictions.csv')
    saved=pd.read_csv(folder/'model_metrics.csv')
    computed=base.evaluate(pred)
    assert saved.method.tolist()==computed.method.tolist()
    for col in ['accuracy','log_loss','brier','accuracy_ci95_low','accuracy_ci95_high']:
        np.testing.assert_allclose(saved[col],computed[col],rtol=1e-12)
    for col in pred.columns:
        if col.startswith('p_home_'): assert pred[col].between(0,1).all()
matches=builder.reconstruct(raw)
prefix_matches=matches.iloc[:40].copy()
prefix_raw=raw[raw['大场序号'].isin(prefix_matches['大场序号'])]
full,_,_=base.causal_predictions(raw,matches,30)
prefix,_,_=base.causal_predictions(prefix_raw,prefix_matches,30)
for col in base.FEATURE_NAMES+list(builder.METHODS.values()):
    np.testing.assert_allclose(full.iloc[:40][col],prefix[col],rtol=1e-12,atol=1e-12)
with ZipFile(root/'Data/Expanded/IVL_single_season_dataset.xlsx') as archive:
    assert archive.testzip() is None
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    sizes=[]
    for i in range(1,5):
        sheet=ET.fromstring(archive.read(f'xl/worksheets/sheet{i}.xml'))
        rows=sheet.findall('s:sheetData/s:row',ns);sizes.append(len(rows))
        for cell in sheet.findall('.//s:c',ns): assert cell.get('t')!='e', f'Error cell in sheet {i}'
    assert sizes[1:]==[91,91,487], sizes
result=dict(raw_records=486,match_records=90,charts=len(list((root/'charts').glob('*.html'))),warmup_metric_recalculation='passed',prefix_causality='passed for first 40 matches',logistic_split_evaluation='passed',xlsx_structure='passed',links='passed',html_browser_preview='blocked by local-file browser URL policy; not performed')
(root/'experiments/qa/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
