import copy,json,time,unittest
from unittest.mock import Mock,patch
import worker,company_ops,publishing,formats,net,venue_identity as vi,engine_ops as engine,program_updates as programs,pipeline,quality_gate
import test_operations,test_publishing

class AlignmentTests(unittest.TestCase):
 def setUp(self):
  self.h=test_operations.OperationalTests();self.h.setUp()
  self.config={'company_id':'company','projects':{'cs':'ClassScout','pa':'Padel Africa','hu':'Sportolok','mg':'Management'},'agents':{'pub':{'role':'publication'},'ops':{'role':'support'},'qa':{'role':'quality'},'search':{'role':'search'},'research':{'role':'research'}},'engine_clients':{'padel-africa':True,'sportolok':True},'automatic_quality_gate':{'enabled':True,'daily_write_limit':20},'reliability_enabled':True,'operational_workflows_enabled':True}
 def tearDown(self):self.h.tearDown()
 def test_uncertain_venue_is_not_an_uncertain_write(self):
  self.assertNotEqual(company_ops.classify('Multi-branch or uncertain sources are held')[0],'write_verification')
  self.assertEqual(company_ops.classify('Uncertain engine submission outcome; inspect receipt')[0],'write_verification')
 def test_unknown_price_and_unstated_timetable_are_not_invented(self):
  h=test_publishing.PublishingTests();p=h.page();p['text']='Keylab Music classes for ages 5-10 at 94 Luquer St, Carroll Gardens, Brooklyn.'
  n,proof=publishing.normalize_sources(h.brief(),[p],[{'field':'address','value':'94 Luquer St','quote':'94 Luquer St'}])
  self.assertEqual(proof['price'],{'evidence':'unknown'});self.assertEqual(proof['schedules'],[]);self.assertNotIn('free',' '.join(n['descriptionFacts']).lower())
 def test_ambiguous_prices_stay_unknown_in_catalog(self):
  h=test_publishing.PublishingTests();p=h.page();p['text']+=' Another program costs $250 per month.'
  n,proof=publishing.normalize_sources(h.brief(),[p],[{'field':'address','value':'94 Luquer St','quote':'94 Luquer St'}]);self.assertEqual(proof['price']['evidence'],'unknown')
 def test_new_expired_camp_still_cannot_publish(self):
  text='Camp dates: 2020-06-01 to 2020-06-30. Ages 5-10 Mondays 9:00 am, 120 minutes.'
  with self.assertRaises(ValueError):formats.schedules(text,'Camps',True)
  self.assertEqual(formats.schedules(text,'Camps',True,allow_expired=True)[0]['endDate'],'2020-06-30')
 def test_structured_metadata_is_bounded_and_not_model_instructions(self):
  p=net.PageParser();p.feed('<meta property="og:site_name" content="Example Padel"><script type="application/ld+json">'+json.dumps({'@type':'SportsActivityLocation','name':'Example Padel','url':'https://examplepadel.org','address':{'streetAddress':'12 Main Road','addressLocality':'Cape Town','addressCountry':'ZA'}})+'</script><p>Visible page content only.</p>')
  self.assertEqual(len(p.structured),1);self.assertNotIn('SportsActivityLocation',p.result()[0]);self.assertEqual(p.metadata['og:site_name'],'Example Padel')
 def venue(self,slug='padel-africa'):
  hu=slug=='sportolok';name='Árvíztűrő Sport';url='https://arvizturo-sport.hu/' if hu else 'https://examplepadel.org/';name=name if hu else 'Example Padel';street='Hunyadi János út 6.' if hu else '12 Main Road';city='Budapest' if hu else 'Cape Town';country='HU' if hu else 'ZA'
  page={'url':url,'title':name,'text':f'{name} {street} {city}. Sport és edzés.' if hu else f'{name} at {street} in {city}, South Africa offers padel courts.','sha256':'hash','fetched_at':time.time(),'links':[],'metadata':{},'structured':[{'@type':'SportsActivityLocation','name':name,'url':url,'address':{'streetAddress':street,'addressLocality':city,'addressCountry':country}}]}
  return page
 def test_hungarian_source_values_are_preserved_verbatim(self):
  page=self.venue('sportolok');found=vi.identities(page,{'kind':'countries','countries':['HU']});self.assertEqual(found[0]['name'],'Árvíztűrő Sport');self.assertEqual(found[0]['address'],'Hunyadi János út 6.')
 def test_directory_cannot_be_its_own_provider_evidence(self):
  page=self.venue();page['url']='https://padellands.com/venue/example';self.assertEqual(vi.identities(page,{'kind':'continent','continent':'Africa'}),[])
 def test_structured_outside_territory_is_rejected(self):
  page=self.venue();page['structured'][0]['address']['addressCountry']='US';self.assertEqual(vi.identities(page,{'kind':'continent','continent':'Africa'}),[])
 def test_query_locality_cannot_assign_source_city(self):
  page=self.venue();page['structured'][0]['address']['addressLocality']='Nairobi';self.assertEqual(vi.identities(page,{'kind':'continent','continent':'Africa'}),[])
 def test_focused_venue_never_inherits_headquarters(self):
  page=self.venue();web=Mock();web.page.return_value=page
  result=vi.resolve(page['url'],web,{'slug':'padel-africa','territoryScope':{'kind':'continent','continent':'Africa'}})
  self.assertEqual(result['city'],'Cape Town');self.assertEqual(web.page.call_count,1)
 def test_program_patch_preserves_other_programs_and_structured_schedule(self):
  p=self.h.page();p['text']='Example Center at 12 Main Street. Ages 5-10 - Mondays 9:00 am, 45 minutes. $150 per month.'
  row=self.h.row();row['recurringPrograms']=[{'id':'a','title':'Ages 5-10','ageMinMonths':60,'ageMaxMonths':120,'daysOfWeek':['Monday'],'timeText':'9:00 am (45 minutes)','price':{'evidence':'unknown','sourceUrl':p['url']}},{'id':'b','title':'Other program','ageMinMonths':144,'ageMaxMonths':180,'daysOfWeek':['Sunday'],'timeText':'5pm'}]
  patch,proof=programs.proposed(row,[p]);self.assertEqual(len(patch['recurringPrograms']),2);self.assertEqual(patch['recurringPrograms'][1],row['recurringPrograms'][1]);self.assertEqual(patch['recurringPrograms'][0]['price']['amount'],150)
  row['recurringPrograms'][0]['schedule']={'precision':'exact'};row['recurringPrograms'][0]['timeText']='10:00 am';patch,proof=programs.proposed(row,[p]);self.assertEqual(patch,{})
 def test_same_program_price_is_not_rewritten_for_new_observation_time(self):
  p=self.h.page();p['text']='Example Center at 12 Main Street. Ages 5-10 - Mondays 9:00 am, 45 minutes. $150 per month.'
  row=self.h.row();row['recurringPrograms']=[{'id':'a','title':'Ages 5-10','ageMinMonths':60,'ageMaxMonths':120,'daysOfWeek':['Monday'],'timeText':'9:00 am (45 minutes)','price':{'evidence':'stated','amount':150.0,'currency':'USD','unit':'month','sourceText':'$150 per month','sourceUrl':p['url'],'observedAt':'old'}}];row['price']=copy.deepcopy(row['recurringPrograms'][0]['price']);self.assertEqual(programs.proposed(row,[p])[0],{})
 def test_other_branch_does_not_update_programs(self):
  p=self.h.page();p['text']='Example Center at 99 Other Street. Ages 5-10 Mondays 9:00 am, 45 minutes. $150 per month.'
  row=self.h.row();row['recurringPrograms']=[{'id':'a','ageMinMonths':60,'ageMaxMonths':120}];self.assertEqual(programs.proposed(row,[p])[0],{})
 def test_engine_lost_reply_is_never_replayed(self):
  engine.initialize(worker.database);issue={'id':'i','title':'Venue','description':'Evidence','projectId':'pa'};client=Mock();client.call.side_effect=TimeoutError();body={'id':'card','sourceText':'literal evidence','sourceUrl':'https://example.org','sourcePool':'ingest'}
  with patch('engine_ops.execute_guard'):
   with self.assertRaises(ValueError):engine.write_once(issue,Mock(),self.config,worker.database,{},client,'padel-africa','intake',body,{'source':'hash'})
   with self.assertRaises(ValueError):engine.write_once(issue,Mock(),self.config,worker.database,{},client,'padel-africa','intake',body,{'source':'different'})
  self.assertEqual(client.call.call_count,1)
 def test_engine_intake_receipt_does_not_become_publication(self):
  issue={'id':'i','title':'Venue','description':'Evidence','projectId':'pa'};client=Mock();client.call.return_value={'cardId':'card','created':True};body={'id':'card','sourceText':'literal evidence','sourceUrl':'https://example.org','sourcePool':'ingest'}
  with patch('engine_ops.execute_guard'):receipt,state=engine.write_once(issue,Mock(),self.config,worker.database,{},client,'padel-africa','intake',body,{'source':'hash'})
  self.assertEqual(state,'accepted');self.assertNotIn('published',receipt)
 def test_hard_or_flagged_cards_are_never_force_published(self):
  client=Mock();client.origin='https://example.org';client.catalog.return_value={'vertical':{'territoryScope':{},'locales':['hu-HU']},'catalog':{'total':0,'listings':[]},'triage':{'reviewReadySample':[{'id':'flag','state':'REVIEW_READY','lastReason':'flagged for review'}]}}
  issue={'id':'i','title':'Maintain','projectId':'hu'};engine.maintain(issue,Mock(),self.config,Mock(),worker.database,{},client);client.call.assert_not_called()
 def test_saved_draft_quality_is_dispatched_outside_ancestor_chain(self):
  p=self.h.page();id=worker.save_draft('ClassScout',{'id':'source'},p,[{'field':'name','value':'Example Center','quote':'Example Center'}]);issue={'id':'source','title':'Saved source','projectId':'cs','description':'Factory workflow: source_research'};board=Mock()
  pipeline.after_research(issue,{'entities':[id]},board,self.config,worker.database);board.call.assert_not_called()
  with worker.database() as db:r=db.execute('SELECT payload_json FROM company_dispatch').fetchone()
  self.assertEqual(json.loads(r[0])['assigneeAgentId'],'qa');self.assertNotIn('parentId',json.loads(r[0]))
 def program_scenario(self):
  page=self.h.page();page['text']='Example Center at 12 Main Street. Ages 5-10 - Mondays 9:00 am, 45 minutes. $150 per month.'
  row=self.h.row();row.update(price={'evidence':'unknown'},recurringPrograms=[{'id':'a','title':'Ages 5-10','ageMinMonths':60,'ageMaxMonths':120,'daysOfWeek':['Monday'],'timeText':'9:00 am (45 minutes)','price':{'evidence':'unknown','sourceUrl':page['url']}}])
  current=[copy.deepcopy(row)];client=Mock();client.existing_provider.side_effect=lambda id:copy.deepcopy(current[0]);public=Mock();public.public_get.side_effect=lambda *a:copy.deepcopy(current[0]);writer=Mock()
  def apply(body):current[0].update(copy.deepcopy(body['patch']));return {'results':[{'ok':True}]}
  writer.apply.side_effect=apply;issue={'id':'program','companyId':'company','projectId':'cs','title':'Program check','description':'Catalog provider: prov-example','status':'in_progress','assigneeAgentId':'pub'};board=Mock();board.call.side_effect=lambda path,*a:issue if path.startswith('/issues/') else {'status':'running','agentId':'pub','companyId':'company'};web=Mock();web.page.return_value=page
  return issue,board,web,client,writer,public,current
 def test_program_write_requires_private_and_public_readback(self):
  i,b,w,c,writer,public,current=self.program_scenario()
  with patch('program_updates.catalog.Catalog',return_value=public):result=programs.run(i,b,self.config,w,worker.database,{'run_id':'r','agent_id':'pub'},c,writer)
  self.assertEqual(result['stage'],'program_applied');self.assertEqual(current[0]['price']['amount'],150);self.assertEqual(current[0]['fieldVerifications'][0]['method'],'official_page')
 def test_program_lost_write_reply_is_never_replayed(self):
  i,b,w,c,writer,public,current=self.program_scenario();writer.apply.side_effect=TimeoutError()
  with self.assertRaises(ValueError):programs.run(i,b,self.config,w,worker.database,{'run_id':'r','agent_id':'pub'},c,writer)
  with self.assertRaises(ValueError):programs.run(i,b,self.config,w,worker.database,{'run_id':'r','agent_id':'pub'},c,writer)
  self.assertEqual(writer.apply.call_count,1)
 def test_manual_program_verification_is_preserved(self):
  i,b,w,c,writer,public,current=self.program_scenario();current[0]['fieldVerifications']=[{'field':'schedule','method':'admin','verifiedAt':'2026-10-28T00:00:00Z'}]
  with self.assertRaises(ValueError):programs.run(i,b,self.config,w,worker.database,{'run_id':'r','agent_id':'pub'},c,writer)
  writer.apply.assert_not_called()

 def test_branch_expansion_is_bounded_and_uses_specific_pages(self):
  web=Mock();web.page.return_value={'url':'https://examplepadel.com/','sha256':'a','links':['/login','/venues/one','/venues/two','/venues/three','/venues/four','https://otherpadel.com/venues/five']}
  links,sha=vi.branch_links('https://examplepadel.com/',web)
  self.assertEqual(len(links),3);self.assertEqual(sha,'a');self.assertTrue(all(x.startswith('https://examplepadel.com/venues/') for x in links))
 def test_branch_expansion_only_queues_independent_checks(self):
  issue={'id':'branch','title':'Check source','projectId':'pa','description':'Official source URL: https://examplepadel.com/'};web=Mock();client=Mock();client.catalog.return_value={'vertical':{'territoryScope':{}}}
  with patch('venue_identity.resolve',side_effect=ValueError('multiple')),patch('venue_identity.branch_links',return_value=(['https://examplepadel.com/venues/one'],'hash')):
   result=engine.candidate(issue,Mock(),self.config,web,worker.database,{},client)
  self.assertEqual(result['stage'],'engine_source_expanded');client.call.assert_not_called()
  with worker.database() as db:body=json.loads(db.execute('SELECT payload_json FROM company_dispatch').fetchone()[0])
  self.assertNotIn('parentId',body);self.assertIn('Branch depth: 1',body['description']);self.assertEqual(body['assigneeAgentId'],'ops')
 def test_branch_expansion_does_not_recurse(self):
  issue={'id':'branch','title':'Check source','projectId':'pa','description':'Official source URL: https://examplepadel.com/venues/one\nBranch depth: 1'};client=Mock();client.catalog.return_value={'vertical':{'territoryScope':{}}}
  with patch('venue_identity.resolve',side_effect=ValueError('multiple')),patch('venue_identity.branch_links') as expand:
   with self.assertRaises(ValueError):engine.candidate(issue,Mock(),self.config,Mock(),worker.database,{},client)
   expand.assert_not_called()
