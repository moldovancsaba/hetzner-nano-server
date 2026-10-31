"""Literal source recovery and branch-specific identity; no inferred contact corrections."""
import json,re,time,urllib.parse
import candidates,publishing
from net import canonical_url
STREET=re.compile(r'\b\d{1,6}(?:-\d{1,4})?[ \t]+(?:(?:[A-Za-z0-9][A-Za-z0-9.\'’-]*|[NSEW])[ \t]+){1,7}?(?:Street|Avenue|Boulevard|Road|Drive|Lane|Place|Court|Terrace|Parkway|St\.?|Ave\.?|Blvd\.?|Rd\.?|Dr\.?|Ln\.?|Pl\.?|Ct\.?|Way)\b',re.I)
def address_key(value):
 value=str(value).casefold()
 for a,b in [('saint','st'),('avenue','ave'),('street','st'),('boulevard','blvd'),('road','rd'),('drive','dr'),('lane','ln'),('place','pl'),('court','ct'),('terrace','ter'),('parkway','pkwy'),('north','n'),('south','s'),('east','e'),('west','w')]:value=re.sub(r'\b'+a+r'\b',b,value)
 return re.sub(r'[^a-z0-9]','',value)
def street(value):
 m=STREET.search(str(value));return m.group(0) if m else None
def address_matches(expected,text):
 anchor=street(expected)
 return bool(anchor and any(address_key(anchor)==address_key(m.group(0)) for m in STREET.finditer(text)))
def host(url):return (urllib.parse.urlsplit(url).hostname or '').removeprefix('www.').lower()
def crawl(url,web,extra=(),maximum=4):
 origin=canonical_url(url);allowed=host(origin);pending=[origin]+list(extra);root=urllib.parse.urlunsplit((*urllib.parse.urlsplit(origin)[:2],'/','',''));seen=set();pages=[]
 while pending and len(seen)<maximum:
  current=pending.pop(0)
  try:
   current=canonical_url(current)
   if host(current)!=allowed or current in seen:continue
   seen.add(current);page=web.page(current)
   if host(page['url'])!=allowed:continue
   pages.append(page)
   links=[]
   for raw in page.get('links',[]):
    try:link=canonical_url(urllib.parse.urljoin(page['url'],raw))
    except Exception:continue
    if host(link)!=allowed or re.search(r'login|account|privacy|terms|billing|\.pdf$',urllib.parse.urlsplit(link).path,re.I):continue
    if re.search(r'contact|location|studio|about|find-us',urllib.parse.urlsplit(link).path,re.I):links.append(link)
   pending.extend(x for x in links+[root] if x not in seen and x not in pending)
  except Exception:continue
 return pages

def names(page,expected=None):
 text=page['text'];results=[]
 if expected and publishing.norm(expected) in publishing.norm(text):return [expected]
 title=page.get('title','');stem=re.sub(r'[^a-z0-9]','',host(page['url']).split('.')[0])
 for name in re.split(r'\s*(?:[|•–—]|::)\s*',title):
  name=name.strip()
  compact=re.sub(r'[^a-z0-9]','',name.lower());compact=compact.removeprefix('the')
  owned=compact==stem or min(len(compact),len(stem))>=10 and (compact.startswith(stem) or stem.startswith(compact))
  if 3<=len(name)<=100 and owned and publishing.norm(name) in publishing.norm(text):results.append(name)
 return list(dict.fromkeys(results))
def literal_facts(page):
 """Fallback for exact visible identity, never prices, schedules or categories."""
 candidates=names(page)
 if len(candidates)!=1:return []
 facts=[{'field':'name','value':candidates[0],'quote':candidates[0]}]
 streets={address_key(m.group(0)):m.group(0) for m in STREET.finditer(page['text'])}
 if len(streets)==1:
  value=next(iter(streets.values()));facts.append({'field':'address','value':value,'quote':value})
 return facts

def initialize(database):
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS evidence_recovery(entity_id TEXT PRIMARY KEY,attempted_at REAL,input_hash TEXT,result_json TEXT)')
def recover(entity,database,web,baseline=None):
 initialize(database)
 with database() as db:
  rows=[dict(r) for r in db.execute('SELECT f.*,s.url FROM facts f JOIN sources s ON s.id=f.source_id WHERE entity_id=?',(entity['id'],))]
  previous=db.execute('SELECT * FROM evidence_recovery WHERE entity_id=?',(entity['id'],)).fetchone()
 signature=publishing.sha({'source':entity['source_url'],'facts':rows,'baseline':baseline})
 if previous and previous['input_hash']==signature and time.time()-previous['attempted_at']<3600:return json.loads(previous['result_json'])
 pages=crawl(entity['source_url'],web,[r['url'] for r in rows]);found=[]
 existing={r['field'] for r in rows}
 if 'name' not in existing:
  candidates=[(n,p) for p in pages for n in names(p,baseline.get('name') if baseline else None)]
  unique={publishing.norm(n) for n,p in candidates}
  if len(unique)==1:found.append(('name',candidates[0][0],candidates[0][1]))
 if 'address' not in existing:
  candidates=[(m.group(0),p) for p in pages for m in STREET.finditer(p['text'])]
  if baseline:candidates=[(v,p) for v,p in candidates if address_matches(baseline.get('address'),v)]
  unique={address_key(v) for v,p in candidates}
  if len(unique)==1:found.append(('address',candidates[0][0],candidates[0][1]))
 with database() as db:
  for field,value,page in found:
   sid=__import__('hashlib').sha256((page['url']+'|'+page['sha256']).encode()).hexdigest()
   db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?)',(sid,page['url'],page['title'],page['sha256'],publishing.stamp()))
   db.execute('INSERT OR IGNORE INTO facts VALUES(?,?,?,?,?)',(entity['id'],field,value,value,sid))
   if field=='name':db.execute('UPDATE entities SET name=? WHERE id=?',(value,entity['id']))
  report={'added_fields':[x[0] for x in found],'recovered_fields':sorted(set([x[0] for x in found]+(json.loads(previous['result_json']).get('recovered_fields',[]) if previous else []))),'pages_checked':[p['url'] for p in pages],'ambiguous_address':len({address_key(m.group(0)) for p in pages for m in STREET.finditer(p['text'])})>1,'method':'literal same-host source pages; unique street or exact known branch'}
  db.execute('INSERT INTO evidence_recovery VALUES(?,?,?,?) ON CONFLICT(entity_id) DO UPDATE SET attempted_at=excluded.attempted_at,input_hash=excluded.input_hash,result_json=excluded.result_json',(entity['id'],time.time(),signature,json.dumps(report)))
 return report

def branch_name_matches(baseline,page,facts):
 def n(value):
  value=re.sub(r'[-’\']',' ',publishing.norm(value))
  value=re.sub(r'\btheatre\b','theater',value)
  value=re.sub(r'\bbrazilian\s+jiu\s+jitsu\b','jiu jitsu',value)
  return re.sub(r'\s+',' ',value).strip()
 if n(baseline.get('name','')) in n(page['text']):return True
 # A brand-level heading may omit the catalog's locality suffix; street identity still must match.
 for f in facts:
  value=f.get('value','');a=n(baseline.get('name',''));b=n(value)
  if f.get('field')=='name' and len(b)>=8 and len(b.split())>=2 and n(f.get('quote','')) in n(page['text']) and b in n(f['quote']) and (a.startswith(b+' ') or b.startswith(a+' ')):return True
 return False

def branch_page(baseline,url,facts,web):
 if not street(baseline.get('address')):raise ValueError('Catalog location is not a specific street address; branch correction is held')
 for page in crawl(url,web):
  if not address_matches(baseline['address'],page['text']) or not branch_name_matches(baseline,page,facts):continue
  matches=list(STREET.finditer(page['text']));target=next(m for m in matches if address_key(m.group(0))==address_key(street(baseline['address'])))
  units=re.findall(r'\b(?:suite|ste\.?|unit|floor)\s+([A-Za-z0-9-]+)\b',baseline.get('address',''),re.I)
  if units and not all(re.search(r'\b(?:suite|ste\.?|unit|floor)\s+'+re.escape(unit)+r'\b',page['text'][max(0,target.start()-60):target.end()+100],re.I) for unit in units):continue
  scoped=page['text'] if len({address_key(m.group(0)) for m in matches})==1 else page['text'][max(0,target.start()-80):min(next((m.start() for m in matches if m.start()>target.start()),len(page['text'])),target.end()+450)]
  def local_quote(quote):
   if len({address_key(m.group(0)) for m in matches})==1:return publishing.norm(quote) in publishing.norm(page['text'])
   for occurrence in re.finditer(re.escape(quote),page['text'],re.I):
    distances=[(min(abs(occurrence.start()-m.end()),abs(occurrence.end()-m.start())),address_key(m.group(0))) for m in matches]
    best=min(d[0] for d in distances);nearest={key for distance,key in distances if distance==best}
    if best<=180 and nearest=={address_key(target.group(0))}:return True
   return False
  valid=[f for f in facts if publishing.norm(f.get('value')) in publishing.norm(f.get('quote')) and publishing.norm(f.get('quote')) in publishing.norm(page['text']) and (f['field'] not in {'phone','email'} or local_quote(f['quote']))]
  # Recover literal contacts only inside the selected branch's own text block.
  for field,pattern in [('email',r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),('phone',r'(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}')]:
   values={v for v in re.findall(pattern,page['text']) if local_quote(v)}
   if len(values)==1 and not any(f['field']==field for f in valid):valid.append({'field':field,'value':next(iter(values)),'quote':next(iter(values))})
  valid.append({'field':'address','value':target.group(0),'quote':target.group(0)})
  return page,valid,{'street':target.group(0),'source_url':page['url'],'scope':'one physical branch','contact_scope':'branch block' if len(matches)>1 else 'single street on source page'}
 raise ValueError('No official page uniquely confirmed the catalog street and provider identity; no correction was proposed')

def run_queue(issue,board,config,web,database,execution):
 initialize(database)
 import pipeline
 with database() as db:
  db.execute('CREATE TABLE IF NOT EXISTS evidence_rechecks(entity_id TEXT PRIMARY KEY,queued_at REAL,task_id TEXT)')
  # The two candidates touched longest ago that were not rechecked in the last day; skipped or failed ones still move back.
  entities=candidates.take(db,'needs_more_evidence',2,where='AND NOT EXISTS(SELECT 1 FROM evidence_rechecks r WHERE r.entity_id=e.id AND r.queued_at>=?)',args=(time.time()-86400,))
 children=[];quality=next(k for k,v in config['agents'].items() if v['role']=='quality')
 for entity in entities:
  source=board.call('/issues/'+entity['issue_id'])
  if '[Factory test]' in source.get('title',''):continue
  child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'evidence-recheck-'+entity['id']+'-'+str(int(time.time()//86400)),'title':'Recover and verify evidence: '+entity['name'][:120],'projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':quality,'reviewPolicy':'anyone','description':'Factory workflow: source_quality\nDraft reference: '+entity['id']+'\n'+pipeline.metadata(source)+'\n\nRe-fetch up to four same-provider pages and recover only unambiguous literal missing identity/address evidence. Preserve branch boundaries.\n'+entity['source_url']})
  with database() as db:db.execute('INSERT INTO evidence_rechecks VALUES(?,?,?) ON CONFLICT(entity_id) DO UPDATE SET queued_at=excluded.queued_at,task_id=excluded.task_id',(entity['id'],time.time(),child['id']))
  children.append(child['identifier'])
 return {'stage':'evidence_rechecks_queued','entities':[],'final_status':'done','automatic_progress':True,'markdown':'## Evidence recovery queue\n\nIndependent quality rechecks: '+(', '.join(children) or 'none due')+'. Each recheck can read four official same-host pages. Ambiguous branches remain held; no model or Brave request was made by this coordinator.'}
