"""Tests for company_ops: blocker classification and handoff, freshness checks, expiring support knowledge,
Padel discovery and candidate intake, delivery metrics; SearchReliabilityTests covers search_workflow
delivery caps and queue fairness, and idempotent company_ops dispatch."""
import datetime,json,time,unittest
from unittest.mock import Mock,patch
import worker,company_ops as ops,search_workflow as sw,catalog,publishing,support,business_metrics
import test_operations,test_search

class CompanyTests(unittest.TestCase):
 def setUp(self):
  self.helper=test_operations.OperationalTests();self.helper.setUp();ops.initialize(worker.database)
  self.config={'company_id':'company','reliability_enabled':True,'padel_enabled':True,'padel_discovery_enabled':True,'projects':{'project':'ClassScout','padel':'Padel Africa','ops':'Factory Operations'},'agents':{'research':{'role':'research'},'quality':{'role':'quality'},'publisher':{'role':'publication'},'support':{'role':'support'},'search':{'role':'search'}}}
  self.issue={'id':'routine','title':'Routine','projectId':'project'}
 def tearDown(self):self.helper.tearDown()
 def stored(self):
  row=self.helper.row();page=self.helper.page()
  with worker.database() as db:db.execute('INSERT INTO catalog_checks VALUES(?,?,?,?,?)',(row['id'],'old','hash',time.time(),json.dumps({'provider':row})))
  client=Mock();client.get.return_value=row;web=Mock();web.page.return_value=page
  return row,page,client,web
 def test_blocker_classification_does_not_blindly_retry_receipts(self):
  category,action=ops.classify('Uncertain write receipt, price also absent');self.assertEqual(category,'write_verification');self.assertIn('Never resend',action)
 def test_branch_identity_does_not_match_age_inside_page(self):
  self.assertEqual(ops.classify('No official page uniquely confirmed street and provider identity')[0],'branch_identity')
 def test_blocked_handoff_names_native_recovery_owner(self):
  value=worker.blocked_handoff(self.config,'Missing price','publisher');self.assertEqual(value['status'],'blocked');self.assertEqual(value['unblockDescriptor']['owner'],{'agentId':'publisher'});self.assertIn('Missing price',value['unblockDescriptor']['action'])
 def test_unchanged_blockers_get_one_action_comment(self):
  t={'id':'held','companyId':'company','title':'Held','status':'blocked','description':'No source yet'};board=Mock();board.call.return_value=[t]
  for _ in range(2):ops.reliability(self.issue,board,self.config,Mock(),worker.database)
  self.assertEqual(sum(c.args[0].endswith('/comments') for c in board.call.call_args_list),1)
 def test_freshness_change_enters_independent_research_once_per_hash(self):
  row,page,client,web=self.stored();board=Mock();board.call.return_value={'identifier':'NAR-NEW'}
  with patch('company_ops.evidence.crawl',return_value=[page]):ops.freshness(self.issue,board,self.config,web,worker.database,client)
  with worker.database() as db:db.execute('UPDATE freshness_checks SET checked_at=0')
  changed={**page,'sha256':'changed'}
  with patch('company_ops.evidence.crawl',return_value=[changed]):ops.freshness(self.issue,board,self.config,web,worker.database,client)
  body=board.call.call_args.args[1];self.assertEqual(body['assigneeAgentId'],'research');self.assertNotIn('parentId',body);self.assertIn('Catalog provider:',body['description'])
  self.assertEqual(board.call.call_count,1)
 def test_claimed_catalog_never_creates_freshness_write(self):
  row,page,client,web=self.stored();client.get.return_value={**row,'owner_managed':True};board=Mock();ops.freshness(self.issue,board,self.config,web,worker.database,client);board.call.assert_not_called();web.page.assert_not_called()
 def test_knowledge_answers_expire_and_failed_revalidation_invalidates(self):
  row,page,client,web=self.stored()
  with patch('company_ops.evidence.branch_page',return_value=(page,[{'field':'address','value':'12 Main Street','quote':'12 Main Street'}],{})):
   result=ops.knowledge(self.issue,Mock(),self.config,web,worker.database,client)
  self.assertGreater(result['report']['ready_answers'],0);self.assertEqual(result['report']['customer_messages_sent'],0)
  with worker.database() as db:db.execute('UPDATE support_knowledge SET verified_at=0')
  with patch('company_ops.evidence.branch_page',side_effect=ValueError('changed')):ops.knowledge(self.issue,Mock(),self.config,web,worker.database,client)
  with worker.database() as db:self.assertEqual(db.execute("SELECT count(*) FROM support_knowledge WHERE status='ready'").fetchone()[0],0)
 def test_cached_answer_requires_same_hash_and_unexpired_evidence(self):
  row,page,client,web=self.stored();v={'source_url':page['url'],'source_sha256':page['sha256'],'facts':[],'reply':'Verified'}
  with worker.database() as db:db.execute('INSERT INTO support_knowledge VALUES(?,?,?,?,?,?)',(row['id'],'website','ready',json.dumps(v),time.time(),time.time()+100))
  self.assertTrue(support.cached_answer(worker.database,row['id'],'What is the official website?',page)['reused_knowledge'])
  self.assertIsNone(support.cached_answer(worker.database,row['id'],'What is the official website?',{**page,'sha256':'changed'}))
  with worker.database() as db:db.execute('UPDATE support_knowledge SET expires_at=0')
  self.assertIsNone(support.cached_answer(worker.database,row['id'],'What is the official website?',page))
 def test_padel_discovery_uses_canonical_city_and_shared_search(self):
  client=Mock();client.catalog.return_value={'vertical':{'discovery':{'localities':['Cape Town']}}};board=Mock();board.call.return_value={'identifier':'NAR-NEW'}
  ops.padel_discovery({**self.issue,'projectId':'padel'},board,self.config,Mock(),worker.database,client)
  body=board.call.call_args.args[1];self.assertIn('Search purpose: padel',body['description']);self.assertIn('Padel city: Cape Town',body['description']);self.assertEqual(body['projectId'],'padel')
 def test_ambiguous_padel_source_is_never_ingested(self):
  client=Mock();client.catalog.return_value={'vertical':{'discovery':{'localities':['Cape Town']}}};i={**self.issue,'description':'Padel city: Cape Town\nOfficial source URL: https://example.org'};board=Mock()
  with patch('company_ops.evidence.crawl',return_value=[self.helper.page()]):
   with self.assertRaises(ValueError):ops.padel_candidate(i,board,self.config,Mock(),worker.database,{},client)
  board.call.assert_not_called();client.call.assert_not_called()
 def test_padel_candidate_queues_literal_intake_without_parent_cycle(self):
  page={'url':'https://examplepadel.org/','title':'Example Padel','text':'Example Padel in Cape Town at 12 Main Street.','sha256':'hash'};client=Mock();client.catalog.return_value={'vertical':{'discovery':{'localities':['Cape Town']}}};i={**self.issue,'description':'Padel city: Cape Town\nOfficial source URL: '+page['url']};board=Mock();board.call.return_value={'identifier':'NAR-NEW'}
  with patch('company_ops.evidence.crawl',return_value=[page]):ops.padel_candidate(i,board,self.config,Mock(),worker.database,{},client)
  body=board.call.call_args.args[1];self.assertIn('Factory workflow: padel_intake',body['description']);self.assertIn('Street address: 12 Main Street',body['description']);self.assertNotIn('parentId',body)
 def test_wrong_brand_workflows_are_rejected(self):
  with self.assertRaises(ValueError):ops.run({**self.issue,'description':'Factory workflow: knowledge_round','projectId':'padel'},Mock(),self.config,Mock(),worker.database,{})
 def test_delivery_metric_does_not_count_completed_run_as_publication(self):
  t={'id':'task','status':'done','title':'Research done'};stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with worker.database() as db:db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',('r','task','research','research','completed','{}',None,stamp,stamp))
  result=business_metrics.delivery_snapshot(worker.database,self.config,{'task':t});self.assertEqual(result['verified_results'],0);self.assertIsNone(result['median_hours_to_publication'])

class SearchReliabilityTests(unittest.TestCase):
 setUp=test_search.SearchTests.setUp
 tearDown=test_search.SearchTests.tearDown
 issue=test_search.SearchTests.issue
 config=test_search.SearchTests.config
 def test_delivery_attempts_stop_at_three_and_never_repeat_search(self):
  i=self.issue();job=sw.enqueue(i,worker.database);outcome=json.loads(job['outcome_json']);outcome['source_pages']=[{'url':'https://example.org/kids','title':'Source'}]
  with worker.database() as db:db.execute("UPDATE search_jobs SET status='delivery_pending',outcome_json=?",(json.dumps(outcome),))
  client=Mock()
  for n in range(3):
   with worker.database() as db:db.execute('UPDATE search_jobs SET next_delivery_at=0')
   with patch('search_workflow.research_backlog',return_value=0),patch('search_workflow.deliver',side_effect=RuntimeError('no sensitive body retained')):result=sw.run(i,Mock(),self.config(),Mock(),worker.database,{'run_id':'r','agent_id':'search'},client,self.budget)
  self.assertEqual(result['stage'],'search_failed');client.search.assert_not_called()
  with worker.database() as db:self.assertEqual(db.execute('SELECT delivery_attempts FROM search_jobs').fetchone()[0],3)
 def test_sleeping_delivery_does_not_starve_fresh_discovery(self):
  sw.enqueue(self.issue('old'),worker.database);sw.enqueue(self.issue('new',purpose='discovery',query='official kids classes Manhattan'),worker.database)
  with worker.database() as db:db.execute("UPDATE search_jobs SET status='delivery_pending',next_delivery_at=? WHERE issue_id='old'",(time.time()+3600,))
  board=Mock();board.call.return_value={'id':'new','status':'in_progress','assigneeAgentId':'search'}
  with patch('search_workflow.research_backlog',return_value=0):chosen=sw.queued_issue(board,self.config(),'search',worker.database)
  self.assertEqual(chosen['id'],'new')
 def test_recovered_publication_uses_independent_continuation(self):
  sw.initialize(worker.database);i=self.issue();parent={'id':'parent','title':'Listing','projectId':'project','companyId':'company','status':'blocked','description':'Original'};job={'issue_id':i['id'],'kind':'publishing','parent_publication':'parent','parent_input_hash':publishing.sha({'description':'Original','title':'Listing','project':'project'})};out={'source_pages':[{'url':'https://example.org/program','title':'Program'}],'research_tasks':[]};board=Mock()
  board.call.side_effect=lambda path,body=None,method=None:parent if path=='/issues/parent' else {'id':'continuation','identifier':'NAR-NEW'}
  with patch('publishing.parse_brief',return_value={'urls':['https://example.org/'],'Publication name':'Example'}):sw.deliver(i,board,{**self.config(),'reliability_enabled':True},job,out,worker.database,{'run_id':'r','agent_id':'search'})
  with worker.database() as db:request=db.execute('SELECT * FROM company_dispatch').fetchone()
  self.assertIsNotNone(request);self.assertIn('continuation_request',out);self.assertNotIn('parentId',json.loads(request['payload_json']));self.assertFalse(any(len(c.args)>2 and c.args[2]=='PATCH' for c in board.call.call_args_list))

 def test_dispatch_runs_under_coordinator_and_is_idempotent(self):
  source={'id':'source','companyId':'company','projectId':'project','title':'Listing','description':'Original','status':'blocked'}
  body={'idempotencyKey':'key','projectId':'project','status':'todo','assigneeAgentId':'publisher','title':'Continuation','description':'Evidence'}
  ops.queue_dispatch(worker.database,'key',source,body);board=Mock();board.call.side_effect=lambda path,payload=None,method=None:source if path=='/issues/source' else {'id':'child','identifier':'NAR-CHILD'}
  config={**self.config(),'projects':{'project':'ClassScout'}}
  first=ops.dispatch_pending(board,config,worker.database);second=ops.dispatch_pending(board,config,worker.database)
  self.assertEqual(first,['NAR-CHILD']);self.assertEqual(second,[]);self.assertEqual(sum(c.args[0].endswith('/issues') for c in board.call.call_args_list),1)
 def test_dispatch_cancels_when_original_brief_changes(self):
  source={'id':'source','companyId':'company','projectId':'project','title':'Listing','description':'Original','status':'blocked'}
  ops.queue_dispatch(worker.database,'key',source,{'projectId':'project','status':'todo','assigneeAgentId':'publisher'});board=Mock();board.call.return_value={**source,'description':'Changed'}
  self.assertEqual(ops.dispatch_pending(board,self.config(),worker.database),[])
  self.assertEqual(board.call.call_count,1)
 def test_aged_padel_search_is_not_starved_by_new_classscout_intents(self):
  sw.enqueue(self.issue('padel',purpose='padel',query='padel club Cape Town official courts'),worker.database);sw.enqueue(self.issue('new',purpose='discovery',query='official kids programs Manhattan'),worker.database)
  with worker.database() as db:db.execute("UPDATE search_jobs SET created_at=? WHERE issue_id='padel'",(time.time()-7200,))
  board=Mock();board.call.side_effect=lambda path:{'id':path.split('/')[-1],'status':'in_progress','assigneeAgentId':'search'}
  with patch('search_workflow.research_backlog',return_value=0):chosen=sw.queued_issue(board,self.config(),'search',worker.database)
  self.assertEqual(chosen['id'],'padel')
