"""Apply reviewed round-4 policy without changing runtime/context configuration."""
import json,pathlib,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
policy=json.loads((ROOT/'model-policy.json').read_text())
results=json.loads((ROOT/'results.json').read_text())
assert results.get('finished_utc') and results['restore']['ok']
key=next(line.split('=',1)[1].strip().strip('"').strip("'") for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if line.startswith('GATEWAY_MAINTENANCE_KEY='))
def lease(action,value=None):
    req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def inventory():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=20) as r:return {m['name'].lower():m for m in json.load(r)['models']}
held=None;stop=threading.Event();errors=[];audit={'installed_new_top_five':[],'defaults':policy['defaults'],'policy_id':policy['policy_id']}
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
try:
    for _ in range(90):
        try:held=lease('acquire')['lease'];break
        except urllib.error.HTTPError as e:
            if e.code!=409:raise
            time.sleep(2)
    assert held,'Could not acquire idle lease'
    def renew():
        while not stop.wait(30):
            try:lease('renew',held)
            except Exception as e:errors.append(type(e).__name__);return
    threading.Thread(target=renew,daemon=True).start()
    fresh={m['model'] for m in results['models'] if m['status']=='completed' and not m.get('oom_kill_delta',0)}
    keep=[name for name,meta in policy['models'].items() if name in fresh and any(task['rank']<=5 for task in meta['tasks'].values())]
    for name in keep:
        assert not errors,'Maintenance lease renewal failed'
        subprocess.run(['docker','exec','narimato-ollama','ollama','pull',name],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=360)
        assert inventory()[name.lower()]['digest']==policy['models'][name]['tested_digest'],'Artifact changed after benchmark'
        audit['installed_new_top_five'].append(name)
    inv=inventory()
    for name in policy['defaults'].values():assert inv[name.lower()]['digest']==policy['models'][name]['tested_digest']
    assert not errors,'Maintenance lease renewal failed'
    target=pathlib.Path('/opt/narimato-gateway/config/model-policy.json')
    backup=ROOT/'policy-before-round4.json';backup.write_bytes(target.read_bytes());backup.chmod(0o600)
    temp=target.with_suffix('.round4.tmp');temp.write_text(json.dumps(policy,indent=2)+'\n');temp.chmod(0o644);temp.replace(target)
    target=pathlib.Path('/opt/narimato-discovery/tested-models.json')
    temp=target.with_suffix('.round4.tmp');temp.write_bytes((ROOT/'tested-models.json').read_bytes());temp.chmod(0o644);temp.replace(target)
    audit['deployed']=True
finally:
    stop.set()
    if held:lease('release',held)
    subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
    (ROOT/'deployment.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit))
