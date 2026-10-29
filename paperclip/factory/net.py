"""Bounded public-web reads, with pinned DNS and redirect/robots checks."""
import gzip,hashlib,html,http.client,io,ipaddress,json,re,socket,ssl,time,urllib.parse,urllib.robotparser
from html.parser import HTMLParser

MAX_BODY=1024*1024
class FetchError(Exception):pass

def canonical_url(value):
 if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value):raise FetchError('Invalid source URL')
 parsed=urllib.parse.urlsplit(value)
 if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:raise FetchError('Only public HTTP/HTTPS source URLs are supported')
 try:port=parsed.port
 except ValueError:raise FetchError('Invalid source port') from None
 if port not in {None,80 if parsed.scheme=='http' else 443}:raise FetchError('Nonstandard source ports are not allowed')
 host=parsed.hostname.encode('idna').decode().lower()
 if host in {'localhost','chatbotapi.haho.ai','paperclip.haho.ai'} or host.endswith(('.localhost','.local','.internal')):raise FetchError('Private or factory hosts cannot be source pages')
 query=[]
 for key,val in urllib.parse.parse_qsl(parsed.query,keep_blank_values=True):
  if re.search(r'(^|_)(token|password|secret|auth|api_key|signature)($|_)',key,re.I):raise FetchError('Credential-bearing source URLs are not allowed')
  if not key.lower().startswith('utm_') and key.lower() not in {'fbclid','gclid'}:query.append((key,val))
 netloc='['+host+']' if ':' in host else host
 return urllib.parse.urlunsplit((parsed.scheme,netloc,parsed.path or '/',urllib.parse.urlencode(query),''))

def public_addresses(host,port):
 addresses=[]
 try:rows=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
 except socket.gaierror:raise FetchError('Source DNS lookup failed') from None
 for row in rows:
  value=row[4][0];address=ipaddress.ip_address(value)
  if not address.is_global or address.is_multicast or address.is_reserved:raise FetchError('Source resolves to a non-public address')
  if value not in addresses:addresses.append(value)
 if not addresses:raise FetchError('No public source address')
 return sorted(addresses,key=lambda value:':' in value)

class PinnedHTTP(http.client.HTTPConnection):
 def __init__(self,host,port,address,secure):
  super().__init__(host,port,timeout=15);self.address=address;self.secure=secure
 def connect(self):
  sock=socket.create_connection((self.address,self.port),self.timeout)
  if self.secure:sock=ssl.create_default_context().wrap_socket(sock,server_hostname=self.host)
  self.sock=sock

class PageParser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.title=[];self.skip=0;self.in_title=False;self.images=[];self.links=[];self.structured=[];self.metadata={};self.ld=None
 def handle_starttag(self,tag,attrs):
  data=dict(attrs)
  if tag=='script' and data.get('type','').lower()=='application/ld+json':self.ld=[]
  if tag=='meta' and data.get('property','').lower() in {'og:site_name','og:url','og:title'}:self.metadata[data['property'].lower()]=str(data.get('content',''))[:300]
  if tag in {'script','style','svg','noscript'}:self.skip+=1
  if tag=='title':self.in_title=True
  if not self.skip:
   data=dict(attrs)
   if tag=='a' and data.get('href') and len(self.links)<250:self.links.append(data['href'])
   if tag=='img' and (data.get('src') or data.get('data-src')) and len(self.images)<80:self.images.append(data.get('src') or data['data-src'])
   if tag=='meta' and data.get('property','').lower() in {'og:image','twitter:image'} and data.get('content'):self.images.insert(0,data['content'])
  if tag in {'p','div','li','br','h1','h2','h3','section','footer','tr','td'}:self.parts.append('\n')
  if tag=='meta':
   attrs=dict(attrs)
   if attrs.get('name','').lower()=='description' and attrs.get('content'):self.parts.append(attrs['content']+'\n')
 def handle_endtag(self,tag):
  if tag=='script' and self.ld is not None:
   try:
    value=json.loads(''.join(self.ld));pending=value if isinstance(value,list) else [value]
    while pending and len(self.structured)<20:
     obj=pending.pop(0)
     if not isinstance(obj,dict):continue
     if isinstance(obj.get('@graph'),list):pending.extend(obj['@graph'][:20])
     if isinstance(obj.get('address'),dict) and isinstance(obj.get('name'),str):self.structured.append({k:obj[k] for k in ['@type','name','url','address'] if k in obj})
   except (ValueError,TypeError):pass
   self.ld=None
  if tag in {'script','style','svg','noscript'} and self.skip:self.skip-=1
  if tag=='title':self.in_title=False
  if tag in {'p','div','li','h1','h2','h3','section','footer','tr'}:self.parts.append('\n')
 def handle_data(self,data):
  if self.ld is not None and sum(map(len,self.ld))<16000:self.ld.append(data[:16000])
  if self.skip:return
  if self.in_title:self.title.append(data)
  self.parts.append(data)
 def result(self):
  lines=[re.sub(r'\s+',' ',line).strip() for line in ''.join(self.parts).splitlines()]
  return '\n'.join(dict.fromkeys(line for line in lines if line)),re.sub(r'\s+',' ',''.join(self.title)).strip()

class PublicWeb:
 def __init__(self):self.robots={}
 def raw(self,url,robots=False):
  url=canonical_url(url)
  for hop in range(5):
   parsed=urllib.parse.urlsplit(url);port=443 if parsed.scheme=='https' else 80
   if robots:self.check_robots(url)
   addresses=public_addresses(parsed.hostname,port);error=None
   for address in addresses[:2]:
    connection=PinnedHTTP(parsed.hostname,port,address,parsed.scheme=='https')
    try:
     connection.request('GET',urllib.parse.urlunsplit(('', '', parsed.path,parsed.query,'')),headers={'Host':parsed.netloc,'User-Agent':'NarimatoFactory/1.0 (public-source research; contact haho.ai)','Accept':'text/html,application/xhtml+xml,text/plain,application/json;q=0.8','Accept-Encoding':'identity'})
     response=connection.getresponse();status=response.status;headers=dict((k.lower(),v) for k,v in response.getheaders())
     if status in {301,302,303,307,308}:
      location=headers.get('location')
      if not location:raise FetchError('Source redirect has no destination')
      url=canonical_url(urllib.parse.urljoin(url,location));break
     content=response.read(MAX_BODY+1)
     if len(content)>MAX_BODY:raise FetchError('Source response exceeds size limit')
     if headers.get('content-encoding','').lower()=='gzip':
      with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:content=stream.read(MAX_BODY+1)
      if len(content)>MAX_BODY:raise FetchError('Expanded source exceeds size limit')
     return {'url':url,'status':status,'headers':headers,'body':content,'fetched_at':time.time()}
    except FetchError:raise
    except (OSError,TimeoutError,http.client.HTTPException) as exc:error=type(exc).__name__;continue
    finally:connection.close()
   else:raise FetchError('Could not read source: '+str(error))
  raise FetchError('Too many source redirects')
 def check_robots(self,url):
  parsed=urllib.parse.urlsplit(url);origin=parsed.scheme+'://'+parsed.netloc
  cached=self.robots.get(origin)
  if cached and time.time()-cached[0]<600:rules=cached[1]
  else:
   result=self.raw(origin+'/robots.txt')
   if result['status']==404:rules=None
   elif result['status'] in {401,403}:raise FetchError('Source disallows automated access')
   elif result['status']!=200:raise FetchError('Source robots policy is unavailable')
   else:
    rules=urllib.robotparser.RobotFileParser();rules.set_url(origin+'/robots.txt');rules.parse(result['body'].decode('utf-8','replace').splitlines())
   self.robots[origin]=(time.time(),rules)
  if rules and not rules.can_fetch('NarimatoFactory',url):raise FetchError('Source robots policy disallows this page')
 def page(self,url):
  result=self.raw(url,robots=True)
  if result['status']!=200:raise FetchError('Source returned HTTP '+str(result['status']))
  content_type=result['headers'].get('content-type','').lower()
  if not any(kind in content_type for kind in ['text/html','application/xhtml+xml','text/plain','application/json']):raise FetchError('Source type is not supported by the first research worker')
  charset=re.search(r'charset=([\w-]+)',content_type)
  try:text=result['body'].decode(charset.group(1) if charset else 'utf-8','replace')
  except LookupError:text=result['body'].decode('utf-8','replace')
  title='';links=[];images=[];structured=[];metadata={}
  if 'html' in content_type:
   parser=PageParser();parser.feed(text);text,title=parser.result();links=parser.links;images=parser.images;structured=parser.structured;metadata=parser.metadata
  if len(text.strip())<80 or any(marker in text[:500].lower() for marker in ['just a moment...','checking your browser','verify you are human']):raise FetchError('Source needs interactive access; no content was inferred')
  return {'url':result['url'],'title':title,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':result['fetched_at'],'links':links,'images':images,'structured':structured,'metadata':metadata}

def excerpts(page,limit=6500):
 text=page['text']
 if len(text)<=limit:return text
 lines=text.splitlines();selected=[];size=0
 # Include the page heading plus contact/price/address sections, not just navigation.
 picks=list(range(min(14,len(lines))))+[i for i,line in enumerate(lines) if re.search(r'contact|address|street|road|avenue|phone|tel:|email|@|hours|opening|price|cost|swim|padel|class|court|coach|location',line,re.I)]
 picks=[neighbor for index in picks for neighbor in range(max(0,index-2),min(len(lines),index+4))]
 for index in sorted(set(picks)):
  line=lines[index][:900]
  if size+len(line)>limit:continue
  selected.append(line);size+=len(line)
 return '\n'.join(selected)[:limit]
