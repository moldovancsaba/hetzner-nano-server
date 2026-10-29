"""Atomically deploy the reviewed policy and tested-model index under the shared idle guard.

Run on the inference host beside model-policy.reviewed.json and tested-models.reviewed.json.
Unlike Round 5 this never pulls weights: installed packages are digest-checked, every other
package stays blocked (the disk reserve does not allow downloads while storage is low).
"""
import json,pathlib,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent;policy=json.loads((ROOT/'model-policy.reviewed.json').read_text())
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def lease(action,value=None):
    req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY})
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def inventory():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=20) as r:return {m['name'].lower():m for m in json.load(r)['models']}
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
held=None;stop=threading.Event();errors=[];audit={'policy_id':policy['policy_id'],'defaults':policy['defaults'],'verified_installed':[],'blocked_not_installed':[],'deployed':False};target=pathlib.Path('/opt/narimato-gateway/config/model-policy.json')
try:
    for _ in range(300):
        try:held=lease('acquire')['lease'];break
        except urllib.error.HTTPError as e:
            if e.code!=409:raise
            time.sleep(1)
    assert held,'No idle guard; production takes priority'
    def renew():
        while not stop.wait(30):
            try:lease('renew',held)
            except Exception as e:errors.append(type(e).__name__);return
    threading.Thread(target=renew,daemon=True).start()
    inv=inventory()
    for name in policy['defaults'].values():assert name.lower() in inv,'Default not installed: '+name
    for name,entry in sorted(policy['models'].items()):
        if name.lower() in inv:
            assert inv[name.lower()]['digest']==entry['tested_digest'],'Artifact changed: '+name
            audit['verified_installed'].append(name)
        else:audit['blocked_not_installed'].append(name)
    assert not errors,'Maintenance lease renewal failed'
    backup=ROOT/('policy-before-'+str(int(time.time()))+'.json');backup.write_bytes(target.read_bytes());backup.chmod(0o600)
    tmp=target.with_suffix('.reviewed.tmp');tmp.write_text(json.dumps(policy,indent=2)+'\n');tmp.chmod(0o644);tmp.replace(target)
    index=ROOT/'tested-models.reviewed.json'
    if index.exists():
        dest=pathlib.Path('/opt/narimato-discovery/tested-models.json');tmp=dest.with_suffix('.reviewed.tmp');tmp.write_bytes(index.read_bytes());tmp.chmod(0o644);tmp.replace(dest)
    audit['deployed']=True
finally:
    stop.set()
    if held:lease('release',held)
    if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
    (ROOT/'deployment-latest.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit))
