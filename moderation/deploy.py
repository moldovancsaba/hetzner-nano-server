"""Run on the authorized server after copying sources and unit; preserves other keys/routes."""
import datetime,json,os,pathlib,secrets,subprocess
root=pathlib.Path('/opt/narimato-ai');keyfile=root/'api-keys.json'
keys=json.loads(keyfile.read_text())
if 'camera' not in keys:
    keys['camera']=secrets.token_urlsafe(36)
    tmp=keyfile.with_suffix('.tmp');tmp.write_text(json.dumps(keys,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(keyfile)
key=keys['camera']
if not isinstance(key,str) or len(key)<32:raise RuntimeError('Unexpected camera key shape')
env=pathlib.Path('/etc/narimato-moderation.env');env.write_text('CAMERA_MODERATION_API_KEY='+key+'\n');env.chmod(0o600)
config=pathlib.Path('/etc/caddy/Caddyfile');original=config.read_text()
if '@moderation' not in original:
    source='    request_body {\n        max_size 128KB\n    }\n'
    if source not in original:raise RuntimeError('Caddy structure changed: inspect before applying')
    changed=original.replace(source,'',1)
    marker='    @authorized {'
    block='''    @moderation path /v1/moderation/*
    handle @moderation {
        request_body {
            max_size 6MB
        }
        reverse_proxy 127.0.0.1:8089
    }
'''
    if marker not in changed:raise RuntimeError('Caddy authorization block missing')
    changed=changed.replace(marker,block+marker,1)
    changed=changed.replace('    handle @authorized {','    handle @authorized {\n        request_body {\n            max_size 128KB\n        }',1)
    changed=changed.replace('    handle @chat {','    handle @chat {\n        request_body {\n            max_size 128KB\n        }',1)
    candidate=root/'Caddyfile.moderation-candidate';candidate.write_text(changed);candidate.chmod(0o600)
    check=subprocess.run(['caddy','validate','--config',str(candidate),'--adapter','caddyfile'],capture_output=True,text=True)
    if check.returncode:raise RuntimeError('Candidate Caddy validation failed; original unchanged')
    backup=root/('Caddyfile.before-moderation-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.write_text(original);backup.chmod(0o600)
    config.write_text(changed);config.chmod(0o640)
    subprocess.run(['chown','root:caddy',str(config)],check=True)
    reload=subprocess.run(['systemctl','reload','caddy'],capture_output=True)
    if reload.returncode:
        config.write_text(original);subprocess.run(['systemctl','reload','caddy'],check=True)
        raise RuntimeError('Caddy reload failed; rolled back')
    snapshot=root/'Caddyfile';snapshot.write_text(changed);snapshot.chmod(0o600)
    candidate.unlink()
subprocess.run(['chmod','644','/opt/narimato-moderation/server.py','/opt/narimato-moderation/policy.py'],check=True)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','--now','narimato-moderation'],check=True,capture_output=True)
print('Moderation service enabled; dedicated key stored without printing it.')
