"""Deploy the exchange metadata service and gated GDS assets without touching factory workers."""
import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path

REMOTE = r'''
import base64,datetime,hashlib,json,os,pathlib,re,shutil,sqlite3,subprocess,sys,tempfile
payload=json.load(sys.stdin)
root=pathlib.Path('/opt/source-exchange')
config=json.loads(pathlib.Path('/etc/source-exchange/config.json').read_text())
if config.get('source_admission') or config.get('claims_enabled'):raise RuntimeError('Metadata-only deployment requires admission and claims disabled')
if not any(p['id']=='dashboard' and p['token_sha256']==hashlib.sha256(payload['dashboard_token'].encode()).hexdigest() for p in config['principals']):raise RuntimeError('Dashboard principal mismatch')
with sqlite3.connect(config['database']) as db:
 if db.execute('SELECT count(*) FROM messages').fetchone()[0]:raise RuntimeError('Use the business-aware release procedure for a nonempty broker')
backup=pathlib.Path('/var/backups/source-exchange')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,mode=0o700);os.chmod(backup.parent,0o700)
caddy=pathlib.Path('/etc/caddy/Caddyfile');snippet=pathlib.Path('/etc/caddy/source-exchange-dashboard.caddy')
shutil.copy2(caddy,backup/'Caddyfile');had_snippet=snippet.exists()
if had_snippet:shutil.copy2(snippet,backup/'dashboard.caddy')
for name in ['exchange','dashboard']:
 if (root/name).exists():shutil.copytree(root/name,backup/name)
artifacts=['openapi.json','examples.json','release-manifest.json','acceptance-scenarios.json']
for name in artifacts:
 if (root/name).is_file():shutil.copy2(root/name,backup/name)
with sqlite3.connect(config['database']) as original,sqlite3.connect(backup/'exchange.sqlite3') as saved:original.backup(saved)
os.chmod(backup/'exchange.sqlite3',0o600)
old=caddy.read_text()
match=re.search(r'^\t\t\t@company_results path ([^\n]+)$',old,re.M)
if not match or set(match[1].split()) not in ({'/factory','/factory/','/factory/metrics'},{'/factory/metrics'}):raise RuntimeError('Unexpected live Caddy layout; no mutation performed')
start=old.find('\t\t\t@exchange_snapshot ')
if start<0:start=match.start()
if start>match.start():raise RuntimeError('Unexpected owned proxy block')
updated=old[:start]+payload['caddy_block']+payload['company_matcher']+old[match.end():]
try:
 for relative,encoded in payload['files'].items():
  target=root/relative
  if not target.resolve().is_relative_to(root):raise RuntimeError('Invalid artifact path')
  content=base64.b64decode(encoded)
  target.parent.mkdir(parents=True,exist_ok=True)
  temporary=target.with_name(target.name+'.release-tmp');temporary.write_bytes(content);os.chmod(temporary,0o644);temporary.replace(target)
 snippet.write_text('reverse_proxy 127.0.0.1:9091 {\n header_up Authorization "Bearer '+payload['dashboard_token']+'"\n}\n')
 import grp
 os.chown(snippet,0,grp.getgrnam('caddy').gr_gid);os.chmod(snippet,0o640)
 caddy.write_text(updated)
 subprocess.run(['caddy','validate','--config',str(caddy),'--adapter','caddyfile'],check=True,capture_output=True)
 subprocess.run(['systemctl','restart','source-exchange'],check=True,capture_output=True)
 subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
 subprocess.run(['systemctl','is-active','--quiet','source-exchange'],check=True)
 print(json.dumps({'service':'active','caddy':'validated-reloaded','browser_gate':'preserved','source_admission':False,'claims_enabled':False,'backup':str(backup),'files':len(payload['files'])}))
except BaseException:
 shutil.copy2(backup/'Caddyfile',caddy)
 if had_snippet:shutil.copy2(backup/'dashboard.caddy',snippet)
 elif snippet.exists():snippet.unlink()
 for name in ['exchange','dashboard']:
  if (backup/name).exists():
   if (root/name).exists():shutil.rmtree(root/name)
   shutil.copytree(backup/name,root/name)
 for name in artifacts:
  if (backup/name).is_file():shutil.copy2(backup/name,root/name)
  elif (root/name).exists(): (root/name).unlink()
 subprocess.run(['systemctl','restart','source-exchange'],capture_output=True)
 subprocess.run(['systemctl','reload','caddy'],capture_output=True)
 raise RuntimeError('Deployment failed; previous code and proxy restored') from None
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',required=True)
    parser.add_argument('--ssh-key',required=True)
    parser.add_argument('--credentials',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    integration=Path(__file__).resolve().parent.parent
    paperclip=integration.parent
    build=paperclip/'dashboard/dist'
    if not (build/'index.html').is_file():raise RuntimeError('Build the reviewed dashboard first')
    files={}
    for prefix,source in [('exchange',integration/'exchange'),('dashboard',build)]:
        for path in source.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or (prefix=='exchange' and path.suffix!='.py'):continue
            if path.is_symlink():raise RuntimeError('Symlink artifacts are not supported')
            files[prefix+'/'+str(path.relative_to(source))]=base64.b64encode(path.read_bytes()).decode()
    manifest=json.loads((integration/'release-manifest.json').read_text())
    for name in ['openapi.json','examples.json','release-manifest.json','acceptance-scenarios.json']:
        content=(integration/name).read_bytes()
        if name in manifest['files'] and hashlib.sha256(content).hexdigest()!=manifest['files'][name]:raise RuntimeError('Canonical release manifest does not match '+name)
        files[name]=base64.b64encode(content).decode()
    digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    if not args.apply:
        print(json.dumps({'apply':False,'files':len(files),'artifact_sha256':digest}));return
    credential_path=Path(args.credentials)
    if credential_path.stat().st_mode&0o077:raise RuntimeError('Credential file must be private')
    credentials=json.loads(credential_path.read_text())
    caddy=(paperclip/'Caddyfile').read_text()
    start=caddy.index('\t\t\t@exchange_snapshot ');end=caddy.index('\t\t\t@company_results ',start)
    matcher=caddy[end:].splitlines()[0]
    body={'files':files,'dashboard_token':credentials['dashboard']['token'],'caddy_block':caddy[start:end],'company_matcher':matcher}
    # Remote code reads private material from stdin, never process arguments or environment.
    import shlex
    result=subprocess.run(['ssh','-i',args.ssh_key,'-o','BatchMode=yes','-o','ConnectTimeout=10',args.host,'python3 -c '+shlex.quote(REMOTE)],input=json.dumps(body).encode(),capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError('Remote deployment refused or rolled back; inspect the private host release logs')
    response=json.loads(result.stdout)
    print(json.dumps({**response,'artifact_sha256':digest}))


if __name__=='__main__':main()
