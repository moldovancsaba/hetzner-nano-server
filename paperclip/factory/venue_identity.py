"""Literal first-party venue identities; query locality is never a factual claim."""
import re,unicodedata,urllib.parse
import evidence,publishing
DENIED={'timeout.com','padelvs.com','padellands.com','padellands','padel-magazine','padelmagazine','playtomic.io','facebook.com','instagram.com','yelp.com','tripadvisor.com'}
# Racket-sport directories, magazines and booking platforms that publish pages about venues they do not run. Each is matched
# as a whole domain or one of its subdomains, never as a substring, so a venue whose own host ends in "tennis.com" stays valid.
DENIED_DOMAINS={'matchi.se':'court-booking marketplace with a facility page per venue','playbypoint.com':'booking platform that hosts club pages','courtreserve.com':'club-management platform that hosts club booking portals','clubspark.lta.org.uk':'LTA booking platform that hosts venue pages','tennis.com':'Tennis Channel editorial site','squashlevels.com':'squash rating site with a club directory','pickleheads.com':'pickleball court and group directory'}
# Registry names that are also common place or personal names ("Jordan, MN", "Chad's Tennis"). A page counts one only as the
# last part of a line, as in "Amman, Jordan"; every other registry name counts anywhere on the page.
HOMONYMS={'chad','georgia','ireland','jamaica','jersey','jordan','lebanon','mexico','panama','peru','turkey'}
# Words that open a unit or building part of an address line, and lowercase words that can sit inside a city name.
UNITS={'suite','ste','unit','floor','fl','level','building','bldg','room','rm','apt','apartment','block'}
CITY_WORDS={'de','da','do','del','di','du','la','le','of','upon','on','am','an','der','van','von','al','el'}
# Fixed link patterns for every vertical except Racket Land, which builds its own from the authenticated vocabulary.
HOST_LINKS=r'padel|club|sport'
VENUE_LINKS=r'location|venue|contact|cape-town|city-rock|club|kapcsolat|elerhetoseg'
BRANCH_LINKS=r'(?:venues?|locations?|clubs?)/[^/?#]+|^/(?:clubs?|venues?|locations?)/?$|^/pages/[^/]*(?:padel|club)[^/]*$|cape[-_]?town|city[-_]?rock|johannesburg'
AFRICA=set('DZ AO BJ BW BF BI CV CM CF TD KM CG CD DJ EG GQ ER SZ ET GA GM GH GN GW CI KE LS LR LY MG MW ML MR MU MA MZ NA NE NG RW ST SN SC SL SO ZA SS SD TZ TG TN UG ZM ZW'.split())
COUNTRIES={'south africa':'ZA','afrique du sud':'ZA','africa do sul':'ZA','egypt':'EG','morocco':'MA','maroc':'MA','kenya':'KE','nigeria':'NG','tunisia':'TN','zambia':'ZM','seychelles':'SC','mauritius':'MU','hungary':'HU','magyarorszag':'HU','romania':'RO','szerbia':'RS','serbia':'RS','szlovakia':'SK','slovakia':'SK','ukrajna':'UA','ukraine':'UA','horvatorszag':'HR','croatia':'HR','szlovenia':'SI','slovenia':'SI','ausztria':'AT','austria':'AT'}
def fold(v):return ''.join(c for c in unicodedata.normalize('NFKD',str(v)).casefold() if not unicodedata.combining(c))
def key(v):return re.sub(r'[^a-z0-9]','',fold(v))
def country_code(v):
 if isinstance(v,dict):v=v.get('name') or v.get('@id') or ''
 value=fold(v).strip()
 if re.fullmatch('[A-Za-z]{2}',str(v)):return str(v).upper()
 import racket_policy
 normalized=re.sub(r'[^a-z0-9]+',' ',value.replace('’','').replace("'",'')).strip()
 return COUNTRIES.get(value) or racket_policy.countries().get(normalized)
def allowed_country(code,scope):
 if not code:return False
 if scope.get('kind')=='unrestricted':
  import racket_policy
  return code in set(racket_policy.countries().values())
 if scope.get('kind')=='continent':return scope.get('continent')=='Africa' and code in AFRICA
 return scope.get('kind')=='countries' and code in scope.get('countries',[])
def provider_host(host):return not any(d in host for d in DENIED) and not any(host==d or host.endswith('.'+d) for d in DENIED_DOMAINS)
def brand_owned(name,url):
 stem=evidence.host(url).split('.')[0];a=key(name);b=key(stem)
 return len(a)>=4 and len(b)>=4 and (a==b or len(b)>=6 and (a.startswith(b) or b.startswith(a)))
def worldwide_countries(text):
 import racket_policy
 names={**COUNTRIES,**racket_policy.countries()};plain=fold(text)
 words=' '+re.sub(r'[^a-z0-9]+',' ',plain.replace('’','').replace("'",''))+' '
 spans=[(m.start(),m.end(),code) for phrase,code in names.items() if phrase not in HOMONYMS for m in re.finditer(r'(?<= )'+re.escape(phrase)+r'(?= )',words)]
 # The longest name wins, so "Equatorial Guinea" does not also name Guinea.
 codes={code for a,b,code in spans if not any(c<=a and b<=d and (c,d)!=(a,b) for c,d,_ in spans)}
 return codes|{code for phrase,code in names.items() if phrase in HOMONYMS and re.search(r'(?:^|,)[ \t]*'+re.escape(phrase)+r'[ \t]*[.;]?[ \t]*$',plain,re.M)}
def city_after(rest):
 # The component right after the street on one line: "12 Main Street, [Suite 4,] Austin, TX 78701, United States".
 parts=rest.split(',')
 if parts[0].strip():return None
 for part in parts[1:4]:
  tokens=part.split()
  if not tokens or tokens[0].strip('.#').casefold() in UNITS or tokens[0].startswith('#'):continue
  words=[]
  for token in tokens:
   if re.search(r'\d',token):break
   if token[:1].isupper() or words and token.casefold() in CITY_WORDS:words.append(token)
   else:return None
  if not words or words[-1].casefold() in CITY_WORDS or len(words)==1 and len(words[0].strip('.'))<3:return None
  if len(words[-1])>4:words[-1]=words[-1].rstrip('.')
  city=' '.join(words)
  return city if 3<=len(city)<=60 and re.fullmatch(r"[^\W\d_](?:[^\W\d_]|[ .'’-])*",city) else None
def page_city(text,street):
 # Only a city written on the same line as the one street counts; two different readings, a country name or nothing is None.
 import racket_policy
 at=re.compile(r'(?<![\w-])'+re.escape(street)+r'(?!\w)')
 found={city_after(line[m.end():]) for line in text.splitlines() for m in [at.search(line)] if m}-{None}
 city=next(iter(found)) if len(found)==1 else None
 return None if city and racket_policy.countries().get(re.sub(r'[^a-z0-9]+',' ',fold(city).replace('’','').replace("'",'')).strip()) else city
def identities(page,scope):
 if not provider_host(evidence.host(page['url'])):return []
 found=[]
 for obj in page.get('structured',[]):
  name=obj.get('name','');address=obj.get('address') or {};own_url=obj.get('url') or page['url'];street=str(address.get('streetAddress','')).strip();city=str(address.get('addressLocality','')).strip();code=country_code(address.get('addressCountry'))
  brand=page.get('metadata',{}).get('og:site_name','')
  if evidence.host(own_url)!=evidence.host(page['url']) or not (brand_owned(name,page['url']) or brand_owned(brand,page['url']) and publishing.norm(name) in publishing.norm(page['text'])):continue
  if not allowed_country(code,scope) or not all(3<=len(x)<=180 and not re.search(r'[\r\n<>]',x) for x in [name,street,city]) or not re.search(r'\d',street):continue
  if not all(publishing.norm(x) in publishing.norm(page['text']) for x in [name,street,city]):continue
  found.append({'name':name,'address':street,'city':city,'country':code,'source_url':page['url'],'source_hash':page['sha256'],'structured':obj})
 # A plain official page can still qualify, with its own visible country and street.
 if not found and not page.get('structured'):
  names=evidence.names(page);brand=page.get('metadata',{}).get('og:site_name','')
  if brand_owned(brand,page['url']) and publishing.norm(brand) in publishing.norm(page['text']):names.append(brand)
  names=list(dict.fromkeys(names));streets=list({m.group(0) for m in evidence.STREET.finditer(page['text'])})
  worldwide=scope.get('kind')=='unrestricted'
  countries=worldwide_countries(page['text']) if worldwide else {code for phrase,code in COUNTRIES.items() if re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',fold(page['text'])) and allowed_country(code,scope)}
  if len(names)==1 and len(streets)==1 and len(countries)==1:
   # Only a worldwide scope reads the city from the page's own address line. Elsewhere none is assigned: the caller may
   # select only a literal canonical locality.
   city=page_city(page['text'],streets[0]) if worldwide else None
   found=[{'name':names[0],'address':streets[0],'city':city if city and publishing.norm(city) in publishing.norm(page['text']) else None,'country':next(iter(countries)),'source_url':page['url'],'source_hash':page['sha256']}]
 return found

def link_patterns(vertical):
 # Racket Land takes its sport words and declared localities from the authenticated vertical; every other vertical, and a
 # caller without one, keeps the fixed patterns. Localities only help to recognise a branch page; they never admit a venue.
 patterns={'host':HOST_LINKS,'venue':VENUE_LINKS,'branch':BRANCH_LINKS}
 if not vertical or vertical.get('slug')!='racket-land':return patterns
 import racket_policy
 racket_policy.validate(vertical);discovery=vertical.get('discovery',{})
 def words(items):return [r'[-_]?'.join(re.escape(w) for w in re.findall(r'[a-z0-9]+',fold(x))) for x in items if re.search(r'[a-z0-9]',fold(x))]
 topic=words(discovery['vocabulary']['requiredTopicWords']);places=words(discovery.get('localities',[])[:200]);near=r'(?<![a-z0-9])(?:'+'|'.join(places)+r')(?![a-z0-9])' if places else None
 patterns['host']='|'.join([HOST_LINKS]+topic)
 patterns['venue']='|'.join([r'location|venue|contact|club|court|facilit|find-us|directions|kapcsolat|elerhetoseg']+([near] if near else []))
 patterns['branch']='|'.join([r'(?:venues?|locations?|clubs?)/[^/?#]+|^/(?:clubs?|venues?|locations?)/?$|^/pages/[^/]*(?:padel|club'+''.join('|'+t for t in topic)+r')[^/]*$']+([near] if near else []))
 return patterns

def resolve(url,web,vertical):
 root=web.page(url);host=evidence.host(root['url']);pending=[];pages=[root]
 direct=identities(root,vertical['territoryScope'])
 import racket_policy
 if len(direct)==1 and direct[0].get('city') and (racket_policy.matches(root['text'],vertical) if vertical['slug']=='racket-land' else vertical['slug']!='padel-africa' or re.search(r'\bpadel\b',root['text'],re.I)):return direct[0]
 # Directories may contribute links only. No directory fact enters an intake packet.
 links=link_patterns(vertical)
 if not provider_host(host):
  for raw in root.get('links',[]):
   target=urllib.parse.urljoin(root['url'],raw)
   if target.startswith('https://') and provider_host(evidence.host(target)) and evidence.host(target)!=host and re.search(links['host'],evidence.host(target),re.I):pending.append(target)
 else:
  pending=[urllib.parse.urljoin(root['url'],raw) for raw in root.get('links',[]) if evidence.host(urllib.parse.urljoin(root['url'],raw))==host and re.search(links['venue'],raw,re.I)]
 for target in list(dict.fromkeys(pending))[:3]:
  try:pages.append(web.page(target))
  except Exception:continue
 options=[];vocabulary=vertical.get('discovery',{});scope=vertical['territoryScope']
 for page in pages:
  if vertical['slug']=='racket-land' and not racket_policy.matches(page['text'],vertical):continue
  if vertical['slug']=='padel-africa' and not re.search(r'\bpadel\b',page['text'],re.I):continue
  for option in identities(page,scope):
   if not option['city']:
    # A city not read from the page is taken only when exactly one declared locality is written on it, else the page stays
    # held. A worldwide scope reads its own city first, so the list never decides whether such a venue is admitted.
    cities=[c for c in vocabulary.get('localities',[]) if publishing.norm(c) in publishing.norm(page['text'])]
    if len(cities)!=1:continue
    option['city']=cities[0]
   options.append(option)
 unique={(key(o['name']),key(o['address']),o['country']):o for o in options}
 if len(unique)!=1:raise ValueError('Official source does not uniquely establish one venue, city, street and declared country. Directory and multiple-branch evidence remain held.')
 return next(iter(unique.values()))

def branch_links(url,web,vertical=None):
 page=web.page(url);host=evidence.host(page['url']);out=[];links=link_patterns(vertical)
 for raw in page.get('links',[]):
  target=urllib.parse.urljoin(page['url'],raw);other=evidence.host(target)
  if not target.startswith('https://') or target.rstrip('/')==page['url'].rstrip('/') or not provider_host(other):continue
  path=urllib.parse.urlsplit(target).path
  if provider_host(host):
   if other!=host or not re.search(links['branch'],path,re.I):continue
  elif other==host or not re.search(links['host'],other,re.I):continue
  if re.search(r'account|login|privacy|terms|search|\.pdf$',path,re.I):continue
  if target not in out:out.append(target)
  if len(out)==3:break
 return out,page['sha256']
