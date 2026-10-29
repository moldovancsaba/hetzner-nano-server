"""Run on inference host. Exclusive, bounded synthetic 8K feasibility probe."""
import concurrent.futures, json, os, pathlib, subprocess, threading, time, urllib.request, urllib.error, sys
ROOT=pathlib.Path('/opt/narimato-ai/context-probe');ROOT.mkdir(exist_ok=True)
def call(port,path,data,timeout=30,key=None):
 headers={'Content-Type':'application/json'}
 if key:headers['Authorization']='Bearer '+key
 req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(data).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
key=dict(line.split('=',1) for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if '=' in line)['GATEWAY_MAINTENANCE_KEY'].strip().strip('"').strip("'")
def lease(action,value=None):return call(8090,'/internal/model-storage',{'action':action,'lease':value},key=key)
def run(cmd):return subprocess.check_output(cmd,text=True).strip()
was_timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
held=None;stop=threading.Event();samples=[];report={'context':'4K vs 8K, matched inputs; no cached prompt reuse','model':'granite4:1b-h','num_batch':128,'cases':[],'started_at':time.time()};fatal=[]
try:
 for attempt in range(90):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 if not held:raise RuntimeError('Could not drain queue safely')
 pid=run(['docker','inspect','--format','{{.State.Pid}}','narimato-ollama'])
 cg=pathlib.Path('/sys/fs/cgroup')/next(x.split('::',1)[1].lstrip('/') for x in pathlib.Path('/proc/'+pid+'/cgroup').read_text().splitlines() if '::' in x)
 def sample():
  stat=dict(line.split() for line in (cg/'memory.stat').read_text().splitlines())
  mem=dict((a,int(b)) for a,b in (line.replace(':','').split()[:2] for line in pathlib.Path('/proc/meminfo').read_text().splitlines()))
  return {'time':time.time(),'current':int((cg/'memory.current').read_text()),'anon':int(stat['anon']),'file':int(stat['file']),'available':mem['MemAvailable']*1024,'events':dict((a,int(b)) for a,b in (line.split() for line in (cg/'memory.events').read_text().splitlines()))}
 report['before']=sample()
 def monitor():
  last=0
  while not stop.wait(1):
   try:
    samples.append(sample())
    if time.monotonic()-last>45:lease('renew',held);last=time.monotonic()
    if samples[-1]['available']<250*1024**2 or samples[-1]['events'].get('oom_kill',0)>report['before']['events'].get('oom_kill',0):
     fatal.append('Memory safety threshold crossed');subprocess.run(['docker','restart','narimato-ollama'],capture_output=True);return
   except Exception as e:fatal.append(type(e).__name__);return
 threading.Thread(target=monitor,daemon=True).start()
 filler='Background record: public venue information was checked.\n'
 schema={'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}
 for name,count,windows in [('short',128,[4096,8192]),('medium',216,[8192,4096])]:
  prompt='The verified code is HAZEL614.\n'+filler*count+'\nReturn JSON with exactly one field code containing the verified code.'
  for context in windows:
   call(11434,'/api/generate',{'model':report['model'],'keep_alive':0},timeout=30)
   begin=len(samples);start=time.monotonic()
   response=call(11434,'/api/chat',{'model':report['model'],'messages':[{'role':'user','content':prompt}],'format':schema,'think':False,'stream':False,'keep_alive':'5m','options':{'num_ctx':context,'num_batch':128,'num_predict':64,'temperature':0}},timeout=180)
   duration=time.monotonic()-start
   assert json.loads(response['message']['content'])=={'code':'HAZEL614'},response
   row={'case':name,'context':context,'seconds':round(duration,3),'prompt_tokens':response['prompt_eval_count'],'output_tokens':response['eval_count'],'load_seconds':response['load_duration']/1e9,'prompt_seconds':response['prompt_eval_duration']/1e9,'generation_seconds':response['eval_duration']/1e9,'response':response['message']['content'],'peak_anonymous_mib':round(max((v['anon'] for v in samples[begin:]),default=0)/1024**2,1)}
   report['cases'].append(row)
   print(json.dumps(row),flush=True)
   (ROOT/'comparison-progress.json').write_text(json.dumps(report,indent=2))
 call(11434,'/api/generate',{'model':report['model'],'keep_alive':0},timeout=30)
 report['loaded']=json.loads(urllib.request.urlopen('http://127.0.0.1:11434/api/ps').read())
 report['after']=sample()
except Exception as e:
 report['error']=str(e)
 # A disconnected caller does not prove Ollama cancelled; restart only while exclusive.
 if held:subprocess.run(['docker','restart','narimato-ollama'],capture_output=True)
finally:
 stop.set();report['samples']=samples;report['fatal']=fatal;report['finished_at']=time.time()
 (ROOT/'compare-4k-8k.json').write_text(json.dumps(report,indent=2))
 if held:
  try:lease('release',held)
  except Exception:pass
 if was_timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
 print(json.dumps({'error':report.get('error'),'fatal':fatal,'samples':len(samples),'result':str(ROOT/'compare-4k-8k.json')}),flush=True)
