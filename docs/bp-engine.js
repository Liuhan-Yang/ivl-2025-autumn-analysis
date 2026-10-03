/* Pure CPU inference for the exported, actually trained generator. */
(function(root) {
  'use strict';
  function rng(seed) {
    let a=Number(seed)>>>0;
    return () => {a+=0x6D2B79F5;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
  }
  function forward(layers,condition,noise) {
    let x=condition.concat(noise);
    for(let n=0;n<layers.length;n++) {
      const layer=layers[n];
      x=layer.weight.map((row,i)=>{let s=layer.bias[i];for(let j=0;j<row.length;j++)s+=row[j]*x[j];return n<layers.length-1?Math.max(0,s):s;});
    }
    return x;
  }
  function condition(v,map,round,hb,sb) {
    if(!v.maps.includes(map)||!v.rounds.includes(round))throw new Error('Unknown map or round');
    if(hb.some(x=>!v.hunters.includes(x))||sb.some(x=>!v.survivors.includes(x)))throw new Error('Ban outside training vocabulary');
    return [...v.maps.map(x=>Number(x===map)),...v.rounds.map(x=>Number(x===round)),...v.hunters.map(x=>Number(hb.includes(x))),...v.survivors.map(x=>Number(sb.includes(x)))];
  }
  function generate(model,options) {
    const v=model.report.vocabulary,h=v.hunters.length,s=v.survivors.length;
    const hb=[...new Set(options.hunterBans)],sb=[...new Set(options.survivorBans)];
    if(h-hb.length<1||s-sb.length<4)throw new Error('Not enough unbanned characters');
    const c=condition(v,options.map,options.round,hb,sb),random=rng(options.seed);
    const normal=()=>Math.sqrt(-2*Math.log(Math.max(random(),1e-12)))*Math.cos(2*Math.PI*random());
    function choose(logits,names,blocked) {
      let best=-Infinity,index=-1;
      logits.forEach((logit,i)=>{if(blocked.has(names[i]))return;const u=Math.max(1e-12,Math.min(1-1e-12,random()));const score=logit-Math.log(-Math.log(u));if(score>best){best=score;index=i;}});
      if(index<0)throw new Error('No feasible choice');return names[index];
    }
    return Array.from({length:options.count||4},()=>{
      const logits=forward(model.layers,c,Array.from({length:16},normal));
      const hunter=choose(logits.slice(0,h),v.hunters,new Set(hb)),blocked=new Set(sb),survivors=[];
      for(let i=0;i<4;i++){const pick=choose(logits.slice(h+i*s,h+(i+1)*s),v.survivors,blocked);survivors.push(pick);blocked.add(pick);}
      return {hunter,survivors};
    });
  }
  const api={forward,condition,generate};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.BPEngine=api;
})(typeof window!=='undefined'?window:this);
