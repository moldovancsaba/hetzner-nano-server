"""Idempotent source-to-quality-to-publication handoffs with explicit editorial scope."""
import json,re,time
import candidates,catalog,publishing,quality_gate

def initialize(database):
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS pipeline_links(link_key TEXT PRIMARY KEY,kind TEXT,source_issue TEXT,target_issue TEXT,target_identifier TEXT,created_at REAL)')
def prefix(issue):return '[Factory test] ' if issue['title'].startswith('[Factory test]') else ''
def metadata(issue):
 lines=[]
 for name in ['Catalog provider','Publication name','Borough','Neighborhood','Format','Activity','Discovery borough','Discovery activity','Discovery campaign','Discovery format']:
  value=catalog.field(issue,name)
  if value:lines.append(name+': '+value)
 return '\n'.join(lines)
def after_research(issue,result,board,config,database):
 if not config.get('operational_workflows_enabled'):return
 initialize(database);agent=next(k for k,v in config['agents'].items() if v['role']=='quality')
 for entity in result.get('entities',[]):
  with database() as db:source=db.execute('SELECT source_url FROM entities WHERE id=?',(entity,)).fetchone();facts=[tuple(r) for r in db.execute('SELECT field,value,quote,source_id FROM facts WHERE entity_id=? ORDER BY field',(entity,))]
  if not source:continue
  key='quality-'+publishing.sha({'entity':entity,'facts':facts,'research_issue':issue['id']})
  body={'idempotencyKey':key,'title':prefix(issue)+'Verify source evidence: '+issue['title'].removeprefix('[Factory test] ')[:125],'projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':'human_only','description':'Factory workflow: source_quality\nDraft reference: '+entity+'\n'+metadata(issue)+'\n\nRe-fetch and verify retained quotes and physical identity. Approved contacts and complete editorial briefs can advance to publication review. Unknown facts stay unknown.'}
  if config.get('reliability_enabled'):
   from company_ops import queue_dispatch
   queue_dispatch(database,key,issue,body)
   continue
  child=board.call('/companies/'+config['company_id']+'/issues',body)
  with database() as db:db.execute('INSERT OR IGNORE INTO pipeline_links VALUES(?,?,?,?,?,?)',(key,'quality',issue['id'],child['id'],child['identifier'],time.time()))

 if result.get('entities') and quality_gate.enabled(config,issue):result.update(final_status='done',automatic_progress=True)

def advance(issue,entity,board,config,database,web=None,role='publication'):
 initialize(database);provider=catalog.field(issue,'Catalog provider');editorial=metadata(issue)

 with database() as db:
  row=db.execute('SELECT * FROM entities WHERE id=?',(entity,)).fetchone()
  if not row or row['brand']!='ClassScout' or row['status']!='ready_for_human_review':return None
  facts=[tuple(r) for r in db.execute('SELECT field,value,quote,source_id FROM facts WHERE entity_id=? ORDER BY field',(entity,))]
 if not provider and not all(catalog.field(issue,k) for k in ['Publication name','Borough','Neighborhood','Format','Activity']):
  if not config.get('growth_mode',{}).get('enabled'):return None
  import growth
  from net import PublicWeb
  try:brief=growth.infer(issue,dict(row),database,web or PublicWeb(),config,role)
  except Exception:brief={}
  if not brief:return None
  issue={**issue,'description':(issue.get('description') or '')+'\n'+'\n'.join(k+': '+v for k,v in brief.items())};editorial=metadata(issue);provider=catalog.field(issue,'Catalog provider')
 kind='refresh_provider' if provider else 'prepare_listing';key='advance-'+publishing.sha({'kind':kind,'entity':entity,'metadata':editorial,'facts':facts,'verified_at':row['updated_at']})
 with database() as db:old=db.execute('SELECT target_issue,target_identifier FROM pipeline_links WHERE link_key=?',(key,)).fetchone()
 if old:return {'id':old[0],'identifier':old[1]}
 if provider:catalog.clean_id(provider)
 import growth
 note=None if provider else growth.brief_note(database,entity)
 description=('Factory workflow: refresh_provider\n' if provider else '')+'Draft reference: '+entity+'\n'+editorial+'\n\n'+row['source_url']+('\n\n'+note if note else '')
 if not provider:
  # Reuse unresolved packets rather than creating competing approvals for the same target. A reused packet older than
  # 48 hours still fails in publishing.run until its brief changes.
  with database() as db:
   table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='publication_packets'").fetchone()
   packets=db.execute("SELECT issue_id,proof_json FROM publication_packets WHERE status IN ('prepared','awaiting_approval','publishing','uncertain','partial')").fetchall() if table else []
  for p in packets:
   proof=json.loads(p['proof_json']);sources=proof.get('sources',[])
   if any(s.get('url')==row['source_url'] for s in sources):
    normalized=proof.get('normalized',{});wanted={'title':catalog.field(issue,'Publication name'),'boroughRaw':catalog.field(issue,'Borough'),'neighborhoodRaw':catalog.field(issue,'Neighborhood'),'categoryHint':catalog.field(issue,'Format')}
    if any(publishing.norm(normalized.get(k))!=publishing.norm(v) for k,v in wanted.items()):raise ValueError('An unresolved publication uses this source with a different editorial brief; review it before creating another packet')
    if publishing.norm(catalog.field(issue,'Activity')) not in [publishing.norm(v) for v in normalized.get('activityTypesRaw',[])]:raise ValueError('An unresolved publication has a different activity brief; review the existing packet first')
    existing=board.call('/issues/'+p['issue_id'])
    if quality_gate.enabled(config,issue) and existing.get('status') in {'in_review','blocked'}:
     publisher=next(k for k,v in config['agents'].items() if v['role']=='publication')
     existing=board.call('/issues/'+p['issue_id'],{'status':'todo','assigneeAgentId':publisher,'assigneeUserId':None},'PATCH')
    with database() as db:db.execute('INSERT OR IGNORE INTO pipeline_links VALUES(?,?,?,?,?,?)',(key,'existing_publication',issue['id'],existing['id'],existing['identifier'],time.time()))
    return {'id':existing['id'],'identifier':existing['identifier']}
 publisher=next(k for k,v in config['agents'].items() if v['role']=='publication')
 child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':key,'title':prefix(issue)+('Review contact refresh: ' if provider else 'Prepare listing: ')+row['name'][:125],'projectId':issue['projectId'],'parentId':issue['id'],'description':description,'status':'todo','assigneeAgentId':publisher,'reviewPolicy':'human_only'})
 with database() as db:db.execute('INSERT OR IGNORE INTO pipeline_links VALUES(?,?,?,?,?,?)',(key,kind,issue['id'],child['id'],child['identifier'],time.time()))
 return child

def after_quality(issue,result,board,config,database,web=None):
 if not config.get('operational_workflows_enabled') or catalog.field(issue,'Factory workflow')!='source_quality':return
 if result.get('review',{}).get('status')!='ready_for_human_review':return
 children=[advance(issue,e,board,config,database,web,'quality') for e in result.get('entities',[])];names=[c['identifier'] for c in children if c]
 if names:
  result['markdown']+='\n\nNext publication/content check: '+', '.join(names)+'. The configured quality policy authorizes eligible writes.'
  if quality_gate.enabled(config,issue):result.update(final_status='done',automatic_progress=True)

def run_queue(issue,board,config,web,database,execution):
 import growth
 initialize(database)
 # The five candidates touched longest ago, stamped now: whatever happens to them below, they go to the back of the line.
 with database() as db:entities=candidates.take(db,'ready_for_human_review',5)
 advanced=[];gaps=[]
 for row in entities[:5]:
  source=board.call('/issues/'+row['issue_id'])
  if '[Factory test]' in source.get('title','') and '[Factory test]' not in issue.get('title',''):continue
  if source['companyId']!=config['company_id'] or source.get('projectId')!=issue['projectId']:continue
  target=advance(source,row['id'],board,config,database,web)
  if target:advanced.append(target['identifier'])
  else:gaps.append({'draft':row['id'],'name':row['name'],'missing':growth.gap_reason(database,row['id']) or 'Source-backed publication name, borough, neighborhood, format and activity; or an exact existing catalog provider ID.'})
 catalog.save_report(database,issue,'publication_queue',{'advanced':advanced,'editorial_gaps':gaps})
 from worker import safe
 lines=['## Publication preparation queue','','Ready source drafts checked: '+str(min(5,len(entities)))+'.','Next review tasks: '+(', '.join(dict.fromkeys(advanced)) or 'none')+'.','']
 for gap in gaps:lines.append('- '+safe(gap['name'])+': '+gap['missing']+' Draft: `'+gap['draft']+'`.')
 lines+=['','Complete briefs advance to preparation; existing pending packets are reused. Timetables, child ages, per-class fees and media still pass the canonical ClassScout checks. No approval or publication was performed by this queue scan.']
 return {'stage':'publication_queue_review','entities':[],'markdown':'\n'.join(lines),'final_status':'done'}
