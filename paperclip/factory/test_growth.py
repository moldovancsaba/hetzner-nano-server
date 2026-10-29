import json,pathlib,time,unittest
from unittest.mock import Mock,patch
import worker,growth,search_workflow,pipeline,publishing,workflows_setup
import test_operations

class GrowthTests(unittest.TestCase):
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp();self.config={'company_id':'company','projects':{'project':'ClassScout'},'agents':{'search':{'role':'search'},'research':{'role':'research'},'quality':{'role':'quality'},'publisher':{'role':'publication'}},'growth_mode':{'enabled':True},'automatic_quality_gate':{'enabled':True},'operational_workflows_enabled':True}
 def tearDown(self):self.helper.tearDown()
 def run_dispatch(self,backlog=0,**status):
  board=Mock();board.call.return_value={'id':'child','identifier':'NAR-child'};budget=Mock();budget.status.return_value={'next_search_at':0,'used_today':0,'daily_limit':48,'used_this_window':2,'automatic_limit':1800,'estimated_account_remaining':1998,'reserve':200,**status}
  with patch('search_workflow.research_backlog',return_value=backlog):result=growth.run({'id':'cycle','projectId':'project'},board,self.config,Mock(),worker.database,{},budget)
  return result,board
 def test_dispatch_creates_bounded_production_search_task(self):
  result,board=self.run_dispatch();self.assertEqual(result['final_status'],'done');self.assertEqual(board.call.call_count,1);body=board.call.call_args.args[1];self.assertEqual(len(search_workflow.parse(body)['queries']),1);self.assertIn('Discovery campaign: classscout-nyc-v1',body['description']);self.assertEqual(body['assigneeAgentId'],'search')
 def test_cooldown_capacity_reserve_and_daily_allowance_stop_dispatch(self):
  cases=[{'next_search_at':time.time()+1800},{'used_today':48},{'used_this_window':1800},{'estimated_account_remaining':200}]
  for status in cases:
   result,board=self.run_dispatch(**status);board.call.assert_not_called();self.assertIsNone(result['report']['created_task'])
  _,board=self.run_dispatch(backlog=10);board.call.assert_not_called()
 def test_existing_search_queue_drains_before_more_work(self):
  search_workflow.initialize(worker.database)
  with worker.database() as db:
   for id in ['one','two']:db.execute("INSERT INTO search_jobs(issue_id,kind,status) VALUES(?,'publishing','queued')",(id,))
  _,board=self.run_dispatch();board.call.assert_not_called()
 def test_campaign_spreads_all_boroughs_and_activities(self):
  rows=growth.intents();self.assertEqual(len(rows),420);self.assertEqual(len({search_workflow.fingerprint(r['query']) for r in rows}),420);self.assertEqual({r['activity'] for r in rows},set(growth.ACTIVITIES));self.assertEqual({r['borough'] for r in rows},set(growth.BOROUGHS))
 def test_old_test_drafts_do_not_stop_production(self):
  board=Mock();board.call.return_value=[{'id':'test','status':'in_review','title':'[Factory test] Research','assigneeAgentId':'research'},{'id':'real','status':'todo','title':'Research children classes','assigneeAgentId':'research'}];self.assertEqual(search_workflow.research_backlog(board,self.config,worker.database),1)
 def inference(self,text='Example Center offers Music classes at 12 Main Street in Carroll Gardens, Brooklyn.'):
  page={'url':'https://example.org/classes','title':'Example','text':text,'sha256':'source','fetched_at':time.time()};facts=[{'field':'name','value':'Example Center','quote':'Example Center'},{'field':'address','value':'12 Main Street','quote':'12 Main Street'}];id=worker.save_draft('ClassScout',{'id':'source'},page,facts)
  with worker.database() as db:db.execute("UPDATE entities SET status='ready_for_human_review' WHERE id=?",(id,));row=dict(db.execute('SELECT * FROM entities WHERE id=?',(id,)).fetchone())
  web=Mock();web.page.return_value=page;issue={'id':'quality','projectId':'project','title':'Verified candidate','description':'Discovery borough: Brooklyn\nDiscovery activity: Music\nDiscovery campaign: classscout-nyc-v1'}
  return issue,row,web
 def test_editorial_brief_requires_actual_page_evidence(self):
  issue,row,web=self.inference()
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):brief=growth.infer(issue,row,worker.database,web)
  self.assertEqual(brief,{'Publication name':'Example Center','Borough':'Brooklyn','Neighborhood':'Carroll Gardens','Format':'Classes','Activity':'Music'})
 def test_query_hints_cannot_invent_activity_or_neighborhood(self):
  issue,row,web=self.inference('Example Center at 12 Main Street in Brooklyn.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):self.assertEqual(growth.infer(issue,row,worker.database,web),{})
 def test_multiple_neighborhoods_require_focused_source(self):
  issue,row,web=self.inference('Example Center Music classes at 12 Main Street in Carroll Gardens, Brooklyn, also serving Park Slope.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens','Park Slope']}):self.assertEqual(growth.infer(issue,row,worker.database,web),{})
 def test_verified_discovery_brief_advances_to_existing_publisher(self):
  issue,row,web=self.inference();board=Mock();board.call.return_value={'id':'publish','identifier':'NAR-publish'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):result=pipeline.advance(issue,row['id'],board,self.config,worker.database,web)
  self.assertEqual(result['identifier'],'NAR-publish');self.assertIn('Publication name: Example Center',board.call.call_args.args[1]['description']);self.assertIn('Neighborhood: Carroll Gardens',board.call.call_args.args[1]['description'])
 def test_discovery_hints_propagate_without_becoming_facts(self):
  text=search_workflow.discovery_metadata({'description':'Discovery borough: Queens\nDiscovery activity: Art\nDiscovery campaign: classscout-nyc-v1'});self.assertIn('Discovery activity: Art',text);self.assertNotIn('Activity:',text)

 def test_daily_write_allowance_wait_uses_native_deadline(self):
  import datetime
  disposition=worker.write_allowance_handoff({'executionPolicy':{'retained':'value'}});self.assertEqual(disposition['status'],'in_review');self.assertEqual(disposition['executionPolicy']['retained'],'value');due=datetime.datetime.fromisoformat(disposition['executionPolicy']['monitor']['nextCheckAt'].replace('Z','+00:00'));self.assertGreater(due.timestamp(),time.time());self.assertLess(due.timestamp(),time.time()+26*3600)
 def test_factory_catalog_pages_cannot_be_used_as_official_discovery_evidence(self):
  web=Mock();job={'source_host':'','kind':'discovery'};rows=[{'url':'https://classscout.ai/providers/prov-any'},{'url':'https://getyourfield.com/nyc/classes'}];self.assertEqual(search_workflow.verified_pages(rows,job,web,worker.database,3),[]);web.page.assert_not_called()

 def test_catalog_controller_and_quality_review_use_distinct_roles(self):
  import operational
  self.assertEqual(operational.ROLES['verify_catalog'],'support');self.assertNotEqual(operational.ROLES['verify_catalog'],'quality')
