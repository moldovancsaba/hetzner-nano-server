"""Fetch and verify daily Paperclip recovery bundles; retain seven days on both hosts."""
import datetime,gzip,hashlib,json,os,pathlib,re,sqlite3,subprocess,sys,tarfile,tempfile,time
from zoneinfo import ZoneInfo
BASE=pathlib.Path(__file__).resolve().parents[1];DEST=BASE/'private/paperclip/daily-backups';PATTERN=r'paperclip-recovery-\d{8}T\d{6}Z\.tar\.gz'
SSH_OPTIONS=['-o','BatchMode=yes','-o','ConnectTimeout=20','-o','UseKeychain=yes','-o','IdentitiesOnly=yes','-i','/Users/chappie/.ssh/hetzner_ai']
SSH=['ssh',*SSH_OPTIONS,'root@2.29.113.132']
def execute(args,data=None,timeout=900):
 result=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
 if result.returncode:raise RuntimeError('backup_transport_or_snapshot_failed')
 return result.stdout

def verify(path,expected):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 if h.hexdigest()!=expected:raise ValueError('Backup checksum mismatch')
 with tarfile.open(path) as t:
  names=t.getnames()
  for required in ['opt/narimato-factory/worker.py','opt/narimato-factory/factory.json','opt/narimato-factory/workflows.json','opt/narimato-paperclip/.env','etc/paperclip-access.env','etc/caddy/Caddyfile']:
   if required not in names:raise ValueError('Recovery component missing')
  caddy=t.extractfile('etc/caddy/Caddyfile').read()
  if b'import /etc/caddy/source-exchange-dashboard.caddy' in caddy and 'etc/caddy/source-exchange-dashboard.caddy' not in names:raise ValueError('Dashboard proxy recovery configuration missing')
  if 'opt/narimato-factory/business_metrics.py' in names and b'native_reporting.read_tasks' in t.extractfile('opt/narimato-factory/business_metrics.py').read():
   for name in ['native_reporting.py','native_reporting.mjs','native_reporting_contract.json']:
    try:component=t.getmember('opt/narimato-factory/'+name)
    except KeyError:raise ValueError('Native reporting recovery component missing') from None
    if not component.isfile() or not 0<component.size<=1048576:raise ValueError('Invalid native reporting recovery component')
   if b'/run/narimato-reporting/read.sock' in t.extractfile('opt/narimato-factory/native_reporting.py').read():
    for name in ['opt/narimato-factory/native_reporting_service.py','etc/systemd/system/native-reporting.socket','etc/systemd/system/native-reporting@.service','etc/systemd/system/narimato-factory.service.d/60-native-reporting.conf']:
     if name not in names or not t.getmember(name).isfile():raise ValueError('Native reporting socket recovery component missing')
  assets=verify_dashboard(t)
  sql=[m for m in t.getmembers() if m.name.endswith(('.sql','.sql.gz')) and m.size>1000]
  if not sql:raise ValueError('Native database SQL backup missing')
  for member in sql:
   if member.name.endswith('.gz'):
    with gzip.GzipFile(fileobj=t.extractfile(member)) as stream:
     while stream.read(1024*1024):pass
  member=next(n for n in names if n.startswith('root/paperclip-backups/factory-') and n.endswith('.sqlite3'))
  with tempfile.TemporaryDirectory(prefix='paperclip-backup-check-') as tmp:
   dbpath=pathlib.Path(tmp)/'factory.sqlite3';dbpath.write_bytes(t.extractfile(member).read())
   with sqlite3.connect(dbpath) as db:
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Factory snapshot integrity failed')
  return {'sqlite_integrity':'ok','native_sql_backups':len(sql),'required_components':True,'dashboard_assets_verified':assets}

def verify_dashboard(archive):
 worker=archive.extractfile('opt/narimato-factory/worker.py').read()
 if b'SOURCE_EXCHANGE_DASHBOARD' not in worker:return 0
 root='opt/source-exchange/dashboard/'
 try:
  index=archive.getmember(root+'index.html')
  if not index.isfile() or index.size>4000000:raise ValueError('Invalid dashboard shell')
  html=archive.extractfile(index).read().decode('utf-8')
  paths=re.findall(r'''(?:src|href)=["'](/factory/exchange/assets/[^"']+)["']''',html)
  if not any(p.endswith('.js') for p in paths) or not any(p.endswith('.css') for p in paths):raise ValueError('Dashboard shell lacks script or styles')
  for path in paths:
   relative=path.removeprefix('/factory/exchange/')
   if '..' in pathlib.PurePosixPath(relative).parts:raise ValueError('Invalid dashboard asset path')
   member=archive.getmember(root+relative)
   if not member.isfile() or not 0<member.size<=4000000:raise ValueError('Invalid dashboard asset')
  return len(paths)
 except (KeyError,UnicodeError) as error:raise ValueError('Dashboard recovery assets missing') from error

def main():
 os.umask(0o077);DEST.mkdir(parents=True,mode=0o700,exist_ok=True)
 latest=DEST/'latest.json'
 if '--prune-only' in sys.argv:
  from backup_retention import prune
  result=prune(DEST,apply=True);print(json.dumps(result));return
 if latest.exists() and '--force' not in sys.argv and time.time()<json.loads(latest.read_text()).get('next_due_at',0):
  print(json.dumps({'status':'not_due'}));return
 info=json.loads(execute(SSH+['python3 /opt/narimato-paperclip/scheduled-backup.py create']))
 if not re.fullmatch(PATTERN,info.get('name','')) or not re.fullmatch(r'[a-f0-9]{64}',info.get('sha256','')):raise ValueError('Invalid backup manifest')
 final=DEST/info['name'];part=final.with_suffix(final.suffix+'.part')
 execute(['scp','-q',*SSH_OPTIONS,'root@2.29.113.132:/root/paperclip-scheduled-backups/'+info['name'],str(part)])
 part.chmod(0o600);checks=verify(part,info['sha256']);os.replace(part,final)
 manifest={**info,**checks,'verified_at':time.time()};final.with_suffix('.verified.json').write_text(json.dumps(manifest,indent=2)+'\n')
 from backup_retention import prune
 retained=prune(DEST,apply=True)['retained'];execute(SSH+['python3 /opt/narimato-paperclip/scheduled-backup.py confirm'],json.dumps({**info,'retained':retained}).encode())
 local=datetime.datetime.now(ZoneInfo('Europe/Budapest'));due=local.replace(hour=3,minute=20,second=0,microsecond=0)
 if due<=local:due+=datetime.timedelta(days=1)
 status={'next_due_at':due.timestamp(),'status':'verified','verified_at':time.time(),'archive':info['name'],'retained':retained,'retention_days':7,**checks};(DEST/'latest.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))
if __name__=='__main__':
 try:main()
 except Exception as e:
  DEST.mkdir(parents=True,mode=0o700,exist_ok=True);(DEST/'last-failure.json').write_text(json.dumps({'at':time.time(),'error_category':type(e).__name__,'reason':str(e)[:200]})+'\n');print(json.dumps({'status':'failed','error_category':type(e).__name__}));sys.exit(1)
