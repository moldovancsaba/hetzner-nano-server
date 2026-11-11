"""Fixed-origin Perplexity web search used only when Brave cannot serve a job; the key stays in the host environment.

One request an hour, 24 a day and 744 a month, counted in the factory database before any network call. The Search API
returns ranked URLs and snippets with no model-written answer, so a row here is a lead exactly like a Brave row: the
factory still fetches the page itself and applies every source check before anything is handed on."""
import datetime,json,time,urllib.error,urllib.request,uuid
from zoneinfo import ZoneInfo
from brave import SearchError,validate
from search_budget import BudgetWait

ORIGIN='https://api.perplexity.ai/search'
KEY_ENV='PERPLEXITY_SEARCH_API_KEY'
GAP=3600
DAILY=24
MONTHLY=744
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def zone(epoch):return datetime.datetime.fromtimestamp(epoch,ZoneInfo('Europe/Budapest'))
def day_key(epoch):return zone(epoch).date().isoformat()
def month_key(epoch):return zone(epoch).strftime('%Y-%m')
def next_day(epoch):return datetime.datetime.combine(zone(epoch).date()+datetime.timedelta(days=1),datetime.time(),ZoneInfo('Europe/Budapest')).timestamp()
def next_month(epoch):
 d=zone(epoch);y,m=(d.year+1,1) if d.month==12 else (d.year,d.month+1);return datetime.datetime(y,m,1,tzinfo=ZoneInfo('Europe/Budapest')).timestamp()

class PerplexityBudget:
 """Durable, process-independent allowance. A reservation counts even when the response never arrives."""
 def __init__(self,database,clock=time.time):self.database=database;self.clock=clock;self.initialize()
 def initialize(self):
  with self.database() as db:
   db.executescript('''CREATE TABLE IF NOT EXISTS perplexity_attempts(id TEXT PRIMARY KEY,job_id TEXT,reserved_at REAL,day_key TEXT,month_key TEXT,status TEXT,http_status INTEGER);
   CREATE INDEX IF NOT EXISTS perplexity_attempt_time ON perplexity_attempts(reserved_at);''')
 def reserve(self,job_id,count=1):
  if count!=1:raise ValueError('Perplexity serves one query per request slot')
  now=self.clock()
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE');last=db.execute('SELECT max(reserved_at) FROM perplexity_attempts').fetchone()[0]
   if last is not None and now<last+GAP:raise BudgetWait('Perplexity allows one request an hour',last+GAP)
   if db.execute('SELECT count(*) FROM perplexity_attempts WHERE day_key=?',(day_key(now),)).fetchone()[0]>=DAILY:raise BudgetWait('Daily Perplexity allowance reached',next_day(now))
   if db.execute('SELECT count(*) FROM perplexity_attempts WHERE month_key=?',(month_key(now),)).fetchone()[0]>=MONTHLY:raise BudgetWait('Monthly Perplexity allowance reached',next_month(now))
   token=str(uuid.uuid4());db.execute('INSERT INTO perplexity_attempts(id,job_id,reserved_at,day_key,month_key,status,http_status) VALUES(?,?,?,?,?,?,?)',(token,job_id,now,day_key(now),month_key(now),'reserved',None))
   return [token]
 def dispatch(self,token):
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT status FROM perplexity_attempts WHERE id=?',(token,)).fetchone()
   if not row or row[0]!='reserved':raise ValueError('This search reservation was already used')
   db.execute("UPDATE perplexity_attempts SET status='dispatched' WHERE id=?",(token,))
 def finish(self,token,status,http_status=None,headers=None):
  with self.database() as db:db.execute('UPDATE perplexity_attempts SET status=?,http_status=? WHERE id=?',(status,http_status,token))
 def status(self):
  now=self.clock()
  with self.database() as db:
   month=db.execute('SELECT count(*) FROM perplexity_attempts WHERE month_key=?',(month_key(now),)).fetchone()[0];today=db.execute('SELECT count(*) FROM perplexity_attempts WHERE day_key=?',(day_key(now),)).fetchone()[0];last=db.execute('SELECT max(reserved_at) FROM perplexity_attempts').fetchone()[0]
  return {'used_this_window':month,'automatic_limit':MONTHLY,'used_today':today,'daily_limit':DAILY,'next_search_at':max(now,(last or 0)+GAP)}

class Perplexity:
 def __init__(self,budget,opener=None,environ=None):
  import os
  self.budget=budget;self.opener=opener or urllib.request.build_opener(NoRedirect);self.environ=os.environ if environ is None else environ
 def search(self,query,token):
  validate(query,'ALL','en')
  key=self.environ.get(KEY_ENV)
  if not key:raise SearchError('Perplexity connection is not configured')
  try:self.budget.dispatch(token)
  except ValueError:raise SearchError('Could not acquire the Perplexity request slot',True) from None
  req=urllib.request.Request(ORIGIN,data=json.dumps({'query':query,'max_results':20}).encode(),method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
  try:
   with self.opener.open(req,timeout=25) as response:
    body=response.read(2*1024*1024+1);self.budget.finish(token,'succeeded',response.status)
    if len(body)>2*1024*1024:raise SearchError('Perplexity response exceeded the size limit')
    rows=json.loads(body).get('results',[])
    if not isinstance(rows,list):raise SearchError('Invalid Perplexity result format')
    return [{'url':r['url'],'title':str(r.get('title') or '')[:300],'description':str(r.get('snippet') or '')[:300]} for r in rows[:20] if isinstance(r,dict) and isinstance(r.get('url'),str)]
  except urllib.error.HTTPError as error:
   self.budget.finish(token,'failed',error.code);raise SearchError('Perplexity returned HTTP '+str(error.code),error.code==429 or error.code>=500) from None
  except SearchError:raise
  except Exception:
   self.budget.finish(token,'uncertain');raise SearchError('Perplexity response was not confirmed; attempt counted conservatively',True) from None
