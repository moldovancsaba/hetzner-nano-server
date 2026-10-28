"""Public test-marked checks after deployment; no customer traffic or credentials logged."""
import base64,json,sys,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from client import key_for,request
policy=json.loads((ROOT/'config/model-policy.json').read_text());report={'checks':[],'jobs':[]}
def check(name,ok):
    report['checks'].append({'name':name,'passed':bool(ok)});assert ok,name
def call(path,tenant='classscout',body=None):return request(path,key_for(tenant),body,purpose='test')
try:
    check('Unauthenticated request refused',request('/models',purpose='test')[0]==401)
    for tenant in ['classscout','habigoal','camera']:
        code,models,_=call('/models',tenant);check(tenant+' discovery',code==200)
        check(tenant+' policy version',models['policy_id']==policy['policy_id'])
        for task,model in models['defaults'].items():check(tenant+' ranked '+task,model==policy['defaults'][task])
        if tenant=='classscout':
            row=next(m for m in models['data'] if m['id']==policy['defaults']['text_chat'])
            check('Existing default 8K preserved',row['rankings']['text_chat']['profile']['num_ctx']==8192)
    image=base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode()
    jobs=[]
    for tenant,task,body in [('classscout','text_chat',{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}),('camera','image_recognition',{'image_base64':image}),('camera','image_moderation',{'image_base64':image})]:
        code,job,_=call('/jobs',tenant,{'task':task,'model':'auto','input':body});check('Submit '+task,code==202);jobs.append((tenant,task,job['id']))
    for tenant,task,jid in jobs:
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            code,row,_=call('/jobs/'+jid,tenant)
            if code==200 and row['status'] in ['completed','failed']:break
            time.sleep(1)
        check('Completed '+task,code==200 and row['status']=='completed')
        check('Actual '+task+' model',row['model']==policy['defaults'][task] and row['result']['model']==policy['defaults'][task])
        report['jobs'].append({'task':task,'model':row['model'],'status':row['status']})
        req=urllib.request.Request('https://chatbotapi.haho.ai/v1/jobs/'+jid,method='DELETE',headers={'Authorization':'Bearer '+key_for(tenant),'X-Request-Purpose':'test'})
        with urllib.request.urlopen(req,timeout=20) as response:check('Delete test '+task,response.status==200)
    code,completion,_=call('/chat/completions',body={'model':'auto','messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16});check('Chat compatibility and restore text',code==200 and completion['model']==policy['defaults']['text_chat'])
    code,queue,_=call('/queue');check('Queue healthy',code==200 and queue['status']=='ok' and not queue['model_storage_maintenance']);report['queue']=queue
    for url in ['https://chatbotapi.haho.ai/chat/','https://paperclip.haho.ai/']:
        with urllib.request.urlopen(url,timeout=20) as response:check(url,response.status==200)
    report['passed']=True
finally:(ROOT/'benchmarks/round4/public-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'checks':len(report['checks'])}))
