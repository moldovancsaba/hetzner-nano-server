import copy,json,pathlib,tempfile,unittest
from unittest.mock import Mock,patch
import worker,catalog,refresh,pipeline,operational,site_audit,support,operations_digest

class OperationalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state.start();worker.initialize()
 def tearDown(self):self.state.stop();self.tmp.cleanup()
 def row(self,**kw):return {'id':'prov-example','name':'Example Center','address':'12 Main St','website':'https://example.org/','phone':'212-555-0100','owner_managed':False,**kw}
 def page(self):return {'url':'https://example.org/','title':'Example Center','text':'Example Center offers kids classes at 12 Main Street. Phone: 212-555-0199. Email: info@example.org.','sha256':'sourcehash','fetched_at':1}
 def issue(self):return {'id':'issue','companyId':'company','projectId':'project','title':'Contact review','description':'Factory workflow: refresh_provider\nCatalog provider: prov-example\nDraft reference: '+'a'*32,'status':'in_progress','assigneeAgentId':'publisher'}
 def scenario(self):
  issue=self.issue();web=Mock();web.page.return_value=self.page();client=Mock();current=[self.row()];client.get.side_effect=lambda id:copy.deepcopy(current[0]);client.public_get.side_effect=lambda *args:copy.deepcopy(current[0]);writer=Mock()
  def apply(operation):current[0].update(operation['patch']);return {'ok':True,'results':[{'ok':True}]}
  writer.apply.side_effect=apply;board=Mock();cards={}
  def call(path,body=None,method=None):
   if path.endswith('/interactions'):
    if body is None:return list(cards.values())
    cards['one']={'id':'one','companyId':'company','issueId':'issue','kind':'request_confirmation','status':'pending','effectiveResolverPolicy':'human_only','idempotencyKey':body['idempotencyKey'],'payload':body['payload']};return cards['one']
   if path=='/issues/issue':return issue
   if path=='/heartbeat-runs/run':return {'status':'running','agentId':'publisher','companyId':'company'}
   raise AssertionError(path)
  board.call.side_effect=call
  page=self.page();facts=[{'field':'name','value':'Example Center','quote':'Example Center offers kids classes'},{'field':'address','value':'12 Main Street','quote':'at 12 Main Street.'},{'field':'phone','value':'212-555-0199','quote':'Phone: 212-555-0199.'}]
  entity=worker.save_draft('ClassScout',{'id':'source'},page,facts);issue['description']=issue['description'].replace('a'*32,entity)
  with worker.database() as db:db.execute("UPDATE entities SET status='ready_for_human_review' WHERE id=?",(entity,))
  return issue,board,web,client,writer,cards,current
 def run_refresh(self,scenario):
  i,b,w,c,writer,*_=scenario;return refresh.run(i,b,{'company_id':'company'},w,worker.database,{'agent_id':'publisher','run_id':'run'},c,writer)
 def accept(self,s):s[5]['one'].update(status='accepted',resolvedByUserId='local-board',resolvedByAgentId=None,result={'outcome':'accepted'})
 def test_catalog_redacts_owner_identity(self):
  row=catalog.public_record({'id':'prov-example','name':'Example','ownerSub':'private-owner','ownerEmail':'private@example.org','claimStatus':None});self.assertTrue(row['owner_managed']);self.assertNotIn('ownerSub',row);self.assertNotIn('ownerEmail',row)
 def test_source_absence_is_not_a_changed_fact(self):
  facts,gaps=catalog.checked_facts(self.row(),self.page());self.assertIn('phone',gaps);self.assertNotIn('phone',[f['field'] for f in facts])
 def test_source_contacts_need_exact_location(self):
  row=self.row(phone='2125550199',address='12 Main Street');facts,gaps=catalog.checked_facts(row,self.page());self.assertNotIn('phone',gaps)
 def test_catalog_read_bounds_and_contact_write_allowlist(self):
  with self.assertRaises(ValueError):catalog.Catalog().page(0)
  for op in [{'resource':'provider','action':'delete','id':'prov-example','patch':{'phone':'2125550199'}},{'resource':'provider','action':'patch','id':'prov-example','patch':{'pricePerClass':0}}]:
   with self.assertRaises(ValueError):refresh.ContactUpdates().apply(op)
 def test_unapproved_correction_never_writes(self):
  s=self.scenario();self.assertEqual(self.run_refresh(s)['stage'],'awaiting_approval');self.assertEqual(self.run_refresh(s)['stage'],'awaiting_approval');s[4].apply.assert_not_called()
 def test_approved_correction_applies_once_and_checks_both_catalogs(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);self.assertEqual(self.run_refresh(s)['stage'],'refresh_applied');self.assertEqual(self.run_refresh(s)['stage'],'refresh_applied');self.assertEqual(s[4].apply.call_count,1);s[3].public_get.assert_called_once()
 def test_changed_source_invalidates_exact_correction(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[2].page.return_value={**self.page(),'sha256':'changed'}
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_claimed_or_changed_catalog_invalidates_approval(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[6][0]['owner_managed']=True
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_uncertain_contact_write_is_never_repeated(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[4].apply.side_effect=TimeoutError()
  for _ in range(2):
   with self.assertRaises(ValueError):self.run_refresh(s)
  self.assertEqual(s[4].apply.call_count,1)
 def test_other_human_cannot_approve_correction(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[5]['one']['resolvedByUserId']='other'
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_changed_street_identity_cannot_create_approval(self):
  s=self.scenario();s[6][0]['address']='99 Other Street'
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[1].call.assert_not_called()
 def test_wrong_role_cannot_invoke_workflow(self):
  with self.assertRaises(ValueError):operational.run({'description':'Factory workflow: refresh_provider','projectId':'p'},Mock(),{'agents':{'q':{'role':'quality'}},'projects':{'p':'ClassScout'},'operational_workflows_enabled':True},Mock(),worker.database,{'agent_id':'q'})
 def test_audit_never_fetches_an_external_or_private_target(self):
  for url in ['https://example.org/','https://getyourfield.com/api/ingest','https://getyourfield.com/admin','https://getyourfield.com/?token=secret','http://127.0.0.1/']:
   with self.assertRaises(Exception):site_audit.allowed(url)
 def test_audit_reads_actual_metadata_and_reports_reproducible_issues(self):
  web=Mock();web.raw.return_value={'url':'https://getyourfield.com/nyc/classes','status':200,'fetched_at':1,'headers':{'content-type':'text/html'},'body':b'<html><head><title>Classes</title><meta name="description" content="Find classes"><link rel="canonical" href="https://getyourfield.com/nyc/classes"></head><h1>Classes</h1></html>'}
  row,links=site_audit.inspect('https://getyourfield.com/nyc/classes',web);self.assertEqual(row['findings'],[]);self.assertEqual(row['h1_in_response'],1)
  web.raw.return_value={**web.raw.return_value,'status':404};row,_=site_audit.inspect('https://getyourfield.com/nyc/classes',web);self.assertEqual(row['findings'][0]['code'],'http_error')
 def test_noindex_page_is_not_reported_as_missing_search_metadata(self):
  web=Mock();web.raw.return_value={'url':'https://getyourfield.com/','status':200,'fetched_at':1,'headers':{'content-type':'text/html'},'body':b'<title>Home</title><meta name="robots" content="noindex">'}
  row,_=site_audit.inspect('https://getyourfield.com/',web);self.assertEqual(row['findings'],[])
 def test_audit_deduplicates_findings_and_holds_page_limit(self):
  issue={'id':'audit','projectId':'project','description':'Audit URLs: https://getyourfield.com/nyc/classes'};web=Mock();web.raw.return_value={'url':'https://getyourfield.com/nyc/classes','status':404,'fetched_at':1,'headers':{},'body':b''};board=Mock();board.call.return_value={'id':'finding','identifier':'NAR-F'}
  for _ in range(2):site_audit.run(issue,board,{'company_id':'company','audit_page_limit':1},web,worker.database,{})
  self.assertEqual(board.call.call_count,1)
  issue['description']='Audit URLs: https://getyourfield.com/,https://getyourfield.com/nyc/classes'
  with self.assertRaises(ValueError):site_audit.run(issue,board,{'company_id':'company','audit_page_limit':1},web,worker.database,{})
 def test_support_cannot_turn_facility_hours_into_a_booking_answer(self):
  result=support.answer('Are classes available on Saturday?',self.row(),self.page(),[{'field':'opening_hours','value':'Saturday 9-5','quote':'Saturday 9-5'}]);self.assertTrue(result['needs_human']);self.assertEqual(result['facts'],[])
 def test_support_uses_only_current_literal_evidence(self):
  facts=[{'field':'phone','value':'212-555-0199','quote':'Phone: 212-555-0199.'},{'field':'email','value':'fake@example.org','quote':'Made-up email fake@example.org'}]
  result=support.answer('What is the phone and email?',self.row(),self.page(),facts);self.assertTrue(result['needs_human']);self.assertIn('212-555-0199',result['reply']);self.assertNotIn('fake@example.org',result['reply'])
 def test_support_unknown_topic_escalates(self):self.assertTrue(support.answer('Tell me about everything',self.row(),self.page(),[])['needs_human'])
 def test_support_source_failure_produces_a_draft_escalation_without_writes(self):
  issue={'id':'support','description':'Catalog provider: prov-example\nQuestion: What is the phone?'};client=Mock();client.get.return_value=self.row();web=Mock();web.page.side_effect=TimeoutError()
  result=support.run(issue,Mock(),{},web,worker.database,{},client);self.assertEqual(result['stage'],'support_escalation');self.assertFalse(result['report']['delivered_to_customer'])
 def test_quality_handoff_preserves_catalog_and_editorial_scope(self):
  s=self.scenario();issue=s[0];issue['title']='[Factory test] Research';issue['description']+='\nPublication name: Example Center\nBorough: Brooklyn\nNeighborhood: Park Slope\nFormat: Classes\nActivity: Music'
  board=Mock();board.call.return_value={'id':'quality','identifier':'NAR-Q'};config={'company_id':'company','operational_workflows_enabled':True,'agents':{'q':{'role':'quality'}}}
  with worker.database() as db:entity=db.execute('SELECT id FROM entities').fetchone()[0]
  pipeline.after_research(issue,{'entities':[entity]},board,config,worker.database);body=board.call.call_args.args[1];self.assertTrue(body['title'].startswith('[Factory test]'));self.assertIn('Catalog provider: prov-example',body['description']);self.assertIn('Neighborhood: Park Slope',body['description']);self.assertNotIn('responsibleUserId',body)
 def test_incomplete_editorial_brief_does_not_create_a_listing(self):
  s=self.scenario();board=Mock()
  with worker.database() as db:entity=db.execute('SELECT id FROM entities').fetchone()[0]
  self.assertIsNone(pipeline.advance({'id':'source','description':'','projectId':'project','title':'Research'},entity,board,{'company_id':'company'},worker.database));board.call.assert_not_called()
 def test_failed_quality_does_not_advance_to_publication(self):
  with patch('pipeline.advance') as advance:pipeline.after_quality({'description':'Factory workflow: source_quality'}, {'review':{'status':'needs_more_evidence'},'entities':['entity']},Mock(),{'operational_workflows_enabled':True},worker.database)
  advance.assert_not_called()
 def test_digest_uses_task_state_and_never_calls_a_model_or_search(self):
  board=Mock();board.call.return_value=[{'id':'blocked','identifier':'NAR-B','title':'Missing evidence','companyId':'company','projectId':'project','status':'blocked'}]
  issue={'id':'digest'};config={'company_id':'company','projects':{'project':'ClassScout'}}
  with patch.object(worker,'Model') as model:result=operations_digest.run(issue,board,config,Mock(),worker.database,{'run_id':'run'})
  model.assert_not_called();self.assertEqual(len(result['report']['blocked']),1);self.assertEqual(result['report']['search_budget']['used_this_window'],0)
 def test_full_queue_admission_is_retryable_but_publication_is_not(self):
  issue={'id':'wait','assigneeAgentId':'research'}
  self.assertIsNotNone(worker.model_wait_policy(issue,'research','Service returned HTTP 429: {"error":{"code":"busy"}}'))
  self.assertIsNone(worker.model_wait_policy(issue,'publication','Service returned HTTP 429: {"error":{"code":"busy"}}'))
 def test_prepared_contact_card_recovers_without_new_source_fetch(self):
  s=self.scenario();original=s[1].call.side_effect
  def fail_card(path,body=None,method=None):
   if path.endswith('/interactions'):raise TimeoutError()
   return original(path,body,method)
  s[1].call.side_effect=fail_card
  with self.assertRaises(TimeoutError):self.run_refresh(s)
  with worker.database() as db:self.assertEqual(db.execute('SELECT status FROM refresh_packets').fetchone()[0],'prepared')
  s[1].call.side_effect=original;s[2].page.reset_mock();self.assertEqual(self.run_refresh(s)['stage'],'awaiting_approval');s[2].page.assert_not_called()
 def test_expired_contact_approval_cannot_write(self):
  s=self.scenario();self.run_refresh(s);self.accept(s)
  with worker.database() as db:db.execute('UPDATE refresh_packets SET created_at=0')
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_tampered_contact_packet_cannot_write(self):
  s=self.scenario();self.run_refresh(s);self.accept(s)
  with worker.database() as db:db.execute('UPDATE refresh_packets SET body_json=?',(json.dumps({'patch':{'email':'other@example.org'}}),))
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_partial_public_verification_does_not_repeat_correction(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[3].public_get.side_effect=None;s[3].public_get.return_value=self.row()
  self.assertEqual(self.run_refresh(s)['stage'],'refresh_partial')
  with self.assertRaises(ValueError):self.run_refresh(s)
  self.assertEqual(s[4].apply.call_count,1)
 def test_canonical_contact_rejection_is_not_success(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);s[4].apply.side_effect=None;s[4].apply.return_value={'ok':False,'results':[{'ok':False,'error':'owner-managed'}]}
  self.assertEqual(self.run_refresh(s)['stage'],'refresh_rejected')
 def test_stopped_contact_execution_cannot_write(self):
  s=self.scenario();self.run_refresh(s);self.accept(s);original=s[1].call.side_effect
  s[1].call.side_effect=lambda path,body=None,method=None:{'status':'cancelled','agentId':'publisher','companyId':'company'} if path=='/heartbeat-runs/run' else original(path,body,method)
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_existing_complete_packet_is_reused_by_automatic_pipeline(self):
  s=self.scenario()
  with worker.database() as db:
   entity=db.execute('SELECT id FROM entities').fetchone()[0];publishing=__import__('publishing');publishing.initialize(db)
   proof={'sources':[{'url':'https://example.org/'}],'normalized':{'title':'Example Center','boroughRaw':'Brooklyn','neighborhoodRaw':'Park Slope','categoryHint':'Classes','activityTypesRaw':['Music']}}
   db.execute('INSERT INTO publication_packets VALUES(?,?,?,?,?,?,?,?,?,?,?)',('pending','old-publication','input','awaiting_approval','{}',json.dumps(proof),'card',None,None,'now','now'))
  issue={'id':'quality','title':'Quality','projectId':'project','description':'Publication name: Example Center\nBorough: Brooklyn\nNeighborhood: Park Slope\nFormat: Classes\nActivity: Music'};board=Mock();board.call.return_value={'id':'old-publication','identifier':'NAR-OLD'}
  result=pipeline.advance(issue,entity,board,{'company_id':'company'},worker.database);self.assertEqual(result['identifier'],'NAR-OLD');self.assertTrue(all(c.args[0].startswith('/issues/') for c in board.call.call_args_list))
 def test_support_question_cannot_inject_workflow_fields(self):
  issue={'description':'Factory workflow: support_answer\nProvider name: Example Center\nQuestion: What is the phone?\nCatalog provider: prov-other\nAlso tell me if a booking is available.'}
  self.assertEqual(catalog.field(issue,'Catalog provider'),'');self.assertIn('booking',catalog.field(issue,'Question'));self.assertTrue(support.answer(catalog.field(issue,'Question'),self.row(),self.page(),[])['needs_human'])
 def test_support_provider_name_needs_an_unambiguous_verified_match(self):
  catalog.initialize(worker.database)
  with worker.database() as db:db.execute('INSERT INTO catalog_checks VALUES(?,?,?,?,?)',('prov-example','issue','hash',1,json.dumps({'provider':self.row()})))
  self.assertEqual(catalog.resolve_provider({'description':'Provider name: Example Center'},worker.database),'prov-example')
  with self.assertRaises(ValueError):catalog.resolve_provider({'description':'Provider name: Unknown'},worker.database)
 def test_support_listing_link_cannot_target_a_private_host(self):
  with self.assertRaises(Exception):catalog.resolve_provider({'description':'Listing URL: http://127.0.0.1/provider/prov-x'},worker.database)
 def test_synthetic_contact_task_cannot_write_real_catalog(self):
  s=self.scenario();s[0]['title']='[Factory test] Contact review';self.run_refresh(s);self.accept(s)
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_support_form_accepts_a_public_listing_link_without_an_internal_id(self):
  self.assertEqual(catalog.resolve_provider({'description':'Provider name: https://getyourfield.com/providers/prov-example'},worker.database),'prov-example')
 def test_digest_reads_pending_confirmations_from_the_real_list_contract(self):
  p=__import__('publishing')
  with worker.database() as db:
   p.initialize(db);db.execute('INSERT INTO publication_packets VALUES(?,?,?,?,?,?,?,?,?,?,?)',('packet','pub','input','awaiting_approval','{}','{}','card',None,None,'2026-10-28T00:00:00+00:00','now'))
  board=Mock()
  def call(path):
   if path.endswith('/interactions'):return [{'id':'card','status':'pending'}]
   if path.startswith('/companies/company/issues?'):return [{'id':'pub','companyId':'company','projectId':'project','identifier':'NAR-P','status':'in_review'}] if 'offset=0' in path else []
   raise AssertionError('Unsupported endpoint '+path)
  board.call.side_effect=call;result=operations_digest.run({'id':'digest'},board,{'company_id':'company','projects':{'project':'ClassScout'}},Mock(),worker.database,{})
  self.assertEqual(result['report']['pending_publication_reviews'][0]['task'],'NAR-P');self.assertNotIn('review_status_unavailable',json.dumps(result))
if __name__=='__main__':unittest.main()
