"""Bounded native benchmark, under the gateway maintenance lease. No live payloads."""
import base64,datetime,json,pathlib,shutil,statistics,subprocess,sys,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'round3'))
from fixtures import cases

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:11434'+path,timeout=20) as r:return json.load(r)
def post(path,data,timeout=120,base='http://127.0.0.1:11434',key=None):
    headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def cgroup():
    pid=subprocess.check_output(['docker','inspect','-f','{{.State.Pid}}','narimato-ollama'],text=True).strip()
    group=pathlib.Path('/proc/'+pid+'/cgroup').read_text().strip().split('::')[-1]
    return pathlib.Path('/sys/fs/cgroup'+group)
CG=cgroup()
def memory():
    return {'current_bytes':int((CG/'memory.current').read_text()),'events':{k:int(v) for k,v in (line.split() for line in (CG/'memory.events').read_text().splitlines())}}
def resident():return get('/api/ps')['models']
def unload():
    started=time.monotonic()
    for m in resident():post('/api/generate',{'model':m['name'],'keep_alive':0},45)
    end=time.monotonic()+45
    while resident():
        if time.monotonic()>end:raise RuntimeError('Resident did not unload; stop rather than overlap inference')
        time.sleep(.3)
    return round(time.monotonic()-started,3)

plan=json.loads((ROOT/'plan.json').read_text())
report={'started_utc':now(),'settings':plan['settings'],'scope':plan['scope'],'models':[],'controls':[]}
def save():
    tmp=ROOT/'results.tmp';tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(ROOT/'results.json')

def infer(payload,timeout=120):
    started=time.monotonic();stop=threading.Event();peak=[memory()['current_bytes']]
    def sample():
        while not stop.wait(.1):peak[0]=max(peak[0],memory()['current_bytes'])
    thread=threading.Thread(target=sample,daemon=True);thread.start()
    result={}
    try:
        try:data=post('/api/chat' if 'messages' in payload else '/api/generate',payload,timeout)
        except urllib.error.HTTPError as e:
            error=e.read().decode()[:1200]
            if 'does not support thinking' in error.lower() and 'think' in payload:
                payload=dict(payload);payload.pop('think');data=post('/api/chat' if 'messages' in payload else '/api/generate',payload,timeout)
            else:raise RuntimeError(error)
        content=data.get('message',{}).get('content',data.get('response',''))
        result={'ok':True,'response':content,'done_reason':data.get('done_reason'),'load_seconds':round(data.get('load_duration',0)/1e9,4),'prompt_tokens':data.get('prompt_eval_count'),'output_tokens':data.get('eval_count'),'tool_calls':data.get('message',{}).get('tool_calls',[])}
    except Exception as e:
        result={'ok':False,'error_type':type(e).__name__,'error':str(e)[:1200]}
        # A timed out native request may still run. Unload synchronously and verify idle.
        if isinstance(e,(TimeoutError,OSError)):
            unload()
    finally:
        stop.set();thread.join(2)
    result.update(seconds=round(time.monotonic()-started,4),peak_cgroup_bytes=peak[0]);return result

OPTIONS={'num_ctx':2048,'num_batch':32,'temperature':0,'num_predict':180}
def payload(model,prompt,**extra):return {'model':model,'prompt':prompt,'think':False,'stream':False,'keep_alive':'5m','options':dict(OPTIONS),**extra}
def parse_test(result,validate):
    try:d=json.loads(result.get('response',''));result['json_valid']=True;result['passed']=result['ok'] and bool(validate(d))
    except Exception:result.update(json_valid=False,passed=False)
    return result

SCHEMAS={
 'photo_animals':({'animal':{'type':'string'},'count':{'type':'integer'}},lambda d:d=={'animal':'cat','count':2}),
 'photo_remotes':({'remote_count':{'type':'integer'}},lambda d:d=={'remote_count':2}),
 'poster_ocr':({'venue':{'type':'string'},'room':{'type':'integer'},'opening_time':{'type':'string'}},lambda d:d=={'venue':'PANDORA','room':12,'opening_time':'09:00'}),
 'poster_shapes':({'red_shape':{'type':'string'},'blue_shape':{'type':'string'},'green_shape':{'type':'string'}},lambda d:d=={'red_shape':'circle','blue_shape':'square','green_shape':'triangle'}),
 'poster_missing_address':({'street_address':{'type':['string','null']}},lambda d:d=={'street_address':None})}
image_cases=json.loads((ROOT.parent/'round3/image-cases.json').read_text())

def test(entry):
    model=entry['model'];before=memory();entry['unload_previous_seconds']=unload();entry['tests']=[]
    if entry['task']=='text':
        entry['load']=infer(payload(model,'Reply READY.',options={**OPTIONS,'num_predict':12}))
        if not entry['load']['ok']:entry['status']='load_failed';return
        for name,prompt,validate in cases:
            for trial in [1,2]:
                r=infer({'model':model,'messages':[{'role':'user','content':prompt}],'think':False,'format':'json','stream':False,'options':OPTIONS})
                entry['tests'].append({'name':name,'trial':trial,**parse_test(r,validate)});save()
                if not r['ok']:entry['status']='failed_during_suite';return
        tools=[{'type':'function','function':{'name':'search_listings','description':'Search public listings','parameters':{'type':'object','properties':{'borough':{'type':'string'},'activity':{'type':'string'}},'required':['borough','activity']}}}]
        r=infer({'model':model,'messages':[{'role':'user','content':'Use search_listings to find Swimming in Brooklyn.'}],'tools':tools,'think':False,'stream':False,'options':OPTIONS})
        r['passed']=any(c.get('function',{}).get('name')=='search_listings' and c['function'].get('arguments',{}).get('borough')=='Brooklyn' and c['function'].get('arguments',{}).get('activity')=='Swimming' for c in r.get('tool_calls',[]));entry['tool_call']=r
    else:
        entry['max_image_dimension']=640;entry['image_attempts']=[]
        for edge in [640,320]:
            image=base64.b64encode((ROOT.parent/'round3'/('cats.png' if edge==640 else 'cats-320.png')).read_bytes()).decode()
            r=infer(payload(model,'Identify the animals. Return JSON with animal and count.',images=[image],format='json',options={**OPTIONS,'num_predict':64}))
            entry['image_attempts'].append({'max_image_dimension':edge,**r});save()
            if r['ok']:entry['max_image_dimension']=edge;break
            if not any(x in r.get('error','').lower() for x in ['memory','killed','eof','timeout','token','context']):break
            unload()
        else:r={'ok':False}
        if not r['ok']:entry['status']='image_inference_failed';return
        images={name:base64.b64encode((ROOT.parent/'round3'/(name if entry['max_image_dimension']==640 else name.replace('.png','-320.png'))).read_bytes()).decode() for name in ['cats.png','poster.png']}
        for case in image_cases:
            for trial in [1,2]:
                p=payload(model,case['prompt'],images=[images[case['image']]],options={**OPTIONS,'num_predict':96})
                if case['json_format']:p['format']='json'
                r=infer(p)
                if case['name'] in SCHEMAS:parse_test(r,SCHEMAS[case['name']][1])
                else:r['passed']=r['ok'] and r['response'].strip().strip('.') in ['2','two','Two']
                entry['tests'].append({'name':case['name'],'trial':trial,**r});save()
                if not r['ok']:entry['status']='failed_during_suite';return
        entry['schema_tests']=[]
        for case in image_cases:
            if case['name'] not in SCHEMAS:continue
            props,validate=SCHEMAS[case['name']];schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
            r=parse_test(infer(payload(model,case['prompt'],images=[images[case['image']]],format=schema,options={**OPTIONS,'num_predict':96})),validate)
            r['keys_match']=r['json_valid'] and set(json.loads(r['response']))==set(props)
            entry['schema_tests'].append({'name':case['name'],**r});save()
    entry['status']='completed';entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)

key=next(line.split('=',1)[1].strip().strip('"') for line in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if line.startswith('GATEWAY_MAINTENANCE_KEY='))
def maintenance(data):return post('/internal/model-storage',data,base='http://127.0.0.1:8090',key=key)
lease=None;stop=threading.Event();renew_failed=threading.Event();current=None;new=False
initial=get('/api/tags');report['initial_inventory']=initial;original={m['name'].lower() for m in initial['models']};report['runtime_version']=get('/api/version');report['initial_memory']=memory()
assert int((CG/'memory.max').read_text())==2800*1024*1024
try:
    subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
    deadline=time.monotonic()+180
    while lease is None:
        try:lease=maintenance({'action':'acquire'})['lease']
        except urllib.error.HTTPError as e:
            if e.code!=409 or time.monotonic()>deadline:raise
            time.sleep(3)
    def renew():
        while not stop.wait(30):
            try:maintenance({'action':'renew','lease':lease})
            except Exception:renew_failed.set();return
    thread=threading.Thread(target=renew,daemon=True);thread.start();save()
    controls=[{'model':'granite4:1b-h','task':'text'},{'model':'hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0','task':'vision'}]
    for candidate,control in [(x,True) for x in controls]+[(x,False) for x in plan['candidates']]:
        if renew_failed.is_set():raise RuntimeError('Maintenance renewal failed; abort')
        entry=dict(candidate);entry.update(status='preparing',started_utc=now());report['controls' if control else 'models'].append(entry);save()
        model=entry['model'];current=model;new=model.lower() not in original;before=memory()
        print('START',model,flush=True)
        try:
            unload()
            if shutil.disk_usage('/').free<7*1024**3:raise RuntimeError('Disk reserve preflight failed')
            if new:
                with (ROOT/'pull.log').open('w') as log:
                    r=subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],stdout=log,stderr=subprocess.STDOUT,timeout=360)
                if r.returncode:
                    entry.update(status='pull_failed',error=(ROOT/'pull.log').read_text(errors='replace')[-1800:]);continue
            entry['tag']=next((m for m in get('/api/tags')['models'] if m['name'].lower()==model.lower()),None)
            show=post('/api/show',{'model':model});entry['capabilities']=show.get('capabilities',[]);entry['details']=show.get('details');entry['license']=show.get('license','')[:500]
            test(entry)
        except Exception as e:entry.update(status='runner_exception',error_type=type(e).__name__,error=str(e)[:1200])
        finally:
            entry['unload_seconds']=unload();entry['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)
            if new:
                # Only temporary packages created by this run; decision and digest persisted first.
                entry['cleanup_decision']='remove_temporary_weights_preserve_evidence';save()
                r=subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],capture_output=True,timeout=60)
                entry['new_package_removed']=r.returncode==0
            entry['disk_free_gib']=round(shutil.disk_usage('/').free/1024**3,2);entry['finished_utc']=now();save();print('DONE',model,entry['status'],sum(t.get('passed',False) for t in entry.get('tests',[])),flush=True);current=None;new=False
finally:
    try:
        unload()
        report['restore']=infer(payload('granite4:1b-h','Reply READY.',options={**OPTIONS,'num_ctx':8192,'num_batch':128,'num_predict':12,'prompt_cache_mib':128,'context_checkpoints':2}))
        report['final_inventory']=get('/api/tags');report['final_memory']=memory()
    finally:
        stop.set()
        if lease:maintenance({'action':'release','lease':lease})
        subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
        report['finished_utc']=now();save();print('FINISHED restored=',report.get('restore',{}).get('ok'),flush=True)
