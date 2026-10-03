"""Conditional GAN for ban-conditioned lineup completion, not optimal BP.

Prepare + train: python experiments/bp/train.py --source /path/public_ivl_expanded.json
Reproduce: python experiments/bp/train.py (uses the committed compact snapshot).
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 20261003


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def prepare(source):
    raw = source.read_bytes()
    payload = json.loads(raw)
    rows, rejected = [], {"non_regular": 0, "missing_or_duplicate_picks": 0, "missing_map": 0, "ban_conflict": 0}
    for r in payload["small_games"]:
        if not r["是否标准常规赛"]:
            rejected["non_regular"] += 1; continue
        s = [r.get("使用角色" + str(i)) for i in range(1, 5)]
        h = r.get("屠选")
        if not h or any(not v for v in s) or len(set(s)) != 4:
            rejected["missing_or_duplicate_picks"] += 1; continue
        if not r.get("地图"):
            rejected["missing_map"] += 1; continue
        # Only initial active-ban slots and recorded global bans are supplied.
        # Later active bans are NOT used: the source is not a verified action log.
        sb = sorted({v for k,v in r.items() if v and k.startswith(("全局禁用人", "人BAN1-"))})
        hb = sorted({v for k,v in r.items() if v and k.startswith(("全局禁用屠", "屠BAN1-"))})
        if h in hb or any(v in sb for v in s):
            rejected["ban_conflict"] += 1; continue
        split = "test" if r["赛季ID"] == "2025-autumn" else "validation" if r["赛季ID"] == "2025-summer" else "train"
        rd = str(r.get("场次号"))
        rows.append({"id":r["小局唯一ID"], "group":r["大场唯一ID"], "season":r["赛季ID"], "split":split, "map":r["地图"], "round":rd if rd in ("1","2","3") else "extra", "hunter":h, "survivors":sorted(s), "hunter_bans":hb, "survivor_bans":sb})
    result = {"source_sha256":hashlib.sha256(raw).hexdigest(), "sources":payload["manifest"]["public_data_sources"], "input_rows":len(payload["small_games"]), "rejected":rejected, "rows":rows}
    save(HERE / "data.json", result)
    return result


class Generator(nn.Module):
    def __init__(self, c, out):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(c+16,64),nn.ReLU(),nn.Linear(64,64),nn.ReLU(),nn.Linear(64,out))
    def forward(self,c,z):
        return self.net(torch.cat((c,z),1))


class Discriminator(nn.Module):
    def __init__(self,c,h,s):
        super().__init__()
        self.h,self.s=h,s
        self.net=nn.Sequential(nn.Linear(c+h+s,64),nn.LeakyReLU(.2),nn.Linear(64,64),nn.LeakyReLU(.2),nn.Linear(64,1))
    def forward(self,c,y):
        # Set representation prevents survivor slot order becoming a shortcut.
        pack=torch.cat((y[:,:self.h],y[:,self.h:].reshape(-1,4,self.s).sum(1)/4),1)
        return self.net(torch.cat((c,pack),1)).squeeze(1)


def draw(logits,h,s,ban_h,ban_s,tau=1.,constrain=True):
    mask_h=ban_h.clone() if constrain else torch.zeros_like(ban_h)
    mask_s=ban_s.clone() if constrain else torch.zeros_like(ban_s)
    choices=[F.gumbel_softmax(logits[:,:h].masked_fill(mask_h,-1e9),tau=tau,hard=True)]
    for i in range(4):
        part=logits[:,h+i*s:h+(i+1)*s].masked_fill(mask_s,-1e9)
        pick=F.gumbel_softmax(part,tau=tau,hard=True)
        choices.append(pick)
        if constrain:mask_s=mask_s | pick.detach().bool()
    return torch.cat(choices,1)


def js(p,q):
    p=np.asarray(p,dtype=float)+1e-8;q=np.asarray(q,dtype=float)+1e-8
    p/=p.sum();q/=q.sum();m=(p+q)/2
    return float(.5*np.sum(p*np.log(p/m))+.5*np.sum(q*np.log(q/m)))


def indices(y,h,s):
    a=y.detach().numpy()
    return np.column_stack((a[:,:h].argmax(1),*[a[:,h+i*s:h+(i+1)*s].argmax(1) for i in range(4)]))


def evaluate(model,part,h,s,training_combos,repeats=8):
    torch.manual_seed(SEED+99)
    c,bh,bs,target=part
    cr=c.repeat_interleave(repeats,0); bhr=bh.repeat_interleave(repeats,0); bsr=bs.repeat_interleave(repeats,0)
    with torch.no_grad():
        logits=model(cr,torch.randn(len(cr),16))
        samples=indices(draw(logits,h,s,bhr,bsr),h,s)
        raw=indices(draw(logits,h,s,bhr,bsr,constrain=False),h,s)
    combos=[(int(row[0]),*sorted(map(int,row[1:]))) for row in samples]
    real=target.numpy()
    hj=js(np.bincount(real[:,0],minlength=h),np.bincount(samples[:,0],minlength=h))
    sj=js(np.bincount(real[:,1:].ravel(),minlength=s),np.bincount(samples[:,1:].ravel(),minlength=s))
    def invalid(arr):
        return sum(bool(bhr[i,row[0]]) or any(bool(bsr[i,j]) for j in row[1:]) or len(set(row[1:]))<4 for i,row in enumerate(arr))/len(arr)
    metrics={"contexts":len(c),"samples":len(samples),"hunter_js":hj,"survivor_js":sj,"mean_js":(hj+sj)/2,"raw_invalid_rate":invalid(raw),"constrained_invalid_rate":invalid(samples),"diversity":float(np.mean([len(set(combos[i:i+repeats]))/repeats for i in range(0,len(combos),repeats)])),"novelty":sum(x not in training_combos for x in combos)/len(combos)}
    return metrics,samples


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path);ap.add_argument("--epochs",type=int,default=60);args=ap.parse_args()
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    snapshot=prepare(args.source) if args.source else json.loads((HERE/"data.json").read_text())
    rows=snapshot["rows"];train=[r for r in rows if r["split"]=="train"]
    vocab={"hunters":sorted({r["hunter"] for r in train}),"survivors":sorted({v for r in train for v in r["survivors"]}),"maps":sorted({r["map"] for r in train}),"rounds":["1","2","3","extra"]}
    h,s=len(vocab["hunters"]),len(vocab["survivors"]);m=len(vocab["maps"])
    hi={v:i for i,v in enumerate(vocab["hunters"])};si={v:i for i,v in enumerate(vocab["survivors"])}
    parts={};kept={};coverage={}
    for split in ["train","validation","test"]:
        raw=[r for r in rows if r["split"]==split]
        eligible=[r for r in raw if r["hunter"] in hi and all(v in si for v in r["survivors"]) and r["map"] in vocab["maps"]]
        unseen=sorted({v for r in raw for v in [r["hunter"]]+r["survivors"] if v not in hi and v not in si})
        coverage[split]={"clean_rows":len(raw),"supported_rows":len(eligible),"coverage":len(eligible)/len(raw),"unseen_characters":unseen,"groups":len({r["group"] for r in eligible})}
        c=[];bh=[];bs=[];target=[]
        for r in eligible:
            a=np.zeros(h);b=np.zeros(s)
            for v in r["hunter_bans"]:
                if v in hi:a[hi[v]]=1
            for v in r["survivor_bans"]:
                if v in si:b[si[v]]=1
            context=np.zeros(m+4);context[vocab["maps"].index(r["map"])]=1;context[m+vocab["rounds"].index(r["round"])]=1
            c.append(np.r_[context,a,b]);bh.append(a);bs.append(b);target.append([hi[r["hunter"]]]+[si[v] for v in r["survivors"]])
        parts[split]=(torch.tensor(np.array(c),dtype=torch.float32),torch.tensor(np.array(bh),dtype=torch.bool),torch.tensor(np.array(bs),dtype=torch.bool),torch.tensor(target,dtype=torch.long))
        kept[split]=eligible
    # Group boundaries are checked before fitting, including the unsupported rows.
    groups=[{r["group"] for r in rows if r["split"]==sp} for sp in parts]
    assert not groups[0]&groups[1] and not groups[0]&groups[2] and not groups[1]&groups[2]
    c,bh,bs,targets=parts["train"];cd=c.shape[1]
    combos={(int(r[0]),*sorted(map(int,r[1:]))) for r in targets.numpy()}
    class Empirical:
        def __init__(self):
            self.counts=torch.ones(m,h+s)
            for ctx,row in zip(c,targets):
                mi=int(ctx[:m].argmax());self.counts[mi,row[0]]+=1
                for v in row[1:]:self.counts[mi,h+v]+=1
        def __call__(self,context,z):
            values=self.counts[context[:,:m].argmax(1)].log()
            return torch.cat((values[:,:h],*[values[:,h:] for _ in range(4)]),1)
    baseline=Empirical()
    results=[];best_score=float("inf");selected=None;all_logs=[]
    for weight in [0.,1.]:
        torch.manual_seed(SEED);np.random.seed(SEED)
        g=Generator(cd,h+4*s);d=Discriminator(cd,h,s)
        go=torch.optim.Adam(g.parameters(),lr=.0003,betas=(.5,.9));do=torch.optim.Adam(d.parameters(),lr=.0003,betas=(.5,.9))
        local_best=float("inf");state=None;logs=[];epoch_best=0
        for epoch in range(1,args.epochs+1):
            gl=[];dl=[]
            for ix in torch.randperm(len(c)).split(128):
                ctx=c[ix];t=targets[ix].clone();n=len(ix)
                # Random survivor order; discriminator sees a permutation-invariant set.
                perm=torch.rand(n,4).argsort(1);t[:,1:]=t[:,1:].gather(1,perm)
                real=torch.cat((F.one_hot(t[:,0],h),*[F.one_hot(t[:,i+1],s) for i in range(4)]),1).float()
                logits=g(ctx,torch.randn(n,16));fake=draw(logits,h,s,bh[ix],bs[ix],tau=max(.5,1-epoch/120))
                do.zero_grad();loss_d=F.softplus(-d(ctx,real)).mean()+F.softplus(d(ctx,fake.detach())).mean();loss_d.backward();do.step()
                go.zero_grad();logits=g(ctx,torch.randn(n,16));fake=draw(logits,h,s,bh[ix],bs[ix],tau=max(.5,1-epoch/120))
                ce=F.cross_entropy(logits[:,:h].masked_fill(bh[ix],-1e9),t[:,0])
                for i in range(4):ce+=F.cross_entropy(logits[:,h+i*s:h+(i+1)*s].masked_fill(bs[ix],-1e9),t[:,i+1])
                loss_g=F.softplus(-d(ctx,fake)).mean()+weight*ce/5
                loss_g.backward();go.step();gl.append(loss_g.item());dl.append(loss_d.item())
            if epoch%5==0 or epoch==1:
                # Evaluation RNG is isolated from subsequent training randomness.
                rng=torch.get_rng_state();val,_=evaluate(g,parts["validation"],h,s,combos);torch.set_rng_state(rng)
                logs.append({"epoch":epoch,"generator_loss":float(np.mean(gl)),"discriminator_loss":float(np.mean(dl)),"validation_js":val["mean_js"]})
                if val["mean_js"]<local_best:local_best=val["mean_js"];state=copy.deepcopy(g.state_dict());epoch_best=epoch
                print(f"CE={weight:g} epoch={epoch} val_JS={val['mean_js']:.4f}",flush=True)
        g.load_state_dict(state)
        val,_=evaluate(g,parts["validation"],h,s,combos)
        results.append({"name":"cGAN" if weight==0 else "Hybrid cGAN","ce_weight":weight,"selected_epoch":epoch_best,"validation":val})
        all_logs.append({"ce_weight":weight,"history":logs})
        if local_best<best_score:best_score=local_best;selected=(copy.deepcopy(g),weight,epoch_best)
    g,weight,epoch=selected
    test,samples=evaluate(g,parts["test"],h,s,combos)
    bv,_=evaluate(baseline,parts["validation"],h,s,combos);bt,_=evaluate(baseline,parts["test"],h,s,combos)
    config={"seed":SEED,"epochs_per_candidate":args.epochs,"batch_size":128,"noise_dim":16,"hidden":[64,64],"learning_rate":.0003,"adam_betas":[.5,.9],"selected_ce_weight":weight,"selected_epoch":epoch,"evaluation_samples_per_context":8,"train_period":"2020 Summer–2024 Autumn","validation_period":"2025 Summer","test_period":"2025 Autumn","selection":"minimum validation mean marginal Jensen-Shannon divergence; test used once after selection"}
    report={"config":config,"coverage":coverage,"audit":{k:v for k,v in snapshot.items() if k!="rows"},"vocabulary":vocab,"candidates":results,"selected_test":test,"baseline":{"name":"Map-frequency sampling","validation":bv,"test":bt},"learning_curves":all_logs,"runtime":{"torch":torch.__version__,"numpy":np.__version__,"device":"cpu"}}
    save(HERE/"results.json",report)
    torch.save({"generator":g.state_dict(),"config":config,"vocabulary":vocab},HERE/"generator.pt")
    layers=[{"weight":layer.weight.detach().numpy().round(7).tolist(),"bias":layer.bias.detach().numpy().round(7).tolist()} for layer in g.net if isinstance(layer,nn.Linear)]
    scenarios=[]
    for r in kept["test"][::max(1,len(kept["test"])//12)][:12]:
        scenarios.append({k:r[k] for k in ["id","map","round","hunter_bans","survivor_bans"]})
    example_c=parts["test"][0][:1];z=torch.zeros(1,16)
    with torch.no_grad():gold=g(example_c,z).numpy()[0].tolist()
    export={"report":report,"layers":layers,"scenarios":scenarios,"parity":{"condition":example_c[0].tolist(),"noise":[0]*16,"logits":gold}}
    save(ROOT/"docs/bp.json",export)
    print(json.dumps({"coverage":coverage,"selected":config,"test":test,"baseline":bt},ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":main()
