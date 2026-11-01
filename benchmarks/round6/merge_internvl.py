"""Merge reviewed continuation evidence, without rewriting the original round."""
import copy,datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
summary=json.loads((ROOT/'internvl-summary.json').read_text());raw=json.loads((ROOT/'internvl-completion.json').read_text())
assert raw.get('finished_utc') and raw.get('restore',{}).get('ok')
model=raw['model']['model'];rank=json.loads((ROOT/'rankings.json').read_text())
rank['generated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
rank['scope']='Round 6 rankings with corrected InternVL continuation; tasks independent, original run retained.'
s=summary['recognition']
if summary['recognition_eligible']:
 row={k:v for k,v in s.items() if k not in ['scored_cases','counts','robustness','status','peak_cgroup_bytes','oom_kill_delta']}
 row.update(benchmark_version='vision-evaluation.v1',tested_profile={'max_image_edge':640,'num_ctx':2048,'num_batch':32,'think':False},max_image_dimension=640,evidence='benchmarks/round6/internvl-completion.json')
 rank['image']=[r for r in rank['image'] if r['model']!=model]+[row]
 rank['image'].sort(key=lambda r:(-r['readiness_score'],-r['valid_rate'],r['median_seconds']))
else:
 rank.setdefault('image_service_ineligible',[])
 rank['image_service_ineligible']=[r for r in rank['image_service_ineligible'] if r['model']!=model]+[{'model':model,'status':raw['model']['status'],'reason':'Incomplete suite or OOM; see continuation evidence.'}]
(ROOT/'rankings-with-internvl.json').write_text(json.dumps(rank,indent=2)+'\n')
rows=json.loads((ROOT/'moderation-summary.json').read_text());modraw=json.loads((ROOT/'moderation-results.json').read_text())
if summary.get('moderation'):
 ms=copy.deepcopy(summary['moderation']);ms.update(benchmark_version='vision-evaluation.v1',ranking_metric='macro_f2',tested_profile={'max_image_edge':640,'num_ctx':2048,'num_batch':32,'think':False})
 rows=[r for r in rows if r['model']!=model]+[ms]
 entry={'model':model,'tag':raw['model']['tag'],'status':'completed' if summary['moderation_eligible'] else 'failed','tests':raw['model']['moderation'],'oom_kill_delta':raw['model'].get('oom_kill_delta',0)}
 modraw['models']=[m for m in modraw['models'] if m['model']!=model]+[entry]
(ROOT/'moderation-with-internvl-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
(ROOT/'moderation-with-internvl-results.json').write_text(json.dumps(modraw,indent=2)+'\n')
print('Continuation merged; policy generation and live verification still required.')
