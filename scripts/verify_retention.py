"""Neutral-data public test: result TTL, tenant isolation and acknowledged deletion."""
import base64,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];keys=json.loads((ROOT/'private/api-keys.json').read_text());base='https://chatbotapi.haho.ai/v1';checks=[]
def req(path,tenant='classscout',data=None,method=None):
 request=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Content-Type':'application/json','X-Request-Purpose':'test','Authorization':'Bearer '+keys[tenant]})
 try:
  with urllib.request.urlopen(request,timeout=20) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as r:return r.code,json.load(r)
def check(name,path,tenant='classscout',data=None,method=None,expected=200):
 status,value=req(path,tenant,data,method);checks.append({'name':name,'status':status,'expected':expected,'passed':status==expected});assert status==expected;return value
def wait(job,tenant):
 for _ in range(90):
  row=check('poll '+tenant,'/jobs/'+job['id'],tenant)
  if row['status'] in ['completed','failed']:break
  time.sleep(2)
 assert row['status']=='completed';return row
report={'checks':checks}
try:
 queue=check('five-minute memory TTL','/queue');assert queue['result_retention_seconds']==300
 job=check('text submit','/jobs',data={'task':'text_chat','input':{'messages':[{'role':'user','content':'Say READY.'}],'max_tokens':12}},expected=202);wait(job,'classscout')
 check('other service cannot delete','/jobs/'+job['id'],'camera',method='DELETE',expected=404)
 check('owner deletes result','/jobs/'+job['id'],method='DELETE');check('result gone','/jobs/'+job['id'],expected=404)
 encoded=base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode();job=check('camera submit','/moderation/jobs','camera',{'image_base64':encoded},expected=202);row=wait(job,'camera');assert row['result']['review_required']
 check('camera deletes via compatibility route','/moderation/jobs/'+job['id'],'camera',method='DELETE');check('camera result gone','/moderation/jobs/'+job['id'],'camera',expected=404)
 report['passed']=True
finally:(ROOT/'results/retention/public-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'result_ttl_seconds':300}))
