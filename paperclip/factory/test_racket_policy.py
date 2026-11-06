"""Worldwide source identity retains actual country and application-owned racket vocabulary."""
import copy
import unittest
from unittest.mock import Mock,patch
import engine_ops,padel,racket_policy,venue_identity

def vertical():return {'slug':'racket-land','territoryScope':{'kind':'unrestricted'},'taxonomy':{'racket-club':'Racket clubs'},'locales':['en','fr','pt'],'discovery':{'vocabulary':{'requiredTopicWords':['tennis','padel','squash','badminton','pickleball','frescobol','tamburello']}}}

class RacketPolicyTests(unittest.TestCase):
 def test_authenticated_new_identity_and_scope_are_required(self):
  client=engine_ops.Client('padel-africa')
  with patch.object(client,'call',return_value={'vertical':vertical(),'catalog':{'listings':[]}}):self.assertEqual(client.catalog()['vertical']['slug'],'racket-land')
  old=vertical();old.update(slug='padel-africa',territoryScope={'kind':'continent','continent':'Africa'})
  with patch.object(client,'call',return_value={'vertical':old}),self.assertRaises(ValueError):client.catalog()
  self.assertEqual(client.origin,'https://racket.land');self.assertEqual(padel.ORIGIN,'https://racket.land')

 def test_actual_countries_worldwide_and_unknown_country_remain_distinct(self):
  for name,code in [('United States','US'),('United Kingdom','GB'),('Singapore','SG'),('Australia','AU'),('Japan','JP'),('Brazil','BR'),('South Africa','ZA')]:
   self.assertEqual(venue_identity.country_code(name),code);self.assertTrue(venue_identity.allowed_country(code,{'kind':'unrestricted'}))
  for code in [None,'','ZZ','UK']:self.assertFalse(venue_identity.allowed_country(code,{'kind':'unrestricted'}))
  self.assertFalse(venue_identity.allowed_country('US',{'kind':'countries','countries':['HU']}))

 def test_page_needs_a_declared_sport_word_beyond_a_generic_venue(self):
  for word in ['Tennis','badminton','pickleball','frescobol','tamburello']:self.assertTrue(racket_policy.matches(word+' courts and coaching',vertical()))
  self.assertFalse(racket_policy.matches('Restaurant with live music',vertical()));self.assertFalse(racket_policy.matches('tennisless restaurant',vertical()))

 def test_worldwide_official_identity_uses_source_city_and_country(self):
  page={'url':'https://tokyobadminton.example/contact','sha256':'a'*64,'text':'Tokyo Badminton at 12 Main Street in Tokyo, Japan offers badminton coaching.','metadata':{},'structured':[{'name':'Tokyo Badminton','url':'https://tokyobadminton.example/','address':{'streetAddress':'12 Main Street','addressLocality':'Tokyo','addressCountry':'Japan'}}]}
  web=Mock();web.page.return_value=page
  result=venue_identity.resolve(page['url'],web,vertical());self.assertEqual((result['city'],result['country']),('Tokyo','JP'));self.assertEqual(web.page.call_count,1)
  unrelated=copy.deepcopy(page);unrelated['text']=unrelated['text'].replace('badminton coaching','dining')
  self.assertEqual(venue_identity.identities(page,{'kind':'countries','countries':['HU']}),[])

if __name__=='__main__':unittest.main()
