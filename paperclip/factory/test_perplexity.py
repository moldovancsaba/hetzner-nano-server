"""Tests for the Perplexity fallback: the hourly allowance, the fixed-origin client and the switch that keeps it off."""
import io,json,pathlib,tempfile,unittest,urllib.error
from unittest.mock import Mock,patch
import worker,search_budget as sb,search_workflow as sw,brave,perplexity as px

BUDAPEST_MIDNIGHT=1799967600.  # 2027-01-14 00:00 Europe/Budapest, so one local day holds 24 whole hours
class Clock:
 def __init__(self,now=BUDAPEST_MIDNIGHT):self.now=now
 def __call__(self):return self.now
class PerplexityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state_patch=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state_patch.start();worker.initialize()
  self.clock=Clock();self.budget=px.PerplexityBudget(worker.database,self.clock);self.brave=sb.Budget(worker.database,self.clock)
 def tearDown(self):self.state_patch.stop();self.tmp.cleanup()
 def issue(self,queries=('site:example.org kids music classes schedule','example.org kids music tuition')):
  return {'id':'issue','projectId':'project','title':'Find official sources','description':'Search purpose: publishing\n'+'\n'.join('Search query: '+q for q in queries)+'\nSource host: example.org'}
 def config(self,**extra):return {'search_enabled':True,'company_id':'company','projects':{'project':'ClassScout'},'agents':{'search':{'role':'search'},'research':{'role':'research'},'quality':{'role':'quality'},'publisher':{'role':'publication'}},**extra}
 def board(self,issue):
  board=Mock()
  def call(path,body=None,method=None):
   if path.startswith('/heartbeat-runs'):return {'status':'running'}
   if path=='/issues/issue':return {**issue,'companyId':'company','status':'in_progress','assigneeAgentId':'search'}
   return {}
  board.call.side_effect=call;return board
 def response(self,body):
  response=Mock();response.status=200;response.read.return_value=body;context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False);opener=Mock();opener.open.return_value=context;return opener
 def test_the_limits_are_one_an_hour_24_a_day_744_a_month(self):self.assertEqual((px.GAP,px.DAILY,px.MONTHLY),(3600,24,744))
 def test_one_request_an_hour(self):
  self.budget.reserve('a')
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('b')
  self.clock.now+=3599
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('b')
  self.clock.now+=1;self.budget.reserve('b');self.assertEqual(self.budget.status()['used_today'],2)
 def test_a_restart_cannot_reset_the_allowance(self):
  self.budget.reserve('a')
  with self.assertRaises(sb.BudgetWait):px.PerplexityBudget(worker.database,self.clock).reserve('b')
 def test_daily_ceiling_ends_at_local_midnight(self):
  with worker.database() as db:
   for i in range(px.DAILY):db.execute('INSERT INTO perplexity_attempts VALUES(?,?,?,?,?,?,?)',('t'+str(i),'job',BUDAPEST_MIDNIGHT-86400*3+i,px.day_key(BUDAPEST_MIDNIGHT+3600),px.month_key(BUDAPEST_MIDNIGHT),'succeeded',200))
  self.clock.now=BUDAPEST_MIDNIGHT+3600
  with self.assertRaises(sb.BudgetWait) as stop:self.budget.reserve('late')
  self.assertEqual(stop.exception.until,BUDAPEST_MIDNIGHT+86400);self.clock.now=BUDAPEST_MIDNIGHT+86400;self.budget.reserve('next day')
 def test_monthly_ceiling(self):
  with worker.database() as db:
   for i in range(px.MONTHLY):db.execute('INSERT INTO perplexity_attempts VALUES(?,?,?,?,?,?,?)',('t'+str(i),'job',BUDAPEST_MIDNIGHT-86400*20+i,'d'+str(i),px.month_key(BUDAPEST_MIDNIGHT),'succeeded',200))
  with self.assertRaises(sb.BudgetWait):self.budget.reserve('over')
 def test_a_reservation_counts_even_when_the_response_never_arrives(self):
  token=self.budget.reserve('job')[0];self.budget.dispatch(token);self.assertEqual(self.budget.status()['used_this_window'],1)
  with self.assertRaises(ValueError):self.budget.dispatch(token)
 def test_a_burst_is_refused(self):
  with self.assertRaises(ValueError):self.budget.reserve('job',2)
 def test_transport_is_fixed_origin_bearer_and_maps_rows(self):
  opener=self.response(json.dumps({'results':[{'url':'https://example.org/kids','title':'Kids','snippet':'Classes'},{'url':7},{'title':'no url'}]}).encode());token=self.budget.reserve('job')[0]
  rows=px.Perplexity(self.budget,opener,{'PERPLEXITY_SEARCH_API_KEY':'test-secret'}).search('kids classes',token)
  self.assertEqual(rows,[{'url':'https://example.org/kids','title':'Kids','description':'Classes'}])
  request=opener.open.call_args.args[0];self.assertEqual(request.full_url,'https://api.perplexity.ai/search');self.assertEqual(request.get_method(),'POST')
  self.assertEqual(request.headers['Authorization'],'Bearer test-secret');self.assertEqual(json.loads(request.data),{'query':'kids classes','max_results':20});self.assertNotIn('test-secret',request.full_url)
  with worker.database() as db:self.assertEqual(db.execute('SELECT status,http_status FROM perplexity_attempts').fetchone()[:],('succeeded',200))
 def test_no_key_means_no_request_and_no_spend_beyond_the_reservation(self):
  opener=Mock();token=self.budget.reserve('job')[0]
  with self.assertRaises(brave.SearchError):px.Perplexity(self.budget,opener,{}).search('kids classes',token)
  opener.open.assert_not_called()
 def test_a_429_is_not_retried_and_stays_counted(self):
  opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://api.perplexity.ai/search',429,'limited',{},io.BytesIO(b'never persist'));token=self.budget.reserve('job')[0]
  with self.assertRaises(brave.SearchError) as error:px.Perplexity(self.budget,opener,{'PERPLEXITY_SEARCH_API_KEY':'k'}).search('kids classes',token)
  self.assertTrue(error.exception.retryable);self.assertEqual(opener.open.call_count,1);self.assertEqual(self.budget.status()['used_this_window'],1)
 def test_a_private_query_is_rejected_before_any_request(self):
  opener=Mock();token=self.budget.reserve('job')[0]
  with self.assertRaises(brave.SearchError):px.Perplexity(self.budget,opener,{'PERPLEXITY_SEARCH_API_KEY':'k'}).search('x '*80,token)
  opener.open.assert_not_called()
 def test_slot_is_none_unless_enabled_and_keyed(self):
  env={'PERPLEXITY_SEARCH_API_KEY':'k'}
  self.assertIsNone(sw.perplexity_slot(self.config(),worker.database,'job',env))
  self.assertIsNone(sw.perplexity_slot(self.config(perplexity_enabled=True),worker.database,'job',{}))
  with worker.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM perplexity_attempts').fetchone()[0],0)
  slot=sw.perplexity_slot(self.config(perplexity_enabled=True),worker.database,'job',env);self.assertIsNotNone(slot);self.assertIsNone(sw.perplexity_slot(self.config(perplexity_enabled=True),worker.database,'job2',env))
 def test_brave_resting_and_switch_off_waits_without_any_request(self):
  self.brave.reserve('prior',1);client=Mock()
  with patch('search_workflow.research_backlog',return_value=0),patch.dict('os.environ',{'PERPLEXITY_SEARCH_API_KEY':'k'}):result=sw.run(self.issue(),Mock(),self.config(),Mock(),worker.database,{'run_id':'run','agent_id':'search'},client,self.brave)
  self.assertEqual(result['stage'],'search_waiting');client.search.assert_not_called()
 def test_brave_resting_and_switch_on_serves_the_first_query_through_perplexity(self):
  self.brave.reserve('prior',1);brave_client=Mock();served=Mock();served.search.return_value=[]
  with patch('search_workflow.research_backlog',return_value=0),patch('perplexity.Perplexity',return_value=served),patch.dict('os.environ',{'PERPLEXITY_SEARCH_API_KEY':'k'}):
   result=sw.run(self.issue(),self.board(self.issue()),self.config(perplexity_enabled=True),Mock(),worker.database,{'run_id':'run','agent_id':'search'},brave_client,self.brave)
  brave_client.search.assert_not_called();self.assertEqual(served.search.call_count,1);self.assertEqual(served.search.call_args.args[0],'site:example.org kids music classes schedule')
  
  with worker.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM perplexity_attempts').fetchone()[0],1)
  self.assertEqual(result['stage'],'search_completed')
 def test_a_second_waiting_job_inside_the_hour_still_waits(self):
  self.brave.reserve('prior',1);self.budget.reserve('earlier');client=Mock()
  with patch('search_workflow.research_backlog',return_value=0),patch.dict('os.environ',{'PERPLEXITY_SEARCH_API_KEY':'k'}):result=sw.run(self.issue(),Mock(),self.config(perplexity_enabled=True),Mock(),worker.database,{'run_id':'run','agent_id':'search'},client,self.brave)
  self.assertEqual(result['stage'],'search_waiting');client.search.assert_not_called()
if __name__=='__main__':unittest.main()
