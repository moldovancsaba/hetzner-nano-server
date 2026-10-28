"""Serial native evaluations with an idle gateway lease per bounded work unit.
No customer payloads. Uses frozen research inputs and exact production image Runner.
"""
import base64,hashlib,json,pathlib,subprocess,threading,time,shutil,sys,traceback
ROOT=pathlib.Path(__file__).resolve().parent
# Reuse the previous English prompts, validators, memory sampling and unload logic.
source=(ROOT.parent/'round4/run.py').read_text().split("key=next(line.split",1)[0]
ns={'__file__':str(ROOT/'run.py'),'__name__':'round5_shared'}
exec(compile(source,'round4_shared','exec'),ns)
now,get,post,memory,unload,infer,payload=[ns[x] for x in ['now','get','post','memory','unload','infer','payload']]
plan=json.loads((ROOT/'plan.json').read_text())
report={'version':'round5.v1','started_utc':now(),'runtime':get('/api/version'),'settings':plan['settings'],'models':[],'controls':[],'scope':plan['scope']}
initial={m['name'].lower() for m in get('/api/tags')['models']};held=None
KEY=next(line.split('=',1)[1].strip().strip('"').strip("'") for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if line.startswith('GATEWAY_MAINTENANCE_KEY='))
def save():
 p=ROOT/'results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'results.json')
ns['report']=report;ns['save']=save
sys.path.insert(0,'/opt/narimato-gateway')
from gateway.server import Runner
from moderation.server import normalize_image
class Profile:
 def profile(self,task,model):return {'max_image_edge':640,'num_ctx':2048,'num_batch':32,'think':False}
runner=Runner(catalog=Profile())
manifest=json.loads((ROOT/'recognition-manifest.json').read_text());images=ROOT/'inputs'
report['manifest_sha256']=hashlib.sha256((ROOT/'recognition-manifest.json').read_bytes()).hexdigest()
def maintenance(action,value=None):return post('/internal/model-storage',{'action':action,'lease':value},base='http://127.0.0.1:8090',key=KEY)
def guarded(fn):
 global held
 deadline=time.monotonic()+600
 while True:
  try:held=maintenance('acquire')['lease'];break
  except Exception as e:
   if getattr(e,'code',None)!=409 or time.monotonic()>deadline:raise
   time.sleep(3)
 stop=threading.Event();errors=[]
 def renew():
  while not stop.wait(25):
   try:maintenance('renew',held)
   except Exception:errors.append('renewal_failed');return
 thread=threading.Thread(target=renew,daemon=True);thread.start()
 try:
  result=fn()
  if errors:raise RuntimeError('Maintenance lease renewal failed')
  return result
 finally:
  stop.set();thread.join(2)
  maintenance('release',held);held=None
  time.sleep(2)
def prepare(model):
 unload()
 assert shutil.disk_usage('/').free>6*1024**3,'Download reserve preflight'
 if model.lower() not in initial:
  with (ROOT/'pull.log').open('w') as log:
   subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=360)
 assert shutil.disk_usage('/').free>4*1024**3,'Hard disk floor'
 tag=next(m for m in get('/api/tags')['models'] if m['name'].lower()==model.lower())
 show=post('/api/show',{'model':model})
 return tag,{'capabilities':show.get('capabilities'),'license':show.get('license','')[:800]}
def image_case(model,case,count=False):
 before=memory();peak=[before['current_bytes']];stop=threading.Event()
 def sample():
  while not stop.wait(.1):peak[0]=max(peak[0],memory()['current_bytes'])
 thread=threading.Thread(target=sample,daemon=True);thread.start();started=time.monotonic()
 r={'id':case['id'],'model':model,'status':'failed'}
 try:
  raw=(images/case['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
  normalized=normalize_image(base64.b64encode(raw).decode())[0]
  if count:
   runner.switch(model)
   data=post('/api/generate',{'model':model,'prompt':'Count the visible '+case['primary_object']+' objects in the image. Return count as an integer, or null if genuinely too occluded/unclear. Do not count pictures or text naming an object.','images':[base64.b64encode(normalized).decode()],'format':{'type':'object','properties':{'count':{'type':['integer','null']}},'required':['count'],'additionalProperties':False},'stream':False,'keep_alive':'1m','think':False,'options':{'num_ctx':2048,'num_batch':32,'num_predict':64,'temperature':0}},timeout=120)
   value=json.loads(data.get('response','{}'));valid=set(value)=={'count'} and (type(value['count']) is int or value['count'] is None) and data.get('done_reason')!='length'
   r.update(status='completed',json_valid=valid,count=value.get('count'),done_reason=data.get('done_reason'),load_seconds=data.get('load_duration',0)/1e9)
  else:
   result,switch=runner('image_recognition',normalized,model);r.update(status='completed',result=result,model_switch=switch)
 except Exception as e:
  r.update(error_type=type(e).__name__,error=str(e)[:800])
  if type(e).__name__=='UpstreamUncertain' or isinstance(e,(TimeoutError,OSError)):
   # Do not admit another job while the native operation may still run.
   unload()
 finally:
  stop.set();thread.join(2)
 r.update(seconds=round(time.monotonic()-started,4),inference_wall_seconds=round(time.monotonic()-started,4),peak_cgroup_bytes=peak[0],oom_kill_delta=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0))
 return r
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
report['cleanup_timer_was_active']=timer
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 controls=[{'model':'granite4:1b-h','task':'text','control':True}]
 for candidate in controls+plan['candidates']:
  model=candidate['model'];entry={**candidate,'status':'preparing','started_utc':now()};report['controls' if candidate.get('control') else 'models'].append(entry);save();print('START',model,flush=True)
  try:
   tag,meta=guarded(lambda:prepare(model));entry.update(tag=tag,**meta);save()
   if candidate['task']=='text':guarded(lambda:ns['test'](entry))
   else:
    entry.update(tests=[],robustness=[],counts=[],status='running')
    # Fresh eight-image control detects a broken runtime/profile; historical full
    # winner scores remain historical, not falsely called a fresh full rerun.
    control={'model':'minicpm-v4.6:1b','task':'vision','status':'running','tests':[],'scope':'Eight-image fresh sentinel, not full cohort'};report['controls'].append(control)
    for case in manifest['recognition'][:6]+manifest['recognition'][-2:]:
     control['tests'].append(guarded(lambda c=case:image_case(control['model'],c)));save()
    control['status']='completed'
    for field,cases in [('tests',manifest['recognition']),('robustness',manifest['robustness']),('counts',[c for c in manifest['recognition'] if c.get('count_probe')])]:
     for case in cases:
      r=guarded(lambda c=case:image_case(model,c,field=='counts'));entry[field].append(r);save();print('CASE',model,field,case['id'],r['status'],r['seconds'],flush=True)
      if r['oom_kill_delta']:raise RuntimeError('OOM observed: stop candidate')
      if len(entry[field])>=3 and all(x['status']=='failed' for x in entry[field][-3:]):raise RuntimeError('Three consecutive failed image cases: stop candidate')
    entry['status']='completed'
  except Exception as e:entry.update(status='failed',error_type=type(e).__name__,error=str(e)[:800])
  finally:
   entry['finished_utc']=now();save()
   guarded(unload)
   if model.lower() not in initial:
    guarded(lambda:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],check=True,capture_output=True,timeout=60));entry['temporary_weights_removed']=True
   entry['disk_free_gib']=round(shutil.disk_usage('/').free/1024**3,3);save();print('DONE',model,entry['status'],flush=True)
finally:
 try:
  def restore():
   unload();return infer(payload('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
  report['restore']=guarded(restore)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();print('FINISHED',flush=True)
