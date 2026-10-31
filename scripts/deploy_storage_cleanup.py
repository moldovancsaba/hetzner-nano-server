"""Server-side controlled update for content-free usage tracking and cleanup.

It rolled out usage tracking and the storage policy. It did not install storage/cleaner.py or the cleanup timer.
"""
import ast,json,pathlib,secrets,subprocess,time,urllib.request
ROOT=pathlib.Path('/opt/narimato-ai');STAGE=pathlib.Path('/opt/narimato-storage-update')
files={
 'gateway/server.py':pathlib.Path('/opt/narimato-gateway/gateway/server.py'),
 'gateway/usage.py':pathlib.Path('/opt/narimato-gateway/gateway/usage.py'),
 'chat/server.py':pathlib.Path('/opt/narimato-chat/server.py'),
 'config/narimato-gateway.service':pathlib.Path('/etc/systemd/system/narimato-gateway.service'),
 'config/model-storage-policy.json':ROOT/'model-storage-policy.json'}
for name in files:
 text=(STAGE/name).read_text()
 if name.endswith('.py'):ast.parse(text)
backup=ROOT/('storage-update-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));backup.mkdir(mode=0o700)
for name,target in files.items():
 if target.exists():p=backup/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(target.read_bytes());p.chmod(0o600)
secret=pathlib.Path('/etc/narimato-model-cleanup.env')
if not secret.exists():secret.write_text('GATEWAY_MAINTENANCE_KEY='+secrets.token_urlsafe(40)+'\n');secret.chmod(0o600)
keys=json.loads((ROOT/'api-keys.json').read_text());caddy=pathlib.Path('/etc/caddy/Caddyfile');original=caddy.read_text()
maintenance=ROOT/'Caddyfile.storage-maintenance';maintenance.write_text('chatbotapi.haho.ai {\n    respond "Service update; retry shortly" 503\n}\n');maintenance.chmod(0o600)
assert subprocess.run(['caddy','validate','--config',str(maintenance),'--adapter','caddyfile'],capture_output=True).returncode==0

def apply(text):
 caddy.write_text(text);caddy.chmod(0o640);subprocess.run(['chown','root:caddy',str(caddy)],check=True);subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
def get():
 request=urllib.request.Request('http://127.0.0.1:8090/v1/queue',headers={'Authorization':'Bearer '+keys['classscout']})
 with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
try:
 apply(maintenance.read_text());subprocess.run(['systemctl','stop','narimato-chat'],check=True)
 for _ in range(180):
  state=get()
  if not state['active_task'] and not state['queued'] and not state.get('model_storage_maintenance',False):break
  time.sleep(1)
 else:raise RuntimeError('Queue not drained')
 if state['status']!='ok':raise RuntimeError('Gateway requires recovery first')
 subprocess.run(['systemctl','stop','narimato-gateway'],check=True)
 for name,target in files.items():target.write_bytes((STAGE/name).read_bytes());target.chmod(0o644)
 subprocess.run(['systemctl','daemon-reload'],check=True)
 subprocess.run(['systemctl','start','narimato-gateway'],check=True)
 for _ in range(40):
  try:assert 'model_storage_maintenance' in get();break
  except Exception:time.sleep(.3)
 else:raise RuntimeError('Gateway not ready')
 assert pathlib.Path('/var/lib/narimato-gateway/model-usage.json').exists()
 apply(original);subprocess.run(['systemctl','start','narimato-chat'],check=True);maintenance.unlink();print('Usage tracking active; metadata initialized without reconstructing customer history.')
except Exception:
 subprocess.run(['systemctl','stop','narimato-gateway'],capture_output=True)
 for name,target in files.items():
  if (backup/name).exists():target.write_bytes((backup/name).read_bytes())
  elif target.exists():target.unlink()
 subprocess.run(['systemctl','daemon-reload'],capture_output=True);subprocess.run(['systemctl','start','narimato-gateway'],capture_output=True);apply(original);subprocess.run(['systemctl','start','narimato-chat'],capture_output=True);raise
