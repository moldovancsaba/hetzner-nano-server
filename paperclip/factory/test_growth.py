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
 def test_gap_reason_names_the_first_failed_field_and_lists_the_rest(self):
  issue,row,web=self.inference('Example Center at 12 Main Street in Brooklyn.')
  self.assertIsNone(growth.gap_reason(worker.database,row['id']))
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):self.assertEqual(growth.infer(issue,row,worker.database,web),{})
  self.assertEqual(growth.gap_reason(worker.database,row['id']),'Activity "Music" is not named on the source pages.')
  with worker.database() as db:stored=json.loads(db.execute('SELECT result_json FROM commissioning_checks WHERE entity_id=?',(row['id'],)).fetchone()[0])
  self.assertEqual([g['field'] for g in stored['gaps']],['activity','format','neighborhood'])
 def test_gap_reason_says_which_other_borough_the_page_names(self):
  issue,row,web=self.inference('Example Center Music classes at 12 Main Street in Queens.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):growth.infer(issue,row,worker.database,web)
  self.assertEqual(growth.gap_reason(worker.database,row['id']),'Borough "Brooklyn" is not named on the source pages (they name Queens).')
 def test_gap_reason_counts_competing_neighborhoods(self):
  issue,row,web=self.inference('Example Center Music classes at 12 Main Street in Carroll Gardens, Brooklyn, also serving Park Slope.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens','Park Slope']}):growth.infer(issue,row,worker.database,web)
  self.assertEqual(growth.gap_reason(worker.database,row['id']),'Neighborhood is ambiguous: 2 Brooklyn neighborhoods are named (Carroll Gardens, Park Slope); a focused page is needed.')
 def test_gap_reason_names_a_missing_quoted_address(self):
  issue,row,web=self.inference();growth.initialize(worker.database)
  with worker.database() as db:db.execute("DELETE FROM facts WHERE entity_id=? AND field='address'",(row['id'],))
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):self.assertEqual(growth.infer(issue,row,worker.database,web),{})
  self.assertEqual(growth.gap_reason(worker.database,row['id']),'Address is not established by a quoted source line.')
 def test_publication_queue_report_shows_the_stored_gap_reason(self):
  issue,row,web=self.inference('Example Center at 12 Main Street in Brooklyn.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):growth.infer(issue,row,worker.database,web)
  board=Mock();board.call.return_value={**issue,'companyId':'company','projectId':'project'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}):result=pipeline.run_queue({'id':'queue','projectId':'project','title':'Queue'},board,self.config,web,worker.database,{})
  self.assertIn('Activity "Music" is not named on the source pages.',result['markdown']);self.assertNotIn('Source-backed publication name',result['markdown'])
 def remote_config(self):return {**self.config,'remote_llm':{'enabled':True}}
 def choose(self,*choices):return patch('segmind.suggest',return_value=(list(choices),{'cost':0.003},None))
 def test_metered_model_picks_the_activity_the_page_names_and_the_brief_is_rechecked(self):
  issue,row,web=self.inference('Example Center offers Dance and Art classes at 12 Main Street in Carroll Gardens, Brooklyn.')
  pick={'field':'activity','value':'Dance','quote':'Example Center offers Dance and Art classes at 12 Main Street'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}),self.choose(pick) as ask:brief=growth.infer(issue,row,worker.database,web,self.remote_config(),'publication')
  self.assertEqual(brief,{'Publication name':'Example Center','Borough':'Brooklyn','Neighborhood':'Carroll Gardens','Format':'Classes','Activity':'Dance'})
  self.assertEqual(ask.call_args.args[2],{'activity':['Art','Dance']})
  self.assertIsNone(growth.gap_reason(worker.database,row['id']));self.assertIn('activity',growth.brief_note(worker.database,row['id']))
 def test_metered_model_cannot_use_a_quote_that_is_not_on_the_page_or_not_tied_to_the_address(self):
  issue,row,web=self.inference('Example Center Music classes at 12 Main Street in Carroll Gardens, Brooklyn, also serving Park Slope.')
  growth.initialize(worker.database)
  for quote in ['Example Center Music classes at 12 Main Street in Park Slope, Brooklyn','also serving Park Slope']:
   with worker.database() as db:db.execute('DELETE FROM commissioning_checks')
   with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens','Park Slope']}),self.choose({'field':'neighborhood','value':'Park Slope','quote':quote}):self.assertEqual(growth.infer(issue,row,worker.database,web,self.remote_config(),'publication'),{})
   self.assertTrue(growth.gap_reason(worker.database,row['id']).startswith('Neighborhood is ambiguous'));self.assertIsNone(growth.brief_note(worker.database,row['id']))
 def test_metered_model_chooses_between_competing_neighborhoods_with_an_address_tied_quote(self):
  issue,row,web=self.inference('Example Center Music classes at 12 Main Street in Carroll Gardens, Brooklyn, also serving Park Slope.')
  pick={'field':'neighborhood','value':'Carroll Gardens','quote':'12 Main Street in Carroll Gardens, Brooklyn'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens','Park Slope']}),self.choose(pick):brief=growth.infer(issue,row,worker.database,web,self.remote_config(),'quality')
  self.assertEqual(brief['Neighborhood'],'Carroll Gardens')
 def test_metered_model_is_not_asked_when_nothing_can_be_chosen(self):
  growth.initialize(worker.database)
  for text in ['Example Center classes at 12 Main Street in Carroll Gardens, Brooklyn.','Example Center Music at 12 Main Street in Brooklyn.']:
   issue,row,web=self.inference(text)
   with worker.database() as db:db.execute('DELETE FROM commissioning_checks')
   with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}),patch('segmind.suggest') as ask:self.assertEqual(growth.infer(issue,row,worker.database,web,self.remote_config(),'publication'),{})
   ask.assert_not_called()
 def test_one_paid_answer_per_unchanged_set_of_pages(self):
  issue,row,web=self.inference('Example Center offers Dance and Art classes at 12 Main Street in Carroll Gardens, Brooklyn.')
  pick={'field':'activity','value':'Art','quote':'Dance and Art classes at 12 Main Street'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}),self.choose(pick) as ask:
   growth.infer(issue,row,worker.database,web,self.remote_config(),'publication')
   with worker.database() as db:db.execute('UPDATE commissioning_checks SET checked_at=0')
   brief=growth.infer(issue,row,worker.database,web,self.remote_config(),'publication')
  self.assertEqual(ask.call_count,1);self.assertEqual(brief['Activity'],'Art')
 def test_an_unavailable_model_is_asked_again_next_time_and_leaves_the_gap(self):
  issue,row,web=self.inference('Example Center offers Dance and Art classes at 12 Main Street in Carroll Gardens, Brooklyn.')
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}),patch('segmind.suggest',return_value=([],None,'Remote choice unavailable: 500.')) as ask:
   self.assertEqual(growth.infer(issue,row,worker.database,web,self.remote_config(),'publication'),{})
   with worker.database() as db:db.execute('UPDATE commissioning_checks SET checked_at=0')
   growth.infer(issue,row,worker.database,web,self.remote_config(),'publication')
  self.assertEqual(ask.call_count,2);self.assertTrue(growth.gap_reason(worker.database,row['id']).startswith('Activity "Music"'))
 def test_publication_task_says_when_the_metered_model_helped_the_brief(self):
  issue,row,web=self.inference('Example Center offers Dance and Art classes at 12 Main Street in Carroll Gardens, Brooklyn.');board=Mock();board.call.return_value={'id':'publish','identifier':'NAR-publish'}
  pick={'field':'activity','value':'Dance','quote':'Example Center offers Dance and Art classes at 12 Main Street'}
  with patch.object(growth,'locations',return_value={'Brooklyn':['Carroll Gardens']}),self.choose(pick):pipeline.advance(issue,row['id'],board,self.remote_config(),worker.database,web)
  body=board.call.call_args.args[1]['description'];self.assertIn('Activity: Dance',body);self.assertIn('metered remote model',body)
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
