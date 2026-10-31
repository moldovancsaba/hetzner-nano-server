"""Retain per-task top three and recent real demand (window set in model-storage-policy.json); delete only under gateway lease."""
import argparse,datetime,json,math,os,subprocess,time,urllib.error,urllib.request
from pathlib import Path

def reasons(model,policy,usage,loaded,now,storage=None):
    storage=storage or {};days=storage.get("keep_production_request_days",3);top=storage.get("keep_top_per_task",3);grace=storage.get("initial_inventory_history_grace_days",0)
    name=model['name'];keep=[]
    if name in policy['defaults'].values():keep.append('current_default')
    entry=next((v for k,v in policy['models'].items() if k.lower()==name.lower()),{})
    for task,rank in entry.get('tasks',{}).items():
        if rank['rank']<=top:keep.append('top_three:'+task)
    recent=next((v for k,v in usage['models'].items() if k.lower()==name.lower()),None)
    if recent and recent['last_valid_request_at']>=now-days*86400:keep.append('production_request_within_%d_days'%days)
    if grace and usage['tracking_started_at']>=now-grace*86400 and usage['bootstrap_inventory'].get(name)==model.get('digest'):
        keep.append('initial_%d_day_history_grace'%grace)
    if name in loaded:keep.append('resident_model')
    return keep

def validate_storage(storage):
    # The retention window and the history grace are checked against bounds, so an owner change of either needs no
# code change and a typo cannot evict everything. keep_top_per_task is the exception: only 3 is accepted.
    assert storage['version']=='model-storage.v2' and storage['automatic_weight_deletion'] is True
    assert storage['keep_top_per_task']==3
    assert isinstance(storage['keep_production_request_days'],int) and 1<=storage['keep_production_request_days']<=30
    assert isinstance(storage['initial_inventory_history_grace_days'],int) and 0<=storage['initial_inventory_history_grace_days']<=30
    return storage

def validate_usage(data):
    assert data['version']=='model-usage.v1' and isinstance(data['models'],dict) and isinstance(data['bootstrap_inventory'],dict)
    assert isinstance(data['tracking_started_at'],(int,float)) and math.isfinite(data['tracking_started_at'])
    for value in data['models'].values():assert isinstance(value['last_valid_request_at'],(int,float)) and math.isfinite(value['last_valid_request_at'])
    return data

def request(url,payload=None,key=None,timeout=15):
    headers={'Content-Type':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)

def main(apply=False,state=Path('/var/lib/narimato-model-cleanup')):
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'apply':apply,'status':'planning','models':[]}
    path=state/('cleanup-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    def save():
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(path)
        tmp=state/'latest.tmp';tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(state/'latest.json')
    save();lease=None;key=os.environ['GATEWAY_MAINTENANCE_KEY']
    endpoint='http://127.0.0.1:8090/internal/model-storage'
    try:
        if apply:
            try:lease=request(endpoint,{'action':'acquire'},key)['lease']
            except urllib.error.HTTPError as error:
                if error.code==409:report['status']='skipped_gateway_busy';save();return report
                raise
        usage_path=Path('/var/lib/narimato-gateway/model-usage.json')
        usage=validate_usage(json.loads(usage_path.read_text()))
        policy_path=Path('/opt/narimato-gateway/config/model-policy.json');policy=json.loads(policy_path.read_text())
        storage=validate_storage(json.loads(Path('/opt/narimato-ai/model-storage-policy.json').read_text()))
        if not policy.get('defaults') or not policy.get('models'):raise ValueError('Missing ranked policy')
        inventory=request('http://127.0.0.1:11434/api/tags')['models']
        report['usage_tracking_started_at']=usage['tracking_started_at'];report['policy_id']=policy['policy_id']
        for model in inventory:
            policy=json.loads(policy_path.read_text());usage=validate_usage(json.loads(usage_path.read_text()))
            loaded={m['name'] for m in request('http://127.0.0.1:11434/api/ps')['models']}
            keep=reasons(model,policy,usage,loaded,time.time(),storage)
            row={'model':model['name'],'digest':model.get('digest'),'size_bytes':model.get('size'),'keep_reasons':keep,'decision':'keep' if keep else 'remove'}
            report['models'].append(row);save() # Persist identity/digest before destructive action.
            if keep or not apply:continue
            request(endpoint,{'action':'renew','lease':lease},key)
            # The lease prevents admission of new service work during this final check and deletion.
            fresh=next((m for m in request('http://127.0.0.1:11434/api/tags')['models'] if m['name']==model['name']),None)
            if not fresh or fresh.get('digest')!=model.get('digest'):
                row['decision']='skipped_artifact_changed';save();continue
            keep=reasons(fresh,json.loads(policy_path.read_text()),validate_usage(json.loads(usage_path.read_text())),{m['name'] for m in request('http://127.0.0.1:11434/api/ps')['models']},time.time(),storage)
            if keep:row['decision']='keep';row['keep_reasons']=keep;save();continue
            result=subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model['name']],capture_output=True,timeout=60)
            row['removed']=result.returncode==0
            if result.returncode:raise RuntimeError('Model removal failed')
            save()
        report['status']='completed'
    except Exception as error:
        report['status']='failed';report['error_type']=type(error).__name__;save();raise
    finally:
        if lease:
            try:request(endpoint,{'action':'release','lease':lease},key)
            except Exception:report['lease_release_failed']=True
        report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--state-dir',type=Path,default=Path('/var/lib/narimato-model-cleanup'));args=parser.parse_args()
    result=main(args.apply,args.state_dir)
    print(json.dumps({'status':result['status'],'removed':sum(r.get('removed',False) for r in result['models']),'kept':sum(r['decision']=='keep' for r in result['models'])}))
