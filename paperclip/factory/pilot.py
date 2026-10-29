"""Owner-side live pilot. Run on the Paperclip host, producing reviewable tasks."""
import json,pathlib,time,urllib.request,urllib.error
ROOT=pathlib.Path('/opt/narimato-factory');config=json.loads((ROOT/'factory.json').read_text());company=config['company_id'];project=next(key for key,val in config['projects'].items() if val=='ClassScout')
def call(path,data=None,method=None):
 req=urllib.request.Request('http://127.0.0.1:3100/api'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
 except urllib.error.HTTPError as error:raise RuntimeError(str(error.code)+' '+error.read().decode()[:1800]) from None
agent=next(key for key,val in config['agents'].items() if val['role']=='research')
issues=call('/companies/'+company+'/issues');issues=issues.get('issues',issues.get('data',[])) if isinstance(issues,dict) else issues
title='[Factory test] Research Dodge YMCA for ClassScout review'
issue=next((row for row in issues if row['title']==title),None)
if issue is None:issue=call('/companies/'+company+'/issues',{'projectId':project,'title':title,'description':'Research this official provider page for a ClassScout listing draft: https://ymcanyc.org/locations/dodge-ymca\n\nCapture only explicitly supported provider facts: name, address, phone, email, opening hours, price and activities. Keep missing facts unknown and include exact source evidence. Prepare a draft for human review. Do not publish or contact the provider.','status':'backlog','assigneeAgentId':agent,'reviewPolicy':'human_only','responsibleUserId':'local-board','priority':'medium'})
# Wake explicitly; recurring timers remain disabled.
run=call('/agents/'+agent+'/wakeup',{'source':'on_demand','reason':'Factory source-page acceptance pilot','payload':{'issueId':issue['id']},'forceFreshSession':True})
(ROOT/'pilot-start.json').write_text(json.dumps({'issue':issue,'wakeup':run},indent=2)+'\n')
print(json.dumps({'issue_id':issue['id'],'identifier':issue.get('identifier'),'run_id':run.get('id'),'status':run.get('status')},indent=2),flush=True)
