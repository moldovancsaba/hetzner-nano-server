"""Worldwide source identity retains actual country and application-owned racket vocabulary: structured and plain
pages resolve anywhere in the registry without a finite city list, an unreadable city stays held, the other verticals keep
their fixed rules, racket directories are refused as whole domains, and link patterns follow the vertical."""
import copy
import re
import unittest
from unittest.mock import Mock,patch
import engine_ops,padel,racket_policy,venue_identity

def vertical(localities=None):
 value={'slug':'racket-land','territoryScope':{'kind':'unrestricted'},'taxonomy':{'racket-club':'Racket clubs'},'locales':['en','fr','pt'],'discovery':{'vocabulary':{'requiredTopicWords':['tennis','padel','squash','badminton','pickleball','frescobol','tamburello']}}}
 if localities is not None:value['discovery']['localities']=localities
 return value
def venue_page(name,address,extra='Tennis courts and coaching'):
 # A plain official page: no structured data, a title that names the host, one address line.
 return {'url':'https://'+re.sub('[^a-z0-9]','',name.lower())+'.example/contact','title':name,'text':name+'\n'+address+'\n'+extra,'sha256':'b'*64,'links':[],'metadata':{},'structured':[]}
def resolve(page,scope_vertical):
 web=Mock();web.page.return_value=page;return venue_identity.resolve(page['url'],web,scope_vertical)

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

 def test_plain_pages_resolve_a_us_a_uk_and_a_japanese_venue_without_a_city_list(self):
  for name,line,extra,city,code in [('Austin Racket Club','123 Main Street, Austin, TX 78701, United States','Tennis and pickleball courts','Austin','US'),('Manchester Squash Centre','10 High Street, Manchester M1 1AA, United Kingdom','Squash courts','Manchester','GB'),('Tokyo Badminton Hall','3-4 Shibuya Road, Tokyo 150-0001, Japan','Badminton coaching','Tokyo','JP'),('Suite Tennis Works','12 Main Street, Suite 4, Houston, TX 77002, United States','Tennis lessons','Houston','US')]:
   with self.subTest(name):
    result=resolve(venue_page(name,line,extra),vertical());self.assertEqual((result['name'],result['city'],result['country'],result['address']),(name,city,code,line.split(', ')[0]))

 def test_plain_page_whose_city_cannot_be_read_stays_held(self):
  for line in ['12 Main Street in Springfield, Japan','12 Main Street, TX 78701, Japan','12 Main Street, Suite 4, Japan','12 Main Street, Japan','Meet us at 12 Main Street, Saturday mornings. Japan','12 Main Street, 78701 Austin, United States']:
   with self.subTest(line):
    page=venue_page('Held Tennis Club',line);self.assertIsNone(venue_identity.identities(page,{'kind':'unrestricted'})[0]['city'])
    with self.assertRaises(ValueError):resolve(page,vertical([]))
  page=venue_page('Held Tennis Club','12 Main Street, Austin, Texas, United States\n12 Main Street, Dallas, Texas, United States')
  self.assertIsNone(venue_identity.identities(page,{'kind':'unrestricted'})[0]['city'])
  with self.assertRaises(ValueError):resolve(page,vertical())
  self.assertEqual(venue_identity.page_city('Visit 112 Main Street, Austin, TX\nAlso 12 Main Street, Dallas, Texas','12 Main Street'),'Dallas')

 def test_declared_locality_is_a_fallback_and_never_a_requirement(self):
  prose=venue_page('Prose Tennis Club','12 Main Street in Springfield, Japan')
  self.assertEqual(resolve(prose,vertical(['Springfield']))['city'],'Springfield')
  with self.assertRaises(ValueError):resolve(prose,vertical(['Springfield','Japan']))
  readable=venue_page('Austin Racket Club','123 Main Street, Austin, TX 78701, United States\nPartner courts in Dallas')
  for localities in [None,[],['Dallas'],['Dallas','Austin']]:self.assertEqual(resolve(readable,vertical(localities))['city'],'Austin')

 def test_country_names_use_the_longest_registry_name_and_guard_homonyms(self):
  count=venue_identity.worldwide_countries
  for text,codes in [('Malabo, Equatorial Guinea',{'GQ'}),('Port Moresby, Papua New Guinea',{'PG'}),('Juba, South Sudan',{'SS'}),('Amman, Jordan',{'JO'}),('12 Main Street, Jordan, MN 55352',set()),("Chad's Tennis Club, 12 Main Street",set()),('Atlanta, Georgia, United States',{'US'}),('Tbilisi, Georgia',{'GE'}),('Belfast, Northern Ireland, United Kingdom',{'GB'}),('Albuquerque, New Mexico',set()),('Mexico City, Mexico',{'MX'}),('Casablanca, Maroc',{'MA'}),('Budapest, Magyarország',{'HU'}),('Austin, TX, USA',set()),('Paris, France and Madrid, Spain',{'FR','ES'})]:
   with self.subTest(text):self.assertEqual(count(text),codes)

 def test_other_verticals_keep_their_fixed_plain_page_rules(self):
  africa={'kind':'continent','continent':'Africa'};hungary={'kind':'countries','countries':['HU']}
  cape=venue_page('Example Padel','12 Main Road, Cape Town, South Africa','Padel courts')
  [found]=venue_identity.identities(cape,africa);self.assertEqual((found['city'],found['country']),(None,'ZA'))
  self.assertEqual(venue_identity.identities(venue_page('Example Padel','123 Main Street, Austin, TX 78701, United States'),africa),[])
  self.assertEqual(venue_identity.identities(venue_page('Example Padel','12 Main Road, Tokyo, Japan'),hungary),[])
  legacy={'slug':'padel-africa','territoryScope':africa,'discovery':{'localities':['Cape Town']}}
  self.assertEqual(resolve(cape,legacy)['city'],'Cape Town')
  del legacy['discovery']['localities']
  with self.assertRaises(ValueError):resolve(cape,legacy)
  budapest=venue_page('Arvizturo Sport','12 Main Street, Budapest, Hungary','Sport es edzes')
  self.assertIsNone(venue_identity.identities(budapest,hungary)[0]['city'])
  self.assertEqual(resolve(budapest,{'slug':'sportolok','territoryScope':hungary,'discovery':{'localities':['Budapest']}})['city'],'Budapest')

 def test_racket_directories_are_refused_as_whole_domains_and_venues_are_not(self):
  for host in ['matchi.se','app.playbypoint.com','app.courtreserve.com','clubspark.lta.org.uk','tennis.com','www.tennis.com','squashlevels.com','pickleheads.com','timeout.com','playtomic.io','padellands.co.uk']:
   with self.subTest(host):self.assertFalse(venue_identity.provider_host(host))
  for host in ['northshoretennis.com','mytennis.com','notmatchi.se','matchi.example','clubspark.example','lta.org.uk','badmintonengland.co.uk','squashlevels.example']:
   with self.subTest(host):self.assertTrue(venue_identity.provider_host(host))
  page=venue_page('Matchi Tennis','1 Main Street, Austin, TX 78701, United States');page['url']='https://matchi.se/facilities/matchi-tennis'
  self.assertEqual(venue_identity.identities(page,{'kind':'unrestricted'}),[])

 def test_a_racket_directory_only_leads_to_the_venues_own_site(self):
  own=venue_page('Tennis Works Austin','123 Main Street, Austin, TX 78701, United States')
  directory={'url':'https://matchi.se/facilities/austin','title':'Austin','text':'Tennis facilities\n123 Main Street, Austin, TX 78701, United States','sha256':'d'*64,'links':[own['url'],'https://matchi.se/facilities/other','https://randomshop.example/'],'metadata':{},'structured':[]}
  pages={directory['url']:directory,own['url']:own};web=Mock();web.page.side_effect=lambda url:pages[url]
  result=venue_identity.resolve(directory['url'],web,vertical());self.assertEqual((result['source_url'],result['city']),(own['url'],'Austin'));self.assertEqual(web.page.call_count,2)
  legacy=Mock();legacy.page.side_effect=lambda url:pages[url]
  with self.assertRaises(ValueError):venue_identity.resolve(directory['url'],legacy,{'slug':'sportolok','territoryScope':{'kind':'countries','countries':['US']}})
  self.assertEqual(legacy.page.call_count,1)

 def test_link_patterns_follow_the_vertical_and_other_verticals_keep_the_fixed_ones(self):
  fixed=venue_identity.link_patterns(None);self.assertEqual(venue_identity.link_patterns({'slug':'sportolok'}),fixed);self.assertEqual(venue_identity.link_patterns({'slug':'padel-africa'}),fixed)
  self.assertIn('cape-town',fixed['venue']);self.assertIn('johannesburg',fixed['branch'])
  racket=venue_identity.link_patterns(vertical(['Tokyo','São Paulo']))
  for name in racket:self.assertNotIn('johannesburg',racket[name]);self.assertNotIn('city-rock',racket[name])
  self.assertNotIn('cape-town',racket['venue']);self.assertTrue(re.search(racket['host'],'tenniscourts.example'));self.assertTrue(re.search(racket['venue'],'/sao-paulo',re.I))
  self.assertFalse(re.search(fixed['host'],'tenniscourts.example'));self.assertEqual(venue_identity.link_patterns(vertical())['venue'],'location|venue|contact|club|court|facilit|find-us|directions|kapcsolat|elerhetoseg')
  with self.assertRaises(ValueError):venue_identity.link_patterns({**vertical(),'territoryScope':{'kind':'continent','continent':'Africa'}})
  web=Mock();web.page.return_value={'url':'https://squashhub.example/','sha256':'a','links':['/pages/squash-courts','/tokyo','/cape-town','/login','/venues/one']}
  racket_links,_=venue_identity.branch_links('https://squashhub.example/',web,vertical(['Tokyo']))
  fixed_links,_=venue_identity.branch_links('https://squashhub.example/',web)
  self.assertEqual([x.rsplit('/',1)[1] for x in racket_links],['squash-courts','tokyo','one']);self.assertEqual([x.rsplit('/',1)[1] for x in fixed_links],['cape-town','one'])
  web.page.return_value={'url':'https://matchi.se/facilities','sha256':'a','links':['https://tenniscourts.example/','https://randomshop.example/','https://matchi.se/x']}
  self.assertEqual(venue_identity.branch_links('https://matchi.se/facilities',web,vertical())[0],['https://tenniscourts.example/']);self.assertEqual(venue_identity.branch_links('https://matchi.se/facilities',web)[0],[])

if __name__=='__main__':unittest.main()
