'use strict';
let D, lang = 'en',
  season = 'all',
  numericIndex = 0,
  categoryIndex = 0,
  warmup = 30;
try {
  lang = localStorage.getItem('ivl-language') === 'zh' ? 'zh' : 'en';
} catch (_) {}
const $ = s => document.querySelector(s);
const t = (en, zh) => lang === 'zh' ? zh : en;
const esc = s => String(s).replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [c]));
const pct = (v, digits = 1) => v == null ? '—' : (v * 100).toFixed(digits) + '%';
const num = v => v == null ? '—' : Number(v).toFixed(3);
const count = v => Number(v).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US');
const dict = {
  'Home': '主队',
  'Away': '客队',
  'Elo': 'Elo',
  'career': '历史',
  'matches': '场次',
  'win rate': '胜率',
  'margin': '分差',
  'season': '赛季',
  'last-5': '近5场',
  'hunter': '监管者',
  'survivor': '求生者',
  'Prior H2H matches': '此前交手场次',
  'H2H': '交手',
  'rest days': '休息天数',
  'previous rank': '上赛季排名',
  'previous win rate': '上赛季胜率',
  'Home team': '主队',
  'Away team': '客队',
  'Season': '赛季',
  'Season split': '赛季类型',
  'Start time': '开赛时间',
  'Map': '地图',
  'Hunter character': '监管角色',
  'Trait': '辅助特质',
  'Map ban': '禁用地图',
  'Survivor ID': '求生者ID',
  'Decoding progress': '破译进度',
  'Rescues': '救援次数',
  'Kiting duration': '牵制时长',
  'Constant': '常数基线',
  'Raw Elo': '原始Elo',
  'Elo LR': 'Elo逻辑回归',
  'Full LR': '完整逻辑回归',
  'Raw-feature LR': '原始字段逻辑回归',
  'Historical win rate': '历史胜率',
  'Equal-weight ensemble': '等权集成',
  'Rolling logistic regression': '滚动逻辑回归',
  'Constant 0.5': '常数0.5',
  'Always draw': '始终预测平局',
  'Logistic regression': '逻辑回归',
  'Last-5 margin diff': '近5场分差之差',
  'H2H win rate': '交手胜率',
  'Elo diff': 'Elo差值',
  'Previous-rank edge': '上赛季排名优势',
  'Career margin diff': '历史分差之差',
  'Season win-rate diff': '赛季胜率差',
  'Hunter margin diff': '监管分差之差',
  'Survivor margin diff': '求生分差之差',
  'Rest-days diff': '休息天数差',
  'H2H margin': '交手分差',
  'Previous win-rate diff': '上赛季胜率差',
  'Last-5 win-rate diff': '近5场胜率差',
  'Career win-rate diff': '历史胜率差',
  'Experience diff': '经验差'
};

function label(s) {
  if (lang === 'en') return s;
  if (dict[s]) return dict[s];
  let out = s;
  Object.keys(dict).sort((a, b) => b.length - a.length).forEach(k => {
    out = out.replace(k, dict[k]);
  });
  return out;
}
const slabel = s => s === 'all' ? t('All seasons', '全部赛季') : s.replace('-summer', t(' Summer', ' 夏季赛')).replace('-autumn', t(' Autumn', ' 秋季赛'));
const colors = () => [D.palette[2], D.palette[4], D.palette[7]];
const svg = (body, h = 280, title = 'Chart', w = 560) => `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title>${body}</svg>`;
const txt = (x, y, s, anchor = 'start', cls = '') => `<text x="${x}" y="${y}" text-anchor="${anchor}" class="${cls}">${esc(s)}</text>`;
const line = (x1, y1, x2, y2, extra = '') => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="axis" ${extra}/>`;
const tip = s => `<title>${esc(s)}</title>`;
const legend = (items, palette = colors()) => `<div class="legend">${items.map((s,i)=>`<span><i style="background:${palette[i]}"></i>${esc(s)}</span>`).join('')}</div>`;
const heading = (title, sub = '') => `<div class="section-heading"><div><h2>${title}</h2>${sub?`<p>${sub}</p>`:''}</div></div>`;

function bars(rows, percent = false, maxValue = null) {
  const h = rows.length * 32 + 34,
    left = 155,
    width = 335,
    max = maxValue || Math.max(...rows.map(r => r.value), 1e-9);
  let b = '';
  [0, .25, .5, .75, 1].forEach(p => {
    b += line(left + width * p, 3, left + width * p, h - 26);
    b += txt(left + width * p, h - 6, percent ? pct(max * p, 0) : max < 1 ? (max * p).toFixed(2) : Math.round(max * p), 'middle');
  });
  rows.forEach((r, i) => {
    const y = 12 + i * 32,
      c = D.palette[Math.round(2 + 5 * (rows.length - 1 - i) / Math.max(rows.length - 1, 1))];
    b += txt(left - 12, y + 13, r.name, 'end');
    b += `<rect x="${left}" y="${y}" width="${Math.max(0,r.value/max*width)}" height="19" rx="3" fill="${c}" data-tip="1">${tip(`${r.name}: ${percent?pct(r.value):max<1?r.value.toFixed(3):count(r.value)}${r.n?' · n='+r.n:''}`)}</rect>`;
    b += txt(left + r.value / max * width + 8, y + 14, percent ? pct(r.value) : max < 1 ? r.value.toFixed(3) : count(r.value), 'start', 'value');
  });
  return svg(b, h, t('Ranked bar chart', '降序条形图'));
}

function donut(values, labels) {
  const total = values.reduce((a, b) => a + b, 0);
  let start = -Math.PI / 2,
    b = '';
  values.forEach((v, i) => {
    const angle = v / total * 2 * Math.PI,
      end = start + angle,
      x1 = 140 + 94 * Math.cos(start),
      y1 = 126 + 94 * Math.sin(start),
      x2 = 140 + 94 * Math.cos(end),
      y2 = 126 + 94 * Math.sin(end);
    if (v) b += `<path d="M140 126 L${x1} ${y1} A94 94 0 ${angle>Math.PI?1:0} 1 ${x2} ${y2} Z" fill="${colors()[i]}" stroke="white" stroke-width="3" data-tip="1">${tip(`${labels[i]}: ${v} (${pct(v/total)})`)}</path>`;
    start = end;
    b += `<circle cx="302" cy="${70+i*57}" r="5" fill="${colors()[i]}"/>` + txt(318, 74 + i * 57, labels[i]) + txt(318, 94 + i * 57, `${count(v)} · ${pct(v/total)}`, 'start', 'value');
  });
  b += '<circle cx="140" cy="126" r="66" fill="white"/>' + `<text x="140" y="125" text-anchor="middle" style="font-size:29px;fill:#242539">${count(total)}</text>` + txt(140, 147, t('observations', '条记录'), 'middle');
  return svg(b, 250, t('Outcome distribution', '赛果分布'));
}

function timeline() {
  let b = '';
  const left = 40,
    base = 225,
    max = 600,
    w = 480;
  [0, 200, 400, 600].forEach(v => {
    let y = base - v / max * 185;
    b += line(left, y, 530, y) + txt(30, y + 4, v, 'end');
  });
  D.seasons.forEach((s, i) => {
    const x = left + i * w / 12 + 9,
      hh = s.half_games / max * 185;
    b += `<rect x="${x}" y="${base-hh}" width="23" height="${hh}" rx="3" fill="${D.palette[i%2?6:3]}" data-tip="1">${tip(slabel(s.season_id)+': '+s.half_games)}</rect>`;
    b += `<text transform="translate(${x+9},241) rotate(-40)" text-anchor="end">${esc(slabel(s.season_id))}</text>`;
  });
  return svg(b, 310, t('Single games by season', '各赛季小局数'));
}

function heatmap() {
  let b = '';
  const left = 145,
    cw = 30,
    ch = 26;
  D.missingLabels.forEach((l, j) => {
    b += txt(left - 10, 34 + j * ch, label(l), 'end');
    D.missing.forEach((s, i) => {
      const v = s.values[j];
      b += `<rect x="${left+i*cw}" y="${18+j*ch}" width="27" height="23" rx="3" fill="${D.gradient[Math.round(v*255)]}" data-tip="1">${tip(`${slabel(s.season)} · ${label(l)}: ${pct(v)}`)}</rect>`;
    });
  });
  D.missing.forEach((s, i) => {
    b += `<text transform="translate(${left+i*cw+14},238) rotate(-45)" text-anchor="end">${esc(slabel(s.season))}</text>`;
  });
  return svg(b, 305, t('Missing values by season', '赛季缺失值比例'));
}

function winCurve(field) {
  let b = '';
  const left = 55,
    right = 520,
    top = 25,
    bottom = 222,
    bins = field.bins,
    min = Math.min(...bins.map(r => r.x)),
    max = Math.max(...bins.map(r => r.x));
  const x = v => left + (v - min) / (max - min || 1) * (right - left),
    y = v => bottom - v * (bottom - top);
  [0, .25, .5, .75, 1].forEach(v => {
    b += line(left, y(v), right, y(v)) + txt(left - 10, y(v) + 4, pct(v, 0), 'end');
  });
  b += `<polyline points="${bins.map(r=>`${x(r.x)},${y(r.win_rate)}`).join(' ')}" fill="none" stroke="${D.palette[3]}" stroke-width="2.5"/>`;
  bins.forEach(r => {
    b += `<line x1="${x(r.x)}" y1="${y(r.low)}" x2="${x(r.x)}" y2="${y(r.high)}" stroke="${D.palette[5]}" stroke-width="2"/><circle cx="${x(r.x)}" cy="${y(r.win_rate)}" r="5" fill="${D.palette[3]}" data-tip="1">${tip(`${r.x.toFixed(2)}: ${pct(r.win_rate)}; 95% CI ${pct(r.low)}–${pct(r.high)}; n=${r.n}`)}</circle>` + txt(x(r.x), 245, r.x.toFixed(Math.abs(r.x) < 10 ? 2 : 0), 'middle');
  });
  b += txt(290, 275, label(field.label), 'middle');
  return svg(b, 285, t('Home win rate with 95% Wilson intervals', '主队胜率与95% Wilson区间'));
}

function pca() {
  let b = '',
    ps = D.pca.points;
  const xmin = Math.min(...ps.map(p => p.x)),
    xmax = Math.max(...ps.map(p => p.x)),
    ymin = Math.min(...ps.map(p => p.y)),
    ymax = Math.max(...ps.map(p => p.y));
  const x = v => 45 + (v - xmin) / (xmax - xmin) * 470,
    y = v => 235 - (v - ymin) / (ymax - ymin) * 210;
  for (let i = 0; i <= 4; i++) {
    const xx = xmin + (xmax - xmin) * i / 4,
      yy = ymin + (ymax - ymin) * i / 4;
    b += line(x(xx), 20, x(xx), 235) + txt(x(xx), 254, xx.toFixed(1), 'middle') + line(45, y(yy), 515, y(yy)) + txt(36, y(yy) + 4, yy.toFixed(1), 'end');
  }
  ps.forEach(p => {
    b += `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="2.5" fill="${p.outcome==='Home win'?colors()[2]:colors()[0]}" opacity=".38" data-tip="1">${tip(lang==='en'?p.match+' · '+p.outcome:p.match.replace('Summer','夏季赛').replace('Autumn','秋季赛')+' · '+(p.outcome==='Home win'?'主胜':'客胜'))}</circle>`;
  });
  b += txt(280, 278, 'PC1 · ' + pct(D.pca.explained_variance[0]), 'middle');
  b += `<text x="10" y="140" transform="rotate(-90,10,140)" text-anchor="middle">PC2 · ${pct(D.pca.explained_variance[1])}</text>`;
  return svg(b, 290, t('Categorical PCA', '分类变量PCA'));
}

function roc() {
  let b = '';
  const x = v => 55 + 440 * v,
    y = v => 230 - 205 * v;
  [0, .25, .5, .75, 1].forEach(v => {
    b += line(x(0), y(v), x(1), y(v)) + txt(44, y(v) + 4, v.toFixed(2), 'end') + txt(x(v), 248, v.toFixed(2), 'middle');
  });
  b += `<path d="M${x(0)} ${y(0)} L${x(1)} ${y(1)}" stroke="#b5b5c5" stroke-dasharray="5 5"/>`;
  b += `<polyline points="${D.raw.roc.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}" fill="none" stroke="${D.palette[3]}" stroke-width="3"/>` + txt(78, 45, 'AUC ' + num(D.raw.test.roc_auc), 'start', 'value') + txt(275, 275, t('False positive rate', '假阳性率'), 'middle');
  b += `<text x="10" y="140" transform="rotate(-90,10,140)" text-anchor="middle">${t('True positive rate','真阳性率')}</text>`;
  return svg(b, 287, 'ROC');
}

function confusion(matrix, labels) {
  const n = labels.length,
    size = n === 2 ? 82 : 62,
    left = 170,
    top = 48,
    max = Math.max(...matrix.flat());
  let b = txt(left + n * size / 2, 18, t('Predicted', '预测值'), 'middle');
  labels.forEach((l, i) => {
    b += txt(left + i * size + size / 2, 39, l, 'middle') + txt(left - 14, top + i * size + size / 2 + 5, l, 'end');
    matrix[i].forEach((v, j) => {
      b += `<rect x="${left+j*size}" y="${top+i*size}" width="${size-3}" height="${size-3}" rx="5" fill="${D.gradient[Math.round(.18*255+v/max*.62*255)]}"/>` + `<text x="${left+j*size+size/2}" y="${top+i*size+size/2+6}" text-anchor="middle" style="font-size:21px;fill:${v/max>.55?'#1c2a34':'white'}">${v}</text>`;
    });
  });
  b += `<text transform="translate(55,145) rotate(-90)" text-anchor="middle">${t('Actual','实际值')}</text>`;
  return svg(b, 270, t('Confusion matrix; rows actual, columns predicted', '混淆矩阵：行是实际值，列是预测值'));
}

function stats(p, scope = season) {
  return `<div class="stats">${[[p.matches,t('Full matches','大场比赛')],[p.games,t('Single games','小局')],[p.teams,t('Normalized teams','归一化队伍')],[scope==='all'?12:1,t('Seasons','赛季')]].map(([n,l])=>`<div class="stat"><strong>${count(n)}</strong><span>${l}</span></div>`).join('')}</div>`;
}

function home() {
  return `<section class="hero"><div><p class="eyebrow">IDENTITY V · ESPORTS RESEARCH</p><h1>${t('Understand the game.<br><em>Measure the edge.</em>','理解比赛。<br><em>用数据检验预测。</em>')}</h1><p class="lead">${t('An open research project exploring what twelve seasons of Identity V competition can tell us about teams, match outcomes, and the limits of prediction.','一个探索第五人格职业赛事的研究项目：用十二个赛季的数据理解队伍、比赛结果，以及预测能力的边界。')}</p><div class="actions"><a class="button" href="#dataset">${t('Explore the data','探索数据')} ↗</a><a class="button secondary" href="#models">${t('Compare models','比较模型')} →</a></div></div><div class="hero-art"><p class="eyebrow">${t('ONE HUNTER. FOUR SURVIVORS.','一位监管者，四位求生者。')}</p><svg viewBox="0 0 450 255" role="img" aria-label="${t('One hunter facing four survivors','一位监管者面对四位求生者')}"><defs><linearGradient id="vline"><stop stop-color="${D.palette[2]}"/><stop offset="1" stop-color="${D.palette[7]}"/></linearGradient></defs>${[52,102,152,202].map(y=>`<path d="M105 127 C235 127 215 ${y} 337 ${y}" fill="none" stroke="url(#vline)" stroke-width="1.4"/><circle cx="345" cy="${y}" r="16" fill="${D.palette[7]}"/><circle cx="345" cy="${y}" r="5" fill="#171a31"/>`).join('')}<path d="M65 127 L100 84 L135 127 L100 170 Z" fill="${D.palette[3]}"/><path d="M87 128 L100 111 L113 128 L100 145 Z" fill="#e6e8f3"/><text x="100" y="219" fill="#cccfe3" text-anchor="middle" font-size="11">${t('HUNTER','监管者')}</text><text x="345" y="247" fill="#cccfe3" text-anchor="middle" font-size="11">${t('SURVIVORS','求生者')}</text></svg><div class="art-bottom"><span>2020 — 2025</span><span>${t('ASYMMETRIC BY DESIGN','非对称竞技')}</span></div></div></section>${stats(D.profiles.all,'all')}${heading(t('The game behind the data','数据背后的游戏'))}<div class="grid three"><article class="card"><div class="number">01</div><h3>${t('Asymmetric competition','非对称对抗')}</h3><p>${t('Identity V is NetEase’s asymmetric multiplayer game. Four survivors work together to decode cipher machines and escape, while one hunter tries to eliminate them. Maps, character abilities, and coordination shape each game.','第五人格是网易开发的非对称多人竞技游戏。四名求生者通过配合破译密码机并逃脱，一名监管者尝试将其淘汰。地图、角色技能和团队配合共同影响小局结果。')}</p></article><article class="card"><div class="number">02</div><h3>${t('Two levels of outcomes','两个层级的赛果')}</h3><p>${t('In a single game, three or more escapes are a survivor win, two are a draw, and one or none are a hunter win. A full esports match combines games played on both sides; its winner follows the applicable competition rules.','在一个小局中，三人及以上逃脱是求生者胜，两人逃脱是平局，一人或无人逃脱是监管者胜。职业赛事的大场包含双方交换阵营的小局，大场胜者按照对应赛事规则判定。')}</p></article><article class="card"><div class="number">03</div><h3>${t('Prediction, with evidence','以证据评估预测')}</h3><p>${t('We profile the data, build pre-match baselines, and test how much information team strength, recent form, and draft choices contain. Our goal is reproducible evaluation—not a claim of certain outcomes or causal effects.','我们分析数据分布，建立赛前预测基线，检验队伍实力、近期状态和BP选择所包含的信息。目标是可复现的评估，而不是保证预测结果或推断因果关系。')}</p></article></div>${heading(t('Three questions guide the project','项目的三个研究问题'))}<div class="grid"><article class="card"><h3>${t('What changes across seasons?','不同赛季有什么变化？')}</h3><p>${t('Track class balance, map usage, and field coverage before interpreting patterns. Missing early statistics and changing rules can distort comparisons.','先了解赛果平衡、地图使用和字段覆盖的变化，再解释数据规律。早期数据缺失与规则变更可能影响跨赛季比较。')}</p><h3>${t('Which signals help prediction?','哪些信号有助于预测？')}</h3><p>${t('Compare logistic regression, Elo, rolling models, and a tree-based model under clearly documented evaluation protocols.','在明确的评估协议下，比较逻辑回归、Elo、滚动模型和基于树的模型。')}</p></article><article class="card"><h3>${t('Can draft decisions be simulated?','能否模拟BP决策？')}</h3><p>${t('A trained conditional GAN now generates lineup alternatives from map, round, and supplied bans. Explore the BP / GAN page for the prototype and held-out evaluation. Complete sequential drafting still requires action logs and season-specific rules.','训练后的条件GAN可根据地图、轮次和给定禁用生成阵容备选。BP / GAN页面展示原型及留出集评估。完整逐步BP仍需动作日志和赛季规则。')}</p><a class="button secondary" href="#models">${t('Read methods and limitations','查看方法与局限')} →</a></article></div><p class="caption">${t('Game reference:','游戏资料：')} <a href="https://www.identityvgame.com/en/">Identity V ↗</a> · ${t('Independent research; not an official game or league service.','独立研究，非游戏或赛事官方服务。')}</p>`;
}

function dataset() {
  const p = D.profiles[season],
    f = D.numeric[numericIndex],
    cat = D.categorical[categoryIndex];
  return `<div class="page-head"><div><p class="eyebrow">01 / ${t('DATA EXPLORER','数据探索')}</p><h1>${t('The dataset','数据集')}</h1><p class="lead">${t('Twelve seasons. Two units of analysis. A closer look at what is—and is not—in the data.','十二个赛季，两个分析层级。了解数据包含什么，以及有哪些缺口。')}</p></div><label class="toolbar">${t('Season','赛季')}<select id="season">${Object.keys(D.profiles).map(s=>`<option value="${s}" ${s===season?'selected':''}>${slabel(s)}</option>`).join('')}</select></label></div>${stats(p)}<div class="note">${t('The season filter updates the four profile counts, outcome charts, and map chart. The timeline, coverage, and feature analyses use all seasons. The expanded corpus contains 1,080 standard regular-season matches plus 2 play-ins. Binary modeling uses 1,051 standard non-draw matches; 29 draws/unresolved outcomes and both play-ins are excluded.','赛季筛选会更新四项统计、赛果图和地图图。赛季趋势、缺失率及特征分析使用全赛季数据。扩充数据包含1,080场标准常规赛和2场附加赛。二分类建模使用1,051场非平局常规赛，排除29场平局/未决比赛及两场附加赛。')}</div><div class="grid"><article class="card"><h3>${t('Match outcomes','大场赛果')}</h3><p>${slabel(season)} · ${t('Listing-side perspective, not a home-venue advantage','主客队为数据列表标识，不代表主场场地优势')}</p>${donut(p.outcomes,[t('Away win','客队胜'),t('Draw / unresolved','平局 / 未决'),t('Home win','主队胜')])}</article><article class="card"><h3>${t('Game outcomes','小局赛果')}</h3><p>${slabel(season)} · ${t('A single hunter-versus-survivors game','一次监管者与求生者的对局')}</p>${donut(p.halves,[t('Survivor win','求生者胜'),t('Draw','平局'),t('Hunter win','监管者胜')])}</article><article class="card"><h3>${t('Maps','地图')}</h3><p>${t('Single-game appearances, sorted descending','小局出场次数，降序排列')}</p>${bars(p.maps.map(r=>({name:r[lang],value:r.n})))}<p class="caption">${p.mapMissing} ${t('games have no recorded map and are excluded from this chart.','个小局未记录地图，不计入此图。')}</p></article><article class="card"><h3>${t('Seasons','赛季')}</h3><p>${t('Single-game volume across all seasons','所有赛季的小局数量')}</p>${timeline()}${legend([t('Summer','夏季赛'),t('Autumn','秋季赛')],[D.palette[3],D.palette[6]])}</article><article class="card wide"><div class="chart-top"><div><h3>${t('Coverage','字段覆盖')}</h3><p>${t('Missing values by season; hover a cell for the exact percentage','各赛季缺失值比例；悬停查看准确比例')}</p></div><div class="small">0% <span class="palette" style="background:linear-gradient(90deg,${D.gradient.filter((_,i)=>i%25===0).join(',')})"></span> 100%</div></div><div style="max-width:780px;margin:auto">${heatmap()}</div><p class="caption">${t('Missingness includes null, blank, and −999 sentinels, not zero. A missing ban can mean “not applicable” under that season’s rules. Survivor statistics here use slot 1 as a coverage sample. In-game statistics are profiled but excluded from pre-match prediction.','缺失包含空值、空字符串和−999标记，不包含零。禁用字段缺失可能表示该赛季规则下“不适用”。求生者统计使用一号位展示覆盖情况。局内统计仅用于描述，不用于赛前预测。')}</p></article></div>${heading(t('Features and outcomes','特征与赛果'),t('All 1,051 standard non-draw matches. Exploratory relationships, not held-out model performance.','全部1,051场非平局常规赛。用于探索关联，不是测试集预测效果。'))}<div class="grid"><article class="card"><div class="chart-top"><h3>${t('Numeric features','数值特征')}</h3><select id="numeric" aria-label="${t('Numeric feature','数值特征')}">${D.numeric.map((r,i)=>`<option value="${i}" ${i===numericIndex?'selected':''}>${label(r.label)}</option>`).join('')}</select></div><p>${t('Home win rate by feature value','不同特征取值下的主队胜率')}</p>${winCurve(f)}<p class="caption">${t('Up to five equal-frequency bins. Points show bin means; intervals are 95% Wilson intervals. Ties can reduce the number of bins.','最多五个等频分箱；横轴为箱内特征均值，区间为95% Wilson区间。相同取值可能减少分箱数量。')} n = ${count(f.n)}</p></article><article class="card"><div class="chart-top"><h3>${t('Categories','分类特征')}</h3><select id="category" aria-label="${t('Categorical feature','分类特征')}">${D.categorical.map((r,i)=>`<option value="${i}" ${i===categoryIndex?'selected':''}>${label(r.label)}</option>`).join('')}</select></div><p>${t('Home win rate, sorted descending','主队胜率，降序排列')}</p>${bars(cat.levels.map(r=>({name:r.level==='summer'?t('Summer','夏季赛'):r.level==='autumn'?t('Autumn','秋季赛'):(lang==='zh'?r.level.replace('Summer','夏季赛').replace('Autumn','秋季赛'):r.level),value:r.win_rate,n:r.n})).sort((a,b)=>b.value-a.value),true,1)}<p class="caption">${t('Every rate uses the home-win target, including the “Away team” view. Team aliases are normalized; these are associations, not adjusted team-strength estimates.','所有分类均以主队获胜为目标，包括“客队”视角。队伍别名已归一化；这些是观察关联，不是调整后的队伍实力估计。')}</p></article><article class="card"><h3>${t('Categorical space','分类空间')}</h3><p>${t('PCA of one-hot team, season, and start-time vectors','队伍、赛季、开赛时间的独热向量PCA')}</p>${pca()}${legend([t('Away win','客队胜'),t('Home win','主队胜')],[colors()[0],colors()[2]])}<p class="caption">${t('The first two components explain 19.73% of variance. This is a descriptive projection fitted on all observations, not a feature transform used to score the test set. Overlapping points do not establish class separability.','前两个主成分解释19.73%的方差。该投影在全体数据上拟合，仅用于描述，不用于测试集预测。点的重叠或分离不代表模型可准确区分赛果。')}</p></article><article class="card"><h3>${t('Data dictionary','数据字典')}</h3><p>${t('The feature table has 65 fields, including metadata and targets—not 65 usable predictors.','特征表有65列，包含元数据和目标，不等于65个可用预测变量。')}</p>${[[t('Context','背景'),t('Season, date, start time, match ID, team identities','赛季、日期、开赛时间、比赛ID、队伍')],[t('Pre-match history','赛前历史'),t('Elo, career/season form, last-five form, faction margins, head-to-head, rest, previous-season rank','Elo、历史/赛季状态、近五场状态、阵营分差、交手记录、休息天数、上赛季排名')],[t('Single-game fields','小局字段'),t('107 fields: map, players, characters, ban/pick slots, scores and in-game statistics','107列：地图、选手、角色、BP位置、比分及局内统计')],[t('Excluded from prediction','预测时排除'),t('Current scores, outcome, round wins, deciding rule, MVP, and current-game performance','当前比分、赛果、回合胜数、判胜规则、MVP及当前局内表现')]].map(([a,b])=>`<details open><summary>${a}</summary><p>${b}</p></details>`).join('')}</article></div>${heading(t('Provenance and limitations','来源与局限'))}<div class="card"><p>${t('Snapshot prepared on 25 August 2026, covering 2020 Summer–2025 Autumn. Public community-maintained records may contain entry errors and sparse early statistics. No duplicate match IDs or game IDs were detected in the prepared snapshot. Source-provided zeros may still encode unreported statistics.','数据快照于2026年8月25日整理，覆盖2020夏季赛至2025秋季赛。公开社区数据可能存在录入错误及早期统计缺失。整理后的快照未检测到重复的大场或小局ID，但源数据中的零值仍可能表示未记录统计。')}</p><p>${t('Alias mapping joins CPG→ACT, Tianba/JHS/Reborn→TE, and XROCK/YS→GW. This represents assumed organizational continuity, not unchanged rosters. The original single-season CSV and expanded source disagree on some reconstructed full-match outcomes; do not silently combine their benchmarks.','别名映射：CPG→ACT，Tianba/JHS/Reborn→TE，XROCK/YS→GW。此映射假定组织延续，不代表选手阵容不变。原始单赛季CSV与扩充源重建的大场赛果存在部分差异，不能直接合并其评估结果。')}</p><ul class="source-list">${D.manifest.public_data_sources.map(s=>`<li><a href="${s.url}">${esc(s.file)} ↗</a> <span class="mono">SHA-256 ${s.sha256.slice(0,12)}…</span></li>`).join('')}<li><a href="https://wiki.biligame.com/dwrg/2025_IVL_%E7%A7%8B%E5%AD%A3%E8%B5%9B">${t('2025 Autumn competition reference','2025秋季赛赛事资料')} ↗</a></li><li><a href="https://cmasher.readthedocs.io/user/cmap_overviews/cmr_cmaps.html">CMasher · voltage ↗</a></li></ul><p class="caption">${t('Charts are locally rendered SVGs with sampled cmr.voltage colors. No live remote dataset or chart CDN is required. Full provenance hashes are available in the downloadable JSON.','图表使用cmr.voltage采样颜色在本地绘制SVG，不依赖实时远端数据或图表CDN。完整来源哈希可在下载的JSON中查看。')}</p></div>`;
}

function metricsTable(rows, {
  auc = true,
  balanced = true
} = {}) {
  return `<div class="table-wrap"><table><thead><tr><th>${t('Method','方法')}</th><th>${t('Configuration','参数配置')}</th><th>n</th><th>${t('Accuracy','准确率')}</th>${balanced?`<th>${t('Balanced acc.','平衡准确率')}</th><th>Macro F1</th>`:''}<th>Log loss ↓</th>${auc?'<th>ROC AUC ↑</th>':''}</tr></thead><tbody>${rows.map(r=>`<tr><td class="model-name">${r.id?`<a href="#models/${r.id}">${label(r.name)}</a>`:label(r.name)}</td><td class="wrap">${r.config}</td><td>${r.n}</td><td>${pct(r.m.accuracy)}</td>${balanced?`<td>${pct(r.m.balanced_accuracy)}</td><td>${num(r.m.macro_f1)}</td>`:''}<td>${num(r.m.log_loss)}</td>${auc?`<td>${num(r.m.roc_auc)}</td>`:''}</tr>`).join('')}</tbody></table></div>`;
}

function method(id, index, title, formula, body, result, detail) {
  return `<article class="card method" id="${id}"><div class="method-head"><span class="method-index">${index}</span><h2>${title}</h2></div><div class="method-grid"><div><div class="formula">${formula}</div><p>${body}</p></div><div class="result"><strong>${result}</strong><span>${detail}</span></div></div></article>`;
}

function tuning() {
  const groups = [
    [t('Raw-feature LR', '原始字段逻辑回归'), D.raw.model.validation_balanced_log_loss, D.raw.model.ridge, t('Validation balanced log loss', '验证集平衡对数损失')],
    ['Elo LR', D.multi.elo_ridge_cv_log_loss, D.multi.elo_selected_ridge, t('Forward CV log loss', '前向验证对数损失')],
    ['Full LR', D.multi.ridge_cv_log_loss, D.multi.selected_ridge, t('Forward CV log loss', '前向验证对数损失')]
  ];
  return `<div class="table-wrap"><table><thead><tr><th>${t('Model','模型')}</th><th>λ</th><th>${t('Validation metric','验证指标')}</th><th>${t('Score ↓','分数 ↓')}</th><th>${t('Selection','选择')}</th></tr></thead><tbody>${groups.map(([name,scores,best,metric])=>Object.entries(scores).map(([k,v])=>`<tr class="${Number(k)===best?'selected':''}"><td>${label(name)}</td><td>${k}</td><td>${metric}</td><td>${v.toFixed(4)}</td><td>${Number(k)===best?t('Selected','已选择'):'—'}</td></tr>`).join('')).join('')}</tbody></table></div>`;
}

function models() {
  const names = ['Constant', 'Raw Elo', 'Elo LR', 'Full LR'],
    ids = ['constant', 'elo', 'elo-lr', 'full-lr'];
  const configs = [t('Training home-win frequency; threshold 0.5', '训练集主胜频率；阈值0.5'), 'K = 28; ' + t('season retention 0.75', '跨季保留0.75'), 'λ = 0.1; ' + t('1 standardized feature', '1个标准化特征'), 'λ = 30; ' + t('14 standardized features', '14个标准化特征')];
  return `<div class="page-head"><div><p class="eyebrow">02 / ${t('PREDICTION BENCHMARKS','预测评估')}</p><h1>${t('Methods and results','方法与结果')}</h1><p class="lead">${t('Start with the comparison. Then inspect the assumptions, equations, and evidence behind each method.','先比较结果，再检查每种方法的假设、公式和证据。')}</p></div></div><div class="note">${t('These are recorded experiments, not a newly standardized model sweep. Compare methods within the same protocol. Full-match binary accuracy and single-game three-class accuracy measure different tasks. “—” means the metric was not recorded; it is not zero.','以下展示已有实验，并非重新统一训练的模型搜索。请在同一评估协议内比较方法。大场二分类与小局三分类准确率衡量不同任务。“—”表示未记录该指标，不是零。')}</div>${heading(t('Overview','总览'),t('Test-set results; hyperparameter trials are reported separately below. Scroll tables horizontally on smaller screens.','测试集结果；超参数试验的验证集指标另列于下方。小屏幕可横向滚动表格。'))}<h3>${t('A · Full-match winner, 12-season dataset','A · 12赛季数据的大场胜负')}</h3><p class="small">${t('Same 88 held-out matches from 2025 Autumn. Raw-feature LR uses a fixed validation split; Elo LR and Full LR use forward-season validation. All fitted LR models are refit on the 963 pre-test matches after selection.','相同的88场2025秋季赛测试比赛。原始字段LR使用固定验证集；Elo LR与完整LR使用前向赛季验证。参数选择后，LR模型在963场测试赛季之前的比赛上重新拟合。')}</p>${metricsTable([{name:'Raw-feature LR',id:'raw-lr',config:'λ = 30; '+t('balanced; threshold 0.568','类别平衡；阈值0.568'),n:88,m:D.raw.test},...names.map((name,i)=>({name,id:ids[i],config:configs[i],n:88,m:D.multi.metrics[name]}))])}<h3>${t('B · Single-game outcome, 2025 Autumn CSV','B · 2025秋季赛CSV的小局赛果')}</h3><p class="small">${t('Survivor win / draw / hunter win. Chronological group holdout: 388 training games, 98 test games (18 full matches). This is not the binary benchmark above.','求生者胜 / 平局 / 监管者胜。按大场分组的时间留出：388个训练小局，98个测试小局（18个大场）。与上方二分类评估不同。')}</p>${metricsTable([{name:'Always draw',id:'dummy',config:t('ε = 10⁻⁶ probability smoothing','ε = 10⁻⁶概率平滑'),n:98,m:D.single.baseline},{name:'Logistic regression',id:'multinomial',config:'C = 0.35; L2; '+t('balanced','类别平衡'),n:98,m:D.single.logistic},{name:'CatBoost',id:'catboost',config:t('depth 5; rate 0.035; L2 8; early stopping','深度5；学习率0.035；L2=8；早停'),n:98,m:D.single.catboost}],{auc:false})}<h3>${t('C · Walk-forward winner, original 90-match CSV','C · 原始90场CSV的大场滚动预测')}</h3><div class="toolbar"><label for="warmup">${t('Warm-up matches','预热比赛数')}</label><select id="warmup">${[20,30,40].map(n=>`<option ${warmup===n?'selected':''}>${n}</option>`).join('')}</select></div><p class="small">${t('Each prediction uses only prior matches. Changing warm-up changes the test population, so it is not a controlled hyperparameter comparison. These outcomes were reconstructed separately from the expanded dataset.','每次预测仅使用此前比赛。改变预热长度也会改变测试样本，因此不是控制变量下的超参数比较。这里的大场赛果与扩充数据分别重建。')}</p>${metricsTable(D.history.filter(r=>r.warmup===warmup).map(r=>({name:r.method,id:r.method==='Bradley-Terry'?'bt':r.method==='Historical win rate'?'history':r.method==='Rolling logistic regression'?'rolling':r.method==='Equal-weight ensemble'?'ensemble':r.method==='Elo'?'rolling-elo':'rolling-constant',config:t('Warm-up ','预热 ')+warmup,n:r.n_non_draw_test,m:r})),{auc:false,balanced:false})}${heading(t('Evaluation protocol','评估协议'))}<div class="card"><h3>${t('Raw-feature baseline split','原始字段基线划分')}</h3><div class="split"><div style="flex:789;background:${D.palette[2]}"><strong>789</strong>${t('Training','训练集')}<span>2020 ${t('Summer','夏季赛')} — 2024 ${t('Summer','夏季赛')}</span></div><div style="flex:240;background:${D.palette[4]}"><strong>174</strong>${t('Validation','验证集')}<span>2024 ${t('Autumn','秋季赛')} — 2025 ${t('Summer','夏季赛')}</span></div><div style="flex:150;background:${D.palette[7]}"><strong>88</strong>${t('Test','测试集')}<span>2025 ${t('Autumn','秋季赛')}</span></div></div><p class="caption">${t('Block widths are schematic. Training fits imputers, scalers, category vocabularies, and weights. Validation selects λ and a threshold from 0.25–0.75 (step 0.001). The selected pipeline is refit on training + validation; the threshold remains fixed. All “prior” features are computed before each match. Test-season history updates after completed matches, so evaluation is sequential pre-match prediction, not a forecast of the entire season at once.','区块宽度为示意。训练集拟合填充值、标准化、分类词表及权重；验证集选择λ与0.25–0.75范围内的阈值（步长0.001）。选择后在训练+验证集重新拟合，阈值保持固定。所有prior特征在赛前计算，测试赛季的历史状态会在比赛结束后更新，因此这是逐场赛前预测，而非赛季开始时一次性预测整个赛季。')}</p><div class="formula">${t('Balanced accuracy','平衡准确率')} = (TPR + TNR) / 2 &nbsp; · &nbsp; Macro F1 = (F1<sub>home</sub> + F1<sub>away</sub>) / 2</div><p>${t('Accuracy reflects overall correctness. Balanced accuracy gives each class equal recall weight; macro F1 averages class-specific F1. ROC AUC measures ranking across thresholds. Log loss evaluates probability quality and penalizes confident errors. There are 39 away wins and 49 home wins in this test set.','准确率衡量总体预测正确率；平衡准确率对各类召回率等权；Macro F1对各类F1等权。ROC AUC衡量不同阈值下的排序能力，Log loss评估概率质量并惩罚自信的错误。测试集包含39场客胜与49场主胜。')}</p></div><div class="grid" style="margin-top:22px"><article class="card"><h3>${t('Confusion','混淆矩阵')}</h3><p>${t('Raw-feature LR · threshold 0.568','原始字段LR · 阈值0.568')}</p>${confusion(D.raw.test.confusion_matrix,[t('Away','客胜'),t('Home','主胜')])}</article><article class="card"><h3>ROC</h3><p>${t('Raw-feature LR · home win is the positive class','原始字段LR · 主胜为正类')}</p>${roc()}</article></div>${heading(t('Hyperparameters','超参数'),t('Validation scores only. Lower is better. λ uses a sum-loss objective and is not interchangeable with sklearn C.','仅展示验证分数，越低越好。λ对应求和损失，不能直接与sklearn的C互换。'))}${tuning()}<p class="caption">${t('Forward validation holds out 2024 Summer, 2024 Autumn, and 2025 Summer in turn, using only preceding seasons for training. The displayed score is the mean of the three season losses. The raw-feature model selects λ by class-balanced validation log loss on its fixed 174-match validation set.','前向验证依次留出2024夏季赛、2024秋季赛及2025夏季赛，每次仅使用之前的赛季训练。展示三次赛季损失的均值。原始字段模型以固定174场验证集上的类别平衡对数损失选择λ。')}</p>${heading(t('The methods','方法详解'))}<nav class="method-links" aria-label="${t('Method navigation','方法导航')}">${[['raw-lr','Raw-feature LR'],['constant','Constant'],['elo','Raw Elo'],['elo-lr','Elo LR'],['full-lr','Full LR'],['dummy','Always draw'],['multinomial','Logistic regression'],['catboost','CatBoost'],['history','Historical win rate'],['bt','Bradley–Terry'],['rolling','Rolling logistic regression'],['ensemble','Equal-weight ensemble'],['rolling-elo','Elo'],['rolling-constant','Constant 0.5']].map(([id,name])=>`<a href="#models/${id}">${label(name)}</a>`).join('')}</nav>${method('raw-lr','01',t('Raw-feature logistic regression','原始字段逻辑回归'),'p(y=1 | x) = σ(β₀ + βᵀx), &nbsp; σ(z) = 1 / (1 + e<sup>−z</sup>)<br>L = −Σᵢ wᵢ[yᵢ log pᵢ + (1−yᵢ) log(1−pᵢ)] + (λ/2)‖β‖²',t('29 numerical fields and 4 categorical fields. Numerical values are median-imputed and standardized; categories are one-hot encoded, with unseen categories mapped to all zeros. Class weights are N/(2Nclass); the intercept is not penalized. “Raw” means original columns of the expanded feature table: many are already engineered historical statistics, not untouched game logs.','29个数值字段与4个分类字段。数值使用中位数填补并标准化；分类使用独热编码，未知类别映射为全零。类别权重为N/(2Nclass)，截距不惩罚。“原始”指扩充特征表中的现有列，许多列已是历史统计特征，并非未经处理的对局日志。'),pct(D.raw.test.balanced_accuracy),t('Balanced accuracy · Accuracy 75.0% · Macro F1 0.750 · AUC 0.812. λ=30 and threshold=0.568 were selected on validation.','平衡准确率 · 准确率75.0% · Macro F1 0.750 · AUC 0.812。λ=30和阈值0.568由验证集选择。'))}${method('constant','02',t('Constant baseline','常数基线'),'p(home win) = N<sub>home wins, train</sub> / N<sub>train</sub>',t('Use the pre-test training home-win frequency for every test match. With a 0.5 threshold, this predicts the majority training class. It provides a probability baseline before introducing team or form information.','使用测试前训练集的主胜频率作为每场测试比赛的预测概率，阈值0.5时预测训练集多数类。用于检验加入队伍或状态信息前的概率基线。'),pct(D.multi.metrics.Constant.accuracy),t('Accuracy · Log loss 0.689 · AUC 0.500. Ranking is no better than chance.','准确率 · Log loss 0.689 · AUC 0.500，排序不优于随机。'))}${method('elo','03',t('Elo rating','Elo评分'),'p = 1 / (1 + 10<sup>(R<sub>away</sub>−R<sub>home</sub>)/400</sup>)<br>R′ = R + K(s−p)',t('Start at 1500, update with K=28 after each match, and retain 75% of the deviation from 1500 at a season boundary. A draw contributes s=0.5 to rating history, but draws are excluded from binary test scoring. This raw probability is not fitted by logistic regression.','初始分1500，每场结束后以K=28更新，跨赛季保留相对1500偏差的75%。平局以s=0.5更新历史评分，但二分类测试排除平局。原始Elo概率不经过逻辑回归拟合。'),pct(D.multi.metrics['Raw Elo'].accuracy),t('Accuracy · Log loss 0.559 · AUC 0.819.','准确率 · Log loss 0.559 · AUC 0.819。'))}${method('elo-lr','04',t('Elo logistic regression','Elo逻辑回归'),'p = σ(β₀ + β₁ · standardize(R<sub>home</sub>−R<sub>away</sub>))',t('Fit a regularized logistic link to just the pre-match Elo difference. The fitted intercept and slope adjust how rating differences translate to win probabilities. Forward validation selects λ=0.1; the decision threshold is 0.5.','仅用赛前Elo差值拟合带正则化的逻辑回归，通过截距和斜率调整评分差与胜率的映射。前向验证选择λ=0.1，预测阈值为0.5。'),pct(D.multi.metrics['Elo LR'].accuracy),t('Accuracy · Log loss 0.543 · AUC 0.819. Best recorded log loss in protocol A; not proof of universal superiority.','准确率 · Log loss 0.543 · AUC 0.819。协议A中记录的最低对数损失，不代表普遍最优。'))}${method('full-lr','05',t('Multi-feature logistic regression','多特征逻辑回归'),'p = σ(β₀ + Σⱼ₌₁¹⁴ βⱼzⱼ), &nbsp; L = BCE<sub>sum</sub> + (λ/2)‖β‖²',t('Use 14 historical difference features: Elo, career/season form, last-five form, faction performance, head-to-head, rest, prior-season rank and experience. Median-impute, standardize, and select λ=30 with forward validation. No class weighting; threshold 0.5. Correlated predictors share coefficient weight.','使用14个历史差值特征：Elo、历史/赛季状态、近五场状态、阵营表现、交手、休息、上季排名和经验。中位数填补并标准化，前向验证选择λ=30。不使用类别权重，阈值0.5。相关特征会分摊系数权重。'),pct(D.multi.metrics['Full LR'].accuracy),t('Accuracy · Log loss 0.561 · AUC 0.816. Extra features did not improve on Elo LR in this test season.','准确率 · Log loss 0.561 · AUC 0.816。在该测试赛季，增加特征未优于Elo LR。'))}<div class="grid" style="margin-top:22px"><article class="card"><h3>${t('Coefficients','系数')}</h3><p>${t('Full LR · signed standardized coefficients','完整LR · 带符号的标准化系数')}</p>${coefficientChart()}<p class="caption">${t('Positive values increase home-win probability. Magnitude is not causal importance.','正值提高主胜概率，大小不代表因果贡献。')}</p></article><article class="card"><h3>${t('Permutation','置换重要性')}</h3><p>${t('Full LR · increase in test log loss after shuffling','完整LR · 打乱特征后的测试对数损失增量')}</p>${bars(D.multi.permutation_importance.filter(r=>r.delta_log_loss>0).slice(0,8).map(r=>({name:label(r.label),value:r.delta_log_loss})),false,.04).replace(/>0<\/text>/g,'>0</text>')}<p class="caption">${t('300 shuffles per feature; top 8 positive means shown. Test-set diagnostic only, not validation evidence for model selection. Negative effects in other features can reflect noise or redundancy.','每个特征打乱300次，显示正增量均值前8项。仅作为测试集诊断，不能作为模型选择的验证证据。其他特征的负增量可能反映噪声或冗余。')}</p></article></div>${method('dummy','06',t('Always-draw baseline','始终平局基线'),'P(draw) = 1−2ε, &nbsp; P(other class) = ε, &nbsp; ε = 10<sup>−6</sup>',t('Always predict the majority single-game outcome: a draw. Very small probabilities assigned to other classes keep log loss finite but heavily penalize errors.','始终预测小局多数类“平局”。其余两类分配极小概率以保持对数损失有限，但错误预测会受到很大惩罚。'),pct(D.single.baseline.accuracy),t('Accuracy · Balanced accuracy 33.3% · Log loss 7.613. A high majority-class accuracy hides failure on both win classes.','准确率 · 平衡准确率33.3% · Log loss 7.613。较高的多数类准确率掩盖了对两种获胜类别的完全失效。'))}${method('multinomial','07',t('Multinomial logistic regression','多项逻辑回归'),'P(y=k | x) = exp(β<sub>k</sub>ᵀx) / Σⱼ exp(β<sub>j</sub>ᵀx)',t('Predict survivor win, draw, or hunter win using pre-game map, teams, players, characters and available BP/context fields. One-hot encoding groups rare categories (minimum frequency 2); numeric fields are standardized. L2, C=0.35, balanced class weights, lbfgs, maximum 3000 iterations.','用赛前地图、队伍、选手、角色及可用BP/背景字段预测求生胜、平局或监管胜。独热编码合并低频类别（最小频次2），数值字段标准化。L2正则，C=0.35，类别平衡权重，lbfgs优化器，最多3000次迭代。'),pct(D.single.logistic.balanced_accuracy),t('Balanced accuracy · Accuracy 36.7% · Macro F1 0.330 · Log loss 1.342.','平衡准确率 · 准确率36.7% · Macro F1 0.330 · Log loss 1.342。'))}${method('catboost','08','CatBoost','F<sub>M</sub>(x) = Σₘ ηhₘ(x), &nbsp; P(y=k) = softmax(F(x))',t('Gradient-boosted trees capture nonlinear interactions and handle categorical inputs natively. Depth 5, learning rate 0.035, L2 leaf penalty 8, balanced classes, seed 42. A 600-iteration cap and 100-round early stopping use the latest 15% of the training groups; the selected tree count is refit on all training games (minimum 50). The exact final count was not saved in metrics.json. Five-fold GroupKFold comparison is not rolling time validation.','梯度提升树捕捉非线性交互并原生处理分类输入。深度5、学习率0.035、叶子L2惩罚8、类别平衡、种子42。最多600轮，用训练大场中最后15%早停（耐心100轮），再按选择轮数在全部训练小局拟合（至少50轮）。metrics.json未保存最终确切轮数。五折GroupKFold比较不是滚动时间验证。'),pct(D.single.catboost.balanced_accuracy),t('Balanced accuracy · Accuracy 41.8% · Macro F1 0.404 · Log loss 1.079. The grouped CV selection chose CatBoost, but its test accuracy remains below always-draw.','平衡准确率 · 准确率41.8% · Macro F1 0.404 · Log loss 1.079。分组交叉验证选择CatBoost，但测试准确率仍低于始终平局基线。'))}<div class="card" style="margin-top:22px"><h3>${t('CatBoost confusion','CatBoost混淆矩阵')}</h3>${confusion(D.single.catboost.confusion_matrix,[t('Survivor','求生胜'),t('Draw','平局'),t('Hunter','监管胜')])}</div>${historyMethods()}${heading(t('What comes next','下一步研究'))}<div class="grid three">${[[t('Controlled model search','统一模型搜索'),t('Use identical folds and features for LR, boosted trees and hyperparameter grids. Add uncertainty across held-out seasons and calibration metrics before declaring a winner.','在一致的特征和划分上比较LR、提升树及参数网格。增加跨赛季不确定性与校准指标，再判断模型优劣。')],[t('Time-aware forecasting','时间序列预测'),t('Model season drift, roster changes, and exponentially weighted form. Compare expanding-window and rolling-window evaluation without accessing future results.','建模赛季漂移、阵容变化与指数加权状态，在不访问未来结果的前提下比较扩展窗口和滚动窗口。')],[t('BP simulation','BP模拟'),t('Extend the BP / GAN lineup-completion prototype with season-specific availability and sequential ban/pick actions. Validate joint and conditional quality; generated alternatives are not evidence of win-rate improvements.','在BP / GAN阵容补全原型上增加赛季角色可用性及逐步禁选动作。验证联合及条件质量；生成备选阵容不代表胜率提升。')]].map(([a,b])=>`<article class="card"><h3>${a}</h3><p>${b}</p></article>`).join('')}</div>`;
}

function coefficientChart() {
  const rows = D.multi.coefficients,
    h = rows.length * 28 + 36,
    left = 305,
    scale = 380,
    max = .35;
  let b = line(left, 0, left, h - 25);
  rows.forEach((r, i) => {
    let v = r.coefficient,
      y = 8 + i * 28;
    b += txt(200, y + 13, label(r.label), 'end');
    b += `<rect x="${v>=0?left:left+v*scale}" y="${y}" width="${Math.abs(v)*scale}" height="18" rx="2" fill="${v>=0?D.palette[6]:D.palette[2]}"/>` + txt(470, y + 13, (v > 0 ? '+' : '') + v.toFixed(3), 'end', 'value');
  });
  return svg(b, h, t('Signed coefficients', '带符号系数'));
}

function historyMethods() {
  const r = n => D.history.find(x => x.warmup === 30 && x.method === n);
  const result = n => pct(r(n).accuracy);
  const info = n => t('30-match warm-up · 59 non-draw tests · Log loss ', '30场预热 · 59场非平局测试 · Log loss ') + num(r(n).log_loss);
  return method('history', '09', t('Historical win rate', '历史胜率'), 'q = (points + 2) / (matches + 4), &nbsp; p = σ(3(q<sub>home</sub>−q<sub>away</sub>))', t('Maintain smoothed historical result rates (a draw adds half a point). Convert the difference to a home-win probability with a fixed sigmoid scale of 3. Update only after the current match finishes.', '维护平滑的历史赛果积分率（平局计半分），以固定尺度3的sigmoid将两队差异转为主胜概率，仅在比赛结束后更新状态。'), result('Historical win rate'), info('Historical win rate')) + method('bt', '10', 'Bradley–Terry', 'p(home win) = σ(b + θ<sub>home</sub> − θ<sub>away</sub>)', t('Fit latent team strengths and a listing-side intercept to previous match outcomes, using ridge λ=2. Begin fitting after 12 past matches; earlier probabilities default to 0.5. Refit as history grows.', '基于此前赛果拟合队伍潜在实力和主客列表截距，岭惩罚λ=2。至少12场历史比赛后开始拟合，此前默认概率0.5。随历史增加重新拟合。'), result('Bradley-Terry'), info('Bradley-Terry')) + method('rolling', '11', t('Rolling logistic regression', '滚动逻辑回归'), 'p<sub>t</sub> = σ(β₀,<sub>t</sub> + β<sub>t</sub>ᵀx<sub>t</sub>)', t('Seven prior-state differences combine Elo, win rate, overall margin, recent margin, hunter margin, survivor margin, and head-to-head margin. Fit after 20 prior matches, with fixed scale factors and ridge λ=2. This is sequential state modeling, not an ARIMA model.', '七个历史状态差值包括Elo、胜率、总分差、近期分差、监管分差、求生分差及交手分差。至少20场历史比赛后拟合，使用固定缩放与λ=2。这是时序状态建模，不是ARIMA模型。'), result('Rolling logistic regression'), info('Rolling logistic regression')) + method('ensemble', '12', t('Equal-weight ensemble', '等权集成'), 'p = (p<sub>Elo</sub> + p<sub>BT</sub> + p<sub>rolling LR</sub>) / 3', t('Average three available pre-match probabilities. The equal weights are fixed rather than optimized on the held-out matches.', '平均三种赛前概率，固定等权，不使用测试结果优化权重。'), result('Equal-weight ensemble'), info('Equal-weight ensemble')) + method('rolling-elo', '13', t('Single-season Elo', '单赛季Elo'), 'p = 1 / (1 + 10<sup>(R<sub>away</sub>−R<sub>home</sub>)/400</sup>), &nbsp; K=28', t('The same Elo update within the original single season, starting all teams at 1500. Unlike the multi-season experiment, this has no inherited cross-season rating history.', '在原始单赛季数据内使用Elo更新，所有队伍从1500起步。与多赛季实验不同，没有跨赛季继承评分。'), result('Elo'), info('Elo')) + method('rolling-constant', '14', t('Constant 0.5', '常数0.5'), 'p(home win) = 0.5', t('An uninformed probability baseline. At a 0.5 decision threshold, ties in probability are classified as home wins. This differs from the learned training-frequency constant in protocol A.', '无信息概率基线。预测阈值为0.5时，概率相等判为主胜。与协议A中根据训练频率得到的常数不同。'), result('Constant 0.5'), info('Constant 0.5'));
}

function render() {
  const page = location.hash.slice(1).split('/')[0] || 'home';
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.title = t('Identity V · Research', '第五人格 · 赛事研究');
  $('#language').value = lang;
  $('#language').setAttribute('aria-label', t('Language', '语言'));
  document.querySelectorAll('[data-nav]').forEach(a => {
    a.textContent = ({
      home: t('Project', '项目'),
      dataset: t('Dataset', '数据集'),
      models: t('Models', '模型')
    })[a.dataset.nav];
    a.classList.toggle('active', a.dataset.nav === page);
    if (a.dataset.nav === page) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  $('#footer-text').textContent = t('Independent research · Not affiliated with NetEase', '独立研究 · 非网易官方项目');
  $('#bp-link').textContent = t('BP / GAN', 'BP / GAN');
  $('.skip').textContent = t('Skip to content', '跳转至正文');
  $('nav').setAttribute('aria-label', t('Main navigation', '主导航'));
  $('#content').innerHTML = page === 'dataset' ? dataset() : page === 'models' ? models() : home();
  [
    ['season', v => season = v],
    ['numeric', v => numericIndex = Number(v)],
    ['category', v => categoryIndex = Number(v)],
    ['warmup', v => warmup = Number(v)]
  ].forEach(([id, fn]) => {
    const el = $('#' + id);
    if (el) el.addEventListener('change', () => {
      const scroll = window.scrollY;
      fn(el.value);
      render();
      window.scrollTo(0, scroll);
      $('#' + id)?.focus({
        preventScroll: true
      });
    });
  });
}
$('#language').addEventListener('change', e => {
  lang = e.target.value;
  try {
    localStorage.setItem('ivl-language', lang);
  } catch (_) {}
  render();
});
$('.skip').addEventListener('click', e => {
  e.preventDefault();
  $('#content').focus();
  $('#content').scrollIntoView();
});
window.addEventListener('hashchange', () => {
  render();
  const id = location.hash.split('/')[1];
  if (id) document.getElementById(id)?.scrollIntoView();
  else window.scrollTo(0, 0);
});
fetch('data.json').then(r => {
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}).then(data => {
  D = data;
  render();
  const id = location.hash.split('/')[1];
  if (id) document.getElementById(id)?.scrollIntoView();
}).catch(e => {
  $('#content').innerHTML = `<div class="note"><h2>${t('Data could not be loaded','数据加载失败')}</h2><p>${t('Serve this directory over HTTP and reload the page.','请通过HTTP服务打开此目录并刷新页面。')} ${esc(e.message)}</p><a href="data.json">JSON</a></div>`;
});
