"""Public deployment verification using a non-sensitive existing cats fixture."""
import base64,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];keys=json.loads((ROOT/'private/api-keys.json').read_text());BASE='https://chatbotapi.haho.ai'
checks=[]
def request(path,key=None,data=None,headers=None):
 h={'Content-Type':'application/json','X-Request-Purpose':'test',**(headers or {})}
 if key:h['Authorization']='Bearer '+key
 req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as r:
  try:body=json.load(r)
  except Exception:body={}
  return r.code,body

def check(name,path,key,expected,data=None):
 status,body=request(path,key,data);checks.append({'name':name,'status':status,'expected':expected,'passed':status==expected});assert status==expected,(name,status);return body
try:
 check('missing key','/v1/moderation/health',None,401)
 check('invalid key','/v1/moderation/health','invalid-test',401)
 check('classscout key excluded','/v1/moderation/health',keys['classscout'],401)
 check('habigoal key excluded','/v1/moderation/health',keys['habigoal'],401)
 check('camera key health','/v1/moderation/health',keys['camera'],200)
 check('camera key not chat','/v1/chat/completions',keys['camera'],401,{})
 check('URL input rejected','/v1/moderation/jobs',keys['camera'],400,{'image_url':'https://example.org/a.jpg'})
 check('invalid image rejected','/v1/moderation/jobs',keys['camera'],400,{'image_base64':base64.b64encode(b'not image').decode()})
 payload={'image_base64':base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode()}
 started=time.monotonic();job=check('real image submit','/v1/moderation/jobs',keys['camera'],202,payload)
 polls=[]
 for _ in range(100):
  status,row=request('/v1/moderation/jobs/'+job['id'],keys['camera']);assert status==200;polls.append(row['status'])
  if row['status'] in ['completed','failed']:break
  time.sleep(2)
 assert row['status']=='completed',row
 result=row['result'];assert result['review_required'] is True and result['automated_decision']=='none';assert len(result['categories'])==9
 checks.append({'name':'real job completed with review-only result','passed':True})
 report={'checks':checks,'job':row,'poll_statuses':polls,'wall_seconds':round(time.monotonic()-started,3)}
finally:
 if 'report' not in globals():report={'checks':checks,'verification_failed':True}
 (ROOT/'results/moderation-api/public-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':all(c['passed'] for c in checks),'checks':len(checks),'job_signal':row['result']['signal'],'seconds':report['wall_seconds']}))
