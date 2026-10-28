"""Guarded, rollback-capable deployment of the additive Hungarian job only."""
import hashlib,json,pathlib,subprocess,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent;CODE=pathlib.Path('/opt/narimato-gateway');STAGE=ROOT/'stage'
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def call(path,data=None,key=KEY):
 req=urllib.request.Request('http://127.0.0.1:8090'+path,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Request-Purpose':'test'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def lease(action,value=None):return call('/internal/model-storage',{'action':action,'lease':value})
files=['gateway/hungarian.py','gateway/server.py','gateway/catalog.py','gateway/metrics.py','config/job-routes.json','config/model-policy.json']
baseline=json.loads((STAGE/'baseline.json').read_text())
existed={name:(CODE/name).exists() for name in files}
for name in files:assert (hashlib.sha256((CODE/name).read_bytes()).hexdigest() if existed[name] else None)==baseline[name],'Concurrent deployment detected: '+name
policy=json.loads((STAGE/'config/model-policy.json').read_text());assert 'text_chat_hu' in policy['defaults']
inventory=json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=20))['models']
for task,model in policy['defaults'].items():
 assert any(m['name'].lower()==model.lower() and m['digest']==policy['models'][model]['tested_digest'] for m in inventory), 'Install and verify exact winning artifact with ensure_models.py before deployment: '+model
backup=ROOT/('backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
for name in files:
 if not existed[name]:continue
 p=backup/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((CODE/name).read_bytes());p.chmod(0o600)
index=pathlib.Path('/opt/narimato-discovery/tested-models.json');(backup/'tested-models.json').write_bytes(index.read_bytes())
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
held=None;deployed=False
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for _ in range(450):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 assert held,'No idle deployment lease'
 subprocess.run(['systemctl','stop','narimato-gateway'],check=True)
 for name in files:
  target=CODE/name;tmp=target.with_suffix('.hu.tmp');tmp.write_bytes((STAGE/name).read_bytes());tmp.chmod(0o644);tmp.replace(target)
 tmp=index.with_suffix('.hu.tmp');tmp.write_bytes((STAGE/'tested-models.json').read_bytes());tmp.chmod(0o644);tmp.replace(index)
 subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 keys=json.loads(pathlib.Path('/opt/narimato-ai/api-keys.json').read_text())
 for _ in range(50):
  try:
   d=call('/v1/job-types',key=keys['classscout']);assert d['job_types']['text_chat_hu']['model']==policy['defaults']['text_chat_hu'];assert policy['defaults']['text_chat_hu'] in d['job_types']['text_chat_hu']['available_models'];deployed=True;break
  except Exception:time.sleep(.3)
 assert deployed,'Hungarian discovery startup check failed'
except Exception:
 subprocess.run(['systemctl','stop','narimato-gateway'],capture_output=True)
 for name in files:
  if existed[name]:(CODE/name).write_bytes((backup/name).read_bytes())
  elif (CODE/name).exists():(CODE/name).unlink()
 index.write_bytes((backup/'tested-models.json').read_bytes());subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 raise
finally:
 if held:
  for _ in range(30):
   try:lease('release',held);break
   except Exception:time.sleep(.3)
 if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
audit={'deployed':deployed,'policy_id':policy['policy_id'],'defaults':policy['defaults'],'backup':str(backup),'guarded_idle_restart':True}
(ROOT/'deployment.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
