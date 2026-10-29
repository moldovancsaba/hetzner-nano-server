"""Finite owner-requested source-page batch; no scheduler and no publication."""
import json,pathlib,time,urllib.request,urllib.error,re,datetime
ROOT=pathlib.Path('/opt/narimato-factory');CFG=json.loads((ROOT/'factory.json').read_text());BASE='http://127.0.0.1:3100/api';DAY='2026-10-28'
SOURCES=[('The Art Farm NYC','https://www.theartfarms.com/contact/'),('Brooklyn Music Factory','https://brooklynmusicfactory.com/'),('STREB','https://www.streb.org/the-lab/'),('Keylab','https://www.keylab.nyc/kids-music-production-classes'),('West Side YMCA','https://ymcanyc.org/locations/west-side-ymca')]
def api(p,b=None,method=None):
 req=urllib.request.Request(BASE+p,data=json.dumps(b).encode() if b is not None else None,headers={'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError(str(e.code)+' '+e.read(900).decode()) from None
def emit(v):print(json.dumps(v),flush=True)
project=next(k for k,v in CFG['projects'].items() if v=='ClassScout');agents={v['role']:k for k,v in CFG['agents'].items()};existing=api('/companies/'+CFG['company_id']+'/issues');existing=existing if isinstance(existing,list) else existing.get('issues',[])
def issue(title,description,agent=None,status='backlog',parent=None):
 old=next((i for i in existing if i['title']==title),None)
 if old:return old
 b={'projectId':project,'title':title,'description':description,'status':status,'reviewPolicy':'human_only','responsibleUserId':'local-board'}
 if agent:b['assigneeAgentId']=agent
 else:b['assigneeUserId']='local-board'
 if parent:b['parentId']=parent
 row=api('/companies/'+CFG['company_id']+'/issues',b);existing.append(row);return row
parent=issue('ClassScout five-provider source research — '+DAY,'Owner-requested batch of five official provider pages. Research and evidence checks run sequentially. Each result returns to owner review. Publishing remains gated by ClassScout’s existing schema and approval rules.',status='in_progress')
state={'date':DAY,'parent':parent,'providers':[],'status':'running'}
def save():
 (ROOT/'batch-20261028.json').write_text(json.dumps(state,indent=2)+'\n')
def start_wait(row,role):
 row=api('/issues/'+row['id'])
 if row['status']=='backlog':row=api('/issues/'+row['id'],{'status':'todo'},'PATCH')
 deadline=time.monotonic()+900
 while time.monotonic()<deadline:
  row=api('/issues/'+row['id'])
  if row['status'] in ['in_review','blocked','done','cancelled']:return row
  time.sleep(3)
 raise RuntimeError('Task deadline reached; inspect existing run before retry: '+row['identifier'])
try:
 for name,url in SOURCES:
  desc='Research the official source '+url+' for a ClassScout provider proposal. Capture only explicitly supported name, address, phone, email, opening hours, price and activities with exact evidence. Distinguish facility opening hours from kids class schedules; unknown ages, registration, class times and prices must remain unknown. Do not publish or contact anyone.'
  r=issue('Research '+name+' for ClassScout — '+DAY,desc,agents['research'],parent=parent['id']);state['providers'].append({'name':name,'url':url,'research_id':r['id'],'research_identifier':r['identifier']})
 save();emit({'parent':parent['identifier'],'research_tasks':[p['research_identifier'] for p in state['providers']]})
 for p in state['providers']:
  row=start_wait({'id':p['research_id']},'research');p['research_status']=row['status'];save();emit({'provider':p['name'],'research_status':row['status']})
  if row['status']!='in_review':continue
  comments=api('/issues/'+row['id']+'/comments');comments=comments if isinstance(comments,list) else comments.get('comments',[])
  refs=[ref for c in comments for ref in re.findall(r'Draft reference: `([a-f0-9]{32})`',c.get('body',''))]
  if not refs:p['quality_status']='missing draft reference';save();continue
  p['draft_id']=refs[-1]
  q=issue('Verify '+p['name']+' evidence — '+DAY,'Draft reference: '+p['draft_id']+'. Re-fetch the source and verify every quote, required name/address and changed facts. This is evidence validation, not publication approval.',agents['quality'],parent=row['id']);p['quality_id']=q['id'];p['quality_identifier']=q['identifier'];save()
  q=start_wait(q,'quality');p['quality_status']=q['status'];save();emit({'provider':p['name'],'quality_status':q['status']})
 lines=['## Five-provider batch results','','Each task contains its own evidence and missing facts. No listing was published.','']
 for p in state['providers']:lines.append('- '+p['name']+': '+p['research_identifier']+' ('+p.get('research_status','unknown')+'); evidence check '+p.get('quality_identifier','not created')+' ('+p.get('quality_status','not run')+').')
 api('/issues/'+parent['id']+'/comments',{'body':'\n'.join(lines)})
 api('/issues/'+parent['id'],{'status':'in_review'},'PATCH');state['status']='in_review';save();emit({'batch_status':state['status']})
except Exception as e:
 state['status']='needs_attention';state['error']=str(e)[:900];save();emit({'error':state['error']});raise
