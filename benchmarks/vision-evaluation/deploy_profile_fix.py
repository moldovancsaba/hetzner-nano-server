"""Minimal, idle, recoverable patch: pass a tested per-model thinking control."""
import hashlib,json,pathlib,shutil,subprocess,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
key=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def lease(action,value=None):
    req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
held=None;changed=[];backup=ROOT/('profile-backup-'+str(int(time.time())));backup.mkdir(mode=0o700)
def update(path,text):
    path=pathlib.Path(path);copy=backup/(str(len(changed))+'-'+path.name);shutil.copy2(path,copy);changed.append((path,copy));tmp=path.with_suffix('.profile.tmp');tmp.write_text(text);tmp.chmod(0o644);tmp.replace(path)
try:
    for _ in range(180):
        try:held=lease('acquire')['lease'];break
        except urllib.error.HTTPError as e:
            if e.code!=409:raise
            time.sleep(1)
    assert held,'No idle guard; no patch'
    path=pathlib.Path('/opt/narimato-gateway/moderation/server.py');text=path.read_text();assert text.count('def infer(image, model=MODEL):')==1
    text=text.replace('def infer(image, model=MODEL):','def infer(image, model=MODEL, think=None):').replace("    request = urllib.request.Request('http://127.0.0.1:11434/api/generate',", "    if think is not None:\n        body['think'] = think\n    request = urllib.request.Request('http://127.0.0.1:11434/api/generate',");update(path,text)
    path=pathlib.Path('/opt/narimato-gateway/gateway/server.py');text=path.read_text();assert text.count('result = moderation_infer(payload, model=model)')==1
    text=text.replace('result = moderation_infer(payload, model=model)',"result = moderation_infer(payload, model=model, think=profile.get('think'))")
    old="'options': {'num_ctx': 2048, 'num_batch': 32, 'num_predict': 256, 'temperature': 0}})";assert text.count(old)==1
    text=text.replace(old,"'options': {'num_ctx': 2048, 'num_batch': 32, 'num_predict': 256, 'temperature': 0},\n                **({'think': profile['think']} if 'think' in profile else {})})");update(path,text)
    subprocess.run(['/opt/narimato-gateway-venv/bin/python','-m','py_compile',str(path),'/opt/narimato-gateway/moderation/server.py'],check=True)
    path=pathlib.Path('/opt/narimato-gateway/config/model-policy.json');policy=json.loads(path.read_text());policy['models']['qwen3.5:0.8b']['tasks']['image_recognition']['profile']['think']=False
    policy.pop('policy_id');policy['policy_id']=hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest();update(path,json.dumps(policy,indent=2)+'\n')
    subprocess.run(['systemctl','restart','narimato-gateway'],check=True)
    for _ in range(40):
        try:lease('renew',held);break
        except Exception:time.sleep(.5)
    else:raise RuntimeError('Gateway did not restore with the persisted lease')
    print(json.dumps({'patched':True,'profile':'qwen3.5 image recognition think=false','defaults_unchanged':True}))
except Exception:
    for path,copy in reversed(changed):shutil.copy2(copy,path)
    if changed:subprocess.run(['systemctl','restart','narimato-gateway'],check=True)
    raise
finally:
    if held:
        for _ in range(40):
            try:lease('release',held);break
            except Exception:time.sleep(.5)
