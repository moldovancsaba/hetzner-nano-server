"""Regression coverage for contract repair, expired packet renewal, focused evidence and program scheduling."""
import copy,datetime,io,json,pathlib,tempfile,time,unittest,urllib.error,urllib.parse
from unittest.mock import Mock,patch
import autonomy,worker,publishing,refresh,packet_renewal as renewal,search_workflow as search,brave,evidence,pipeline,growth,portfolio,program_updates,company_ops
import test_automatic,test_operations

class DeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state.start();worker.initialize()
  self.config={'company_id':'company','projects':{'project':'ClassScout','hu':'Sportolok','ops':'Factory Operations'},'agents':{'publisher':{'role':'publication'},'research':{'role':'research'},'search':{'role':'search'},'quality':{'role':'quality'}},'automatic_quality_gate':{'enabled':True,'daily_write_limit':20},'program_updates_enabled':True,'reliability_enabled':True}
 def tearDown(self):self.state.stop();self.tmp.cleanup()
 def packet(self):
  issue={'id':'original','companyId':'company','projectId':'project','title':'Prepare Example','description':'Draft reference: '+'a'*32,'status':'blocked'}
  body={'draftPayload':{'id':'prov-example'}};proof={'sources':[]};ph=publishing.sha({'body':body,'proof':proof});ih=publishing.sha({'description':issue['description'],'title':issue['title'],'project':issue['projectId']})
  with worker.database() as db:
   publishing.initialize(db);db.execute('INSERT INTO publication_packets VALUES(?,?,?,?,?,?,?,?,?,?,?)',(ph,issue['id'],ih,'awaiting_approval',json.dumps(body),json.dumps(proof),None,None,None,'2020-01-01T00:00:00+00:00',publishing.stamp()))
  board=Mock();seen=[]
  def call(path,body=None,method=None):
   if path=='/issues/original':return copy.deepcopy(issue)
   if path.endswith('/issues'):
    seen.append(body);return {'id':'child','identifier':'NAR-CHILD','companyId':'company','projectId':'project'}
   if path.endswith('/interactions'):return []
   raise AssertionError(path)
  board.call.side_effect=call
  return issue,ph,board,seen
 def test_renewal_is_scheduled_once_and_retains_original(self):
  issue,ph,board,seen=self.packet()
  result=renewal.coordinate([issue],board,self.config,worker.database);again=renewal.coordinate([issue],board,self.config,worker.database)
  self.assertEqual(result['delivered'],['NAR-CHILD']);self.assertEqual(again['planned'],0);self.assertEqual(len(seen),1);self.assertEqual(issue['status'],'blocked')
  with worker.database() as db:
   self.assertEqual(db.execute('SELECT status FROM publication_packets').fetchone()[0],'superseded');self.assertEqual(db.execute('SELECT target_issue FROM packet_renewals').fetchone()[0],'child')
  self.assertIn('Packet renewal root: original',seen[0]['description'])
 def test_lost_creation_reply_reuses_same_native_key(self):
  issue,ph,board,seen=self.packet();original=board.call.side_effect
  def call(path,body=None,method=None):
   if path.endswith('/issues'):
    seen.append(body)
    if len(seen)==1:raise TimeoutError()
    return {'id':'child','identifier':'NAR-CHILD','companyId':'company','projectId':'project'}
   return original(path,body,method)
  board.call.side_effect=call
  renewal.coordinate([issue],board,self.config,worker.database)
  with worker.database() as db:db.execute('UPDATE packet_renewals SET next_at=0')
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['delivered'],['NAR-CHILD']);self.assertEqual(seen[0]['idempotencyKey'],seen[1]['idempotencyKey'])
 def test_renewal_refuses_every_submitted_or_terminal_state(self):
  issue,ph,board,seen=self.packet()
  for state in ['publishing','uncertain','partial','published','blocked']:
   with worker.database() as db:db.execute('UPDATE publication_packets SET status=?',(state,))
   self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0)
  self.assertFalse(seen)
 def test_renewal_refuses_gate_off_changed_brief_and_active_execution(self):
  issue,ph,board,seen=self.packet()
  self.assertEqual(renewal.coordinate([issue],board,{**self.config,'automatic_quality_gate':{'enabled':False}},worker.database)['planned'],0)
  issue['description']+=' changed';self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0)
  issue['description']=issue['description'].removesuffix(' changed')
  with patch('autonomy.stopped',return_value=False):self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0)
  self.assertFalse(seen)
 def test_human_decline_prevents_renewal(self):
  issue,ph,board,seen=self.packet()
  with worker.database() as db:db.execute("UPDATE publication_packets SET interaction_id='card'")
  old=board.call.side_effect
  board.call.side_effect=lambda path,*a:[{'id':'card','status':'rejected'}] if path.endswith('/interactions') else old(path,*a)
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0);self.assertFalse(seen)
 def test_packet_receipt_prevents_renewal(self):
  issue,ph,board,seen=self.packet()
  with worker.database() as db:db.execute("UPDATE publication_packets SET receipt_json='{}'")
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0)
 def test_hungarian_query_uses_supported_country(self):
  budget=Mock();opener=Mock();response=Mock();response.headers={};response.status=200;response.read.return_value=b'{"web":{"results":[]}}';opener.open.return_value.__enter__=Mock(return_value=response);opener.open.return_value.__exit__=Mock(return_value=False)
  with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'secret'}):brave.Brave(budget,opener,country='ALL',language='hu').search('uszoda Budapest','token')
  query=urllib.parse.parse_qs(urllib.parse.urlsplit(opener.open.call_args.args[0].full_url).query);self.assertEqual(query['country'],['ALL']);self.assertEqual(query['search_lang'],['hu'])
 def test_invalid_country_and_query_fail_before_dispatch(self):
  budget=Mock();opener=Mock()
  with self.assertRaises(brave.SearchError):brave.Brave(budget,opener,country='HU',language='hu')
  with self.assertRaises(brave.SearchError):brave.Brave(budget,opener).search('x '*76,'token')
  budget.dispatch.assert_not_called();opener.open.assert_not_called()
 def test_422_diagnostic_is_actionable_and_redacted(self):
  error=urllib.error.HTTPError('https://api.search.brave.com',422,'invalid',{},io.BytesIO(json.dumps({'error':{'meta':{'errors':[{'loc':['query','country'],'input':'SECRET','msg':'SECRET'}]}}}).encode()));opener=Mock();opener.open.side_effect=error
  with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'secret'}):
   with self.assertRaises(brave.SearchError) as caught:brave.Brave(Mock(),opener).search('kids classes','token')
  self.assertIn('country',str(caught.exception));self.assertNotIn('SECRET',str(caught.exception));self.assertFalse(caught.exception.retryable);self.assertEqual(opener.open.call_count,1)
 def test_query_dedup_includes_locale(self):self.assertNotEqual(search.fingerprint('children swimming','sportolok'),search.fingerprint('children swimming','discovery'))
 def test_failed_legacy_search_gets_one_budgeted_successor(self):
  issue={'id':'legacy','companyId':'company','projectId':'hu','title':'Find pools','description':'Search purpose: sportolok\nSearch query: uszoda Budapest','status':'in_review'}
  search.enqueue(issue,worker.database)
  with worker.database() as db:db.execute("UPDATE search_jobs SET status='needs_attention',error='Brave returned HTTP 422',request_contract='legacy'")
  board=Mock();bodies=[]
  def call(path,body=None,method=None):
   if path=='/issues/legacy':return issue
   bodies.append(body);return {'id':'new-search','identifier':'NAR-SEARCH','companyId':'company','projectId':'hu'}
  board.call.side_effect=call
  self.assertEqual(search.recover_contract(board,self.config,worker.database),['NAR-SEARCH']);self.assertEqual(search.recover_contract(board,self.config,worker.database),[])
  child={**bodies[0],'id':'new-search'};job=search.enqueue(child,worker.database);self.assertEqual(job['status'],'queued');self.assertEqual(job['request_contract'],brave.CONTRACT)
  with worker.database() as db:self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='search_attempts'").fetchone())
 def test_failed_contract_creation_backs_off_and_stops(self):
  issue={'id':'legacy','companyId':'company','projectId':'hu','title':'Find pools','description':'Search purpose: sportolok\nSearch query: uszoda Budapest','status':'in_review'}
  search.enqueue(issue,worker.database)
  with worker.database() as db:db.execute("UPDATE search_jobs SET status='needs_attention',error='Brave returned HTTP 422',request_contract='legacy'")
  board=Mock();board.call.side_effect=TimeoutError()
  for attempt in range(3):
   search.recover_contract(board,self.config,worker.database)
   with worker.database() as db:db.execute('UPDATE search_contract_recovery SET next_at=0')
  search.recover_contract(board,self.config,worker.database);self.assertEqual(board.call.call_count,3)
  with worker.database() as db:self.assertEqual(db.execute('SELECT status FROM search_contract_recovery').fetchone()[0],'needs_attention')
 def test_expired_preparation_failure_can_be_renewed_but_successor_is_not_duplicated(self):
  issue,ph,board,seen=self.packet()
  with worker.database() as db:db.execute("UPDATE publication_packets SET status='superseded'")
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['delivered'],['NAR-CHILD'])
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0)
 def test_tampered_expired_packet_does_not_block_later_coordination(self):
  issue,ph,board,seen=self.packet()
  with worker.database() as db:db.execute("UPDATE publication_packets SET body_json='{}'")
  self.assertEqual(renewal.coordinate([issue],board,self.config,worker.database)['planned'],0);self.assertFalse(seen)
 def test_publication_handoff_carries_focused_official_evidence(self):
  growth.initialize(worker.database);source={'id':'research','projectId':'project','title':'Research','description':'Publication name: Example Center\nBorough: Brooklyn\nNeighborhood: Carroll Gardens\nFormat: Classes\nActivity: Music'}
  entity='a'*32;report={'brief':{'Publication name':'Example Center'},'focused_pages':[{'url':'https://example.org/contact'},{'url':'https://other.org/location'}]}
  with worker.database() as db:
   db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?)',(entity,'ClassScout','https://example.org/','Example Center','ready_for_human_review','research',publishing.stamp()));db.execute('INSERT INTO commissioning_checks VALUES(?,?,?)',(entity,0,json.dumps(report)))
  board=Mock();board.call.return_value={'id':'publication','identifier':'NAR-PUBLISH'}
  pipeline.advance(source,entity,board,self.config,worker.database,Mock())
  body=board.call.call_args.args[1];self.assertIn('https://example.org/contact',body['description']);self.assertNotIn('https://other.org',body['description'])
 def test_focused_research_stops_at_three_attempts_per_root(self):
  growth.initialize(worker.database);report={'gaps':[{'field':'address'}],'reason':'Address is missing.','initial_urls':[],'focused_pages':[{'url':'https://example.org/one','sha256':'h','title':'Contact'}]}
  with worker.database() as db:db.execute('INSERT INTO commissioning_checks VALUES(?,?,?)',('entity',0,json.dumps(report)))
  issue={'id':'research','title':'Research','projectId':'project','description':'Evidence followup root: root'}
  for n in range(3):
   report['focused_pages'][0]['url']='https://example.org/'+str(n)
   with worker.database() as db:db.execute('UPDATE commissioning_checks SET result_json=?',(json.dumps(report),))
   self.assertIsNotNone(evidence.queue_focused_research(issue,'entity',Mock(),self.config,worker.database))
  report['focused_pages'][0]['url']='https://example.org/four'
  with worker.database() as db:db.execute('UPDATE commissioning_checks SET result_json=?',(json.dumps(report),))
  self.assertIsNone(evidence.queue_focused_research(issue,'entity',Mock(),self.config,worker.database))
 def test_seeded_crawl_is_same_host_bounded_and_does_not_refetch_seed(self):
  first={'url':'https://example.org/','text':'Example Center','links':['/privacy','https://other.org/classes','/programs','/classes/two','/classes/three','/classes/four']};web=Mock();web.page.side_effect=lambda url:{'url':url,'text':'Kids classes','links':[]}
  pages=evidence.crawl(first['url'],web,maximum=4,purpose='program',seed=[first]);self.assertEqual(len(pages),4);self.assertEqual(web.page.call_count,3);self.assertNotIn(first['url'],[c.args[0] for c in web.page.call_args_list]);self.assertTrue(all(c.args[0].startswith('https://example.org/') for c in web.page.call_args_list))
 def test_branch_contact_proof_excludes_non_address_model_fields(self):
  h=test_operations.OperationalTests();row=h.row();page=h.page();page['text']+=' 27 years of reputation.';web=Mock();web.page.return_value=page
  _,facts,_=evidence.branch_page(row,page['url'],[{'field':'address','value':'27 years of reputation','quote':'27 years of reputation'}],web)
  self.assertEqual([f['value'] for f in facts if f['field']=='address'],['12 Main Street'])
 def test_non_address_model_quote_cannot_supply_publication_street(self):
  import test_publishing
  h=test_publishing.PublishingTests();page=h.page();page['text']+=' 27 years of reputation.'
  with self.assertRaisesRegex(ValueError,'Missing source-verified street'):publishing.normalize_sources(h.brief(),[page],[{'field':'address','value':'27 years of reputation','quote':'27 years of reputation'}])
 def test_branch_parser_renewal_is_limited_to_affected_contact_proofs(self):
  packet={'created_at':time.time(),'proof_json':json.dumps({'facts':[{'field':'address','value':'27 years of reputation'}]})}
  self.assertTrue(renewal.due(packet,'refresh_packets'));self.assertFalse(renewal.due(packet,'publication_packets'))
  packet['proof_json']=json.dumps({'facts':[{'field':'address','value':'12 Main Street'}]});self.assertFalse(renewal.due(packet,'refresh_packets'))
 def test_program_fee_is_not_broadcast_across_age_groups(self):
  h=test_operations.OperationalTests();page=h.page();page['text']='Example Center at 12 Main Street. Ages 5-10 - Mondays 9:00 am, 45 minutes. Ages 12-15 - Tuesdays 4:00 pm, 60 minutes. $150 per month.'
  row=h.row();row['recurringPrograms']=[{'id':'a','title':'Ages 5-10','ageMinMonths':60,'ageMaxMonths':120,'price':{'evidence':'unknown','sourceUrl':page['url']}}]
  patch,_=program_updates.proposed(row,[page]);self.assertTrue(patch);self.assertEqual(patch['recurringPrograms'][0]['price']['evidence'],'unknown');self.assertNotIn('price',patch)
 def test_gap_categories_do_not_treat_the_word_pages_as_ages(self):
  self.assertEqual(evidence.gap_kind('Neighborhood is missing on source pages.'),'identity');self.assertEqual(evidence.gap_kind('Activity Theater is not named on the source pages.'),'editorial');self.assertEqual(evidence.gap_kind('Missing explicit ages on source pages.'),'program')
 def test_unreadable_program_source_is_not_reported_as_no_change(self):
  issue={'id':'program','projectId':'project','title':'Program check','description':'Catalog provider: prov-example'};client=Mock();client.existing_provider.return_value={'id':'prov-example','website':'https://example.org/','recurringPrograms':[{'id':'p'}]};writer=Mock()
  with patch('program_updates.evidence.crawl',return_value=[]):result=program_updates.run(issue,Mock(),self.config,Mock(),worker.database,None,client,writer)
  self.assertEqual(result['stage'],'program_source_unavailable');writer.apply.assert_not_called()
  with worker.database() as db:self.assertEqual(json.loads(db.execute("SELECT result_json FROM workflow_reports WHERE kind='program_update'").fetchone()[0])['outcome'],'source_unavailable')
 def test_native_creation_disables_title_dedup_but_keeps_exact_key(self):
  body={'title':'About Us','description':'https://example.org/about','projectId':'project','idempotencyKey':'stable'};reply={**body,'id':'child','companyId':'company'};board=worker.Board('secret','run')
  with patch('worker.request_json',return_value=reply) as request:
   board.call('/companies/company/issues',body)
  self.assertIs(request.call_args.args[1]['allowDuplicate'],True);self.assertEqual(request.call_args.args[1]['idempotencyKey'],'stable');self.assertNotIn('allowDuplicate',body)
 def test_native_receipt_for_another_provider_is_refused(self):
  body={'title':'About Us','description':'https://example.org/about','projectId':'project','idempotencyKey':'stable'};reply={**body,'id':'wrong','companyId':'company','description':'https://other.org/about'}
  with patch('worker.request_json',return_value=reply):
   with self.assertRaisesRegex(ValueError,'exact factory intent'):worker.Board('secret','run').call('/companies/company/issues',body)
 def test_wrong_focused_receipt_is_repaired_without_touching_other_research(self):
  company_ops.initialize(worker.database);source={'id':'source','companyId':'company','projectId':'project','title':'Research','description':'Source','status':'done'}
  body={'title':'About Us','projectId':'project','description':'Factory workflow: source_research\nEvidence followup root: correct\nhttps://correct.org/about','assigneeAgentId':'research','status':'todo','idempotencyKey':'focused-evidence-key'}
  company_ops.queue_dispatch(worker.database,'focused-evidence-key',source,body)
  with worker.database() as db:db.execute("UPDATE company_dispatch SET status='delivered',target_issue='wrong'")
  wrong={'id':'wrong','companyId':'company','projectId':'project','description':'Factory workflow: source_research\nEvidence followup root: different\nhttps://other.org/about'};board=Mock()
  board.call.side_effect=lambda path,*a:wrong if path=='/issues/wrong' else source
  company_ops.reconcile_focused_receipts(board,self.config,worker.database)
  with worker.database() as db:
   row=db.execute('SELECT * FROM company_dispatch').fetchone();self.assertEqual(row['status'],'queued');self.assertIsNone(row['target_issue']);self.assertEqual(json.loads(row['payload_json'])['idempotencyKey'],'focused-evidence-key-intent-v2');self.assertEqual(db.execute('SELECT target_issue FROM handoff_receipt_checks').fetchone()[0],'wrong')
  self.assertEqual(board.call.call_count,2)
  with worker.database() as db:db.execute("UPDATE company_dispatch SET status='delivered',target_issue='correct',next_at=0")
  board.call.side_effect=lambda path,*a:{**body,'id':'correct','companyId':'company'}
  company_ops.reconcile_focused_receipts(board,self.config,worker.database)
  with worker.database() as db:
   self.assertEqual(db.execute('SELECT count(*) FROM handoff_receipt_history').fetchone()[0],2);self.assertEqual(db.execute("SELECT outcome FROM handoff_receipt_history WHERE target_issue='wrong'").fetchone()[0],'mismatch')
 def test_stopped_read_without_factory_run_is_hydrated_from_native_detail(self):
  issue={'id':'qa','companyId':'company','projectId':'project','title':'Verify source evidence','description':'Factory workflow: source_quality','status':'blocked','updatedAt':'2026-11-01T09:00:00Z'}
  detail={**issue,'executionBlocker':{'runId':'failed','runStatus':'failed','cause':'legacy_execution_requires_reconciliation'}};board=Mock();board.call.side_effect=lambda path,*a:detail if path=='/issues/qa' else {'companyId':'company','status':'failed'}
  planned=autonomy.plan([issue],board,self.config,worker.database)
  self.assertEqual(planned['planned'][0]['condition'],'stopped_execution')
  with worker.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM native_recovery_checks').fetchone()[0],1)
 def test_unknown_native_details_are_bounded_and_cooled_down(self):
  issues=[{'id':'qa-'+str(n),'companyId':'company','projectId':'project','title':'Verify evidence','description':'Factory workflow: source_quality','status':'blocked','updatedAt':'2026-11-01T09:00:00Z'} for n in range(12)];board=Mock();board.call.side_effect=lambda path,*a:next(i for i in issues if path=='/issues/'+i['id'])
  autonomy.plan(issues,board,self.config,worker.database);self.assertEqual(board.call.call_count,10)
  autonomy.plan(issues,board,self.config,worker.database);self.assertEqual(board.call.call_count,12)
  autonomy.plan(issues,board,self.config,worker.database);self.assertEqual(board.call.call_count,12)
 def test_positive_native_hints_survive_the_two_successor_round_cap(self):
  issues=[{'id':'qa-'+str(n),'companyId':'company','projectId':'project','title':'Verify source evidence','description':'Factory workflow: source_quality','status':'blocked','updatedAt':'2026-11-01T09:00:00Z'} for n in range(3)];details={i['id']:{**i,'executionBlocker':{'runId':'failed','runStatus':'failed','cause':'legacy_execution_requires_reconciliation'}} for i in issues};board=Mock()
  board.call.side_effect=lambda path,*a:details[path.rsplit('/',1)[-1]] if path.startswith('/issues/') else {'companyId':'company','status':'failed'}
  first=autonomy.plan(issues,board,self.config,worker.database);second=autonomy.plan(issues,board,self.config,worker.database)
  self.assertEqual(len(first['planned']),2);self.assertEqual(len(second['planned']),1)
 def test_literal_address_can_replace_an_invalid_value_with_the_same_source_hash(self):
  h=test_operations.OperationalTests();page=h.page();page['text']+=' 27 years of reputation.';facts=[{'field':'name','value':'Example Center','quote':'Example Center'},{'field':'address','value':'27 years of reputation','quote':'27 years of reputation'}];entity=worker.save_draft('ClassScout',{'id':'source'},page,facts);web=Mock();web.page.return_value=page
  evidence.recover({'id':entity,'source_url':page['url']},worker.database,web)
  with worker.database() as db:self.assertEqual(db.execute("SELECT value FROM facts WHERE entity_id=? AND field='address'",(entity,)).fetchone()[0],'12 Main Street')
 def test_program_provenance_precedes_homepage_and_rejects_other_hosts(self):
  row={'website':'https://example.org/','recurringPrograms':[{'registrationUrl':'https://example.org/classes','price':{'sourceUrl':'https://other.org/fees'}}]};self.assertEqual(program_updates.source_urls(row),['https://example.org/classes','https://example.org/'])
 def test_program_queue_skips_empty_records_and_reaches_structured_programs(self):
  import catalog
  catalog.initialize(worker.database)
  with worker.database() as db:
   for index in range(5):db.execute('INSERT INTO catalog_checks VALUES(?,?,?,?,?)',('prov-'+str(index),'x','h',index,json.dumps({'provider':{'id':'prov-'+str(index)}})))
  client=Mock();client.existing_provider.side_effect=lambda id:{'id':id,'name':'Example','website':'https://example.org/','recurringPrograms':[{'id':'p','registrationUrl':'https://example.org/classes'}] if id=='prov-4' else []}
  board=Mock();board.call.return_value={'id':'child','identifier':'NAR-CHECK'};issue={'id':'queue','projectId':'project','title':'Program queue'}
  result=portfolio.program_queue(issue,board,self.config,Mock(),worker.database,None,client);self.assertEqual(result['report']['created'],['NAR-CHECK']);self.assertEqual(len(result['report']['checked']),5)
  self.assertEqual(sum(r['status']=='no_existing_structured_programs' for r in result['report']['checked']),4);self.assertIn('Program source: https://example.org/classes',board.call.call_args.args[1]['description'])
 def test_program_queue_gate_off_makes_no_catalog_or_board_calls(self):
  client=Mock();board=Mock();portfolio.program_queue({'projectId':'project'},board,{**self.config,'program_updates_enabled':False},Mock(),worker.database,None,client);client.existing_provider.assert_not_called();board.call.assert_not_called()
 def test_focused_followups_deduplicate_and_keep_root(self):
  growth.initialize(worker.database);report={'gaps':[{'field':'address'}],'reason':'Address is missing.','initial_urls':['https://example.org/'],'focused_pages':[{'url':'https://example.org/contact','sha256':'h','title':'Contact'}]}
  with worker.database() as db:db.execute('INSERT INTO commissioning_checks VALUES(?,?,?)',('entity',0,json.dumps(report)))
  issue={'id':'research','title':'Research','projectId':'project','description':'Evidence followup root: root\nDiscovery campaign: classscout-nyc-v1'}
  first=evidence.queue_focused_research(issue,'entity',Mock(),self.config,worker.database);self.assertIsNotNone(first);self.assertIsNone(evidence.queue_focused_research(issue,'entity',Mock(),self.config,worker.database))
  with worker.database() as db:
   body=json.loads(db.execute('SELECT payload_json FROM company_dispatch').fetchone()[0]);self.assertEqual(db.execute('SELECT root_issue FROM evidence_followups').fetchone()[0],'root')
  self.assertIn('Evidence followup root: root',body['description']);self.assertIn('Evidence followup root: root',pipeline.metadata(issue))
 def test_publication_queue_isolates_one_bad_candidate(self):
  issue={'id':'queue','projectId':'project','title':'Queue'};board=Mock();board.call.side_effect=lambda path:{'id':path.rsplit('/',1)[-1],'companyId':'company','projectId':'project','title':'Research'}
  rows=[{'id':'one','issue_id':'one','name':'One'},{'id':'two','issue_id':'two','name':'Two'}]
  with patch('pipeline.candidates.take',return_value=rows),patch('pipeline.advance',side_effect=[ValueError('conflicting brief'),{'identifier':'NAR-NEXT'}]):result=pipeline.run_queue(issue,board,self.config,Mock(),worker.database,None)
  self.assertIn('NAR-NEXT',result['markdown'])

class FreshPreparationTests(unittest.TestCase):
 def setUp(self):self.h=test_automatic.AutomaticTests();self.h.setUp()
 def tearDown(self):self.h.tearDown()
 def test_expired_automatic_publication_fetches_and_prepares_again(self):
  s,body,proof,page,ph=self.h.publication();page['images']=proof['image_candidates']
  with worker.database() as db:
   db.execute("UPDATE publication_packets SET created_at='2020-01-01T00:00:00+00:00'");db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('s',page['url'],'Keylab',page['sha256'],'now'));db.execute('INSERT INTO facts VALUES(?,?,?,?,?)',('a'*32,'address','94 Luquer St','at 94 Luquer St','s'))
  prepared={'gateResult':{'approved':True},'resolvedDraft':{'draft':body['draftPayload'],'adapterVersion':'test'},'entityKind':'provider','mediaResult':body['mediaResult']};s[3].call.return_value=prepared
  with patch('publishing.request_review',return_value={'stage':'new_review'}) as review:result=self.h.run_publication(s)
  self.assertEqual(result['stage'],'new_review');self.assertEqual(s[3].call.call_args.args[0],'/api/content-intelligence/prepare-review');self.assertEqual(review.call_args.args[5]['renewal_of'],ph)
  with worker.database() as db:self.assertEqual(db.execute('SELECT status FROM publication_packets WHERE packet_hash=?',(ph,)).fetchone()[0],'superseded')
 def test_expired_refresh_rechecks_baseline_and_source_before_write(self):
  s=self.h.scenario()
  with patch('refresh.offer_review',return_value={'stage':'prepared'}):self.h.run_refresh(s)
  with worker.database() as db:db.execute("UPDATE refresh_packets SET status='awaiting_approval',created_at=0")
  # The old reviewed contact has changed. Fresh evidence now proposes no correction.
  s[6][0]['phone']='212-555-0199';s[6][0]['email']='info@example.org'
  result=self.h.run_refresh(s);self.assertEqual(result['stage'],'refresh_no_change');s[4].apply.assert_not_called()
  with worker.database() as db:self.assertEqual(db.execute('SELECT status FROM refresh_packets').fetchone()[0],'superseded')

if __name__=='__main__':unittest.main()
