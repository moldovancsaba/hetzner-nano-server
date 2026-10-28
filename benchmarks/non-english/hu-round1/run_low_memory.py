"""Hungarian-only native evaluation with per-case renewable maintenance leases."""
import datetime,hashlib,json,pathlib,subprocess,threading,time,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
ns={'__file__':str(ROOT/'run.py'),'__name__':'hu_shared'}
source=(ROOT.parent/'round4/run.py').read_text().split("key=next(line.split",1)[0]
exec(compile(source,'round4_shared','exec'),ns)
get,post,infer,unload,memory,now=[ns[x] for x in ['get','post','infer','unload','memory','now']]
plan=json.loads((ROOT/'plan.json').read_text());fixtures=json.loads((ROOT/'fixtures.json').read_text())
report={'version':'hungarian-evaluation.v1','language':'hu','started_utc':now(),'settings':plan['settings'],'runtime':get('/api/version'),'fixture_sha256':hashlib.sha256((ROOT/'fixtures.json').read_bytes()).hexdigest(),'models':[]}
resume=ROOT/'resume.json'
if resume.exists():
 report=json.loads(resume.read_text());assert report['fixture_sha256']==hashlib.sha256((ROOT/'fixtures.json').read_bytes()).hexdigest()
 report.setdefault('resume_events',[]).append({'at':now(),'reason':'Add reviewed 2B text-only fallback; no completed candidate is rerun.'})
 report.setdefault('prior_restorations',[]).append(report.pop('restore',None));report.pop('finished_utc',None)
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
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0 or (json.loads((ROOT/'installation.json').read_text()).get('cleanup_timer_was_active',False) if (ROOT/'installation.json').exists() else False)
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for model in plan['models']:
  if any(m['model']==model and m['status']=='completed' for m in report['models']):continue
  entry={'model':model,'status':'preparing','tests':[],'operating_profile':plan.get('model_profiles',{}).get(model,{'num_ctx':2048,'num_batch':32})};report['models'].append(entry);save();print('START',model,flush=True)
  try:
   entry['tag']=next(m for m in get('/api/tags')['models'] if m['name'].lower()==model.lower())
   guarded(unload);before=memory();entry['memory_before']=before
   for case in fixtures['cases']:
    body={'model':model,'messages':[{'role':'system','content':'Segítőkész magyar nyelvű asszisztens vagy. Magyarul válaszolj. Csak a megadott adatokból dolgozz; ismeretlen adatot ne találj ki.'},{'role':'user','content':case['prompt']}],'think':False,'stream':False,'keep_alive':'1m','options':{'num_ctx':entry['operating_profile']['num_ctx'],'num_batch':entry['operating_profile']['num_batch'],'num_predict':192,'temperature':0}}
    if case['kind']=='structured':body['format']='json'
    row=guarded(lambda:infer(body,timeout=120));row.update(id=case['id'],kind=case['kind'])
    if case['kind']=='structured':
     try:
      value=json.loads(row.get('response',''));row['json_valid']=True;row['correct']=row['ok'] and value==case['expected'] and row.get('done_reason')!='length'
     except (ValueError,TypeError):row.update(json_valid=False,correct=False)
    entry['tests'].append(row);save();print('CASE',model,case['id'],row.get('correct',row['ok']),row['seconds'],flush=True)
    if memory()['events'].get('oom_kill',0)>before['events'].get('oom_kill',0):raise RuntimeError('OOM during Hungarian evaluation')
   entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0);entry['status']='completed'
  except Exception as e:
   entry.update(status='failed',error_type=type(e).__name__,error=str(e)[:700])
   if 'memory_before' in entry:entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-entry['memory_before']['events'].get('oom_kill',0)
  finally:save();guarded(unload);print('DONE',model,entry['status'],flush=True)
finally:
 try:
  report['restore']=guarded(lambda:infer({'model':'granite4:1b-h','prompt':'Reply READY.','stream':False,'think':False,'options':{'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}}))
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();print('FINISHED',flush=True)
