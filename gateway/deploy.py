"""Server-side cutover: stop direct callers, drain Ollama, then expose one queue."""
import json,pathlib,secrets,subprocess,time,urllib.request
ROOT=pathlib.Path('/opt/narimato-ai');CODE=pathlib.Path('/opt/narimato-gateway')
keysfile=ROOT/'api-keys.json';keys=json.loads(keysfile.read_text())
if 'pandora' not in keys:
    keys['pandora']=secrets.token_urlsafe(36)
    tmp=keysfile.with_suffix('.tmp');tmp.write_text(json.dumps(keys,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(keysfile)
assert all(isinstance(keys.get(t),str) and len(keys[t])>=32 for t in ['classscout','habigoal','camera','pandora'])
secret=pathlib.Path('/etc/narimato-model-cleanup.env')
if not secret.exists():secret.write_text('GATEWAY_MAINTENANCE_KEY='+secrets.token_urlsafe(40)+'\n');secret.chmod(0o600)
env=pathlib.Path('/etc/narimato-gateway.env');env.write_text(''.join('GATEWAY_'+t.upper()+'_KEY='+keys[t]+'\n' for t in ['classscout','habigoal','camera','pandora']));env.chmod(0o600)
config=pathlib.Path('/etc/caddy/Caddyfile');original=config.read_text()
if '@gateway' in original:raise RuntimeError('Already cut over; use controlled source update instead')
start=original.index('    @moderation');end=original.index('    @chat path')
assert '127.0.0.1:11434' in original[start:end]
block='''    @gateway path /v1/models /v1/chat/completions /v1/jobs /v1/jobs/* /v1/job-types /v1/queue /v1/moderation/*
    handle @gateway {
        request_body {
            max_size 6MB
        }
        reverse_proxy 127.0.0.1:8090
    }
'''
changed=original[:start]+block+original[end:]
maintenance='chatbotapi.haho.ai {\n    respond "Service update; retry shortly" 503\n}\n'
def validate(text,name):
    path=ROOT/name;path.write_text(text);path.chmod(0o600)
    result=subprocess.run(['caddy','validate','--config',str(path),'--adapter','caddyfile'],capture_output=True)
    if result.returncode:raise RuntimeError('Caddy validation failed')
    return path
candidate=validate(changed,'Caddyfile.gateway-candidate');maint=validate(maintenance,'Caddyfile.gateway-maintenance')
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());backup=ROOT/('gateway-backup-'+stamp);backup.mkdir(mode=0o700)
chat=pathlib.Path('/opt/narimato-chat/server.py');chatenv=pathlib.Path('/etc/narimato-chat.env');oldchat=chat.read_text();oldenv=chatenv.read_text()
for name,text in [('Caddyfile',original),('chat-server.py',oldchat),('chat.env',oldenv)]:
    p=backup/name;p.write_text(text);p.chmod(0o600)
def apply(text):
    config.write_text(text);config.chmod(0o640);subprocess.run(['chown','root:caddy',str(config)],check=True)
    subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
def native(path,body=None):
    request=urllib.request.Request('http://127.0.0.1:11434'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=150) as response:return json.load(response)
try:
    apply(maintenance)
    subprocess.run(['systemctl','stop','narimato-chat','narimato-moderation'],check=True)
    for item in native('/api/ps').get('models',[]):native('/api/generate',{'model':item['name'],'keep_alive':0})
    for _ in range(40):
        if not native('/api/ps').get('models'):break
        time.sleep(.25)
    else:raise RuntimeError('Could not drain resident models')
    chat.write_text((CODE/'chat/server.py').read_text());chat.chmod(0o644)
    lines=[line for line in oldenv.splitlines() if not line.startswith('GATEWAY_PANDORA_KEY=')]
    chatenv.write_text('\n'.join(lines)+'\nGATEWAY_PANDORA_KEY='+keys['pandora']+'\n');chatenv.chmod(0o600)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','narimato-gateway'],check=True,capture_output=True)
    for _ in range(30):
        try:
            req=urllib.request.Request('http://127.0.0.1:8090/v1/queue',headers={'Authorization':'Bearer '+keys['classscout']})
            with urllib.request.urlopen(req,timeout=2) as response:assert json.load(response)['status']=='ok'
            break
        except Exception:time.sleep(.3)
    else:raise RuntimeError('Gateway failed readiness')
    apply(changed)
    subprocess.run(['systemctl','start','narimato-chat'],check=True)
    subprocess.run(['systemctl','disable','narimato-moderation'],check=True,capture_output=True)
    snapshot=ROOT/'Caddyfile';snapshot.write_text(changed);snapshot.chmod(0o600)
    candidate.unlink();maint.unlink()
    print('Shared gateway active; prior config and chat source backed up privately.')
except Exception:
    subprocess.run(['systemctl','stop','narimato-gateway'],capture_output=True)
    chat.write_text(oldchat);chatenv.write_text(oldenv);chatenv.chmod(0o600)
    apply(original)
    subprocess.run(['systemctl','start','narimato-chat','narimato-moderation'],capture_output=True)
    raise
