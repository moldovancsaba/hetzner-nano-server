"""Fresh preparation for expired or parser-affected, never-submitted automatic packets; originals and write receipts stay immutable."""
import datetime,json,time
import catalog,publishing,quality_gate
TABLES={'publication_packets':'publication','refresh_packets':'refresh'}
DECLINED={'rejected','withdrawn','cancelled','expired','skipped'}

def initialize(database):
 with database() as db:db.execute('''CREATE TABLE IF NOT EXISTS packet_renewals(packet_hash TEXT PRIMARY KEY,packet_table TEXT,source_issue TEXT,root_issue TEXT,input_hash TEXT,body_json TEXT,status TEXT,target_issue TEXT,created_at REAL,next_at REAL,attempts INTEGER,error_category TEXT)''')

def expired(packet,table,now=None):
 value=packet['created_at'];created=datetime.datetime.fromisoformat(value).timestamp() if isinstance(value,str) else value
 return (time.time() if now is None else now)-created>48*3600

def due(packet,table):
 if expired(packet,table):return True
 # A released branch parser can re-prepare only the affected unsubmitted contact proof, once.
 if table=='refresh_packets':
  import evidence
  return any(f.get('field')=='address' and not evidence.street(f.get('value','')) for f in json.loads(packet['proof_json']).get('facts',[]))
 return False

def allowed(packet,table,issue,board,config):
 if table not in TABLES or packet['status'] not in {'prepared','awaiting_approval'} or not quality_gate.enabled(config,issue):return False
 if packet.get('receipt_json'):return False
 if packet['input_hash']!=publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']}):return False
 cards=board.call('/issues/'+issue['id']+'/interactions') if packet.get('interaction_id') else []
 if any(c.get('id')==packet.get('interaction_id') and c.get('status') in DECLINED for c in cards):return False
 body=json.loads(packet['body_json']);proof=json.loads(packet['proof_json'])
 if table=='publication_packets':valid=publishing.sha({'body':body,'proof':proof})==packet['packet_hash']
 else:
  import refresh
  valid=refresh.packet_hash(packet['issue_id'],packet['input_hash'],body,proof,json.loads(packet['baseline_json']))==packet['packet_hash']
 if not valid:raise ValueError('Expired packet integrity check failed; no automatic renewal')
 return True

def supersede(packet,table,database):
 if table not in TABLES:raise ValueError('Unsupported renewal table')
 with database() as db:
  db.execute('BEGIN IMMEDIATE')
  changed=db.execute('UPDATE '+table+" SET status='superseded' WHERE packet_hash=? AND status IN ('prepared','awaiting_approval') AND receipt_json IS NULL",(packet['packet_hash'],)).rowcount
  if changed!=1:raise ValueError('Packet changed during renewal; inspect its existing state')

def coordinate(tasks,board,config,database):
 """Scheduled successors avoid native historical execution guards without clearing or replaying them."""
 initialize(database)
 from autonomy import stopped
 publisher=next(k for k,v in config['agents'].items() if v['role']=='publication');by_id={t['id']:t for t in tasks};now=time.time()
 with database() as db:
  packets=[]
  for table in TABLES:
   if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():packets += [(table,dict(r)) for r in db.execute('SELECT p.* FROM '+table+" p WHERE status IN ('prepared','awaiting_approval','superseded') AND packet_hash=(SELECT x.packet_hash FROM "+table+" x WHERE x.issue_id=p.issue_id ORDER BY created_at DESC LIMIT 1) AND NOT EXISTS(SELECT 1 FROM packet_renewals r WHERE r.packet_hash=p.packet_hash)")]
 planned=0
 for table,packet in sorted(packets,key=lambda x:str(x[1]['created_at'])):
  if planned>=2:break
  source=by_id.get(packet['issue_id'])
  if not source or source.get('status') not in {'blocked','in_review'} or source.get('companyId')!=config['company_id'] or config['projects'].get(source.get('projectId'))!='ClassScout':continue
  if not due(packet,table):continue
  try:
   if not allowed({**packet,'status':'awaiting_approval'} if packet['status']=='superseded' else packet,table,source,board,config) or not stopped(source,board,database):continue
  except (ValueError,TypeError,KeyError):continue
  root=catalog.field(source,'Packet renewal root') or source['id'];description=source.get('description') or ''
  if not catalog.field(source,'Packet renewal root'):description+='\nPacket renewal root: '+root
  description+='\nRenewal of packet: '+packet['packet_hash']
  body={'idempotencyKey':'renew-packet-'+packet['packet_hash'],'title':'Prepare fresh evidence: '+source['title'][-110:],'description':description,'projectId':source['projectId'],'status':'todo','assigneeAgentId':publisher,'reviewPolicy':'anyone'}
  with database() as db:
   db.execute('BEGIN IMMEDIATE')
   if db.execute('SELECT count(*) FROM packet_renewals WHERE root_issue=?',(root,)).fetchone()[0]>=3:continue
   if db.execute('SELECT 1 FROM packet_renewals WHERE packet_hash=?',(packet['packet_hash'],)).fetchone():continue
   changed=db.execute('UPDATE '+table+" SET status='superseded' WHERE packet_hash=? AND status IN ('prepared','awaiting_approval','superseded') AND receipt_json IS NULL",(packet['packet_hash'],)).rowcount
   if changed!=1:continue
   db.execute('INSERT INTO packet_renewals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(packet['packet_hash'],table,source['id'],root,packet['input_hash'],json.dumps(body),'queued',None,now,now,0,None));planned+=1
 delivered=[];held=[]
 with database() as db:requests=[dict(r) for r in db.execute("SELECT * FROM packet_renewals WHERE status IN ('queued','creating') AND next_at<=? ORDER BY created_at LIMIT 2",(now,))]
 for request in requests:
  try:
   source=board.call('/issues/'+request['source_issue'])
   with database() as db:packet=dict(db.execute('SELECT * FROM '+request['packet_table']+' WHERE packet_hash=?',(request['packet_hash'],)).fetchone())
   candidate={**packet,'status':'awaiting_approval'}
   if source.get('companyId')!=config['company_id'] or source.get('status') not in {'blocked','in_review'} or packet['status']!='superseded' or not allowed(candidate,request['packet_table'],source,board,config) or not stopped(source,board,database):
    with database() as db:db.execute("UPDATE packet_renewals SET status='held',error_category='source_or_policy_changed' WHERE packet_hash=?",(request['packet_hash'],))
    held.append(source['id']);continue
   with database() as db:db.execute("UPDATE packet_renewals SET status='creating' WHERE packet_hash=?",(request['packet_hash'],))
   child=board.call('/companies/'+config['company_id']+'/issues',json.loads(request['body_json']))
   if child.get('companyId')!=config['company_id'] or child.get('projectId')!=source['projectId'] or not child.get('id'):raise ValueError('Invalid renewal receipt')
   with database() as db:db.execute("UPDATE packet_renewals SET status='delivered',target_issue=? WHERE packet_hash=?",(child['id'],request['packet_hash']))
   delivered.append(child['identifier'])
  except Exception as error:
   count=request['attempts']+1
   with database() as db:db.execute('UPDATE packet_renewals SET attempts=?,next_at=?,status=?,error_category=? WHERE packet_hash=?',(count,now+[60,300,900][min(count-1,2)],'needs_attention' if count>=3 else 'creating',type(error).__name__,request['packet_hash']))
 return {'planned':planned,'delivered':delivered,'held':held}
