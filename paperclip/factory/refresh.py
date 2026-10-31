"""Exact contact and content corrections through ClassScout's existing validation path. With the automatic gate on,
quality_gate.check_refresh decides (phone, email and neutral descriptions); with it off, a human approves the exact
packet and only phone and email can change."""
import datetime,json,os,re,time,urllib.error,urllib.parse,urllib.request
import catalog,publishing,quality_gate,evidence

def initialize(database):
 with database() as db:db.execute('''CREATE TABLE IF NOT EXISTS refresh_packets(packet_hash TEXT PRIMARY KEY,issue_id TEXT,provider_id TEXT,input_hash TEXT,status TEXT,body_json TEXT,proof_json TEXT,baseline_json TEXT,interaction_id TEXT,receipt_json TEXT,created_at REAL,error TEXT)''')
def equal(key,a,b):
 if key=='phone':return re.sub(r'\D','',a or '')[-10:]==re.sub(r'\D','',b or '')[-10:]
 return (a or '').strip().casefold()==(b or '').strip().casefold()
def address_key(value):
 value=re.sub(r'[^a-z0-9\s-]',' ',str(value).lower())
 for a,b in [('street','st'),('avenue','ave'),('road','rd'),('place','pl'),('north','n'),('south','s'),('east','e'),('west','w')]:value=re.sub(r'\b'+a+r'\b',b,value)
 return publishing.norm(value)
def approval_valid(interaction,packet,config):
 return bool(interaction and interaction.get('companyId')==config['company_id'] and interaction.get('issueId')==packet['issue_id'] and interaction.get('kind')=='request_confirmation' and interaction.get('status')=='accepted' and interaction.get('effectiveResolverPolicy')=='human_only' and interaction.get('resolvedByUserId')==config.get('reviewer_user_id','local-board') and not interaction.get('resolvedByAgentId') and interaction.get('idempotencyKey')=='refresh-'+packet['packet_hash'] and interaction.get('result',{}).get('outcome')=='accepted' and packet['packet_hash'] in (interaction.get('payload',{}).get('detailsMarkdown') or ''))
def packet_hash(issue_id,input_hash,body,proof,baseline):return publishing.sha({'issue_id':issue_id,'input_hash':input_hash,'body':body,'proof':proof,'baseline':baseline})
class ContactUpdates:
 def apply(self,operation):
  if set(operation)!={'resource','action','id','patch'} or operation['resource']!='provider' or operation['action']!='patch':raise ValueError('Only a reviewed provider contact patch is allowed')
  # quality_gate.FIELDS also holds shortDescription and longDescription; the 'phone and email' wording of the error below predates that.
  catalog.clean_id(operation['id']);patch=operation['patch']
  if not isinstance(patch,dict) or not patch or set(patch)-quality_gate.FIELDS:raise ValueError('Only phone and email can be corrected by this connector')
  for k,v in patch.items():
   if not isinstance(v,str) or len(v)>(5000 if k in {'shortDescription','longDescription'} else 200) or (k=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v)) or (k=='phone' and not 7<=len(re.sub(r'\D','',v))<=16):raise ValueError('Invalid contact correction')
  key=os.environ.get('CLASSSCOUT_INGEST_KEY')
  if not key:raise ValueError('ClassScout connection is unavailable')
  request=urllib.request.Request(publishing.ClassScout.BASE+'/api/ingest',data=json.dumps({'operations':[operation]}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  try:
   with urllib.request.build_opener(catalog.NoRedirect).open(request,timeout=45) as r:return json.load(r)
  except urllib.error.HTTPError as e:
   if e.code==422:return json.loads(e.read(65536))
   raise RuntimeError('Contact update returned HTTP '+str(e.code)) from None

def baseline_matches(current,baseline):
 # Older saved packets predate added catalog read fields. Preserve every fact
 # actually reviewed; the contact patch cannot write newly exposed program fields.
 return all(current.get(k)==v for k,v in baseline.items())

def source_proof(id,draft,database,client,web,content=False):
 baseline=client.get(id)
 if baseline['owner_managed']:raise ValueError('This listing is owner-managed; use its existing owner review workflow')
 with database() as db:
  entity=db.execute('SELECT * FROM entities WHERE id=? AND brand=?',(draft,'ClassScout')).fetchone()
  if not entity or entity['status']!='ready_for_human_review':raise ValueError('A current source draft must pass quality review first')
  facts=[dict(r) for r in db.execute('SELECT field,value,quote FROM facts WHERE entity_id=?',(draft,))]
 if evidence.host(entity['source_url'])!=evidence.host(baseline.get('website') or ''):raise ValueError('Official source and catalog host do not match')
 page,valid,branch=evidence.branch_page(baseline,entity['source_url'],facts,web)
 patch={f['field']:f['value'] for f in valid if f['field'] in {'phone','email'} and not equal(f['field'],baseline.get(f['field']),f['value'])}
 if content:
  with database() as db:previous=[json.loads(r[0])['patch'] for r in db.execute("SELECT body_json FROM refresh_packets WHERE provider_id=? AND status='applied'",(id,))]
  patch.update({k:v for k,v in quality_gate.descriptions(baseline,page).items() if baseline.get(k)!=v and (not baseline.get(k) or any(p.get(k)==baseline.get(k) for p in previous))})
 proof={'source_url':page['url'],'source_sha256':page['sha256'],'facts':valid,'draft_id':draft,'checked_at':page['fetched_at'],'branch':branch}
 return baseline,patch,proof

def run(issue,board,config,web,database,execution,client=None,writer=None):
 initialize(database);automatic=quality_gate.enabled(config,issue);client=client or catalog.Catalog();writer=writer or ContactUpdates();id=catalog.clean_id(catalog.field(issue,'Catalog provider'));draft=catalog.field(issue,'Draft reference')
 if not re.fullmatch(r'[a-f0-9]{32}',draft):raise ValueError('A verified draft reference is required')
 ih=publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']})
 with database() as db:
  row=db.execute('SELECT * FROM refresh_packets WHERE issue_id=? ORDER BY created_at DESC LIMIT 1',(issue['id'],)).fetchone();packet=dict(row) if row else None
  other=db.execute("SELECT issue_id,status FROM refresh_packets WHERE provider_id=? AND issue_id<>? AND status IN ('prepared','awaiting_approval','applying','uncertain','partial')",(id,issue['id'])).fetchone()
 if other:raise ValueError('Another unresolved correction already exists for this listing; inspect task '+other['issue_id'])
 if packet and packet['status'] in {'applying','uncertain','partial'}:raise ValueError('A previous correction has an unresolved outcome. Inspect the catalog and receipt; it will not be sent again.')
 if packet and packet['status']=='applied':return {'stage':'refresh_applied','entities':[],'markdown':'The contact/content update was already applied and verified. It was not sent again.','final_status':'done','automatic_write':automatic}
 if packet and packet['input_hash']!=ih:raise ValueError('The correction brief changed. Reject or reconcile the existing packet before preparing a fresh correction.')
 if packet and packet['status']=='prepared':return offer_review(packet,board,config,database,issue,web,execution,client,writer)
 if packet:
  if packet['status']!='awaiting_approval':raise ValueError('This correction needs a new review after its previous disposition')
  cards=board.call('/issues/'+issue['id']+'/interactions');interaction=next((c for c in cards if c['id']==packet['interaction_id']),{})
  if not interaction and not automatic:raise ValueError('The contact confirmation is unavailable; restore the review before any correction')
  if interaction.get('status') in {'rejected','withdrawn','expired','cancelled','skipped'}:
   with database() as db:db.execute("UPDATE refresh_packets SET status='rejected' WHERE packet_hash=?",(packet['packet_hash'],))
   return {'stage':'refresh_rejected','entities':[],'markdown':'The contact correction was declined or withdrawn. No change was sent.'}
  if not automatic and interaction.get('status')=='accepted' and not approval_valid(interaction,packet,config):raise ValueError('Contact confirmation was not accepted by the required human owner')
  if not automatic and not approval_valid(interaction,packet,config):return {'stage':'awaiting_approval','entities':[],'markdown':None}
  if time.time()-packet['created_at']>48*3600:raise ValueError('Contact approval expired after 48 hours; prepare a fresh review')
  body=json.loads(packet['body_json']);proof=json.loads(packet['proof_json']);baseline=json.loads(packet['baseline_json'])
  if packet_hash(issue['id'],ih,body,proof,baseline)!=packet['packet_hash']:raise ValueError('Contact packet integrity check failed')
  current=client.get(id)
  if current['owner_managed'] or not baseline_matches(current,baseline):raise ValueError('Catalog or owner status changed since review; a fresh approval is required')
  page=web.page(proof['source_url'])
  if page['sha256']!=proof['source_sha256']:raise ValueError('Official source changed after review; a fresh approval is required')
  if issue['title'].startswith('[Factory test]'):raise ValueError('Synthetic factory tests cannot change real catalog records')
  if automatic:quality_gate.check_refresh(database,packet['packet_hash'],body,proof,baseline,page)
  publishing.ensure_execution(issue,board,config,execution,ih)
  with database() as db:
   db.execute('BEGIN IMMEDIATE')
   if automatic:quality_gate.reserve(db,packet['packet_hash'],config)
   changed=db.execute("UPDATE refresh_packets SET status='applying' WHERE packet_hash=? AND status='awaiting_approval'",(packet['packet_hash'],)).rowcount
   if changed!=1:raise ValueError('The correction was already submitted or changed')
  try:
   receipt=writer.apply(body);rows=receipt.get('results',[])
   if not receipt.get('ok') or len(rows)!=1 or not rows[0].get('ok'):
    with database() as db:db.execute("UPDATE refresh_packets SET status='rejected_by_catalog',receipt_json=? WHERE packet_hash=?",(json.dumps({'ok':False,'errors':[str(r.get('error','Rejected'))[:240] for r in rows]}),packet['packet_hash']))
    return {'stage':'refresh_rejected','entities':[],'markdown':'ClassScout rejected this correction through its canonical checks. No successful update is claimed; review the saved rejection.'}
   private=client.get(id);private_ok=all(equal(k,private.get(k),v) for k,v in body['patch'].items())
   public=client.public_get(id,packet['packet_hash']);public_ok=all(equal(k,public.get(k),v) for k,v in body['patch'].items())
   state='applied' if private_ok and public_ok else 'partial';verified={'private_verified':private_ok,'public_verified':public_ok,'fields':list(body['patch']),'provider_id':id}
   with database() as db:db.execute('UPDATE refresh_packets SET status=?,receipt_json=? WHERE packet_hash=?',(state,json.dumps(verified),packet['packet_hash']))
  except Exception:
   with database() as db:db.execute("UPDATE refresh_packets SET status='uncertain',error='Response or verification unavailable; inspect before any retry' WHERE packet_hash=?",(packet['packet_hash'],))
   raise ValueError('Contact correction outcome is uncertain; do not repeat the write before reconciliation') from None
  return {'stage':'refresh_applied' if state=='applied' else 'refresh_partial','entities':[],'markdown':('Automatically qualified update ' if automatic else 'Approved correction ')+('saved and verified in both the private and public catalog.' if state=='applied' else 'needs verification; it will not be submitted again.')+'\n\nProvider: '+id+'\nFields: '+', '.join(body['patch']),'final_status':'done' if state=='applied' else 'in_review','automatic_write':automatic}
 baseline,patch,proof=source_proof(id,draft,database,client,web,content=automatic)
 if not patch:return {'stage':'refresh_no_change','entities':[],'final_status':'done','automatic_write':automatic,'markdown':'Catalog contacts already agree with the verified source. No write or new approval was needed.'}
 body={'resource':'provider','action':'patch','id':id,'patch':patch};ph=packet_hash(issue['id'],ih,body,proof,baseline)
 with database() as db:db.execute('INSERT INTO refresh_packets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(ph,issue['id'],id,ih,'prepared',json.dumps(body),json.dumps(proof),json.dumps(baseline),None,None,time.time(),None))
 with database() as db:packet=dict(db.execute('SELECT * FROM refresh_packets WHERE packet_hash=?',(ph,)).fetchone())
 return offer_review(packet,board,config,database,issue,web,execution,client,writer)

def offer_review(packet,board,config,database,issue=None,web=None,execution=None,client=None,writer=None):
 if issue and quality_gate.enabled(config,issue):
  with database() as db:db.execute("UPDATE refresh_packets SET status='awaiting_approval' WHERE packet_hash=? AND status='prepared'",(packet['packet_hash'],))
  return run(issue,board,config,web,database,execution,client,writer)
 body=json.loads(packet['body_json']);proof=json.loads(packet['proof_json']);baseline=json.loads(packet['baseline_json']);ph=packet['packet_hash'];patch=body['patch'];id=packet['provider_id']
 if packet_hash(packet['issue_id'],packet['input_hash'],body,proof,baseline)!=ph:raise ValueError('Contact packet integrity check failed')
 from worker import safe
 details='## Review contact correction\n\n'+safe(baseline.get('name',id))+'\n\n'
 for k,v in patch.items():details+=k.capitalize()+': '+safe(baseline.get(k) or 'not listed')+' → '+safe(v)+'\n\n'
 details+='Official source: '+proof['source_url']+'\n\nOnly these contact fields will change. Listing ownership, source content and current catalog facts are checked again. Approval expires after 48 hours.\n\nPacket: `'+ph+'`'
 card=board.call('/issues/'+packet['issue_id']+'/interactions',{'kind':'request_confirmation','idempotencyKey':'refresh-'+ph,'resolverPolicy':'human_only','addresseeUserId':config.get('reviewer_user_id','local-board'),'title':'Approve contact correction','summary':'Review the exact source-supported contact changes.','continuationPolicy':'wake_assignee','payload':{'version':1,'prompt':'Apply this exact contact correction?','detailsMarkdown':details,'acceptLabel':'Apply correction','rejectLabel':'Request changes','supersedeOnUserComment':False}})
 with database() as db:db.execute("UPDATE refresh_packets SET status='awaiting_approval',interaction_id=? WHERE packet_hash=?",(card['id'],ph))
 return {'stage':'awaiting_approval','entities':[],'markdown':details}
