"""Install disabled exchange hooks into the current native factory without replacing other work."""
import argparse
import base64
import hashlib
import json
import shlex
import subprocess
from pathlib import Path


def patch_hooks(name, source):
    patches = {
        'worker.py': (
            "  for fact in facts:db.execute('INSERT INTO facts VALUES(?,?,?,?,?)',(entity_id,fact['field'],fact['value'],fact['quote'],source_id))\n",
            "  import source_exchange\n  source_exchange.save_offer(db,json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {},issue,page,facts)\n"),
        'autonomy.py': (
            ' initialize(database)\n handoffs=company_ops.dispatch_pending(board,config,database,limit=10)\n',
            " import source_exchange\n source_exchange.coordinate(database,config.get('source_exchange',{}),board,config)\n")}
    anchor, hook = patches[name]
    if hook in source:
        if source.count(hook) != 1:
            raise ValueError('Duplicate exchange hook')
        return source
    target='source_exchange.save_offer' if name=='worker.py' else 'source_exchange.coordinate'
    if target in source or source.count(anchor) != 1:
        raise ValueError('Native source does not match the reviewed insertion boundary')
    if name == 'worker.py':
        updated = source.replace(anchor, anchor + hook)
    else:
        updated = source.replace(anchor, ' initialize(database)\n' + hook + anchor.split('\n', 1)[1])
    compile(updated, name, 'exec')
    return updated


REMOTE = r'''
import base64,datetime,hashlib,json,os,pathlib,shutil,sqlite3,subprocess,sys,time,urllib.request
payload=json.load(sys.stdin)
root=pathlib.Path('/opt/narimato-factory')
state=pathlib.Path('/var/lib/narimato-factory/factory.sqlite3')
unit='narimato-factory.service'
dropin=pathlib.Path('/etc/systemd/system/narimato-factory.service.d/40-source-exchange.conf')
def command(*args):
 return subprocess.run(list(args),check=True,capture_output=True,timeout=20).stdout.decode().strip()
def database():
 if not state.is_file():raise RuntimeError('Existing native database required')
 return sqlite3.connect(state.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)
def idle():
 pid=int(command('systemctl','show',unit,'--property=MainPID','--value'))
 if not pid:return False
 threads=len(list(pathlib.Path('/proc/'+str(pid)+'/task').iterdir()))
 with database() as db:runs=db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0]
 return threads==1 and runs==0
def stop_idle():
 if not idle():return False
 try:
  command('systemctl','freeze',unit)
  if not idle():return False
  # Queue termination while frozen; no handler can start after the final idle check.
  command('systemctl','kill','--kill-whom=main','--signal=SIGTERM',unit)
 finally:command('systemctl','thaw',unit)
 command('systemctl','stop',unit)
 return True
configpath=root/'factory.json'
configbytes=configpath.read_bytes();settings=json.loads(configbytes).get('source_exchange',{})
if any(settings.get(key) for key in ['offers_enabled','events_enabled','gap_tasks_enabled']):raise RuntimeError('Disabled-hook deployment requires all business hooks off')
for name,expected in payload['expected'].items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Native source changed since preflight')
scope={};exec(payload['patcher'],scope)
files={name:scope['patch_hooks'](name,(root/name).read_text()).encode() for name in ['worker.py','autonomy.py']}
files['source_exchange.py']=base64.b64decode(payload['module'])
for name,body in files.items():compile(body,name,'exec')
sys.path.insert(0,'/opt/source-exchange')
from exchange.factory import initialize
from exchange.contract import Contract
Contract()
if not payload['apply']:
 print(json.dumps({'apply':False,'idle':idle(),'business_flags':'off','files':{name:hashlib.sha256(body).hexdigest() for name,body in files.items()}}));sys.exit(0)
if not stop_idle():
 print(json.dumps({'apply':False,'state':'busy','business_flags':'off','reason':'native run or HTTP handler active; no files or schema changed'}));sys.exit(0)
backup=pathlib.Path('/var/backups/source-exchange')/('native-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
previous={name:(root/name).exists() for name in files}
had_dropin=dropin.exists()
try:
 backup.mkdir(parents=True,mode=0o700);os.chmod(backup.parent,0o700)
 if configpath.read_bytes()!=configbytes:raise RuntimeError('Factory configuration changed; no release applied')
 for name,present in previous.items():
  if present:shutil.copy2(root/name,backup/name)
 if had_dropin:shutil.copy2(dropin,backup/'unit-dropin')
 with database() as original,sqlite3.connect(backup/'factory.sqlite3') as saved:
  original.backup(saved)
  if saved.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failed')
 os.chmod(backup/'factory.sqlite3',0o600)
 with database() as db:initialize(db,create=True)
 for name,body in files.items():
  target=root/name;temporary=target.with_name(target.name+'.exchange-release')
  temporary.write_bytes(body);os.chmod(temporary,0o644);temporary.replace(target)
 dropin.parent.mkdir(parents=True,exist_ok=True)
 dropin.write_text('[Service]\nEnvironment=SOURCE_EXCHANGE_MODULES=/opt/source-exchange\n')
 os.chmod(dropin,0o644)
 command('systemctl','daemon-reload');command('systemctl','start',unit)
 health=None
 for _ in range(20):
  try:
   with urllib.request.urlopen('http://127.0.0.1:9089/health',timeout=1) as response:health=json.load(response)
   if health.get('status')=='ok':break
  except OSError:time.sleep(0.2)
 if not health or health.get('status')!='ok':raise RuntimeError('Native health check failed')
 if configpath.read_bytes()!=configbytes:raise RuntimeError('Configuration changed during release; review required')
 with database() as db:tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'exchange_%'")]
 print(json.dumps({'apply':True,'state':'healthy','native_hooks_installed':True,'business_flags':'off','factory_config_unchanged':True,'exchange_tables':len(tables),'private_backup':str(backup),'files':{name:hashlib.sha256(body).hexdigest() for name,body in files.items()}}))
except BaseException:
 # Never replace a newer business database with the forensic backup.
 active=command('systemctl','show',unit,'--property=MainPID','--value')!='0'
 if active and not stop_idle():raise RuntimeError('Release check failed; running native work preserved. Drain before code rollback; private backup retained.') from None
 for name,present in previous.items():
  if present and (backup/name).is_file():shutil.copy2(backup/name,root/name)
  elif not present and (root/name).exists():(root/name).unlink()
 if had_dropin and (backup/'unit-dropin').is_file():shutil.copy2(backup/'unit-dropin',dropin)
 elif not had_dropin and dropin.exists():dropin.unlink()
 command('systemctl','daemon-reload');command('systemctl','start',unit)
 raise RuntimeError('Native release failed; prior code restored; business state preserved') from None
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',required=True)
    parser.add_argument('--ssh-key',required=True)
    parser.add_argument('--expected-worker-sha256',required=True)
    parser.add_argument('--expected-autonomy-sha256',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    import inspect
    module=Path(__file__).resolve().parents[2]/'factory/source_exchange.py'
    payload={'apply':args.apply,'expected':{'worker.py':args.expected_worker_sha256,'autonomy.py':args.expected_autonomy_sha256},'module':base64.b64encode(module.read_bytes()).decode(),'patcher':inspect.getsource(patch_hooks)}
    result=subprocess.run(['ssh','-i',args.ssh_key,'-o','BatchMode=yes','-o','ConnectTimeout=10',args.host,'python3 -c '+shlex.quote(REMOTE)],input=json.dumps(payload).encode(),capture_output=True,timeout=70)
    if result.returncode:
        raise SystemExit('Factory release refused or needs recovery; inspect private host service and backup state. No customer data is printed.')
    print(json.dumps(json.loads(result.stdout)))


if __name__=='__main__':main()
