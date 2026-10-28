"""Full paired service-contract evaluation, normal FIFO jobs plus guarded count probes."""
import base64,datetime,hashlib,json,pathlib,random,shutil,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/'recognition-manifest.json').read_text());IMAGES=ROOT/'inputs'
MODELS=['hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0','hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0','minicpm-v4.6:1b','hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0','qwen3.5:0.8b']
KEY=json.loads(pathlib.Path('/opt/narimato-ai/api-keys.json').read_text())['camera']
MAINT=next(line.split('=',1)[1].strip().strip('"').strip("'") for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if line.startswith('GATEWAY_MAINTENANCE_KEY='))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def request(port,path,data=None,key=None,method=None,timeout=25):
    headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
def api(path,data=None,method=None):return request(8090,'/v1'+path,data,KEY,method)
def lease(action,value=None):return request(8090,'/internal/model-storage',{'action':action,'lease':value},MAINT)
def native(path,data=None,timeout=120):return request(11434,path,data,timeout=timeout)
CG=None
def memory():
    global CG
    if CG is None or not CG.exists():
        pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip();CG=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1].lstrip('/')
    return {'current':int((CG/'memory.current').read_text()),'events':{k:int(v) for k,v in (x.split() for x in (CG/'memory.events').read_text().splitlines())}}
report={'version':'full-vision-evaluation.v1','started_utc':now(),'manifest_sha256':hashlib.sha256((ROOT/'recognition-manifest.json').read_bytes()).hexdigest(),'runtime':native('/api/version'),'models':[],'settings':{'num_ctx':2048,'num_batch':32,'temperature':0,'output_limit':256,'memory_mib':2800,'primary':'Actual gateway Camera recognition contract; one outstanding test job; ordinary FIFO scheduling.'}}
def save():
    p=ROOT/'recognition-results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'recognition-results.json')
def collect_job(model,case):
    encoded=base64.b64encode((IMAGES/case['file']).read_bytes()).decode();before=memory();peak=before['current'];start=time.monotonic()
    for _ in range(120):
        try:job=api('/jobs',{'task':'image_recognition','model':model,'input':{'image_base64':encoded}});break
        except urllib.error.HTTPError as e:
            if e.code not in [429,503]:raise
            if api('/queue').get('status')!='ok':raise RuntimeError('Gateway degraded; do not continue native work')
            time.sleep(2)
    else:raise RuntimeError('No admission after bounded waiting')
    row=None
    for _ in range(720):
        row=api('/jobs/'+job['id'])
        if row['status']=='running':peak=max(peak,memory()['current'])
        if row['status'] in ['completed','failed']:break
        time.sleep(.5)
    if row['status'] not in ['completed','failed']:raise RuntimeError('Job state unresolved; leave guard recovery to operator')
    if model=='qwen3.5:0.8b':assert row['model_profile'].get('think') is False,'Wrong Qwen operating profile'
    result={'id':case['id'],'status':row['status'],'result':row.get('result'),'error':row.get('error'),'seconds':round(time.monotonic()-start,4),'queue_wait_seconds':row.get('queue_wait_seconds'),'inference_wall_seconds':round(row.get('finished_at',time.time())-row.get('started_at',time.time()),4),'model_switch':row.get('model_switch'),'model':row['model'],'digest':row.get('model_digest'),'model_profile':row.get('model_profile'),'peak_cgroup_bytes':peak,'oom_kill_delta':memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)}
    api('/jobs/'+job['id'],method='DELETE')
    if row.get('error')=='upstream_state_unknown':raise RuntimeError('Gateway circuit opened; operator must recover uncertain native state')
    return result
def count_probe(model,case):
    held=None;before=memory();peak=[before['current']];stop=threading.Event();renew_error=[];started=time.monotonic()
    try:
        for _ in range(180):
            try:held=lease('acquire')['lease'];break
            except urllib.error.HTTPError as e:
                if e.code!=409:raise
                time.sleep(2)
        if not held:raise RuntimeError('No idle maintenance lease for count probe')
        def monitor():
            last=time.monotonic()
            while not stop.wait(.2):
                peak[0]=max(peak[0],memory()['current'])
                if time.monotonic()-last>30:
                    try:lease('renew',held);last=time.monotonic()
                    except Exception as e:renew_error.append(type(e).__name__);return
        threading.Thread(target=monitor,daemon=True).start()
        # Exact gateway normalization is reproduced; labels/count never appear in model input.
        import sys;sys.path.insert(0,'/opt/narimato-gateway')
        from moderation.server import normalize_image
        image=normalize_image(base64.b64encode((IMAGES/case['file']).read_bytes()).decode())[0]
        payload={'model':model,'prompt':'Count the visible '+case['primary_object']+' objects in the image. Return count as an integer, or null if genuinely too occluded/unclear. Do not count pictures or text naming an object.','images':[base64.b64encode(image).decode()],'format':{'type':'object','properties':{'count':{'type':['integer','null']}},'required':['count'],'additionalProperties':False},'stream':False,'keep_alive':'1m','options':{'num_ctx':2048,'num_batch':32,'num_predict':64,'temperature':0}}
        if model=='qwen3.5:0.8b':payload['think']=False
        t=time.monotonic();data=native('/api/generate',payload,timeout=120)
        assert not renew_error,'Lease renewal failed'
        text=data.get('response','')
        try:value=json.loads(text)
        except (ValueError,TypeError):value={}
        valid=isinstance(value,dict) and set(value)=={'count'} and (type(value['count']) is int or value['count'] is None) and data.get('done_reason')!='length'
        return {'id':case['id'],'status':'completed','json_valid':valid,'response':text,'count':value.get('count'),'seconds':round(time.monotonic()-t,4),'load_seconds':data.get('load_duration',0)/1e9,'done_reason':data.get('done_reason'),'thinking_characters':len(data.get('thinking','')),'peak_cgroup_bytes':peak[0],'oom_kill_delta':memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)}
    except (TimeoutError,urllib.error.URLError):
        # Exclusive lease and drained gateway: stop uncertain native work before releasing.
        if held:subprocess.run(['docker','restart','narimato-ollama'],check=True,capture_output=True,timeout=45)
        raise
    finally:
        stop.set()
        if held:lease('release',held)

original=native('/api/tags');report['initial_inventory']=original;initial={m['name'].lower():m for m in original['models']}
resume=ROOT/'recognition-resume.json'
if resume.exists():
    report=json.loads(resume.read_text());report.setdefault('resume_events',[]).append(now());report.pop('finished_utc',None);report['status']='running'
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0 or report.get('cleanup_timer_was_active',False)
report['cleanup_timer_was_active']=timer
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True);save()
try:
    for model in MODELS:
        entry=next((x for x in report['models'] if x['model']==model),None)
        if entry and entry['status']=='completed':continue
        if entry is None:
            entry={'model':model,'status':'preparing','tests':[],'robustness':[],'counts':[]};report['models'].append(entry)
        save();print('START',model,flush=True)
        if model.lower() not in initial:
            assert shutil.disk_usage('/').free>6*1024**3,'Disk reserve preflight'
            subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=360)
        tag=next(m for m in native('/api/tags')['models'] if m['name'].lower()==model.lower());entry['tag']=tag
        entry['status']='running';entry['operating_profile']={'think':False} if model=='qwen3.5:0.8b' else {};before=memory();save()
        for field,cases in [('tests',MANIFEST['recognition']),('robustness',MANIFEST['robustness'])]:
            ordered=cases.copy();random.Random(20261028).shuffle(ordered)
            for case in ordered:
                if any(x['id']==case['id'] for x in entry[field]):continue
                r=collect_job(model,case);entry[field].append(r);save();print('CASE',model,field,case['id'],r['status'],round(r['inference_wall_seconds'],2),flush=True)
                if r['oom_kill_delta']:raise RuntimeError('OOM during actual service case; stop experiment')
                time.sleep(1)
        for case in [c for c in MANIFEST['recognition'] if c.get('count_probe')]:
            if any(x['id']==case['id'] for x in entry['counts']):continue
            r=count_probe(model,case);entry['counts'].append(r);save();print('COUNT',model,case['id'],flush=True);time.sleep(2)
        entry['status']='completed';entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0);save();print('DONE',model,flush=True)
    report['status']='completed'
except Exception as error:
    report.update(status='interrupted',error_type=type(error).__name__,error=str(error)[:500]);save();raise
finally:
    # No unsafe restart of a running public job. Normal queue admission handles restoration.
    try:
        keys=json.loads(pathlib.Path('/opt/narimato-ai/api-keys.json').read_text())
        job=request(8090,'/v1/jobs',{'task':'text_chat','model':'auto','input':{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}},keys['classscout'])
        for _ in range(360):
            row=request(8090,'/v1/jobs/'+job['id'],key=keys['classscout'])
            if row['status'] in ['completed','failed']:break
            time.sleep(.5)
        report['restore']={'status':row['status'],'model':row['model']};request(8090,'/v1/jobs/'+job['id'],key=keys['classscout'],method='DELETE')
    except Exception as error:report['restore_error_type']=type(error).__name__
    if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
    report['finished_utc']=now();report['final_inventory']=native('/api/tags');save();print('FINISHED',report.get('status'),report.get('restore'),flush=True)
