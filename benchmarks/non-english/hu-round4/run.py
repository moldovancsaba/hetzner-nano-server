"""Hungarian-only native evaluation of one candidate under the gateway maintenance lease; run on the inference host.

Uses the frozen fixtures.json (the original
24 structured and 6 chat cases plus five separate synthetic Habi regressions). The candidate is pulled if absent, evaluated at
the plan's profile, unloaded and removed again unless it was installed before; the cleanup timer is stopped for the run and
restarted afterwards, and Granite is exercised once to prove the host serves again. Writes results.json next to this file."""
import datetime,hashlib,json,pathlib,subprocess,threading,time,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent

# Native helpers, as in ../../round4/run.py (kept here so this run needs no sibling files).
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:11434'+path,timeout=20) as r:return json.load(r)
def post(path,data,timeout=120,base='http://127.0.0.1:11434',key=None):
 headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
 if key:headers['Authorization']='Bearer '+key
 req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def cgroup():
 pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip()
 group=pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1]
 return pathlib.Path('/sys/fs/cgroup'+group)
CG=cgroup()
def memory():
 return {'current_bytes':int((CG/'memory.current').read_text()),'events':{k:int(v) for k,v in (line.split() for line in (CG/'memory.events').read_text().splitlines())}}
def resident():return get('/api/ps')['models']
def unload():
 started=time.monotonic()
 for m in resident():post('/api/generate',{'model':m['name'],'keep_alive':0},45)
 end=time.monotonic()+45
 while resident():
  if time.monotonic()>end:raise RuntimeError('Resident did not unload; stop rather than overlap inference')
  time.sleep(.3)
 return round(time.monotonic()-started,3)
def infer(payload,timeout=120):
 started=time.monotonic();stop=threading.Event();peak=[memory()['current_bytes']]
 def sample():
  while not stop.wait(.1):peak[0]=max(peak[0],memory()['current_bytes'])
 thread=threading.Thread(target=sample,daemon=True);thread.start()
 result={}
 try:
  try:data=post('/api/chat' if 'messages' in payload else '/api/generate',payload,timeout)
  except urllib.error.HTTPError as e:
   error=e.read().decode()[:1200]
   if 'does not support thinking' in error.lower() and 'think' in payload:
    payload=dict(payload);payload.pop('think');data=post('/api/chat' if 'messages' in payload else '/api/generate',payload,timeout)
   else:raise RuntimeError(error)
  content=data.get('message',{}).get('content',data.get('response',''))
  result={'ok':True,'response':content,'done_reason':data.get('done_reason'),'load_seconds':round(data.get('load_duration',0)/1e9,4),'prompt_tokens':data.get('prompt_eval_count'),'output_tokens':data.get('eval_count'),'tool_calls':data.get('message',{}).get('tool_calls',[])}
 except Exception as e:
  result={'ok':False,'error_type':type(e).__name__,'error':str(e)[:1200]}
  # A timed out native request may still run. Unload synchronously and verify idle.
  if isinstance(e,(TimeoutError,OSError)):unload()
 finally:
  stop.set();thread.join(2)
 result.update(seconds=round(time.monotonic()-started,4),peak_cgroup_bytes=peak[0]);return result

plan=json.loads((ROOT/'plan.json').read_text());fixtures=json.loads((ROOT/'fixtures.json').read_text())
report={'version':'hungarian-evaluation.v1','language':'hu','started_utc':now(),'settings':plan['settings'],'runtime':get('/api/version'),'fixture_sha256':hashlib.sha256((ROOT/'fixtures.json').read_bytes()).hexdigest(),'models':[]}
def save():
 p=ROOT/'results.tmp';p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');p.replace(ROOT/'results.json')
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def maint(action,lease=None):return post('/internal/model-storage',{'action':action,'lease':lease},base='http://127.0.0.1:8090',key=KEY)
def guarded(fn):
 held=None;stop=threading.Event();errors=[];deadline=time.monotonic()+900
 while held is None:
  try:held=maint('acquire')['lease']
  except urllib.error.HTTPError as e:
   if e.code!=409 or time.monotonic()>deadline:raise
   time.sleep(3)
 def renew():
  while not stop.wait(25):
   try:maint('renew',held)
   except Exception:errors.append('renew_failed');return
 t=threading.Thread(target=renew,daemon=True);t.start()
 try:
  value=fn()
  if errors:raise RuntimeError('Lease renewal failed')
  return value
 finally:
  stop.set();t.join(2);maint('release',held);time.sleep(2)

initial={m['name'].lower() for m in get('/api/tags')['models']}
def prepare(model):
 import shutil
 if not any(m['name'].lower()==model.lower() for m in get('/api/tags')['models']):
  assert shutil.disk_usage('/').free > 5*1024**3, 'Insufficient staging reserve'
  subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],check=True,capture_output=True,timeout=900)
 return next(m for m in get('/api/tags')['models'] if m['name'].lower()==model.lower())

timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
SYSTEM='Segítőkész magyar nyelvű asszisztens vagy. Magyarul válaszolj. Csak a megadott adatokból dolgozz; ismeretlen adatot ne találj ki.'
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for model in plan['models']:
  profile=plan['model_profiles'].get(model,{'num_ctx':plan['settings']['num_ctx'],'num_batch':plan['settings']['num_batch']})
  entry={'model':model,'status':'preparing','tests':[],'operating_profile':profile};report['models'].append(entry);save();print('START',model,flush=True)
  try:
   entry['tag']=guarded(lambda: prepare(model))
   try:
    shown=post('/api/show',{'model':model});entry['show']={'details':shown.get('details'),'template':(shown.get('template') or '')[:1500],'parameters':shown.get('parameters')}
   except Exception as e:entry['show']={'error':str(e)[:300]}
   guarded(unload);before=memory();entry['memory_before']=before
   for case in fixtures['cases']:
    body={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':case['prompt']}],'stream':False,'keep_alive':'1m','options':{'num_ctx':profile['num_ctx'],'num_batch':profile['num_batch'],'num_predict':plan['settings']['num_predict'],'temperature':0}}
    if case['kind']=='structured':body['format']='json'
    row=guarded(lambda:infer(body,timeout=180));row.update(id=case['id'],kind=case['kind'])
    if case['kind']=='structured':
     try:
      value=json.loads(row.get('response',''));row['json_valid']=True;row['correct']=row['ok'] and value==case['expected'] and row.get('done_reason')!='length'
     except (ValueError,TypeError):row.update(json_valid=False,correct=False)
    entry['tests'].append(row);save();print('CASE',case['id'],row.get('correct',row['ok']),row['seconds'],flush=True)
    if memory()['events'].get('oom_kill',0)>before['events'].get('oom_kill',0):raise RuntimeError('OOM during Hungarian evaluation')
   entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0);entry['status']='completed'
  except Exception as e:
   entry.update(status='failed',error_type=type(e).__name__,error=str(e)[:700])
   if 'memory_before' in entry:entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-entry['memory_before']['events'].get('oom_kill',0)
  finally:
   save();guarded(unload)
   if model.lower() not in initial:guarded(lambda: subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],check=True,capture_output=True,timeout=60))
   print('DONE',model,entry['status'],flush=True)
finally:
 try:
  report['restore']=guarded(lambda:infer({'model':'granite4:1b-h','prompt':'Reply READY.','stream':False,'think':False,'options':{'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}}))
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();print('FINISHED',flush=True)
