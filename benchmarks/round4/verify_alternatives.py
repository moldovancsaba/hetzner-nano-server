"""Test the two newly retained explicit choices, then restore default text residency."""
import base64,json,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from client import request,key_for
report={'jobs':[]}
try:
    image=base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode()
    for tenant,task,model,payload in [('classscout','text_chat','qwen2.5:0.5b',{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}),('camera','image_recognition','minicpm-v4.6:1b',{'image_base64':image})]:
        code,job,_=request('/jobs',key_for(tenant),{'task':task,'model':model,'input':payload},purpose='test');assert code==202,(task,code)
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            code,row,_=request('/jobs/'+job['id'],key_for(tenant),purpose='test')
            if code==200 and row['status'] in ['completed','failed']:break
            time.sleep(1)
        assert row['status']=='completed',row
        assert row['model']==model and row['result']['model']==model
        report['jobs'].append({'task':task,'model':model,'status':row['status'],'result':row['result']})
        req=urllib.request.Request('https://chatbotapi.haho.ai/v1/jobs/'+job['id'],method='DELETE',headers={'Authorization':'Bearer '+key_for(tenant),'X-Request-Purpose':'test'})
        with urllib.request.urlopen(req,timeout=20) as response:assert response.status==200
    report['passed']=True
finally:
    code,data,_=request('/chat/completions',key_for('classscout'),{'model':'auto','messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16},purpose='test')
    report['restored_default']=code==200 and data.get('model')=='granite4:1b-h'
    (ROOT/'benchmarks/round4/alternative-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report.get('passed',False),'restored_default':report['restored_default']}))
