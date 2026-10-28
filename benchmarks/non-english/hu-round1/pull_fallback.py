"""Download a bounded larger Hungarian candidate under the same idle guard."""
import json,pathlib,shutil,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def lease(action,value=None):
 req=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','X-Request-Purpose':'test'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
held=None;stop=threading.Event();errors=[]
try:
 assert shutil.disk_usage('/').free/1024**3-1.813>4,'Known manifest would cross hard floor'
 for _ in range(450):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 assert held,'No idle guard'
 def renew():
  while not stop.wait(25):
   try:lease('renew',held)
   except Exception:errors.append('renew_failed');return
 t=threading.Thread(target=renew,daemon=True);t.start()
 with (ROOT/'fallback-pull.log').open('w') as log:subprocess.run(['docker','exec','narimato-ollama','ollama','pull','qwen3.5:2b-q4_K_M'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=360)
 assert not errors and shutil.disk_usage('/').free>4*1024**3
 print('Qwen 3.5 2B Q4 candidate downloaded; hard disk floor preserved.')
finally:
 stop.set()
 if held:lease('release',held)
