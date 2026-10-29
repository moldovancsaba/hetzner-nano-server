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
held=None;stop=threading.Event();samples=[];report={'context':8192,'model':'granite4:1b-h','num_batch':128,'cases':[],'started_at':time.time()};fatal=[]
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
 calibration='Read the background records then reply READY.\n'+filler*128+'\nReply READY.'
 prompts=[] if '--tools-only' in sys.argv else [('calibration',calibration,16)]
 for case,prompt,budget in prompts:
  start=time.monotonic()
  response=call(11434,'/api/generate',{'model':report['model'],'prompt':prompt,'think':False,'stream':False,'keep_alive':'5m','options':{'num_ctx':8192,'num_batch':128,'num_predict':budget,'temperature':0}},timeout=900)
  if case=='calibration':
   density=max(1,(response['prompt_eval_count']-50)/128)
   count=int((7000-250)/density)
   per=count//3
   long_prompt=('Find the three access codes in the records. Return a JSON object with exactly start, middle, end. Copy each code exactly.\nSTART access code: MAPLE-527.\n'+filler*per+'MIDDLE access code: CORAL-841.\n'+filler*per+'END access code: BIRCH-396.\n'+filler*(count-2*per)+'\nReturn only JSON with start, middle, end access codes.')
   prompts.append(('long_retrieval',long_prompt,128))
  row={'case':case,'seconds':round(time.monotonic()-start,3),'response':response};report['cases'].append(row)
  (ROOT/'progress.json').write_text(json.dumps(report,indent=2))
  print(json.dumps({'case':case,'seconds':row['seconds'],'response':response.get('response'),'prompt_eval_count':response.get('prompt_eval_count')}),flush=True)
 tool={'type':'function','function':{'name':'lookup_venue','description':'Look up the current verified record for a venue.','parameters':{'type':'object','properties':{'name':{'type':'string'}},'required':['name']}}}
 messages=[{'role':'user','content':'Use lookup_venue to check the opening time for Maple Tennis Club. Do not guess.'}]
 start=time.monotonic()
 choice=call(11434,'/api/chat',{'model':report['model'],'messages':messages,'tools':[tool],'think':False,'stream':False,'keep_alive':'5m','options':{'num_ctx':8192,'num_batch':128,'num_predict':128,'temperature':0}},timeout=180)
 report['cases'].append({'case':'native_tool_selection','seconds':round(time.monotonic()-start,3),'response':choice})
 calls=choice.get('message',{}).get('tool_calls',[])
 if calls:
  messages.append(choice['message'])
  messages.append({'role':'tool','tool_name':'lookup_venue','content':'{"name":"Maple Tennis Club","opening_time":"09:30","source":"synthetic-test-record"}'})
  start=time.monotonic()
  answer=call(11434,'/api/chat',{'model':report['model'],'messages':messages,'think':False,'stream':False,'keep_alive':'5m','options':{'num_ctx':8192,'num_batch':128,'num_predict':128,'temperature':0}},timeout=180)
  report['cases'].append({'case':'tool_result_answer','seconds':round(time.monotonic()-start,3),'response':answer})
 report['loaded']=json.loads(urllib.request.urlopen('http://127.0.0.1:11434/api/ps').read())
 report['after']=sample()
except Exception as e:
 report['error']=str(e)
 # A disconnected caller does not prove Ollama cancelled; restart only while exclusive.
 if held:subprocess.run(['docker','restart','narimato-ollama'],capture_output=True)
finally:
 stop.set();report['samples']=samples;report['fatal']=fatal;report['finished_at']=time.time()
 (ROOT/'results.json').write_text(json.dumps(report,indent=2))
 if held:
  try:lease('release',held)
  except Exception:pass
 if was_timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
 print(json.dumps({'error':report.get('error'),'fatal':fatal,'samples':len(samples),'result':str(ROOT/'results.json')}),flush=True)
