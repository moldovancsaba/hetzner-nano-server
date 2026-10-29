"""One finite rework using a shorter official source; retain original failed evidence."""
import json,pathlib,urllib.request,time
ROOT=pathlib.Path('/opt/narimato-factory');cfg=json.loads((ROOT/'factory.json').read_text());base='http://127.0.0.1:3100/api';out=ROOT/'rework-bmf-20261028.json'
def api(p,b=None):
 with urllib.request.urlopen(urllib.request.Request(base+p,data=json.dumps(b).encode() if b else None,headers={'Content-Type':'application/json'}),timeout=30) as r:return json.load(r)
def wait(i):
 end=time.monotonic()+900
 while time.monotonic()<end:
  r=api('/issues/'+i)
  if r['status'] in ['in_review','blocked','cancelled','done']:return r
  time.sleep(3)
 raise RuntimeError('Inspect existing task before retry: '+i)
def save():out.write_text(json.dumps(state,indent=2)+'\n')
state=json.loads(out.read_text()) if out.exists() else {'name':'Brooklyn Music Factory','url':'https://brooklynmusicfactory.com/calendar/','previous_research':'NAR-13','previous_result':'Only name passed; six unsupported quote/value combinations were rejected; missing core address. Changed condition: shorter official calendar page with explicit contact footer.'}
if not state.get('research_id'):
 r=api('/companies/'+cfg['company_id']+'/issues',{'title':'Rework Brooklyn Music Factory evidence from official calendar — 2026-10-28','description':'The original homepage draft NAR-13 had six rejected quote/value pairs. Use the shorter official source https://brooklynmusicfactory.com/calendar/ . Capture exact supported provider identity, street address, phone and email. Keep unknown price unknown. Calendar event dates and facility hours are not a recurring class schedule. Do not publish.','projectId':next(k for k,v in cfg['projects'].items() if v=='ClassScout'),'parentId':api('/issues/NAR-13')['id'],'status':'todo','assigneeAgentId':next(k for k,v in cfg['agents'].items() if v['role']=='research'),'responsibleUserId':'local-board','reviewPolicy':'human_only'})
 state.update(research_id=r['id'],research_identifier=r['identifier']);save();print(json.dumps({'rework':r['identifier']}),flush=True)
r=wait(state['research_id']);state['research_status']=r['status'];save()
if r['status']=='in_review':
 import re
 comments=api('/issues/'+r['id']+'/comments');refs=[v for c in comments for v in re.findall(r'Draft reference: `([a-f0-9]{32})`',c.get('body',''))];state['draft_id']=refs[-1];save()
 if not state.get('quality_id'):
  q=api('/companies/'+cfg['company_id']+'/issues',{'title':'Verify Brooklyn Music Factory rework — 2026-10-28','description':'Draft reference: '+state['draft_id']+'. Recheck all source quotes and required name/address. Preserve the original failed pass in the audit history. No publishing.','projectId':r['projectId'],'parentId':r['id'],'status':'todo','assigneeAgentId':next(k for k,v in cfg['agents'].items() if v['role']=='quality'),'responsibleUserId':'local-board','reviewPolicy':'human_only'})
  state.update(quality_id=q['id'],quality_identifier=q['identifier']);save()
 q=wait(state['quality_id']);state['quality_status']=q['status'];save()
print(json.dumps({'rework_result':state}),flush=True)
