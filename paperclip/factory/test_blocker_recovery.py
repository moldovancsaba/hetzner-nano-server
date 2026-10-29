import json,time,unittest
from unittest.mock import Mock,patch
import worker,quality_gate,evidence,venue_identity,search_workflow as search,engine_ops,company_ops
import test_operations
class BlockerRecoveryTests(unittest.TestCase):
 def setUp(self):self.h=test_operations.OperationalTests();self.h.setUp()
 def tearDown(self):self.h.tearDown()
 def test_full_and_street_only_addresses_are_equivalent(self):
  self.assertTrue(quality_gate.unambiguous_contacts([{'field':'address','value':'321 Communipaw Ave, Jersey City, NJ 07304'},{'field':'address','value':'321 Communipaw Avenue'}]))
 def test_different_buildings_units_and_zip_codes_stay_ambiguous(self):
  for a,b in [('12 Main Street','13 Main Street'),('12 Main Street Suite 2','12 Main Street Suite 3'),('12 Main Street NY 10001','12 Main Street NY 10002')]:
   self.assertFalse(quality_gate.unambiguous_contacts([{'field':'address','value':a},{'field':'address','value':b}]))
 def test_phone_formatting_is_not_a_contact_conflict(self):
  self.assertTrue(quality_gate.unambiguous_contacts([{'field':'phone','value':'+1 (201) 946-9400'},{'field':'phone','value':'201-946-9400'}]))
 def test_different_phone_numbers_remain_ambiguous(self):
  self.assertFalse(quality_gate.unambiguous_contacts([{'field':'phone','value':'201-946-9400'},{'field':'phone','value':'201-946-9401'}]))
 def test_saint_marks_street_alias_preserves_building_number(self):
  self.assertTrue(evidence.address_matches('27 Saint Marks Place',"27 St. Mark's Place"));self.assertFalse(evidence.address_matches('27 Saint Marks Place',"127 St. Mark's Place"))
 def test_directories_do_not_become_official_venue_sources(self):
  for h in ['www.timeout.com','padelvs.com','padellands.com']:self.assertFalse(venue_identity.provider_host(h))
 def test_directory_leaf_screening_completes_without_accepting_a_venue(self):
  config={'projects':{'pa':'Padel Africa'},'engine_clients':{'padel-africa':True}};issue={'id':'i','projectId':'pa','description':'Official source URL: https://padelvs.com/en/club/example\nBranch depth: 1'};client=Mock();client.catalog.return_value={'vertical':{}}
  with patch('venue_identity.resolve',side_effect=ValueError('missing facts')):result=engine_ops.candidate(issue,Mock(),config,Mock(),worker.database,{},client)
  self.assertEqual(result['stage'],'engine_source_rejected');client.call.assert_not_called()
 def test_extraction_error_is_not_misclassified_by_tuition_in_url(self):
  category,action=company_ops.classify('No source-backed draft could be prepared. https://example.org/tuition: No source-supported fields passed validation');self.assertEqual(category,'source_extraction')
 def test_unchanged_failed_source_is_not_selected_again(self):
  search.initialize(worker.database);page=self.h.page();url=search.canonical_url(page['url']).replace('://www.','://').rstrip('/')
  with worker.database() as db:db.execute('INSERT INTO source_attempts VALUES(?,?,?,?,?)',('cs',url,page['sha256'],'previous',time.time()))
  web=Mock();web.page.return_value=page;job={'project_id':'cs','kind':'discovery','source_host':''}
  result=search.verified_pages([{'url':page['url']}],job,web,worker.database,2);self.assertEqual(result,[])
 def test_changed_source_can_be_selected_again(self):
  search.initialize(worker.database);page=self.h.page();page['text']+=' Music classes for kids.';url=search.canonical_url(page['url']).replace('://www.','://').rstrip('/')
  with worker.database() as db:db.execute('INSERT INTO source_attempts VALUES(?,?,?,?,?)',('cs',url,'old','previous',time.time()))
  web=Mock();web.page.return_value=page;result=search.verified_pages([{'url':page['url']}],{'project_id':'cs','kind':'discovery','source_host':''},web,worker.database,2);self.assertEqual(len(result),1)

 def test_official_image_provenance_is_part_of_the_classscout_contract(self):
  media={'status':'ready','originalUrl':'https://example.org/photo.jpg','sourceDocumentUrl':'https://example.org/classes','uploadedUrl':'https://images.example.org/a.jpg','contentHash':'hash','qualification':{'status':'accepted','provenance':'official'}};proof={'image_candidates':[media['originalUrl']]};pages=[{'url':media['sourceDocumentUrl']}];draft={'image':media['uploadedUrl']}
  self.assertTrue(quality_gate.qualified_media(media,proof,pages,draft))
  media['qualification']['provenance']='unknown';self.assertFalse(quality_gate.qualified_media(media,proof,pages,draft))
 def test_accepted_image_still_requires_source_provenance_and_hash(self):
  media={'status':'ready','originalUrl':'https://other.org/photo.jpg','sourceDocumentUrl':'https://example.org/classes','uploadedUrl':'https://images.example.org/a.jpg','contentHash':'hash','qualification':{'status':'accepted','provenance':'official'}}
  self.assertFalse(quality_gate.qualified_media(media,{'image_candidates':['https://example.org/photo.jpg']},[{'url':media['sourceDocumentUrl']}],{'image':media['uploadedUrl']}))
  media['originalUrl']='https://example.org/photo.jpg';media['contentHash']='';self.assertFalse(quality_gate.qualified_media(media,{'image_candidates':[media['originalUrl']]},[{'url':media['sourceDocumentUrl']}],{'image':media['uploadedUrl']}))

 def test_legacy_contact_baseline_allows_new_read_fields(self):
  import refresh
  self.assertTrue(refresh.baseline_matches({'name':'Example','phone':'123','price':{'evidence':'unknown'}},{'name':'Example','phone':'123'}))
 def test_legacy_contact_baseline_still_rejects_reviewed_fact_changes(self):
  import refresh
  self.assertFalse(refresh.baseline_matches({'name':'Example','phone':'999'},{'name':'Example','phone':'123'}))

 def test_regional_theatre_spelling_keeps_exact_provider_identity(self):
  self.assertTrue(evidence.branch_name_matches({'name':'City Island Theatre Group'},{'text':'City Island Theater Group welcomes families'},[]))
  self.assertFalse(evidence.branch_name_matches({'name':'City Island Theatre Group'},{'text':'Other Island Theater Group welcomes families'},[]))
 def test_jiu_jitsu_descriptor_does_not_break_same_provider_name(self):
  self.assertTrue(evidence.branch_name_matches({'name':'Team Jucao Long Island City Brazilian Jiu Jitsu'},{'text':'Team Jucao Long Island City Jiu-Jitsu'},[]))
  self.assertFalse(evidence.branch_name_matches({'name':'Team Jucao Long Island City Brazilian Jiu Jitsu'},{'text':'Team Other Long Island City Jiu-Jitsu'},[]))
