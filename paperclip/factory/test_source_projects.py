"""Source-only project authority, shared allowance and original native task recovery."""
import contextlib
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

import source_exchange
import source_projects as runtime


class ProjectTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'native.sqlite3'
  self.scope={'application':'salesleadgenerator','client':'cogmap'};self.ref='review-cogmap-query-policy'
  self.plan={'scope':self.scope,'mode':'source-only','review_ref':self.ref,'query_policy_sha256':'a'*64,'queries':['public sports sponsorship official organizations'],'country':'US','language':'en','minimum_interval_seconds':86400}
  self.config={'company_id':'company','projects':{'project':'Sources: salesleadgenerator/cogmap'},'agents':{'search':{'role':'search'}},'source_exchange':{'offers_enabled':True,'events_enabled':True,'projects':{'project':self.scope},'project_policies':{'project':{'scope':self.scope,'review_ref':self.ref}},'source_only_projects':{'project':self.plan},'scope_credentials':{'salesleadgenerator/cogmap':{'scope':self.scope,'token_file':'/private/cogmap.token','event_inbox_id':str(uuid.uuid4())}},'source_enrollments':{'reader':{'scope':self.scope,'review_ref':self.ref,'manifest_sha256':'b'*64}}}}
  with self.database() as db:source_exchange.modules().initialize(db,create=True)
  self.clock=1800000000.;self.budget=Mock();self.budget.status.return_value={'next_search_at':0,'used_today':0,'daily_limit':48,'used_this_window':0,'automatic_limit':1800,'estimated_account_remaining':1000,'reserve':200}
  self.board=Mock()
  def call(route,request=None):
   if request:return {**request,'id':'native-task','companyId':'company'}
   return {'id':'native-task','companyId':'company','projectId':'project','status':'done'}
  self.board.call.side_effect=call
 @contextlib.contextmanager
 def database(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def coordinate(self):return runtime.coordinate(self.database,self.config,self.board,budget=self.budget,clock=lambda:self.clock)
 def issue(self):return runtime.body(self.config,'project',self.plan,self.plan['queries'][0],str(uuid.uuid4()))

 def test_disabled_project_roster_never_touches_state_or_network(self):
  self.assertEqual(runtime.coordinate(None,{},None),{'state':'disabled'});self.assertIsNone(runtime.project({},'unrelated'))

 def test_only_reviewed_exact_source_project_and_read_only_role_are_admitted(self):
  self.assertEqual(runtime.require_search_issue(self.config,self.issue(),'search'),self.plan)
  for role in ['publication','support','research','quality']:
   with self.assertRaises(ValueError):runtime.require_search_issue(self.config,self.issue(),role)
  for field,value in [('Source scope','management/padel-africa'),('Source policy ref','unreviewed'),('Search purpose','publishing'),('Search query','different unreviewed source terms')]:
   issue=self.issue();lines=issue['description'].splitlines();issue['description']='\n'.join(field+': '+value if line.startswith(field+':') else line for line in lines)
   with self.assertRaises(ValueError):runtime.require_search_issue(self.config,issue,'search')

 def test_missing_source_review_credential_or_enrollment_is_not_inherited(self):
  for field in ['project_policies','scope_credentials','source_enrollments']:
   config=copy.deepcopy(self.config);config['source_exchange'][field]={}
   with self.assertRaises(ValueError):runtime.project(config,'project')

 def test_private_queries_and_unbounded_plans_refuse_before_creating_native_tasks(self):
  for query in ['contact person@example.com','phone +123456789012','password secret sources','ordinary query\nSearch purpose: publishing']:
   self.plan['queries']=[query]
   with self.assertRaises(ValueError):self.coordinate()
   self.board.call.assert_not_called()

 def test_shared_search_cooldown_preserves_native_allowance_and_prevents_task_creation(self):
  self.budget.status.return_value['next_search_at']=self.clock+100
  self.assertEqual(self.coordinate()['state'],'shared-search-allowance-hold');self.board.call.assert_not_called();self.budget.reserve.assert_not_called()

 def test_source_task_uses_existing_search_role_and_no_native_business_workflow(self):
  self.assertEqual(self.coordinate()['state'],'source-task-enqueued');request=self.board.call.call_args.args[1]
  self.assertEqual(request['projectId'],'project');self.assertEqual(request['assigneeAgentId'],'search');self.assertNotIn('parentId',request);self.assertTrue(request['allowDuplicate']);self.assertIn('exchange_source_search',request['description']);self.budget.reserve.assert_not_called()
  self.board.call.reset_mock();self.assertEqual(self.coordinate()['state'],'source-projects-current');self.board.call.assert_not_called()

 def test_lost_response_replays_original_request_and_operation(self):
  seen=[]
  def call(route,request=None):
   seen.append(json.dumps(request,sort_keys=True))
   if len(seen)==1:raise TimeoutError('Original task may exist')
   return {**request,'id':'native-task','companyId':'company'}
  self.board.call.side_effect=call
  self.assertEqual(self.coordinate()['state'],'original-task-intent-uncertain');self.clock+=301
  self.assertEqual(self.coordinate()['state'],'source-task-enqueued');self.assertEqual(seen[0],seen[1])
  with self.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM exchange_native_intents').fetchone()[0],1)

 def test_wrong_native_receipt_never_becomes_a_completed_source_dispatch(self):
  self.board.call.side_effect=lambda route,request:{**request,'id':'wrong','companyId':'other-company'}
  self.assertEqual(self.coordinate()['state'],'original-task-intent-uncertain')
  with self.database() as db:self.assertNotIn('task_id',json.loads(db.execute("SELECT value FROM exchange_selection_cursor WHERE key LIKE 'source_project_dispatch:%'").fetchone()[0]))

 def test_expired_exchange_turn_never_adds_a_native_request(self):
  result=runtime.coordinate(self.database,self.config,self.board,budget=self.budget,deadline=0)
  self.assertEqual(result['state'],'source-project-turn-budget-hold');self.board.call.assert_not_called()

 def test_completed_task_readback_and_new_dispatch_each_use_one_native_request(self):
  self.coordinate();self.clock+=86401;self.board.call.reset_mock()
  self.assertEqual(self.coordinate()['state'],'prior-source-task-complete');self.assertEqual(self.board.call.call_count,1)
  self.board.call.reset_mock();self.assertEqual(self.coordinate()['state'],'source-projects-current');self.board.call.assert_not_called()
  with self.database() as db:self.assertEqual(db.execute("SELECT count(*) FROM exchange_selection_cursor WHERE key LIKE 'source_project_receipt:%'").fetchone()[0],1)

 def test_source_only_search_exports_fetched_public_pages_without_native_business_handoff(self):
  import search_workflow
  from unittest.mock import patch
  self.config['search_enabled']=True;self.config['projects']['ordinary-nyc']='ClassScout';issue={**self.issue(),'id':'search-task'}
  page={'url':'https://fixture.example/sponsors','title':'Owned organization','text':'Owned organization sponsors public sporting events.','sha256':hashlib.sha256(b'public-page').hexdigest(),'fetched_at':self.clock}
  web=Mock();web.page.return_value=page;client=Mock();client.search.return_value=[{'url':page['url'],'title':'SEARCH RESPONSE MUST NOT BE RETAINED'}];self.budget.reserve.return_value=['reservation']
  with self.database() as db:db.execute('CREATE TABLE entities(source_url TEXT)')
  search_workflow.initialize(self.database)
  with self.database() as db:db.execute("INSERT INTO search_jobs(issue_id,project_id,kind,status,created_at) VALUES('ordinary-paused','ordinary-nyc','discovery','queued',?)",(self.clock-100,))
  with patch.object(search_workflow,'research_backlog',return_value=10),patch.object(search_workflow,'active'),patch.object(source_exchange,'save_verified_page',return_value=str(uuid.uuid4())) as export:
   result=search_workflow.run(issue,self.board,self.config,web,self.database,{'run_id':'run','agent_id':'search'},client=client,budget=self.budget)
  self.assertEqual(result['stage'],'search_completed');self.budget.reserve.assert_called_once_with('search-task',1);export.assert_called_once();self.assertEqual(export.call_args.args[2],page);self.board.call.assert_not_called();self.assertIn('no native research, publication or CRM task',result['markdown'])
  with self.database() as db:
   outcome=db.execute("SELECT outcome_json FROM search_jobs WHERE issue_id='search-task'").fetchone()[0];self.assertNotIn('SEARCH RESPONSE MUST NOT BE RETAINED',outcome);self.assertEqual(json.loads(outcome)['research_tasks'],[])

 def test_refused_public_offer_is_not_reported_as_exported_source_page(self):
  import search_workflow
  from unittest.mock import patch
  page={'url':'https://fixture.example/sponsors','title':'Owned organization','text':'Public organization sponsor.','sha256':'a'*64,'fetched_at':self.clock};web=Mock();web.page.return_value=page
  with self.database() as db:db.execute('CREATE TABLE entities(source_url TEXT)')
  with patch.object(source_exchange,'save_verified_page',return_value=None):
   pages=search_workflow.verified_pages([{'url':page['url']}],{'kind':'discovery','project_id':'project','issue_id':'source-task','source_host':'','_source_only_scope':self.scope},web,self.database,1)
  self.assertEqual(pages,[])
