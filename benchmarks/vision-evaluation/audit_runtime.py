"""Read-only runtime audit; optional removal of completed-run temporary inputs."""
import argparse,datetime,hashlib,json,pathlib,shutil,subprocess,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--clean-inputs',action='store_true');args=parser.parse_args()
assert ROOT==pathlib.Path('/opt/narimato-benchmarks/vision-evaluation'),'Run only in the documented server evaluation directory'
def command(*parts):return subprocess.check_output(parts,text=True).strip()
def native(path):
    with urllib.request.urlopen('http://127.0.0.1:11434'+path,timeout=20) as response:return json.load(response)
def state(unit):return subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True).stdout.strip()
for filename in ['recognition-results.json','moderation-results.json']:
    result=json.loads((ROOT/filename).read_text());assert result['status']=='completed' and result.get('restore',{}).get('status')=='completed','Incomplete run/restoration'
assert all(state(unit)!='active' for unit in ['narimato-vision-recognition.service','narimato-vision-moderation.service']),'Benchmark still active'
audit={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'temporary_inputs':{}}
for name in ['inputs','moderation-inputs']:
    path=ROOT/name;assert not path.is_symlink(),'Refuse symlink input directory'
    count=sum(p.is_file() for p in path.rglob('*')) if path.exists() else 0
    if args.clean_inputs and path.exists():shutil.rmtree(path)
    audit['temporary_inputs'][name]={'files_before':count,'removed':args.clean_inputs,'exists_after':path.exists()}
audit['services']={unit:state(unit) for unit in ['caddy','docker','narimato-gateway','narimato-chat','narimato-moderation','narimato-model-cleanup.timer','narimato-model-discovery.timer']}
info=json.loads(command('docker','inspect','narimato-ollama'))[0]
audit['runtime']={'image_id':info['Image'],'memory_limit_bytes':info['HostConfig']['Memory'],'nano_cpus':info['HostConfig']['NanoCpus'],'oom_killed':info['State']['OOMKilled'],'version':native('/api/version'),'resident_models':[r['name'] for r in native('/api/ps')['models']]}
pid=str(info['State']['Pid']);cg=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1].lstrip('/')
audit['memory_events']={key:int(value) for key,value in (line.split() for line in (cg/'memory.events').read_text().splitlines())}
audit['disk_free_gib']=round(shutil.disk_usage('/').free/1024**3,3)
policy=json.loads(pathlib.Path('/opt/narimato-gateway/config/model-policy.json').read_text());audit['policy_id']=policy['policy_id'];audit['defaults']=policy['defaults']
inventory={row['name'].lower():row for row in native('/api/tags')['models']};audit['installed_models']=len(inventory)
audit['default_artifacts_match']={task:inventory.get(name.lower(),{}).get('digest')==policy['models'][name]['tested_digest'] for task,name in policy['defaults'].items()}
audit['source_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [pathlib.Path('/opt/narimato-gateway/gateway/server.py'),pathlib.Path('/opt/narimato-gateway/moderation/server.py'),pathlib.Path('/opt/narimato-gateway/moderation/policy.py')]}
audit['passed']=all(audit['services'][unit]=='active' for unit in ['caddy','docker','narimato-gateway','narimato-chat','narimato-model-cleanup.timer','narimato-model-discovery.timer']) and audit['services']['narimato-moderation']!='active' and all(audit['default_artifacts_match'].values()) and not audit['runtime']['oom_killed'] and not audit['memory_events']['oom_kill'] and audit['disk_free_gib']>=4
(ROOT/'final-runtime-audit.json').write_text(json.dumps(audit,indent=2)+'\n');assert audit['passed'],'Review failed final runtime audit'
print(json.dumps({'passed':audit['passed'],'policy_id':audit['policy_id'],'disk_free_gib':audit['disk_free_gib'],'temporary_inputs_removed':args.clean_inputs}))
