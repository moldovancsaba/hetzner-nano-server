"""Neutral live verification; no production-use events are created by these tests."""
import json,subprocess,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def remote(code):
 result=subprocess.run(['ssh','-i','/Users/chappie/.ssh/hetzner_ai','-o','BatchMode=yes','root@2.31.100.246','python3 -'],input=code,text=True,capture_output=True,check=True)
 return json.loads(result.stdout)
read="import json; print(json.dumps(json.load(open('/var/lib/narimato-gateway/model-usage.json'))))"
before=remote(read);keys=json.loads((ROOT/'private/api-keys.json').read_text())
req=urllib.request.Request('https://chatbotapi.haho.ai/v1/jobs',data=json.dumps({'task':'text_chat','input':{'messages':[{'role':'user','content':'Say READY.'}],'max_tokens':12}}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+keys['classscout'],'X-Request-Purpose':'test'})
with urllib.request.urlopen(req,timeout=20) as response:job=json.load(response)
after=remote(read);assert before['models']==after['models'],'Concurrent production traffic or unexpected usage mutation; inspect privately'
report={'tagged_test_does_not_update_usage':True,'tracking_initialized':True}
initial=ROOT/'results/auto-cleanup/initial-cleanup.json'
if initial.exists():
 report['initial_grace_survives_restart']=before['tracking_started_at']==json.loads(initial.read_text())['usage_tracking_started_at']
 assert report['initial_grace_survives_restart']
lease=remote('''import json,urllib.request,urllib.error
keys=json.load(open('/opt/narimato-ai/api-keys.json'));key=open('/etc/narimato-model-cleanup.env').read().strip().split('=',1)[1]
def call(path,payload,provided):
 req=urllib.request.Request('http://127.0.0.1:8090'+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+provided,'X-Request-Purpose':'test'})
 try:
  with urllib.request.urlopen(req,timeout=10) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as response:return response.code,json.load(response)
import time
for _ in range(40):
 status,data=call('/internal/model-storage',{'action':'acquire'},key)
 if status==200:break
 time.sleep(.5)
assert status==200
try:
 status,_=call('/v1/jobs',{'task':'text_chat','input':{'messages':[{'role':'user','content':'test'}]}},keys['classscout']);assert status==503
 denied,_=call('/internal/model-storage',{'action':'renew','lease':data['lease']},keys['classscout']);assert denied==401
 print(json.dumps({'lease_blocks_new_requests':True,'normal_project_key_cannot_manage_cleanup':True}))
finally:call('/internal/model-storage',{'action':'release','lease':data['lease']},key)
''');report.update(lease)
(ROOT/'results/auto-cleanup/public-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
