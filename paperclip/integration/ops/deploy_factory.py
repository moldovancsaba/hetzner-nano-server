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
            " import source_exchange\n source_exchange.coordinate(database,config.get('source_exchange',{}),board,config)\n"),
        'search_workflow.py': (
            "   pages.append({'url':page['url'],'title':page['title'][:160],'sha256':page['sha256'],'fetched_at':page['fetched_at']})\n",
            "   import source_exchange\n   source_exchange.save_verified_page(database,job,page)\n")}
    anchor, hook = patches[name]
    if hook in source:
        if source.count(hook) != 1:
            raise ValueError('Duplicate exchange hook')
        return source
    target={'worker.py':'source_exchange.save_offer','autonomy.py':'source_exchange.coordinate','search_workflow.py':'source_exchange.save_verified_page'}[name]
    if target in source or source.count(anchor) != 1:
        raise ValueError('Native source does not match the reviewed insertion boundary')
    if name == 'worker.py':
        updated = source.replace(anchor, anchor + hook)
    elif name=='autonomy.py':
        updated = source.replace(anchor, ' initialize(database)\n' + hook + anchor.split('\n', 1)[1])
    else:updated=source.replace(anchor,hook+anchor)
    compile(updated, name, 'exec')
    return updated


def patch_writer_handoff(name, source):
    import re
    specs={'publishing.py':('run','source_exchange.require_native_catalog_writer(config,issue)','source_exchange'),'refresh.py':('run','source_exchange.require_native_catalog_writer(config,issue)','source_exchange'),'program_updates.py':('run','source_exchange.require_native_catalog_writer(config,issue)','source_exchange'),'engine_ops.py':('write_once',"destination_handoff.require_native_destination_writer(config,issue,'management',slug)",'destination_handoff'),'padel.py':('run',"destination_handoff.require_native_destination_writer(config,issue,'management','padel-africa')",'destination_handoff'),'slg.py':('mutate',"destination_handoff.require_native_destination_writer(config,issue,'salesleadgenerator',client.brand)",'destination_handoff')}
    if name not in specs:raise ValueError('Unexpected writer handoff module')
    function,call,module=specs[name];hook=' import '+module+'\n '+call+'\n'
    pattern=r'^def '+function+r'\([^\n]*\):\n'+(r' """CRM writes are never equated to sent email or a won sale\."""\n' if name=='slg.py' else '')
    matches=list(re.finditer(pattern,source,re.M))
    if len(matches)!=1:raise ValueError('Native writer entry point requires review')
    match=matches[0]
    if source[match.end():].startswith(hook):
        if source.count(hook)!=1:raise ValueError('Duplicate writer handoff hook')
        return source
    if module+'.require_native_' in source:raise ValueError('Unknown writer handoff insertion')
    updated=source[:match.end()]+hook+source[match.end():]
    compile(updated,name,'exec')
    return updated


REMOTE = r'''
import base64,datetime,hashlib,json,os,pathlib,shutil,signal,sqlite3,subprocess,sys,time,urllib.request
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
configpath=root/'factory.json'
configbytes=configpath.read_bytes();settings=json.loads(configbytes).get('source_exchange',{})
module_only=payload.get('module_only') is True;writer_handoff=payload.get('writer_handoff') is True;application_writers=payload.get('application_writers') is True
if module_only and writer_handoff:raise RuntimeError('Conflicting native release modes')
if application_writers and not writer_handoff:raise RuntimeError('Application writers require the handoff release mode')
preserve_active=module_only or writer_handoff
if not preserve_active and any(settings.get(key) for key in ['offers_enabled','events_enabled','gap_tasks_enabled']):raise RuntimeError('Disabled-hook deployment requires all business hooks off')
for name,expected in payload['expected'].items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Native source changed since preflight')
scope={};exec(payload['patcher'],scope)
allowed={'source_exchange.py','publishing.py','refresh.py','program_updates.py'} if writer_handoff else {'source_exchange.py'} if module_only else {'worker.py','autonomy.py','search_workflow.py'}
if application_writers:allowed|={'engine_ops.py','padel.py','slg.py'}
if set(payload['expected'])-allowed or (preserve_active and set(payload['expected'])!=allowed):raise RuntimeError('Unexpected native deployment file')
files={name:scope['patch_writer_handoff'](name,(root/name).read_text()).encode() for name in allowed-{'source_exchange.py'}} if writer_handoff else {} if module_only else {name:scope['patch_hooks'](name,(root/name).read_text()).encode() for name in payload['expected']}
files['source_exchange.py']=base64.b64decode(payload['module'])
if application_writers:
 target=root/'destination_handoff.py';expected=payload.get('expected_destination_guard')
 if (target.exists() and (not expected or hashlib.sha256(target.read_bytes()).hexdigest()!=expected)) or (not target.exists() and expected):raise RuntimeError('Application writer guard source changed since preflight')
 files['destination_handoff.py']=base64.b64decode(payload['destination_guard'])
for name,body in files.items():compile(body,name,'exec')
sys.path.insert(0,'/opt/source-exchange')
from exchange.factory import initialize
from exchange.contract import Contract
Contract()
if not payload['apply']:
 print(json.dumps({'apply':False,'idle':idle(),'business_flags':'preserved' if preserve_active else 'off','files':{name:hashlib.sha256(body).hexdigest() for name,body in files.items()}}));sys.exit(0)
try:stopped=stop_idle()
except BaseException:
 if command('systemctl','show',unit,'--property=MainPID','--value')=='0':command('systemctl','start',unit)
 raise RuntimeError('Native stop failed; existing configuration preserved') from None
if not stopped:
 print(json.dumps({'apply':False,'state':'busy','business_flags':'preserved' if preserve_active else 'off','reason':'native run or HTTP handler active; no files or schema changed'}));sys.exit(0)
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
 if not preserve_active:
  with database() as db:initialize(db,create=True)
 for name,body in files.items():
  target=root/name;temporary=target.with_name(target.name+'.exchange-release')
  temporary.write_bytes(body);os.chmod(temporary,0o644);temporary.replace(target)
 if not preserve_active:
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
 print(json.dumps({'apply':True,'state':'healthy','native_hooks_installed':True,'business_flags':'preserved' if preserve_active else 'off','factory_config_unchanged':True,'exchange_tables':len(tables),'private_backup':str(backup),'files':{name:hashlib.sha256(body).hexdigest() for name,body in files.items()}}))
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
    parser.add_argument('--expected-worker-sha256')
    parser.add_argument('--expected-autonomy-sha256')
    parser.add_argument('--expected-search-sha256')
    parser.add_argument('--exchange-module-only',action='store_true')
    parser.add_argument('--writer-handoff-hooks',action='store_true')
    parser.add_argument('--application-writers',action='store_true')
    parser.add_argument('--expected-module-sha256')
    parser.add_argument('--expected-publishing-sha256')
    parser.add_argument('--expected-refresh-sha256')
    parser.add_argument('--expected-program-sha256')
    parser.add_argument('--expected-engine-sha256')
    parser.add_argument('--expected-padel-sha256')
    parser.add_argument('--expected-slg-sha256')
    parser.add_argument('--expected-destination-guard-sha256')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    import inspect
    module=Path(__file__).resolve().parents[2]/'factory/source_exchange.py'
    if args.exchange_module_only and args.writer_handoff_hooks:parser.error('Choose one native release mode')
    handoff_digests=[args.expected_publishing_sha256,args.expected_refresh_sha256,args.expected_program_sha256]
    application_digests=[args.expected_engine_sha256,args.expected_padel_sha256,args.expected_slg_sha256]
    if args.application_writers:
        if not args.writer_handoff_hooks or not all(application_digests):parser.error('Application writer release requires handoff mode and all three exact application source digests')
    elif any(application_digests) or args.expected_destination_guard_sha256:parser.error('Application writer digests require --application-writers')
    if args.writer_handoff_hooks:
        if not args.expected_module_sha256 or not all(handoff_digests) or any([args.expected_worker_sha256,args.expected_autonomy_sha256,args.expected_search_sha256]):parser.error('Writer handoff release requires only the current module and three writer digests')
        expected=dict(zip(['source_exchange.py','publishing.py','refresh.py','program_updates.py'],[args.expected_module_sha256,*handoff_digests]))
        if args.application_writers:expected.update(zip(['engine_ops.py','padel.py','slg.py'],application_digests))
    elif any(handoff_digests):parser.error('Writer digests require writer handoff mode')
    elif args.exchange_module_only:
        if not args.expected_module_sha256 or any([args.expected_worker_sha256,args.expected_autonomy_sha256,args.expected_search_sha256]):parser.error('Module-only release requires only the existing module digest')
        expected={'source_exchange.py':args.expected_module_sha256}
    else:
        if not args.expected_worker_sha256 or not args.expected_autonomy_sha256 or args.expected_module_sha256:parser.error('Hook release requires worker and autonomy digests')
        expected={'worker.py':args.expected_worker_sha256,'autonomy.py':args.expected_autonomy_sha256}
        if args.expected_search_sha256:expected['search_workflow.py']=args.expected_search_sha256
    payload={'apply':args.apply,'module_only':args.exchange_module_only,'writer_handoff':args.writer_handoff_hooks,'expected':expected,'module':base64.b64encode(module.read_bytes()).decode(),'patcher':inspect.getsource(patch_hooks)+'\n'+inspect.getsource(patch_writer_handoff)}
    if args.application_writers:payload.update(application_writers=True,destination_guard=base64.b64encode(module.with_name('destination_handoff.py').read_bytes()).decode(),expected_destination_guard=args.expected_destination_guard_sha256)
    result=subprocess.run(['ssh','-i',args.ssh_key,'-o','BatchMode=yes','-o','ConnectTimeout=10',args.host,'python3 -c '+shlex.quote(REMOTE)],input=json.dumps(payload).encode(),capture_output=True,timeout=70)
    if result.returncode:
        raise SystemExit('Factory release refused or needs recovery; inspect private host service and backup state. No customer data is printed.')
    print(json.dumps(json.loads(result.stdout)))


if __name__=='__main__':main()
