"""Persistent account-wide Brave reservations, cooldown and quota accounting."""
import datetime,json,sqlite3,time,uuid
from zoneinfo import ZoneInfo

class BudgetWait(ValueError):
 def __init__(self,reason,until):super().__init__(reason);self.reason=reason;self.until=until

def day_key(epoch):return datetime.datetime.fromtimestamp(epoch,ZoneInfo('Europe/Budapest')).date().isoformat()
def monthly_headers(headers):
 h={k.lower():v for k,v in headers.items() if v is not None}
 try:
  policies=[x.strip() for x in h['x-ratelimit-policy'].split(',')];remaining=[int(x.strip()) for x in h['x-ratelimit-remaining'].split(',')];resets=[int(x.strip()) for x in h['x-ratelimit-reset'].split(',')]
  for i,policy in enumerate(policies):
   cap,window=policy.split(';w=');window=int(window)
   if window>=86400:return {'limit':min(2000,int(cap)),'period':window,'remaining':max(0,remaining[i]),'reset_seconds':max(1,resets[i])}
 except (ValueError,KeyError,IndexError,AttributeError):pass
 return None

class Budget:
 def __init__(self,database,clock=time.time):self.database=database;self.clock=clock;self.initialize()
 def initialize(self):
  now=self.clock()
  with self.database() as db:
   db.executescript('''CREATE TABLE IF NOT EXISTS search_account(id INTEGER PRIMARY KEY CHECK(id=1),window_start REAL,reset_at REAL,period REAL,next_allowed REAL,last_http REAL,remaining INTEGER,last_seen REAL);
   CREATE TABLE IF NOT EXISTS search_attempts(id TEXT PRIMARY KEY,job_id TEXT,reserved_at REAL,day_key TEXT,status TEXT,http_status INTEGER,quota_headers TEXT,burst_size INTEGER NOT NULL DEFAULT 1);
   CREATE INDEX IF NOT EXISTS search_attempt_window ON search_attempts(reserved_at);
   CREATE INDEX IF NOT EXISTS search_attempt_day ON search_attempts(day_key);''')
   columns={row[1] for row in db.execute('PRAGMA table_info(search_attempts)')}
   if 'burst_size' not in columns:db.execute('ALTER TABLE search_attempts ADD COLUMN burst_size INTEGER NOT NULL DEFAULT 1')
   db.execute('INSERT OR IGNORE INTO search_account VALUES(1,?,?,?,?,?,?,?)',(now,now+31*86400,31*86400,0,0,2000,now))
 def seed_probe(self,report):
  observed=monthly_headers(report.get('quota_headers',{}));when=datetime.datetime.fromisoformat(report['checked_at']).timestamp()
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE')
   if db.execute('SELECT count(*) FROM search_attempts').fetchone()[0]:return
   if observed:
    end=when+observed['reset_seconds'];db.execute('UPDATE search_account SET window_start=?,reset_at=?,period=?,remaining=?,next_allowed=? WHERE id=1',(end-observed['period'],end,observed['period'],max(0,min(2000,observed['remaining'])-1),when+1800))
   db.execute('INSERT INTO search_attempts(id,job_id,reserved_at,day_key,status,http_status,quota_headers) VALUES(?,?,?,?,?,?,?)',('owner-authorized-probe-20261028','manual-probe',when,day_key(when),'succeeded',report.get('http_status'),json.dumps(report.get('quota_headers',{}))))
 def _state(self,db,now):
  state=dict(db.execute('SELECT * FROM search_account WHERE id=1').fetchone())
  if now<state['last_seen']-5:raise BudgetWait('Clock moved backwards; preserve the existing quota window',state['last_seen'])
  if now>=state['reset_at']:
   start=state['reset_at']+int((now-state['reset_at'])//state['period'])*state['period'];state.update(window_start=start,reset_at=start+state['period'],remaining=2000)
   db.execute('UPDATE search_account SET window_start=?,reset_at=?,remaining=? WHERE id=1',(state['window_start'],state['reset_at'],state['remaining']))
  db.execute('UPDATE search_account SET last_seen=? WHERE id=1',(now,));return state
 def reserve(self,job_id,count):
  if not 1<=count<=3:raise ValueError('A search burst must contain one to three queries')
  now=self.clock()
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE');s=self._state(db,now)
   if now<s['next_allowed']:raise BudgetWait('Shared search cooldown',s['next_allowed'])
   used=db.execute('SELECT count(*) FROM search_attempts WHERE reserved_at>=?',(s['window_start'],)).fetchone()[0]
   if used+count>1800 or s['remaining']-count<200:raise BudgetWait('Monthly search allowance reserved/exhausted',s['reset_at'])
   days={day_key(now+2*i) for i in range(count)}
   for day in days:
    needed=sum(day_key(now+2*i)==day for i in range(count));spent=db.execute('SELECT count(*) FROM search_attempts WHERE day_key=?',(day,)).fetchone()[0]
    if spent+needed>48:
     tomorrow=datetime.datetime.combine(datetime.date.fromisoformat(day)+datetime.timedelta(days=1),datetime.time(),ZoneInfo('Europe/Budapest')).timestamp();raise BudgetWait('Daily search allowance reached',tomorrow)
   tokens=[]
   for i in range(count):
    token=str(uuid.uuid4());db.execute('INSERT INTO search_attempts(id,job_id,reserved_at,day_key,status,http_status,quota_headers) VALUES(?,?,?,?,?,?,?)',(token,job_id,now,day_key(now+2*i),'reserved',None,None));db.execute('UPDATE search_attempts SET burst_size=? WHERE id=?',(count,token));tokens.append(token)
   db.execute('UPDATE search_account SET next_allowed=?,remaining=remaining-? WHERE id=1',(now+1800*count+2*(count-1),count))
   return tokens
 def dispatch(self,token):
  now=self.clock()
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE');s=self._state(db,now);a=db.execute('SELECT * FROM search_attempts WHERE id=?',(token,)).fetchone()
   if not a or a['status']!='reserved':raise ValueError('This search reservation was already used')
   if a['reserved_at']<s['window_start']:
    used=db.execute('SELECT count(*) FROM search_attempts WHERE reserved_at>=?',(s['window_start'],)).fetchone()[0]
    if used>=1800 or s['remaining']<=200:raise BudgetWait('Rollover reservation cannot spend the monthly reserve',s['reset_at'])
    db.execute('UPDATE search_attempts SET reserved_at=? WHERE id=?',(now,token));db.execute('UPDATE search_account SET remaining=remaining-1 WHERE id=1');s['remaining']-=1
   if s['remaining']<200:raise BudgetWait('Account reserve reached during burst',s['reset_at'])
   if now<s['last_http']+2:raise BudgetWait('Brave request spacing',s['last_http']+2)
   actual_day=day_key(now)
   if actual_day!=a['day_key']:
    if db.execute('SELECT count(*) FROM search_attempts WHERE day_key=?',(actual_day,)).fetchone()[0]>=48:raise BudgetWait('Daily allowance changed while the burst waited',now+1800)
   db.execute("UPDATE search_attempts SET status='dispatched',day_key=? WHERE id=?",(actual_day,token));db.execute('UPDATE search_account SET last_http=? WHERE id=1',(now,))
 def finish(self,token,status,http_status=None,headers=None):
  now=self.clock();headers=headers or {};observed=monthly_headers(headers)
  with self.database() as db:
   db.execute('BEGIN IMMEDIATE');s=self._state(db,now)
   if observed:
    reset=now+observed['reset_seconds'];start=reset-observed['period']
    # Keep the earlier boundary when header rounding or network latency differs.
    if abs(start-s['window_start'])<120:start=min(start,s['window_start'])
    if start>s['window_start']+86400:
     remaining=max(0,observed['remaining']-1)
    else:remaining=min(s['remaining'],observed['remaining'])
    db.execute('UPDATE search_account SET window_start=?,reset_at=?,period=?,remaining=? WHERE id=1',(start,reset,observed['period'],remaining))
   attempt=db.execute('SELECT burst_size FROM search_attempts WHERE id=?',(token,)).fetchone()
   if attempt:db.execute('UPDATE search_account SET next_allowed=MAX(next_allowed,?) WHERE id=1',(now+1800*attempt[0],))
   safe={k:v for k,v in headers.items() if k.lower().startswith('x-ratelimit-') or k.lower()=='retry-after'}
   db.execute('UPDATE search_attempts SET status=?,http_status=?,quota_headers=? WHERE id=?',(status,http_status,json.dumps(safe),token))
 def status(self):
  now=self.clock()
  with self.database() as db:
   s=self._state(db,now);used=db.execute('SELECT count(*) FROM search_attempts WHERE reserved_at>=?',(s['window_start'],)).fetchone()[0];daily=db.execute('SELECT count(*) FROM search_attempts WHERE day_key=?',(day_key(now),)).fetchone()[0]
  return {'used_this_window':used,'automatic_limit':1800,'account_limit':2000,'estimated_account_remaining':s['remaining'],'reserve':200,'used_today':daily,'daily_limit':48,'next_search_at':s['next_allowed'],'provider_reset_at':s['reset_at'],'window_start':s['window_start']}
