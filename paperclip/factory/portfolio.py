"""Coordinators for saved evidence, structured updates and declared engine clients."""
import json,time
import catalog,company_ops,pipeline,publishing,engine_ops

def queue_engine_candidate(issue,page,board,config):
 project=issue['projectId'];slug=next(k for k,v in engine_ops.SPECS.items() if config['projects'].get(project)==v['project']);agent=company_ops.role(config,'support')
 return board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'engine-candidate-'+slug+'-'+publishing.sha(page['url']),'title':'Verify official venue source: '+page['title'][:110],'projectId':project,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone','description':'Factory workflow: engine_candidate\nOfficial source URL: '+page['url']+'\nEngine client: '+slug+'\n\nResolve this venue from its own page. Search locality is not evidence; preserve literal source values.'})

def program_queue(issue,board,config,web,database,execution,client=None):
 """Prefer known structured programs and published records, while rotating all catalog candidates."""
 import program_updates,quality_gate
 if not config.get('program_updates_enabled') or not quality_gate.enabled(config,issue):return {'stage':'program_queue','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Structured program updates are switched off.'}
 program_updates.initialize(database);catalog.initialize(database);client=client or publishing.ClassScout()
 with database() as db:
  db.execute('CREATE TABLE IF NOT EXISTS program_queue_checks(provider_id TEXT PRIMARY KEY,queued_at REAL,target_issue TEXT)')
  ids=[r[0] for r in db.execute("SELECT provider_id FROM catalog_checks ORDER BY coalesce(json_array_length(json_extract(result_json,'$.provider.recurringPrograms')),0) DESC,checked_at")]
  if db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_packets'").fetchone():ids += [r[0] for r in db.execute("SELECT json_extract(body_json,'$.draftPayload.id') FROM publication_packets WHERE status='published'")]
  prior={r['provider_id']:dict(r) for r in db.execute('SELECT * FROM program_queue_checks')}
 candidates=sorted(dict.fromkeys(ids),key=lambda id:prior.get(id,{}).get('queued_at',0))
 created=[];checks=[]
 for id in candidates:
  if len(checks)>=12 or len(created)>=3:break
  previous=prior.get(id,{})
  if previous.get('queued_at',0)>time.time()-86400:continue
  if previous.get('target_issue'):
   target=board.call('/issues/'+previous['target_issue'])
   if target.get('status') not in {'done','cancelled'}:continue
  try:
   row=client.existing_provider(id)
   reason='eligible'
   if not row:reason='provider_missing'
   elif row.get('ownerSub') or row.get('ownerManaged') or row.get('ownerManagedAt') or row.get('claimStatus') in {'claimed','claim_pending'}:reason='owner_managed'
   elif not row.get('recurringPrograms'):reason='no_existing_structured_programs'
   elif not row.get('website'):reason='no_official_website'
   if reason!='eligible':
    with database() as db:db.execute('INSERT INTO program_queue_checks VALUES(?,?,NULL) ON CONFLICT(provider_id) DO UPDATE SET queued_at=excluded.queued_at,target_issue=NULL',(id,time.time()))
    checks.append({'provider_id':id,'status':reason});continue
   key='program-check-'+id+'-'+str(int(time.time()//86400))
   urls=program_updates.source_urls(row)
   child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':key,'title':'Recheck structured programs: '+row['name'][:110],'projectId':issue['projectId'],'status':'todo','assigneeAgentId':company_ops.role(config,'publication'),'reviewPolicy':'anyone','description':'Factory workflow: program_update\nCatalog provider: '+id+'\n'+'\n'.join('Program source: '+url for url in urls)+'\n\nRefresh only unambiguous same-branch, same-program structured facts. Preserve all unmatched programs and owner changes.'})
   with database() as db:db.execute('INSERT INTO program_queue_checks VALUES(?,?,?) ON CONFLICT(provider_id) DO UPDATE SET queued_at=excluded.queued_at,target_issue=excluded.target_issue',(id,time.time(),child['id']))
   created.append(child['identifier']);checks.append({'provider_id':id,'status':'queued','task':child['identifier']})
  except Exception as error:checks.append({'provider_id':id,'status':'check_failed','error_category':type(error).__name__})
 report={'checked':checks,'created':created,'scan_limit':12,'task_limit':3};catalog.save_report(database,issue,'program_queue',report)
 return {'stage':'program_queue','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Structured program checks queued: '+(', '.join(created) or 'none')+'. Checked '+str(len(checks))+' records; skipped records have explicit reasons in the saved report.','report':report}

def recover_legacy(board,config,database):
 """Re-use saved drafts from failed delegation, without another extraction or search."""
 company_ops.initialize(database);queued=[]
 with database() as db:rows=[dict(r) for r in db.execute("SELECT e.id AS entity_id,e.issue_id FROM entities e JOIN runs r ON e.issue_id=r.issue_id WHERE r.status='failed' AND r.error LIKE '%delegation_cycle%' GROUP BY e.id LIMIT 5")]
 for row in rows:
  issue=board.call('/issues/'+row['issue_id'])
  if issue['status'] not in {'blocked','in_review'} or issue.get('companyId')!=config['company_id']:continue
  with database() as db:existing=db.execute("SELECT 1 FROM company_dispatch WHERE source_issue=? AND status IN ('queued','delivered')",(issue['id'],)).fetchone()
  if existing:continue
  pipeline.after_research(issue,{'entities':[row['entity_id']]},board,config,database);queued.append(issue.get('identifier'))
 return queued
