"""Operating summaries from authoritative task states and bounded local ledgers."""
import collections,datetime,json,time
import catalog
from search_budget import Budget

def run(issue,board,config,web,database,execution):
 catalog.initialize(database);company=config['company_id'];rows=board.call('/companies/'+company+'/issues');rows=rows if isinstance(rows,list) else rows.get('issues',[])
 scope=set(config['projects']);rows=[r for r in rows if r.get('companyId')==company and r.get('projectId') in scope];counts=dict(collections.Counter(r['status'] for r in rows));blocked=[{'identifier':r['identifier'],'title':r['title']} for r in rows if r['status']=='blocked'];waiting=[r['identifier'] for r in rows if r['status']=='in_review' and r.get('assigneeUserId')==config.get('reviewer_user_id','local-board')]
 since=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=1)).isoformat();metrics={};pending=[]
 with database() as db:
  tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")};runs=[dict(r) for r in db.execute('SELECT role,status,result FROM runs WHERE started_at>? AND id<>?',(since,execution.get('run_id','')))];metrics['runs_last_24h']=dict(collections.Counter(r['status'] for r in runs));metrics['runs_by_role']=dict(collections.Counter(r['role'] for r in runs));metrics['drafts']=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM entities')))
  metrics['catalog_checks']=dict(collections.Counter(json.loads(r[0])['status'] for r in db.execute('SELECT result_json FROM catalog_checks'))) if 'catalog_checks' in tables else {}
  metrics['open_audit_findings']=db.execute("SELECT count(*) FROM audit_findings WHERE status='observed'").fetchone()[0] if 'audit_findings' in tables else 0
  metrics['contact_packets']=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM refresh_packets'))) if 'refresh_packets' in tables else {}
  metrics['automatic_quality_decisions']=dict(collections.Counter(r[0] for r in db.execute('SELECT decision FROM automatic_decisions'))) if 'automatic_decisions' in tables else {}
  metrics['automatic_writes_attempted']=db.execute('SELECT count(*) FROM automatic_decisions WHERE submitted_at IS NOT NULL').fetchone()[0] if 'automatic_decisions' in tables else 0
  metrics['publication_packets']=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM publication_packets'))) if 'publication_packets' in tables else {}
  packets=[dict(r) for r in db.execute("SELECT issue_id,status,interaction_id,created_at FROM publication_packets WHERE status='awaiting_approval' ORDER BY created_at LIMIT 10")] if 'publication_packets' in tables else []
 for p in packets:
  if not p['interaction_id']:continue
  try:
   cards=board.call('/issues/'+p['issue_id']+'/interactions');card=next((c for c in cards if c['id']==p['interaction_id']),{});task=next((r for r in rows if r['id']==p['issue_id']),None)
   if card.get('status')=='pending':pending.append({'task':task['identifier'] if task else p['issue_id'],'created_at':p['created_at'],'approval_expires_after_hours':48})
  except Exception:pending.append({'task':p['issue_id'],'status':'review_status_unavailable'})
 budget=Budget(database).status();report={'task_counts':counts,'blocked':blocked,'owner_review_count':len(waiting),'owner_review_tasks':waiting[:15],'pending_publication_reviews':pending,'metrics':metrics,'search_budget':budget,'note':'Idle is expected between useful tasks; source drafts, prepared packets and confirmed catalog writes are separate outcomes.'};catalog.save_report(database,issue,'operations_digest',report)
 from worker import safe
 lines=['## Factory operating summary','','Task states: '+', '.join(k.replace('_',' ')+': '+str(v) for k,v in sorted(counts.items()))+'.','Blocked tasks: '+str(len(blocked))+'. Owner review items: '+str(len(waiting))+'.','']
 for r in blocked[:10]:lines.append('- Needs attention: '+r['identifier']+' — '+safe(r['title']))
 for p in pending:lines.append('- Publication decision: '+p['task']+'; '+('approval expires after 48 hours from '+p['created_at'] if p.get('created_at') else 'check the current approval card')+'.')
 lines+=['','### Work and quality','Runs in the last 24 hours: '+json.dumps(metrics['runs_last_24h'])+'.','Source draft states: '+json.dumps(metrics['drafts'])+'.','Catalog verification: '+json.dumps(metrics['catalog_checks'])+'.','Open website findings: '+str(metrics['open_audit_findings'])+'.','Contact correction states: '+json.dumps(metrics['contact_packets'])+'.','Publication packet states: '+json.dumps(metrics['publication_packets'])+'.','Automatic quality decisions: '+json.dumps(metrics['automatic_quality_decisions'])+'. Writes attempted: '+str(metrics['automatic_writes_attempted'])+'.','','### Shared search allowance','Used: '+str(budget['used_this_window'])+'/'+str(budget['automatic_limit'])+' automatic requests this allowance period; '+str(budget['used_today'])+'/'+str(budget['daily_limit'])+' today. Estimated account balance: '+str(budget['estimated_account_remaining'])+'; protected reserve: '+str(budget['reserve'])+'.','','Source-check success does not establish publication completeness. A confirmed private save and public receipt establish a completed catalog write. This report ran without model inference or a Brave request.']
 return {'stage':'operations_digest','entities':[],'markdown':'\n'.join(lines),'final_status':'done','report':report}
