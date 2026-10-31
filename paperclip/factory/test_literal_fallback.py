"""Tests for literal fallback facts: evidence.literal_facts yields a name and address only when title, domain and
visible text agree and omits an address when several appear; worker.extract uses it when the model returns
no facts; venue_identity.branch_links picks specific venue pages."""
import unittest
from unittest.mock import Mock
import evidence,worker,venue_identity
class LiteralFallbackTests(unittest.TestCase):
 def test_provider_title_segment_with_matching_domain_and_visible_name(self):
  page={'url':'https://bronxriverart.org/classes','title':"Bronx River Art Center :: Children's Classes",'text':'Bronx River Art Center at 1087 East Tremont Avenue. Classes cost $25.'}
  facts=evidence.literal_facts(page);self.assertEqual({x['field'] for x in facts},{'name','address'});self.assertEqual(worker.validate_facts(facts,page)[1],[])
 def test_title_without_visible_identity_is_not_evidence(self):
  self.assertEqual(evidence.literal_facts({'url':'https://bronxriverart.org/','title':'Bronx River Art Center','text':'A third-party checkout page'}),[])
 def test_unrelated_title_cannot_supply_a_name(self):
  self.assertEqual(evidence.literal_facts({'url':'https://example.org/','title':'Bronx River Art Center','text':'Bronx River Art Center at 12 Main Street'}),[])
 def test_multiple_addresses_remain_absent(self):
  p={'url':'https://bronxschoolformusic.org/','title':'Admission | Bronx School For Music','text':'Bronx School For Music: 12 Main Street and 25 Other Avenue'}
  self.assertEqual([x['field'] for x in evidence.literal_facts(p)],['name'])
 def test_empty_model_facts_can_use_literal_identity(self):
  p={'url':'https://examplecenter.org/','title':'Example Center','text':'Example Center welcomes children at 12 Main Street.'};model=Mock();model.call.return_value=({'facts':[]},{'usage':{}})
  facts,rejected,usage=worker.extract(p,model,'run',0);self.assertEqual({x['field'] for x in facts},{'name','address'})
 def test_specific_shop_venue_page_is_eligible_for_branch_check(self):
  web=Mock();web.page.return_value={'url':'https://examplepadel.com/pages/venues','links':['/collections/rackets','/pages/lourensford-padel-pickleball-club-cpt','/account','/clubs'],'sha256':'hash'}
  links,_=venue_identity.branch_links('https://examplepadel.com/pages/venues',web);self.assertEqual(len(links),2);self.assertNotIn('https://examplepadel.com/collections/rackets',links)
