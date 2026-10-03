"""Rebuild this single-season IVL output from the included CSV. No network needed.
Run: python experiments/build_output.py (from any working directory).
"""
from pathlib import Path
import hashlib, html, json, math, shutil
import numpy as np
import pandas as pd
import match_prediction_experiment as base

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Data/Data_details_All_games_details.csv'
LABELS = ['Elo 分差 / 400', '平滑历史胜率差', '历史净胜分差 / 10', '最近五场净胜分差 / 10', '监管表现差 / 4', '求生表现差 / 4', '历史交锋净胜分 / 10']
METHODS = {'历史胜率':'p_home_win_rate','Elo':'p_home_elo','Bradley-Terry':'p_home_bradley_terry','状态逻辑回归':'p_home_form_logistic','三模型等权集成':'p_home_ensemble'}
CSS = '''body{margin:0;background:#f4f6fa;color:#192739;font:16px/1.65 "Microsoft YaHei",Arial,sans-serif}main{max-width:1160px;margin:32px auto;padding:0 24px}h1{font-size:30px;line-height:1.3}h2{font-size:20px}a{color:#265ab5}header,section{background:white;border:1px solid #dce3ec;border-radius:12px;padding:24px;margin:18px 0}p{color:#506176}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{flex:1;min-width:140px;background:#edf3fb;padding:16px;border-radius:8px}.card strong{display:block;font-size:28px;color:#254f91}svg{width:100%;height:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #e4e9f0}th{background:#eaf0f8;position:sticky;top:0}tr:hover{background:#f0f5fd}.scroll{overflow:auto}select,input{padding:8px;font-size:15px;border:1px solid #adbdd2;border-radius:6px}nav{display:flex;gap:16px;flex-wrap:wrap}.notice{border-left:4px solid #c78a24;padding-left:14px}footer{font-size:13px;color:#617286;margin:24px 0}circle:hover{stroke:#172c48;stroke-width:2}'''

def dump(path, obj):
    path=ROOT/path; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def records(df):
    return json.loads(df.to_json(orient='records',force_ascii=False,date_format='iso'))

def table(df):
    return '<div class="scroll">'+df.to_html(index=False,escape=True,border=0,float_format=lambda v:f'{v:.4f}')+'</div>'

def page(name,title,subtitle,content,script=''):
    back='../index.html' if name!='index' else '#'
    doc=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><main><nav><a href="{back}">分析首页</a></nav><header><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></header>{content}<footer>来源：随包 CSV。图表与指标由本次数据重新计算，可离线浏览。</footer></main><script>{script}</script></body></html>'
    if name=='index': (ROOT/'index.html').write_text(doc,encoding='utf-8')
    else:
        for folder in ['charts','chart_sources']:
            (ROOT/folder/f'{name}.html').write_text(doc,encoding='utf-8')

def bars(names,values,title,percent=False,signed=False):
    n=len(names); height=80+n*44; left=250; width=650
    maxv=max([abs(v) for v in values]+[.001])*(1.16 if not percent else 1)
    if percent: maxv=max(maxv,1)
    zero=left+width/2 if signed else left
    scale=width/(2*maxv) if signed else width/maxv
    s=f'<svg viewBox="0 0 1040 {height}" role="img" aria-label="{html.escape(title)}"><text x="20" y="28" font-size="17">{html.escape(title)}</text>'
    for i,(name,v) in enumerate(zip(names,values)):
        y=50+i*44; x=zero+min(v,0)*scale; w=abs(v)*scale
        lab=f'{v:.1%}' if percent else f'{v:.3f}'
        s+=f'<text x="15" y="{y+20}" font-size="14">{html.escape(str(name))}</text><rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="27" rx="3" fill="{"#416fb8" if v>=0 else "#bd745b"}"><title>{html.escape(str(name))}：{lab}</title></rect><text x="{zero+max(v,0)*scale+8:.2f}" y="{y+20}" font-size="13">{lab}</text>'
    return s+'</svg>'

def wilson(k,n):
    p=k/n; d=1+1.96**2/n; c=(p+1.96**2/(2*n))/d; r=1.96*math.sqrt(p*(1-p)/n+1.96**2/(4*n*n))/d
    return c-r,c+r

def metric(y,p):
    p=np.clip(np.asarray(p),1e-6,1-1e-6); acc=float(np.mean((p>=.5)==y)); lo,hi=wilson(int(np.sum((p>=.5)==y)),len(y))
    positives=p[y==1]; negatives=p[y==0]
    auc=float(np.mean((positives[:,None]>negatives)+.5*(positives[:,None]==negatives))) if len(positives)*len(negatives) else None
    return dict(n=len(y),accuracy=acc,accuracy_ci95_low=lo,accuracy_ci95_high=hi,log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),brier=float(np.mean((p-y)**2)),roc_auc=auc)

def categorical_outcome_analysis(matches, predictions):
    """Rank categorical levels and project their one-hot match vectors with PCA."""
    rows=[]
    weekday_names={'Monday':'周一','Tuesday':'周二','Wednesday':'周三','Thursday':'周四','Friday':'周五','Saturday':'周六','Sunday':'周日'}
    for i,match in matches.iterrows():
        raw_time=int(match['time'])
        rows.append({
            '主队':str(match['home']), '客队':str(match['away']),
            '开赛时间':f'{raw_time//100:02d}:{raw_time%100:02d}',
            '星期':weekday_names[pd.Timestamp(match['date']).day_name()],
            'actual':str(predictions.iloc[i]['actual']),
            'match_number':int(match['大场序号']),
            'match':f"{match['home']} vs {match['away']}",
        })
    categorical=[]
    for label in ['主队','客队','开赛时间','星期']:
        levels=[]
        values=sorted({row[label] for row in rows})
        for level in values:
            selected=[row for row in rows if row[label]==level and row['actual']!='平局']
            n=len(selected); wins=sum(row['actual']=='主胜' for row in selected)
            if not n: continue
            lo,hi=wilson(wins,n)
            levels.append(dict(level=level,home_win_rate=wins/n,n=n,home_wins=wins,ci_low=lo,ci_high=hi))
        levels.sort(key=lambda r:(-r['home_win_rate'],-r['n'],r['level']))
        categorical.append(dict(label=label,levels=levels))
    offsets={}; offset=0
    for label in ['主队','客队','开赛时间','星期']:
        levels=sorted({row[label] for row in rows})
        offsets[label]={value:offset+i for i,value in enumerate(levels)}
        offset+=len(levels)
    matrix=np.zeros((len(rows),offset),dtype=float)
    for i,row in enumerate(rows):
        for label,lookup in offsets.items(): matrix[i,lookup[row[label]]]=1.
    centered=matrix-matrix.mean(axis=0)
    u,s,_=np.linalg.svd(centered,full_matrices=False)
    coords=u[:,:2]*s[:2]; explained=s[:2]**2/np.sum(s**2)
    points=[dict(match_number=row['match_number'],match=row['match'],actual=row['actual'],pc1=float(coords[i,0]),pc2=float(coords[i,1])) for i,row in enumerate(rows)]
    return categorical,points,explained

def reconstruct(raw):
    matches=base.reconstruct_matches(raw)
    rounds=raw.groupby(['大场序号','场次号'])[['主分','客分']].sum()
    details={}
    for number,g in rounds.groupby(level=0):
        hw=int((g['主分']>g['客分']).sum()); aw=int((g['主分']<g['客分']).sum())
        details[number]=(hw,aw)
    matches['home_round_wins']=[details[k][0] for k in matches['大场序号']]
    matches['away_round_wins']=[details[k][1] for k in matches['大场序号']]
    matches['score_target']=matches['target']
    edge=matches.home_round_wins-matches.away_round_wins
    matches['target']=np.where(edge>0,1.,np.where(edge<0,0.,matches.score_target))
    matches['deciding_rule']=np.where(edge!=0,'round_wins',np.where(matches.margin!=0,'total_score','draw_or_unresolved'))
    matches['label_disagreement']=matches.target!=matches.score_target
    return matches

def main():
    raw=pd.read_csv(SOURCE,header=1,encoding='utf-8-sig')
    required=['大场序号','场次号','小局唯一ID','日期','具体时间','主场','客场','主分','客分','监管方队伍','求生方队伍','监管方得分','求生方得分']
    assert not raw[required].isna().any().any(), 'Required source data is missing'
    assert raw['小局唯一ID'].is_unique, 'Duplicate small-game IDs'
    assert raw.groupby(['大场序号','场次号']).size().eq(2).all(), 'Each round must have two halves'
    for c in ['日期','具体时间','主场','客场']:
        assert raw.groupby('大场序号')[c].nunique().eq(1).all(), f'Inconsistent match identity: {c}'
    matches=reconstruct(raw)
    assert not matches.duplicated(['date','time']).any(), 'Simultaneous match starts require batch state updates'
    predictions,elo,_=base.causal_predictions(raw,matches,30)
    features=predictions[['match_number','date','home','away','actual']+base.FEATURE_NAMES].copy()
    frames=[]
    for warmup in [20,30,40]:
        pred=predictions.copy(); pred['is_test']=pred.chronological_index>warmup
        metrics=base.evaluate(pred)
        folder=ROOT/f'experiments/results_warmup_{warmup}'; folder.mkdir(exist_ok=True)
        pred.to_csv(folder/'walk_forward_predictions.csv',index=False,encoding='utf-8-sig')
        metrics.to_csv(folder/'model_metrics.csv',index=False,encoding='utf-8-sig')
        summary=dict(input_rows=len(raw),matches=len(matches),warmup_matches=warmup,test_non_draw_matches=int(metrics.iloc[0].n_non_draw_test),label_rule='round wins first, then total score; tied totals unresolved',final_elo=dict(sorted(elo.items(),key=lambda x:-x[1])))
        dump(f'experiments/results_warmup_{warmup}/experiment_summary.json',summary)
        for row in records(metrics): row['warmup']=warmup; frames.append(row)
    shutil.copytree(ROOT/'experiments/results_warmup_30',ROOT/'experiments/results',dirs_exist_ok=True)
    allmetrics=pd.DataFrame(frames); mainmetrics=allmetrics[allmetrics.warmup==30].drop(columns='warmup')
    mask=predictions.is_test & (predictions.actual!='平局')
    y=(predictions.loc[mask,'actual']=='主胜').to_numpy(dtype=float)
    x=features[base.FEATURE_NAMES].to_numpy(dtype=float)
    # Online Elo logistic baseline: fixed ridge, fitted only on past matches.
    elo_lr=[]; constant=[]
    targets=matches.target.to_numpy(dtype=float)
    for i in range(len(matches)):
        elo_lr.append(base.logistic_predict(base.fit_ridge_logistic(x[:i,:1],targets[:i],ridge=2.),x[i,:1]) if i>=20 else .5)
        constant.append(float(np.mean(targets[:i])) if i else .5)
    comparison={'历史均值基线':metric(y,np.array(constant)[mask]),'原始 Elo':metric(y,predictions.loc[mask,'p_home_elo']),'Elo 逻辑回归':metric(y,np.array(elo_lr)[mask]),'全部七特征逻辑回归':metric(y,predictions.loc[mask,'p_home_form_logistic'])}
    predictions['p_home_elo_logistic']=elo_lr; predictions['p_home_historical_constant']=constant
    predictions.to_csv(ROOT/'experiments/results/walk_forward_predictions.csv',index=False,encoding='utf-8-sig')
    # Interpret a frozen model fitted to warmup history, not a model fitted on test outcomes.
    frozen=base.fit_ridge_logistic(x[:30],targets[:30],ridge=2.)
    frozen_p=np.array([base.logistic_predict(frozen,row) for row in x[mask]])
    frozen_metrics=metric(y,frozen_p)
    coefficients=[dict(feature=k,label=lab,standardized_coefficient=float(v)) for k,lab,v in zip(base.FEATURE_NAMES,LABELS,frozen[0][1:])]
    rng=np.random.default_rng(42); importance=[]
    for j,(k,lab) in enumerate(zip(base.FEATURE_NAMES,LABELS)):
        delta=[]
        for _ in range(100):
            xp=x[mask].copy(); xp[:,j]=rng.permutation(xp[:,j]); pp=[base.logistic_predict(frozen,row) for row in xp]
            delta.append(metric(y,pp)['log_loss']-frozen_metrics['log_loss'])
        importance.append(dict(feature=k,label=lab,delta_log_loss=float(np.mean(delta)),sd=float(np.std(delta))))
    binary=targets!=.5; outcomes=targets[binary]
    relations=[]
    for j,(k,lab) in enumerate(zip(base.FEATURE_NAMES,LABELS)):
        vals=x[binary,j]; edges=np.unique(np.quantile(vals,np.linspace(0,1,6)))
        ids=np.digitize(vals,edges[1:-1],right=True); bins=[]
        for b in range(len(edges)-1):
            bm=ids==b; n=int(bm.sum())
            if not n: continue
            wins=int(outcomes[bm].sum()); lo,hi=wilson(wins,n)
            bins.append(dict(mean=float(vals[bm].mean()),n=n,wins=wins,home_win_rate=wins/n,ci_low=lo,ci_high=hi))
        corr=float(np.corrcoef(vals,outcomes)[0,1]) if vals.std()>0 else 0.
        relations.append(dict(feature=k,label=lab,correlation=corr,bins=bins))
    # PCA of standardized seven numerical pre-match features, all rows, descriptive only.
    scales=x.std(axis=0); scales[scales<1e-8]=1; z=(x-x.mean(axis=0))/scales
    u,s,vt=np.linalg.svd(z,full_matrices=False); coords=u[:,:2]*s[:2]; variance=s*s/np.sum(s*s)
    points=[dict(match_number=int(matches.iloc[i]['大场序号']),home=matches.iloc[i].home,away=matches.iloc[i].away,actual=predictions.iloc[i].actual,pc1=float(c[0]),pc2=float(c[1])) for i,c in enumerate(coords)]
    categorical,categorical_points,categorical_variance=categorical_outcome_analysis(matches,predictions)
    disagreements=matches[matches.label_disagreement].copy(); disagreements['date']=disagreements.date.dt.strftime('%Y-%m-%d')
    disagreements.to_csv(ROOT/'experiments/label_disagreements.csv',index=False,encoding='utf-8-sig')
    missing=[dict(column=c,missing=int(raw[c].isna().sum()),missing_rate=float(raw[c].isna().mean())) for c in raw.columns]
    profile=dict(source=SOURCE.name,sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),rows=len(raw),columns=len(raw.columns),matches=len(matches),teams=len(elo),date_min=matches.date.min().strftime('%Y-%m-%d'),date_max=matches.date.max().strftime('%Y-%m-%d'),small_game_outcomes=raw['单局结果'].value_counts().to_dict(),match_outcomes=predictions.actual.value_counts().to_dict(),label_disagreements=len(disagreements),duplicate_small_game_ids=int(raw['小局唯一ID'].duplicated().sum()),missing=missing)
    mexport=matches.copy(); mexport['date']=mexport.date.dt.strftime('%Y-%m-%d')
    payload=dict(manifest=profile,matches=records(mexport),features=records(features),small_games=records(raw),feature_dictionary=[dict(feature=k,label=l,available_at='before current match; after prior matches finish') for k,l in zip(base.FEATURE_NAMES,LABELS)])
    dump('Data/Expanded/intermediate/ivl_single_season_dataset.json',payload)
    for df,name in [(raw,'small_games'),(mexport,'matches'),(features,'pre_match_features')]:
        df.to_csv(ROOT/f'Data/Expanded/{name}.csv',index=False,encoding='utf-8-sig')
    dump('experiments/data_profile.json',profile)
    dump('experiments/results/logistic_baseline_results.json',dict(protocol='walk-forward, fixed ridge=2, warmup=30',metrics=comparison,frozen_model_metrics=frozen_metrics,coefficients=coefficients,permutation_importance=importance,interpretation_training_matches=30))
    dump('experiments/results/feature_winrate_relationships.json',dict(population='all non-draw matches; exploratory, not independent validation',features=relations))
    dump('experiments/results/raw_feature_outcome.json',dict(
        population='90 matches; win-rate rankings exclude 2 draws',
        numeric=relations,
        categorical=categorical,
        categorical_pca=dict(method='PCA of one-hot categorical vectors',features=['主队','客队','开赛时间','星期'],explained_variance=categorical_variance.tolist(),points=categorical_points),
        numeric_pca=dict(method='PCA of standardized seven pre-match numerical features',explained_variance=variance[:2].tolist(),points=points)))
    generate_charts(profile,mainmetrics,allmetrics,comparison,coefficients,importance,relations,categorical,categorical_points,categorical_variance,raw,disagreements)
    report(profile,mainmetrics,comparison,disagreements,frozen_metrics)
    print(json.dumps({k:v for k,v in profile.items() if k!='missing'},ensure_ascii=False,indent=2))
    print(mainmetrics.to_string(index=False))

def generate_charts(p,metrics,sensitivity,comparison,coef,imp,relations,categorical,categorical_points,categorical_var,raw,disagreements):
    cards='<div class="cards">'+''.join(f'<div class="card">{lab}<strong>{val}</strong></div>' for lab,val in [('半局记录',p['rows']),('大场',p['matches']),('队伍',p['teams']),('字段',p['columns'])])+'</div>'
    counts=raw['地图'].value_counts()
    missing=pd.DataFrame(p['missing']).sort_values('missing_rate',ascending=False)
    page('ivl-data-profile','数据概况',f"{p['date_min']} 至 {p['date_max']}，2025 IVL 秋季赛常规赛。",f'<section>{cards}</section><section>{bars(counts.index.tolist(),counts.values.tolist(),"各地图半局数")}</section><section><h2>原始字段缺失率</h2><p>BP 空值可能表示该轮不适用，不能统一理解为采集缺失。</p>{table(missing)}</section>')
    def donut(counts,title):
        total=sum(counts.values()); color=['#416fb8','#d49b47','#64a696']; acc=0; pieces=''
        for i,(name,n) in enumerate(counts.items()):
            size=100*n/total
            pieces+=f'<circle cx="150" cy="150" r="95" fill="none" stroke="{color[i%3]}" stroke-width="38" pathLength="100" stroke-dasharray="{size} {100-size}" stroke-dashoffset="{-acc}" transform="rotate(-90 150 150)"><title>{name}：{n}（{n/total:.1%}）</title></circle>'
            pieces+=f'<text x="310" y="{90+i*45}" fill="{color[i%3]}" font-size="19">{name}：{n}（{n/total:.1%}）</text>'; acc+=size
        return f'<h2>{title}</h2><svg viewBox="0 0 750 300">{pieces}<text x="150" y="158" text-anchor="middle" font-size="30">{total}</text></svg>'
    page('ivl-outcome-pie','赛果分布','半局按原始单局结果统计；大场优先按回合胜负判定。',f'<section>{donut(p["small_game_outcomes"],"半局三类结果")}</section><section>{donut(p["match_outcomes"],"大场结果")}</section><section><h2>标签口径差异：{len(disagreements)} 场</h2>{table(disagreements[["date","home","away","home_score","away_score","home_round_wins","away_round_wins","score_target","target"]])}<p>大场 target：主胜=1、客胜=0、平局或未决=0.5。半局结果保留原始中文标签。</p></section>')
    page('baseline','基线回测','前 30 场热身，随后逐场预测；记录概率后才更新状态，平局不计入二分类指标。',f'<section>{bars(metrics.method.tolist(),metrics.accuracy.tolist(),"准确率",percent=True)}{table(metrics)}</section><section><h2>热身长度敏感性</h2><p>20、30、40 场切分的测试集不同，结果用于探索，不用于挑选最佳切分。</p>{table(sensitivity)}</section>')
    comp=pd.DataFrame([dict(model=k,**v) for k,v in comparison.items()])
    page('ivl-model-comparison','模型比较','统一使用前 30 场热身后的非平局比赛。逻辑回归 ridge=2 为预设值，未根据测试指标调参。',f'<section>{bars(comp.model.tolist(),comp.log_loss.tolist(),"对数损失（越低越好）")}{table(comp)}</section><section><p>历史均值基线使用此前全部赛果的均值。Elo 与逻辑回归随历史逐场更新。此处没有多赛季训练结果。</p></section>')
    co=pd.DataFrame(coef); im=pd.DataFrame(imp).sort_values('delta_log_loss',ascending=False)
    page('logistic-feature-contribution','逻辑回归特征贡献','解释对象是仅用前 30 场训练并冻结的模型。该模型与逐场重训模型的成绩不同。',f'<section>{bars(co.label.tolist(),co.standardized_coefficient.tolist(),"标准化系数",signed=True)}<p>正系数增加主胜倾向，负系数增加客胜倾向；相关特征会分摊权重，不能解释为因果关系。</p></section><section>{bars(im.label.tolist(),im.delta_log_loss.tolist(),"置换后对数损失变化",signed=True)}{table(im)}<p>在同一测试集上置换每个特征 100 次。负值可能提示噪声，但不能据此重新选择特征后继续声称该测试集独立。</p></section>')
    options=''.join(f'<option value="{i}">{html.escape(r["label"])}</option>' for i,r in enumerate(relations))
    script='const data='+json.dumps(relations,ensure_ascii=False)+';'+'''function draw(){const r=data[document.querySelector('select').value];document.querySelector('#info').textContent='与主胜标签的相关系数：'+r.correlation.toFixed(3);let s='<svg viewBox="0 0 960 420"><path d="M80 30 V350 H900" fill="none" stroke="#a7b7ca"/>';for(let t=0;t<=1;t+=.25){let y=350-300*t;s+=`<line x1="80" y1="${y}" x2="900" y2="${y}" stroke="#e1e8f1"/><text x="25" y="${y+5}">${Math.round(t*100)}%</text>`;}r.bins.forEach((b,i)=>{let x=150+i*160,y=350-b.home_win_rate*300;s+=`<line x1="${x}" x2="${x}" y1="${350-b.ci_low*300}" y2="${350-b.ci_high*300}" stroke="#416fb8"/><circle cx="${x}" cy="${y}" r="7" fill="#416fb8"><title>均值 ${b.mean.toFixed(3)}，${b.wins}/${b.n} 主胜，95%区间 ${(b.ci_low*100).toFixed(1)}%–${(b.ci_high*100).toFixed(1)}%</title></circle><text x="${x}" y="380" text-anchor="middle">${b.mean.toFixed(2)}</text><text x="${x}" y="405" text-anchor="middle">n=${b.n}</text>`});document.querySelector('#plot').innerHTML=s+'</svg>';}document.querySelector('select').addEventListener('change',draw);draw();'''
    page('feature-win-rate','赛前特征与主胜率','全部非平局大场的探索性统计；按特征分位数分组，误差线为 95% Wilson 区间。',f'<section><label>特征 <select>{options}</select></label><p id="info"></p><div id="plot"></div><p>横轴为组内特征均值，纵轴为实际主胜率。等频分组在大量相同取值时会少于五组，相关性不等于预测增益。</p></section>',script)
    corr=sorted(relations,key=lambda r:abs(r['correlation']),reverse=True)
    category_options=''.join(f'<option value="{i}">{html.escape(item["label"])}</option>' for i,item in enumerate(categorical))
    script='const categorical='+json.dumps(categorical,ensure_ascii=False)+';const points='+json.dumps(categorical_points,ensure_ascii=False)+';'+'''const colors={'主胜':'#416fb8','客胜':'#c47b54','平局':'#8e99a8'};
function drawRanks(){const item=categorical[document.querySelector('#category-variable').value],levels=item.levels,h=70+levels.length*42;let s=`<svg viewBox="0 0 960 ${h}"><text x="15" y="24">${item.label}各水平主胜率（降序）</text>`;levels.forEach((d,i)=>{const y=44+i*42,w=d.home_win_rate*650;s+=`<text x="15" y="${y+20}">${d.level}</text><rect x="190" y="${y}" width="${w}" height="26" rx="3" fill="#416fb8"><title>${d.home_wins}/${d.n} 主胜，95%区间 ${(d.ci_low*100).toFixed(1)}%–${(d.ci_high*100).toFixed(1)}%</title></rect><text x="${198+w}" y="${y+20}">${(d.home_win_rate*100).toFixed(1)}%（n=${d.n}）</text>`});document.querySelector('#category-ranking').innerHTML=s+'</svg>'}
function drawPca(){const filter=document.querySelector('#outcome-filter').value,a=points.map(p=>p.pc1),b=points.map(p=>p.pc2),lo=Math.min(...a)-.2,hi=Math.max(...a)+.2,bot=Math.min(...b)-.2,top=Math.max(...b)+.2;let s='<svg viewBox="0 0 960 500"><path d="M70 30 V440 H900" fill="none" stroke="#a7b7ca"/>';points.forEach(p=>{const x=70+(p.pc1-lo)/(hi-lo)*830,y=440-(p.pc2-bot)/(top-bot)*400,opacity=(filter==='全部'||p.actual===filter)?.8:.08;s+=`<circle cx="${x}" cy="${y}" r="6" opacity="${opacity}" fill="${colors[p.actual]}"><title>第 ${p.match_number} 场 ${p.match}，${p.actual}，PC1=${p.pc1.toFixed(2)}，PC2=${p.pc2.toFixed(2)}</title></circle>`});s+='<text x="470" y="480">第一主成分</text><text x="20" y="30">第二主成分</text></svg>';document.querySelector('#categorical-pca').innerHTML=s}
document.querySelector('#category-variable').addEventListener('change',drawRanks);document.querySelector('#outcome-filter').addEventListener('change',drawPca);drawRanks();drawPca();'''
    page('raw-features','原始变量与胜负关系','数值变量按相关性展示；分类变量水平按主胜率降序排列；分类独热向量经 PCA 降至二维。',f'<section><h2>数值变量</h2>{bars([r["label"] for r in corr],[r["correlation"] for r in corr],"与主胜标签的相关系数",signed=True)}<p>相关性使用 88 场非平局比赛，只描述线性关系，不代表因果。</p></section><section><h2>分类变量（降序）</h2><label>分类变量 <select id="category-variable">{category_options}</select></label><div id="category-ranking"></div><p>主胜率排名排除 2 场平局；悬停可查看主胜场数、样本数和 95% Wilson 区间。</p></section><section><h2>分类向量降维</h2><p>主队、客队、开赛时间和星期进行独热编码。PC1 解释 {categorical_var[0]:.1%} 方差，PC2 解释 {categorical_var[1]:.1%}。蓝：主胜；橙：客胜；灰：平局。</p><label>赛果 <select id="outcome-filter"><option>全部</option><option>主胜</option><option>客胜</option><option>平局</option></select></label><div id="categorical-pca"></div><p>PCA 未使用胜负标签；二维位置接近表示分类组合相似，不表示胜负因果关系。</p></section>',script)
    titles={'logistic-baseline-evaluation':'Logistic Regression 训练/验证/测试评估','baseline':'基线回测','feature-win-rate':'特征与胜率','ivl-data-profile':'数据概况','ivl-model-comparison':'模型比较','ivl-outcome-pie':'赛果分布','logistic-feature-contribution':'特征贡献','raw-features':'特征探索与 PCA'}
    links='<nav>'+''.join(f'<a href="charts/{k}.html">{v}</a>' for k,v in titles.items())+'</nav>'
    best=metrics.iloc[0]
    page('index','2025 IVL 秋季赛数据分析',f"{p['date_min']} 至 {p['date_max']}。单一 CSV 数据，所有图表可离线使用。",f'<section>{cards}</section><section><h2>分析图表</h2>{links}</section><section><h2>逐场回测</h2><p>前 30 场热身；测试非平局 {int(best.n_non_draw_test)} 场。对数损失最低的模型为 {best.method}，准确率 {best.accuracy:.1%}。这是历史探索性成绩。</p>{table(metrics)}</section><section><h2>数据与报告</h2><nav><a href="Data/Expanded/IVL_single_season_dataset.xlsx">Excel 数据集</a><a href="Data/Expanded/intermediate/ivl_single_season_dataset.json">JSON 数据集</a><a href="experiments/研究报告.md">研究报告</a><a href="experiments/label_disagreements.csv">标签差异清单</a></nav><p class="notice">大场优先比较回合胜数，再比较总分；与直接按总比分判断存在 {p["label_disagreements"]} 场差异。此规则由 CSV 重建，尚未逐场核对官方结果。</p></section>')

def report(p,metrics,comp,disagreements,frozen):
    md=f'''# 2025 IVL 秋季赛 CSV 分析

## 数据与目标
来源：Data/Data_details_All_games_details.csv；SHA256：{p['sha256']}。
第一行是导出标题，读取使用 header=1、encoding=utf-8-sig。
{p['rows']} 条半局记录、{p['columns']} 个字段、{p['matches']} 个大场、{p['teams']} 支队伍。
日期：{p['date_min']} 至 {p['date_max']}。只有一个赛季，未使用参考包的跨赛季数据。
半局分布：{p['small_game_outcomes']}。大场分布：{p['match_outcomes']}。

## 大场标签
按大场序号和场次号聚合两条半局，主客分之和决定一轮胜负。
先比较大场回合胜数；回合胜数相同时比较总比分；两者都相同记为平局或未决。
大场主胜=1、客胜=0、平局或未决=0.5。原始半局三分类中文标签保留。
与只比较总比分存在 {p['label_disagreements']} 场差异，详见 label_disagreements.csv。
这是一种可复核的数据重建口径，仍需核对官方赛果及加赛规则。

## 回测方法
按日期、具体时间、大场序号排序。前 30 场热身，之后每场先预测，再更新历史。
Elo 初始 1500，K=28；历史胜率采用 Beta(2,2) 平滑；逻辑回归 ridge=2 固定。
逻辑回归每次仅用之前比赛训练，均值和标准差也仅用训练历史。
所有七个特征都来自已结束的大场，不直接使用当前比分、当前用时、MVP 或底牌后。
训练状态更新接受平局=0.5；二分类指标排除平局，模型不输出平局概率。
表中概率是主胜/客胜二分类倾向，不能作为包含平局事件的完整三分类分布。
20/30/40 热身切分用于敏感性分析，不选择成绩最佳的切分。

## 30 场热身结果
'''
    columns=metrics.columns.tolist(); md+='\n|'+'|'.join(columns)+'|\n|'+'|'.join(['---']*len(columns))+'|\n'
    for row in records(metrics): md+='|'+'|'.join(f'{row[c]:.4f}' if isinstance(row[c],float) else str(row[c]) for c in columns)+'|\n'
    md+='\n## Elo 与逻辑回归比较\n\n|模型|准确率|对数损失|Brier|\n|---|---:|---:|---:|\n'
    for k,v in comp.items(): md+=f'|{k}|{v["accuracy"]:.1%}|{v["log_loss"]:.4f}|{v["brier"]:.4f}|\n'
    md+=f'''\n## 特征解释与限制
系数和置换重要性使用前 30 场训练后冻结的模型，测试准确率 {frozen['accuracy']:.1%}，对数损失 {frozen['log_loss']:.4f}。
它与逐场重训模型不同，不能把冻结模型的重要性直接当成所有在线模型的重要性。
分组胜率与相关系数使用全部非平局比赛，是探索统计，不能用于独立验证。
原始变量图同时保留数值变量相关性、分类水平降序主胜率和分类独热向量 PCA；PCA 只描述分类组合方差，完整坐标存于 raw_feature_outcome.json。
特征存在相关性；系数和重要性不是因果效应。小样本区间较宽，不能声称模型显著优于另一模型。
数据已用于探索，后续根据此结果选模后，需要新赛季测试。
主客队只是数据的列举顺序，不保证真实场地优势。版本、转会、轮换与临场 BP 未建模。
BP 空值既可能为不适用，也可能为缺失；缺失率图没有将两者混为已确认的采集错误。

## 复现
安装 requirements.txt 中的 numpy、pandas。
在任意目录运行：python experiments/build_output.py（脚本路径按所在位置调整）。
脚本使用随包 CSV，重新生成 JSON、CSV、报告及七类离线 HTML 图表。
Excel 导出脚本为 experiments/build_workbook.mjs，需要 @oai/artifact-tool。
原始 match_prediction_experiment.py 是辅助算法模块，主入口 build_output.py 负责回合标签重建。
'''
    (ROOT/'experiments/研究报告.md').write_text(md,encoding='utf-8')
    (ROOT/'README.md').write_text('''# 2025 IVL 秋季赛 CSV 输出

打开 index.html 浏览七类图表，全部可离线使用。

- charts/：HTML 图表页面，包括 Logistic Regression 独立测试评估。
- chart_sources/：本次生成的相同 HTML 源文件，方便修改。
- Data/：原始 CSV 副本；Expanded/ 内有 Excel、整理后的 CSV 与 JSON。
- experiments/：可复现脚本、报告、逐场预测、指标、标签差异及特征解释。

仅使用本包 CSV；没有沿用参考包的多赛季数据或模型成绩。
大场优先按回合胜数、再按总分判定，尚未逐场核对官方赛果。
二分类模型评估排除平局，不提供三分类平局概率。
详细方法、限制与复现步骤见 experiments/研究报告.md。
''',encoding='utf-8')
    (ROOT/'requirements.txt').write_text('numpy>=1.24\npandas>=2.0\n',encoding='utf-8')

if __name__=='__main__': main()

