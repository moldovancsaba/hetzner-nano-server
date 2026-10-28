"""Five-model policy-matched moderation evaluation, one guarded image at a time."""
import base64,datetime,hashlib,json,pathlib,random,shutil,subprocess,sys,threading,time,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent;MANIFEST=json.loads((ROOT/'moderation-manifest.json').read_text());INPUTS=ROOT/'moderation-inputs'
MODELS=['hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0','hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0','minicpm-v4.6:1b','hf.co/LiquidAI/LFM2.5-VL-450M-Extract-GGUF:Q8_0','qwen3.5:0.8b']
sys.path.insert(0,'/opt/narimato-gateway')
from moderation.server import normalize_image
from moderation.policy import PROMPT,SCHEMA
assert PROMPT==MANIFEST['prompt'] and SCHEMA==MANIFEST['schema'],'Policy changed after labels froze'
KEY=next(line.split('=',1)[1].strip().strip('"').strip("'") for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if line.startswith('GATEWAY_MAINTENANCE_KEY='))
def request(port,path,data=None,key=None,timeout=20,method=None):
    headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def native(path,data=None,timeout=120):return request(11434,path,data,timeout=timeout)
def lease(action,value=None):return request(8090,'/internal/model-storage',{'action':action,'lease':value},KEY)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
CG=None
def memory():
    global CG
    if CG is None or not CG.exists():
        pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip();CG=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1].lstrip('/')
    return {'current':int((CG/'memory.current').read_text()),'events':{k:int(v) for k,v in (x.split() for x in (CG/'memory.events').read_text().splitlines())}}
report={'version':'full-moderation-evaluation.v1','status':'waiting_for_recognition','started_utc':now(),'manifest_sha256':hashlib.sha256((ROOT/'moderation-manifest.json').read_bytes()).hexdigest(),'models':[],'settings':{'num_ctx':2048,'num_batch':32,'num_predict':256,'temperature':0,'memory_mib':2800,'max_image_edge':640,'yield_to_production_seconds':5,'same_prompt_schema_as_live_service':True}}
def save():
    p=ROOT/'moderation-results.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'moderation-results.json')
save();print('WAITING for recognition run to finish; no simultaneous native generation.',flush=True)
deadline=time.monotonic()+14400
while subprocess.run(['systemctl','is-active','--quiet','narimato-vision-recognition.service']).returncode==0:
    if time.monotonic()>deadline:raise RuntimeError('Recognition did not finish before bounded waiting deadline')
    time.sleep(5)
recognition=json.loads((ROOT/'recognition-results.json').read_text());assert recognition['status']=='completed','Recognition experiment interrupted; require operator review'
assert recognition.get('restore',{}).get('status')=='completed','Recognition restoration did not pass'

def run_case(model,case):
    held=None;stop=threading.Event();fatal=[];peak=[0];before=memory();started=time.monotonic();row={'id':case['id'],'valid':False}
    try:
        for _ in range(180):
            try:held=lease('acquire')['lease'];break
            except urllib.error.HTTPError as e:
                if e.code!=409:raise
                time.sleep(2)
        if not held:raise RuntimeError('Could not acquire an idle gateway lease; production takes priority')
        def monitor():
            last=time.monotonic()
            while not stop.wait(.1):
                peak[0]=max(peak[0],memory()['current'])
                if time.monotonic()-last>30:
                    try:lease('renew',held);last=time.monotonic()
                    except Exception as e:fatal.append(type(e).__name__);return
        threading.Thread(target=monitor,daemon=True).start()
        for loaded in native('/api/ps')['models']:
            if loaded['name'].lower()!=model.lower():native('/api/generate',{'model':loaded['name'],'keep_alive':0},timeout=40)
        encoded=base64.b64encode((INPUTS/case['file']).read_bytes()).decode();image=normalize_image(encoded)[0]
        payload={'model':model,'prompt':MANIFEST['prompt'],'images':[base64.b64encode(image).decode()],'format':MANIFEST['schema'],'stream':False,'keep_alive':'1m','options':{'num_ctx':2048,'num_batch':32,'num_predict':256,'temperature':0}}
        if model=='qwen3.5:0.8b':payload['think']=False
        t=time.monotonic();data=native('/api/generate',payload,timeout=120);row.update(think=payload.get('think'),thinking_characters=len(data.get('thinking','')),seconds=round(time.monotonic()-t,4),load_seconds=round(data.get('load_duration',0)/1e9,4),prompt_tokens=data.get('prompt_eval_count'),output_tokens=data.get('eval_count'),done_reason=data.get('done_reason'),response=data.get('response',''))
        try:
            parsed=json.loads(row['response']);valid=isinstance(parsed,dict) and set(parsed)=={'categories','evidence'} and isinstance(parsed['categories'],dict) and set(parsed['categories'])==set(MANIFEST['categories']) and all(v is None or type(v) is bool for v in parsed['categories'].values()) and isinstance(parsed['evidence'],str) and len(parsed['evidence'])<=2000 and data.get('done') is True and data.get('done_reason')!='length'
            row.update(parsed=parsed,valid=valid)
        except (ValueError,TypeError):row['parse_error']=True
        if fatal:raise RuntimeError('Maintenance renewal failed')
    except urllib.error.HTTPError as error:
        row.update(error_type='HTTPError',error=error.read().decode()[:800],seconds=round(time.monotonic()-started,4))
    except (TimeoutError,urllib.error.URLError):
        # Own idle lease excludes public inference; resolve uncertain native work before release.
        if held:subprocess.run(['docker','restart','narimato-ollama'],check=True,capture_output=True,timeout=45)
        raise
    finally:
        stop.set();row.update(peak_cgroup_bytes=peak[0],oom_kill_delta=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0),lease_wait_and_total_seconds=round(time.monotonic()-started,4))
        if held:lease('release',held)
    return row

def prepare_model(model):
    # A resumed persistent cleanup timer may have a catch-up run. Acquire the
    # same guard before inventory/pull so a cleaner cannot remove a just-pulled artifact.
    held=None;stop=threading.Event();errors=[]
    try:
        for _ in range(180):
            try:held=lease('acquire')['lease'];break
            except urllib.error.HTTPError as e:
                if e.code!=409:raise
                time.sleep(2)
        assert held,'No idle guard for model preparation'
        def renew():
            while not stop.wait(30):
                try:lease('renew',held)
                except Exception as error:errors.append(type(error).__name__);return
        threading.Thread(target=renew,daemon=True).start()
        inventory=native('/api/tags')['models']
        if not any(m['name'].lower()==model.lower() for m in inventory):
            assert shutil.disk_usage('/').free>6*1024**3,'Disk reserve preflight'
            subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=360)
        assert not errors,'Model preparation lost its lease'
        return next(m for m in native('/api/tags')['models'] if m['name'].lower()==model.lower())
    finally:
        stop.set()
        if held:lease('release',held)

timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
report['status']='running';report['runtime']=native('/api/version');report['initial_memory']=memory();save()
try:
    for model in MODELS:
        entry={'model':model,'status':'running','tests':[],'robustness':[]};report['models'].append(entry);save();print('START',model,flush=True)
        entry['tag']=prepare_model(model);before=memory()
        assert entry['tag']['digest']==next(m['tag']['digest'] for m in recognition['models'] if m['model']==model),'Artifact changed between task evaluations'
        for field,cases in [('tests',MANIFEST['cases']),('robustness',MANIFEST['robustness'])]:
            ordered=cases.copy();random.Random(20261028).shuffle(ordered)
            for case in ordered:
                result=run_case(model,case);entry[field].append(result);save();print('CASE',model,case['id'],'valid',result['valid'],'seconds',result.get('seconds'),flush=True)
                if result['oom_kill_delta']:raise RuntimeError('OOM event; stop and review resource eligibility')
                time.sleep(5)
        entry['status']='completed';entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0);save();print('DONE',model,flush=True)
    report['status']='completed'
except Exception as error:
    report.update(status='interrupted',error_type=type(error).__name__,error=str(error)[:800]);save();raise
finally:
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
    report['finished_utc']=now();save();print('FINISHED',report.get('status'),report.get('restore'),flush=True)
