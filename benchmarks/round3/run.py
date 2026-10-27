import pathlib,json,subprocess,time,datetime,base64,shutil,urllib.request,statistics
from fixtures import call,trim,unload,cases
ROOT=pathlib.Path(__file__).parent
plan=json.loads((ROOT/'plan.json').read_text())
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':plan['scope'],'settings':plan['settings'],'text':[],'vision':[],'notes':['Two controlled images and a small synthetic English case set, not general production accuracy.','English and image analytics ranked independently; no non-English data.','num_batch=32 used for all new requests; some earlier text runs used the runtime default.','Disk-first policy: record metadata then remove only packages newly downloaded here.','Original model restored after the run; no production routing/config change.']}
def save():
 p=ROOT/'results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'results.json')
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:11434'+path,timeout=15) as r:return json.load(r)
def events():
 pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip();group=pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1];p=pathlib.Path('/sys/fs/cgroup'+group)
 return {'memory_limit':int((p/'memory.max').read_text()),'events':dict((l.split()[0],int(l.split()[1])) for l in (p/'memory.events').read_text().splitlines())}
def request(path,payload,timeout=100):
 r=call(path,payload,timeout)
 if not r['ok'] and 'does not support thinking' in r.get('error','').lower() and 'think' in payload:
  payload=dict(payload);payload.pop('think');retry=call(path,payload,timeout);retry['thinking_option_retry']=True;return retry
 return r
def options(tokens):return {'num_ctx':2048,'num_batch':32,'num_predict':tokens,'temperature':0}
def validated(text,fn):
 try:return bool(fn(json.loads(text)))
 except Exception:return False
def dictcheck(d):return isinstance(d,dict)
validators={
 'photo_animals':lambda t:validated(t,lambda d:dictcheck(d) and d.get('animal')=='cat' and type(d.get('count')) is int and d['count']==2),
 'photo_count_plain':lambda t:t.strip().strip('.') in ['2','two','Two'],
 'photo_remotes':lambda t:validated(t,lambda d:dictcheck(d) and type(d.get('remote_count')) is int and d['remote_count']==2),
 'poster_ocr':lambda t:validated(t,lambda d:dictcheck(d) and d.get('venue')=='PANDORA' and type(d.get('room')) is int and d['room']==12 and d.get('opening_time')=='09:00'),
 'poster_shapes':lambda t:validated(t,lambda d:d=={'red_shape':'circle','blue_shape':'square','green_shape':'triangle'}),
 'poster_missing_address':lambda t:validated(t,lambda d:dictcheck(d) and 'street_address' in d and d['street_address'] is None)}
schemas={
 'photo_animals':{'animal':{'type':'string'},'count':{'type':'integer'}},'photo_remotes':{'remote_count':{'type':'integer'}},'poster_ocr':{'venue':{'type':'string'},'room':{'type':'integer'},'opening_time':{'type':'string'}},'poster_shapes':{'red_shape':{'type':'string'},'blue_shape':{'type':'string'},'green_shape':{'type':'string'}},'poster_missing_address':{'street_address':{'type':['string','null']}}}
imagecases=json.loads((ROOT/'image-cases.json').read_text())
extra=[('chat_followup',[{'role':'user','content':'My project is called ClassScout. We help families find activities.'},{'role':'assistant','content':'Understood.'},{'role':'user','content':'What is my project called? Return JSON with project.'}],lambda d:d=={'project':'ClassScout'}),('chat_unknown_secret',[{'role':'user','content':'What is my MongoDB Atlas password? You have not been given it. Return JSON with known (boolean) and password (string or null). Do not invent a password.'}],lambda d:d=={'known':False,'password':None})]
textcases=[(n,[{'role':'user','content':p}],f) for n,p,f in cases]+extra
initial=get('/api/tags');original={m['name'].lower() for m in initial['models']};report['initial_inventory']=initial;report['runtime_version']=get('/api/version');report['initial_memory']=events();save()
if report['initial_memory']['memory_limit']!=2800*1024*1024:raise RuntimeError('Memory cap differs; no automatic change authorized by this benchmark profile')
previous='qwen3:1.7b';current_new=False;current=None
try:
 for workload in ['vision','text']:
  for model in plan[workload]:
   print('START',workload,model,flush=True);entry={'model':model,'tests':[],'status':'preparing'};report[workload].append(entry);save();current=model;current_new=model.lower() not in original;before=events()
   try:
    unload(previous);previous=model
    if shutil.disk_usage('/').free<4*1024**3+2600*1024**2:
     entry['status']='disk_reserve_skip';save();continue
    log=ROOT/('pull-'+model.replace('/','_').replace(':','_')+'.log');start=time.monotonic()
    with log.open('w') as f:pull=subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],stdout=f,stderr=subprocess.STDOUT,timeout=300)
    entry['pull_seconds']=round(time.monotonic()-start,3);entry['pull_exit_code']=pull.returncode
    if pull.returncode:
     entry['status']='pull_failed';entry['error']=log.read_text(errors='replace')[-800:];save();continue
    show=request('/api/show',{'model':model});entry['capabilities']=show.get('data',{}).get('capabilities',[]);entry['details']=show.get('data',{}).get('details');entry['tag']=next((x for x in get('/api/tags')['models'] if x['name'].lower()==model.lower()),None);save()
    if workload=='text':
     first=request('/api/generate',{'model':model,'prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':options(12)},100);entry['load']={**trim(first),'response':first.get('data',{}).get('response','')}
     if not first['ok']:entry['status']='load_failed';save();continue
     entry['status']='ran'
     for name,messages,validate in textcases:
      for trial in range(2):
       result=request('/api/chat',{'model':model,'messages':messages,'think':False,'format':'json','stream':False,'options':options(180)},100);text=result.get('data',{}).get('message',{}).get('content','');valid=False;passed=False
       try:d=json.loads(text);valid=True;passed=bool(validate(d))
       except Exception:pass
       entry['tests'].append({'name':name,'trial':trial+1,**trim(result),'response':text,'json_valid':valid,'passed':result['ok'] and passed});save()
       if not result['ok']:entry['status']='failed_during_suite';break
      if entry['status']=='failed_during_suite':break
     tools=[{'type':'function','function':{'name':'search_listings','description':'Search public listings','parameters':{'type':'object','properties':{'borough':{'type':'string'},'activity':{'type':'string'}},'required':['borough','activity']}}}]
     t=request('/api/chat',{'model':model,'messages':[{'role':'user','content':'Use search_listings to find Swimming in Brooklyn.'}],'tools':tools,'think':False,'stream':False,'options':options(100)},100);tc=t.get('data',{}).get('message',{}).get('tool_calls',[])
     entry['tool_call']={**trim(t),'calls':tc,'passed':any(c.get('function',{}).get('name')=='search_listings' and c['function'].get('arguments',{}).get('borough')=='Brooklyn' and c['function'].get('arguments',{}).get('activity')=='Swimming' for c in tc)}
     t=request('/api/chat',{'model':model,'messages':[{'role':'user','content':'How can I build a habit of walking daily? Answer in two short sentences.'}],'think':False,'stream':False,'options':options(140)},100)
     entry['english_chat_sample']={**trim(t),'response':t.get('data',{}).get('message',{}).get('content','')};save()
    else:
     entry['image_attempts']=[];selected=None
     for size in [640,320]:
      image=base64.b64encode((ROOT/('cats.png' if size==640 else 'cats-320.png')).read_bytes()).decode()
      first=request('/api/generate',{'model':model,'prompt':'Identify the animals. Return JSON with animal and count.','images':[image],'think':False,'format':'json','stream':False,'keep_alive':'30m','options':options(64)},120)
      entry['image_attempts'].append({'max_image_dimension':size,**trim(first),'response':first.get('data',{}).get('response','')});save()
      if first['ok']:selected=size;break
      error=first.get('error','').lower()
      if not any(s in error for s in ['memory','context','token','killed','eof','timeout']):break
      unload(model)
     if selected is None:entry['status']='image_inference_failed';save();continue
     entry['status']='ran';entry['max_image_dimension']=selected;images={n:base64.b64encode((ROOT/(n if selected==640 else n.replace('.png','-320.png'))).read_bytes()).decode() for n in ['cats.png','poster.png']}
     for case in imagecases:
      for trial in range(2):
       payload={'model':model,'prompt':case['prompt'],'images':[images[case['image']]],'think':False,'stream':False,'options':options(96)}
       if case['json_format']:payload['format']='json'
       result=request('/api/generate',payload,100);text=result.get('data',{}).get('response','');valid=None
       if case['json_format']:
        try:json.loads(text);valid=True
        except Exception:valid=False
       entry['tests'].append({'name':case['name'],'trial':trial+1,**trim(result),'response':text,'json_valid':valid,'passed':result['ok'] and validators[case['name']](text)});save()
       if not result['ok']:entry['status']='failed_during_suite';break
      if entry['status']=='failed_during_suite':break
     entry['schema_tests']=[]
     if entry['status']=='ran':
      for case in imagecases:
       name=case['name']
       if name not in schemas:continue
       props=schemas[name];schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
       result=request('/api/generate',{'model':model,'prompt':case['prompt'],'images':[images[case['image']]],'think':False,'format':schema,'stream':False,'options':options(96)},100);text=result.get('data',{}).get('response','');valid=False;keys=False
       try:d=json.loads(text);valid=True;keys=isinstance(d,dict) and set(d)==set(props)
       except Exception:pass
       entry['schema_tests'].append({'name':name,**trim(result),'response':text,'json_valid':valid,'keys_match':keys,'passed':result['ok'] and keys and validators[name](text)});save()
       if not result['ok']:break
    ts=entry['tests'];entry['summary']={'passed':sum(x['passed'] for x in ts),'total':len(ts),'json_valid':sum(x.get('json_valid') is True for x in ts),'median_seconds':statistics.median(x['seconds'] for x in ts if x['ok']) if any(x['ok'] for x in ts) else None}
    if 'schema_tests' in entry:entry['schema_summary']={'passed':sum(x['passed'] for x in entry['schema_tests']),'total':len(entry['schema_tests'])}
   except Exception as e:entry['status']='runner_exception';entry['error_type']=type(e).__name__
   finally:
    unload(model);entry['oom_kill_delta']=events()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)
    if current_new:
     clean=subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],capture_output=True,text=True,timeout=45);entry['new_package_removed']=clean.returncode==0
    entry['disk_free_gib']=round(shutil.disk_usage('/').free/1024**3,2);save();print('DONE',workload,model,entry['status'],entry.get('summary'),entry.get('schema_summary'),flush=True);current=None;current_new=False
finally:
 if current is not None:
  unload(current)
  if current_new:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',current],capture_output=True,timeout=45)
 restore=request('/api/generate',{'model':'qwen3:1.7b','prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':options(12)},120);report['restored_original']=trim(restore);report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['final_memory']=events();report['final_inventory']=get('/api/tags');save();print('RESTORED ORIGINAL; ROUND COMPLETE',flush=True)
