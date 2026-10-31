"""Padel Africa's existing machine catalog and evidence-intake contracts."""
import hashlib,json,os,re,threading,time,urllib.request,urllib.parse
import catalog,publishing,quality_gate
from net import canonical_url
ORIGIN='https://padel-africa.doneisbetter.com'
LOCK=threading.Lock();TOKEN=None
class Client:
 def token(self):
  global TOKEN
  with LOCK:
   if TOKEN and TOKEN[1]>time.time()+300:return TOKEN[0]
   issuer=os.environ.get('PADEL_SSO_ISSUER','')
   if issuer!='https://sso.doneisbetter.com':raise ValueError('Padel machine issuer is not configured')
   body={'grant_type':'client_credentials','client_id':os.environ['PADEL_SSO_CLIENT_ID'],'client_secret':os.environ['PADEL_SSO_CLIENT_SECRET'],'scope':'management:ingest.write management:catalog.read'}
   req=urllib.request.Request(issuer+'/api/oauth/token',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.build_opener(catalog.NoRedirect).open(req,timeout=30) as r:value=json.load(r)
   if not isinstance(value.get('access_token'),str):raise ValueError('Padel machine token unavailable')
   TOKEN=(value['access_token'],time.time()+int(value.get('expires_in',3600)));return TOKEN[0]
 def call(self,path,body=None):
  if path not in {'/api/machine/catalog','/api/ingest'}:raise ValueError('Unsupported Padel machine operation')
  if path=='/api/ingest' and (not body or set(body)!={'id','sourceText','sourceUrl','sourcePool'} or body['sourcePool']!='ingest' or len(body['sourceText'])>50000):raise ValueError('Padel connector accepts only bounded new source evidence; no forced publication or raw patch')
  req=urllib.request.Request(ORIGIN+path,data=json.dumps(body).encode() if body else None,headers={'Authorization':'Bearer '+self.token(),'Content-Type':'application/json'})
  with urllib.request.build_opener(catalog.NoRedirect).open(req,timeout=45) as r:
   raw=r.read(8*1024*1024+1)
   if len(raw)>8*1024*1024:raise ValueError('Padel response exceeded its bound')
   return json.loads(raw)
 def catalog(self):
  value=self.call('/api/machine/catalog')
  if value.get('vertical',{}).get('slug')!='padel-africa' or value.get('vertical',{}).get('territoryScope')!={'kind':'continent','continent':'Africa'}:raise ValueError('Padel tenant identity or territory does not match; no write allowed')
  if len(value.get('catalog',{}).get('listings',[]))>500:raise ValueError('Padel catalog contract changed')
  return value

def initialize(database):
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS padel_packets(packet_hash TEXT PRIMARY KEY,issue_id TEXT,status TEXT,body_json TEXT,proof_json TEXT,receipt_json TEXT,created_at REAL)')
# Evidence intake only; this connector never force-publishes (engine_ops.Client is the one that can). Like the engine and
# program-update writes, this path has no human-approval mode: it records a gate decision and uses the daily cap, and the
# reservation refuses while automatic_quality_gate.enabled is not true, so the switch stops it too.
def run(issue,board,config,web,database,execution,client=None):
 initialize(database);client=client or Client();value=client.catalog();kind=catalog.field(issue,'Factory workflow');vertical=value['vertical'];current=value['catalog']
 if kind=='padel_maintenance':
  report={'brand':'Padel Africa','origin':ORIGIN,'tenant_verified':True,'catalog_total':current['total'],'rows_available':len(current['listings']),'truncated':current.get('truncated',False),'triage':value.get('triage',{}),'localities':vertical.get('discovery',{}).get('localities',[]),'checked_at':publishing.stamp(),'writes':0}
  catalog.save_report(database,issue,kind,report)
  return {'stage':'padel_connected','entities':[],'final_status':'done','automatic_progress':True,'markdown':'## Padel Africa connection\n\nAuthenticated tenant and Africa territory verified. Canonical machine catalog: '+str(current['total'])+' eligible catalog records; bounded slice: '+str(len(current['listings']))+'. Engine lifecycle counts are recorded for the dashboard. No catalog record changed. New evidence can be submitted through the Padel source intake form; the receiving engine owns extraction and publication.','report':report}
 if kind!='padel_intake':raise ValueError('Unsupported Padel workflow')
 url=canonical_url(catalog.field(issue,'Official source URL'));name=catalog.field(issue,'Provider name');city=catalog.field(issue,'City');address=catalog.field(issue,'Street address')
 if not url.startswith('https://') or not all(3<=len(x)<=180 for x in [name,city,address]) or not re.search(r'\d',address):raise ValueError('Provide a focused HTTPS official source and exact provider, city and street address')
 if city not in vertical.get('discovery',{}).get('localities',[]):raise ValueError('City is not in the receiving Padel vertical discovery scope')
 page=web.page(url)
 if __import__('evidence').host(page['url'])!=__import__('evidence').host(url) or not all(publishing.norm(x) in publishing.norm(page['text']) for x in [name,city,address]) or not re.search(r'\bpadel\b',page['text'],re.I):raise ValueError('Official page must literally support provider, city, street and padel activity')
 for listing in current['listings']:
  if publishing.norm(listing.get('name'))==publishing.norm(name) or listing.get('source',{}).get('sourceUrl')==page['url']:raise ValueError('An existing Padel listing matches; this new-source connector will not duplicate or overwrite it')
 source_text=page['text']
 if len(source_text)>48000:
  excerpts='\n'.join(line for line in source_text.splitlines() if any(publishing.norm(x) in publishing.norm(line) for x in [name,city,address]))[:6000]
  source_text=excerpts+'\n'+source_text[:40000]
 if not all(publishing.norm(x) in publishing.norm(source_text) for x in [name,city,address]):raise ValueError('Bounded source evidence does not retain all identity fields')
 body={'id':'paperclip-padel-'+publishing.sha({'url':url,'address':address})[:24],'sourceText':source_text,'sourceUrl':page['url'],'sourcePool':'ingest'};proof={'source_url':page['url'],'sha256':page['sha256'],'name':name,'city':city,'address':address};ph=publishing.sha({'body':body,'proof':proof})
 with database() as db:
  old=db.execute('SELECT status,receipt_json FROM padel_packets WHERE packet_hash=?',(ph,)).fetchone()
  pending=db.execute("SELECT 1 FROM padel_packets WHERE json_extract(body_json,'$.id')=? AND status IN ('submitting','uncertain')",(body['id'],)).fetchone()
 if pending:raise ValueError('Padel source identity has an unresolved submission; it will not be replayed')
 if old:
  if old['status']=='accepted':return {'stage':'padel_evidence_accepted','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Source evidence was already accepted by the Padel engine. No second submission was sent; publication remains a separate engine outcome.'}
  raise ValueError('Padel evidence has an unresolved submission; reconcile it before another write')
 if issue['title'].startswith('[Factory test]'):raise ValueError('Synthetic factory tests cannot submit real Padel evidence')
 ih=publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']});publishing.ensure_execution(issue,board,config,execution,ih)
 quality_gate.record(database,ph,'padel_source_intake',{'tenant_scope':True,'literal_source_identity':True,'no_known_match_in_bounded_catalog':True,'engine_deduplication_required':True})
 with database() as db:
  db.execute('BEGIN IMMEDIATE');quality_gate.reserve(db,ph,config);db.execute('INSERT INTO padel_packets VALUES(?,?,?,?,?,?,?)',(ph,issue['id'],'submitting',json.dumps(body),json.dumps(proof),None,time.time()))
 try:
  receipt=client.call('/api/ingest',body)
  if receipt.get('cardId')!=body['id'] or not isinstance(receipt.get('created'),bool):raise ValueError('No definitive Padel intake receipt')
 except Exception:
  with database() as db:db.execute("UPDATE padel_packets SET status='uncertain' WHERE packet_hash=?",(ph,))
  raise ValueError('Padel submission outcome is uncertain; it will not be resent automatically') from None
 with database() as db:db.execute("UPDATE padel_packets SET status='accepted',receipt_json=? WHERE packet_hash=?",(json.dumps(receipt),ph))
 return {'stage':'padel_evidence_accepted','entities':[],'final_status':'done','automatic_progress':True,'markdown':'## Padel source receipt\n\nEvidence '+('accepted for engine processing' if receipt['created'] else 'already exists in the engine; no reprocessing was requested')+'. Card: '+body['id']+'. Engine state: '+str(receipt.get('state','unknown'))+'. This receipt does not claim public publication.'}
