"""Source-backed publication preparation and ClassScout delivery. With the automatic quality gate on (quality_gate.enabled)
the packet is checked and sent in the same run; with it off, delivery waits for an exact human approval."""
# quality_gate imports this module too. Each side uses the other only inside functions, so the cycle is safe; do not add
# module-level attribute access between them. catalog is imported lazily below for the same reason.
import quality_gate,formats
import copy,datetime,hashlib,json,os,re,time,urllib.error,urllib.parse,urllib.request
from net import canonical_url,public_addresses

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def norm(value):return re.sub(r'\s+',' ',str(value)).strip().casefold()
def initialize(db):
 db.execute('''CREATE TABLE IF NOT EXISTS publication_packets(packet_hash TEXT PRIMARY KEY,issue_id TEXT,input_hash TEXT,status TEXT,body_json TEXT,proof_json TEXT,interaction_id TEXT,receipt_json TEXT,error TEXT,created_at TEXT,updated_at TEXT)''')

def read_time_text(text):
 """ClassScout rule 474: a public read never shows an em dash (src/lib/copy/emDash.ts). Mirror that guard exactly,
 so a draft with a dash is compared with what the public page really serves; any other difference still fails."""
 if not isinstance(text,str) or '\u2014' not in text:return text
 if text.strip()=='\u2014':return '\u2013'
 text=re.sub(r'([.!?:;,])\s*\u2014\s*',r'\1 ',text)
 text=re.sub(r'\A\s*\u2014\s*','',text)
 text=re.sub(r'\s*\u2014\s*\Z','',text)
 return re.sub(r'\s*\u2014\s*',', ',text)

class ClassScout:
 BASE='https://classscout.ai'
 ALLOWED={'/api/content-intelligence/prepare-review','/api/content-intelligence/publish-reviewed','/api/ingest'}
 def call(self,path,body,timeout=150):
  if path not in self.ALLOWED:raise ValueError('Unsupported ClassScout operation')
  if path=='/api/ingest':
   ops=body.get('operations',[])
   if len(ops)!=1 or set(ops[0])!={'resource','action','id'} or ops[0]['resource']!='provider' or ops[0]['action']!='get':raise ValueError('Publication connector allows only provider.get through ingest')
  key=os.environ.get('CLASSSCOUT_INGEST_KEY')
  if not key:raise ValueError('ClassScout publication connection is not configured')
  req=urllib.request.Request(self.BASE+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
  except urllib.error.HTTPError as error:
   # HTTP 207 and 422 still carry a JSON receipt (partial save, or a gate refusal) that callers inspect; other errors raise.
   if error.code in {207,422}:return json.loads(error.read(131072))
   raise RuntimeError('ClassScout request failed: HTTP '+str(error.code)) from None

 def existing_provider(self,entity_id):
  response=self.call('/api/ingest',{'operations':[{'resource':'provider','action':'get','id':entity_id}]},timeout=30)
  rows=response.get('results',[])
  if len(rows)!=1:raise ValueError('Catalog identity check returned no definitive result')
  if rows[0].get('ok'):
   data=rows[0].get('data')
   if not isinstance(data,dict) or data.get('id')!=entity_id:raise ValueError('Catalog identity check returned an incomplete provider')
   return data
  if rows[0].get('error')=='provider not found':return None
  raise ValueError('Catalog identity check failed; no publication will be submitted')


 def verify_catalog(self,body):
  """Read only: exact private payload and bounded per-ID core public lookup."""
  from catalog import NoRedirect,clean_id
  draft=body['draftPayload'];id=clean_id(draft['id']);private=self.existing_provider(id)
  private_ok=isinstance(private,dict) and all(private.get(k)==v for k,v in draft.items())
  url=self.BASE+'/api/public/providers/'+urllib.parse.quote(id,safe='')+'?city=nyc&verification='+sha(body)
  with urllib.request.build_opener(NoRedirect).open(url,timeout=30) as response:
   raw=response.read(2*1024*1024+1)
   if len(raw)>2*1024*1024:raise ValueError('Core catalog detail exceeded its response bound')
   public=json.loads(raw).get('provider')
  fields=['id','name','category','borough','neighborhood','address','shortDescription','longDescription']
  public_ok=isinstance(public,dict) and all(public.get(k)==read_time_text(draft.get(k)) for k in fields)
  return {'verified':private_ok and public_ok,'private_verified':private_ok,'public_verified':public_ok,'origin':self.BASE,'public_fields':fields,'checked_at':stamp(),'method':'read-only per-ID core catalog verification'}

def reconcile_catalog(client,body,receipt):
 try:verification=client.verify_catalog(body)
 except Exception:return False
 if not isinstance(verification,dict) or verification.get('verified') is not True or verification.get('origin')!=ClassScout.BASE:return False
 receipt['catalogVerification']=verification
 return True

def parse_brief(issue):
 text=issue.get('description') or '';fields={}
 for key in ['Publication name','Borough','Neighborhood','Format','Activity','Draft reference']:
  m=re.search(r'^'+re.escape(key)+r':\s*(.+?)\s*$',text,re.M)
  if m:fields[key]=m.group(1).strip().strip('`')
 missing=[key for key in ['Publication name','Borough','Neighborhood','Format','Activity','Draft reference'] if not fields.get(key)]
 if missing:raise ValueError('Publication brief needs: '+', '.join(missing)+'. Supply source-backed editorial values, not guesses.')
 if fields['Format'] not in {'Classes','Camps'}:raise ValueError('Supported publication formats are Classes and dated Camps')
 if not re.fullmatch(r'[a-f0-9]{32}',fields['Draft reference']):raise ValueError('Invalid draft reference')
 urls=[]
 for raw in re.findall(r'https?://[^\s<>\]\)"`]+',text):
  url=canonical_url(raw.rstrip('.,;'))
  if url not in urls:urls.append(url)
 if not 1<=len(urls)<=4:raise ValueError('Publication tasks need one to four official source pages')
 hosts={urllib.parse.urlsplit(u).hostname.removeprefix('www.') for u in urls}
 if len(hosts)!=1:raise ValueError('All publication sources must belong to the same provider host')
 fields['urls']=urls;return fields

# age_ranges, program_schedules and class_price are older single-format parsers. The production path uses formats.ages,
# formats.schedules and formats.price (see normalize_sources); these three are not used by it and are kept for their tests.
def age_ranges(text):
 rows=[]
 for m in re.finditer(r'\bages?\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\b',text,re.I):
  lo,hi=map(int,m.groups())
  if not 0<=lo<=hi<=17:continue
  if (lo,hi) not in [(x['min'],x['max']) for x in rows]:rows.append({'min':lo,'max':hi,'quote':m.group(0)})
 if not rows:raise ValueError('Missing explicit numerical child age ranges; fetch a program page with stated ages')
 return rows

def buckets(lo,hi):return [label for a,b,label in [(0,2,'0–2'),(3,5,'3–5'),(6,8,'6–8'),(9,12,'9–12'),(13,17,'Teens')] if lo<=b and hi>=a]
def program_schedules(text):
 rows=[]
 pattern=r'ages?\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\s*[-–:]?\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?\s+(\d{1,2}:\d{2}\s*[ap]m)\s*[,;]?\s*(\d{1,3})\s*minutes'
 for m in re.finditer(pattern,text,re.I):
  lo,hi=int(m[1]),int(m[2]);duration=int(m[5]);clock=m[4]
  if not 0<=lo<=hi<=17 or not 15<=duration<=240:continue
  hour,minute=map(int,re.findall(r'\d+',clock)[:2])
  if not 1<=hour<=12 or not 0<=minute<=59:continue
  if any(x['age_min']==lo and x['age_max']==hi and x['daysOfWeek']==[m[3].capitalize()] and norm(x['startTime'])==norm(clock) for x in rows):continue
  rows.append({'daysOfWeek':[m[3].capitalize()],'startTime':clock,'timeText':clock+' ('+str(duration)+' minutes)','title':'Ages '+str(lo)+'–'+str(hi),'summary':m[0],'age_min':lo,'age_max':hi,'quote':m[0]})
 if not rows:raise ValueError('Missing explicit age-specific class timetable and duration; facility hours cannot satisfy this requirement')
 return rows

def class_price(text):
 matches=list(re.finditer(r'\$(\d+(?:\.\d{1,2})?)\s*per\s*class\b',text,re.I))
 amounts={float(m[1]) for m in matches}
 if len(amounts)!=1:raise ValueError('Missing or ambiguous per-class price. Session/camp prices must not be treated as per-class fees')
 return {'evidence':'stated','amount':next(iter(amounts)),'currency':'USD','unit':'class','sourceText':matches[0][0]}

# Third-party lists and directories describe many providers; they never establish one provider's listing.
LISTING_HOSTS={'newyorkfamily.com','newyorkloveskids.com','nymetroparents.com','amny.com','coursehorse.com','mommypoppins.com','activityhero.com','kidsdancemap.com','growingupnyc.cityofnewyork.us','yelp.com','tripadvisor.com','timeout.com','facebook.com','instagram.com','eventbrite.com','patch.com','care.com'}
BOROUGH_NAMES=['Brooklyn','Manhattan','Queens','Bronx','Staten Island']
def third_party_listing(url):
 host=(urllib.parse.urlsplit(str(url)).hostname or '').lower()
 return any(host==h or host.endswith('.'+h) for h in LISTING_HOSTS)

def normalize_sources(brief,pages,facts):
 if any(third_party_listing(page['url']) for page in pages):raise ValueError('The source is a third-party list or directory, not the provider; a first-party provider page is required')
 text='\n'.join(p['text'] for p in pages)
 for field in ['Publication name','Borough','Neighborhood','Activity']:
  if norm(brief[field]) not in norm(text):raise ValueError(field+' is not supported by these source pages')
 if not re.search(r'\b'+('camps?' if brief['Format']=='Camps' else 'class(?:es)?')+r'\b',text,re.I):raise ValueError('Program format not evidenced')
 # No stale or fabricated fact is inherited from the seven-field research draft.
 valid={}
 for f in facts:
  if any(norm(f['quote']) in norm(p['text']) and norm(f['value']) in norm(f['quote']) for p in pages):valid[f['field']]=f['value']
 if not valid.get('address') or not re.search(r'\d',valid['address']):raise ValueError('Missing source-verified street address')
 named=[b for b in BOROUGH_NAMES if re.search(r'\b'+b+r'\b',valid['address'],re.I)]
 if named and brief['Borough'] not in named:raise ValueError('The brief borough '+brief['Borough']+' conflicts with the verified address, which names '+', '.join(named))
 if '|' in brief['Publication name']:raise ValueError('The publication name looks like a page title (it contains "|"); a clean provider name is required')
 try:price=formats.price(text,brief['Format'])
 except ValueError as error:
  if brief['Format']=='Camps':raise
  price={'evidence':'unknown'}
 exact=price.get('unit')!='class' or brief['Format']=='Camps';ages=formats.ages(text,exact)
 try:schedules=formats.schedules(text,brief['Format'],exact)
 except ValueError:
  if brief['Format']=='Camps':raise
  schedules=[]
 lo=min(a['min'] for a in ages);hi=max(a['max'] for a in ages)
 # Every class group must fit explicit source-supported ages, never the reverse.
 for s in schedules:
  if not any(formats.bounds(a)[0]<=formats.bounds(s,True)[0] and formats.bounds(a)[1]>=formats.bounds(s,True)[1] for a in ages):raise ValueError('Timetable age range lacks supporting evidence')
 contact={'website':pages[0]['url']}
 for field in ['phone','email']:
  if valid.get(field):contact[field]=valid[field]
 age_text='; '.join(a['quote'] for a in ages)
 overview=(f"{brief['Publication name']} offers {brief['Activity'].lower()} {brief['Format'].lower()} for children {age_text} at {valid['address']} in {brief['Neighborhood']}, {brief['Borough']}." if any(a.get('unit')=='month' for a in ages) or brief['Format']=='Camps' else f"{brief['Publication name']} offers {brief['Activity'].lower()} classes for children ages {lo}–{hi} at {valid['address']} in {brief['Neighborhood']}, {brief['Borough']}.")
 detail=' '.join(('The '+str(s['age_min'])+'–'+str(s['age_max'])+' age group' if not any(a.get('unit')=='month' for a in ages) else s['title'])+' meets on '+s['daysOfWeek'][0]+' at '+s['timeText']+'.'+(' Camp dates: '+s['startDate']+' to '+s['endDate']+'.' if s.get('startDate') else '') for s in schedules)
 price_line=formats.price_sentence(price) if price.get('evidence')!='unknown' else ''
 normalized={'title':brief['Publication name'],'listingKindHint':'provider','categoryHint':brief['Format'],'boroughRaw':brief['Borough'],'neighborhoodRaw':brief['Neighborhood'],'addressRaw':valid['address'],'activityTypesRaw':[brief['Activity']],'ageRangesRaw':buckets(lo,hi),'scheduleBlocks':[{k:v for k,v in s.items() if k not in {'quote','age_min','age_max','age_min_months','age_max_months','startDate','endDate'}} for s in schedules],'descriptionFacts':[overview],'contactFacts':contact,'sourceUrls':{'canonical':pages[0]['url'],'additional':[p['url'] for p in pages[1:]]},'lastVerifiedAtRaw':stamp(),'verificationStatusRaw':'source_reviewed'}
 proof={'sources':[{'url':p['url'],'title':p['title'],'sha256':p['sha256'],'fetched_at':p['fetched_at']} for p in pages],'ages':ages,'schedules':schedules,'price':price,'facts':[{k:f[k] for k in ['field','value','quote']} for f in facts if f['field'] in valid],'normalized':normalized}
 return normalized,proof

def collect_for_publication(brief,web,facts):
 pages=[];tried=set();pending=list(brief['urls']);host=urllib.parse.urlsplit(pending[0]).hostname.removeprefix('www.');last_error='No accepted source pages'
 while pending and len(tried)<4:
  url=pending.pop(0)
  if url in tried:continue
  tried.add(url)
  try:
   page=web.page(url)
   if urllib.parse.urlsplit(page['url']).hostname.removeprefix('www.')!=host:raise ValueError('Source redirected to another provider host')
   pages.append(page)
   normalized,proof=normalize_sources(brief,pages,facts)
   if all(u in tried for u in brief['urls']):return pages,normalized,proof
  except ValueError as error:last_error=str(error)
  except Exception as error:last_error='Source could not be read: '+type(error).__name__
  if pages:
   for raw in pages[-1].get('links',[]):
    try:link=canonical_url(urllib.parse.urljoin(pages[-1]['url'],raw))
    except Exception:continue
    path=urllib.parse.urlsplit(link).path.lower()
    if urllib.parse.urlsplit(link).hostname.removeprefix('www.')!=host or re.search(r'adult|privacy|terms|login|account|billing',path):continue
    if re.search(r'kids|children|class|schedule|pricing|tuition|contact',path) and link not in tried and link not in pending:pending.append(link)
 raise ValueError(last_error+'; checked '+str(len(tried))+' source pages. Add a focused official program/pricing/schedule page and correct the brief.')

def media_candidates(pages):
 urls=[]
 for p in pages:
  for raw in p.get('images',[]):
   try:
    url=canonical_url(urllib.parse.urljoin(p['url'],raw));host=urllib.parse.urlsplit(url).hostname
    public_addresses(host,443 if url.startswith('https:') else 80)
    if not url.startswith('https:') or url in urls:continue
    if re.search(r'logo|icon|pixel|tracking|\.svg(?:\?|$)',url,re.I):continue
    urls.append(url)
   except Exception:continue
   if len(urls)>=5:return urls
 return urls

def category_banner(media):
 # ClassScout's own hosted category banner, used when no official image qualifies (owner decision 2026-10-30).
 media=media or {}
 return media.get('status')=='ready' and (media.get('qualification') or {}).get('status')=='accepted' and any(d.get('code')=='content_card_category_banner_fallback' for d in media.get('diagnostics',[])) and urllib.parse.urlsplit(media.get('uploadedUrl') or '').hostname=='i.ibb.co'

def completed_body(prepared,proof,issue_id):
 if not prepared.get('gateResult',{}).get('approved'):raise ValueError('ClassScout publication blockers: '+('; '.join(x['code']+': '+x['message'] for x in prepared.get('gateResult',{}).get('errors',[])))[:1400])
 resolved=prepared['resolvedDraft'];draft=copy.deepcopy(resolved['draft'])
 expected=proof['normalized']
 for field,source in [('name','title'),('category','categoryHint'),('borough','boroughRaw'),('neighborhood','neighborhoodRaw'),('address','addressRaw')]:
  if norm(draft.get(field))!=norm(expected[source]):raise ValueError('Canonical adapter changed source-backed '+field+'; review before approval')
 if prepared['entityKind']!='provider':raise ValueError('Only provider publications are supported')
 media=prepared.get('mediaResult') or {}
 if not (proof.get('image_placeholder') is True and category_banner(media)) and (media.get('status')!='ready' or media.get('originalUrl') not in proof.get('image_candidates',[]) or media.get('sourceDocumentUrl') not in [p['url'] for p in proof['sources']]):raise ValueError('Prepared image lacks checked official-page provenance')
 draft['price']={**proof['price'],'sourceUrl':proof['sources'][0]['url'],'observedAt':stamp()};draft['pricePerClass']=proof['price'].get('amount',0)
 ages=proof['ages'];lo=min(a['min'] for a in ages);hi=max(a['max'] for a in ages);draft.update(ageMinMonths=min(formats.bounds(a)[0] for a in ages),ageMaxMonths=max(formats.bounds(a)[1] for a in ages),ageSourceText=formats.age_evidence(ages))
 programs=draft.get('recurringPrograms',[])
 if len(programs)!=len(proof['schedules']):raise ValueError('ClassScout schedule mapping changed; review adapter compatibility')
 for rp,source in zip(programs,proof['schedules']):
  rp['ageRanges']=buckets(source['age_min'],source['age_max']);rp['ageMinMonths'],rp['ageMaxMonths']=formats.bounds(source,True);
  if source.get('startDate'):rp.update(startDate=source['startDate'],endDate=source['endDate'])
  rp['price']={**proof['price'],'sourceUrl':proof['sources'][0]['url']}
 return {'draftId':'paperclip-'+issue_id,'entityKind':'provider','draftPayload':draft,'adapterVersion':resolved['adapterVersion'],'mediaResult':prepared.get('mediaResult'),'workflowMetadata':{'source':'paperclip','issueId':issue_id},'idempotencyKey':'paperclip:'+issue_id}

# Human-approval mode only (used when automatic_quality_gate is off).
def approval_valid(interaction,packet,company,reviewer):
 return bool(interaction and interaction.get('kind')=='request_confirmation' and interaction.get('companyId')==company and interaction.get('issueId')==packet['issue_id'] and interaction.get('status')=='accepted' and interaction.get('resolvedByUserId')==reviewer and not interaction.get('resolvedByAgentId') and interaction.get('effectiveResolverPolicy')=='human_only' and interaction.get('idempotencyKey')=='publish-'+packet['packet_hash'] and interaction.get('result',{}).get('outcome')=='accepted' and packet['packet_hash'] in (interaction.get('payload',{}).get('detailsMarkdown') or ''))

def review_markdown(body,proof,packet_hash):
 d=body['draftPayload'];esc=lambda value:re.sub(r'([\\`*_\[\]{}|!<>])',r'\\\1',str(value));lines=['## Ready for publication review','',esc(d['name']),'',esc(d['shortDescription']),'',esc(d['longDescription']),'', '**Location:** '+esc(d['address'])+'; '+esc(d['neighborhood'])+', '+esc(d['borough']), ('**Price:** unknown; not advertised as free.' if proof['price']['evidence']=='unknown' else '**Price:** $'+format(proof['price']['amount'],'g')+' per '+proof['price']['unit']+'.'),'**Ages:** '+', '.join(a['quote'] for a in proof['ages']), '', '**Class timetable:**']
 for s in proof['schedules']:lines.append('- '+s['title']+': '+s['daysOfWeek'][0]+', '+s['timeText'])
 lines+=['','**Official sources:**']+[ '- '+p['url'] for p in proof['sources']]
 if d.get('image'):lines+=['','**Prepared listing image:**' if not proof.get('image_placeholder') else '**Listing image: ClassScout category banner. No official image qualified; replace it when one is found.**','![Listing image]('+d['image']+')']
 lines+=['','Approve to publish this exact listing through ClassScout’s final duplicate, image and schema checks. The final gate may still refuse it. Approval expires after 48 hours. No listing has been published yet.','','Packet: `'+packet_hash+'`']
 return '\n'.join(lines)

def receipt_markdown(body,receipt,state):
 name=body['draftPayload']['name'];entity_id=urllib.parse.quote(body['draftPayload']['id'],safe='')
 core=receipt.get('catalogVerification',{});saved=bool(core.get('private_verified') or receipt.get('privateVerification',{}).get('verified'));visible=bool(core.get('verified') and core.get('origin')==ClassScout.BASE or receipt.get('publicVerification',{}).get('verified') and receipt.get('publicVerification',{}).get('verificationSource')=='public-api')
 lines=['## '+('Published to ClassScout' if state=='published' else 'Publication needs attention'),'',name,'','Catalog save: '+('confirmed' if saved else 'not confirmed')+'.','ClassScout catalog visibility: '+('confirmed' if visible else 'not confirmed')+'.']
 if state=='published':lines+=['','[Open the listing](https://classscout.ai/providers/'+entity_id+')']
 else:lines+=['','Check the saved receipt before retrying. The workflow will not automatically repeat an uncertain write.']
 return '\n'.join(lines)

def ensure_execution(issue,board,config,execution,input_hash):
 if not execution:raise ValueError('Publication requires a current authenticated Paperclip execution')
 current=board.call('/issues/'+issue['id']);run=board.call('/heartbeat-runs/'+execution['run_id'])
 if current.get('companyId')!=config['company_id'] or current.get('status')!='in_progress' or current.get('assigneeAgentId')!=execution['agent_id']:raise ValueError('Publication task was stopped or reassigned; no new write will be sent')
 if sha({'description':current.get('description'),'title':current['title'],'project':current['projectId']})!=input_hash:raise ValueError('Publication brief changed while executing; prepare a fresh review')
 if run.get('status')!='running' or run.get('agentId')!=execution['agent_id'] or run.get('companyId')!=config['company_id']:raise ValueError('Publication execution is no longer active')

def run(issue,board,config,web,database,client=None,execution=None):
 client=client or ClassScout();brief=parse_brief(issue);input_hash=sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']});reviewer=config.get('reviewer_user_id','local-board')
 with database() as db:
  initialize(db);row=db.execute('SELECT * FROM publication_packets WHERE issue_id=? ORDER BY created_at DESC LIMIT 1',(issue['id'],)).fetchone();packet=dict(row) if row else None
 # 'saved_hidden' is a legacy status that no current code assigns; it stays here so old rows can still be reconciled.
 if packet and packet['status'] in {'publishing','uncertain','partial','published','saved_hidden'}:
  if packet['status'] in {'partial','saved_hidden'}:
   receipt=json.loads(packet['receipt_json'] or '{}');body=json.loads(packet['body_json'])
   if reconcile_catalog(client,body,receipt):
    with database() as db:db.execute("UPDATE publication_packets SET status='published',receipt_json=?,updated_at=? WHERE packet_hash=? AND status IN ('partial','saved_hidden')",(json.dumps(receipt),stamp(),packet['packet_hash']))
    packet['status']='published';packet['receipt_json']=json.dumps(receipt)
  if packet['status']=='published':return {'stage':'published','markdown':receipt_markdown(json.loads(packet['body_json']),json.loads(packet['receipt_json']),'published'),'entities':[],'final_status':'done','automatic_write':quality_gate.enabled(config,issue)}
  raise ValueError('Publication receipt needs reconciliation ('+packet['status']+'). Do not submit another catalog write; inspect the existing entity and receipt first.')
 if packet and packet['input_hash']==input_hash and packet['status']=='prepared':
  return request_review(issue,board,config,database,json.loads(packet['body_json']),json.loads(packet['proof_json']),packet['packet_hash'],web,client,execution)
 if packet and packet['input_hash']==input_hash and packet['status']=='awaiting_approval':
  automatic=quality_gate.enabled(config,issue)
  interactions=board.call('/issues/'+issue['id']+'/interactions');interaction=next((x for x in interactions if x['id']==packet['interaction_id']),None)
  if interaction and interaction['status'] in {'rejected','withdrawn','cancelled','expired','skipped'}:return {'stage':'rejected','markdown':'Publication was declined. No catalog write was sent. Correct the brief and prepare a fresh packet.','entities':[]}
  if not automatic and not approval_valid(interaction,packet,config['company_id'],reviewer):return {'stage':'awaiting_approval','markdown':None,'entities':[]}
  age=datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(packet['created_at'])
  # Applies in automatic mode too. A packet left in awaiting_approval longer than 48 hours fails here on every rerun
  # until the brief text changes (that produces a new input_hash and a fresh packet).
  if age.total_seconds()>48*3600:raise ValueError('Publication approval expired; prepare a fresh source-checked packet')
  if issue['title'].startswith('[Factory test]'):raise ValueError('Synthetic factory tests cannot publish real catalog records')
  proof=json.loads(packet['proof_json']);body=json.loads(packet['body_json'])
  if sha({'body':body,'proof':proof})!=packet['packet_hash']:raise ValueError('Publication payload changed after approval')
  with database() as db:
   competing=db.execute("SELECT body_json FROM publication_packets WHERE issue_id<>? AND status IN ('publishing','uncertain','partial','published','saved_hidden')",(issue['id'],)).fetchall()
  if any(json.loads(row['body_json']).get('draftPayload',{}).get('id')==body['draftPayload']['id'] for row in competing):raise ValueError('Another packet already published or has an uncertain write for this provider. Reconcile it before continuing.')
  if client.existing_provider(body['draftPayload']['id']) is not None:raise ValueError('This provider already exists. Use the existing-listing review workflow; new publication must not overwrite it.')
  pages=[]
  for old in proof['sources']:
   page=web.page(old['url']);pages.append(page)
   if page['sha256']!=old['sha256']:raise ValueError('Source content changed after preparation; a new review is required')
  if automatic:quality_gate.check_publication(database,packet['packet_hash'],issue,body,proof,pages)
  ensure_execution(issue,board,config,execution,input_hash)
  # Order matters. The daily reservation and the awaiting_approval -> publishing compare-and-set commit together BEFORE
  # the HTTP call. If the reply is lost the packet is marked 'uncertain' and is never resent automatically.
  with database() as db:
   db.execute('BEGIN IMMEDIATE')
   if automatic:quality_gate.reserve(db,packet['packet_hash'],config)
   changed=db.execute("UPDATE publication_packets SET status='publishing',updated_at=? WHERE packet_hash=? AND status='awaiting_approval'",(stamp(),packet['packet_hash'])).rowcount
   if changed!=1:raise ValueError('Publication already started; reconcile its existing receipt')
  try:receipt=client.call('/api/content-intelligence/publish-reviewed',body)
  except Exception:
   with database() as db:db.execute("UPDATE publication_packets SET status='uncertain',error=?,updated_at=? WHERE packet_hash=?",('No confirmed response; reconcile before retry',stamp(),packet['packet_hash']))
   raise ValueError('Publication response was not confirmed. Existing request must be reconciled before another write.') from None
  # Published only if ClassScout reports both verifications with these exact source labels (private-mongodb, public-api);
  # a skipped or differently labelled check is not success. This ties the factory to ClassScout's receipt wording.
  verified=receipt.get('status')=='published' and receipt.get('publishedEntityId')==body['draftPayload']['id'] and receipt.get('privateVerification',{}).get('verified') and receipt.get('publicVerification',{}).get('verified') and receipt.get('publicVerification',{}).get('verificationSource')=='public-api' and receipt.get('privateVerification',{}).get('verificationSource')=='private-mongodb'
  if not verified and receipt.get('status')=='partial':verified=reconcile_catalog(client,body,receipt)
  state='published' if verified else 'blocked' if receipt.get('status')=='blocked' else 'partial'
  with database() as db:db.execute('UPDATE publication_packets SET status=?,receipt_json=?,updated_at=? WHERE packet_hash=?',(state,json.dumps(receipt),stamp(),packet['packet_hash']))
  return {'stage':state,'markdown':receipt_markdown(body,receipt,state),'entities':[],'final_status':'done' if state=='published' else 'in_review','automatic_write':automatic}
 if packet and packet['input_hash']==input_hash and packet['status']=='blocked':raise ValueError('The unchanged publication brief is still blocked; correct its evidence before retrying')
 # New or corrected briefs must prove identity and completeness before any review request.
 with database() as db:
  entity=db.execute('SELECT * FROM entities WHERE id=? AND brand=?',(brief['Draft reference'],'ClassScout')).fetchone();facts=[dict(r) for r in db.execute('SELECT field,value,quote FROM facts WHERE entity_id=?',(brief['Draft reference'],))]
 if not entity:raise ValueError('Unknown ClassScout draft reference')
 if urllib.parse.urlsplit(entity['source_url']).hostname.removeprefix('www.')!=urllib.parse.urlsplit(brief['urls'][0]).hostname.removeprefix('www.'):raise ValueError('Research identity and publication sources have different hosts')
 with database() as db:extra=[r[0] for r in db.execute('SELECT DISTINCT s.url FROM sources s JOIN facts f ON f.source_id=s.id WHERE f.entity_id=?',(brief['Draft reference'],))]
 brief['urls']=list(dict.fromkeys(brief['urls']+[u for u in extra if urllib.parse.urlsplit(u).hostname.removeprefix('www.')==urllib.parse.urlsplit(brief['urls'][0]).hostname.removeprefix('www.')]))[:4]
 pages,normalized,proof=collect_for_publication(brief,web,facts);images=media_candidates(pages);proof['image_candidates']=images
 if execution:ensure_execution(issue,board,config,execution,input_hash)
 prepared=client.call('/api/content-intelligence/prepare-review',{'draftId':'paperclip-'+issue['id'],'normalizedListing':normalized,'evidenceSummary':{'sources':proof['sources']},'workflowMetadata':{'source':'paperclip','allowCategoryBannerFallback':True},'mediaRequest':{'candidateId':'paperclip-'+issue['id'],'sourceImageUrl':images[0],'fallbackImageUrls':images[1:],'sourceDocumentUrl':pages[0]['url'],'destinationEntityKind':'provider','requestedBy':'publication-workflow'} if images else None})
 if category_banner(prepared.get('mediaResult')):proof['image_placeholder']=True
 body=completed_body(prepared,proof,issue['id'])
 if client.existing_provider(body['draftPayload']['id']) is not None:raise ValueError('This provider already exists; route it to existing-listing review, not new publication')
 packet_hash=sha({'body':body,'proof':proof});markdown=review_markdown(body,proof,packet_hash)
 with database() as db:db.execute('INSERT INTO publication_packets VALUES(?,?,?,?,?,?,?,?,?,?,?)',(packet_hash,issue['id'],input_hash,'prepared',json.dumps(body),json.dumps(proof),None,None,None,stamp(),stamp()))
 return request_review(issue,board,config,database,body,proof,packet_hash,web,client,execution)

def request_review(issue,board,config,database,body,proof,packet_hash,web=None,client=None,execution=None):
 if sha({'body':body,'proof':proof})!=packet_hash:raise ValueError('Prepared publication packet failed integrity check')
 if quality_gate.enabled(config,issue):
  with database() as db:db.execute("UPDATE publication_packets SET status='awaiting_approval',updated_at=? WHERE packet_hash=? AND status='prepared'",(stamp(),packet_hash))
  return run(issue,board,config,web,database,client,execution)
 brief=parse_brief(issue);reviewer=config.get('reviewer_user_id','local-board');markdown=review_markdown(body,proof,packet_hash)
 interaction=board.call('/issues/'+issue['id']+'/interactions',{'kind':'request_confirmation','idempotencyKey':'publish-'+packet_hash,'resolverPolicy':'human_only','addresseeUserId':reviewer,'title':'Publish '+brief['Publication name']+' to ClassScout','summary':'Complete source-backed listing, prepared image and final ClassScout checks.','continuationPolicy':'wake_assignee','payload':{'version':1,'prompt':'Publish this exact listing to ClassScout?','acceptLabel':'Publish listing','rejectLabel':'Request changes','detailsMarkdown':markdown,'supersedeOnUserComment':False}})
 with database() as db:db.execute("UPDATE publication_packets SET status='awaiting_approval',interaction_id=?,updated_at=? WHERE packet_hash=?",(interaction['id'],stamp(),packet_hash))
 return {'stage':'awaiting_approval','markdown':markdown,'entities':[],'packet_hash':packet_hash}
