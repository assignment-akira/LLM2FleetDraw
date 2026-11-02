import argparse,csv,json,math,random,statistics
from pathlib import Path

def dist(a,b):return math.dist(a,b)
def length(s):return sum(dist(a,b) for a,b in zip(s['points'],s['points'][1:]))
def center(s):
 p=s['points'];return [sum(q[0] for q in p)/len(p),sum(q[1] for q in p)/len(p)]
def weight(s):return length(s)+.25*len(s['points'])+1.5
def nearest_order(bucket,start=(5.544445,5.544445)):
 pending=[dict(s,points=list(s['points'])) for s in bucket];ordered=[];at=start
 while pending:
  _,idx,rev=min((dist(at,s['points'][0]),i,0) for i,s in enumerate(pending)) if False else min([(dist(at,s['points'][0]),i,0) for i,s in enumerate(pending)]+[(dist(at,s['points'][-1]),i,1) for i,s in enumerate(pending)])
  s=pending.pop(idx)
  if rev:s['points'].reverse()
  ordered.append(s);at=s['points'][-1]
 return ordered

def assignments(ss,k,method):
 # deterministic initialization and tie-breaking; every stroke assigned exactly once
 n=len(ss);assert n>=k
 w=[weight(s) for s in ss];c=[center(s) for s in ss]
 if method=='greedy':
  bins=[[] for _ in range(k)];loads=[0.]*k
  for i in sorted(range(n),key=lambda i:(-w[i],i)):
   j=min(range(k),key=lambda j:(loads[j],j));bins[j].append(i);loads[j]+=w[i]
 elif method=='rcb':
  def rec(ids,count):
   if count==1:return [ids]
   axis=max(range(2),key=lambda ax:max(c[i][ax] for i in ids)-min(c[i][ax] for i in ids))
   ids=sorted(ids,key=lambda i:(c[i][axis],i));cut=round(count/2)
   target=sum(w[i] for i in ids)*cut/count
   choices=range(1,len(ids))
   split=min(choices,key=lambda h:(abs(sum(w[i] for i in ids[:h])-target),abs(h/len(ids)-cut/count)))
   return rec(ids[:split],cut)+rec(ids[split:],count-cut)
  bins=rec(list(range(n)),k)
 else:
  # Spatial k-medoids-like iterative centers with load-balancing penalty.
  # Graph variant embeds local line-to-line distance in assignment affinity.
  seeds=[min(range(n),key=lambda i:(c[i][0],i))]
  while len(seeds)<k:
   seeds.append(max((i for i in range(n) if i not in seeds),key=lambda i:(min(dist(c[i],c[j]) for j in seeds),-i)))
  means=[c[i][:] for i in seeds];bins=[[] for _ in range(k)]
  for it in range(12):
   bins=[[] for _ in range(k)];loads=[0.]*k;avg=sum(w)/k
   for i in sorted(range(n),key=lambda i:(-w[i],i)):
    def score(j):
     spatial=dist(c[i],means[j]);over=max(0,loads[j]+w[i]-avg)/max(1,avg)
     if method=='graph' and bins[j]:
      # endpoints/centroid connection surrogate; favors adjacent strokes
      close=min(min(dist(s['points'][0],ss[h]['points'][0]),dist(s['points'][-1],ss[h]['points'][-1]),dist(c[i],c[h])) for h in bins[j] for s in [ss[i]])
      spatial=.5*spatial+.5*close
     return spatial+ (3.0 if method=='kmeans' else 3.8)*over
    j=min(range(k),key=lambda j:(score(j),j));bins[j].append(i);loads[j]+=w[i]
   # Repair empty clusters by moving a stroke from a cluster with >1
   for j in range(k):
    if not bins[j]:
     donor=max(range(k),key=lambda q:len(bins[q]));bins[j].append(bins[donor].pop())
   means=[[sum(c[i][t]*w[i] for i in b)/sum(w[i] for i in b) for t in (0,1)] for b in bins]
 # ensure exact coverage
 allidx=[i for b in bins for i in b]
 assert len(allidx)==n and len(set(allidx))==n and set(allidx)==set(range(n))
 return [[ss[i] for i in b] for b in bins]

def evaluate(bins):
 ordered=[nearest_order(b) for b in bins]
 loads=[];penups=[];compact=[]
 for bucket in ordered:
  at=(5.544445,5.544445);penup=0;centers=[center(s) for s in bucket]
  for s in bucket:
   penup+=dist(at,s['points'][0]);at=s['points'][-1]
  penups.append(penup)
  loads.append(sum(weight(s) for s in bucket)+penup)
  mx=[statistics.mean(c[t] for c in centers) for t in (0,1)]
  compact.append(statistics.mean(dist(c,mx) for c in centers))
 avg=sum(loads)/len(loads)
 return ordered,{'max_estimated_cost':round(max(loads),3),'load_cv':round(statistics.pstdev(loads)/avg,4),'total_penup':round(sum(penups),3),'compactness':round(statistics.mean(compact),3),'costs':[round(x,3) for x in loads], 'stroke_counts':[len(b) for b in ordered]}

def svg(ordered,path):
 colors=['#e35b57','#168ac0','#37a06a','#a96fca','#c6a237']
 lines=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512"><rect width="512" height="512" fill="#fefefe"/>']
 for j,bucket in enumerate(ordered):
  for s in bucket:
   pts=' '.join(f'{(p[0]-.7)*511/9.6:.2f},{(10.3-p[1])*511/9.6:.2f}' for p in s['points'])
   lines.append(f'<polyline points="{pts}" fill="none" stroke="{colors[j]}" stroke-width="1.6"/>')
 path.write_text(''.join(lines)+'</svg>')

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args()
 root=Path(a.root);subjects=('robot','turtle','flower');rows=[];runs=[]
 for subject in subjects:
  f=root/'plans'/f'{subject}.json'
  doc=json.loads(f.read_text());ss=doc['strokes'];assert len(ss)>=5
  for k in (3,5):
   candidates=[]
   for method in ('greedy','rcb','kmeans','graph'):
    raw=assignments(ss,k,method);ordered,metrics=evaluate(raw)
    key=f'{subject}_{k}_{method}';dest=root/'partitions'/key;dest.mkdir(parents=True,exist_ok=True)
    plan={'subject':subject,'method':method,'robots':k,'assignments':[{'turtle':f'turtle{j+1}','region':f'cluster{j+1}','strokes':b} for j,b in enumerate(ordered)]}
    (dest/'plan.json').write_text(json.dumps(plan,indent=2))
    svg(ordered,dest/'color.svg')
    item={'subject':subject,'robots':k,'method':method,**metrics,'path':str(dest/'plan.json')};candidates.append(item)
   # rank within subject+robot count, normalized metrics (no arbitrary stroke-splitting score)
   keys=['max_estimated_cost','total_penup','compactness'];weights=[.50,.30,.20]
   for item in candidates:
    item['score']=round(sum(weights[i]*(item[key]-min(x[key] for x in candidates))/(max(x[key] for x in candidates)-min(x[key] for x in candidates) or 1) for i,key in enumerate(keys)),5)
   candidates.sort(key=lambda x:(x['score'],x['method']))
   rows.extend(candidates);winner=candidates[0];runs.append(winner)
   print('WINNER',subject,k,winner['method'],'score',winner['score'],'estimated_cost',winner['max_estimated_cost'])
 with (root/'rankings.csv').open('w',newline='') as f:
  fields=['subject','robots','method','score','max_estimated_cost','load_cv','total_penup','compactness','stroke_counts','costs','path'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:v for k,v in r.items() if k in fields} for r in rows])
 (root/'selected.json').write_text(json.dumps(runs,indent=2))
 assert len(rows)==24 and len(runs)==6
 print('RANKING PASS',len(rows),'conditions,',len(runs),'selected; results are estimates, not measured drawing time')
if __name__=='__main__':main()
