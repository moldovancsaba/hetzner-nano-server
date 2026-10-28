"""ARM64 CPU evaluation, sequential models with a gateway idle lease per image."""
import datetime,hashlib,json,pathlib,resource,subprocess,threading,time,urllib.request,urllib.error
import numpy as np
import onnxruntime as ort
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parent;plan=json.loads((ROOT/'plan.json').read_text());manifest=json.loads((ROOT/'manifest.json').read_text())
key=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def req(url,payload=None,auth=None):
 headers={'Content-Type':'application/json'}
 if auth:headers['Authorization']='Bearer '+auth
 r=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
 with urllib.request.urlopen(r,timeout=40) as x:return json.load(x)
def lease(action,held=None):return req('http://127.0.0.1:8090/internal/model-storage',{'action':action,'lease':held},key)
def guarded(fn):
 held=None;deadline=time.monotonic()+600
 while held is None:
  try:held=lease('acquire')['lease']
  except urllib.error.HTTPError as e:
   if e.code!=409 or time.monotonic()>deadline:raise
   time.sleep(3)
 try:
  for m in req('http://127.0.0.1:11434/api/ps')['models']:req('http://127.0.0.1:11434/api/generate',{'model':m['name'],'keep_alive':0})
  return fn()
 finally:lease('release',held);time.sleep(1)
report={'version':'camera-specialists.v1','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),'models':[],'runtime':ort.__version__,'hardware':'Hetzner CAX11 ARM64, CPU only; separate evaluation cgroup capped 2800 MiB / 2 CPU; no concurrent inference'}
def save():(ROOT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for model in plan['models']:
  row={'model':model['model'],'revision':model['revision'],'status':'running','artifact_sha256':hashlib.sha256((ROOT/model['file']).read_bytes()).hexdigest(),'tests':[]};report['models'].append(row);save()
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
  t=time.monotonic();session=guarded(lambda:ort.InferenceSession(str(ROOT/model['file']),sess_options=options,providers=['CPUExecutionProvider']));row['load_seconds']=time.monotonic()-t
  cfg=json.loads((ROOT/model['processor']).read_text());size=cfg['size'];input_name=session.get_inputs()[0].name
  for case in manifest['cases']:
   raw=(ROOT/'inputs'/case['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
   def analyse():
    image=Image.open(ROOT/'inputs'/case['file']).convert('RGB').resize((size['width'],size['height']),resample=Image.Resampling(cfg.get('resample',2)))
    value=np.asarray(image,dtype=np.float32)*cfg.get('rescale_factor',1/255)
    value=(value-np.asarray(cfg['image_mean'],dtype=np.float32))/np.asarray(cfg['image_std'],dtype=np.float32)
    pixels=np.ascontiguousarray(value.transpose(2,0,1)[None]);t=time.monotonic();logits=session.run(None,{input_name:pixels})[0][0];seconds=time.monotonic()-t
    scores=np.exp(logits-logits.max());scores=scores/scores.sum()
    return {'id':case['id'],'valid':True,'nsfw_score':float(scores[1]),'detected':bool(scores[1]>=plan['threshold']),'seconds':round(seconds,5)}
   row['tests'].append(guarded(analyse));save()
  row['status']='completed';row['peak_process_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;del session;save();print('DONE',model['model'],flush=True)
finally:
 try:
  report['restore']=guarded(lambda:req('http://127.0.0.1:11434/api/generate',{'model':'granite4:1b-h','prompt':'Reply READY.','stream':False,'keep_alive':'1m','options':{'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}})).get('done',False)
 except Exception as error:report['restore_error']=type(error).__name__
 if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
 report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
