"""Export anonymous synthetic chat replies for assistant rubric review."""
import hashlib,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parent
plan=json.loads((ROOT/'plan.json').read_text());models=list(plan['models']);mapping={m:'H-'+hashlib.sha256(m.encode()).hexdigest()[:8] for m in models}
raw=json.loads((ROOT/'results.json').read_text());fixtures={c['id']:c for c in json.loads((ROOT/'fixtures.json').read_text())['cases']}
rows=[]
for m in raw['models']:
 if m['status']!='completed':continue
 for t in m['tests']:
  if t['kind']=='chat':rows.append({'model_code':mapping[m['model']],'id':t['id'],'prompt':fixtures[t['id']]['prompt'],'criteria':fixtures[t['id']]['review_criteria'],'response':t.get('response',''),'done_reason':t.get('done_reason'),'ok':t['ok']})
rows.sort(key=lambda x:(x['model_code'],x['id']))
# Mapping remains local/ignored until review has been recorded.
private=ROOT.parents[2]/'private/hungarian-evaluation'
# ROOT is benchmarks/non-english/hu-round1; repository is parents[2].
private.mkdir(parents=True,exist_ok=True);(private/'review-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
print(json.dumps(rows,ensure_ascii=False,indent=2))
