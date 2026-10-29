"""Small read-only HTTP and HTML metadata audits of ClassScout's public pages."""
import hashlib,json,re,time,urllib.parse
from html.parser import HTMLParser
import catalog,publishing
from net import canonical_url

class Metadata(HTMLParser):
 def __init__(self):super().__init__();self.in_title=False;self.title=[];self.description='';self.canonical=[];self.robots='';self.links=[];self.h1=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='title':self.in_title=True
  if tag=='h1':self.h1+=1
  if tag=='meta' and a.get('name','').lower()=='description':self.description=a.get('content','').strip()
  if tag=='meta' and a.get('name','').lower()=='robots':self.robots=a.get('content','').lower()
  if tag=='link' and 'canonical' in a.get('rel','').lower().split() and a.get('href'):self.canonical.append(a['href'])
  if tag=='a' and a.get('href') and len(self.links)<150:self.links.append(a['href'])
 def handle_endtag(self,tag):
  if tag=='title':self.in_title=False
 def handle_data(self,data):
  if self.in_title:self.title.append(data)

def allowed(url):
 url=canonical_url(url);u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or u.hostname!='getyourfield.com' or u.query or re.search(r'^/(api|admin|account|login|_next|checkout|billing)(/|$)',u.path):raise ValueError('Audit accepts public ClassScout HTML pages only, without query strings')
 return url

def inspect(url,web):
 url=allowed(url);raw=web.raw(url,robots=True);final=allowed(raw['url']);row={'url':url,'final_url':final,'http_status':raw['status'],'checked_at':raw['fetched_at'],'findings':[]}
 def finding(code,severity,detail,fix):row['findings'].append({'code':code,'severity':severity,'detail':detail,'fix':fix})
 if raw['status']>=400:finding('http_error','high','The public page returned HTTP '+str(raw['status']), 'Restore the page or remove/update links to this exact URL.');return row,[]
 if raw['status']!=200:row['not_checked']='The final response was not HTTP 200';return row,[]
 if 'html' not in raw['headers'].get('content-type',''):row['not_checked']='The response was not HTML';return row,[]
 parser=Metadata();parser.feed(raw['body'].decode('utf-8','replace'));title=' '.join(parser.title).strip();row.update(title=title[:240],description=parser.description[:400],canonical=parser.canonical,robots=parser.robots,h1_in_response=parser.h1)
 if not title:finding('missing_title','medium','No title was found in the served HTML.','Provide a descriptive title for this route and verify it in the served HTML.')
 if not parser.description and 'noindex' not in parser.robots:finding('missing_description','low','No description was found in the served HTML.','Review whether this indexable route needs a page-specific search description.')
 if not parser.canonical and 'noindex' not in parser.robots:finding('missing_canonical','medium','No canonical URL was found in the served HTML.','Define the intended canonical for this route and verify it after rendering.')
 if len(set(parser.canonical))>1:finding('conflicting_canonical','medium','The response contains different canonical URLs.','Keep a single intended canonical URL for this route.')
 for link in parser.canonical:
  target=urllib.parse.urljoin(final,link);u=urllib.parse.urlsplit(target)
  if u.scheme!='https' or u.hostname not in {'getyourfield.com','www.getyourfield.com'}:finding('canonical_other_origin','medium','Canonical points outside the expected HTTPS site.','Confirm the preferred host and remove an unintended cross-origin canonical.')
 return row,parser.links

def run(issue,board,config,web,database,execution):
 maximum=min(8,max(1,int(config.get('audit_page_limit',6))));explicit=catalog.field(issue,'Audit URLs');pending=[allowed(x.strip()) for x in explicit.split(',')] if explicit else [allowed(u) for u in config.get('audit_seed_urls',['https://getyourfield.com/'])]
 if len(pending)>maximum:raise ValueError('Audit request exceeds the configured page limit')
 rows=[];seen=set();titles={}
 while pending and len(rows)<maximum:
  url=pending.pop(0)
  if url in seen:continue
  seen.add(url)
  try:
   row,links=inspect(url,web)
   title=row.get('title')
   if title and title in titles and titles[title]!=row['final_url']:row['findings'].append({'code':'duplicate_title','severity':'low','detail':'This title also appears on '+titles[title],'fix':'Review whether these routes need distinct search titles.'})
   elif title:titles[title]=row['final_url']
   if not explicit:
    for link in links:
     try:target=allowed(urllib.parse.urljoin(row['final_url'],link))
     except Exception:continue
     if target not in seen and target not in pending and re.search(r'/nyc/(classes|places|family-events|providers)(/|$)',urllib.parse.urlsplit(target).path) and len(pending)<maximum:pending.append(target)
  except Exception as error:row={'url':url,'not_checked':str(error)[:180],'findings':[]}
  rows.append(row)
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS audit_findings(finding_key TEXT PRIMARY KEY,url TEXT,code TEXT,severity TEXT,detail_json TEXT,status TEXT,task_id TEXT,identifier TEXT,first_seen REAL,last_seen REAL)')
 tasks=[];all_keys=set()
 for row in rows:
  for finding in row['findings']:
   key=publishing.sha({'url':row['url'],'code':finding['code']});all_keys.add(key)
   with database() as db:
    previous=db.execute('SELECT task_id,identifier FROM audit_findings WHERE finding_key=?',(key,)).fetchone()
    db.execute('INSERT INTO audit_findings VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(finding_key) DO UPDATE SET detail_json=excluded.detail_json,status=excluded.status,last_seen=excluded.last_seen',(key,row['url'],finding['code'],finding['severity'],json.dumps(finding),'observed',previous[0] if previous else None,previous[1] if previous else None,time.time(),time.time()))
   if previous and previous[0]:tasks.append(previous[1]);continue
   if finding['severity'] not in {'high','medium'} or len(tasks)>=5:continue
   child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'site-finding-'+key,'title':'Website audit: '+finding['code'].replace('_',' ')+' — '+urllib.parse.urlsplit(row['url']).path,'projectId':issue['projectId'],'parentId':issue['id'],'status':'backlog','assigneeUserId':config.get('reviewer_user_id','local-board'),'reviewPolicy':'human_only','description':'Affected URL: '+row['url']+'\n\nObserved: '+finding['detail']+'\n\nExpected fix: '+finding['fix']+'\n\nReproduce with an ordinary HTTP GET and inspect the returned HTML. Scope: HTTP response and HTML metadata; browser rendering, indexing and search ranking were not tested. No production change was performed.'})
   with database() as db:db.execute('UPDATE audit_findings SET task_id=?,identifier=? WHERE finding_key=?',(child['id'],child['identifier'],key))
   tasks.append(child['identifier'])
 checked={r['url'] for r in rows if r.get('http_status')==200 and 'not_checked' not in r}
 with database() as db:
  for old in db.execute("SELECT finding_key,url FROM audit_findings WHERE status='observed'").fetchall():
   if old['url'] in checked and old['finding_key'] not in all_keys:db.execute("UPDATE audit_findings SET status='not_reproduced',last_seen=? WHERE finding_key=?",(time.time(),old['finding_key']))
 report={'pages':rows,'finding_tasks':list(dict.fromkeys(tasks)),'page_limit':maximum,'scope':'HTTP/HTML metadata only; not browser rendering, indexing, ranking or a security scan'};catalog.save_report(database,issue,'audit_site',report)
 lines=['## ClassScout website audit','','Pages attempted: '+str(len(rows))+'. Findings: '+str(sum(len(r['findings']) for r in rows))+'.','Follow-up tasks: '+(', '.join(report['finding_tasks']) or 'none')+'.','']
 for r in rows:
  lines+=['- '+r['url']+': '+(r.get('not_checked') or 'HTTP '+str(r.get('http_status'))+'; '+str(len(r['findings']))+' findings')]
  for f in r['findings']:lines.append('  - '+f['code'].replace('_',' ')+': '+f['detail']+' '+f['fix'])
 lines+=['','This is a bounded response/metadata audit. It does not establish browser usability, Google indexing or ranking. No site content was changed.']
 return {'stage':'site_audit_review','entities':[],'markdown':'\n'.join(lines),'final_status':'done','report':report}
