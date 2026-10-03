/* Offline tests for static rendering and data consistency. Run: node --test tests/test_site.cjs */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root,'docs/data.json')));
function app() {
  const nodes = new Map();
  const get = s => { if(!nodes.has(s)) nodes.set(s,{innerHTML:'',textContent:'',value:'',setAttribute(){},removeAttribute(){},addEventListener(){},focus(){}});return nodes.get(s); };
  const ctx = vm.createContext({document:{querySelector:get,querySelectorAll:()=>[],documentElement:{},getElementById:()=>null},localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){},scrollTo(){}},location:{hash:'#home'},fetch:()=>({then(){return this;},catch(){}}),fixture:data});
  vm.runInContext(fs.readFileSync(path.join(root,'docs/app.js'),'utf8'),ctx);
  vm.runInContext('D=fixture',ctx);
  return {ctx,nodes,run:s=>vm.runInContext(s,ctx)};
}
test('Profile totals, split counts and confusion matrices reconcile',()=>{
  assert.equal(data.seasons.length,12);
  for(const p of Object.values(data.profiles)) {
    assert.equal(p.outcomes.reduce((a,b)=>a+b),p.matches);
    assert.equal(p.halves.reduce((a,b)=>a+b),p.games);
    assert.equal(p.maps.reduce((a,b)=>a+b.n,0)+p.mapMissing,p.games);
  }
  assert.equal(data.raw.split.train.n+data.raw.split.validation.n+data.raw.split.test.n,1051);
  assert.equal(data.raw.test.confusion_matrix.flat().reduce((a,b)=>a+b),88);
  for(const key of ['baseline','logistic','catboost']) assert.equal(data.single[key].confusion_matrix.flat().reduce((a,b)=>a+b),98);
  assert.equal(data.palette.length,9);
  assert.equal(data.gradient.length,256);
});
test('All routes render in English and Chinese without invalid values',()=>{
  const a=app();
  for(const lang of ['en','zh']) for(const route of ['home','dataset','models']) {
    a.run(`lang='${lang}';location.hash='#${route}';render()`);
    const html=a.nodes.get('#content').innerHTML;
    assert.ok(html.length>3000,route);
    assert.doesNotMatch(html,/undefined|NaN|Infinity/);
    assert.match(html,/<h1>/);
    if(lang==='en') assert.doesNotMatch(html,/[\u4e00-\u9fff]/,'English content must not contain untranslated Chinese labels');
    const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
    assert.equal(new Set(ids).size,ids.length,'No duplicate IDs');
    for(const match of html.matchAll(/href="#models\/([^"]+)"/g)) assert.ok(ids.includes(match[1]),'Model link resolves');
  }
});
test('Every data control renders and home statistics remain unfiltered',()=>{
  const a=app();
  for(const s of Object.keys(data.profiles)) {a.run(`season='${s}';location.hash='#dataset';render()`);assert.doesNotMatch(a.nodes.get('#content').innerHTML,/undefined|NaN/);}
  for(let i=0;i<data.numeric.length;i++) {a.run(`numericIndex=${i};render()`);assert.doesNotMatch(a.nodes.get('#content').innerHTML,/undefined|NaN/);}
  for(let i=0;i<data.categorical.length;i++) {a.run(`categoryIndex=${i};render()`);assert.doesNotMatch(a.nodes.get('#content').innerHTML,/undefined|NaN/);}
  for(const w of [20,30,40]) {a.run(`warmup=${w};location.hash='#models';render()`);assert.ok(a.nodes.get('#content').innerHTML.includes('Bradley'))}
  a.run("season='2025-autumn';location.hash='#home';render()");
  assert.match(a.nodes.get('#content').innerHTML,/<strong>12<\/strong><span>Seasons/);
});
test('Plotted feature bins have valid confidence intervals and probabilities',()=>{
  for(const f of data.numeric) for(const b of f.bins){assert.ok(b.n>0);assert.ok(b.low>=0&&b.low<=b.win_rate&&b.high>=b.win_rate&&b.high<=1+1e-12);}
  const roc=data.raw.roc;
  for(let i=1;i<roc.length;i++) assert.ok(roc[i][0]>=roc[i-1][0]&&roc[i][1]>=roc[i-1][1]);
  for(const row of data.missing) assert.ok(row.values.every(v=>v>=0&&v<=1));
});
