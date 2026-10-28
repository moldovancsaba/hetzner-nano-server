"""Hungarian-only strict scoring. Free-form chat requires explicit separate review."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def exact(value,expected):
 if type(value) is not type(expected):return False
 if isinstance(expected,dict):return set(value)==set(expected) and all(exact(value[k],v) for k,v in expected.items())
 if isinstance(expected,list):return len(value)==len(expected) and all(exact(a,b) for a,b in zip(value,expected))
 return value==expected

def build():
 raw=json.loads((ROOT/'results.json').read_text());fixtures=json.loads((ROOT/'fixtures.json').read_text());reviews=json.loads((ROOT/'chat-review.json').read_text()) if (ROOT/'chat-review.json').exists() else {'models':{}}
 rows=[];byid={c['id']:c for c in fixtures['cases']}
 for entry in raw['models']:
  checks=[]
  for result in entry['tests']:
   case=byid[result['id']]
   if case['kind']!='structured':continue
   valid=False;correct=False
   try:
    value=json.loads(result.get('response',''));valid=True;correct=result['ok'] and result.get('done_reason')!='length' and exact(value,case['expected'])
   except (ValueError,TypeError):pass
   checks.append({'id':case['id'],'json_valid':valid,'correct':correct})
  review=reviews['models'].get(entry['model'],{}) if entry['status']=='completed' else {}
  usable=sum(v.get('usable',False) for v in review.values())
  complete=entry['status']=='completed' and {t['id'] for t in entry['tests']}==set(byid)
  eligible=complete and sum(t['correct'] for t in checks)>=20 and len(review)==6 and usable>=5 and entry.get('oom_kill_delta',0)==0
  rows.append({'model':entry['model'],'language':'hu','status':entry['status'],'profile':'ctx'+str(entry.get('operating_profile',{}).get('num_ctx',2048))+'/batch'+str(entry.get('operating_profile',{}).get('num_batch',32)),'correct':sum(t['correct'] for t in checks),'total':24,'json_valid':sum(t['json_valid'] for t in checks),'chat_usable':usable,'chat_total':6,'chat_reviewed':len(review),'median_seconds':round(statistics.median(t['seconds'] for t in entry['tests']),3),'peak_cgroup_bytes':max((t.get('peak_cgroup_bytes',0) for t in entry['tests']),default=0),'oom_kill_delta':entry.get('oom_kill_delta',0),'ranking_eligible':eligible,'tested_profile':{'max_image_edge':640,'num_ctx':entry.get('operating_profile',{}).get('num_ctx',2048),'num_batch':entry.get('operating_profile',{}).get('num_batch',32),**({'think':False} if 'thinking' in entry.get('tag',{}).get('capabilities',[]) else {})},'checks':checks})
 rows.sort(key=lambda r:(not r['ranking_eligible'],-r['correct'],-r['chat_usable'],r['median_seconds']))
 result={'version':'hungarian-ranking.v1','language':'hu','scope':'Synthetic Hungarian text pilot; separate from English, vision and moderation. Assistant chat review is not independent native-speaker certification.','ranking_policy':'Eligibility: >=20/24 strict structured cases, >=5/6 usable assistant-reviewed chat cases, complete suite and no OOM; rank correctness, chat usability, latency.','generated_utc':raw.get('finished_utc'),'rows':rows,'winner':next((r['model'] for r in rows if r['ranking_eligible']),None)}
 completed=[r for r in rows if r['status']=='completed' and r['oom_kill_delta']==0 and r['chat_reviewed']==6]
 result['pilot_winner']=result['winner'] or (completed[0]['model'] if completed else None)
 result['deployment_stage']='experimental_only' if not result['winner'] else 'accepted_pilot'
 result['production_accepted']=bool(result['winner'])
 result['pilot_selection_note']='No quality gate was lowered. If no model passes, the best complete resource-valid profile is exposed only as the explicitly selected experimental Hungarian job for owner-requested testing/feedback; human review required.'
 for row in rows:
  row['api_eligible']=row['status']=='completed' and row['model']==result['pilot_winner'] and row['oom_kill_delta']==0
 (ROOT/'rankings.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');return result
if __name__=='__main__':
 r=build();print(json.dumps({'winner':r['winner'],'scores':[(x['model'],x['correct'],x['chat_usable']) for x in r['rows']]}))
