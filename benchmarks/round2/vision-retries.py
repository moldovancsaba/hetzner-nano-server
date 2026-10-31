"""Round 2 image follow-up, run after the main run: retries granite3.2-vision:2b, qwen3-vl:2b and ministral-3:3b with larger context or 320-pixel images, and tests SmolVLM2 2.2B.
Uses num_batch 32 and the cases from run.py, and records out-of-memory kill counts from the container cgroup.
Writes vision-retries.json and reloads qwen3:1.7b at the end."""
import pathlib,json,base64,subprocess,datetime
ROOT=pathlib.Path(__file__).parent
scope={'__file__':str(ROOT/'run.py')}
exec((ROOT/'run.py').read_text().split("previous='qwen3:1.7b'")[0],scope)
call,trim,unload=scope['call'],scope['trim'],scope['unload']
cases=scope['viscases']
results={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'memory_cap_mib':2800,'models':[]}
def save():(ROOT/'vision-retries.json').write_text(json.dumps(results,indent=2))
def events():
 pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip()
 g=pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1]
 return dict((l.split()[0],int(l.split()[1])) for l in pathlib.Path('/sys/fs/cgroup'+g+'/memory.events').read_text().splitlines())
previous='qwen3:1.7b'
try:
 for model,ctx,size in [('granite3.2-vision:2b',4096,640),('granite3.2-vision:2b',2048,320),('qwen3-vl:2b',2048,320),('ministral-3:3b',2048,320),('hf.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF:Q4_K_M',2048,640),('hf.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF:Q4_K_M',2048,320)]:
  if any(m['model']==model and m.get('status')=='ran' for m in results['models']):continue
  print('RETRY START',model,'context',ctx,'image',size,flush=True);unload(previous);previous=model;before=events()
  entry={'model':model,'context':ctx,'prefill_batch':32,'max_image_dimension':size,'tests':[]};results['models'].append(entry)
  images={n:base64.b64encode((ROOT/(n if size==640 else n.replace('.png','-320.png'))).read_bytes()).decode() for n in ['cats.png','poster.png']}
  payload={'model':model,'prompt':'Identify the animals. Return JSON with animal and count.','images':[images['cats.png']],'think':False,'format':'json','stream':False,'keep_alive':'30m','options':{'num_ctx':ctx,'num_batch':32,'num_predict':64,'temperature':0}}
  r=call('/api/generate',payload,150);entry['first_image']={**trim(r),'response':r.get('data',{}).get('response','')};save()
  if not r['ok']:
   entry['status']='failed';entry['oom_kill_delta']=events().get('oom_kill',0)-before.get('oom_kill',0);save();print('RETRY FAILED',model,entry['first_image'].get('error'),flush=True);continue
  entry['status']='ran'
  for name,image,prompt,validate,jsonformat in cases:
   for trial in range(2):
    payload={'model':model,'prompt':prompt,'images':[images[image]],'think':False,'stream':False,'options':{'num_ctx':ctx,'num_batch':32,'num_predict':96,'temperature':0}}
    if jsonformat:payload['format']='json'
    r=call('/api/generate',payload,100);text=r.get('data',{}).get('response','');valid=None
    if jsonformat:
     try:json.loads(text);valid=True
     except Exception:valid=False
    entry['tests'].append({'name':name,'trial':trial+1,**trim(r),'response':text,'json_valid':valid,'passed':r['ok'] and validate(text)});save()
    if not r['ok']:entry['status']='failed_during_suite';break
   if entry['status']=='failed_during_suite':break
  entry['summary']={'passed':sum(t['passed'] for t in entry['tests']),'total':len(entry['tests'])};entry['oom_kill_delta']=events().get('oom_kill',0)-before.get('oom_kill',0);save();print('RETRY DONE',model,entry['summary'],flush=True)
finally:
 unload(previous);r=call('/api/generate',{'model':'qwen3:1.7b','prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':{'num_ctx':2048,'num_predict':12}},120);results['restored_original']=trim(r);results['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print('RETRY RESTORED ORIGINAL',flush=True)
