"""Chronological train/validation/test logistic-regression baseline."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'Data/Expanded/pre_match_features.csv'
OUT=ROOT/'experiments/baseline_logistic_split'
FEATURES=['elo_diff_scaled','smoothed_win_rate_diff','avg_point_margin_diff','recent5_margin_diff','hunter_margin_diff','survivor_margin_diff','head_to_head_margin']
LABELS=['Elo差 / 400','历史胜率差','历史净胜分差 / 10','近五场净胜分差 / 10','监管表现差 / 4','求生表现差 / 4','历史交锋分差 / 10']

def sigmoid(v): return 1/(1+np.exp(-np.clip(v,-35,35)))

def fit(x,y,ridge,balanced):
    means=x.mean(0); scales=x.std(0); scales[scales<1e-9]=1
    z=np.column_stack([np.ones(len(x)),(x-means)/scales]); beta=np.zeros(z.shape[1])
    if balanced:
        counts=np.bincount(y,minlength=2); sw=np.array([len(y)/(2*counts[v]) for v in y])
    else: sw=np.ones(len(y))
    penalty=np.eye(z.shape[1])*ridge; penalty[0,0]=.05
    for _ in range(100):
        p=sigmoid(z@beta); w=np.maximum(p*(1-p)*sw,1e-7)
        step=np.linalg.solve(z.T@(z*w[:,None])+penalty,z.T@(sw*(y-p))-penalty@beta)
        beta+=step
        if np.max(np.abs(step))<1e-9: break
    return {'beta':beta,'means':means,'scales':scales,'ridge':ridge,'class_weight':'balanced' if balanced else 'none'}

def predict(model,x):
    z=np.column_stack([np.ones(len(x)),(x-model['means'])/model['scales']])
    return sigmoid(z@model['beta'])

def auc(y,p):
    pos=p[y==1]; neg=p[y==0]
    return float(np.mean((pos[:,None]>neg)+.5*(pos[:,None]==neg)))

def evaluate(y,p):
    p=np.clip(p,1e-9,1-1e-9); pred=(p>=.5).astype(int)
    tn=int(np.sum((y==0)&(pred==0))); fp=int(np.sum((y==0)&(pred==1)))
    fn=int(np.sum((y==1)&(pred==0))); tp=int(np.sum((y==1)&(pred==1)))
    r0=tn/(tn+fp); r1=tp/(tp+fn)
    f10=2*tn/(2*tn+fp+fn) if 2*tn+fp+fn else 0
    f11=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0
    return {'n':len(y),'accuracy':float(np.mean(pred==y)),'balanced_accuracy':(r0+r1)/2,'macro_f1':(f10+f11)/2,'roc_auc':auc(y,p),'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),'brier':float(np.mean((p-y)**2)),'confusion_matrix':[[tn,fp],[fn,tp]],'class_counts':{'away_win':int(np.sum(y==0)),'home_win':int(np.sum(y==1))}}

def balanced_log_loss(y,p):
    p=np.clip(p,1e-9,1-1e-9)
    return float(.5*(-np.log(1-p[y==0]).mean()-np.log(p[y==1]).mean()))

def roc_points(y,p):
    thresholds=[float('inf')]+sorted(set(map(float,p)),reverse=True)+[float('-inf')]
    return [{'fpr':float(np.sum((p>=t)&(y==0))/np.sum(y==0)),'tpr':float(np.sum((p>=t)&(y==1))/np.sum(y==1)),'threshold':None if not np.isfinite(t) else t} for t in thresholds]

def serial_model(m):
    return {'ridge':m['ridge'],'class_weight':m['class_weight'],'intercept':float(m['beta'][0]),'standardized_coefficients':{label:float(v) for label,v in zip(LABELS,m['beta'][1:])},'training_means':dict(zip(FEATURES,map(float,m['means']))),'training_scales':dict(zip(FEATURES,map(float,m['scales'])))}

def make_chart(result):
    bal=result['models']['balanced']; plain=result['models']['unweighted']; cm=bal['test_metrics']['confusion_matrix']
    data=json.dumps({'balanced':bal['roc'],'unweighted':plain['roc']},ensure_ascii=False,separators=(',',':'))
    rows=''
    for key,label in [('balanced','类别权重修正'),('unweighted','未加权')]:
        m=result['models'][key]['test_metrics']; rows+=f'<tr><td>{label}</td><td>{m["accuracy"]:.3f}</td><td>{m["balanced_accuracy"]:.3f}</td><td>{m["macro_f1"]:.3f}</td><td>{m["roc_auc"]:.3f}</td><td>{m["log_loss"]:.3f}</td></tr>'
    css='''body{margin:0;background:#f4f6fa;color:#192739;font:16px/1.6 "Microsoft YaHei",Arial,sans-serif}main{max-width:1120px;margin:30px auto;padding:0 22px}header,section{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:22px;margin:16px 0}h1{font-size:29px}h2{font-size:20px}p{color:#52647a}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.matrix{display:grid;grid-template-columns:120px 1fr 1fr}.matrix div{padding:18px;text-align:center;border:1px solid #d6dfeb}.head{background:#eaf0f8;font-weight:700}.good{background:#dceee6}.bad{background:#f4ded8}.big{font-size:28px;font-weight:700}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #e1e7ef;text-align:right}th:first-child,td:first-child{text-align:left}svg{width:100%;height:auto}@media(max-width:760px){.grid{grid-template-columns:1fr}}'''
    doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Logistic Regression 测试集评估</title><style>{css}</style><body><main><a href="../index.html">分析首页</a><header><h1>Logistic Regression 测试集评估</h1><p>按时间切分：训练60场、验证15场、测试15场；排除平局后为59、15、14场。验证集选择 ridge={result['selection']['selected_ridge']}，测试集未参与选择。</p></header><section><h2>测试集指标</h2><table><thead><tr><th>模型</th><th>Accuracy</th><th>Balanced Accuracy</th><th>Macro-F1</th><th>ROC-AUC</th><th>Log Loss</th></tr></thead><tbody>{rows}</tbody></table></section><div class="grid"><section><h2>类别权重模型混淆矩阵</h2><div class="matrix"><div></div><div class="head">预测客胜</div><div class="head">预测主胜</div><div class="head">实际客胜</div><div class="good"><span class="big">{cm[0][0]}</span><br>TN</div><div class="bad"><span class="big">{cm[0][1]}</span><br>FP</div><div class="head">实际主胜</div><div class="bad"><span class="big">{cm[1][0]}</span><br>FN</div><div class="good"><span class="big">{cm[1][1]}</span><br>TP</div></div></section><section><h2>ROC 曲线</h2><div id="roc"></div><p>虚线为随机分类水平。</p></section></div><section><p>类别权重仅由训练数据计算。Balanced Accuracy 与 Macro-F1 对两类给予相近权重。测试集仅14场，结果不确定性较大。</p></section></main><script>const data={data};function draw(){{const W=520,H=430,L=62,R=24,T=24,B=58,x=v=>L+v*(W-L-R),y=v=>T+(1-v)*(H-T-B);let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="ROC曲线"><path d="M${{L}} ${{T}}V${{H-B}}H${{W-R}}" fill="none" stroke="#9cabbc"/><path d="M${{x(0)}} ${{y(0)}}L${{x(1)}} ${{y(1)}}" stroke="#9cabbc" stroke-dasharray="6 5"/>`;[['balanced','#416fb8'],['unweighted','#c47b54']].forEach(([k,c])=>{{s+=`<polyline points="${{data[k].map(d=>`${{x(d.fpr)}},${{y(d.tpr)}}`).join(' ')}}" fill="none" stroke="${{c}}" stroke-width="3"/>`}});for(let q=0;q<=1;q+=.25)s+=`<text x="${{x(q)}}" y="${{H-25}}" text-anchor="middle">${{q.toFixed(2)}}</text><text x="35" y="${{y(q)+4}}" text-anchor="end">${{q.toFixed(2)}}</text>`;s+=`<text x="${{(L+W-R)/2}}" y="${{H-4}}" text-anchor="middle">False Positive Rate</text><text x="18" y="${{(T+H-B)/2}}" transform="rotate(-90 18 ${{(T+H-B)/2}})" text-anchor="middle">True Positive Rate</text><rect x="90" y="35" width="14" height="4" fill="#416fb8"/><text x="112" y="42">权重 AUC {bal['test_metrics']['roc_auc']:.3f}</text><rect x="290" y="35" width="14" height="4" fill="#c47b54"/><text x="312" y="42">未加权 AUC {plain['test_metrics']['roc_auc']:.3f}</text></svg>`;document.querySelector('#roc').innerHTML=s}}draw();</script></body></html>'''
    for folder in ['charts','chart_sources']:(ROOT/folder/'logistic-baseline-evaluation.html').write_text(doc,encoding='utf-8')

def make_chart_dashboard(result):
    """Dashboard layout matching the requested Baseline reference."""
    model=result['models']['balanced']; m=model['test_metrics']; cm=m['confusion_matrix']
    roc=json.dumps(model['roc'],ensure_ascii=False,separators=(',',':'))
    split=result['split']; ridge=result['selection']['selected_ridge']
    test_predictions=pd.read_csv(OUT/'test_predictions.csv',encoding='utf-8-sig')
    away=test_predictions[test_predictions.binary_target==0].p_home_win_balanced.to_numpy(float)
    home=test_predictions[test_predictions.binary_target==1].p_home_win_balanced.to_numpy(float)
    balanced_loss=float(.5*(-np.log(1-away).mean()-np.log(home).mean()))
    css='''
*{box-sizing:border-box}body{margin:0;background:#fff;color:#17191d;font:16px/1.45 Inter,"Segoe UI","Microsoft YaHei",Arial,sans-serif}main{max-width:1200px;margin:32px auto;padding:22px 42px 46px}a{color:#346fb7;text-decoration:none}.top-link{font-size:14px;color:#717780}h1{font-size:29px;line-height:1.2;margin:22px 0 3px;font-weight:600}h2{font-size:22px;margin:25px 0 12px;font-weight:600}.subtitle,.context{color:#8a8f97}.subtitle{margin:0 0 26px}.split{display:flex;height:82px;width:100%;gap:2px}.split>div{padding:16px 14px;font-size:17px;font-weight:600}.split span{display:block;margin-top:5px;font-size:15px;font-weight:500}.train{width:66.666%;background:#abc1e8}.validation{width:16.667%;background:#fae5ae}.test{width:16.667%;background:#efc0dc}.split-note{margin:7px 0 28px;color:#8a8f97}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.kpi{background:#f1f2f3;border-radius:18px;padding:16px 16px 13px;min-height:88px}.kpi-label{color:#8a8f97;font-size:16px}.kpi-value{font-size:27px;margin-top:4px;font-variant-numeric:tabular-nums}.metric-note{color:#8a8f97;margin:10px 0 24px}.plots{display:grid;grid-template-columns:minmax(350px,.84fr) minmax(500px,1.25fr);gap:38px}.panel h2{margin-top:0}.matrix-wrap{padding:17px 6px 0 38px}.matrix-labels{display:grid;grid-template-columns:70px 1fr 1fr;align-items:end;text-align:center;color:#888d94;margin-bottom:6px}.matrix{display:grid;grid-template-columns:70px 1fr 1fr;grid-template-rows:1fr 1fr;min-height:330px}.ylabel{display:flex;align-items:center;justify-content:center;color:#888d94}.cell{display:flex;align-items:center;justify-content:center;flex-direction:column;border:2px solid #fff}.correct{background:#abc1e8}.wrong{background:#f9e7b8}.number{font-size:36px;line-height:1}.code{margin-top:3px}.axis-caption{text-align:center;color:#5f6369;margin-top:2px}.roc-box{min-height:420px}svg{display:block;width:100%;height:auto}.footer-note{margin-top:25px;padding-top:14px;border-top:1px solid #e5e7eb;color:#767c84;font-size:14px}@media(max-width:850px){main{padding:18px}.plots{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.split>div{padding:10px 8px;font-size:14px}.split span{font-size:13px}}'''
    html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Baseline</title><style>{css}</style></head><body><main><a class="top-link" href="../index.html">← Analysis Home</a><h1>Baseline</h1><p class="subtitle">Class-balanced logistic regression · 7 original pre-match features · threshold 0.500 · ridge {ridge:g}</p><h2>Split</h2><div class="split" aria-label="60 training matches, 15 validation matches, and 15 test matches"><div class="train">Train<span>{split['training']['all_matches']} · 2025-10-02—11-09</span></div><div class="validation">Validation<span>{split['validation']['all_matches']}</span></div><div class="test">Test<span>{split['test']['all_matches']}</span></div></div><p class="split-note">Validation: 2025-11-14—11-22 · Test: 2025-11-23—11-30 · Draws retained in split manifest and excluded from binary fitting</p><div class="kpis"><div class="kpi"><div class="kpi-label">Accuracy</div><div class="kpi-value">{m['accuracy']:.1%}</div></div><div class="kpi"><div class="kpi-label">Balanced accuracy</div><div class="kpi-value">{m['balanced_accuracy']:.1%}</div></div><div class="kpi"><div class="kpi-label">Macro F1</div><div class="kpi-value">{m['macro_f1']:.3f}</div></div><div class="kpi"><div class="kpi-label">ROC AUC</div><div class="kpi-value">{m['roc_auc']:.3f}</div></div></div><p class="metric-note">Test: {m['class_counts']['home_win']} home wins, {m['class_counts']['away_win']} away wins · log loss {m['log_loss']:.3f} · balanced log loss {balanced_loss:.3f}</p><div class="plots"><section class="panel"><h2>Confusion Matrix</h2><div class="matrix-wrap"><div class="matrix-labels"><span></span><span>Away</span><span>Home</span></div><div class="matrix"><div class="ylabel">Away<br>Actual</div><div class="cell correct"><span class="number">{cm[0][0]}</span><span class="code">TN</span></div><div class="cell wrong"><span class="number">{cm[0][1]}</span><span class="code">FP</span></div><div class="ylabel">Home<br>Actual</div><div class="cell wrong"><span class="number">{cm[1][0]}</span><span class="code">FN</span></div><div class="cell correct"><span class="number">{cm[1][1]}</span><span class="code">TP</span></div></div><div class="axis-caption">Predicted</div></div></section><section class="panel"><h2>ROC</h2><div id="roc" class="roc-box"></div></section></div><p class="footer-note">Validation selected ridge strength using balanced validation log loss. Training-set class frequencies determine class weights. The final test set was evaluated once after selection and refitting on train + validation.</p></main><script>const roc={roc};function draw(){{const W=650,H=430,L=72,R=24,T=18,B=58,x=v=>L+v*(W-L-R),y=v=>T+(1-v)*(H-T-B),pts=roc.map(d=>`${{x(d.fpr)}},${{y(d.tpr)}}`).join(' ');let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="ROC curve, area under curve {m['roc_auc']:.3f}"><defs><linearGradient id="aucFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#abc1e8" stop-opacity=".65"/><stop offset="1" stop-color="#abc1e8" stop-opacity=".18"/></linearGradient></defs><rect x="${{L}}" y="${{T}}" width="${{W-L-R}}" height="${{H-T-B}}" fill="#fff" stroke="#d9dde3"/>`;for(let q=0;q<=1;q+=.25)s+=`<line x1="${{x(q)}}" y1="${{T}}" x2="${{x(q)}}" y2="${{H-B}}" stroke="#e7e9ed"/><line x1="${{L}}" y1="${{y(q)}}" x2="${{W-R}}" y2="${{y(q)}}" stroke="#e7e9ed"/><text x="${{x(q)}}" y="${{H-30}}" text-anchor="middle" fill="#555b63">${{q.toFixed(2)}}</text><text x="${{L-12}}" y="${{y(q)+5}}" text-anchor="end" fill="#555b63">${{q.toFixed(2)}}</text>`;const polygon=`${{x(0)}},${{y(0)}} `+pts+` ${{x(1)}},${{y(0)}}`;s+=`<polygon points="${{polygon}}" fill="url(#aucFill)"/><polyline points="${{pts}}" fill="none" stroke="#2f6fbe" stroke-width="4"/><line x1="${{x(0)}}" y1="${{y(0)}}" x2="${{x(1)}}" y2="${{y(1)}}" stroke="#9299a3" stroke-dasharray="7 6"/><text x="${{x(.68)}}" y="${{y(.24)}}" text-anchor="middle" font-size="16">AUC = {m['roc_auc']:.3f}</text><text x="${{(L+W-R)/2}}" y="${{H-5}}" text-anchor="middle">False positive rate</text><text x="18" y="${{(T+H-B)/2}}" transform="rotate(-90 18 ${{(T+H-B)/2}})" text-anchor="middle">True positive rate</text></svg>`;document.querySelector('#roc').innerHTML=s}}draw();</script></body></html>'''
    for folder in ['charts','chart_sources']:
        (ROOT/folder/'logistic-baseline-evaluation.html').write_text(html,encoding='utf-8')

def main():
    df=pd.read_csv(INPUT,encoding='utf-8-sig').sort_values('match_number').reset_index(drop=True)
    df['split']=np.where(df.index<60,'training',np.where(df.index<75,'validation','test'))
    df['binary_target']=df.actual.map({'客胜':0,'主胜':1})
    OUT.mkdir(parents=True,exist_ok=True)
    df[['match_number','date','home','away','actual','binary_target','split']].to_csv(OUT/'dataset_split.csv',index=False,encoding='utf-8-sig')
    usable=df[df.binary_target.notna()].copy(); usable.binary_target=usable.binary_target.astype(int)
    sets={name:usable[usable.split==name] for name in ['training','validation','test']}
    x={k:v[FEATURES].to_numpy(float) for k,v in sets.items()}; y={k:v.binary_target.to_numpy(int) for k,v in sets.items()}
    candidates=[]
    for ridge in [.1,.3,1.,3.,10.,30.]:
        model=fit(x['training'],y['training'],ridge,True); p=predict(model,x['validation'])
        candidates.append({'ridge':ridge,'balanced_validation_log_loss':balanced_log_loss(y['validation'],p),'validation_metrics':evaluate(y['validation'],p)})
    selected=min(candidates,key=lambda r:r['balanced_validation_log_loss'])['ridge']
    combined=pd.concat([sets['training'],sets['validation']]); xc=combined[FEATURES].to_numpy(float); yc=combined.binary_target.to_numpy(int)
    models={}; test_predictions=sets['test'][['match_number','date','home','away','actual','binary_target']].copy()
    for key,balanced in [('balanced',True),('unweighted',False)]:
        model=fit(xc,yc,selected,balanced); p=predict(model,x['test'])
        models[key]={'model':serial_model(model),'test_metrics':evaluate(y['test'],p),'roc':roc_points(y['test'],p)}
        test_predictions[f'p_home_win_{key}']=p; test_predictions[f'predicted_{key}']=np.where(p>=.5,'主胜','客胜')
    result={'target':'主胜=1, 客胜=0; draws excluded','features':{'keys':FEATURES,'labels':LABELS,'availability':'prior completed matches only'},'split':{k:{'all_matches':int(np.sum(df.split==k)),'non_draw_matches':len(v),'home_wins':int(v.binary_target.sum()),'away_wins':int(len(v)-v.binary_target.sum()),'date_min':v.date.min(),'date_max':v.date.max()} for k,v in sets.items()},'selection':{'criterion':'minimum balanced validation log loss','selected_ridge':selected,'candidates':candidates},'models':models,'test_evaluated_after_selection':True}
    (OUT/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); test_predictions.to_csv(OUT/'test_predictions.csv',index=False,encoding='utf-8-sig'); make_chart_dashboard(result)
    report='# Logistic Regression baseline\n\n|Model|Accuracy|Balanced Accuracy|Macro-F1|ROC-AUC|Log Loss|\n|---|---:|---:|---:|---:|---:|\n'
    for key,label in [('balanced','Class-weight balanced'),('unweighted','Unweighted')]:
        m=models[key]['test_metrics']; report+=f'|{label}|{m["accuracy"]:.3f}|{m["balanced_accuracy"]:.3f}|{m["macro_f1"]:.3f}|{m["roc_auc"]:.3f}|{m["log_loss"]:.3f}|\n'
    report+=f'\nChronological split: 60 training / 15 validation / 15 test; binary counts 59 / 15 / 14. Validation selected ridge={selected}; test was used once after selection.\n'
    (OUT/'report.md').write_text(report,encoding='utf-8')
    print(json.dumps({'selected_ridge':selected,'split':result['split'],'test':{k:v['test_metrics'] for k,v in models.items()}},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
