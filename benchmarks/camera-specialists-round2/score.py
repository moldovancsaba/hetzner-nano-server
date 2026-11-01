"""Binary-only scores; no nine-category rank or automated moderation approval."""
import json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'vision-evaluation'))
from scoring import wilson
r=json.loads((ROOT/'results.json').read_text());assert r.get('finished_utc') and r.get('restore'),'Incomplete or unrestored run'
m=r['models'][0];cases={c['id']:c for c in json.loads((ROOT/'manifest.json').read_text())['cases']}
assert len({t['id'] for t in m['tests']})==len(m['tests'])
c=dict(tp=0,tn=0,fp=0,fn=0,unknown=0,invalid=0)
for t in m['tests']:
 golds=[cases[t['id']]['expected'][k] for k in ['nudity','sexualContent']]
 gold=True if any(x is True for x in golds) else False if all(x is False for x in golds) else None
 if gold is None:c['unknown']+=1;continue
 if not t.get('valid'):c['invalid']+=1;continue
 c['tp' if gold and t['detected'] else 'fn' if gold else 'fp' if t['detected'] else 'tn']+=1
positive=c['tp']+c['fn'];negative=c['tn']+c['fp'];denom=5*c['tp']+4*c['fn']+c['fp']
row={'model':m['model'],'status':m['status'],'total_images':len(m['tests']),'valid':sum(t.get('valid',False) for t in m['tests']),'median_seconds':statistics.median(t['seconds'] for t in m['tests']),'p95_seconds':sorted(t['seconds'] for t in m['tests'])[max(0,__import__('math').ceil(.95*len(m['tests']))-1)],'true_positives':c['tp'],'false_positives':c['fp'],'macro_f2':5*c['tp']/denom if denom else 0,'macro_detection_recall':c['tp']/positive if positive else None,'benchmark_version':'binary-nsfw-41.v1','ranking_eligible':False,'binary_confusion':c,'positive_recall_wilson95':wilson(c['tp'],positive),'specificity_wilson95':wilson(c['tn'],negative),'scope':'Only nudity/sexualContent union. Threshold fixed at 0.5 before inference. No held-out threshold calibration; not nine-category moderation or twelve-reason approval.'}
(ROOT/'summary.json').write_text(json.dumps({'version':r['version'],'generated_utc':r['finished_utc'],'rows':[row]},indent=2)+'\n')
print(json.dumps(row))
