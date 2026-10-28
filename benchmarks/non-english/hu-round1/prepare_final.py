"""Retire only this run's failed temporary packages, then stage one final candidate."""
import json,pathlib,shutil,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
ns={'__file__':str(ROOT/'pull_fallback.py')};exec((ROOT/'pull_fallback.py').read_text().split('held=None;stop=')[0],ns);lease=ns['lease']
def native(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:11434'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
held=None;stop=threading.Event();errors=[];timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
try:
 for unit in ['narimato-benchmark-hungarian','narimato-benchmark-hungarian-supplement']:
  assert subprocess.run(['systemctl','is-active','--quiet',unit]).returncode!=0,'Prior batch still active'
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for _ in range(450):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 assert held
 def renew():
  while not stop.wait(25):
   try:lease('renew',held)
   except Exception:errors.append('renew_failed');return
 t=threading.Thread(target=renew,daemon=True);t.start()
 raw=json.loads((ROOT/'results.json').read_text());policy=json.loads(pathlib.Path('/opt/narimato-gateway/config/model-policy.json').read_text());audit=[]
 for name in ['hungarian-qwen35-trimmed:q8_0','hungarian-qwen35-2b:q4_k_m']:
  row=next(r for r in raw['models'] if r['model']==name)
  assert row['status']=='completed' and sum(t.get('correct',False) for t in row['tests'])<20 and name not in policy['models']
  assert name not in [m['name'] for m in native('/api/ps')['models']]
  audit.append({'model':name,'digest':row['tag']['digest'],'reason':'Failed fixed Hungarian acceptance gate; remove this run temporary weights only.'})
  (ROOT/'temporary-cleanup.json').write_text(json.dumps(audit,indent=2)+'\n')
  subprocess.run(['docker','exec','narimato-ollama','ollama','rm',name],check=True,capture_output=True)
 assert shutil.disk_usage('/').free/1024**3-1.934>4,'Known candidate exceeds disk reserve'
 target='hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q3_K_M'
 with (ROOT/'final-pull.log').open('w') as log:subprocess.run(['docker','exec','narimato-ollama','ollama','pull',target],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=360)
 assert not errors and shutil.disk_usage('/').free>4*1024**3
 (ROOT/'final-preparation.json').write_text(json.dumps({'candidate':target,'cleanup_timer_was_active':timer,'temporary_failures_removed':audit},indent=2)+'\n')
 print('Failed temporary weights retired; final 4B Q3 candidate staged within disk budget.')
finally:
 stop.set()
 if held:lease('release',held)
 if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
