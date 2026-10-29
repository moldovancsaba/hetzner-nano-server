"""Isolated recovery of app, native SQL, factory SQLite and access gate; no network egress."""
import gzip,hashlib,json,os,pathlib,re,shutil,signal,sqlite3,subprocess,sys,tarfile,tempfile,time
NAME='paperclip-recovery-drill';PROCESSES=[];CURRENT_ROOT=None
def command(args,timeout=180,env=None):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout,env=env)
 if r.returncode:
  if CURRENT_ROOT:
   p=CURRENT_ROOT/'command-failure.log';p.write_text(json.dumps({'program':args[0],'stderr':r.stderr[-8000:],'stdout':r.stdout[-4000:]}));p.chmod(0o600)
  raise RuntimeError('Drill command failed: '+args[0])
 return r.stdout

def load_env(path):
 result={}
 for line in path.read_text().splitlines():
  if line.strip() and not line.startswith('#') and '=' in line:
   k,v=line.split('=',1);result[k]=v.strip().strip('"\'')
 return result

def spawn(args,log,env=None):
 f=open(log,'w');os.chmod(log,0o600);p=subprocess.Popen(args,stdout=f,stderr=f,env=env,start_new_session=True);PROCESSES.append((p,f));return p

def wait_file(path,timeout=120):
 deadline=time.time()+timeout
 while time.time()<deadline:
  if path.exists():return json.loads(path.read_text())
  time.sleep(1)
 raise TimeoutError('Restore bootstrap did not finish')

def main(archive):
 global CURRENT_ROOT
 root=pathlib.Path(tempfile.mkdtemp(prefix='paperclip-restore-',dir='/root'));CURRENT_ROOT=root;os.chmod(root,0o700);tree=root/'archive';tree.mkdir()
 existing=command(['docker','ps','-a','--filter','name=^/'+NAME+'$','--format','{{.Names}}']).strip()
 if existing:raise ValueError('A previous isolated drill container must be inspected first')
 proof={'started_at':time.time(),'network_egress':False,'production_files_changed':False}
 try:
  with tarfile.open(archive) as tar:
   for m in tar.getmembers():
    if m.name.startswith('/') or '..' in pathlib.PurePosixPath(m.name).parts:raise ValueError('Unsafe recovery archive member')
   tar.extractall(tree,filter='data')
  deployment=tree/'opt/narimato-paperclip';data=deployment/'data';factory=tree/'opt/narimato-factory';state=root/'factory-state';state.mkdir()
  sql=sorted([p for p in data.rglob('*.sql*') if p.name.endswith(('.sql','.sql.gz')) and p.stat().st_size>1000],key=lambda p:p.name)[-1]
  if sql.name.endswith('.gz'):
   uncompressed=data/'restore-input.sql'
   with gzip.open(sql,'rb') as source,open(uncompressed,'wb') as output:shutil.copyfileobj(source,output)
   uncompressed.chmod(0o600);sql=uncompressed
  snapshot=next((tree/'root/paperclip-backups').glob('factory-*.sqlite3'));shutil.copy2(snapshot,state/'factory.sqlite3')
  with sqlite3.connect(state/'factory.sqlite3') as db:
   assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';proof['factory_tables']=db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
  secrets=load_env(deployment/'.env');access=load_env(tree/'etc/paperclip-access.env');assert access.get('ACCESS_PASSWORD_HASH') and access.get('ACCESS_SIGNING_KEY')
  # Only the copied directory is assigned to the container's existing node user.
  for parent,dirs,files in os.walk(data):
   os.chown(parent,1000,1000)
   for name in files:
    p=pathlib.Path(parent)/name
    if not p.is_symlink():os.chown(p,1000,1000)
  image=command(['docker','inspect','narimato-paperclip','--format','{{.Image}}']).strip()
  args=['docker','run','-d','--name',NAME,'--network','none','--memory','900m','--cpus','0.5','--pids-limit','384','--user','1000:1000','--entrypoint','sleep','-v',str(data)+':/paperclip','-w','/app',image,'infinity']
  command(args);proof['image_matches_production']=True
  bootstrap=root/'restore.mjs';bootstrap.write_text('''import { createRequire } from 'node:module';import fs from 'node:fs';
const require=createRequire('/app/server/package.json');const {default:EmbeddedPostgres}=await import(require.resolve('embedded-postgres'));
const pg=new EmbeddedPostgres({databaseDir:'/paperclip/instances/default/db',user:'paperclip',password:'paperclip',port:54329,persistent:true,initdbFlags:['--encoding=UTF8','--locale=C','--lc-messages=C'],onLog:()=>{},onError:()=>{}});
await pg.initialise();await pg.start();await pg.createDatabase('paperclip');
const {runDatabaseRestore}=await import('/app/packages/db/src/backup-lib.ts');await runDatabaseRestore({connectionString:'postgres://paperclip:paperclip@127.0.0.1:54329/paperclip',backupFile:process.argv[2]});
const {default:postgres}=await import(createRequire('/app/packages/db/package.json').resolve('postgres'));const db=postgres('postgres://paperclip:paperclip@127.0.0.1:54329/paperclip');
const [companies]=await db`select count(*)::int as n from companies`;const [agents]=await db`select count(*)::int as n from agents`;const [issues]=await db`select count(*)::int as n from issues`;
await db`update agents set status='paused'`;await db`update routine_triggers set enabled=false`;await db`update heartbeat_runs set status='cancelled' where status in ('queued','running')`;
await db.end();fs.writeFileSync('/paperclip/restore-db-proof.json',JSON.stringify({companies:companies.n,agents:agents.n,issues:issues.n,agents_paused:true,triggers_disabled:true}));setInterval(()=>{},1000);
''');os.chmod(bootstrap,0o644);command(['docker','cp',str(bootstrap),NAME+':/tmp/restore.mjs'])
  backup_in_container='/paperclip/'+str(sql.relative_to(data))
  spawn(['docker','exec','-u','node',NAME,'node','--import','./server/node_modules/tsx/dist/loader.mjs','/tmp/restore.mjs',backup_in_container],root/'database.log')
  proof['native_database']=wait_file(data/'restore-db-proof.json',180);assert proof['native_database']['companies']>=1 and proof['native_database']['agents']>=5
  env={**os.environ,'DATABASE_URL':'postgres://paperclip:paperclip@127.0.0.1:54329/paperclip','PAPERCLIP_HOME':'/paperclip','HOST':'127.0.0.1','PORT':'3100','PAPERCLIP_DEPLOYMENT_MODE':'local_trusted','PAPERCLIP_DEPLOYMENT_EXPOSURE':'private','PAPERCLIP_PUBLIC_URL':'https://paperclip.haho.ai','PAPERCLIP_ALLOWED_HOSTNAMES':'paperclip.haho.ai,localhost,127.0.0.1','NODE_OPTIONS':'--max-old-space-size=512'}
  for key in ['PAPERCLIP_AGENT_JWT_SECRET','BETTER_AUTH_SECRET','PAPERCLIP_TOOL_ACTION_SIGNING_SECRET']:env[key]=secrets[key]
  app=['docker','exec','-u','node']
  for key in ['DATABASE_URL','PAPERCLIP_HOME','HOST','PORT','PAPERCLIP_DEPLOYMENT_MODE','PAPERCLIP_DEPLOYMENT_EXPOSURE','PAPERCLIP_PUBLIC_URL','PAPERCLIP_ALLOWED_HOSTNAMES','NODE_OPTIONS','PAPERCLIP_AGENT_JWT_SECRET','BETTER_AUTH_SECRET','PAPERCLIP_TOOL_ACTION_SIGNING_SECRET']:app+=['-e',key]
  spawn(app+[NAME,'node','--import','./server/node_modules/tsx/dist/loader.mjs','server/dist/index.js'],root/'app.log',env)
  pid=command(['docker','inspect',NAME,'--format','{{.State.Pid}}']).strip();ns=['nsenter','--target',pid,'--net']
  factory_env={**os.environ,'FACTORY_STATE':str(state),'FACTORY_CONFIG':str(factory/'factory.json')}
  spawn(ns+['python3',str(factory/'worker.py')],root/'factory.log',factory_env)
  spawn(ns+['python3',str(deployment/'access/gate.py')],root/'gate.log',{**os.environ,**access})
  # The archived production proxy is kept intact; only the isolated listener uses HTTP loopback.
  proxy=root/'Caddyfile';proxy.write_text('''{\n admin off\n auto_https off\n}\nhttp://127.0.0.1:8080 {\n handle /_access/* {\n reverse_proxy 127.0.0.1:8088\n }\n handle {\n forward_auth 127.0.0.1:8088 {\n uri /_access/check\n }\n @factory path /factory /factory/ /factory/metrics\n handle @factory {\n reverse_proxy 127.0.0.1:9089\n }\n handle {\n reverse_proxy 127.0.0.1:3100\n }\n }\n}\n''')
  command(ns+['caddy','validate','--adapter','caddyfile','--config',str(proxy)])
  spawn(ns+['caddy','run','--adapter','caddyfile','--config',str(proxy)],root/'proxy.log')
  checker=root/'check.py';checker.write_text('''import hashlib,hmac,json,pathlib,secrets,time,urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
op=urllib.request.build_opener(NoRedirect);values={}
for line in pathlib.Path(__import__('sys').argv[1]).read_text().splitlines():
 if line.strip() and not line.startswith('#'):
  k,v=line.split('=',1);values[k]=v.strip().strip(chr(34)+chr(39))
payload=str(int(time.time()+120))+'.'+secrets.token_hex(16);token=payload+'.'+hmac.new(values['ACCESS_SIGNING_KEY'].encode(),payload.encode(),hashlib.sha256).hexdigest()
def get(path,auth=True):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,headers={'X-Request-Purpose':'test',**({'Cookie':'__Host-paperclip_access='+token} if auth else {})})
 try:
  with op.open(req,timeout=20) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
end=time.time()+150
while time.time()<end:
 try:
  if get('/api/health')[0]==200:break
 except Exception:pass
 time.sleep(2)
assert get('/factory',False)[0]==303
status,body=get('/factory');assert status==200 and b'Company dashboard' in body
status,body=get('/factory/metrics');assert status==200;metrics=json.loads(body)
status,body=get('/api/companies');assert status==200;companies=json.loads(body);assert any(c['name']=='Narimato' for c in companies)
status,body=get('/');assert status==200 and b'<html' in body.lower()
print(json.dumps({'password_gate_restored':True,'locked_dashboard_refused':True,'native_ui':True,'company_api':True,'factory_dashboard':True,'factory_metrics':True,'published_receipts_restored':metrics['funnel']['published'],'active_agents_in_clone':sum(a['status']!='paused' for a in metrics['operations']['team'])}))
''')
  result=json.loads(command(ns+['python3',str(checker),str(tree/'etc/paperclip-access.env')],timeout=180));assert result['active_agents_in_clone']==0;proof.update(result)
  proof.update(completed_at=time.time(),status='passed',scope='Isolated full stack: SQL, persistent files, secrets, factory state, native UI, proxy and password gate. Public DNS/TLS issuance and real host failover are not exercised.')
  destination=pathlib.Path('/opt/narimato-factory/restore-drill-latest.json');destination.write_text(json.dumps(proof,indent=2)+'\n');destination.chmod(0o644)
  print(json.dumps(proof))
 finally:
  for p,f in PROCESSES:
   try:os.killpg(p.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   f.close()
  command(['docker','rm','-f',NAME],timeout=30)
  # Keep only private diagnostics until the successful report is saved; never touch original data.
  if proof.get('status')=='passed':shutil.rmtree(root)
if __name__=='__main__':
 try:main(pathlib.Path(sys.argv[1]))
 except Exception as error:print(json.dumps({'status':'failed','error_category':type(error).__name__}));sys.exit(1)
