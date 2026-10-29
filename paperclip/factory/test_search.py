import contextlib,datetime,io,json,pathlib,tempfile,threading,unittest,urllib.error
from unittest.mock import Mock,patch
import worker,search_budget as sb,search_workflow as sw,brave

class Clock:
 def __init__(self):self.now=1800000000.
 def __call__(self):return self.now
class SearchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state_patch=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state_patch.start();worker.initialize();self.clock=Clock();self.budget=sb.Budget(worker.database,self.clock)
 def tearDown(self):self.state_patch.stop();self.tmp.cleanup()
 def headers(self,remaining='1999',reset='2678400'):return {'X-RateLimit-Policy':'1;w=1, 2000;w=2678400','X-RateLimit-Remaining':'0, '+remaining,'X-RateLimit-Reset':'1, '+reset}
 def issue(self,id='issue',purpose='publishing',query='site:example.org kids music classes schedule'):
  return {'id':id,'projectId':'project','title':'Find official sources','description':'Search purpose: '+purpose+'\nSearch query: '+query+'\nSource host: example.org'}
 def config(self):return {'search_enabled':True,'company_id':'company','projects':{'project':'ClassScout'},'agents':{'search':{'role':'search'},'research':{'role':'research'},'quality':{'role':'quality'},'publisher':{'role':'publication'}}}
 def test_model_maintenance_wait_is_bounded_and_excludes_publication(self):
  message='Service returned HTTP 503: {"error": {"code": "model_storage_maintenance"}}'
  issue={'id':'maintenance','assigneeAgentId':'research'}
  policy=worker.model_wait_policy(issue,'research',message);self.assertIn('Model wait 1/12',policy['monitor']['notes'])
  self.assertIsNone(worker.model_wait_policy(issue,'publication',message));self.assertIsNone(worker.model_wait_policy(issue,'research','Missing supported facts'))
  for i in range(11):self.assertIsNotNone(worker.model_wait_policy(issue,'research',message))
  self.assertIsNone(worker.model_wait_policy(issue,'research',message))
 def test_single_burst_cooldown(self):
  self.budget.reserve('job',1)
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('job2',1)
  self.clock.now+=1800;self.budget.reserve('job2',1);self.assertEqual(self.budget.status()['used_this_window'],2)
 def test_three_query_burst_debits_future_slots(self):
  self.budget.reserve('job',3);self.assertEqual(self.budget.status()['next_search_at'],self.clock.now+5404);self.assertEqual(self.budget.status()['estimated_account_remaining'],1997)
 def test_spacing_is_durable(self):
  a,b=self.budget.reserve('job',2);self.budget.dispatch(a)
  with self.assertRaises(sb.BudgetWait):sb.Budget(worker.database,self.clock).dispatch(b)
  self.clock.now+=2;self.budget.dispatch(b)
 def test_restart_cannot_reset_allowance(self):
  self.budget.reserve('job',2);other=sb.Budget(worker.database,self.clock)
  with self.assertRaises(sb.BudgetWait):other.reserve('job2',1)
  self.assertEqual(other.status()['used_this_window'],2)
 def test_two_concurrent_reservations_cannot_both_spend(self):
  outcomes=[];barrier=threading.Barrier(2)
  def reserve():
   barrier.wait()
   try:self.budget.reserve('job',1);outcomes.append('admitted')
   except sb.BudgetWait:outcomes.append('waiting')
  a=threading.Thread(target=reserve);b=threading.Thread(target=reserve);a.start();b.start();a.join();b.join();self.assertCountEqual(outcomes,['admitted','waiting'])
 def test_daily_ceiling(self):
  with worker.database() as db:db.executemany('INSERT INTO search_attempts(id,job_id,reserved_at,day_key,status,http_status,quota_headers) VALUES(?,?,?,?,?,?,?)',[(str(i),'old',self.clock.now-10,sb.day_key(self.clock.now),'succeeded',200,None) for i in range(48)])
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('job',1)
 def test_monthly_ceiling(self):
  with worker.database() as db:
   db.execute('UPDATE search_account SET window_start=?',(self.clock.now-20*86400,));db.executemany('INSERT INTO search_attempts(id,job_id,reserved_at,day_key,status,http_status,quota_headers) VALUES(?,?,?,?,?,?,?)',[(str(i),'old',self.clock.now-86400,'older-day','succeeded',200,None) for i in range(1800)])
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('job',1)
 def test_account_reserve_cannot_be_spent(self):
  with worker.database() as db:db.execute('UPDATE search_account SET remaining=201')
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('job',2)
  self.budget.reserve('job',1)
 def test_external_use_reduces_our_allowance(self):
  token=self.budget.reserve('job',1)[0];self.budget.finish(token,'succeeded',200,self.headers('190'));self.clock.now+=1800
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('job2',1)
 def test_lagging_provider_header_cannot_refund_local_usage(self):
  token=self.budget.reserve('job',1)[0];self.budget.finish(token,'succeeded',200,self.headers('2000'));self.assertEqual(self.budget.status()['estimated_account_remaining'],1999)
 def test_timeout_remains_counted(self):
  token=self.budget.reserve('job',1)[0];self.budget.dispatch(token);self.budget.finish(token,'uncertain');self.assertEqual(self.budget.status()['used_this_window'],1)
 def test_window_rollover_uses_observed_reset(self):
  report={'checked_at':datetime.datetime.fromtimestamp(self.clock.now,datetime.timezone.utc).isoformat(),'http_status':200,'quota_headers':self.headers('2000','3600')};self.budget.seed_probe(report)
  self.assertEqual(self.budget.status()['used_this_window'],1);self.clock.now+=3601;self.budget.reserve('new-period',1);self.assertEqual(self.budget.status()['used_this_window'],1)
 def test_probe_seed_is_idempotent(self):
  report={'checked_at':datetime.datetime.fromtimestamp(self.clock.now,datetime.timezone.utc).isoformat(),'http_status':200,'quota_headers':self.headers()};self.budget.seed_probe(report);self.budget.seed_probe(report);self.assertEqual(self.budget.status()['used_this_window'],1)
 def test_no_dispatch_can_reuse_a_token(self):
  token=self.budget.reserve('job',1)[0];self.budget.dispatch(token);self.clock.now+=5
  with self.assertRaises(ValueError):self.budget.dispatch(token)
 def test_crossed_midnight_rechecks_daily_capacity(self):
  token=self.budget.reserve('job',1)[0];self.clock.now+=86400
  with worker.database() as db:db.executemany('INSERT INTO search_attempts(id,job_id,reserved_at,day_key,status,http_status,quota_headers) VALUES(?,?,?,?,?,?,?)',[(str(i),'old',self.clock.now,sb.day_key(self.clock.now),'succeeded',200,None) for i in range(48)])
  with self.assertRaises(sb.BudgetWait):self.budget.dispatch(token)
 def test_burst_cooldown_starts_after_last_response(self):
  a,b=self.budget.reserve('job',2);self.clock.now+=25;self.budget.finish(a,'succeeded',200,self.headers());self.clock.now+=25;self.budget.finish(b,'succeeded',200,self.headers());self.assertEqual(self.budget.status()['next_search_at'],self.clock.now+3600)
 def test_reservation_crossing_reset_is_counted_in_new_window(self):
  token=self.budget.reserve('job',1)[0]
  with worker.database() as db:db.execute('UPDATE search_account SET reset_at=?,period=3600',(self.clock.now+1,))
  self.clock.now+=2;self.budget.dispatch(token);self.assertEqual(self.budget.status()['used_this_window'],1);self.assertEqual(self.budget.status()['estimated_account_remaining'],1999)
 def test_source_search_does_not_trigger_on_uncertain_publication(self):
  board=Mock();self.assertIsNone(sw.request_gap_search(self.issue(),board,self.config(),'Publication response was not confirmed'));board.call.assert_not_called()
 def test_paused_discovery_does_not_starve_support(self):
  sw.enqueue(self.issue('discover',purpose='discovery',query='site:example.org kids classes'),worker.database);sw.enqueue(self.issue('support',purpose='support',query='site:example.org published tuition'),worker.database);board=Mock();board.call.return_value={'id':'support','assigneeAgentId':'search','status':'in_progress'}
  with patch('search_workflow.research_backlog',return_value=10):chosen=sw.queued_issue(board,self.config(),'search',worker.database)
  self.assertEqual(chosen['id'],'support');self.assertEqual(board.call.call_args.args[0],'/issues/support')
 def test_approved_parent_is_never_mutated(self):
  sw.initialize(worker.database);i=self.issue();outcome={'source_pages':[{'url':'https://example.org/new','title':'Direct','research_id':'child'}],'research_tasks':[]};job={'issue_id':'issue','parent_publication':'parent','parent_input_hash':'old'};board=Mock();board.call.return_value={'id':'parent','title':'Ready listing','description':'','status':'in_review','companyId':'company','projectId':'project'}
  sw.deliver(i,board,self.config(),job,outcome,worker.database,{'run_id':'run','agent_id':'search'});self.assertFalse(any(call.args[-1]=='PATCH' for call in board.call.call_args_list if len(call.args)>2));self.assertNotIn('publication_resumed',outcome)
 def test_private_query_terms_rejected(self):
  for q in ['customer alice@example.org','phone +1 212 555 1234','Brave BSAp-secret','password secret']:
   with self.assertRaises(ValueError):sw.parse(self.issue(query=q))
 def test_duplicate_query_never_gets_another_job_allowance(self):
  sw.enqueue(self.issue('one'),worker.database);second=sw.enqueue(self.issue('two'),worker.database);self.assertEqual(second['status'],'deduplicated');self.assertEqual(self.budget.status()['used_this_window'],0)
 def test_partial_duplicate_can_resume_unchanged_brief(self):
  sw.enqueue(self.issue('one'),worker.database);i=self.issue('two');i['description']+='\nSearch query: site:example.org children tuition';first=sw.enqueue(i,worker.database);second=sw.enqueue(i,worker.database);self.assertEqual(len(json.loads(first['queries_json'])),1);self.assertEqual(second['status'],'queued')
 def test_quota_wait_never_calls_brave(self):
  self.budget.reserve('prior',1);board=Mock();client=Mock();web=Mock()
  with patch('search_workflow.research_backlog',return_value=0):result=sw.run(self.issue(),board,self.config(),web,worker.database,{'run_id':'run','agent_id':'search'},client,self.budget)
  self.assertEqual(result['stage'],'search_waiting');client.search.assert_not_called()
 def test_discovery_backpressure_never_calls_brave(self):
  client=Mock()
  with patch('search_workflow.research_backlog',return_value=10):result=sw.run(self.issue(purpose='discovery'),Mock(),self.config(),Mock(),worker.database,{'run_id':'run','agent_id':'search'},client,self.budget)
  self.assertEqual(result['stage'],'search_waiting');client.search.assert_not_called()
 def test_search_creates_task_only_after_direct_source_fetch(self):
  issue=self.issue();board=Mock()
  def call(path,body=None,method=None):
   if path.startswith('/heartbeat-runs'):return {'status':'running'}
   if path=='/issues/issue':return {**issue,'companyId':'company','status':'in_progress','assigneeAgentId':'search'}
   if path.endswith('/issues'):
    self.assertNotIn('responsibleUserId',body) # Paperclip derives agent-created attribution from its authenticated actor.
    return {'id':'child','identifier':'NAR-TEST'}
   raise AssertionError(path)
  board.call.side_effect=call;client=Mock();client.search.return_value=[{'url':'https://example.org/kids','title':'DO NOT SAVE BRAVE TITLE','description':'DO NOT SAVE BRAVE SNIPPET'}];web=Mock();web.page.return_value={'url':'https://example.org/kids','title':'Direct source title','text':'Kids music classes at 12 Main Street.','sha256':'hash','fetched_at':1}
  with patch('search_workflow.research_backlog',return_value=0):result=sw.run(issue,board,self.config(),web,worker.database,{'run_id':'run','agent_id':'search'},client,self.budget)
  self.assertEqual(result['stage'],'search_completed')
  with worker.database() as db:stored=db.execute('SELECT outcome_json FROM search_jobs').fetchone()[0]
  self.assertNotIn('DO NOT SAVE',stored);self.assertIn('Direct source title',stored);self.assertIn('NAR-TEST',stored)
 def test_delivery_retry_reuses_source_without_spending_search(self):
  issue=self.issue();job=sw.enqueue(issue,worker.database);outcome=json.loads(job['outcome_json']);outcome['source_pages']=[{'url':'https://example.org/kids','title':'Source page','sha256':'hash','fetched_at':1}]
  with worker.database() as db:db.execute("UPDATE search_jobs SET status='delivery_pending',outcome_json=?,error='old failure' WHERE issue_id=?",(json.dumps(outcome),issue['id']))
  client=Mock();board=Mock()
  with patch('search_workflow.research_backlog',return_value=0),patch('search_workflow.deliver',return_value=outcome):result=sw.run(issue,board,self.config(),Mock(),worker.database,{'run_id':'run','agent_id':'search'},client,self.budget)
  self.assertEqual(result['stage'],'search_completed');client.search.assert_not_called();self.assertEqual(self.budget.status()['used_this_window'],0)
  with worker.database() as db:self.assertIsNone(db.execute('SELECT error FROM search_jobs').fetchone()[0])
 def test_cross_host_candidate_is_not_fetched(self):
  sw.initialize(worker.database);web=Mock();pages=sw.verified_pages([{'url':'https://other.org/kids'}],{'source_host':'example.org','kind':'publishing'},web,worker.database,5);self.assertEqual(pages,[]);web.page.assert_not_called()
 def test_brave_transport_does_not_retry_429(self):
  opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://api.search.brave.com',429,'limited',self.headers('0'),io.BytesIO(b'never persist'))
  token=self.budget.reserve('job',1)[0]
  with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-secret'}):
   with self.assertRaises(brave.SearchError):brave.Brave(self.budget,opener).search('kids classes',token)
  self.assertEqual(opener.open.call_count,1);self.assertEqual(self.budget.status()['used_this_window'],1)
 def test_brave_transport_fixed_origin_and_no_payload_archive(self):
  response=Mock();response.status=200;response.headers=self.headers();response.read.return_value=b'{"web":{"results":[{"url":"https://example.org/kids","description":"private to RAM"}]}}';context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False);opener=Mock();opener.open.return_value=context;token=self.budget.reserve('job',1)[0]
  with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-secret'}):rows=brave.Brave(self.budget,opener).search('kids classes',token)
  self.assertEqual(len(rows),1);request=opener.open.call_args.args[0];self.assertTrue(request.full_url.startswith('https://api.search.brave.com/res/v1/web/search?'));self.assertNotIn('test-secret',request.full_url)
  with worker.database() as db:row=dict(db.execute('SELECT * FROM search_attempts').fetchone())
  self.assertNotIn('private to RAM',json.dumps(row));self.assertNotIn('test-secret',json.dumps(row))
if __name__=='__main__':unittest.main()
