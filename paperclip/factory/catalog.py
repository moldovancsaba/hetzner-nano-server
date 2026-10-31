"""Bounded ClassScout catalog reads and independently checked public listing facts."""
import datetime,hashlib,json,re,time,urllib.parse,urllib.request
from publishing import ClassScout,sha,norm
from net import canonical_url

PUBLIC_FIELDS=('id','name','website','address','phone','email','borough','neighborhood','city','category','activityTypes','lastVerifiedAt','shortDescription','longDescription','price','pricePerClass','recurringPrograms','ageMinMonths','ageMaxMonths','fieldVerifications')
# Reads one 'Name: value' line from a task description. Only the text before the first 'Question:' line is searched, so a
# customer question cannot inject 'Factory workflow:' or 'Catalog provider:' lines. A repeated field name raises instead
# of picking one. Workflow routing (operational.workflow) and every other caller of this function depend on it.
def field(issue,name,default=''):
 text=issue.get('description') or ''
 if name=='Question':
  m=re.search(r'^Question:\s*(.*)',text,re.M|re.S);return m[1].strip() if m else default
 text=re.split(r'^Question:',text,maxsplit=1,flags=re.M)[0]
 matches=re.findall(r'^'+re.escape(name)+r':\s*(.+?)\s*$',text,re.M)
 if len(matches)>1:raise ValueError('Repeated '+name+' fields need clarification')
 return matches[0].strip() if matches else default

def clean_id(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,140}',value):raise ValueError('Choose an exact catalog provider ID')
 return value
def public_record(row):
 result={k:row[k] for k in PUBLIC_FIELDS if k in row};result['id']=clean_id(row.get('id'));result['owner_managed']=bool(row.get('ownerSub') or row.get('ownerManaged') or row.get('ownerManagedAt')) or row.get('claimStatus') in {'claimed','claim_pending'}
 return result
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class Catalog:
 def __init__(self):self.client=ClassScout()
 def get(self,id):
  row=self.client.existing_provider(clean_id(id))
  if row is None:raise ValueError('Catalog provider was not found')
  return public_record(row)
 def public_get(self,id,verification=''):
  clean_id(id)
  if verification and not re.fullmatch(r'[a-f0-9]{64}',verification):raise ValueError('Invalid verification reference')
  url=ClassScout.BASE+'/api/public/providers/'+urllib.parse.quote(id,safe='')+'?city=nyc&verification='+verification
  with urllib.request.build_opener(NoRedirect).open(url,timeout=30) as r:
   raw=r.read(2*1024*1024+1)
   if len(raw)>2*1024*1024:raise ValueError('Catalog detail exceeded its response bound')
   value=json.loads(raw).get('provider')
  if not isinstance(value,dict) or value.get('id')!=id:raise ValueError('Public catalog identity is not confirmed')
  return public_record(value)
 def page(self,page=1):
  if not isinstance(page,int) or not 1<=page<=500:raise ValueError('Catalog page must be between 1 and 500')
  url=ClassScout.BASE+'/api/public/providers?city=nyc&page='+str(page)
  with urllib.request.build_opener(NoRedirect).open(url,timeout=30) as response:
   raw=response.read(2*1024*1024+1)
   if len(raw)>2*1024*1024:raise ValueError('Catalog page exceeded the response bound')
   rows=json.loads(raw);more=response.headers.get('X-Has-More','false').lower()=='true'
  if not isinstance(rows,list) or len(rows)>20:raise ValueError('Catalog page contract changed; expected at most twenty records')
  return [public_record(r) for r in rows],more

def initialize(database):
 with database() as db:db.executescript('''
 CREATE TABLE IF NOT EXISTS catalog_cursor(id INTEGER PRIMARY KEY CHECK(id=1),page INTEGER,offset INTEGER);
 INSERT OR IGNORE INTO catalog_cursor VALUES(1,1,0);
 CREATE TABLE IF NOT EXISTS catalog_checks(provider_id TEXT PRIMARY KEY,issue_id TEXT,catalog_hash TEXT,checked_at REAL,result_json TEXT);
 CREATE TABLE IF NOT EXISTS workflow_reports(issue_id TEXT PRIMARY KEY,kind TEXT,created_at REAL,result_json TEXT);
 ''')
def resolve_provider(issue,database):
 explicit=field(issue,'Catalog provider')
 if explicit:return clean_id(explicit)
 name=field(issue,'Provider name');link=field(issue,'Listing URL') or (name if name.startswith('https://') else '')
 if link:
  url=urllib.parse.urlsplit(canonical_url(link))
  if url.scheme!='https' or url.hostname not in {'classscout.ai','getyourfield.com'}:raise ValueError('Use a ClassScout public listing link')
  return clean_id(urllib.parse.unquote(url.path.rstrip('/').split('/')[-1]))
 name=field(issue,'Provider name')
 if not 2<=len(name)<=160:raise ValueError('Choose a provider name or paste its ClassScout listing link')
 initialize(database)
 with database() as db:rows=db.execute("SELECT provider_id,result_json FROM catalog_checks WHERE lower(json_extract(result_json,'$.provider.name'))=lower(?) LIMIT 20",(name,)).fetchall()
 address=field(issue,'Provider address')
 if address:
  from refresh import address_key
  rows=[r for r in rows if address_key(address)==address_key(json.loads(r['result_json'])['provider'].get('address',''))]
 if len(rows)!=1:raise ValueError('Provider name is not uniquely verified yet. Paste its ClassScout listing link or specify the street address.')
 return rows[0]['provider_id']

def save_report(database,issue,kind,result):
 initialize(database)
 with database() as db:db.execute('INSERT INTO workflow_reports VALUES(?,?,?,?) ON CONFLICT(issue_id) DO UPDATE SET kind=excluded.kind,created_at=excluded.created_at,result_json=excluded.result_json',(issue['id'],kind,time.time(),json.dumps(result)))
def snippet(text,value):
 target=norm(value);lines=text.splitlines()
 for line in lines:
  if target and target in norm(line):
   at=norm(line).find(target);return line[max(0,at-35):at+len(str(value))+65][:400]
 return None

def checked_facts(row,page):
 facts=[];missing=[]
 for key in ['name','address','phone','email']:
  value=row.get(key)
  if not value:continue
  quote=snippet(page['text'],value)
  if key=='phone' and not quote:
   digits=lambda x:re.sub(r'\D','',x)[-10:]
   for candidate in re.findall(r'(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}',page['text']):
    if digits(value)==digits(candidate):quote=snippet(page['text'],candidate);value=candidate;break
  if quote:facts.append({'field':key,'value':value,'quote':quote})
  else:missing.append(key)
 for key in ['name','address']:
  if not row.get(key) and key not in missing:missing.append(key)
 return facts,missing

def verify(row,web):
 url=canonical_url(row.get('website') or '');page=web.page(url)
 if urllib.parse.urlsplit(page['url']).hostname.removeprefix('www.')!=urllib.parse.urlsplit(url).hostname.removeprefix('www.'):raise ValueError('Official source redirected to another host; confirm provider identity')
 facts,missing=checked_facts(row,page)
 return {'provider':row,'source_url':page['url'],'source_sha256':page['sha256'],'checked_at':page['fetched_at'],'facts':facts,'unconfirmed_fields':missing,'status':'owner_review_required' if row['owner_managed'] else 'needs_source_research' if missing else 'source_fields_verified','scope':'Name, address and listed contacts only; prices, age groups and class timetables are not certified by this contact check.'}

def run(issue,board,config,web,database,execution,client=None):
 initialize(database);client=client or Catalog();explicit=field(issue,'Catalog IDs');maximum=min(3,max(1,int(config.get('catalog_batch_size',3))));selected=[];more=False;next_cursor=None
 if explicit:
  ids=list(dict.fromkeys(clean_id(x.strip()) for x in explicit.split(',')))
  if not 1<=len(ids)<=maximum:raise ValueError('A catalog check accepts at most '+str(maximum)+' provider IDs')
  selected=ids
 else:
  with database() as db:cursor=db.execute('SELECT page,offset FROM catalog_cursor WHERE id=1').fetchone()
  page,offset=cursor;rows,more=client.page(page)
  selected=[r['id'] for r in rows[offset:offset+maximum]];offset+=len(selected)
  next_cursor=(page+1 if more else 1,0) if offset>=len(rows) else (page,offset)
  if next_cursor[0]>500:next_cursor=(1,0)
 results=[];children=[]
 import search_workflow
 paused=search_workflow.research_backlog(board,config,database)>=10
 for id in selected:
  try:
   row=client.get(id);result=verify(row,web)
   with database() as db:
    prior=db.execute('SELECT result_json,checked_at,catalog_hash FROM catalog_checks WHERE provider_id=?',(id,)).fetchone()
    db.execute('INSERT INTO catalog_checks VALUES(?,?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET issue_id=excluded.issue_id,catalog_hash=excluded.catalog_hash,checked_at=excluded.checked_at,result_json=excluded.result_json',(id,issue['id'],sha(row),time.time(),json.dumps(result)))
   prior_report=json.loads(prior['result_json']) if prior else {}
   last_requested=prior_report.get('research_requested_at',0)
   result['research_requested_at']=last_requested
   same_gap=prior and prior['catalog_hash']==sha(row) and time.time()-last_requested<7*86400 and prior_report.get('unconfirmed_fields')==result['unconfirmed_fields']
   import quality_gate
   content_due=quality_gate.enabled(config,issue) and result['status']=='source_fields_verified'
   if (result['status']=='needs_source_research' or content_due) and not same_gap and not paused and len(children)<2:
    researcher=next(k for k,v in config['agents'].items() if v['role']=='research');prefix='[Factory test] ' if issue['title'].startswith('[Factory test]') else ''
    child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'catalog-research-'+id+'-'+result['source_sha256']+'-'+str(int(time.time()//(7*86400))),'title':prefix+'Verify listing facts: '+row.get('name',id)[:125],'description':'Factory workflow: source_research\nCatalog provider: '+id+'\n\nResearch '+result['source_url']+' for supported name, exact street address and contact information. Keep program/branch scope explicit. Missing or different contacts require review, not an overwrite. Unknown values stay unknown.','projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':researcher,'reviewPolicy':'human_only'})
    children.append(child['identifier']);result['research_task']=child['identifier'];result['research_requested_at']=time.time()
   with database() as db:db.execute('UPDATE catalog_checks SET result_json=? WHERE provider_id=?',(json.dumps(result),id))
  except Exception as error:result={'provider_id':id,'status':'source_unavailable','reason':type(error).__name__,'action':'Use an accessible official source; no fact was inferred and no catalog write occurred.'}
  results.append(result)
 if next_cursor:
  with database() as db:db.execute('UPDATE catalog_cursor SET page=?,offset=? WHERE id=1',next_cursor)
 report={'checked':results,'research_tasks':children,'catalog_writes':0,'research_paused_for_review_backlog':paused,'next_cursor':next_cursor};save_report(database,issue,'verify_catalog',report)
 from worker import safe
 lines=['## Catalog verification','','Checked '+str(len(results))+' existing listings. New research tasks: '+(', '.join(children) or 'none')+'. No catalog record was changed.','']
 for r in results:
  p=r.get('provider',{});lines+=['- '+safe(p.get('name',r.get('provider_id','Provider')))+': '+r['status'].replace('_',' ')+('. Unconfirmed: '+', '.join(r['unconfirmed_fields']) if r.get('unconfirmed_fields') else '')+('. Research: '+r['research_task'] if r.get('research_task') else '')]
 lines+=['','This checks identity and contacts against official pages. Source absence is an evidence gap, not proof a catalog value is wrong. Claimed listings stay in their owner workflow. Eligible contact and content changes pass the configured automatic quality gate; exceptions remain held.']
 return {'stage':'catalog_review','markdown':'\n'.join(lines),'entities':[],'report':report,'final_status':'done'}
