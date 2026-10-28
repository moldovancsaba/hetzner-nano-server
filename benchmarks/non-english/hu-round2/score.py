"""Preserve the unchanged Hungarian gate and separate Habi regression reviews."""
import importlib.util,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('hu_round1_score',ROOT.parent/'hu-round1/score.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
raw=json.loads((ROOT/'results.json').read_text());fixtures=json.loads((ROOT/'fixtures.json').read_text());reviews=json.loads((ROOT/'chat-review.json').read_text());byid={c['id']:c for c in fixtures['cases']};rows=[]
for m in raw['models']:
 checks=[]
 for t in m['tests']:
  if byid[t['id']]['kind']!='structured':continue
  try:v=json.loads(t['response']);valid=True;correct=t['ok'] and t.get('done_reason')!='length' and module.exact(v,byid[t['id']]['expected'])
  except (ValueError,KeyError,TypeError):valid=correct=False
  checks.append({'id':t['id'],'json_valid':valid,'correct':correct})
 review=reviews['models'][m['model']];usable=sum(x['usable'] for x in review['chat'].values());full=m['status']=='completed' and {t['id'] for t in m['tests']}==set(byid)
 eligible=full and sum(x['correct'] for x in checks)>=20 and usable>=5 and len(review['chat'])==6 and m.get('oom_kill_delta',0)==0
 rows.append({'model':m['model'],'status':m['status'],'profile':'ctx4096/batch8','correct':sum(x['correct'] for x in checks),'total':24,'json_valid':sum(x['json_valid'] for x in checks),'chat_usable':usable,'chat_total':6,'client_regression_usable':sum(x['usable'] for x in review['client_regression'].values()),'client_regression_total':5,'median_seconds':statistics.median(t['seconds'] for t in m['tests']),'peak_cgroup_bytes':max(t.get('peak_cgroup_bytes',0) for t in m['tests']),'oom_kill_delta':m.get('oom_kill_delta',0),'ranking_eligible':eligible,'checks':checks})
result={'version':'hungarian-followup.v1','generated_utc':raw.get('finished_utc'),'scope':'Hungarian-only frozen follow-up; six original chat cases assistant-reviewed; five Habi-derived synthetic regressions separate. No independent native-speaker certification or long-context recall test.','ranking_policy':'Unchanged >=20/24 strict structured and >=5/6 usable original chat, complete and zero OOM. Habi regressions separately reported.','rows':rows,'winner':next((r['model'] for r in rows if r['ranking_eligible']),None)}
(ROOT/'rankings.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps([{k:v for k,v in r.items() if k!='checks'} for r in rows],indent=2))
