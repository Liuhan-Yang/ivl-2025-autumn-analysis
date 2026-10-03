const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const engine=require('../docs/bp-engine.js');
const root=path.resolve(__dirname,'..');
const model=JSON.parse(fs.readFileSync(path.join(root,'docs/bp.json')));
const data=JSON.parse(fs.readFileSync(path.join(root,'experiments/bp/data.json')));
test('Browser forward pass matches trained PyTorch logits',()=>{
  const p=model.parity,out=engine.forward(model.layers,p.condition,p.noise);
  assert.equal(out.length,p.logits.length);
  assert.ok(Math.max(...out.map((x,i)=>Math.abs(x-p.logits[i])))<1e-4);
});
test('Seed reproducibility, faction pools, all supplied bans and unique survivors',()=>{
  const v=model.report.vocabulary;
  const opts={map:v.maps[0],round:'1',hunterBans:v.hunters.slice(0,5),survivorBans:v.survivors.slice(0,15),seed:42,count:100};
  const a=engine.generate(model,opts),b=engine.generate(model,opts);
  assert.deepEqual(a,b);
  assert.notDeepEqual(a,engine.generate(model,{...opts,seed:43}));
  for(const r of a){assert.ok(v.hunters.includes(r.hunter));assert.ok(!opts.hunterBans.includes(r.hunter));assert.equal(new Set(r.survivors).size,4);assert.ok(r.survivors.every(x=>v.survivors.includes(x)&&!opts.survivorBans.includes(x)));}
});
test('Impossible or unknown constraints fail rather than fabricate a legal result',()=>{
  const v=model.report.vocabulary,base={map:v.maps[0],round:'1',hunterBans:[],survivorBans:[],seed:1};
  assert.throws(()=>engine.generate(model,{...base,hunterBans:v.hunters}));
  assert.throws(()=>engine.generate(model,{...base,survivorBans:v.survivors.slice(0,-3)}));
  assert.throws(()=>engine.generate(model,{...base,map:'unknown'}));
  assert.throws(()=>engine.generate(model,{...base,hunterBans:['unknown']}));
  const a=engine.generate(model,{...base,hunterBans:v.hunters.slice(0,-1),survivorBans:v.survivors.slice(0,-4)});
  assert.ok(a.every(x=>x.hunter===v.hunters.at(-1)&&x.survivors.every(s=>v.survivors.slice(-4).includes(s))));
});
test('Chronological group splits and train-only vocabulary',()=>{
  const sets=['train','validation','test'].map(sp=>new Set(data.rows.filter(r=>r.split===sp).map(r=>r.group)));
  for(let i=0;i<3;i++)for(let j=i+1;j<3;j++)assert.ok(![...sets[i]].some(x=>sets[j].has(x)));
  const train=data.rows.filter(r=>r.split==='train');
  assert.deepEqual([...new Set(train.map(r=>r.hunter))].sort(),model.report.vocabulary.hunters);
  assert.deepEqual([...new Set(train.flatMap(r=>r.survivors))].sort(),model.report.vocabulary.survivors);
  for(const row of data.rows){assert.ok(!('outcome' in row));assert.ok(!('score' in row));}
  assert.equal(data.rows.length+Object.values(data.rejected).reduce((a,b)=>a+b,0),data.input_rows);
});
test('Metrics and selection reconcile without unselected test scores',()=>{
  const r=model.report;
  assert.equal(r.selected_test.contexts,r.coverage.test.supported_rows);
  assert.equal(r.selected_test.samples,r.selected_test.contexts*8);
  assert.equal(r.selected_test.constrained_invalid_rate,0);
  assert.equal(r.config.selected_ce_weight,r.candidates.reduce((a,b)=>a.validation.mean_js<b.validation.mean_js?a:b).ce_weight);
  assert.ok(r.candidates.every(c=>!('test' in c)));
  assert.ok(r.coverage.test.coverage<1);
});
