import copy,json,time,unittest
from unittest.mock import Mock,MagicMock,patch
import worker,evidence,formats,publishing,quality_gate,padel,business_metrics
import test_operations,test_publishing
class DeliveryTests(unittest.TestCase):
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def page(self,url='https://example.org/',text='Example Center Music classes at 12 Main Street in Brooklyn.',title='Example Center'):
  return {'url':url,'text':text,'title':title,'sha256':publishing.sha(text),'fetched_at':time.time(),'links':[]}
 def test_street_matches_ignore_city_zip_and_abbreviations(self):
  self.assertTrue(evidence.address_matches('1295 Allerton Avenue, Bronx, NY 10469','Visit 1295 Allerton Ave.'));self.assertFalse(evidence.address_matches('1295 Allerton Ave','11295 Allerton Ave'))
 def test_queens_hyphenated_building_number_is_exact(self):
  self.assertTrue(evidence.address_matches('32-32 Steinway Street, Queens','32-32 Steinway St., 3rd floor'));self.assertFalse(evidence.address_matches('32-32 Steinway Street','32 Steinway Street'))
 def test_branch_rejects_non_street_and_different_location(self):
  for address in ['Queens, NY','99 Other Street']:
   web=Mock();web.page.return_value=self.page()
   with self.assertRaises(ValueError):evidence.branch_page({'name':'Example Center','address':address},'https://example.org/',[],web)
 def test_branch_contacts_do_not_cross_locations(self):
  text='Example Center\n12 Main Street\nPhone 212-555-0100\n\n\n\n\n\n\n\n\n\n\n99 Other Road\nPhone 718-555-0199';web=Mock();web.page.return_value=self.page(text=text)
  _,facts,proof=evidence.branch_page({'name':'Example Center','address':'12 Main St, Brooklyn'},'https://example.org/',[],web);self.assertIn('212-555-0100',[f['value'] for f in facts]);self.assertNotIn('718-555-0199',[f['value'] for f in facts]);self.assertEqual(proof['scope'],'one physical branch')
 def test_crawl_only_same_host_and_four_requests(self):
  web=Mock()
  def page(url):return {**self.page(url),'links':['https://other.example/contact','http://127.0.0.1/contact','/contact','/about','/locations','/studios']}
  web.page.side_effect=page;pages=evidence.crawl('https://example.org/start',web);self.assertLessEqual(web.page.call_count,4);self.assertTrue(all(p['url'].startswith('https://example.org/') for p in pages))
 def recovery(self,text):
  page=self.page(text=text);id=worker.save_draft('ClassScout',{'id':'source'},page,[{'field':'name','value':'Example Center','quote':'Example Center'}]);web=Mock();web.page.return_value=page
  with worker.database() as db:entity=dict(db.execute('SELECT * FROM entities WHERE id=?',(id,)).fetchone())
  return entity,web
 def test_missing_address_is_recovered_with_source_provenance(self):
  entity,web=self.recovery('Example Center at 12 Main Street.');result=evidence.recover(entity,worker.database,web);self.assertEqual(result['added_fields'],['address'])
  with worker.database() as db:fact=db.execute("SELECT f.value,s.url FROM facts f JOIN sources s ON s.id=f.source_id WHERE field='address'").fetchone();self.assertEqual(fact['value'],'12 Main Street');self.assertEqual(fact['url'],'https://example.org/')
 def test_multiple_locations_are_not_guessed(self):
  entity,web=self.recovery('Example Center at 12 Main Street and 99 Other Road.');self.assertEqual(evidence.recover(entity,worker.database,web)['added_fields'],[])
 def test_recovery_selects_exact_known_branch_only(self):
  entity,web=self.recovery('Example Center at 12 Main Street and 99 Other Road.');result=evidence.recover(entity,worker.database,web,{'name':'Example Center','address':'99 Other Rd, NY'});self.assertEqual(result['added_fields'],['address'])
 def test_name_recovery_requires_literal_brand_title_and_domain(self):
  self.assertEqual(evidence.names(self.page('https://examplecenter.org/',text='Welcome to Example Center',title='Home | Example Center')),['Example Center']);self.assertEqual(evidence.names(self.page('https://directory.org/',text='Example Center',title='Example Center')),[])
 def test_quality_verifies_recovered_quote_on_its_own_page(self):
  first=self.page('https://example.org/pricing',text='Example Center classes.');other=self.page('https://example.org/contact',text='Example Center at 12 Main Street.');first['links']=['/contact'];id=worker.save_draft('ClassScout',{'id':'source'},first,[{'field':'name','value':'Example Center','quote':'Example Center'}]);web=Mock();web.page.side_effect=lambda u:first if u==first['url'] else other
  with patch.object(worker,'WEB',web):result=worker.quality({'id':'review','description':'Draft reference: '+id},'ClassScout')
  self.assertEqual(result['review']['status'],'ready_for_human_review');self.assertIn(other['url'],result['review']['source_urls'])
 def test_monthly_and_semester_fees_keep_their_units(self):
  for unit in ['month','semester','term']:
   result=formats.price('$150 per '+unit);self.assertEqual(result['amount'],150);self.assertEqual(result['unit'],unit);self.assertIn('per '+unit,formats.price_sentence(result))
 def test_mixed_price_units_require_evidence_resolution(self):
  with self.assertRaises(ValueError):formats.price('$42 per class and $150 per month')
 def test_month_based_ages_keep_exact_bounds(self):
  age=formats.ages('Ages 6-18 months')[0];self.assertEqual(formats.bounds(age),(6,18));s=formats.schedules('Ages 6-18 months - Tuesdays 10:00 am, 45 minutes')[0];self.assertEqual(formats.bounds(s,True),(6,18))
 def test_camps_require_future_dates_and_supported_fee_unit(self):
  text='Camp dates: 2027-06-14 to 2027-06-18. Ages 5-10 - Monday 9:00 am, 360 minutes.';s=formats.schedules(text,'Camps')[0];self.assertEqual(s['startDate'],'2027-06-14');self.assertEqual(formats.price('$350 per week','Camps')['unit'],'week')
  with self.assertRaises(ValueError):formats.schedules('Ages 5-10 - Monday 9:00 am, 360 minutes.','Camps')
  with self.assertRaises(ValueError):formats.schedules(text.replace('2027','2020'),'Camps')
 def test_month_and_camp_normalization_passes_through_real_pipeline(self):
  helper=test_publishing.PublishingTests();brief=helper.brief();page=helper.page();page['text']='Keylab Music classes at 94 Luquer St in Carroll Gardens, Brooklyn. Ages 6-18 months - Tuesdays 10:00 am, 45 minutes. $150 per month.';n,proof=publishing.normalize_sources(brief,[page],[{'field':'address','value':'94 Luquer St','quote':'94 Luquer St'}]);self.assertEqual(proof['price']['unit'],'month');self.assertEqual(formats.bounds(proof['ages'][0]),(6,18));self.assertEqual(proof['price']['amount'],150);self.assertNotIn('$150',' '.join(n['descriptionFacts']))
 def test_padel_wrong_tenant_is_refused(self):
  client=padel.Client()
  with patch.object(client,'call',return_value={'vertical':{'slug':'sportolok'}}):
   with self.assertRaises(ValueError):client.catalog()
 def test_padel_forced_publish_and_raw_patch_are_not_available(self):
  for body in [{'id':'x','patch':{'name':'Fake'}},{'id':'x','forcePublish':True}]:
   with self.assertRaises(ValueError):padel.Client().call('/api/ingest',body)
 def test_padel_maintenance_is_a_read_and_reports_actual_scope(self):
  client=Mock();client.catalog.return_value={'vertical':{'slug':'padel-africa','discovery':{'localities':['Cape Town']}},'catalog':{'total':944,'listings':[],'truncated':True},'triage':{}}
  result=padel.run({'id':'padel','description':'Factory workflow: padel_maintenance'},Mock(),{},Mock(),worker.database,{},client);self.assertEqual(result['report']['catalog_total'],944);self.assertEqual(result['report']['writes'],0);client.call.assert_not_called()
 def test_business_dashboard_distinguishes_checked_from_published(self):
  helper=test_publishing.PublishingTests();publishing.initialize.__name__;worker.initialize()
  with worker.database() as db:publishing.initialize(db)
  result=business_metrics.snapshot(worker.database,{'company_id':'company','automatic_quality_gate':{'daily_write_limit':20}},tasks=[]);self.assertEqual(result['funnel']['published'],0);self.assertIn('does not establish',result['definitions']['source_checked']);self.assertNotIn('sourceText',json.dumps(result));self.assertEqual(result['daily_write_limit'],20)

 def padel_scenario(self):
  issue={'id':'padel-new','companyId':'company','projectId':'padel','title':'Submit a Padel source','description':'Factory workflow: padel_intake\nOfficial source URL: https://example.org/\nProvider name: Example Padel\nCity: Cape Town\nStreet address: 12 Main Street','status':'in_progress','assigneeAgentId':'support'};page=self.page(text='Example Padel at 12 Main Street in Cape Town offers padel courts.');web=Mock();web.page.return_value=page;client=Mock();client.catalog.return_value={'vertical':{'discovery':{'localities':['Cape Town']}},'catalog':{'listings':[]}};client.call.side_effect=lambda path,body:{'cardId':body['id'],'created':True,'state':'DISCOVERED'};board=Mock();board.call.side_effect=lambda p:issue if p.startswith('/issues/') else {'status':'running','agentId':'support','companyId':'company'}
  return issue,board,web,client
 def test_padel_intake_uses_engine_receipt_and_does_not_claim_publication(self):
  i,b,w,c=self.padel_scenario();r=padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c);self.assertEqual(r['stage'],'padel_evidence_accepted');self.assertIn('does not claim',r['markdown']);padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c);self.assertEqual(c.call.call_count,1)
 def test_padel_unknown_write_is_not_replayed(self):
  i,b,w,c=self.padel_scenario();c.call.side_effect=TimeoutError()
  for _ in range(2):
   with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  self.assertEqual(c.call.call_count,1)
 def test_padel_city_outside_vertical_scope_cannot_be_submitted(self):
  i,b,w,c=self.padel_scenario();i['description']=i['description'].replace('Cape Town','New York')
  with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  c.call.assert_not_called()
 def test_padel_duplicate_listing_is_held(self):
  i,b,w,c=self.padel_scenario();c.catalog.return_value['catalog']['listings']=[{'name':'Example Padel'}]
  with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  c.call.assert_not_called()
 def test_fake_padel_receipt_keeps_submission_uncertain(self):
  i,b,w,c=self.padel_scenario();c.call.side_effect=lambda p,body:{'cardId':'wrong-id','created':True}
  with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  with worker.database() as db:self.assertEqual(db.execute('SELECT status FROM padel_packets').fetchone()[0],'uncertain')
 def test_recovery_does_not_bridge_address_lines(self):
  found=[m.group(0) for m in evidence.STREET.finditer('Call 2125550100\n99 Other Road')];self.assertEqual(found,['99 Other Road'])

 def test_month_price_cannot_be_relabelled_as_per_class_by_auto_gate(self):
  import test_automatic
  helper=test_automatic.AutomaticTests();scenario,body,proof,page,ph=helper.publication();page['text']='Keylab Music classes at 94 Luquer St in Carroll Gardens, Brooklyn. Ages 6-18 months - Tuesdays 10:00 am, 45 minutes. $150 per month.';page['fetched_at']=time.time();brief=test_publishing.PublishingTests().brief();n,p=publishing.normalize_sources(brief,[page],[{'field':'address','value':'94 Luquer St','quote':'94 Luquer St'}]);p['image_candidates']=['https://example.org/image.jpg'];draft=body['draftPayload'];draft.update(shortDescription=n['descriptionFacts'][0],longDescription=' '.join(n['descriptionFacts']),ageMinMonths=6,ageMaxMonths=18,pricePerClass=150,price=p['price'],recurringPrograms=[{'daysOfWeek':x['daysOfWeek'],'timeText':x['timeText'],'ageMinMonths':formats.bounds(x,True)[0],'ageMaxMonths':formats.bounds(x,True)[1],'price':p['price']} for x in p['schedules']]);self.assertTrue(quality_gate.check_publication(worker.database,'monthly-pass',scenario[0],body,p,[page])['passed']);draft['price']={**p['price'],'unit':'class'}
  with self.assertRaises(ValueError):quality_gate.check_publication(worker.database,'monthly-fail',scenario[0],body,p,[page])

 def test_padel_changed_source_cannot_replay_uncertain_card(self):
  i,b,w,c=self.padel_scenario();c.call.side_effect=TimeoutError()
  with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  w.page.return_value['text']+=' Changed program information.';w.page.return_value['sha256']='changed'
  with self.assertRaises(ValueError):padel.run(i,b,{'company_id':'company'},w,worker.database,{'run_id':'run','agent_id':'support'},c)
  self.assertEqual(c.call.call_count,1)

 def test_saint_street_name_is_not_truncated_to_st(self):
  self.assertEqual(evidence.street('126 St. Felix Street, Brooklyn'),'126 St. Felix Street')
 def test_known_suite_must_match_the_address_block(self):
  web=Mock();web.page.return_value=self.page(text='Example Center at 12 Main Street, Suite 3.')
  with self.assertRaises(ValueError):evidence.branch_page({'name':'Example Center','address':'12 Main St, Suite 2'},'https://example.org/',[],web)

 def test_verified_existing_branch_avoids_duplicate_new_listing(self):
  import growth,catalog
  page=self.page(text='Example Center Music classes at 12 Main Street in Brooklyn.');id=worker.save_draft('ClassScout',{'id':'source'},page,[{'field':'name','value':'Example Center','quote':'Example Center'},{'field':'address','value':'12 Main Street','quote':'12 Main Street'}]);catalog.initialize(worker.database)
  with worker.database() as db:row=dict(db.execute('SELECT * FROM entities WHERE id=?',(id,)).fetchone());db.execute('INSERT INTO catalog_checks VALUES(?,?,?,?,?)',('prov-example','old','hash',time.time(),json.dumps({'provider':{'id':'prov-example','name':'Example Center','website':'https://example.org/','address':'12 Main St','owner_managed':False}})))
  web=Mock();web.page.return_value=page;issue={'description':'Discovery campaign: classscout-nyc-v1\nDiscovery borough: Brooklyn\nDiscovery activity: Music'};self.assertEqual(growth.infer(issue,row,worker.database,web),{'Catalog provider':'prov-example'})
 def test_publication_gap_sources_do_not_create_delegation_loop(self):
  import search_workflow
  parent=test_publishing.PublishingTests().issue();parent.update(id='parent',companyId='company',status='blocked');ih=publishing.sha({'description':parent['description'],'title':parent['title'],'project':parent['projectId']});board=Mock();board.call.return_value=parent;job={'kind':'publishing','issue_id':'search','parent_publication':'parent','parent_input_hash':ih};outcome={'source_pages':[{'url':'https://example.org/pricing'}],'research_tasks':[]};search_workflow.initialize(worker.database)
  with patch.object(search_workflow,'persist_outcome'):
   result=search_workflow.deliver({'id':'search','projectId':'project','title':'Find source'},board,{'company_id':'company','agents':{'r':{'role':'research'},'p':{'role':'publication'}}},job,outcome,worker.database,{})
  self.assertEqual(result['research_tasks'],[]);self.assertFalse(any('/companies/' in call.args[0] for call in board.call.call_args_list));self.assertEqual(board.call.call_args.args[1]['status'],'todo')
