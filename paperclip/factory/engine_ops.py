"""Shared Management-engine operations, scoped by each authenticated vertical contract."""
import datetime,json,re,time,urllib.request,urllib.parse,urllib.error
import catalog,evidence,padel,publishing,quality_gate,venue_identity
SPECS={'padel-africa':{'origin':padel.ORIGIN,'project':'Padel Africa'},'sportolok':{'origin':'https://sportolok.vercel.app','project':'Sportolok'}}
# Inherits token() from padel.Client, so the Padel SSO client-credentials token (cached in one module-level variable,
# not per engine) is also sent to the other engine origin, sportolok.vercel.app. This assumes both engines accept that identity.
class Client(padel.Client):
 def __init__(self,slug):
  if slug not in SPECS:raise ValueError('Unknown engine client')
  self.slug=slug;self.origin=SPECS[slug]['origin']
 def call(self,path,body=None):
  if path not in {'/api/machine/catalog','/api/ingest'}:raise ValueError('Unsupported engine endpoint')
  if body is not None:
   intake=set(body)=={'id','sourceText','sourceUrl','sourcePool'} and body['sourcePool']=='ingest' and len(body['sourceText'])<=50000
   publish=set(body)=={'id','forcePublish','reason'} and body['forcePublish'] is True and 12<=len(body['reason'])<=500
   if not (intake or publish):raise ValueError('Only evidenced intake and engine-governed soft publication are allowed')
  request=urllib.request.Request(self.origin+path,data=json.dumps(body).encode() if body else None,headers={'Authorization':'Bearer '+self.token(),'Content-Type':'application/json'})
  with urllib.request.build_opener(catalog.NoRedirect).open(request,timeout=45) as r:
   raw=r.read(8*1024*1024+1)
   if len(raw)>8*1024*1024:raise ValueError('Engine response exceeded bounds')
   return json.loads(raw)
 def catalog(self):
  value=self.call('/api/machine/catalog');v=value.get('vertical',{});scope=v.get('territoryScope',{})
  if v.get('slug')!=self.slug or not v.get('taxonomy') or not v.get('locales') or scope.get('kind') not in {'countries','continent'}:raise ValueError('Engine tenant or declared scope unavailable')
  if self.slug=='padel-africa' and scope!={'kind':'continent','continent':'Africa'}:raise ValueError('Padel Africa territory changed; review contract')
  if self.slug=='sportolok' and ('hu-HU' not in v['locales'] or 'HU' not in scope.get('countries',[])):raise ValueError('Sportolok language or home territory changed')
  if len(value.get('catalog',{}).get('listings',[]))>500:raise ValueError('Engine catalog bound changed')
  return value

def initialize(database):
 with database() as db:db.executescript('''CREATE TABLE IF NOT EXISTS engine_packets(packet_hash TEXT PRIMARY KEY,slug TEXT,issue_id TEXT,item_id TEXT,kind TEXT,status TEXT,body_json TEXT,proof_json TEXT,receipt_json TEXT,created_at REAL);
 CREATE TABLE IF NOT EXISTS engine_attempts(slug TEXT,item_id TEXT,attempted_at REAL,result_json TEXT,PRIMARY KEY(slug,item_id));
 CREATE TABLE IF NOT EXISTS engine_cursor(slug TEXT PRIMARY KEY,position INTEGER);''')

def slug_for(issue,config):
 brand=config['projects'].get(issue.get('projectId'));slug=next((k for k,v in SPECS.items() if v['project']==brand),None)
 if not slug or not config.get('engine_clients',{}).get(slug):raise ValueError('Engine client is not enabled for this project')
 return slug

def execute_guard(issue,board,config,execution):
 publishing.ensure_execution(issue,board,config,execution,publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']}))

def candidate(issue,board,config,web,database,execution,client=None):
 initialize(database);slug=slug_for(issue,config);client=client or Client(slug);value=client.catalog();v=value['vertical'];url=catalog.field(issue,'Official source URL')
 try:identity=venue_identity.resolve(url,web,v)
 except ValueError:
  depth=catalog.field(issue,'Branch depth','0')
  if depth!='0':
   if not venue_identity.provider_host(evidence.host(url)):return done('engine_source_rejected','Screened out: a third-party directory page cannot establish the official venue identity. No listing was accepted.')
   raise
  links,source_hash=venue_identity.branch_links(url,web)
  if not links:
   if not venue_identity.provider_host(evidence.host(url)):return done('engine_source_rejected','Screened out: third-party directory has no usable first-party venue link. No venue facts or listing were accepted.')
   raise
  from company_ops import queue_dispatch,role
  for target in links:
   key='venue-branch-'+slug+'-'+publishing.sha({'url':target,'source_hash':source_hash})
   queue_dispatch(database,key,issue,{'idempotencyKey':key,'title':'Verify specific venue page: '+urllib.parse.urlsplit(target).path[-90:],'description':'Factory workflow: engine_candidate\nOfficial source URL: '+target+'\nBranch depth: 1','projectId':issue['projectId'],'status':'todo','assigneeAgentId':role(config,'support'),'reviewPolicy':'anyone'})
  return done('engine_source_expanded','Staged '+str(len(links))+' specific first-party venue links for independent checks. No directory facts, search locality or new listing were assumed.')
 for row in value['catalog'].get('listings',[]):
  source=row.get('source',{}).get('sourceUrl','')
  address=row.get('venue',{}).get('address',{})
  same_place=publishing.norm(address.get('line1',''))==publishing.norm(identity['address']) and venue_identity.key(address.get('locality'))==venue_identity.key(identity['city']) and address.get('countryCode')==identity['country']
  if same_place and (source==identity['source_url'] or venue_identity.key(row.get('name'))==venue_identity.key(identity['name'])):
   return done('engine_known_source','The exact source or physical venue already exists. No new intake or overwrite was sent.')
 page=web.page(identity['source_url'])
 if page['sha256']!=identity['source_hash']:raise ValueError('Engine candidate source changed; recheck before intake')
 fresh=venue_identity.identities(page,v['territoryScope'])
 if not any(x['name']==identity['name'] and x['address']==identity['address'] and x['country']==identity['country'] for x in fresh):raise ValueError('Structured venue identity changed before intake')
 text=page['text'][:46000]
 if identity.get('structured'):text+='\nStructured organization data from this official page:\n'+json.dumps(identity['structured'],ensure_ascii=False)[:3000]
 body={'id':'paperclip-'+slug+'-'+publishing.sha({'url':page['url'],'address':identity['address']})[:24],'sourceText':text,'sourceUrl':page['url'],'sourcePool':'ingest'}
 if issue['title'].startswith('[Factory test]'):raise ValueError('Synthetic tests cannot create engine cards')
 receipt,state=write_once(issue,board,config,database,execution,client,slug,'intake',body,identity)
 return done('engine_intake_'+state,'Official-source evidence '+('accepted by the engine' if state=='accepted' else 'requires reconciliation')+'. Intake acceptance is separate from public publication.')

# Order: refuse if an earlier write for this item is unresolved; run the execution guard; record the gate decision; reserve
# the daily slot and insert the 'submitting' row in one transaction; only then send. An HTTP 4xx answer is a refusal
# ('held'); any other unconfirmed outcome is 'uncertain' and is never replayed. No human-approval mode exists on this path.
def write_once(issue,board,config,database,execution,client,slug,kind,body,proof):
 initialize(database);ph=publishing.sha({'slug':slug,'kind':kind,'body':body,'proof':proof});item=body['id']
 with database() as db:
  previous=db.execute('SELECT status,receipt_json FROM engine_packets WHERE packet_hash=?',(ph,)).fetchone()
  unresolved=db.execute("SELECT 1 FROM engine_packets WHERE slug=? AND item_id=? AND status IN ('submitting','uncertain')",(slug,item)).fetchone()
 if unresolved:raise ValueError('Uncertain engine submission outcome; inspect the saved receipt before any retry')
 if previous:return json.loads(previous['receipt_json'] or '{}'),previous['status']
 execute_guard(issue,board,config,execution);quality_gate.record(database,ph,'engine_'+kind,{'tenant_contract':True,'literal_source_identity':True,'engine_retains_final_gate':True})
 with database() as db:
  db.execute('BEGIN IMMEDIATE');quality_gate.reserve(db,ph,config);db.execute('INSERT INTO engine_packets VALUES(?,?,?,?,?,?,?,?,?,?)',(ph,slug,issue['id'],item,kind,'submitting',json.dumps(body),json.dumps(proof),None,time.time()))
 try:
  response=client.call('/api/ingest',body)
  if response.get('cardId')!=item:raise ValueError('No definitive engine receipt')
  if kind=='intake':
   if not isinstance(response.get('created'),bool):raise ValueError('Invalid engine intake receipt')
   state='accepted'
  else:
   if not isinstance(response.get('published'),bool) or not response.get('auditId'):raise ValueError('No governed engine publication audit receipt')
   state='published' if response['published'] else 'held'
  with database() as db:db.execute('UPDATE engine_packets SET status=?,receipt_json=? WHERE packet_hash=?',(state,json.dumps(response),ph))
  return response,state
 except urllib.error.HTTPError as error:
  if 400<=error.code<500:
   response={'http_status':error.code,'refused':True};state='held'
   with database() as db:db.execute('UPDATE engine_packets SET status=?,receipt_json=? WHERE packet_hash=?',(state,json.dumps(response),ph))
   return response,state
  with database() as db:db.execute("UPDATE engine_packets SET status='uncertain' WHERE packet_hash=?",(ph,))
  raise ValueError('Engine submission outcome uncertain; automatic replay stopped') from None
 except Exception:
  with database() as db:db.execute("UPDATE engine_packets SET status='uncertain' WHERE packet_hash=?",(ph,))
  raise ValueError('Engine write outcome uncertain; automatic replay stopped') from None

def maintain(issue,board,config,web,database,execution,client=None):
 initialize(database);slug=slug_for(issue,config);client=client or Client(slug);value=client.catalog();rows=value['catalog'].get('listings',[]);by_id={r['id']:r for r in rows};results=[]
 with database() as db:attempts={r['item_id']:r['attempted_at'] for r in db.execute('SELECT item_id,attempted_at FROM engine_attempts WHERE slug=?',(slug,))}
 # Hard/safety/terminal cards are never offered to this endpoint.
 sample=[c for c in value.get('triage',{}).get('reviewReadySample',[]) if c.get('state')=='REVIEW_READY' and str(c.get('lastReason','')).startswith('soft-incomplete')]
 for card in sorted(sample,key=lambda c:attempts.get(c['id'],0))[:2]:
  if time.time()-attempts.get(card['id'],0)<86400:continue
  row=by_id.get(card.get('listingId'),{});url=row.get('source',{}).get('sourceUrl');name=row.get('name')
  result={'card_id':card['id'],'status':'source_unavailable'}
  try:
   if not url or not name:raise ValueError('No exact stored source/name in the bounded catalog slice')
   page=web.page(url)
   if evidence.host(page['url'])!=evidence.host(url):raise ValueError('Recorded source redirected to another organization host')
   if publishing.norm(name) not in publishing.norm(page['text']):raise ValueError('Stored source no longer names the venue')
   if not venue_identity.provider_host(evidence.host(page['url'])):raise ValueError('Publish source is a directory; require first-party revalidation')
   body={'id':card['id'],'forcePublish':True,'reason':'Automatic governed publication: engine reports only a declared soft completeness gap; official source still names this exact listing. Hard and safety blockers remain authoritative.'}
   proof={'listing_id':card['listingId'],'name':name,'source_url':page['url'],'source_hash':page['sha256'],'tenant_scope':value['vertical']['territoryScope']}
   response,state=write_once(issue,board,config,database,execution,client,slug,'publish',body,proof);result.update(status='engine_published' if state=='published' else state,audit_id=response.get('auditId'))
   if state=='published':
    try:
     request=urllib.request.Request(client.origin+'/listing/'+urllib.parse.quote(card['listingId'],safe=''),headers={'X-Request-Purpose':'test','User-Agent':'NarimatoFactory/1.0'})
     with urllib.request.build_opener(catalog.NoRedirect).open(request,timeout=25) as response_page:html=response_page.read(2*1024*1024).decode('utf-8','replace')
     if publishing.norm(name) in publishing.norm(__import__('html').unescape(html)):result.update(status='published_verified',public_verified=True)
    except Exception:result['public_verified']=False
  except Exception as error:result.update(reason=str(error)[:220])
  with database() as db:db.execute('INSERT INTO engine_attempts VALUES(?,?,?,?) ON CONFLICT(slug,item_id) DO UPDATE SET attempted_at=excluded.attempted_at,result_json=excluded.result_json',(slug,card['id'],time.time(),json.dumps(result)))
  results.append(result)
 # Source verification rotates locally without inventing an empty remote "touch" capability.
 for row in sorted(rows,key=lambda r:attempts.get(r['id'],0))[:3]:
  if time.time()-attempts.get(row['id'],0)<86400:continue
  result={'listing_id':row['id'],'status':'not_checked'}
  try:
   url=row.get('source',{}).get('sourceUrl');page=web.page(url)
   if not venue_identity.provider_host(evidence.host(page['url'])):raise ValueError('Recorded source is not first-party')
   if publishing.norm(row.get('name','')) not in publishing.norm(page['text']):raise ValueError('Recorded source does not literally name this listing')
   result.update(status='source_verified',source_url=page['url'],source_hash=page['sha256'])
  except Exception as error:result.update(reason=str(error)[:220])
  with database() as db:db.execute('INSERT INTO engine_attempts VALUES(?,?,?,?) ON CONFLICT(slug,item_id) DO UPDATE SET attempted_at=excluded.attempted_at,result_json=excluded.result_json',(slug,row['id'],time.time(),json.dumps(result)))
  results.append(result)
 report={'slug':slug,'origin':client.origin,'tenant_verified':True,'catalog_total':value['catalog']['total'],'catalog_rows_available':len(rows),'catalog_truncated':value['catalog'].get('truncated'),'territory':value['vertical']['territoryScope'],'locales':value['vertical']['locales'],'triage':value.get('triage',{}).get('byState',{}),'results':results,'checked_at':publishing.stamp(),'language_generation':'none; source values remain verbatim'}
 catalog.save_report(database,issue,'engine_'+slug,report)
 return {**done('engine_maintenance','Engine maintenance completed. Source holds, governed audit receipts and publication outcomes are recorded separately.'),'report':report}

def discover(issue,board,config,web,database,execution,client=None):
 initialize(database);slug=slug_for(issue,config);client=client or Client(slug);v=client.catalog()['vertical'];localities=v['discovery']['localities'];templates=v['discovery']['queryTemplates']
 if not localities or not templates:raise ValueError('Engine declares no discovery plan')
 import search_workflow
 search_workflow.initialize(database)
 with database() as db:
  pending=db.execute("SELECT count(*) FROM search_jobs WHERE kind=? AND status IN ('queued','running','delivery_pending')",('padel' if slug=='padel-africa' else 'sportolok',)).fetchone()[0]
  db.execute('INSERT OR IGNORE INTO engine_cursor VALUES(?,0)',(slug,));position=db.execute('SELECT position FROM engine_cursor WHERE slug=?',(slug,)).fetchone()[0]
 if pending:return done('engine_discovery_waiting','This client already has a pending discovery intent; no duplicate was queued.')
 city=localities[position%len(localities)];query=templates[(position//len(localities))%len(templates)].replace('{locality}',city);kind='padel' if slug=='padel-africa' else 'sportolok';agent=next(k for k,v in config['agents'].items() if v['role']=='search');day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'engine-discovery-'+slug+'-'+day+'-'+publishing.sha(query),'title':'Discover official sources: '+city,'description':'Search purpose: '+kind+'\nSearch query: '+query+'\nEngine client: '+slug+'\n\nSearch intent is not location evidence. Use the authenticated vertical territory and literal source values.','projectId':issue['projectId'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone'})
 with database() as db:db.execute('UPDATE engine_cursor SET position=position+1 WHERE slug=?',(slug,))
 return done('engine_discovery','Queued '+child['identifier']+' from the engine’s own query template and locality rotation.')

def overview(issue,board,config,web,database,execution):
 reports=[]
 for slug in SPECS:
  if not config.get('engine_clients',{}).get(slug):continue
  value=Client(slug).catalog();reports.append({'client':slug,'catalog_total':value['catalog']['total'],'territory':value['vertical']['territoryScope'],'locales':value['vertical']['locales'],'states':value.get('triage',{}).get('byState',{})})
 catalog.save_report(database,issue,'management_overview',{'clients':reports,'checked_at':publishing.stamp()})
 return done('management_overview','Shared Management engine verified for its enabled clients. This is engine oversight, not a third customer catalog.')

def done(stage,text):return {'stage':stage,'entities':[],'final_status':'done','automatic_progress':True,'markdown':text}
