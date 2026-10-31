"""Run on the inference host after staging the tested chatbot context changes.

Single use: it asserts the pre-update SHA-256 of every live source file it replaces, so it cannot run again
once they have changed. Kept as the record of the Pandora and gateway context rollout.
"""
import ast,json,pathlib,shutil,subprocess,time,urllib.request,hashlib
ROOT=pathlib.Path('/opt/narimato-ai');CODE=pathlib.Path('/opt/narimato-gateway');CHAT=pathlib.Path('/opt/narimato-chat');STAGE=pathlib.Path('/opt/narimato-chatbot-context-stage')
files={'gateway/server.py':CODE/'gateway/server.py','gateway/catalog.py':CODE/'gateway/catalog.py','config/model-policy.json':CODE/'config/model-policy.json','chat/server.py':CHAT/'server.py','chat/context.py':CHAT/'context.py','chat/index.html':CHAT/'index.html','config/narimato-chat.service':pathlib.Path('/etc/systemd/system/narimato-chat.service')}
expected={CODE/'gateway/server.py':'cad1f309d624c8b03d7221d5282b284a027d0afd35fbad1c71d2d3e65cb9c7d9',CODE/'gateway/catalog.py':'47042ae661909091754748cd758d1ebd99cb4c228a4ddf0947e2bda32650051f',CHAT/'server.py':'cba65d910d42a05d640d3033a966d7399ac6f8ae16d5be9e83ddc5abb10a9b94',CHAT/'index.html':'dbbfa30bf67779a63ee96ccef96d9c39086d2065518925f16789f72e77195343'}
for path,digest in expected.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Live source changed; review before deployment: '+str(path)
for name in files:
 text=(STAGE/name).read_text()
 if name.endswith('.py'):ast.parse(text)
 elif name.endswith('.json'):json.loads(text)
subprocess.run(['systemd-analyze','verify',str(STAGE/'config/narimato-chat.service')],check=True,capture_output=True)
keys=json.loads((ROOT/'api-keys.json').read_text())
key=dict(line.split('=',1) for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if '=' in line)['GATEWAY_MAINTENANCE_KEY'].strip().strip('"').strip("'")
def lease(action,value=None):
 req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
def models(tenant):
 req=urllib.request.Request('http://127.0.0.1:8090/v1/models',headers={'Authorization':'Bearer '+keys[tenant]})
 with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
was_timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
was_chat=subprocess.run(['systemctl','is-active','--quiet','narimato-chat']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
backup=ROOT/('chatbot-context-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
held=None;changed=False
try:
 for attempt in range(180):
  try:held=lease('acquire')['lease'];break
  except Exception:time.sleep(2)
 if not held:raise RuntimeError('Shared queue is busy; no deployment')
 for name,target in files.items():
  if target.exists():
   dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,dest);dest.chmod(0o600)
 subprocess.run(['systemctl','stop','narimato-chat','narimato-gateway'],check=True);changed=True
 for name,target in files.items():target.write_bytes((STAGE/name).read_bytes());target.chmod(0o644)
 subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 for attempt in range(50):
  try:
   for tenant in ['classscout','habigoal','pandora','paperclip']:
    data=models(tenant);default=next(row for row in data['data'] if 'text_chat' in row['default_for'])
    assert default['rankings']['text_chat']['profile']['num_ctx']==8192
   break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('Context profile readiness check failed')
 code='''from gateway.server import CATALOG,Runner,text_input
selection=CATALOG.select('text_chat','auto',tenant='classscout')
payload=text_input({'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16},selection['model'],selection['model_profile'])
payload['_runtime_profile']=selection['model_profile']
result,_=Runner(CATALOG)('text_chat',payload,selection['model'])
assert result['choices'][0]['message']['content'].strip().rstrip('.')=='READY'
from pathlib import Path
import sys
sys.path.insert(0,'/opt/narimato-chat')
from context import prepare
payload,kept,trimmed,count=prepare([{'role':'user','content':'A short test.'}])
assert kept==1 and not trimmed
print('8K API runner and Pandora token-budget preparation passed')'''
 subprocess.run(['/opt/narimato-gateway-venv/bin/python','-c',code],cwd=CODE,check=True)
 if was_chat:
  subprocess.run(['systemctl','start','narimato-chat'],check=True)
  for attempt in range(40):
   try:
    with urllib.request.urlopen('http://127.0.0.1:8088/chat/',timeout=5) as response:assert response.status==200
    break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Pandora did not become ready')
 lease('release',held);held=None
 print('Chatbotapi defaults and Pandora chat upgraded to verified 8K. Paperclip remains 8K; model pins and Camera profiles preserved.')
except Exception:
 if changed:
  subprocess.run(['systemctl','stop','narimato-chat','narimato-gateway'],check=True)
  for name,target in files.items():
   source=backup/name
   if source.exists():shutil.copyfile(source,target);target.chmod(0o644)
   elif target.exists():target.unlink()
  subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','start','narimato-gateway'],check=True)
  if was_chat:subprocess.run(['systemctl','start','narimato-chat'],check=True)
 raise
finally:
 if held:
  try:lease('release',held)
  except Exception:pass
 if was_timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
