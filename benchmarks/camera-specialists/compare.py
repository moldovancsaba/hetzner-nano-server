"""Descriptive 1/2/3-model alert unions, preserving unknown labels and missing coverage."""
import itertools,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
manifest=json.loads((ROOT/'manifest.json').read_text());cases={c['id']:c for c in manifest['cases']}
legacy=json.loads((REPO/'benchmarks/vision-evaluation/moderation-results.json').read_text())['models']
special=json.loads((ROOT/'results.json').read_text())['models']
def union(values):
 if any(v is True for v in values):return True
 if values and all(v is False for v in values):return False
 return None
mapping={'nudity':['nudity','sexualContent'],'offensive_gesture':['middleFinger'],'alcohol':['alcohol'],'violence':['violence','weapons'],'hate':['hateSymbols','hateWords'],'drugs':['drugs']}
pred={}
for m in legacy:
 pred[m['model']]={}
 for t in m['tests']:
  cats=(t.get('parsed') or {}).get('categories',{}) if t.get('valid') else {}
  pred[m['model']][t['id']]={k:union([cats.get(c) for c in v]) for k,v in mapping.items()}
for m in special:pred[m['model']]={t['id']:{'nudity':t['detected']} for t in m['tests']}
rows=[]
for count in [1,2,3]:
 for models in itertools.combinations(pred,count):
  cats={}
  for category,fields in mapping.items():
   tp=tn=fp=fn=abstained=0
   for identity,c in cases.items():
    gold=union([c['expected'].get(x) for x in fields])
    if gold is None:continue
    outcome=union([pred[m].get(identity,{}).get(category) for m in models if category in pred[m].get(identity,{})])
    if outcome is None:abstained+=1
    if gold is True:
     if outcome is True:tp+=1
     else:fn+=1
    elif outcome is True:fp+=1
    elif outcome is False:tn+=1
   denom=5*tp+4*fn+fp
   cats[category]={'tp':tp,'fn':fn,'fp':fp,'tn':tn,'abstained':abstained,'f2':5*tp/denom if denom else 0,'recall':tp/(tp+fn) if tp+fn else None}
  rows.append({'models':list(models),'count':count,'macro_f2':statistics.mean(c['f2'] for c in cats.values()),'categories':cats})
rows.sort(key=lambda x:(-x['macro_f2'],x['count']))
result={'version':'camera-coverage.v1','scope':'Exploratory retrospective union comparison on same 41 research images, six mapped Camera reasons only. Selecting a combination here needs a fresh held-out validation set; no production promotion. Legacy general-model outputs are historical, not simultaneous reruns. Binary NSFW is the union of nudity/sexualContent, not proof of either subtype.','reason_coverage':list(mapping),'not_evaluated':['forbidden','competitor_brand','political','poor_quality','spam_test','other'],'best_by_count':{str(n):next(x for x in rows if x['count']==n) for n in [1,2,3]},'rows':rows}
(ROOT/'combination-results.json').write_text(json.dumps(result,indent=2)+'\n')
summary=[]
for m in special:
 times=[t['seconds'] for t in m['tests']];r=next(x for x in rows if x['models']==[m['model']])
 c=r['categories']['nudity'];summary.append({'model':m['model'],'status':m['status'],'total_images':len(m['tests']),'valid':len(m['tests']),'median_seconds':statistics.median(times),'macro_f2':c['f2'],'macro_detection_recall':c['recall'],'true_positives':c['tp'],'false_positives':c['fp'],'benchmark_version':'binary-nsfw-41.v1','ranking_eligible':False})
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'specialists':summary,'best_by_count':result['best_by_count']},indent=2))
