"""Fetch and verify a complete Paperclip recovery bundle; retain seven verified copies."""
import datetime,gzip,hashlib,json,os,pathlib,re,sqlite3,subprocess,sys,tarfile,tempfile,time
from zoneinfo import ZoneInfo
BASE=pathlib.Path(__file__).resolve().parents[1];DEST=BASE/'private/paperclip/daily-backups';SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=20','-i','/Users/chappie/.ssh/hetzner_ai','root@2.29.113.132'];PATTERN=r'paperclip-recovery-\d{8}T\d{6}Z\.tar\.gz'
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
  for required in ['opt/narimato-factory/factory.json','opt/narimato-factory/workflows.json','opt/narimato-paperclip/.env','etc/paperclip-access.env','etc/caddy/Caddyfile']:
   if required not in names:raise ValueError('Recovery component missing')
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
  return {'sqlite_integrity':'ok','native_sql_backups':len(sql),'required_components':True}

def main():
 os.umask(0o077);DEST.mkdir(parents=True,mode=0o700,exist_ok=True)
 latest=DEST/'latest.json'
 if latest.exists() and '--force' not in sys.argv and time.time()<json.loads(latest.read_text()).get('next_due_at',0):
  print(json.dumps({'status':'not_due'}));return
 info=json.loads(execute(SSH+['python3 /opt/narimato-paperclip/scheduled-backup.py create']))
 if not re.fullmatch(PATTERN,info.get('name','')) or not re.fullmatch(r'[a-f0-9]{64}',info.get('sha256','')):raise ValueError('Invalid backup manifest')
 final=DEST/info['name'];part=final.with_suffix(final.suffix+'.part')
 execute(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=20','-i','/Users/chappie/.ssh/hetzner_ai','root@2.29.113.132:/root/paperclip-scheduled-backups/'+info['name'],str(part)])
 part.chmod(0o600);checks=verify(part,info['sha256']);os.replace(part,final)
 manifest={**info,**checks,'verified_at':time.time()};final.with_suffix('.verified.json').write_text(json.dumps(manifest,indent=2)+'\n')
 # A prior file name format is never guessed or removed.
 manifests=sorted(DEST.glob('paperclip-recovery-*.tar.verified.json'),reverse=True)
 if not manifests:manifests=sorted(DEST.glob('paperclip-recovery-*.verified.json'),reverse=True)
 for marker in manifests[7:]:
  name=json.loads(marker.read_text())['name']
  if re.fullmatch(PATTERN,name):(DEST/name).unlink(missing_ok=True);marker.unlink()
 retained=min(7,len(manifests));execute(SSH+['python3 /opt/narimato-paperclip/scheduled-backup.py confirm'],json.dumps({**info,'retained':retained}).encode())
 local=datetime.datetime.now(ZoneInfo('Europe/Budapest'));due=local.replace(hour=3,minute=20,second=0,microsecond=0)
 if due<=local:due+=datetime.timedelta(days=1)
 status={'next_due_at':due.timestamp(),'status':'verified','verified_at':time.time(),'archive':info['name'],'retained':retained,**checks};(DEST/'latest.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))
if __name__=='__main__':
 try:main()
 except Exception as e:
  DEST.mkdir(parents=True,mode=0o700,exist_ok=True);(DEST/'last-failure.json').write_text(json.dumps({'at':time.time(),'error_category':type(e).__name__,'reason':str(e)[:200]})+'\n');print(json.dumps({'status':'failed','error_category':type(e).__name__}));sys.exit(1)
