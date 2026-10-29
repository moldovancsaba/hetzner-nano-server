"""Controlled, lease-protected context-profile deployment; run on inference host."""
import ast, hashlib, json, pathlib, secrets, shutil, subprocess, time, urllib.request
ROOT=pathlib.Path('/opt/narimato-ai');CODE=pathlib.Path('/opt/narimato-gateway');STAGE=pathlib.Path('/opt/narimato-context-stage')
FILES=['gateway/server.py','gateway/catalog.py','gateway/long_context.py','config/model-policy.json','config/job-routes.json']
EXPECTED='cea4374e8b8896deb5c2052b399a10b6cfa32b76bb380d6dc2982dbf49b42263'
assert hashlib.sha256((CODE/'gateway/server.py').read_bytes()).hexdigest()==EXPECTED,'Live gateway changed; review before deployment'
for name in FILES:
 text=(STAGE/name).read_text()
 if name.endswith('.py'):ast.parse(text)
 else:json.loads(text)
subprocess.run(['/opt/narimato-gateway-venv/bin/python','-c','from tokenizers import Tokenizer; Tokenizer.from_file("/opt/narimato-gateway/tokenizers/granite4-h-1b.json")'],check=True)
key=dict(line.split('=',1) for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if '=' in line)['GATEWAY_MAINTENANCE_KEY'].strip().strip('"').strip("'")
def lease(action,value=None):
 req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
was_timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
backup=ROOT/('context-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
held=None;changed=False
unit=pathlib.Path('/etc/systemd/system/narimato-gateway.service');env=pathlib.Path('/etc/narimato-gateway.env');keysfile=ROOT/'api-keys.json'
targets=[(CODE/name,backup/name) for name in FILES]+[(unit,backup/'service'),(env,backup/'gateway.env'),(keysfile,backup/'api-keys.json')]
for target,dest in targets:
 if target.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,dest);dest.chmod(0o600)
try:
 for attempt in range(90):
  try:held=lease('acquire')['lease'];break
  except Exception:time.sleep(2)
 if not held:raise RuntimeError('Queue not drained; no deployment')
 keys=json.loads(keysfile.read_text());keys.setdefault('paperclip',secrets.token_urlsafe(36))
 oldunit=unit.read_text();oldcommand='ExecStart=/usr/bin/python3 /opt/narimato-gateway/gateway/server.py'
 assert oldunit.count(oldcommand)==1
 newunit=oldunit.replace(oldcommand,'Environment=TOKENIZERS_PARALLELISM=false\nExecStart=/opt/narimato-gateway-venv/bin/python /opt/narimato-gateway/gateway/server.py')
 subprocess.run(['systemctl','stop','narimato-gateway'],check=True);changed=True
 for name in FILES:
  target=CODE/name;target.write_bytes((STAGE/name).read_bytes());target.chmod(0o644)
 unit.write_text(newunit);unit.chmod(0o644)
 content=env.read_text()
 if 'GATEWAY_PAPERCLIP_KEY=' not in content:env.write_text(content.rstrip()+'\nGATEWAY_PAPERCLIP_KEY='+keys['paperclip']+'\n')
 env.chmod(0o600)
 keysfile.write_text(json.dumps(keys,indent=2)+'\n');keysfile.chmod(0o600)
 subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 for attempt in range(50):
  try:
   req=urllib.request.Request('http://127.0.0.1:8090/v1/models',headers={'Authorization':'Bearer '+keys['paperclip']})
   with urllib.request.urlopen(req,timeout=5) as r:discovery=json.load(r)
   default=discovery['defaults']['text_chat'];model=next(m for m in discovery['data'] if m['id']==default)
   assert model['rankings']['text_chat']['profile']['num_ctx']==8192
   break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('Context gateway did not become ready')
 # Exercise the actual production conversion path while new work is excluded.
 code='''from gateway.server import CATALOG,Runner,text_input
selection=CATALOG.select('text_chat','auto',tenant='paperclip');profile=selection['model_profile']
request=text_input({'model':'auto','messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16},selection['model'],profile)
request['_runtime_profile']=profile
result,_=Runner(CATALOG)('text_chat',request,selection['model'])
assert result['choices'][0]['message']['content'].strip().rstrip('.')=='READY',result
print('Native 8K gateway path verified')'''
 subprocess.run(['/opt/narimato-gateway-venv/bin/python','-c',code],cwd=CODE,check=True)
 lease('release',held);held=None
 print('8K Paperclip context profile deployed; other consumers retain their tested context profiles and credentials.')
except Exception:
 if changed:
  subprocess.run(['systemctl','stop','narimato-gateway'],check=True)
  for target,source in targets:
   if source.exists():shutil.copyfile(source,target);target.chmod(0o600 if target in [env,keysfile] else 0o644)
   elif target.exists():target.unlink()
  subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 raise
finally:
 if held:
  try:lease('release',held)
  except Exception:pass
 if was_timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
