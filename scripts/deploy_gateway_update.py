"""Run on Hetzner after staging reviewed files in /opt/narimato-gateway-update.

It ships only the five files in FILES. The gateway modules added later (usage.py, metrics.py, hungarian.py,
long_context.py) are not among them, so it cannot update today's gateway on its own.
"""
import ast,json,pathlib,subprocess,time,urllib.request
ROOT=pathlib.Path('/opt/narimato-ai');CODE=pathlib.Path('/opt/narimato-gateway');STAGE=pathlib.Path('/opt/narimato-gateway-update')
FILES=['gateway/server.py','gateway/catalog.py','moderation/server.py','config/model-policy.json','config/job-routes.json']
keys=json.loads((ROOT/'api-keys.json').read_text());config=pathlib.Path('/etc/caddy/Caddyfile');original=config.read_text()
for name in FILES:
 text=(STAGE/name).read_text()
 if name.endswith('.py'):ast.parse(text)
 else:json.loads(text)
backup=ROOT/('ranked-gateway-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
for name in FILES:
 target=CODE/name
 if target.exists():
  out=backup/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(target.read_bytes());out.chmod(0o600)
maintenance=ROOT/'Caddyfile.ranked-maintenance';maintenance.write_text('chatbotapi.haho.ai {\n    respond "Service update; retry shortly" 503\n}\n');maintenance.chmod(0o600)
assert subprocess.run(['caddy','validate','--config',str(maintenance),'--adapter','caddyfile'],capture_output=True).returncode==0

def apply(text):
 config.write_text(text);config.chmod(0o640);subprocess.run(['chown','root:caddy',str(config)],check=True);subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
def get(path,tenant='classscout'):
 request=urllib.request.Request('http://127.0.0.1:8090'+path,headers={'Authorization':'Bearer '+keys[tenant]})
 with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
try:
 apply(maintenance.read_text());subprocess.run(['systemctl','stop','narimato-chat'],check=True)
 for _ in range(180):
  state=get('/v1/queue')
  if not state['queued'] and not state['active_task'] and not state.get('model_storage_maintenance',False):break
  time.sleep(1)
 else:raise RuntimeError('Queue not drained')
 if state['status']!='ok':raise RuntimeError('Recover upstream before update')
 subprocess.run(['systemctl','stop','narimato-gateway'],check=True)
 for name in FILES:(CODE/name).write_bytes((STAGE/name).read_bytes());(CODE/name).chmod(0o644)
 subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 for _ in range(40):
  try:
   for tenant in ['classscout','camera']:
    discovery=get('/v1/job-types',tenant)
    assert discovery['version']=='job-router.v2'
    assert all(spec['model'] in spec['available_models'] for spec in discovery['job_types'].values())
   break
  except Exception:time.sleep(.3)
 else:raise RuntimeError('Ranked defaults are not ready/installed/tested')
 apply(original);subprocess.run(['systemctl','start','narimato-chat'],check=True);maintenance.unlink();print('Ranked defaults and installed-model selection live; queue drained before update.')
except Exception:
 subprocess.run(['systemctl','stop','narimato-gateway'],capture_output=True)
 for name in FILES:
  target=CODE/name
  if (backup/name).exists():target.write_bytes((backup/name).read_bytes())
  elif target.exists():target.unlink()
 subprocess.run(['systemctl','start','narimato-gateway'],capture_output=True);apply(original);subprocess.run(['systemctl','start','narimato-chat'],capture_output=True);raise
