"""Coordinators for saved evidence, structured updates and declared engine clients."""
import json,time
import catalog,company_ops,pipeline,publishing,engine_ops

def queue_engine_candidate(issue,page,board,config):
 project=issue['projectId'];slug=next(k for k,v in engine_ops.SPECS.items() if config['projects'].get(project)==v['project']);agent=company_ops.role(config,'support')
 return board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'engine-candidate-'+slug+'-'+publishing.sha(page['url']),'title':'Verify official venue source: '+page['title'][:110],'projectId':project,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone','description':'Factory workflow: engine_candidate\nOfficial source URL: '+page['url']+'\nEngine client: '+slug+'\n\nResolve this venue from its own page. Search locality is not evidence; preserve literal source values.'})

def program_queue(issue,board,config,web,database,execution):
 import program_updates
 program_updates.initialize(database);catalog.initialize(database)
 with database() as db:
  db.execute('CREATE TABLE IF NOT EXISTS program_queue_checks(provider_id TEXT PRIMARY KEY,queued_at REAL,target_issue TEXT)')
  candidates=[dict(r) for r in db.execute('SELECT c.provider_id,c.result_json FROM catalog_checks c LEFT JOIN program_queue_checks q ON c.provider_id=q.provider_id WHERE q.queued_at IS NULL OR q.queued_at<? ORDER BY coalesce(q.queued_at,0),c.checked_at LIMIT 3',(time.time()-86400,))]
 created=[]
 for candidate in candidates:
  row=publishing.ClassScout().existing_provider(candidate['provider_id'])
  with database() as db:db.execute('INSERT INTO program_queue_checks VALUES(?,?,NULL) ON CONFLICT(provider_id) DO UPDATE SET queued_at=excluded.queued_at',(candidate['provider_id'],time.time()))
  if not row or not row.get('recurringPrograms') or row.get('ownerSub') or row.get('ownerManaged'):continue
  key='program-check-'+row['id']+'-'+str(int(time.time()//86400))
  child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':key,'title':'Recheck structured programs: '+row['name'][:110],'projectId':issue['projectId'],'status':'todo','assigneeAgentId':company_ops.role(config,'publication'),'reviewPolicy':'anyone','description':'Factory workflow: program_update\nCatalog provider: '+row['id']+'\nProgram source: '+row['website']+'\n\nRefresh only unambiguous same-branch, same-program structured facts. Preserve all unmatched programs and owner changes.'})
  with database() as db:db.execute('INSERT INTO program_queue_checks VALUES(?,?,?) ON CONFLICT(provider_id) DO UPDATE SET queued_at=excluded.queued_at,target_issue=excluded.target_issue',(row['id'],time.time(),child['id']))
  created.append(child['identifier'])
 return {'stage':'program_queue','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Structured program checks queued: '+(', '.join(created) or 'none; no eligible program record in this bounded pass')+'.'}

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
