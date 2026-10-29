"""Branch- and program-scoped structured updates through ClassScout's ingest contract."""
import copy,datetime,json,re,time,urllib.request
import catalog,evidence,formats,publishing,quality_gate,refresh

def initialize(database):
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS program_packets(packet_hash TEXT PRIMARY KEY,provider_id TEXT,issue_id TEXT,status TEXT,body_json TEXT,proof_json TEXT,baseline_hash TEXT,receipt_json TEXT,created_at REAL)')

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def proposed(row,pages):
 """Never replace the program collection with just the programs found on a page."""
 programs=copy.deepcopy(row.get('recurringPrograms') or []);changes=[];patch={};proof=[]
 for page in pages:
  if evidence.host(page['url'])!=evidence.host(row.get('website','')):continue
  if not evidence.address_matches(row.get('address',''),page['text']) or publishing.norm(row.get('name')) not in publishing.norm(page['text']):continue
  kind='Camps' if row.get('category')=='Camps' else 'Classes'
  try:fee=formats.price(page['text'],kind)
  except ValueError:fee=None
  try:slots=formats.schedules(page['text'],kind,True,allow_expired=True)
  except ValueError:slots=[]
  for slot in slots:
   bounds=formats.bounds(slot,True)
   matches=[p for p in programs if p.get('ageMinMonths')==bounds[0] and p.get('ageMaxMonths') in ({bounds[1],bounds[1]+11} if bounds[1]%12==0 else {bounds[1]})]
   # One source age group must identify exactly one existing program.
   if len(matches)!=1 or len([s for s in slots if formats.bounds(s,True)==bounds])!=1:continue
   p=matches[0]
   same_source=(p.get('price') or {}).get('sourceUrl')==page['url'] or p.get('registrationUrl')==page['url']
   unknown=not p.get('daysOfWeek') or not p.get('timeText') or not p.get('price') or p.get('price',{}).get('evidence')=='unknown'
   if not same_source and not unknown:continue
   # Existing title must be grounded too; equal ages alone must not switch between two classes.
   title=str(p.get('title',''))
   generic=bool(re.fullmatch(r'ages?\s+\d+\s*[-–]\s*\d+(?:\s+months?)?',title,re.I))
   if generic and not same_source:continue
   if publishing.norm(title) not in publishing.norm(page['text']) and not re.fullmatch(r'ages?\s+\d+\s*[-–]\s*\d+(?:\s+months?)?',title,re.I):continue
   old=copy.deepcopy(p)
   p.update(daysOfWeek=slot['daysOfWeek'],timeText=slot['timeText'])
   # An old structured recurrence would override the new timeText in the UI. Preserve it and hold
   # until that precise structure has its own parser instead of silently contradicting it.
   if old.get('schedule') and (old.get('daysOfWeek')!=p['daysOfWeek'] or old.get('timeText')!=p['timeText']):p.clear();p.update(old);continue
   if fee:
    existing_price=p.get('price') or {}
    if any(existing_price.get(k)!=v for k,v in {**fee,'sourceUrl':page['url']}.items()):p['price']={**fee,'sourceUrl':page['url'],'observedAt':stamp()}
   if slot.get('endDate'):p.update(startDate=slot['startDate'],endDate=slot['endDate'])
   if p!=old:changes.append(p['id']);proof.append({'program_id':p['id'],'url':page['url'],'sha256':page['sha256'],'quote':slot['quote'],'price_quote':fee.get('sourceText') if fee else None})
  # Provider-level price is filled only when the source and catalog each identify a single program.
  if fee and len(programs)==1 and len(slots)==1 and programs[0]['id'] in changes:
   previous=row.get('price') or {}
   if previous.get('evidence') in {None,'unknown'} or previous.get('sourceUrl')==page['url']:
    wanted={**fee,'sourceUrl':page['url'],'observedAt':stamp()}
    if any(previous.get(k)!=wanted.get(k) for k in ['evidence','amount','unit']):patch['price']=wanted
 if changes:
  if any(v.get('method')=='admin' and v.get('field') in {'price','schedule','recurringPrograms'} for v in row.get('fieldVerifications',[])):raise ValueError('Existing manual program verification requires owner review; no update proposed')
  if len(changes)!=len(set(changes)):raise ValueError('Conflicting program facts from multiple pages; no update proposed')
  patch['recurringPrograms']=programs
  verifications=copy.deepcopy(row.get('fieldVerifications') or [])
  for url in sorted({v['url'] for v in proof}):
   verifications=[v for v in verifications if not (v.get('field')=='schedule' and v.get('sourceUrl')==url and v.get('method')=='official_page')]
   verifications.append({'field':'schedule','verifiedAt':stamp(),'sourceUrl':url,'method':'official_page'})
  if len(verifications)>60:raise ValueError('Verification ledger is full; preserve existing entries')
  patch['fieldVerifications']=verifications
 return patch,proof

class Writer:
 def apply(self,body):
  if set(body)!={'resource','action','id','patch'} or body['resource']!='provider' or body['action']!='patch' or not set(body['patch'])<={'price','recurringPrograms','fieldVerifications'}:raise ValueError('Invalid structured program patch')
  import os
  key=os.environ.get('CLASSSCOUT_INGEST_KEY')
  if not key:raise ValueError('ClassScout connection unavailable')
  req=urllib.request.Request(publishing.ClassScout.BASE+'/api/ingest',data=json.dumps({'operations':[body]}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  with urllib.request.build_opener(catalog.NoRedirect).open(req,timeout=45) as r:return json.load(r)

def run(issue,board,config,web,database,execution,client=None,writer=None):
 initialize(database);client=client or publishing.ClassScout();writer=writer or Writer();id=catalog.clean_id(catalog.field(issue,'Catalog provider'));row=client.existing_provider(id)
 if not row or row.get('ownerSub') or row.get('ownerManaged') or row.get('ownerManagedAt') or row.get('claimStatus') in {'claimed','claim_pending'}:raise ValueError('Program listing is absent or owner-managed')
 with database() as db:
  pending=db.execute("SELECT status FROM program_packets WHERE provider_id=? AND status IN ('submitting','uncertain','partial')",(id,)).fetchone()
 if pending:raise ValueError('An unresolved program write requires reconciliation; never replay it')
 urls=re.findall(r'^Program source:\s*(https://\S+)',issue.get('description') or '',re.M)
 if not urls:urls=[row.get('website','')]
 pages=evidence.crawl(urls[0],web,extra=urls[1:],maximum=4);patch,proof=proposed(row,pages)
 if not patch:return {'stage':'program_no_change','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Program source checked. No unambiguous, supported change was found. Existing programs and unknown values were preserved.'}
 body={'resource':'provider','action':'patch','id':id,'patch':patch};ph=publishing.sha({'body':body,'proof':proof,'baseline':row});baseline=publishing.sha(row)
 quality_gate.record(database,ph,'program_update',{'unclaimed':True,'literal_branch_program_evidence':bool(proof),'existing_programs_preserved':len(patch['recurringPrograms'])==len(row.get('recurringPrograms',[])),'source_hosts_match':all(evidence.host(p['url'])==evidence.host(row['website']) for p in proof)})
 if publishing.sha(client.existing_provider(id))!=baseline:raise ValueError('Program baseline changed; prepare a new check')
 publishing.ensure_execution(issue,board,config,execution,publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']}))
 for p in pages:
  if web.page(p['url'])['sha256']!=p['sha256']:raise ValueError('Program source changed during validation')
 with database() as db:
  old=db.execute('SELECT status FROM program_packets WHERE packet_hash=?',(ph,)).fetchone()
  if old and old['status']=='applied':return {'stage':'program_applied','entities':[],'final_status':'done','automatic_progress':True,'markdown':'This exact program update was already verified; no duplicate write.'}
  db.execute('BEGIN IMMEDIATE');quality_gate.reserve(db,ph,config);db.execute('INSERT INTO program_packets VALUES(?,?,?,?,?,?,?,?,?)',(ph,id,issue['id'],'submitting',json.dumps(body),json.dumps(proof),baseline,None,time.time()))
 try:
  receipt=writer.apply(body);results=receipt.get('results',[])
  if not len(results)==1 or not results[0].get('ok'):raise ValueError('Program write refused or receipt unavailable')
  private=client.existing_provider(id);public=catalog.Catalog().public_get(id,ph)
  verified=all(private.get(k)==v for k,v in patch.items()) and all(public.get(k)==v for k,v in patch.items() if k!='fieldVerifications')
  state='applied' if verified else 'partial'
  with database() as db:db.execute('UPDATE program_packets SET status=?,receipt_json=? WHERE packet_hash=?',(state,json.dumps({'receipt':receipt,'private_public_verified':verified}),ph))
 except Exception:
  with database() as db:db.execute("UPDATE program_packets SET status='uncertain' WHERE packet_hash=?",(ph,))
  raise ValueError('Program write outcome uncertain; no automatic replay') from None
 return {'stage':'program_applied' if verified else 'program_partial','entities':[],'final_status':'done' if verified else 'in_review','automatic_write':True,'markdown':'Structured program update '+('saved and verified privately and publicly.' if verified else 'requires readback reconciliation; it will not be replayed.')}
