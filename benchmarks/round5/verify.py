"""Low-volume public routing/regression checks, separate from quality evaluation."""
import argparse,base64,json,sys,time,urllib.error,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from client import key_for
parser=argparse.ArgumentParser();parser.add_argument('--with-moderation',action='store_true');args=parser.parse_args()
policy=json.loads((ROOT/'config/model-policy.json').read_text());base='https://chatbotapi.haho.ai/v1';report={'policy_id':policy['policy_id'],'checks':[],'jobs':[]}
def call(path,tenant='classscout',body=None,method=None,missing=False):
    headers={'Content-Type':'application/json','X-Request-Purpose':'test'}
    if not missing:headers['Authorization']='Bearer '+key_for(tenant)
    if body is not None:headers['Idempotency-Key']='vision-verification-'+uuid.uuid4().hex
    req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
    for _ in range(240):
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in [429,503] and body is not None:time.sleep(1);continue
            return error.code,json.load(error)
    raise TimeoutError('No safe admission within bounded waiting')
def check(name,ok):report['checks'].append({'name':name,'passed':bool(ok)});assert ok,name
def poll(tenant,jid):
    for _ in range(480):
        code,row=call('/jobs/'+jid,tenant)
        if code==200 and row['status'] in ['completed','failed']:return row
        time.sleep(.5)
    raise TimeoutError('Verification job did not finish')
def consume(tenant,row):
    check('Job completed '+row['task'],row['status']=='completed')
    expected=policy['defaults'][row['task']];check('Actual ranked model '+row['task'],row['model']==expected and row['result']['model']==expected)
    report['jobs'].append({key:row.get(key) for key in ['task','model','status','created_at','started_at','finished_at','queue_wait_seconds','model_profile']})
    code,_=call('/jobs/'+row['id'],tenant,method='DELETE');check('Delete synthetic '+row['task'],code==200)
try:
    code,_=call('/models',missing=True);check('Missing key refused',code==401)
    for tenant in ['classscout','habigoal','camera']:
        code,models=call('/models',tenant);check(tenant+' authenticated discovery',code==200);check(tenant+' matching policy',models['policy_id']==policy['policy_id'])
        for task,model in models['defaults'].items():check(tenant+' default '+task,model==policy['defaults'][task])
        if tenant=='classscout':
            row=next(r for r in models['data'] if r['id']==policy['defaults']['text_chat']);check('Verified default text context preserved',row['rankings']['text_chat']['profile']['num_ctx']==8192)
        if tenant=='camera':
            legacy=[meta for r in models['data'] for meta in r['rankings'].values() if meta.get('ranking_tier')=='legacy_screening_not_comparable'];check('Legacy evidence is not a current quality rank',all(r['current_rank'] is None and r['rank']>5 for r in legacy))
    image=base64.b64encode((ROOT/'private/vision-evaluation/images/coco-98261.jpg').read_bytes()).decode()
    code,_=call('/jobs','classscout',{'task':'image_recognition','input':{'image_base64':image}});check('ClassScout image access refused',code==403)
    code,_=call('/jobs','camera',{'task':'text_chat','input':{'messages':[{'role':'user','content':'Hi'}]}});check('Camera text access refused',code==403)
    code,job=call('/jobs','camera',{'task':'image_recognition','model':'auto','input':{'image_base64':image}});check('Auto image admission',code==202)
    code,text=call('/jobs','classscout',{'task':'text_chat','model':'auto','input':{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}});check('Mixed text admission',code==202)
    image_row=poll('camera',job['id']);text_row=poll('classscout',text['id'])
    check('Mixed work serialized',text_row.get('started_at',0)>=image_row.get('finished_at',1e20))
    consume('camera',image_row);consume('classscout',text_row)
    if args.with_moderation:
        code,job=call('/jobs','camera',{'task':'image_moderation','model':'auto','input':{'image_base64':image}});check('Auto moderation admission',code==202)
        row=poll('camera',job['id']);check('Moderation remains human review',row.get('result',{}).get('review_required') is True and row['result']['automated_decision']=='none');consume('camera',row)
        explicit='hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0'
        code,job=call('/jobs','camera',{'task':'image_moderation','model':explicit,'input':{'image_base64':image}});check('Explicit tested moderation admitted',code==202)
        row=poll('camera',job['id']);check('Explicit model remains a deliberate override',row['status']=='completed' and row['model']==row['result']['model']==explicit)
        check('Explicit moderation remains human review',row['result']['review_required'] is True and row['result']['automated_decision']=='none')
        report['jobs'].append({key:row.get(key) for key in ['task','model','status','created_at','started_at','finished_at','queue_wait_seconds','model_profile']})
        code,_=call('/jobs/'+row['id'],'camera',method='DELETE');check('Delete explicit synthetic result',code==200)
        code,job=call('/jobs','classscout',{'task':'text_chat','model':'auto','input':{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}});check('Default text restoration admitted',code==202);consume('classscout',poll('classscout',job['id']))
    explicit='minicpm-v4.6:q5_K_M'
    code,inventory=call('/models','camera')
    if any(x['id']==explicit and 'image_recognition' in x.get('selectable_for',[]) for x in inventory.get('data',[])):
        code,job=call('/jobs','camera',{'task':'image_recognition','model':explicit,'input':{'image_base64':image}})
        check('Explicit new image candidate admitted',code==202)
        row=poll('camera',job['id'])
        check('Explicit image model honored',row['status']=='completed' and row['model']==row['result']['model']==explicit)
        code,_=call('/jobs/'+row['id'],'camera',method='DELETE');check('Explicit new image result deleted',code==200)
        code,job=call('/jobs','classscout',{'task':'text_chat','model':'auto','input':{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}});check('Text restoration after explicit image admitted',code==202);consume('classscout',poll('classscout',job['id']))
    code,queue=call('/queue');check('Shared queue healthy',code==200 and queue['status']=='ok');report['queue']=queue
    report['passed']=True
finally:
    name='public-verification.json' if args.with_moderation else 'recognition-public-verification.json'
    (ROOT/'benchmarks/round5'/name).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report.get('passed',False),'checks':len(report['checks'])}))
