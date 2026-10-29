import copy,json,time,unittest
from unittest.mock import Mock,patch
import autonomy,worker,company_ops,catalog
import test_operations
class AutonomyTests(unittest.TestCase):
 def setUp(self):
  self.h=test_operations.OperationalTests();self.h.setUp();autonomy.initialize(worker.database)
  self.config={'company_id':'company','reliability_enabled':True,'projects':{'cs':'ClassScout','pa':'Padel Africa','ops':'Factory Operations'},'agents':{'r':{'role':'research'},'q':{'role':'quality'},'s':{'role':'support'},'p':{'role':'publication'},'search':{'role':'search'}}}
  self.source={'id':'source','identifier':'NAR-S','title':'Evidence check','companyId':'company','projectId':'cs','description':'Factory workflow: source_research\nhttps://example.org','status':'blocked','reviewPolicy':'anyone','updatedAt':'2026-10-28T00:00:00Z'}
  self.issues={'source':copy.deepcopy(self.source)};self.creates=[];self.children={};self.fail_reply=False;self.fail_close=False
  self.board=Mock();self.board.call.side_effect=self.call
  self.run_record('source','blocked','No source-supported fields passed validation')
 def tearDown(self):self.h.tearDown()
 def run_record(self,id,status,error):
  with worker.database() as db:db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',(id+'-run',id,'r','research',status,None,error,'2026-10-28T00:00:00Z','2026-10-28T00:00:01Z'))
 def call(self,path,body=None,method=None):
  if path=='/companies/company/issues' and body is None:return list(self.issues.values())
  if path=='/companies/company/issues':
   key=body['idempotencyKey']
   if key not in self.children:
    child={**body,'id':'child-'+str(len(self.children)),'identifier':'NAR-C'+str(len(self.children)),'companyId':'company'};self.children[key]=child;self.issues[child['id']]=child;self.creates.append(copy.deepcopy(body))
   if self.fail_reply:self.fail_reply=False;raise TimeoutError('Lost task creation reply')
   return copy.deepcopy(self.children[key])
  if path.startswith('/heartbeat-runs/'):return {'companyId':'company','status':'cancelled'}
  if path.endswith('/comments'):return {'id':'comment'}
  if path.startswith('/issues/'):
   id=path.split('/')[2]
   if method=='PATCH':
    if self.fail_close:self.fail_close=False;raise TimeoutError('Close failed')
    self.issues[id].update(body)
   return copy.deepcopy(self.issues[id])
  raise ValueError(path)
 def plan(self):return autonomy.plan(list(self.issues.values()),self.board,self.config,worker.database)
 def test_repeated_ticks_create_one_successor_and_handoff_history(self):
  for _ in range(3):self.plan();autonomy.deliver(self.board,self.config,worker.database)
  self.assertEqual(len(self.creates),1);self.assertEqual(self.issues['source']['status'],'blocked');self.assertNotIn('parentId',self.creates[0])
 def test_same_contract_does_not_retry_again_in_a_descendant(self):
  self.plan();autonomy.deliver(self.board,self.config,worker.database);child=self.issues['child-0'];child['status']='blocked';self.run_record(child['id'],'blocked','No source-supported fields passed validation')
  with worker.database() as db:db.execute('UPDATE autonomous_recovery SET created_at=0')
  self.assertEqual(self.plan()['planned'],[])
 def test_any_write_packet_prevents_automatic_successor(self):
  with worker.database() as db:db.execute('CREATE TABLE engine_packets(issue_id TEXT,status TEXT)');db.execute("INSERT INTO engine_packets VALUES('source','accepted')")
  self.assertEqual(self.plan()['planned'],[]);self.assertEqual(len(self.creates),0)
 def test_active_factory_execution_cannot_be_recovered(self):
  with worker.database() as db:db.execute("UPDATE runs SET status='running'")
  self.assertEqual(self.plan()['planned'],[])
 def test_live_native_execution_cannot_be_recovered(self):
  self.issues['source']['executionRunId']='native'
  original=self.board.call.side_effect
  self.board.call.side_effect=lambda p,*a: {'companyId':'company','status':'running'} if p.startswith('/heartbeat-runs/') else original(p,*a)
  self.assertEqual(self.plan()['planned'],[])
 def test_changed_brief_cancels_planned_recovery_before_creation(self):
  self.plan();self.issues['source']['description']+='\nChanged input';autonomy.deliver(self.board,self.config,worker.database);self.assertEqual(len(self.creates),0)
 def test_lost_task_creation_reply_reuses_exact_native_idempotency_key(self):
  self.plan();self.fail_reply=True;autonomy.deliver(self.board,self.config,worker.database)
  with worker.database() as db:db.execute('UPDATE autonomous_recovery SET next_at=0')
  autonomy.deliver(self.board,self.config,worker.database);self.assertEqual(len(self.creates),1);self.assertEqual(self.issues['source']['status'],'blocked')
 def test_handoff_keeps_native_blocked_history_unchanged(self):
  self.plan();self.fail_close=True;autonomy.deliver(self.board,self.config,worker.database)
  with worker.database() as db:db.execute('UPDATE autonomous_recovery SET next_at=0')
  autonomy.deliver(self.board,self.config,worker.database);self.assertEqual(len(self.creates),1);self.assertEqual(self.issues['source']['status'],'blocked')
  self.assertFalse(any(c.args[0].endswith('/comments') or len(c.args)>2 and c.args[2]=='PATCH' for c in self.board.call.call_args_list))
 def test_publication_workflows_are_not_eligible_for_stopped_run_recovery(self):
  for kind in ['prepare_listing','refresh_provider','program_update','padel_intake','sales_pipeline']:
   self.issues['source']['description']='Factory workflow: '+kind;self.assertEqual(self.plan()['planned'],[])
 def test_evidence_hold_with_stopped_blocker_does_not_become_transport_failure(self):
  self.issues['source']['description']='Factory workflow: source_quality';self.issues['source']['executionBlocker']={'runId':'native','runStatus':'failed'}
  self.assertEqual(self.plan()['planned'],[])
 def test_stopped_quality_run_can_get_safe_successor(self):
  self.issues['source']['description']='Factory workflow: source_quality';self.issues['source']['executionBlocker']={'runId':'native','runStatus':'failed','cause':'legacy_execution_requires_reconciliation'}
  with worker.database() as db:db.execute("UPDATE runs SET status='failed',error='Process exited before completing'")
  self.assertEqual(len(self.plan()['planned']),1)
 def test_three_successors_is_a_lineage_cap(self):
  for n in range(3):
   with worker.database() as db:db.execute('INSERT INTO autonomous_recovery VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(n),'source','old'+str(n),'c','i','{}','handed_off',None,0,0,0,None))
  self.assertEqual(self.plan()['planned'],[])
 def test_owner_changed_status_is_not_overwritten(self):
  self.plan();self.issues['source']['status']='done';autonomy.deliver(self.board,self.config,worker.database);self.assertEqual(self.issues['source']['status'],'done');self.assertEqual(self.creates,[])
 def test_cross_company_and_test_items_are_ignored(self):
  self.issues['source']['companyId']='other';self.assertEqual(self.plan()['planned'],[])
  self.issues['source']['companyId']='company';self.issues['source']['title']='[Factory test] Fixture';self.assertEqual(self.plan()['planned'],[])
 def test_poison_dispatch_does_not_starve_next_valid_request(self):
  src=self.issues['source'];bad={'projectId':'cs','status':'todo','assigneeAgentId':'missing'};good={'projectId':'cs','status':'todo','assigneeAgentId':'q','title':'Review','description':'Factory workflow: source_quality'}
  company_ops.queue_dispatch(worker.database,'bad',src,bad);company_ops.queue_dispatch(worker.database,'good',src,good)
  self.assertEqual(len(company_ops.dispatch_pending(self.board,self.config,worker.database,limit=10)),1)
  with worker.database() as db:r=db.execute("SELECT attempts,next_at FROM company_dispatch WHERE request_key='bad'").fetchone()
  self.assertEqual(r['attempts'],1);self.assertGreater(r['next_at'],time.time())
 def test_due_handoff_batch_is_bounded_and_has_stable_keys(self):
  for n in range(12):company_ops.queue_dispatch(worker.database,str(n),self.issues['source'],{'projectId':'cs','status':'todo','assigneeAgentId':'q','title':'Review','description':'Factory workflow: source_quality'})
  self.assertEqual(len(company_ops.dispatch_pending(self.board,self.config,worker.database,limit=100)),10);self.assertEqual(len({b['idempotencyKey'] for b in self.creates}),10)
 def test_failed_first_source_fetch_obeys_next_check_time(self):
  with worker.database() as db:db.execute('INSERT INTO company_blockers VALUES(?,?,?,?,?,?,?,?)',('source','branch_identity','check','sig',0,time.time()+86400,0,None))
  web=Mock();self.assertEqual(company_ops.recheck_blocked([self.source],self.board,self.config,web,worker.database),[]);web.page.assert_not_called()
 def test_native_coordinator_finishes_without_model_or_search(self):
  issue={'id':'tick','projectId':'ops','title':'Coordination','description':'Factory workflow: autonomous_coordination'}
  result=autonomy.run(issue,self.board,self.config,Mock(),worker.database,{})
  self.assertEqual(result['final_status'],'done');self.assertEqual(len(self.creates),1)

 def test_specific_branch_with_missing_facts_does_not_repeat_parser_expansion(self):
  self.issues['source'].update(projectId='pa',description='Factory workflow: engine_candidate\nBranch depth: 1')
  with worker.database() as db:db.execute("UPDATE runs SET error='Official source does not uniquely establish one venue'")
  self.assertEqual(self.plan()['planned'],[])
 def test_three_delivery_failures_stop_with_review_state(self):
  self.plan();original=self.board.call.side_effect
  self.board.call.side_effect=lambda p,*args: (_ for _ in ()).throw(TimeoutError()) if p=='/companies/company/issues' else original(p,*args)
  for _ in range(3):
   with worker.database() as db:db.execute('UPDATE autonomous_recovery SET next_at=0')
   autonomy.deliver(self.board,self.config,worker.database)
  with worker.database() as db:state=db.execute('SELECT status,attempts FROM autonomous_recovery').fetchone()
  self.assertEqual((state['status'],state['attempts']),('needs_attention',3))
 def test_recheck_rotation_uses_oldest_source_check(self):
  sources=[]
  for index in range(3):
   issue={**self.source,'id':'held'+str(index),'description':'Factory workflow: source_quality\nhttps://example.org'};sources.append(issue)
   with worker.database() as db:
    db.execute('INSERT INTO company_blockers VALUES(?,?,?,?,?,?,?,?)',(issue['id'],'branch_identity','check','sig',0,0,0,None))
    db.execute('INSERT INTO blocker_sources VALUES(?,?,?)',(issue['id'],'old',100-index))
  web=Mock();web.page.side_effect=TimeoutError()
  result=company_ops.recheck_blocked(sources,self.board,self.config,web,worker.database)
  self.assertEqual([x['task'] for x in result],['NAR-S','NAR-S'])
  with worker.database() as db:updated=[r['issue_id'] for r in db.execute('SELECT issue_id FROM company_blockers WHERE next_at>0')]
  self.assertEqual(set(updated),{'held2','held1'})
