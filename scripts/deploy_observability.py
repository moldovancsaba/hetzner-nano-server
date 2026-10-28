"""Deploy reviewed operational telemetry under the existing idle maintenance guard."""
import ast,hashlib,json,pathlib,subprocess,time,urllib.error,urllib.request
STAGE=pathlib.Path('/opt/narimato-observability-stage');CODE=pathlib.Path('/opt/narimato-gateway')
KEY=next(x.split('=',1)[1].strip().strip('"').strip("'") for x in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if x.startswith('GATEWAY_MAINTENANCE_KEY='))
expected=json.loads((STAGE/'baseline.json').read_text())
assert hashlib.sha256((CODE/'gateway/server.py').read_bytes()).hexdigest()==expected['server_sha256'],'Live source changed; review before deployment'
for name in ['gateway/server.py','gateway/metrics.py','scripts/usage_report.py']:ast.parse((STAGE/name).read_text())
config=pathlib.Path('/etc/caddy/Caddyfile');old=config.read_text();new=old if '@gateway path /v1/usage ' in old else old.replace('@gateway path /v1/models ', '@gateway path /v1/usage /v1/models ');assert '@gateway path /v1/usage ' in new
candidate=STAGE/'Caddyfile.reviewed';candidate.write_text(new);candidate.chmod(0o600)
assert subprocess.run(['caddy','validate','--config',str(candidate),'--adapter','caddyfile'],capture_output=True).returncode==0
backup=pathlib.Path('/opt/narimato-ai')/('observability-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
files=['gateway/server.py','gateway/metrics.py','scripts/usage_report.py'];existed={name:(CODE/name).exists() for name in files}
for name in files:
 if existed[name]:
  out=backup/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((CODE/name).read_bytes());out.chmod(0o600)
(backup/'Caddyfile').write_text(old);(backup/'Caddyfile').chmod(0o600)
def lease(action,token=None):
 req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':token}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY,'X-Request-Purpose':'test'})
 with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True);held=None
try:
 for _ in range(300):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(1)
 assert held,'No idle window; stop without modifying source'
 subprocess.run(['systemctl','stop','narimato-gateway'],check=True)
 for name in files:
  target=CODE/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((STAGE/name).read_bytes());target.chmod(0o644)
 subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 keys=json.loads(pathlib.Path('/opt/narimato-ai/api-keys.json').read_text())
 for _ in range(40):
  try:
   req=urllib.request.Request('http://127.0.0.1:8090/v1/usage?hours=12',headers={'Authorization':'Bearer '+keys['classscout'],'X-Request-Purpose':'test'})
   with urllib.request.urlopen(req,timeout=10) as response:assert json.load(response)['schema_version']=='operational-usage.v1'
   break
  except (OSError,urllib.error.URLError):time.sleep(.3)
 else:raise RuntimeError('Telemetry startup check did not pass')
 config.write_text(new);config.chmod(0o640);subprocess.run(['chown','root:caddy',str(config)],check=True)
 subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
 print(json.dumps({'deployed':True,'backup':str(backup),'telemetry_started':True,'existing_model_policy_preserved':True}))
except Exception:
 subprocess.run(['systemctl','stop','narimato-gateway'],capture_output=True)
 for name in files:
  target=CODE/name
  if existed[name]:target.write_bytes((backup/name).read_bytes())
  elif target.exists():target.unlink()
 config.write_text(old);config.chmod(0o640);subprocess.run(['chown','root:caddy',str(config)],check=True)
 subprocess.run(['systemctl','start','narimato-gateway'],capture_output=True);subprocess.run(['systemctl','reload','caddy'],capture_output=True);raise
finally:
 if held:
  try:lease('release',held)
  except Exception:pass
 if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
