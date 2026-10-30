import copy,json,pathlib,tempfile,time,unittest
from unittest.mock import patch
import quality_gate as q,worker,publishing,refresh
import test_operations
import test_publishing

class AutomaticTests(unittest.TestCase):
 def setUp(self):
  self.settings=patch.object(q,'runtime_settings',return_value={'version':'test','settings':{}});self.settings.start();self.helper=test_operations.OperationalTests();self.helper.setUp();self.config={'company_id':'company','projects':{'project':'ClassScout'},'automatic_quality_gate':{'enabled':True,'daily_write_limit':10}}
 def tearDown(self):self.helper.tearDown();self.settings.stop()
 def scenario(self):
  s=self.helper.scenario();s[2].page.return_value['fetched_at']=time.time();return s
 def run_refresh(self,s):return refresh.run(s[0],s[1],self.config,s[2],worker.database,{'agent_id':'publisher','run_id':'run'},s[3],s[4])
 def publication(self):
  helper=test_publishing.PublishingTests();s=helper.scenario(approval=False);i,b,w,c,card=s;page={**helper.page(),'fetched_at':time.time()};w.page.return_value=page
  facts=[{'field':'address','value':'94 Luquer St','quote':'at 94 Luquer St'}];normalized,proof=publishing.normalize_sources(helper.brief(),[page],facts);proof['image_candidates']=['https://example.org/image.jpg']
  draft={'id':'prov-example','name':'Keylab','category':'Classes','borough':'Brooklyn','neighborhood':'Carroll Gardens','address':'94 Luquer St','shortDescription':normalized['descriptionFacts'][0],'longDescription':' '.join(normalized['descriptionFacts']),'activityTypes':['Music'],'website':page['url'],'phone':'','email':'','ageMinMonths':108,'ageMaxMonths':215,'pricePerClass':42,'price':proof['price'],'claimStatus':'unclaimed','image':'https://cdn.example.org/image.jpg','recurringPrograms':[{'daysOfWeek':x['daysOfWeek'],'timeText':x['timeText'],'ageMinMonths':x['age_min']*12,'ageMaxMonths':x['age_max']*12+11,'price':proof['price']} for x in proof['schedules']]}
  body={'entityKind':'provider','draftPayload':draft,'mediaResult':{'status':'ready','qualification':{'status':'accepted','provenance':'authoritative'},'originalUrl':proof['image_candidates'][0],'sourceDocumentUrl':page['url'],'uploadedUrl':draft['image'],'contentHash':'imagehash'}};ph=publishing.sha({'body':body,'proof':proof})
  with worker.database() as db:
   db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?)',('a'*32,'ClassScout',page['url'],'Keylab','ready_for_human_review','issue',publishing.stamp()))
   db.execute('UPDATE publication_packets SET body_json=?,proof_json=?,packet_hash=?',(json.dumps(body),json.dumps(proof),ph))
  return s,body,proof,page,ph
 def run_publication(self,s):return publishing.run(s[0],s[1],self.config,s[2],worker.database,s[3],execution={'agent_id':'pubagent','run_id':'run'})
 def test_verified_contact_writes_without_human_acceptance_once(self):
  s=self.scenario();self.assertEqual(self.run_refresh(s)['stage'],'refresh_applied');self.run_refresh(s);self.assertEqual(s[4].apply.call_count,1);self.assertFalse(s[5])
 def test_non_classscout_does_not_auto_authorize(self):
  self.assertFalse(q.enabled(self.config,{'projectId':'other'}))
 def test_owner_managed_cannot_auto_update(self):
  s=self.scenario();s[6][0]['owner_managed']=True
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_unknown_response_never_retries(self):
  s=self.scenario();s[4].apply.side_effect=TimeoutError()
  for _ in range(2):
   with self.assertRaises(ValueError):self.run_refresh(s)
  self.assertEqual(s[4].apply.call_count,1)
 def test_factory_tests_cannot_auto_write(self):
  s=self.scenario();s[0]['title']='[Factory test] Contact'
  with self.assertRaises(ValueError):self.run_refresh(s)
  s[4].apply.assert_not_called()
 def test_content_is_grounded_and_existing_editorial_copy_preserved(self):
  s=self.scenario();s[2].page.return_value['text']+=' Music in Brooklyn, Carroll Gardens.';s[6][0].update(borough='Brooklyn',neighborhood='Carroll Gardens',activityTypes=['Music'],shortDescription='Editorial description')
  self.run_refresh(s);body=s[4].apply.call_args.args[0]['patch'];self.assertNotIn('shortDescription',body);self.assertIn('longDescription',body);self.assertIn('12 Main St',body['longDescription'])
 def test_missing_location_does_not_invent_content(self):
  self.assertEqual(q.descriptions(self.helper.row(),self.helper.page()),{})
 def test_auto_publication_runs_full_gate_and_no_human_confirmation(self):
  s,body,proof,page,ph=self.publication();result=self.run_publication(s);self.assertEqual(result['stage'],'published');self.assertEqual(result['final_status'],'done');self.run_publication(s);self.assertEqual(s[3].call.call_count,1);self.assertEqual(s[4]['status'],'pending')
 def test_invented_copy_fails_despite_other_valid_fields(self):
  s,body,proof,page,ph=self.publication();body['draftPayload']['longDescription']+=' Award winning and free.'
  with self.assertRaises(ValueError):q.check_publication(worker.database,ph,s[0],body,proof,[page])
 def test_facility_hours_or_modified_age_cannot_pass(self):
  s,body,proof,page,ph=self.publication();body['draftPayload']['recurringPrograms'][0]['timeText']='9am to 6pm'
  with self.assertRaises(ValueError):q.check_publication(worker.database,ph,s[0],body,proof,[page])
 def test_unqualified_image_cannot_pass(self):
  s,body,proof,page,ph=self.publication();body['mediaResult']['qualification']['status']='rejected'
  with self.assertRaises(ValueError):q.check_publication(worker.database,ph,s[0],body,proof,[page])
 def test_changed_source_cannot_auto_publish(self):
  s,*_=self.publication();s[2].page.return_value['sha256']='changed'
  with self.assertRaises(ValueError):self.run_publication(s)
  s[3].call.assert_not_called()
 def test_rejected_human_packet_is_not_overridden(self):
  s,*_=self.publication();s[4]['status']='rejected';self.assertEqual(self.run_publication(s)['stage'],'rejected');s[3].call.assert_not_called()
 def test_stale_source_check_is_held(self):
  s,body,proof,page,ph=self.publication();page['fetched_at']=1
  with self.assertRaises(ValueError):q.check_publication(worker.database,ph,s[0],body,proof,[page])
 def test_daily_cap_and_consumed_authorizations(self):
  q.record(worker.database,'first','content_update',{'valid':True});q.record(worker.database,'second','content_update',{'valid':True});config={**self.config,'automatic_quality_gate':{'daily_write_limit':1}}
  with worker.database() as db:q.reserve(db,'first',config)
  for ph in ['first','second']:
   with self.assertRaises(ValueError):
    with worker.database() as db:q.reserve(db,ph,config)
 def test_scope_and_contact_injection_rejected(self):
  s=self.scenario();q.initialize(worker.database)
  with self.assertRaises(ValueError):q.check_refresh(worker.database,'bad',{'patch':{'email':'fake@example.org'}},{'facts':[]},s[6][0],s[2].page.return_value)

 def test_client_hidden_music_does_not_block_shared_catalog_intake(self):
  s,body,proof,page,ph=self.publication();q.runtime_settings.return_value={'version':'client','settings':{'disabledActivityTypes':['Music']}}
  self.assertEqual(self.run_publication(s)['stage'],'published');q.runtime_settings.assert_not_called()
 def test_visibility_honors_region_category_and_allowlist(self):
  d={'borough':'Brooklyn','activityTypes':['Music']}
  for settings in [{'disabledRegions':['Brooklyn']},{'disabledBrowseCategories':['classes']},{'enabledActivityTypes':['Swimming']},{'cityEnabled':False}]:self.assertFalse(q.visible_by_settings(d,settings))
 def test_dark_activity_requires_explicit_activation(self):
  self.assertFalse(q.visible_by_settings({'activityTypes':['Capoeira']},{}));self.assertTrue(q.visible_by_settings({'activityTypes':['Capoeira']},{'enabledActivityTypes':['Capoeira']}))
 def test_saved_hidden_reconciles_core_without_another_write(self):
  s,body,proof,page,ph=self.publication();s[3].verify_catalog.return_value={'verified':True,'private_verified':True,'public_verified':True,'origin':publishing.ClassScout.BASE}
  with worker.database() as db:db.execute("UPDATE publication_packets SET status='saved_hidden',receipt_json=?",(json.dumps({'privateVerification':{'verified':True}}),))
  self.assertEqual(self.run_publication(s)['stage'],'published');s[3].call.assert_not_called();s[3].verify_catalog.assert_called_once()
 def test_partial_core_reconciliation_cannot_publish_on_mismatch(self):
  s,*_=self.publication();s[3].verify_catalog.return_value={'verified':False,'origin':publishing.ClassScout.BASE}
  with worker.database() as db:db.execute("UPDATE publication_packets SET status='partial',receipt_json='{}'")
  with self.assertRaises(ValueError):self.run_publication(s)
  s[3].call.assert_not_called()
 def test_client_or_unknown_origin_cannot_masquerade_as_core_receipt(self):
  s,*_=self.publication();s[3].verify_catalog.return_value={'verified':True,'origin':'https://getyourfield.com'}
  with worker.database() as db:db.execute("UPDATE publication_packets SET status='partial',receipt_json='{}'")
  with self.assertRaises(ValueError):self.run_publication(s)
  s[3].call.assert_not_called()
 def test_missing_core_verification_keeps_uncertain_outcome(self):
  s,*_=self.publication();s[3].verify_catalog.side_effect=TimeoutError()
  with worker.database() as db:db.execute("UPDATE publication_packets SET status='partial',receipt_json='{}'")
  with self.assertRaises(ValueError):self.run_publication(s)
  s[3].call.assert_not_called()
 def test_missing_independent_review_is_held(self):
  s,body,proof,page,ph=self.publication()
  with worker.database() as db:db.execute("UPDATE entities SET status='needs_more_evidence'")
  with self.assertRaises(ValueError):self.run_publication(s)
  s[3].call.assert_not_called()

 def verified_transport(self,body,private=None,public=None):
  from unittest.mock import MagicMock
  client=publishing.ClassScout();private=body['draftPayload'] if private is None else private;public=body['draftPayload'] if public is None else public
  opener=MagicMock();opener.open.return_value.__enter__.return_value.read.return_value=json.dumps({'provider':public}).encode()
  with patch.object(client,'existing_provider',return_value=private),patch('publishing.urllib.request.build_opener',return_value=opener):result=client.verify_catalog(body)
  self.assertTrue(opener.open.call_args.args[0].startswith('https://classscout.ai/api/public/providers/'))
  return result
 def test_read_only_core_verifier_confirms_exact_private_and_public_data(self):
  _,body,*_=self.publication();self.assertTrue(self.verified_transport(body)['verified'])
 def test_read_only_core_verifier_rejects_private_price_drift(self):
  _,body,*_=self.publication();private={**body['draftPayload'],'pricePerClass':999};self.assertFalse(self.verified_transport(body,private=private)['verified'])
 def test_read_only_core_verifier_rejects_public_identity_mismatch(self):
  _,body,*_=self.publication();public={**body['draftPayload'],'id':'prov-other'};self.assertFalse(self.verified_transport(body,public=public)['verified'])
 def test_the_public_page_never_shows_an_em_dash_so_the_verifier_compares_what_is_served(self):
  _,body,*_=self.publication();draft=dict(body['draftPayload'],name='Kids Dance \u2014 Brooklyn Basement Dance Co.',shortDescription='Kids Dance \u2014 Brooklyn Basement Dance Co. offers dance classes.')
  body={**body,'draftPayload':draft};served={**draft,'name':'Kids Dance, Brooklyn Basement Dance Co.','shortDescription':'Kids Dance, Brooklyn Basement Dance Co. offers dance classes.'}
  self.assertTrue(self.verified_transport(body,private=draft,public=served)['verified'])
  self.assertFalse(self.verified_transport(body,private=draft,public={**served,'name':'Kids Dance, Another Studio'})['verified'])
  self.assertFalse(self.verified_transport(body,private=draft,public=draft)['verified'],'the stored text with the dash is never what the public page serves')
 def test_read_time_text_mirrors_the_classscout_guard(self):
  r=publishing.read_time_text
  self.assertEqual(r('A \u2014 B'),'A, B');self.assertEqual(r('Done. \u2014 Next'),'Done. Next');self.assertEqual(r('\u2014'),'\u2013')
  self.assertEqual(r('\u2014 A'),'A');self.assertEqual(r('A \u2014'),'A');self.assertEqual(r('A\u2014B\u2014C'),'A, B, C')
  self.assertEqual(r('A \u2013 B'),'A \u2013 B');self.assertEqual(r('plain'),'plain');self.assertIsNone(r(None));self.assertEqual(r(5),5)
 def test_core_listing_links_resolve_without_client_filter(self):
  import catalog
  self.assertEqual(catalog.resolve_provider({'description':'Listing URL: https://classscout.ai/providers/prov-keylab'},worker.database),'prov-keylab')
