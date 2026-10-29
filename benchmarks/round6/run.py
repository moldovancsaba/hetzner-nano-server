"""Full frozen text, recognition, moderation and separately-scored Hungarian suites."""
import base64,hashlib,json,pathlib,subprocess,threading,time,shutil,sys,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
source=(ROOT.parent/'round4/run.py').read_text().split("key=next(line.split",1)[0]
ns={'__file__':str(ROOT/'run.py'),'__name__':'round6_shared'};exec(compile(source,'round4_shared','exec'),ns)
now,get,post,memory,unload,infer,payload=[ns[x] for x in ['now','get','post','memory','unload','infer','payload']]
plan=json.loads((ROOT/'plan.json').read_text());manifest=json.loads((ROOT/'recognition-manifest.json').read_text());moderation=json.loads((ROOT/'moderation-manifest.json').read_text());hu=json.loads((ROOT/'hu-fixtures.json').read_text());images=ROOT/'inputs'
report={'version':'round6.v1','started_utc':now(),'runtime':get('/api/version'),'settings':plan['settings'],'scope':plan['scope'],'models':[],'controls':[],'fixture_hashes':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['recognition-manifest.json','moderation-manifest.json','hu-fixtures.json']}}
initial={m['name'].lower() for m in get('/api/tags')['models']}
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def save():
 p=ROOT/'results.tmp';p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');p.replace(ROOT/'results.json')
ns['report']=report;ns['save']=save
sys.path.insert(0,'/opt/narimato-gateway')
from gateway.server import Runner,UpstreamUncertain
from moderation.server import normalize_image
class Profile:
 def profile(self,task,model):return plan['image_profile']
runner=Runner(catalog=Profile())
def maintenance(action,value=None):return post('/internal/model-storage',{'action':action,'lease':value},base='http://127.0.0.1:8090',key=KEY)
def guarded(fn):
 held=None;deadline=time.monotonic()+900
 while held is None:
  try:held=maintenance('acquire')['lease']
  except urllib.error.HTTPError as e:
   if e.code!=409 or time.monotonic()>deadline:raise
   time.sleep(3)
 stop=threading.Event();errors=[]
 def renew():
  while not stop.wait(25):
   try:maintenance('renew',held)
   except Exception:errors.append('lease_renewal_failed');return
 thread=threading.Thread(target=renew,daemon=True);thread.start()
 try:
  value=fn()
  if errors:raise RuntimeError(errors[0])
  return value
 finally:
  stop.set();thread.join(2);maintenance('release',held);time.sleep(2)
def prepare(candidate):
 model=candidate['model'];unload()
 if model.lower() not in initial:
  budget=candidate.get('expected_primary_bytes',0)+candidate.get('maximum_projector_bytes',0)+plan['settings']['disk_staging_margin_bytes']
  assert shutil.disk_usage('/').free>4*1024**3+budget,'Disk preflight refuses to cross 4 GiB floor'
  with (ROOT/'pull.log').open('w') as log:subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert shutil.disk_usage('/').free>4*1024**3,'Hard disk floor'
 tag=next(m for m in get('/api/tags')['models'] if m['name'].lower()==model.lower());show=post('/api/show',{'model':model})
 return tag,{'capabilities':show.get('capabilities'),'license':show.get('license','')[:800],'native_model_info':show.get('model_info',{})}
def image_case(model,case,task):
 before=memory();peak=[before['current_bytes']];stop=threading.Event()
 def sample():
  while not stop.wait(.1):peak[0]=max(peak[0],memory()['current_bytes'])
 thread=threading.Thread(target=sample,daemon=True);thread.start();started=time.monotonic();row={'id':case['id'],'model':model,'status':'failed'}
 try:
  raw=(images/case['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256'];image=normalize_image(base64.b64encode(raw).decode())[0]
  if task=='count':
   runner.switch(model)
   d=post('/api/generate',{'model':model,'prompt':'Count the visible '+case['primary_object']+' objects in the image. Return count as an integer, or null if genuinely too occluded/unclear. Do not count pictures or text naming an object.','images':[base64.b64encode(image).decode()],'format':{'type':'object','properties':{'count':{'type':['integer','null']}},'required':['count'],'additionalProperties':False},'stream':False,'keep_alive':'1m','think':False,'options':{'num_ctx':2048,'num_batch':32,'num_predict':64,'temperature':0}},timeout=120)
   value=json.loads(d.get('response','{}'));valid=set(value)=={'count'} and (type(value['count']) is int or value['count'] is None) and d.get('done') and d.get('done_reason')!='length';row.update(status='completed',json_valid=valid,count=value.get('count'),done_reason=d.get('done_reason'),load_seconds=d.get('load_duration',0)/1e9)
  else:
   result,switch=runner(task,image,model);row.update(status='completed',result=result,model_switch=switch)
   if task=='image_moderation':
    mapping={'detected':True,'not_detected':False,'uncertain':None};row.update(valid=True,parsed={'categories':{k:mapping[v] for k,v in result['categories'].items()},'evidence':result.get('evidence','')})
 except Exception as e:
  row.update(error_type=type(e).__name__,error=str(e)[:800],valid=False)
  if isinstance(e,(UpstreamUncertain,TimeoutError,OSError)):unload();raise RuntimeError('Upstream resource/timeout uncertainty; stop candidate') from e
 finally:
  stop.set();thread.join(2);row.update(seconds=round(time.monotonic()-started,4),inference_wall_seconds=round(time.monotonic()-started,4),peak_cgroup_bytes=peak[0],oom_kill_delta=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0))
 return row
def hu_case(model,case):
 options={k:v for k,v in plan['hungarian_profile'].items() if k!='temperature'};options.update(temperature=0)
 body={'model':model,'messages':[{'role':'system','content':'Segítőkész magyar nyelvű asszisztens vagy. Magyarul válaszolj. Csak a megadott adatokból dolgozz; ismeretlen adatot ne találj ki.'},{'role':'user','content':case['prompt']}],'think':False,'stream':False,'keep_alive':'1m','options':options}
 if case['kind']=='structured':body['format']='json'
 row=infer(body,120);row.update(id=case['id'],kind=case['kind']);return row

timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0;report['cleanup_timer_was_active']=timer;save()
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for candidate in [{'model':'granite4:1b-h','task':'text','control':True}]+plan['candidates']:
  model=candidate['model'];entry={**candidate,'status':'preparing','started_utc':now()};report['controls' if candidate.get('control') else 'models'].append(entry);save();print('START',model,flush=True)
  try:
   tag,meta=guarded(lambda:prepare(candidate));entry.update(tag=tag,**meta);before=memory();entry['memory_before']=before;save()
   if candidate['task']=='text':
    guarded(lambda:ns['test'](entry));entry['english_status']=entry['status']
    if not candidate.get('control') and entry['status']=='completed':
     entry['hungarian']=[]
     for case in hu['cases']:
      row=guarded(lambda c=case:hu_case(model,c));entry['hungarian'].append(row);save();print('HU',model,case['id'],row['ok'],flush=True)
      if memory()['events'].get('oom_kill',0)>before['events'].get('oom_kill',0):raise RuntimeError('OOM during Hungarian suite; stop candidate')
      if not row['ok'] and row.get('error_type') in ['TimeoutError','URLError','OSError']:raise RuntimeError('Hungarian upstream uncertainty; stop candidate')
      if len(entry['hungarian'])>=3 and all(not t['ok'] for t in entry['hungarian'][-3:]):raise RuntimeError('Three consecutive Hungarian technical failures; stop candidate')
   else:
    entry.update(tests=[],robustness=[],counts=[],moderation=[],status='running')
    fields=[('tests',manifest['recognition'],'image_recognition'),('robustness',manifest['robustness'],'image_recognition'),('counts',[c for c in manifest['recognition'] if c.get('count_probe')],'count'),('moderation',moderation['cases'],'image_moderation')]
    for field,cases,task in fields:
     for case in cases:
      row=guarded(lambda c=case,t=task:image_case(model,c,t));entry[field].append(row);save();print('CASE',model,field,case['id'],row['status'],row['seconds'],flush=True)
      if row['oom_kill_delta']:raise RuntimeError('OOM observed; stop candidate')
      if len(entry[field])>=3 and all(t['status']=='failed' for t in entry[field][-3:]):raise RuntimeError('Three consecutive technical failures; stop candidate')
    entry['status']='completed'
   entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)
  except Exception as e:entry.update(status='failed',error_type=type(e).__name__,error=str(e)[:800])
  finally:
   entry['finished_utc']=now();save();guarded(unload)
   if model.lower() not in initial:
    guarded(lambda:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],capture_output=True,timeout=60));entry['temporary_weights_removed']=not any(m['name'].lower()==model.lower() for m in get('/api/tags')['models'])
   entry['disk_free_gib']=round(shutil.disk_usage('/').free/1024**3,3);save();print('DONE',model,entry['status'],flush=True)
finally:
 try:
  def restore():
   unload();return infer(payload('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
  report['restore']=guarded(restore)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();print('FINISHED',flush=True)
