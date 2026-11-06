"""Replace named files of the Paperclip factory on the host in one idle-stopped window.

Dry run by default (prints the plan); `--apply` performs it. Each file is checked by its current SHA-256, backed up, compiled
before it is written, and written atomically while the factory service is stopped at a verified idle moment. The service is
started again and must answer its health check; any failure restores the files and starts the previous code. A busy factory is
left alone (exit 2). The payload is a JSON file {"files": {name: {"old": sha256, "new": base64}}}.
"""
import argparse, json, pathlib, shlex, subprocess, sys

REMOTE = r'''
import base64,datetime,hashlib,json,os,pathlib,shutil,signal,sqlite3,subprocess,sys,time,urllib.request
payload=json.load(sys.stdin)
sim=payload.get('simulate') is True
root=pathlib.Path(payload['root']);state=pathlib.Path(payload['state'])
unit='narimato-factory.service'
files=payload['files']
def command(*args):return subprocess.run(list(args),check=True,capture_output=True,timeout=60).stdout.decode().strip()
def database():return sqlite3.connect(state.resolve().as_uri()+'?mode=rw',uri=True,timeout=10)
def sha(data):return hashlib.sha256(data).hexdigest()
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
problems=[]
for name,spec in files.items():
 path=root/name
 if not path.is_file() or sha(path.read_bytes())!=spec['old']:problems.append(name+': not the expected release')
 try:compile(base64.b64decode(spec['new']).decode(),name,'exec')
 except SyntaxError as exc:problems.append(name+': new code does not compile ('+str(exc.lineno)+')')
plan={'apply':payload.get('apply') is True,'simulate':sim,'idle':idle(),'files':sorted(files),'problems':problems}
if problems or not payload.get('apply'):
 print(json.dumps(plan));sys.exit(1 if problems else 0)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=pathlib.Path(payload['backup_root'])/('patch-'+stamp);backup.mkdir(parents=True,mode=0o700)
for name in files:shutil.copy2(root/name,backup/name)
stopped=False
try:
 if not stop_idle():
  print(json.dumps({**plan,'state':'busy','changed':False}));sys.exit(2)
 stopped=True
 for name,spec in files.items():
  path=root/name;temp=path.with_name(path.name+'.patch-tmp');temp.write_bytes(base64.b64decode(spec['new']))
  st=path.stat();os.chmod(temp,st.st_mode&0o7777)
  try:os.chown(temp,st.st_uid,st.st_gid)
  except PermissionError:pass
  os.replace(temp,path)
  for cache in path.parent.glob('__pycache__/'+path.stem+'.*.pyc'):cache.unlink()
 if payload.get('fail_at')=='after_write':raise RuntimeError('injected failure')
 if not sim:
  command('systemctl','start',unit);health=None
  for _ in range(60):
   try:
    with urllib.request.urlopen('http://127.0.0.1:9089/health',timeout=1) as response:health=json.load(response)
    if health.get('status')=='ok':break
   except OSError:time.sleep(.5)
  if not health or health.get('status')!='ok':raise RuntimeError('Native health check failed')
 print(json.dumps({**plan,'state':'healthy','changed':True,'private_backup':str(backup)}))
except SystemExit:raise
except BaseException as failure:
 try:
  if not sim and command('systemctl','show',unit,'--property=MainPID','--value')!='0':
   if not stop_idle():raise RuntimeError('Release check failed; running work preserved; backup retained at '+str(backup))
  for name in files:shutil.copy2(backup/name,root/name)
  if not sim:command('systemctl','start',unit)
 except BaseException as second:raise RuntimeError('Rollback needs manual review: '+str(second)+'; backup at '+str(backup)) from None
 raise RuntimeError('Release failed; prior code restored: '+str(failure)) from None
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--host', required=True)
    parser.add_argument('--ssh-key', required=True)
    parser.add_argument('--payload', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    payload = json.loads(pathlib.Path(args.payload).read_text())
    payload.update(apply=args.apply, root='/opt/narimato-factory', state='/var/lib/narimato-factory/factory.sqlite3',
                   backup_root='/var/backups/factory-patches')
    result = subprocess.run(['ssh', '-i', args.ssh_key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', f'root@{args.host}',
                             'python3 -I -c ' + shlex.quote(REMOTE)],
                            input=json.dumps(payload).encode(), capture_output=True, timeout=600)
    print(result.stdout.decode().strip() or result.stderr.decode().strip())
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
