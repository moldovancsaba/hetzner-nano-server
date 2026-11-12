"""Digest-guarded reporting release using the existing native idle fence."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import backup
SPEC=importlib.util.spec_from_file_location('native_deploy',ROOT/'integration/ops/deploy_factory.py')
NATIVE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(NATIVE)
ANCHOR='configpath=root/'
if NATIVE.REMOTE.count(ANCHOR)!=1:raise RuntimeError('Native idle fence boundary changed')
REMOTE=NATIVE.REMOTE.split(ANCHOR)[0]+r'''
import fcntl
release_lock=open('/run/narimato-reporting-release.lock','a');fcntl.flock(release_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
allowed={'business_metrics.py','native_reporting.py','native_reporting.mjs','native_reporting_contract.json','native_reporting_service.py','worker.py'}
if set(payload['files'])!=allowed or set(payload['expected'])!=allowed:raise ValueError('Unexpected reporting release scope')
for name,expected in payload['expected'].items():
 path=root/name
 if (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)!=expected:raise RuntimeError('Reporting source changed since preflight')
for name,encoded in payload['files'].items():
 if name.endswith('.py'):compile(base64.b64decode(encoded),name,'exec')
configpath=root/'factory.json';configbytes=configpath.read_bytes()
if not payload['apply']:
 print(json.dumps({'apply':False,'idle':idle(),'configuration_preserved':True}));sys.exit(0)
deadline=time.monotonic()+45
while not idle() and time.monotonic()<deadline:time.sleep(.5)
if not stop_idle():
 print(json.dumps({'apply':False,'state':'busy','configuration_preserved':True}));sys.exit(0)
saved=pathlib.Path('/var/backups/source-exchange')/('reporting-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));mutated=[]
try:
 saved.mkdir(mode=0o700,parents=True)
 for name,expected in payload['expected'].items():
  if expected:shutil.copy2(root/name,saved/name)
 if configpath.read_bytes()!=configbytes:raise RuntimeError('Factory configuration changed')
 for name,encoded in payload['files'].items():
  target=root/name;temp=target.with_suffix(target.suffix+'.reporting-release');temp.write_bytes(base64.b64decode(encoded));temp.chmod(0o644);temp.replace(target);mutated.append(name)
 command('systemctl','start',unit)
 for _ in range(40):
  try:
   with urllib.request.urlopen('http://127.0.0.1:9089/health',timeout=1) as response:health=json.load(response)
   if health.get('status')=='ok':break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Factory health did not recover')
 if configpath.read_bytes()!=configbytes:raise RuntimeError('Factory configuration changed')
 print(json.dumps({'apply':True,'state':'healthy','configuration_preserved':True,'rollback_directory':str(saved),'hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in allowed}}))
except BaseException:
 if command('systemctl','show',unit,'--property=MainPID','--value')!='0' and not stop_idle():raise RuntimeError('Rollback waits for native idle; active work preserved') from None
 for name in mutated:
  if payload['expected'][name]:shutil.copy2(saved/name,root/name)
  else:(root/name).unlink(missing_ok=True)
 command('systemctl','start',unit)
 raise
'''


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 expected=json.loads(args.plan.read_text())
 names=['business_metrics.py','native_reporting.py','native_reporting.mjs','native_reporting_contract.json','native_reporting_service.py','worker.py']
 payload={'expected':{name:expected[name] for name in names},'files':{name:base64.b64encode((ROOT/'factory'/name).read_bytes()).decode() for name in names},'apply':args.apply}
 result=subprocess.run(backup.SSH+['python3 -c '+shlex.quote(REMOTE)],input=json.dumps(payload),capture_output=True,text=True,timeout=60)
 if result.returncode:raise RuntimeError('Reporting release failed; inspect private diagnostics')
 print(result.stdout.strip())


if __name__=='__main__':main()
