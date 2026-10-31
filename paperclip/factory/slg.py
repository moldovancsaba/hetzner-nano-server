"""Brand-bound SLG MCP connector and bounded sales preparation workflows."""
import datetime,json,os,re,time,urllib.request,urllib.error,uuid
import catalog,publishing
ORIGIN='https://salesleadgenerator.vercel.app'
READ={'slg_search_leads','slg_get_lead','slg_get_pre_call_briefing','slg_list_pipeline_stages'}
WRITE={'slg_capture_lead','slg_update_lead_stage'}
TOOLS=READ|WRITE
STAGES={'DISCOVERED','QUALIFIED','ENGAGED','PROPOSAL','WON','LOST','BACKLOG'}
class Client:
 def __init__(self,brand,key=None):
  if not re.fullmatch('[a-z][a-z0-9-]{1,48}',brand or ''):raise ValueError('An explicit SLG workspace is required')
  self.brand=brand;self.key=key
 def credential(self):
  if self.key:return self.key
  try:keys=json.loads(os.environ.get('SLG_SCOPED_KEYS','{}'))
  except ValueError:raise ValueError('SLG scoped credential is not installed') from None
  key=keys.get(self.brand,'')
  if not re.fullmatch(r'slg_[A-Za-z0-9_-]{30,100}',key):raise ValueError('SLG scoped credential missing for this workspace')
  return key
 def transport(self,body,authenticated=True):
  headers={'Content-Type':'application/json','X-Request-Purpose':'test' if getattr(self,'test',False) else 'production'}
  if authenticated:headers['x-api-key']=self.credential()
  request=urllib.request.Request(ORIGIN+'/api/mcp',data=json.dumps(body).encode(),headers=headers)
  try:
   with urllib.request.build_opener(catalog.NoRedirect).open(request,timeout=45) as response:
    raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('SLG response exceeds bound')
    value=json.loads(raw)
  except urllib.error.HTTPError as error:raise ValueError('SLG refused request (HTTP '+str(error.code)+')') from None
  except Exception:raise ValueError('SLG transport failed; no automatic replay') from None
  if not isinstance(value,dict) or value.get('jsonrpc')!='2.0' or value.get('id')!=body['id'] or value.get('error'):raise ValueError('SLG returned an invalid or failed RPC response')
  return value.get('result',{})
 def discover(self):
  result=self.transport({'jsonrpc':'2.0','id':uuid.uuid4().hex,'method':'tools/list'},False)
  found={t.get('name') for t in result.get('tools',[])}
  if not TOOLS.issubset(found):raise ValueError('SLG required tool contract is incomplete')
  return sorted(found)
 def arguments(self,name,args):
  if name not in TOOLS or not isinstance(args,dict):raise ValueError('Unsupported SLG tool')
  args=dict(args)
  if args.get('brand',self.brand)!=self.brand:raise ValueError('Cross-workspace SLG access refused')
  args['brand']=self.brand
  if name in {'slg_get_lead','slg_get_pre_call_briefing','slg_update_lead_stage'} and not re.fullmatch('[a-fA-F0-9]{24}',str(args.get('leadId',''))):raise ValueError('Exact SLG lead ID required')
  if name=='slg_search_leads':
   args['limit']=min(20,max(1,int(args.get('limit',10))))
   if 'stage' in args and args['stage'] not in STAGES:raise ValueError('Invalid SLG stage')
  if name=='slg_update_lead_stage':
   if args.get('stage') not in STAGES:raise ValueError('Invalid SLG stage')
   if args['stage']=='LOST' and not args.get('declineReason'):raise ValueError('LOST requires a recorded reason')
  if name=='slg_capture_lead':
   # Server defaults country, contact name and decision-maker status when omitted.
   # Those defaults are not safe evidence for an unattended business capture.
   for field in ['url','companyName','name','jobTitle','location','buyingRole']:
    if not isinstance(args.get(field),str) or not args[field].strip():raise ValueError('Evidenced SLG capture requires '+field)
   if args['buyingRole'] not in {'economic_buyer','champion','decision_maker'}:raise ValueError('Capture cannot infer a decision maker')
   if not args['url'].startswith('https://'):raise ValueError('Capture requires an exact HTTPS source')
  return args
 def execute(self,name,args,write=False):
  if name in WRITE and not write:raise ValueError('SLG mutations require the durable write path')
  args=self.arguments(name,args)
  result=self.transport({'jsonrpc':'2.0','id':uuid.uuid4().hex,'method':'tools/call','params':{'name':name,'arguments':args}})
  if result.get('isError'):raise ValueError('SLG tool refused the operation; inspect the exact workspace contract')
  parts=[x['text'] for x in result.get('content',[]) if x.get('type')=='text' and isinstance(x.get('text'),str)]
  if len(parts)!=1:raise ValueError('SLG tool returned an unsupported content shape')
  if name=='slg_get_pre_call_briefing':return {'briefing':parts[0]}
  try:return json.loads(parts[0])
  except ValueError:raise ValueError('SLG tool returned malformed data') from None

def initialize(database):
 with database() as db:db.executescript('''CREATE TABLE IF NOT EXISTS slg_packets(packet_hash TEXT PRIMARY KEY,brand TEXT,issue_id TEXT,tool TEXT,object_key TEXT,status TEXT,request_json TEXT,receipt_json TEXT,created_at REAL);
 CREATE TABLE IF NOT EXISTS slg_briefings(brand TEXT,lead_id TEXT,source_hash TEXT,briefing TEXT,checked_at REAL,PRIMARY KEY(brand,lead_id));''')

# Not called by any routine or workflow in this tree (run() only connects, reviews the pipeline and prepares briefings).
# The CRM write path is built and tested but unreachable until a workflow uses it.
def mutate(client,name,args,issue,board,config,database,execution):
 """CRM writes are never equated to sent email or a won sale."""
 initialize(database);settings=config.get('sales',{})
 if name not in WRITE or not settings.get('crm_writes_enabled') or client.brand not in settings.get('brands',[]):raise ValueError('SLG CRM writes are not enabled for this workspace')
 args=client.arguments(name,args);key=args.get('leadId') or publishing.sha({'companyName':args['companyName'],'url':args['url']});ph=publishing.sha({'brand':client.brand,'tool':name,'arguments':args})
 with database() as db:
  old=db.execute('SELECT * FROM slg_packets WHERE packet_hash=?',(ph,)).fetchone()
  unresolved=db.execute("SELECT 1 FROM slg_packets WHERE brand=? AND object_key=? AND status IN ('submitting','uncertain')",(client.brand,key)).fetchone()
 if unresolved:raise ValueError('Uncertain SLG write; reconcile the saved receipt before retrying')
 if old:return json.loads(old['receipt_json'])
 publishing.ensure_execution(issue,board,config,execution,publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']}))
 with database() as db:
  db.execute('BEGIN IMMEDIATE')
  if db.execute("SELECT 1 FROM slg_packets WHERE brand=? AND object_key=? AND status IN ('submitting','uncertain')",(client.brand,key)).fetchone():raise ValueError('SLG write already in flight')
  db.execute('INSERT INTO slg_packets VALUES(?,?,?,?,?,?,?,?,?)',(ph,client.brand,issue['id'],name,key,'submitting',json.dumps(args),None,time.time()))
 try:
  receipt=client.execute(name,args,write=True)
  if receipt.get('ok') is not True or receipt.get('brand')!=client.brand or not re.fullmatch('[a-fA-F0-9]{24}',str(receipt.get('leadId',''))):raise ValueError('SLG write receipt is incomplete')
  if name=='slg_update_lead_stage' and (receipt['leadId']!=args['leadId'] or receipt.get('stage')!=args['stage']):raise ValueError('SLG stage receipt does not match request')
  current=client.execute('slg_get_lead',{'leadId':receipt['leadId']})
  actual=current.get('_id');actual=actual.get('$oid') if isinstance(actual,dict) else actual
  if actual!=receipt['leadId'] or name=='slg_update_lead_stage' and current.get('kanbanColumn')!=args['stage']:raise ValueError('SLG readback did not confirm the write')
  with database() as db:db.execute("UPDATE slg_packets SET status='applied',receipt_json=? WHERE packet_hash=?",(json.dumps(receipt),ph))
  return receipt
 except Exception:
  with database() as db:db.execute("UPDATE slg_packets SET status='uncertain' WHERE packet_hash=?",(ph,))
  raise ValueError('SLG write outcome uncertain; automatic replay stopped') from None

def done(stage,markdown):return {'stage':stage,'entities':[],'final_status':'done','automatic_progress':True,'markdown':markdown}
def run(issue,board,config,web,database,execution):
 if config['projects'].get(issue.get('projectId'))!='Sales Lead Generator':raise ValueError('SLG workflow requires its own project')
 settings=config.get('sales',{});brand=catalog.field(issue,'SLG workspace')
 if not brand or brand not in settings.get('brands',[]):raise ValueError('Choose and configure the intended SLG workspace before sales work')
 client=Client(brand);kind=catalog.field(issue,'Factory workflow');initialize(database)
 if kind=='sales_connection':
  tools=client.discover();client.execute('slg_list_pipeline_stages',{})
  report={'brand':brand,'status':'authenticated','tools':tools,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'delivery':'drafts_only'}
  catalog.save_report(database,issue,'sales_connection',report)
  return done(kind,'SLG authenticated workspace verified: '+brand+'. Six tools available. Customer delivery remains unconfigured; no message sent.')
 if kind=='sales_pipeline':
  results={};contacts=0
  for stage in sorted(STAGES):
   value=client.execute('slg_search_leads',{'stage':stage,'limit':20});leads=value.get('leads')
   if not isinstance(leads,list) or len(leads)>20:raise ValueError('Invalid bounded SLG search response')
   results[stage]={'sample':len(leads),'at_limit':len(leads)==20};contacts+=sum(x.get('contactsCount',0)>0 for x in leads)
  report={'brand':brand,'stages':results,'sample_with_contacts':contacts,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'delivery':'drafts_only','note':'At most 20 per stage; these are samples, not total pipeline counts. No stage or lead changes.'}
  catalog.save_report(database,issue,'sales_pipeline',report)
  return done(kind,'SLG bounded pipeline review for '+brand+':\n\n'+'\n'.join('- '+stage+': '+str(v['sample'])+(' or more' if v['at_limit'] else '') for stage,v in results.items())+'\n\nSamples, not full totals. No contact or stage changes and no messages sent.')
 if kind=='sales_briefing':
  lead_id=catalog.field(issue,'SLG lead ID');lead=client.execute('slg_get_lead',{'leadId':lead_id});brief=client.execute('slg_get_pre_call_briefing',{'leadId':lead_id})['briefing']
  source_hash=publishing.sha(lead)
  with database() as db:db.execute('INSERT INTO slg_briefings VALUES(?,?,?,?,?) ON CONFLICT(brand,lead_id) DO UPDATE SET source_hash=excluded.source_hash,briefing=excluded.briefing,checked_at=excluded.checked_at',(brand,lead_id,source_hash,brief,time.time()))
  return done(kind,'## Internal partner briefing\n\nWorkspace: '+brand+'; lead: '+lead_id+'.\n\n'+brief+'\n\nInternal preparation from the stored CRM record, not independent verification. No outreach sent or sales stage changed.')
 raise ValueError('Unsupported sales workflow')
