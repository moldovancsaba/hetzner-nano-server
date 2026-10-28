"""Merge only complete comparable evidence; preserve task and cohort separation."""
import datetime,json,statistics,sys,random
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'vision-evaluation'))
from scoring import recognition_summary
r=json.loads((ROOT/'results.json').read_text())
assert r.get('finished_utc') and r.get('restore',{}).get('ok'),'Round not completed/restored'
rank=json.loads((ROOT.parent/'vision-evaluation/rankings.json').read_text())
rank['generated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
rank['scope']='Round 5 English additions and exact production image Runner under idle leases; historical comparable broader scores retained. No moderation or language changes.'
manifest=json.loads((ROOT/'recognition-manifest.json').read_text());summaries=[]
for m in r['models']:
 if m['status']!='completed':continue
 if m['task']=='text' and len(m.get('tests',[]))==14:
  row={'model':m['model'],'passed':sum(t.get('passed',False) for t in m['tests']),'total':14,'json_valid':sum(t.get('json_valid',False) for t in m['tests']),'native_tool_passed':m.get('tool_call',{}).get('passed',False),'median_seconds':round(statistics.median(t['seconds'] for t in m['tests']),3),'evidence':'benchmarks/round5/results.json'}
  rank['english']=[x for x in rank['english'] if x['model']!=m['model']]+[row]
 if m['task']=='vision' and len(m['tests'])==len(manifest['recognition']) and len(m['robustness'])==len(manifest['robustness']) and len(m['counts'])==8:
  s=recognition_summary(m,manifest);summaries.append(s)
  if not any(t.get('oom_kill_delta',0) for field in ['tests','robustness','counts'] for t in m[field]):
   row={k:v for k,v in s.items() if k not in ['scored_cases','counts','robustness','status','peak_cgroup_bytes','oom_kill_delta']}
   row.update(benchmark_version='vision-evaluation.v1',tested_profile={'max_image_edge':640,'num_ctx':2048,'num_batch':32,'think':False},max_image_dimension=640,evidence='benchmarks/round5/results.json')
   rank['image']=[x for x in rank['image'] if x['model']!=m['model']]+[row]
rank['english'].sort(key=lambda x:(-x['passed'],-x['json_valid'],-x['native_tool_passed'],x['median_seconds']))
rank['image'].sort(key=lambda x:(-x['readiness_score'],-x['valid_rate'],x['median_seconds']))
(ROOT/'rankings.json').write_text(json.dumps(rank,indent=2)+'\n')
(ROOT/'recognition-summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
lines=['# Round 5 results','','Three new variants, measured separately for English and image recognition. No moderation, non-English, movie or multi-image claims.','','| Model | Outcome | Result |','| --- | --- | --- |']
for m in r['models']:
 score=str(sum(t.get('passed',False) for t in m.get('tests',[])))+'/14 English checks' if m['task']=='text' else next((f"{s['valid']}/32 valid; reference readiness {s['readiness_score']:.3f}; median {s['median_seconds']:.2f}s" for s in summaries if s['model']==m['model']),'No complete image cohort')
 lines.append('| '+m['model']+' | '+m['status']+' | '+score+' |')
lines+=['','## Method and limits','','English uses the same seven frozen prompts, each run twice (14 checks), plus a separately scored native tool call. Repetition is not 14 independent scenarios. Granite was rerun as a fresh complete English control.','','The image candidate uses all 32 frozen recognition images, nine paired robustness variants and eight count probes. It calls the exact deployed Camera recognition Runner with normalized images under a renewable idle maintenance lease. This measures the service implementation, not HTTPS/queue latency. Eight fresh current-winner sentinel images detect regression; the full current-winner score is historical, not a fresh paired full-cohort rerun. No new unseen holdout or independent human adjudication was added.','','No production payloads or training exports. Temporary inputs are approved public research fixtures. Per-request guards give production work opportunities between image cases. Declined temporary weights are removed, digests/evidence retained. Context, memory cap and CPU allocation unchanged. Historical speed comparisons can vary with cache and load.','','See [raw run](results.json), [plan](plan.json), [source revisions](source-metadata.json), [per-case image scores](recognition-summary.json) and [merged task rankings](rankings.json).','','Current ranking leaders: English **'+rank['english'][0]['model']+'**, recognition **'+rank['image'][0]['model']+'**. Deployment verification is recorded separately.']
intervals=[]
old_scores=json.loads((ROOT.parent/'vision-evaluation/recognition-summary.json').read_text())
base=next(x for x in old_scores if x['model']=='minicpm-v4.6:1b')
for candidate in summaries:
 a={x['id']:x for x in candidate['scored_cases']};b={x['id']:x for x in base['scored_cases']}
 groups=[[x['id'] for x in manifest['recognition'] if x['task']==task] for task in ['recognition','ocr_vqa']]
 rng=random.Random(20261028);deltas=[]
 for _ in range(2000):
  samples=[rng.choices(g,k=len(g)) for g in groups]
  deltas.append(.65*statistics.mean(a[i]['score']-b[i]['score'] for i in samples[0])+.35*statistics.mean(a[i]['score']-b[i]['score'] for i in samples[1]))
 deltas.sort();item={'model':candidate['model'],'versus':base['model'],'point_delta':candidate['readiness_score']-base['readiness_score'],'paired_bootstrap_95':[deltas[49],deltas[1949]],'note':'Paired reference cases; baseline full run is historical. Descriptive uncertainty, not proof of general superiority.'};intervals.append(item)
 lines+=['','Paired readiness difference versus historical Q4 baseline: '+str(round(item['point_delta'],4))+'; descriptive 95% bootstrap interval '+str([round(v,4) for v in item['paired_bootstrap_95']])+'. A range spanning zero does not establish a reliable quality improvement.']
(ROOT/'recognition-comparison-intervals.json').write_text(json.dumps(intervals,indent=2)+'\n')
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'english':rank['english'][0]['model'],'image':rank['image'][0]['model'],'attempted':len(r['models'])}))
