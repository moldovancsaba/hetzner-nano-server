"""Literal first-party venue identities; query locality is never a factual claim."""
import re,unicodedata,urllib.parse
import evidence,publishing
DENIED={'timeout.com','padelvs.com','padellands.com','padellands','padel-magazine','padelmagazine','playtomic.io','facebook.com','instagram.com','yelp.com','tripadvisor.com'}
AFRICA=set('DZ AO BJ BW BF BI CV CM CF TD KM CG CD DJ EG GQ ER SZ ET GA GM GH GN GW CI KE LS LR LY MG MW ML MR MU MA MZ NA NE NG RW ST SN SC SL SO ZA SS SD TZ TG TN UG ZM ZW'.split())
COUNTRIES={'south africa':'ZA','afrique du sud':'ZA','africa do sul':'ZA','egypt':'EG','morocco':'MA','maroc':'MA','kenya':'KE','nigeria':'NG','tunisia':'TN','zambia':'ZM','seychelles':'SC','mauritius':'MU','hungary':'HU','magyarorszag':'HU','romania':'RO','szerbia':'RS','serbia':'RS','szlovakia':'SK','slovakia':'SK','ukrajna':'UA','ukraine':'UA','horvatorszag':'HR','croatia':'HR','szlovenia':'SI','slovenia':'SI','ausztria':'AT','austria':'AT'}
def fold(v):return ''.join(c for c in unicodedata.normalize('NFKD',str(v)).casefold() if not unicodedata.combining(c))
def key(v):return re.sub(r'[^a-z0-9]','',fold(v))
def country_code(v):
 if isinstance(v,dict):v=v.get('name') or v.get('@id') or ''
 value=fold(v).strip();return str(v).upper() if re.fullmatch('[A-Za-z]{2}',str(v)) else COUNTRIES.get(value)
def allowed_country(code,scope):
 if not code:return False
 if scope.get('kind')=='continent':return scope.get('continent')=='Africa' and code in AFRICA
 return scope.get('kind')=='countries' and code in scope.get('countries',[])
def provider_host(host):return not any(d in host for d in DENIED)
def brand_owned(name,url):
 stem=evidence.host(url).split('.')[0];a=key(name);b=key(stem)
 return len(a)>=4 and len(b)>=4 and (a==b or len(b)>=6 and (a.startswith(b) or b.startswith(a)))
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
  countries={code for phrase,code in COUNTRIES.items() if re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',fold(page['text'])) and allowed_country(code,scope)}
  if len(names)==1 and len(streets)==1 and len(countries)==1:
   # No city is assigned here: the caller may select only a literal canonical locality.
   found=[{'name':names[0],'address':streets[0],'city':None,'country':next(iter(countries)),'source_url':page['url'],'source_hash':page['sha256']}]
 return found

def resolve(url,web,vertical):
 root=web.page(url);host=evidence.host(root['url']);pending=[];pages=[root]
 direct=identities(root,vertical['territoryScope'])
 if len(direct)==1 and direct[0].get('city') and (vertical['slug']!='padel-africa' or re.search(r'\bpadel\b',root['text'],re.I)):return direct[0]
 # Directories may contribute links only. No directory fact enters an intake packet.
 if not provider_host(host):
  for raw in root.get('links',[]):
   target=urllib.parse.urljoin(root['url'],raw)
   if target.startswith('https://') and provider_host(evidence.host(target)) and evidence.host(target)!=host and re.search(r'padel|club|sport',evidence.host(target),re.I):pending.append(target)
 else:
  pending=[urllib.parse.urljoin(root['url'],raw) for raw in root.get('links',[]) if evidence.host(urllib.parse.urljoin(root['url'],raw))==host and re.search(r'location|venue|contact|cape-town|city-rock|club|kapcsolat|elerhetoseg',raw,re.I)]
 for target in list(dict.fromkeys(pending))[:3]:
  try:pages.append(web.page(target))
  except Exception:continue
 options=[];vocabulary=vertical.get('discovery',{});scope=vertical['territoryScope']
 for page in pages:
  if vertical['slug']=='padel-africa' and not re.search(r'\bpadel\b',page['text'],re.I):continue
  for option in identities(page,scope):
   if not option['city']:
    cities=[c for c in vocabulary.get('localities',[]) if publishing.norm(c) in publishing.norm(page['text'])]
    if len(cities)!=1:continue
    option['city']=cities[0]
   options.append(option)
 unique={(key(o['name']),key(o['address']),o['country']):o for o in options}
 if len(unique)!=1:raise ValueError('Official source does not uniquely establish one venue, city, street and declared country. Directory and multiple-branch evidence remain held.')
 return next(iter(unique.values()))

def branch_links(url,web):
 page=web.page(url);host=evidence.host(page['url']);out=[]
 for raw in page.get('links',[]):
  target=urllib.parse.urljoin(page['url'],raw);other=evidence.host(target)
  if not target.startswith('https://') or target.rstrip('/')==page['url'].rstrip('/') or not provider_host(other):continue
  path=urllib.parse.urlsplit(target).path
  if provider_host(host):
   if other!=host or not re.search(r'(?:venues?|locations?|clubs?)/[^/?#]+|^/(?:clubs?|venues?|locations?)/?$|^/pages/[^/]*(?:padel|club)[^/]*$|cape[-_]?town|city[-_]?rock|johannesburg',path,re.I):continue
  elif other==host or not re.search(r'padel|club|sport',other,re.I):continue
  if re.search(r'account|login|privacy|terms|search|\.pdf$',path,re.I):continue
  if target not in out:out.append(target)
  if len(out)==3:break
 return out,page['sha256']
