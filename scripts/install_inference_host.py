#!/usr/bin/env python3
"""Install or update the inference host (narimato-chatbot) from this repository, safely and as often as needed.

Usage: python3 scripts/install_inference_host.py [--apply] [--restart] [--force] [--host root@IP] [--identity KEY]
Default is a read-only plan: every managed file is OK, UPDATE (the repository is newer), BLOCKED (the host copy was changed
by hand or the difference is more than comments, so a person must look; --force overrides) or MISSING. Nothing is changed
without --apply. Re-running with nothing to do changes nothing, so the script replaces the single-use scripts/deploy_*.py.

--apply stages each changed file next to its target, validates it (Python compiles, JSON parses, Caddy validates), copies the
old file to /root/narimato-install-backup-<time>/, then replaces it atomically, keeping the owner and mode of the old file.
Files that differ only in comments are installed without any restart. A change to code or a unit needs its service restarted,
which happens only with --restart: the gateway is restarted only after the maintenance lease (no active job, empty queue) was
acquired, and a restart that fails the health check is rolled back from the backup. Compose changes are installed but never
applied; run docker compose up -d by hand after reading the diff, because it reloads the model. The host's record of what
this script installed is /var/lib/narimato-install/manifest.json: a file that differs from both that record and the
repository was edited on the host and is BLOCKED. Credentials (/etc/narimato-*.env) are only checked for presence.

Not managed on purpose: the retired moderation service, /opt/narimato-gateway/{chat,moderation} duplicates of old
deployments, the *-stage and *-update directories, benchmarks, and api-keys.json. The Granite tokenizer is verified by hash
and downloaded only when absent. Never run this from a checkout that is behind the commit you mean to release.
"""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
HOST='root@2.31.100.246'
G='/opt/narimato-gateway/'
UNIT_DIR='/etc/systemd/system/'
MANIFEST='/var/lib/narimato-install/manifest.json'
TOKENIZER=(G+'tokenizers/granite4-h-1b.json','e2bad66439538cb4d5a7580680932432ed9ece9d3b8577e675512bdf11599253','https://huggingface.co/ibm-granite/granite-4.0-h-1b/resolve/main/tokenizer.json')
ENV_FILES=('/etc/narimato-gateway.env','/etc/narimato-chat.env','/etc/narimato-model-cleanup.env','/etc/narimato-monitor.env')
SERVICES=('narimato-gateway','narimato-chat','narimato-monitor')
TIMERS=('narimato-model-cleanup.timer','narimato-model-discovery.timer')
def managed():
 """(repository path, host path, service to restart after a real change or '' for none, kind)."""
 m=[('gateway/%s.py'%n,G+'gateway/%s.py'%n,'narimato-gateway','py') for n in ('server','catalog','long_context','usage','metrics','hungarian')]
 m+=[('moderation/%s.py'%n,G+'moderation/%s.py'%n,'narimato-gateway','py') for n in ('policy','server')]
 m+=[('operations/%s.py'%n,G+'operations/%s.py'%n,'narimato-monitor','py') for n in ('monitor','alerts','notifications')]
 m+=[('scripts/usage_report.py',G+'scripts/usage_report.py','','py'),('config/job-routes.json',G+'config/job-routes.json','narimato-gateway','json'),('config/model-policy.json',G+'config/model-policy.json','','json')]
 m+=[('chat/%s'%n,'/opt/narimato-chat/'+n,'narimato-chat','py' if n.endswith('.py') else 'text') for n in ('server.py','context.py','index.html','login.html')]
 m+=[('storage/cleaner.py','/opt/narimato-model-cleanup/cleaner.py','','py'),('research/collect.py','/opt/narimato-discovery/collect.py','','py')]
 m+=[('config/'+n,'/opt/narimato-discovery/'+n,'','json') for n in ('model-discovery.json','tested-models.json')]
 m+=[('config/model-storage-policy.json','/opt/narimato-ai/model-storage-policy.json','','json'),('config/compose.yaml','/opt/narimato-ai/compose.yaml','COMPOSE','text')]
 m+=[('config/%s.service'%s,UNIT_DIR+'%s.service'%s,s,'unit') for s in SERVICES+('narimato-model-cleanup','narimato-model-discovery')]
 m+=[('config/'+t,UNIT_DIR+t,'','unit') for t in TIMERS]
 m+=[('config/Caddyfile.example','/etc/caddy/Caddyfile','CADDY','caddy')]
 return [(r,h,s,k) for r,h,s,k in m if (ROOT/r).is_file()]
def strip_comments(text):
 """Text without comment lines and trailing blanks, which is all a Caddyfile or compose file loses in a comment-only edit."""
 return '\n'.join(l.rstrip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#'))
def comment_only(kind,old,new):
 """True when the two versions of a file behave the same: equal syntax trees, equal JSON, or equal text without comments."""
 try:
  if kind=='py':
   import check_comment_only as c;return c.dump(old)==c.dump(new)
  if kind=='json':return json.loads(old)==json.loads(new)
 except (SyntaxError,ValueError):return False
 return strip_comments(old)==strip_comments(new)
def classify(kind,repo,host,recorded,old=None,new=None,force=False):
 """Status of one file: OK, MISSING, UPDATE or BLOCKED. recorded is the hash this script last installed, if any."""
 if host is None:return 'MISSING'
 if repo==host:return 'OK'
 if recorded is not None and recorded!=host and not force:return 'BLOCKED'
 if recorded==host or force or (old is not None and comment_only(kind,old,new)):return 'UPDATE'
 return 'BLOCKED'
def run(host,identity,remote,stdin=None,check=True):
 """Run one command on the host and return its text output; a failure raises CalledProcessError unless check is False."""
 cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15']+(['-i',identity] if identity else [])+[host,remote]
 return subprocess.run(cmd,input=stdin,capture_output=True,check=check).stdout.decode('utf8','replace')
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect(host,identity,items):
 """Hash of every managed file on the host (None when absent), including the tokenizer, and the install record."""
 script=''.join('if [ -f %s ]; then sha256sum -- %s; else echo MISSING %s; fi\n'%((p,)*3) for p in [h for _,h,_,_ in items]+[TOKENIZER[0]])
 hashes={}
 for line in run(host,identity,'sh -s',script.encode()).splitlines():
  head,_,path=line.partition(' ');hashes[path.lstrip(' *')]=None if head=='MISSING' else head
 try:record=json.loads(run(host,identity,'cat '+MANIFEST,check=False) or '{}')
 except ValueError:record={}
 return hashes,record
def plan(host,identity,items,force=False):
 """One row per managed file. restart names what a real change needs (a service, CADDY or COMPOSE), empty for comment-only edits."""
 hashes,record=inspect(host,identity,items);rows=[]
 for repo,path,service,kind in items:
  data=(ROOT/repo).read_bytes();text=data.decode('utf8');mine=sha(data);theirs=hashes.get(path);old=None
  if theirs not in (None,mine):old=run(host,identity,'cat '+path)
  status=classify(kind,mine,theirs,record.get(path),old,text,force)
  restart=service if service and ((status=='UPDATE' and not comment_only(kind,old,text)) or status=='MISSING') else ''
  rows.append({'repo':repo,'path':path,'status':status,'restart':restart,'kind':kind,'sha':mine,'host':theirs,'service':service})
 return rows,hashes,record
CHECKS={'py':"python3 -c \"import sys;compile(open(sys.argv[1]).read(),sys.argv[1],'exec')\" {f}",'json':"python3 -c \"import json,sys;json.load(open(sys.argv[1]))\" {f}",'caddy':"caddy validate --config {f} --adapter caddyfile >/dev/null 2>&1"}
def restore(host,identity,backup,paths):
 for path in paths:run(host,identity,"if [ -e '{b}{p}' ]; then cp -p '{b}{p}' '{p}'; else rm -f '{p}'; fi".format(b=backup,p=path),check=False)
def install(host,identity,rows,stamp):
 """Stage and validate every changed file next to its target, then back up and replace each atomically; undo on failure."""
 todo=[r for r in rows if r['status'] in ('UPDATE','MISSING')];done=[];backup='/root/narimato-install-backup-'+stamp
 try:
  for r in todo:
   new=r['path']+'.install-new'
   run(host,identity,"mkdir -p '%s' && cat > '%s'"%(os.path.dirname(r['path']),new),(ROOT/r['repo']).read_bytes())
   if r['kind'] in CHECKS:run(host,identity,CHECKS[r['kind']].format(f="'%s'"%new))
  for r in todo:
   run(host,identity,"set -e; if [ -e '{p}' ]; then mkdir -p '{b}{d}'; cp -p '{p}' '{b}{p}'; chown --reference='{p}' '{p}.install-new'; chmod --reference='{p}' '{p}.install-new'; else chmod 644 '{p}.install-new'; fi; mv '{p}.install-new' '{p}'".format(p=r['path'],b=backup,d=os.path.dirname(r['path'])))
   done.append(r['path'])
 except subprocess.CalledProcessError as error:
  for r in todo:run(host,identity,"rm -f '%s.install-new'"%r['path'],check=False)
  restore(host,identity,backup,done)
  raise SystemExit('install failed and was undone: '+(error.stderr or b'').decode('utf8','replace')[:300])
 return backup
LEASE="""import json,sys,urllib.request
key=[l.split('=',1)[1].strip() for l in open('/etc/narimato-model-cleanup.env') if l.startswith('GATEWAY_MAINTENANCE_KEY=')][0]
body={'action':sys.argv[1]}
if len(sys.argv)>2:body['lease']=sys.argv[2]
req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',json.dumps(body).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
try:print(json.dumps(json.load(urllib.request.urlopen(req,timeout=10))))
except Exception as e:print(json.dumps({'error':type(e).__name__}))
"""
def lease(host,identity,action,token=''):
 """Maintenance lease on the gateway, called on the host so the key never leaves it. acquire succeeds only when idle."""
 return json.loads(run(host,identity,'python3 - %s %s'%(action,token),LEASE.encode()) or '{}')
def health(host,identity):
 """(ok, lines): services and timers active, gateway and public API answer 401 without a key, Ollama answers 200."""
 out=run(host,identity,"for s in %s; do echo \"$s $(systemctl is-active $s)\"; done; echo \"gateway $(curl -s -o /dev/null -m 10 -w %%{http_code} http://127.0.0.1:8090/v1/models)\"; echo \"public $(curl -s -o /dev/null -m 15 -w %%{http_code} https://chatbotapi.haho.ai/v1/models)\"; echo \"ollama $(curl -s -o /dev/null -m 10 -w %%{http_code} http://127.0.0.1:11434/api/version)\""%' '.join(SERVICES+TIMERS),check=False)
 lines=out.strip().splitlines();expect={'gateway 401','public 401','ollama 200'}
 return len(lines)==len(SERVICES)+len(TIMERS)+len(expect) and all(l in expect or (l.endswith(' active')) for l in lines),lines
def restart(host,identity,service,backup,rows):
 """Restart one service, the gateway only while it holds the maintenance lease. Put its files back if it is not healthy after."""
 token=''
 if service=='narimato-gateway':
  token=lease(host,identity,'acquire').get('lease','')
  if not token:print('gateway is busy or in maintenance; not restarted');return False
 run(host,identity,'systemctl restart '+service);time.sleep(4);ok,lines=health(host,identity)
 if token:lease(host,identity,'release',token)
 if not ok:
  restore(host,identity,backup,[r['path'] for r in rows if r['service']==service and r['status'] in ('UPDATE','MISSING')])
  run(host,identity,'systemctl restart '+service,check=False);print('health failed after restarting %s; its files were restored from %s: %s'%(service,backup,lines))
 return ok
def describe(r):
 if r['status']!='UPDATE' and r['status']!='MISSING':return ''
 if r['restart']=='COMPOSE':return '  (compose is never applied automatically)'
 if r['restart']=='CADDY':return '  (caddy reload needed)'
 return '  (restart %s)'%r['restart'] if r['restart'] else '  (comment-only or no restart needed)'
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__.split('\n')[0]);p.add_argument('--host',default=os.environ.get('INFERENCE_HOST',HOST));p.add_argument('--identity',default=os.environ.get('INFERENCE_SSH_KEY',os.path.expanduser('~/.ssh/hetzner_ai')))
 p.add_argument('--apply',action='store_true');p.add_argument('--restart',action='store_true');p.add_argument('--force',action='store_true')
 a=p.parse_args(argv);host,key=a.host,a.identity
 try:rows,hashes,record=plan(host,key,managed(),a.force)
 except (subprocess.CalledProcessError,OSError) as error:print('error: cannot read the host:',getattr(error,'stderr',error));return 2
 counts={}
 for r in rows:
  counts[r['status']]=counts.get(r['status'],0)+1
  if r['status']!='OK':print('%-8s %s%s'%(r['status'],r['repo'],describe(r)))
 tok=hashes.get(TOKENIZER[0]);print('tokenizer:','OK' if tok==TOKENIZER[1] else 'MISSING' if tok is None else 'WRONG HASH')
 absent=[e for e in ENV_FILES if run(host,key,'[ -f %s ] && echo y || echo n'%e).strip()!='y'];print('credential files:','all present' if not absent else 'MISSING '+', '.join(absent))
 print('summary:',', '.join('%s %d'%(k,v) for k,v in sorted(counts.items())))
 pending=[r for r in rows if r['status'] in ('UPDATE','MISSING')];blocked=[r for r in rows if r['status']=='BLOCKED']
 if not a.apply:return 1 if pending or blocked or tok!=TOKENIZER[1] else 0
 if blocked:print('blocked files need a decision (rerun with --force once reviewed); nothing was changed');return 1
 if tok!=TOKENIZER[1]:
  if tok is not None:print('tokenizer has the wrong hash; fix by hand');return 1
  data=subprocess.run(['curl','-fsSL',TOKENIZER[2]],capture_output=True,check=True).stdout
  if sha(data)!=TOKENIZER[1]:print('downloaded tokenizer has the wrong hash; not installed');return 1
  run(host,key,"mkdir -p '%s' && cat > '%s'"%(os.path.dirname(TOKENIZER[0]),TOKENIZER[0]),data)
 backup=install(host,key,rows,time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())) if pending else ''
 if any(r['kind']=='unit' for r in pending):run(host,key,'systemctl daemon-reload')
 run(host,key,'for t in %s; do systemctl is-enabled --quiet $t || systemctl enable --now $t; done'%' '.join(TIMERS))
 services=sorted({r['restart'] for r in pending if r['restart'] not in ('','COMPOSE','CADDY')});ok=True
 if a.restart:
  for s in services:ok=restart(host,key,s,backup,rows) and ok
  if any(r['restart']=='CADDY' for r in pending):run(host,key,'systemctl reload caddy')
 elif services:print('installed; restart pending for:',', '.join(services),'(rerun with --restart)')
 good,lines=health(host,key);print('health:','ok' if good else 'FAILED','|'.join(lines))
 if not (good and ok):return 1
 record.update({r['path']:r['sha'] for r in rows});run(host,key,'mkdir -p /var/lib/narimato-install && chmod 700 /var/lib/narimato-install && cat > '+MANIFEST,json.dumps(record,indent=1,sort_keys=True).encode())
 print('backup:',backup or 'none (nothing changed)');return 0
if __name__=='__main__':sys.exit(main())
