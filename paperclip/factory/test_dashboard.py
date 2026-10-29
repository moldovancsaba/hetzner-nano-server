"""Dashboard accounting: no invented publication, billing, or cross-company activity."""
import datetime,json,unittest
import business_metrics,worker,test_operations

class DashboardTests(unittest.TestCase):
 def setUp(self):
  self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def test_usage_and_runs_only_include_company_tasks(self):
  now=datetime.datetime.now(datetime.timezone.utc);stamp=now.isoformat()
  tasks=[{'id':'real','status':'done','identifier':'NAR-1','title':'Real work','projectId':'p','completedAt':stamp,'assigneeAgentId':'a'}]
  with worker.database() as db:
   for id,issue,tokens in [('1','real',100),('2','other',900)]:
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',(id,issue,'a','research','completed',json.dumps({'model_metrics':[{'model':'local','context':8192,'usage':{'total_tokens':tokens}}]}),None,stamp,stamp))
  result=business_metrics.operating_snapshot(worker.database,{'projects':{'p':'ClassScout'}},tasks,agents=[{'id':'a','name':'Analyst','status':'idle'}])
  self.assertEqual(result['inference']['tokens_24h'],100)
  self.assertEqual(result['operations']['runs_24h']['completed'],1)
  self.assertEqual(result['operations']['projects'][0]['done_24h'],1)
  self.assertEqual(result['operations']['team'][0]['assigned'],0)
  self.assertEqual(result['operations']['team'][0]['last_outcome'],'completed')
  self.assertNotIn('cost',result['inference'])
 def test_completion_includes_failed_and_held_runs(self):
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with worker.database() as db:
   for id,status in [('1','completed'),('2','failed'),('3','blocked')]:
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',(id,'task','a','quality',status,'{}',None,stamp,stamp))
  r=business_metrics.operating_snapshot(worker.database,{},[{'id':'task','status':'blocked'}],agents=[])
  self.assertEqual(r['operations']['completion_rate_24h'],33)
  self.assertEqual(r['operations']['model_waits'],0)
 def test_schedule_uses_budapest_local_time(self):
  now=datetime.datetime(2026,10,28,7,0,tzinfo=datetime.timezone.utc).timestamp()
  result=business_metrics.next_schedule('10 9 * * *',now)
  self.assertEqual(datetime.datetime.fromtimestamp(result,datetime.timezone.utc).hour,8)
  self.assertEqual(datetime.datetime.fromtimestamp(result,datetime.timezone.utc).minute,10)
  self.assertIsNone(business_metrics.next_schedule('0 9 * * 1',now))
