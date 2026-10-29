"""Build an allowlisted, payload-free public benchmark dashboard."""
import json, html
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
BASE='https://github.com/moldovancsaba/hetzner-nano-server/blob/main/'
FIELDS={'model','status','passed','total','json_valid','native_tool_passed','median_seconds','p95_seconds','valid','total_images','valid_rate','readiness_score','object_reference_f1','object_recall','ocr_target_recall','ocr_correct','ocr_total','count_correct','count_total','macro_f2','macro_specificity','macro_detection_recall','true_positives','false_positives','known_correct','benchmark_version','correct','score','chat_usable','chat_total','ranking_eligible','profile','api_eligible','client_regression_usable','client_regression_total'}
def read(p):return json.loads((ROOT/p).read_text())
def safe(row):return {k:v for k,v in row.items() if k in FIELDS and isinstance(v,(str,int,float,bool,type(None)))}
def build():
 from build_tested_model_index import build as index
 registry=index()
 data={'generated_utc':datetime.now(timezone.utc).isoformat(),'model_variants_attempted':len(registry['models']),'hardware':'Hetzner CAX11 · 2 shared ARM64 CPU · 4 GB RAM · no GPU','defaults':read('config/model-policy.json')['defaults'],'models':[{'model':r['model'],'outcomes':r['outcomes'],'sources':r['evidence'],'ranked_tasks':r.get('ranked_tasks',[])} for r in registry['models']],'cohorts':[]}
 for path,label in [('benchmarks/round3/rankings.json','Round 3 screening'),('benchmarks/round4/rankings.json','Round 4 screening'),('benchmarks/vision-evaluation/rankings.json','Broader evaluation'),('benchmarks/round5/rankings.json','Round 5 merged ranking'),('benchmarks/round6/rankings.json','Round 6 merged ranking')]:
  if not (ROOT/path).exists():continue
  r=read(path)
  for key,task in [('english','English structured tasks'),('english_budget_limited','English: output-budget limited'),('image','Image recognition')]:
   if r.get(key):data['cohorts'].append({'label':label+' · '+task,'date':r.get('generated_utc'),'policy':r.get('english_policy' if key.startswith('english') else 'image_policy',''),'source':path,'rows':[safe(x) for x in r[key]]})
 for path,label in [('benchmarks/moderation/summary.json','Moderation · preliminary 25-image set'),('benchmarks/vision-evaluation/moderation-summary.json','Moderation · broader 41-image set'),('benchmarks/round6/moderation-new-summary.json','Moderation · Round 6 candidates, same 41 images')]:
  data['cohorts'].append({'label':label,'date':None,'policy':'Human review required. Valid JSON is not detection accuracy. Small category samples; see source for confidence intervals and category breakdowns.','source':path,'rows':[safe(x) for x in read(path)]})
 hu_path='benchmarks/non-english/hu-round1/rankings.json'
 if (ROOT/hu_path).exists():
  hu=read(hu_path)
  data['cohorts'].append({'label':'Hungarian · independent text pilot','date':hu.get('generated_utc'),'policy':hu['ranking_policy']+' '+hu['scope'],'source':hu_path,'rows':[safe(x) for x in hu['rows']]})
 for path,label,policy in [('benchmarks/non-english/hu-round3/rankings.json','Hungarian · LFM2 1.2B and OLMo 2 1B follow-up','Same frozen 24 structured cases; scored separately from English. Both missed the unchanged 20/24 structured gate, so the free-form chat review was not performed (recorded as not performed, not as zero). Five synthetic Habi regressions are not scored.'),('benchmarks/non-english/hu-round2/rankings.json','Hungarian · Apertus Mini follow-up','Same frozen 24 structured + six assistant-reviewed chat cases; five synthetic Habi regressions separate. No candidate passed the unchanged gate. 4K allocation is not long-context approval.'),('benchmarks/camera-specialists/summary.json','Camera specialists · binary NSFW only','41 frozen public research images. Binary nudity/sexual-content union only; not comparable with nine-category macro scores. No calibrated probabilities or new production route.')]:
  if (ROOT/path).exists():
   value=read(path);rows=value['rows'] if isinstance(value,dict) else value
   data['cohorts'].append({'label':label,'date':value.get('generated_utc') if isinstance(value,dict) else None,'policy':policy,'source':path,'rows':[safe(x) for x in rows]})
 data['experimental_tasks']=[task for task,model in data['defaults'].items() if read('config/model-policy.json')['models'][model]['tasks'][task].get('experimental')]
 (ROOT/'dashboard/results.json').write_text(json.dumps(data,indent=2)+'\n')
 print(f"Built {data['model_variants_attempted']} variants, {len(data['cohorts'])} historical cohorts")
 return data
if __name__=='__main__':build()
