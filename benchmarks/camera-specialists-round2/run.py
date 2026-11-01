"""Bounded ARM64 CPU specialist benchmark; approved public fixtures only."""
import datetime, hashlib, json, pathlib, resource, subprocess, threading, time, urllib.request, urllib.error
import numpy as np
import onnxruntime as ort
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parent
plan=json.loads((ROOT/'plan.json').read_text());manifest=json.loads((ROOT/'manifest.json').read_text())
key=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def req(path,body=None,auth=False,timeout=120):
 base='http://127.0.0.1:8090' if auth else 'http://127.0.0.1:11434'
 headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
 if auth:headers['Authorization']='Bearer '+key
 with urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers),timeout=timeout) as r:return json.load(r)
def lease(action,held=None):return req('/internal/model-storage',{'action':action,'lease':held},True)
def unload():
 for model in req('/api/ps')['models']:req('/api/generate',{'model':model['name'],'keep_alive':0})
 deadline=time.monotonic()+45
 while req('/api/ps')['models']:
  if time.monotonic()>deadline:raise RuntimeError('Native worker did not unload')
  time.sleep(.3)
def preprocess(image):
 # timm crop_pct=1.0: resize shorter edge, then center-crop (not aspect-distorting resize).
 image=image.convert('RGB');w,h=image.size;edge=384
 size=(edge,int(edge*h/w)) if w<h else (int(edge*w/h),edge)
 image=image.resize(size,Image.Resampling.BICUBIC)
 left=int(round((size[0]-edge)/2));top=int(round((size[1]-edge)/2))
 image=image.crop((left,top,left+edge,top+edge))
 x=(np.asarray(image,dtype=np.float32)/255-.5)/.5
 return np.ascontiguousarray(x.transpose(2,0,1)[None])
held=None;deadline=time.monotonic()+10800
while held is None:
 try:held=lease('acquire')['lease']
 except urllib.error.HTTPError as e:
  if e.code!=409 or time.monotonic()>deadline:raise
  time.sleep(5)
stop=threading.Event();renew_errors=[]
def renew():
 while not stop.wait(25):
  try:lease('renew',held)
  except Exception as e:renew_errors.append(type(e).__name__);return
thread=threading.Thread(target=renew,daemon=True);thread.start()
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
report={'version':plan['version'],'started_utc':now(),'models':[],'threshold':plan['threshold'],'scope':plan['scope'],'runtime':{'onnxruntime':ort.__version__,'numpy':np.__version__,'hardware':'Hetzner CAX11 ARM64 CPU; 2800 MiB / 2 CPU isolated cgroup; native worker unloaded'},'manifest_sha256':hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()}
def save():
 p=ROOT/'results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'results.json')
row={'model':plan['model'],'revision':plan['revision'],'status':'running','tests':[]};report['models'].append(row);save()
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True);unload()
 artifact=ROOT/'marqo.onnx';audit=json.loads((ROOT/'export-audit.json').read_text())
 assert hashlib.sha256(artifact.read_bytes()).hexdigest()==audit['onnx_sha256']
 row['artifact_sha256']=audit['onnx_sha256'];options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
 started=time.monotonic();session=ort.InferenceSession(str(artifact),sess_options=options,providers=['CPUExecutionProvider']);row['load_seconds']=time.monotonic()-started
 for case in manifest['cases']:
  if renew_errors:raise RuntimeError('Maintenance lease renewal failed')
  path=ROOT/'inputs'/case['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==case['sha256']
  pixels=preprocess(Image.open(path));started=time.monotonic()
  logits=session.run(None,{'pixel_values':pixels})[0][0];seconds=time.monotonic()-started
  assert logits.shape==(2,) and np.isfinite(logits).all()
  scores=np.exp(logits-logits.max());scores/=scores.sum();score=float(scores[plan['nsfw_index']])
  row['tests'].append({'id':case['id'],'valid':True,'nsfw_score':score,'detected':score>=plan['threshold'],'seconds':round(seconds,6)});save()
 row['status']='completed';row['peak_process_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;del session
except Exception as e:row.update(status='failed',error_type=type(e).__name__,error=str(e)[:500])
finally:
 try:
  unload();report['restore']=req('/api/generate',{'model':'granite4:1b-h','prompt':'Reply READY.','stream':False,'keep_alive':'1m','options':{'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}}).get('done',False)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();stop.set();thread.join(2);lease('release',held)
print('FINISHED',row['status'],len(row['tests']),flush=True)
