"""Idempotent owner-side factory scaffolding. Run on the Paperclip server."""
import json,pathlib,urllib.request,urllib.error
ROOT=pathlib.Path('/opt/narimato-factory');BASE='http://127.0.0.1:3100/api'
def api(path,data=None,method=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
 except urllib.error.HTTPError as error:raise RuntimeError(str(error.code)+' '+error.read().decode()[:1500]) from None
company=json.loads(pathlib.Path('/opt/narimato-paperclip/company.json').read_text())['id']
projects=api('/companies/'+company+'/projects');agents=api('/companies/'+company+'/agents')
if isinstance(projects,dict):projects=projects.get('projects',projects.get('data',[]))
if isinstance(agents,dict):agents=agents.get('agents',agents.get('data',[]))
brands={'Sales Lead Generator':'Partner pipeline and internal sales preparation through the brand-scoped SLG MCP connector. Workspace and sending configuration must be confirmed before authenticated operation.','ClassScout':'NYC kids and family activities. Prepare source-backed proposals for the existing ClassScout content pipeline; publication uses its existing quality and approval rules.','Sportolok':'Sports-related research and content proposals. Brand schema and target markets require owner confirmation.','Management':'Research proposals appropriate to Management’s confirmed business model. Schema and integrations require owner confirmation.','Padel Africa':'Source-backed research on padel clubs, courts, coaches and events in Africa.','Factory Operations':'Operating charter, integrations, quality rules and owner decisions for the portfolio factory.'}
config={'company_id':company,'reviewer_user_id':'local-board','mode':'source research with budgeted Brave discovery','projects':{},'agents':{},'pilot_brand':'ClassScout','publishing_enabled':True,'search_enabled':pathlib.Path('/etc/paperclip-brave.env').exists(),'search_candidate_limit':2,'outreach_enabled':False,'max_source_pages_per_task':2,'operational_workflows_enabled':True,'catalog_batch_size':3,'audit_page_limit':6,'audit_seed_urls':['https://getyourfield.com/','https://getyourfield.com/nyc/classes','https://getyourfield.com/nyc/family-events']}
for name,description in brands.items():
 project=next((row for row in projects if row['name']==name),None)
 if project is None:project=api('/companies/'+company+'/projects',{'name':name,'description':description})
 config['projects'][project['id']]=name
roles=[('Research Analyst','researcher','research','Reads official source pages and prepares listing drafts with exact supporting evidence.'),('Content Quality Reviewer','qa','quality','Re-fetches source pages, verifies stored evidence and flags changed or missing fields before human review.'),('Support Drafter','general','support','Prepares source-backed information for human support replies. Does not contact customers.'),('Publication Coordinator','general','publication','Prepares complete source-backed ClassScout listings and sends only exact human-approved packets through the canonical publish gate; verifies receipts.')]
roles.append(('Search Coordinator','researcher','search','Consumes the shared quota-controlled Brave queue, verifies source pages and hands off bounded research tasks. No publication or outreach.'))
for name,role,kind,capabilities in roles:
 agent=next((row for row in agents if row['name']==name),None)
 payload={'name':name,'role':role,'title':name,'capabilities':capabilities,'adapterType':'process','adapterConfig':{'command':'python3','args':['/paperclip/factory/bridge.py'],'cwd':'/paperclip/factory','timeoutSec':960,'graceSec':15},'runtimeConfig':{'heartbeat':{'enabled':kind=='search' and config['search_enabled'],'intervalSec':1800 if kind=='search' else 0,'wakeOnDemand':True,'maxConcurrentRuns':1}},'permissions':{'canCreateAgents':False,'canCreateSkills':False},'budgetMonthlyCents':0}
 if agent is None:
  hire=api('/companies/'+company+'/agent-hires',payload);agent=hire['agent']
  if hire.get('approval'):api('/approvals/'+hire['approval']['id']+'/approve',{'decisionNote':'Owner-side provisioning of fixed factory roles for the requested workflow; listing publication still requires its separate human-only confirmation.'})
 else:
  # Preserve existing agent IDs; updating these known factory roles is deliberate.
  agent=api('/agents/'+agent['id'],{key:value for key,value in payload.items() if key!='name'},'PATCH')
 config['agents'][agent['id']]={'name':name,'role':kind}
if (ROOT/'factory.json').exists():
 previous=json.loads((ROOT/'factory.json').read_text())
 for field in ['automatic_quality_gate','growth_mode','search_candidate_limit','padel_enabled','reliability_enabled','padel_discovery_enabled','engine_clients','program_updates_enabled','sales']:
  if field in previous:config[field]=previous[field]
ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'factory.json').write_text(json.dumps(config,indent=2)+'\n');(ROOT/'factory.json').chmod(0o644)
api('/companies/'+company,{'requireBoardApprovalForNewAgents':True},'PATCH')
existing=api('/companies/'+company+'/issues')
if isinstance(existing,dict):existing=existing.get('issues',existing.get('data',[]))
ops=next(key for key,value in config['projects'].items() if value=='Factory Operations')
charter='Factory operating charter — Phase 1'
if not any(row['title']==charter for row in existing):
 api('/companies/'+company+'/issues',{'title':charter,'projectId':ops,'status':'backlog','priority':'high','reviewPolicy':'human_only','responsibleUserId':'local-board','description':'Build a portfolio content factory across ClassScout, Sportolok, Management and Padel Africa. Start with ClassScout official source-page research. Research Analyst prepares quoted facts, Content Quality Reviewer re-checks evidence, and Support Drafter prepares information for owner review. All output is draft-only. Existing ClassScout discovery and publication safeguards remain authoritative. No automated publishing, customer outreach, purchases or contractual decisions. Agent runs are on demand; recurring discovery is not enabled. Success measures: supported fields, missing evidence, factual errors, review acceptance and time per accepted draft.'})
for title,description in [('Connect ClassScout review and publishing handoff','Connect factory-approved proposals to the existing ClassScout content pipeline. Inspect that application’s instructions, schema and publishing guards before any integration. No production database write is authorized by this placeholder.'),('Define approved support knowledge and escalation rules','Choose source documents, owners and escalation rules before using drafts for customer replies. External delivery remains disabled.'),('Define pilot volume and recurring cadence','Review pilot results, shared CPU capacity and owner business priorities before scheduling recurring work. Source-page research requires explicit links; broad discovery needs a search provider.'),('Confirm Sportolok, Management and Padel Africa source schemas','Confirm each brand’s actual business model, target geography, approved source pages and content fields before live research is assigned.')]:
 if not any(row['title']==title for row in existing):api('/companies/'+company+'/issues',{'title':title,'projectId':ops,'description':description,'status':'backlog','priority':'medium','reviewPolicy':'human_only','responsibleUserId':'local-board'})
print(json.dumps({'company':company,'projects':config['projects'],'agents':config['agents'],'source_mode':config['mode']},indent=2))
