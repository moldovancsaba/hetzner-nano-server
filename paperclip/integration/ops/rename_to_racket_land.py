"""One-time release: the Padel Africa identity of the Paperclip factory becomes Racket Land.

Runs a dry run by default and prints the plan; `--apply` performs it. On the host it, in one idle-stopped window:
verifies the code it replaces by digest, backs up files, unit, env file and the database, writes the new code,
migrates the stored names (two tables, the search purpose, the workflow report kinds), renames the credential file
and its variables, updates the routines and the old tasks that carry the old workflow or purpose names through
Paperclip's own API, starts the service and checks it. Any failure restores the code, the files and the stored names
from the backup and starts the old code again.

The protocol client id `padel-africa` is not touched here: the writer authority and the exchange are configured
against it (see racket_land.CLIENT).
"""
import argparse, json, pathlib, shlex, subprocess, sys

REMOTE = r'''
import base64,datetime,hashlib,json,os,pathlib,re,shutil,signal,sqlite3,subprocess,sys,time,urllib.request
payload=json.load(sys.stdin)
sim=payload.get('simulate') is True
root=pathlib.Path(payload['root']);state=pathlib.Path(payload['state'])
unit='narimato-factory.service'
unit_path=pathlib.Path(payload['unit_path']);env_old=pathlib.Path(payload['env_old']);env_new=pathlib.Path(payload['env_new'])
snapshot_path=pathlib.Path(payload['snapshot_path'])
API='http://127.0.0.1:3100/api';COMPANY=payload['company']
def command(*args):
 return subprocess.run(list(args),check=True,capture_output=True,timeout=60).stdout.decode().strip()
def database():
 return sqlite3.connect(state.resolve().as_uri()+'?mode=rw',uri=True,timeout=10)
def idle():
 if sim:return True
 pid=int(command('systemctl','show',unit,'--property=MainPID','--value'))
 if not pid:return False
 threads=len(list(pathlib.Path('/proc/'+str(pid)+'/task').iterdir()))
 with database() as db:runs=db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0]
 return threads==1 and runs==0
def stop_idle():
 if sim:return True
 if not idle():return False
 if command('systemctl','show',unit,'--property=Restart','--value') not in {'no','on-failure','on-abnormal','on-abort','on-watchdog'}:raise RuntimeError('Automatic restart policy requires separate drain review')
 pid=int(command('systemctl','show',unit,'--property=MainPID','--value'));descriptor=os.pidfd_open(pid)
 try:
  signal.pidfd_send_signal(descriptor,signal.SIGSTOP)
  for _ in range(40):
   if any(line.startswith('State:') and line.split()[1]=='T' for line in pathlib.Path('/proc/'+str(pid)+'/status').read_text().splitlines()):break
   time.sleep(.025)
  else:raise RuntimeError('Native process did not enter a verified pause')
  if int(command('systemctl','show',unit,'--property=MainPID','--value'))!=pid or not idle():return False
  signal.pidfd_send_signal(descriptor,signal.SIGTERM)
 finally:
  try:signal.pidfd_send_signal(descriptor,signal.SIGCONT)
  except ProcessLookupError:pass
  finally:os.close(descriptor)
 command('systemctl','stop',unit)
 return True
def sha(data):return hashlib.sha256(data).hexdigest()
def table(db,name):return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None
def api(method,path,body=None):
 request=urllib.request.Request(API+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=30) as response:
  raw=response.read();return json.loads(raw) if raw else None
def paperclip_issues():
 if sim:return payload.get('sim_issues',[])
 script="const {Client}=require('/app/node_modules/.pnpm/pg@8.18.0/node_modules/pg');(async()=>{const c=new Client({host:'127.0.0.1',port:54329,user:'paperclip',password:'paperclip',database:'paperclip'});await c.connect();await c.query('SET default_transaction_read_only = on');const r=await c.query(\"select id, description from issues where description ~ 'Factory workflow: padel_' or description ~* 'Search purpose:\\\\s*padel'\");console.log(JSON.stringify(r.rows));await c.end()})().catch(e=>{console.error(e.message);process.exit(1)})"
 return json.loads(subprocess.run(['docker','exec','-i','narimato-paperclip','node','-'],input=script.encode(),capture_output=True,timeout=60,check=True).stdout.decode())
def fix_description(text):
 text=text.replace('Factory workflow: padel_','Factory workflow: racket_')
 return re.sub(r'(Search purpose:\s*)padel\b',r'\1racket',text,flags=re.I)
files=payload['files']
# -- verify the code being replaced
problems=[]
for name,spec in files.items():
 path=root/name
 if spec['old'] is None:
  if path.exists() and sha(path.read_bytes())!=sha(base64.b64decode(spec['new'])):problems.append(name+': unexpected existing file')
 elif not path.is_file() or sha(path.read_bytes())!=spec['old']:problems.append(name+': not the expected release')
for label,path,old in (('unit',unit_path,payload['unit']['old']),('snapshot',snapshot_path,payload['snapshot']['old'])):
 if not path.is_file() or sha(path.read_bytes())!=old:problems.append(label+': not the expected release')
if not env_old.is_file() and not env_new.is_file():problems.append('credential file missing')
for name,spec in files.items():
 if spec['new'] is not None and name.endswith('.py'):
  try:compile(base64.b64decode(spec['new']).decode(),name,'exec')
  except SyntaxError as exc:problems.append(name+': new code does not compile ('+str(exc.lineno)+')')
 if spec['new'] is not None and name.endswith('.json'):
  try:json.loads(base64.b64decode(spec['new']))
  except ValueError:problems.append(name+': new JSON invalid')
with database() as db:
 plan_db={'padel_packets_rows':db.execute('SELECT count(*) FROM padel_packets').fetchone()[0] if table(db,'padel_packets') else None,
  'padel_discovery_cursor_rows':db.execute('SELECT count(*) FROM padel_discovery_cursor').fetchone()[0] if table(db,'padel_discovery_cursor') else None,
  'search_jobs_to_migrate':db.execute("SELECT count(*) FROM search_jobs WHERE kind='padel'").fetchone()[0],
  'report_kinds_to_migrate':db.execute("SELECT count(*) FROM workflow_reports WHERE kind LIKE 'padel\\_%' ESCAPE '\\'").fetchone()[0],
  'racket_tables_already':[t for t in ('racket_packets','racket_discovery_cursor') if table(db,t)]}
routines=[] if sim else [r for r in api('GET','/companies/'+COMPANY+'/routines') if 'Factory workflow: padel_' in (r.get('description') or '')]
issues=paperclip_issues()
plan={'apply':payload.get('apply') is True,'simulate':sim,'idle':idle(),'files_replaced':sorted(n for n,s in files.items() if s['old'] is not None and s['new'] is not None),
 'files_added':sorted(n for n,s in files.items() if s['old'] is None),'files_removed':sorted(n for n,s in files.items() if s['new'] is None),
 'database':plan_db,'routines_to_update':len(routines) if not sim else payload.get('sim_routines',0),'issues_to_update':len(issues),'problems':problems}
if problems or not payload.get('apply'):
 print(json.dumps(plan));sys.exit(1 if problems else 0)
if plan_db['racket_tables_already']:raise RuntimeError('racket tables already exist; refusing')
# -- backup
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=pathlib.Path(payload['backup_root'])/('rename-'+stamp);backup.mkdir(parents=True,mode=0o700)
previous={}
for name,spec in files.items():
 path=root/name;previous[name]=path.is_file()
 if path.is_file():shutil.copy2(path,backup/name)
for label,path in (('unit',unit_path),('snapshot',snapshot_path)):shutil.copy2(path,backup/label)
had_env_old=env_old.is_file()
if had_env_old:shutil.copy2(env_old,backup/'env_old');os.chmod(backup/'env_old',0o600)
with database() as original,sqlite3.connect(backup/'factory.sqlite3') as saved:original.backup(saved)
os.chmod(backup/'factory.sqlite3',0o600)
api_backup={'routines':[{'id':r['id'],'description':r['description']} for r in routines],'issues':issues}
(backup/'paperclip.json').write_text(json.dumps(api_backup));os.chmod(backup/'paperclip.json',0o600)
migrated_reports=[]
done={'files':[],'db':False,'env':False,'unit':False,'snapshot':False,'api_routines':[],'api_issues':[]}
def write_atomic(path,data,mode_from=None):
 temp=path.with_name(path.name+'.rename-tmp');temp.write_bytes(data)
 if mode_from and mode_from.exists():
  st=mode_from.stat();os.chmod(temp,st.st_mode&0o7777)
  try:os.chown(temp,st.st_uid,st.st_gid)
  except PermissionError:pass
 os.replace(temp,path)
try:
 if not stop_idle():
  print(json.dumps({**plan,'state':'busy','changed':False}));sys.exit(2)
 if payload.get('fail_at')=='after_stop':raise RuntimeError('injected failure')
 for name,spec in files.items():
  path=root/name
  if spec['new'] is None:
   if path.exists():path.unlink()
   for cache in path.parent.glob('__pycache__/'+path.stem+'.*.pyc'):cache.unlink()
  else:write_atomic(path,base64.b64decode(spec['new']),path)
  done['files'].append(name)
 write_atomic(unit_path,base64.b64decode(payload['unit']['new']),unit_path);done['unit']=True
 write_atomic(snapshot_path,base64.b64decode(payload['snapshot']['new']),snapshot_path);done['snapshot']=True
 if had_env_old:
  text=env_old.read_text().replace('PADEL_SSO_','RACKET_SSO_')
  write_atomic(env_new,text.encode(),env_old);done['env']=True
 with database() as db:
  db.execute('BEGIN IMMEDIATE')
  if table(db,'padel_packets'):db.execute('ALTER TABLE padel_packets RENAME TO racket_packets')
  if table(db,'padel_discovery_cursor'):db.execute('ALTER TABLE padel_discovery_cursor RENAME TO racket_discovery_cursor')
  db.execute("UPDATE search_jobs SET kind='racket' WHERE kind='padel'")
  migrated_reports=[r[0] for r in db.execute("SELECT rowid FROM workflow_reports WHERE kind LIKE 'padel\\_%' ESCAPE '\\'")]
  db.execute("UPDATE workflow_reports SET kind='racket_'||substr(kind,7) WHERE kind LIKE 'padel\\_%' ESCAPE '\\'")
  db.commit()
 done['db']=True
 (backup/'migrated_reports.json').write_text(json.dumps(migrated_reports))
 if payload.get('fail_at')=='after_db':raise RuntimeError('injected failure')
 if not sim:command('systemctl','daemon-reload')
 for r in routines:
  api('PATCH','/routines/'+r['id'],{'description':fix_description(r['description'])});done['api_routines'].append(r['id'])
 for i in issues:
  api('PATCH','/issues/'+i['id'],{'description':fix_description(i['description'])});done['api_issues'].append(i['id'])
 if payload.get('fail_at')=='after_api':raise RuntimeError('injected failure')
 health=None
 if not sim:
  command('systemctl','start',unit)
  for _ in range(40):
   try:
    with urllib.request.urlopen('http://127.0.0.1:9089/health',timeout=1) as response:health=json.load(response)
    if health.get('status')=='ok':break
   except OSError:time.sleep(0.25)
  if not health or health.get('status')!='ok':raise RuntimeError('Native health check failed')
  metrics=None;deadline=time.time()+120
  while metrics is None and time.time()<deadline:
   try:
    with urllib.request.urlopen('http://127.0.0.1:9089/factory/metrics',timeout=30) as response:metrics=json.load(response)
   except OSError:time.sleep(1)
  if not metrics or 'racket' not in metrics:raise RuntimeError('Metrics do not carry the renamed section')
 print(json.dumps({**plan,'state':'healthy','changed':True,'private_backup':str(backup),'migrated_report_rows':len(migrated_reports),'routines_updated':len(done['api_routines']),'issues_updated':len(done['api_issues'])}))
except BaseException as failure:
 # Restore code, files and stored names; never replace newer business rows with the backup copy.
 try:
  if not sim and command('systemctl','show',unit,'--property=MainPID','--value')!='0':
   if not stop_idle():raise RuntimeError('Release check failed; running work preserved; drain before rollback; backup retained at '+str(backup))
  for name,spec in files.items():
   path=root/name
   if previous.get(name) and (backup/name).is_file():shutil.copy2(backup/name,path)
   elif not previous.get(name) and path.exists():path.unlink()
  shutil.copy2(backup/'unit',unit_path);shutil.copy2(backup/'snapshot',snapshot_path)
  if env_new.exists() and had_env_old:env_new.unlink()
  with database() as db:
   db.execute('BEGIN IMMEDIATE')
   if table(db,'racket_packets') and not table(db,'padel_packets'):db.execute('ALTER TABLE racket_packets RENAME TO padel_packets')
   if table(db,'racket_discovery_cursor') and not table(db,'padel_discovery_cursor'):db.execute('ALTER TABLE racket_discovery_cursor RENAME TO padel_discovery_cursor')
   if done['db']:
    db.execute("UPDATE search_jobs SET kind='padel' WHERE kind='racket'")
    for rowid in migrated_reports:db.execute("UPDATE workflow_reports SET kind='padel_'||substr(kind,8) WHERE rowid=?",(rowid,))
   db.commit()
  if not sim:
   command('systemctl','daemon-reload')
   for r in api_backup['routines']:
    if r['id'] in done['api_routines']:api('PATCH','/routines/'+r['id'],{'description':r['description']})
   for i in api_backup['issues']:
    if i['id'] in done['api_issues']:api('PATCH','/issues/'+i['id'],{'description':i['description']})
   command('systemctl','start',unit)
 except BaseException as second:
  raise RuntimeError('Rollback needs manual review: '+str(second)+'; backup at '+str(backup)) from None
 raise RuntimeError('Release failed; prior code and stored names restored: '+str(failure)) from None
'''


def run_remote(host, key, payload):
    result = subprocess.run(['ssh', '-i', key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', f'root@{host}',
                             'python3 -I -c ' + shlex.quote(REMOTE)],
                            input=json.dumps(payload).encode(), capture_output=True, timeout=600)
    return result.returncode, result.stdout.decode(), result.stderr.decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--host', required=True)
    parser.add_argument('--ssh-key', required=True)
    parser.add_argument('--payload', required=True, help='JSON file built by the release preparation step')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    payload = json.loads(pathlib.Path(args.payload).read_text())
    payload['apply'] = args.apply
    code, out, err = run_remote(args.host, args.ssh_key, payload)
    print(out.strip() or err.strip())
    sys.exit(code)


if __name__ == '__main__':
    main()
