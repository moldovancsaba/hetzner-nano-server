"""Bounded production commissioning and recurring discovery, sharing existing quotas."""
import json,re,time,urllib.parse,urllib.request
import catalog,publishing,search_workflow
from search_budget import Budget
BOROUGHS=['Brooklyn','Manhattan','Queens','Bronx','Staten Island']
ACTIVITIES=['Music','Art','STEM','Dance','Swimming','Gymnastics','Soccer','Basketball','Tennis','Martial Arts','Theater','Coding']
ANGLES=['official program registration ages schedule tuition price','weekly classes per class pricing','after school classes timetable','weekend classes ages tuition','drop in class duration price','official children program ages timetable fees registration']
LOCATION_CACHE=None

def intents():
 # Interleave activities and boroughs before trying a different search angle.
 return [{'format':'Classes','borough':b,'activity':a,'query':'kids '+a+' classes '+b+' NYC '+angle} for angle in ANGLES for a in ACTIVITIES for b in BOROUGHS]+[{'format':'Camps','borough':b,'activity':a,'query':'kids '+a+' camp '+b+' NYC dates schedule weekly tuition official'} for a in ACTIVITIES for b in BOROUGHS]

def initialize(database):
 with database() as db:db.executescript('''CREATE TABLE IF NOT EXISTS growth_cursor(id INTEGER PRIMARY KEY CHECK(id=1),position INTEGER); INSERT OR IGNORE INTO growth_cursor VALUES(1,0); CREATE TABLE IF NOT EXISTS commissioning_checks(entity_id TEXT PRIMARY KEY,checked_at REAL,result_json TEXT);''')

def run(issue,board,config,web,database,execution,budget=None):
 if not config.get('growth_mode',{}).get('enabled'):raise ValueError('Production growth mode is disabled')
 initialize(database);search_workflow.initialize(database);budget=budget or Budget(database);status=budget.status();backlog=search_workflow.research_backlog(board,config,database);reason=None
 with database() as db:pending=db.execute("SELECT count(*) FROM search_jobs WHERE status IN ('queued','running','delivery_pending')").fetchone()[0]
 if backlog>=10:reason='Production research queue is full; discovery waits for work to drain.'
 elif pending>=2:reason='Existing search intents have priority; no extra search task was created.'
 elif time.time()<status['next_search_at']:reason='Shared Brave cooldown is still active.'
 elif status['used_today']>=status['daily_limit'] or status['used_this_window']>=status['automatic_limit'] or status['estimated_account_remaining']<=status['reserve']:reason='Shared Brave allowance is reserved or exhausted.'
 target=None
 if not reason:
  choices=intents()
  with database() as db:
   position=db.execute('SELECT position FROM growth_cursor WHERE id=1').fetchone()[0]
   recent=[dict(r) for r in db.execute("SELECT issue_id,queries_json FROM search_jobs WHERE created_at>? AND status<>'cancelled'",(time.time()-7*86400,))]
   seen={search_workflow.fingerprint(q) for r in recent for q in json.loads(r['queries_json'])}
  selected=next(((position+n,choices[(position+n)%len(choices)]) for n in range(len(choices)) if search_workflow.fingerprint(choices[(position+n)%len(choices)]['query']) not in seen),None)
  if selected:
   index,item=selected;agent=next(k for k,v in config['agents'].items() if v['role']=='search');week=int(time.time()//(7*86400))
   description='Search purpose: discovery\nSearch query: '+item['query']+'\nDiscovery borough: '+item['borough']+'\nDiscovery activity: '+item['activity']+'\nDiscovery format: '+item['format']+'\nDiscovery campaign: classscout-nyc-v1\n\nFind official children class/program pages. Query terms are research hints, not listing facts. Fetch sources directly and preserve evidence. Shared cooldown and monthly reserve remain mandatory.'
   target=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'growth-'+str(week)+'-'+search_workflow.fingerprint(item['query']),'projectId':issue['projectId'],'parentId':issue['id'],'title':'Discover '+item['activity']+' '+item['format'].lower()+' in '+item['borough'],'description':description,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone'})
   with database() as db:db.execute('UPDATE growth_cursor SET position=? WHERE id=1',((index+1)%len(choices),))
  else:reason='All campaign intents were covered in the seven-day deduplication window.'
 report={'production_research_backlog':backlog,'pending_search_jobs':pending,'created_task':target.get('identifier') if target else None,'reason':reason,'budget':status};catalog.save_report(database,issue,'growth_dispatch',report)
 return {'stage':'growth_dispatched','entities':[],'markdown':'## Production discovery\n\n'+('Queued '+target['identifier']+'.' if target else reason)+'\n\nBrave remains limited to one request per shared 30-minute slot, 48/day and 1,800 per provider allowance period. Only independently fetched source evidence may advance.','final_status':'done','automatic_progress':True,'report':report}

def locations():
 global LOCATION_CACHE
 if LOCATION_CACHE and time.time()-LOCATION_CACHE[0]<3600:return LOCATION_CACHE[1]
 with urllib.request.build_opener(catalog.NoRedirect).open(publishing.ClassScout.BASE+'/api/public/locations?city=nyc',timeout=25) as r:
  raw=r.read(262145)
  if len(raw)>262144:raise ValueError('Location vocabulary exceeded its response bound')
  value=json.loads(raw)
 if not isinstance(value,dict) or not value or any(b not in BOROUGHS or not isinstance(v,list) or any(not isinstance(n,str) or not 1<len(n)<120 for n in v) for b,v in value.items()):raise ValueError('Canonical location vocabulary is unavailable')
 LOCATION_CACHE=(time.time(),value);return value

def present(value,text):return bool(re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',text,re.I))
def gap_reason(database,entity_id):
 """The last stored first-gap sentence for a draft, or None when it has not been checked yet."""
 initialize(database)
 with database() as db:row=db.execute('SELECT result_json FROM commissioning_checks WHERE entity_id=?',(entity_id,)).fetchone()
 return json.loads(row[0]).get('reason') if row else None

def established(facts,pages,key):
 n=publishing.norm
 return {f['value'] for f in facts if f['field']==key and n(f['value']) in n(f['quote']) and n(f['quote']) in n(pages.get(f['url'],{}).get('text',''))}

def evaluate(issue,row,facts,pages,known,vocabulary):
 """The editorial brief from page evidence, or the fields that blocked it, first failure first.

 Returns (brief, gaps); gaps is a list of (field, detail) and is empty when the brief is complete."""
 combined='\n'.join(p['text'] for p in pages.values());values={};gaps=[]
 for key in ['name','address']:
  found=established(facts,pages,key)
  if len(found)==1:values[key]=next(iter(found))
  else:gaps.append((key,'is not established by a quoted source line' if not found else 'has %d conflicting quoted values'%len(found)))
 if set(values)=={'name','address'}:
  import evidence
  matches=[p for p in known if not p.get('owner_managed') and publishing.norm(p.get('name'))==publishing.norm(values['name']) and evidence.host(p.get('website',''))==evidence.host(row['source_url']) and evidence.address_matches(p.get('address'),values['address'])]
  if len(matches)==1:return {'Catalog provider':matches[0]['id']},[]
 borough=catalog.field(issue,'Discovery borough');activity=catalog.field(issue,'Discovery activity');kind=catalog.field(issue,'Discovery format','Classes')
 for key,hint,choices in [('borough',borough,BOROUGHS),('activity',activity,ACTIVITIES)]:
  named=[c for c in choices if present(c,combined)]
  if hint not in choices:gaps.append((key,'has no valid search hint'))
  elif hint not in named:gaps.append((key,'"%s" is not named on the source pages%s'%(hint,' (they name '+', '.join(named)+')' if named else '')))
 if kind not in {'Classes','Camps'} or not re.search(r'\b'+('camps?' if kind=='Camps' else 'classes?')+r'\b',combined,re.I):gaps.append(('format','is not evidenced: the source pages do not use the word "%s"'%('camp' if kind=='Camps' else 'class')))
 neighborhoods=[]
 if borough in BOROUGHS:
  neighborhoods=[x for x in vocabulary().get(borough,[]) if present(x,combined)]
  # Multiple locations on a provider page need a more focused page; never pick the first.
  if len(neighborhoods)!=1:gaps.append(('neighborhood','is missing: no %s neighborhood is named on the source pages'%borough if not neighborhoods else 'is ambiguous: %d %s neighborhoods are named (%s); a focused page is needed'%(len(neighborhoods),borough,', '.join(neighborhoods[:6]))))
 if gaps:return {},gaps
 return {'Publication name':values['name'],'Borough':borough,'Neighborhood':neighborhoods[0],'Format':kind,'Activity':activity},[]

def remote_candidates(issue,gaps,combined,vocabulary):
 """What the metered model may choose between: only values the pages already name. Empty when a gap cannot be settled that way."""
 fields={f for f,_ in gaps}
 if not fields or fields-{'borough','activity','neighborhood'}:return {}
 candidates={};boroughs=[b for b in BOROUGHS if present(b,combined)]
 if 'borough' in fields:
  if not boroughs:return {}
  candidates['borough']=boroughs
 if 'activity' in fields:
  activities=[a for a in ACTIVITIES if present(a,combined)]
  if not activities:return {}
  candidates['activity']=activities
 if 'neighborhood' in fields or 'borough' in fields:
  hint=catalog.field(issue,'Discovery borough');names=sorted({x for b in (boroughs if 'borough' in fields else [hint]) for x in vocabulary().get(b,[]) if present(x,combined)})
  if len(names)<(1 if 'borough' in fields else 2):return {}
  candidates['neighborhood']=names
 return candidates

def settle(issue,choices,values,pages,vocabulary):
 """Apply quoted, address-tied choices, then rerun the deterministic checks. Returns (brief, accepted, rejected)."""
 n=publishing.norm;texts=[n(p['text']) for p in pages.values()];combined='\n'.join(p['text'] for p in pages.values());accepted={};rejected=[]
 import evidence
 for c in choices:
  quote=c['quote']
  # A quote must be on the pages, hold the value, and (for place) sit beside this location's street address.
  if len(quote)<=240 and any(n(quote) in t for t in texts) and n(c['value']) in n(quote) and (c['field']=='activity' or evidence.address_matches(values['address'],quote)):accepted[c['field']]=c['value']
  else:rejected.append({'field':c['field'],'detail':'the quote is not on the pages, does not hold the value, or is not tied to the address'})
 borough=accepted.get('borough') or catalog.field(issue,'Discovery borough');activity=accepted.get('activity') or catalog.field(issue,'Discovery activity');kind=catalog.field(issue,'Discovery format','Classes')
 if borough not in BOROUGHS or activity not in ACTIVITIES or not present(borough,combined) or not present(activity,combined) or kind not in {'Classes','Camps'} or not re.search(r'\b'+('camps?' if kind=='Camps' else 'classes?')+r'\b',combined,re.I):return {},accepted,rejected
 listed=vocabulary().get(borough,[]);named=[x for x in listed if present(x,combined)];neighborhood=accepted.get('neighborhood') or (named[0] if len(named)==1 else None)
 if neighborhood not in named:return {},accepted,rejected
 return {'Publication name':values['name'],'Borough':borough,'Neighborhood':neighborhood,'Format':kind,'Activity':activity},accepted,rejected

def refine(issue,row,facts,pages,gaps,vocabulary,database,config,role,previous):
 """Let the metered model choose between values the pages name. Returns (brief, record); the deterministic gaps stand otherwise."""
 import segmind
 combined='\n'.join(p['text'] for p in pages.values());names=established(facts,pages,'name');addresses=established(facts,pages,'address')
 if len(names)!=1 or len(addresses)!=1:return {},None
 values={'name':next(iter(names)),'address':next(iter(addresses))};candidates=remote_candidates(issue,gaps,combined,vocabulary)
 if not candidates:return {},None
 key=publishing.sha({'policy':'brief-choice-v1','pages':sorted(p['sha256'] for p in pages.values()),'address':values['address'],'candidates':candidates})
 old=(previous or {}).get('remote') or {}
 # One paid call per unchanged set of pages: a later pass reuses the answer and only reruns the checks.
 if old.get('key')==key and old.get('raw') is not None:raw,note,cost=old['raw'],old.get('note'),old.get('cost')
 else:
  raw,metric,note=segmind.suggest({'title':row['name'],'url':row['source_url'],'text':combined},values['address'],candidates,config,role,database,'brief-'+row['id'][:40])
  if metric is None:return {},{'key':key,'raw':None,'note':note,'accepted':{},'rejected':[],'cost':None}
  cost=metric.get('cost')
 brief,accepted,rejected=settle(issue,raw,values,pages,vocabulary)
 return brief,{'key':key,'raw':raw,'note':note,'accepted':accepted,'rejected':rejected,'cost':cost,'candidates':candidates}

def brief_note(database,entity_id):
 """A sentence for the publication task when the metered model took part in the editorial brief."""
 initialize(database)
 with database() as db:row=db.execute('SELECT result_json FROM commissioning_checks WHERE entity_id=?',(entity_id,)).fetchone()
 remote=(json.loads(row[0]).get('remote') or {}) if row else {}
 return 'Editorial brief choices made by the metered remote model, each tied to a verbatim page quote and rechecked here: '+', '.join(sorted(remote['accepted']))+'.' if remote.get('accepted') and json.loads(row[0]).get('brief') else None

def infer(issue,row,database,web,config=None,role=None):
 """Query hints become editorial fields only with current official-page evidence."""
 if catalog.field(issue,'Discovery campaign')!='classscout-nyc-v1':return {}
 initialize(database)
 with database() as db:
  previous=db.execute('SELECT checked_at,result_json FROM commissioning_checks WHERE entity_id=?',(row['id'],)).fetchone()
  facts=[dict(r) for r in db.execute('SELECT f.field,f.value,f.quote,s.url FROM facts f JOIN sources s ON s.id=f.source_id WHERE entity_id=?',(row['id'],))]
 input_hash=publishing.sha({'policy':'verified-existing-branch-v5','facts':facts,'updated_at':row.get('updated_at'),'hints':issue.get('description')})
 if previous and time.time()-previous['checked_at']<3600 and json.loads(previous['result_json']).get('input_hash')==input_hash:
  return json.loads(previous['result_json']).get('brief',{})
 page=web.page(row['source_url']);source_pages={row['source_url']:page}
 for f in facts:
  if f['url'] not in source_pages and len(source_pages)<4 and urllib.parse.urlsplit(f['url']).hostname.removeprefix('www.')==urllib.parse.urlsplit(row['source_url']).hostname.removeprefix('www.'):source_pages[f['url']]=web.page(f['url'])
 catalog.initialize(database)
 with database() as db:known=[json.loads(r[0])['provider'] for r in db.execute('SELECT result_json FROM catalog_checks') if 'provider' in json.loads(r[0])]
 brief,gaps=evaluate(issue,row,facts,source_pages,known,locations);remote=None
 if gaps and config and role:
  # Optional paid help, only to choose between values the pages already name; every choice is rechecked here.
  brief,remote=refine(issue,row,facts,source_pages,gaps,locations,database,config,role,json.loads(previous['result_json']) if previous else None)
 reason=('%s %s.'%(gaps[0][0].capitalize(),gaps[0][1])) if gaps and not brief else None
 result={'input_hash':input_hash,'brief':brief,'reason':reason,'gaps':[{'field':f,'detail':d} for f,d in gaps],'source_url':page['url'],'source_sha256':page['sha256']}
 if remote:result['remote']=remote
 with database() as db:db.execute('INSERT INTO commissioning_checks VALUES(?,?,?) ON CONFLICT(entity_id) DO UPDATE SET checked_at=excluded.checked_at,result_json=excluded.result_json',(row['id'],time.time(),json.dumps(result)))
 return brief
