"""Public end-to-end context verification; never prints the Paperclip API key."""
import json, time, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
key=json.loads((ROOT/'private/api-keys.json').read_text())['paperclip']
BASE='https://chatbotapi.haho.ai'
def request(path,data=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Request-Purpose':'test'})
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
code,models=request('/v1/models');assert code==200
model=next(m for m in models['data'] if 'text_chat' in m['default_for'])
assert model['rankings']['text_chat']['profile']['num_ctx']==8192
checks=[{'check':'dedicated Paperclip discovery shows 8K','passed':True}]
code,error=request('/v1/jobs',{'task':'text_chat','input':{'messages':[{'role':'user','content':' venue'*18000}]}})
assert code==400 and 'token budget' in error['error']['message'],(code,error)
checks.append({'check':'oversized token input rejected before admission','passed':True})
code,error=request('/v1/jobs',{'task':'image_recognition','input':{'image_base64':'a'}})
assert code==403
checks.append({'check':'Paperclip cannot use Camera jobs','passed':True})
prompt='Remember this exact test code: MAPLE527\n'+'Background record: public venue information was checked.\n'*450+'\nReturn exactly one JSON field named code, whose value is the test code given at the start. No other fields.'
started=time.monotonic()
code,submitted=request('/v1/jobs',{'task':'text_chat','input':{'messages':[{'role':'user','content':prompt}],'max_tokens':64,'temperature':0,'response_format':{'type':'json_schema','json_schema':{'name':'context_probe','strict':True,'schema':{'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}}}}})
assert code==202,(code,submitted)
job_id=submitted['id']
for _ in range(180):
 code,job=request('/v1/jobs/'+job_id)
 assert code==200
 if job['status'] in {'completed','failed'}:break
 time.sleep(2)
else:raise RuntimeError('Job did not finish in bounded wait')
assert job['status']=='completed',job
result=job['result'];message=result['choices'][0]['message']['content']
attempt={'job':job_id,'model':result['model'],'context':job['model_profile']['num_ctx'],'usage':result['usage'],'response':message}
(ROOT/'benchmarks/paperclip-context/public-verification-latest-attempt.json').write_text(json.dumps(attempt,indent=2)+'\n')
assert json.loads(message)=={'code':'MAPLE527'},message
assert job['model_profile']['num_ctx']==8192,job
assert result['usage']['prompt_tokens']>2048,result
checks.append({'check':'public async input beyond 2K retains beginning-of-prompt fact','passed':True})
print(json.dumps({'checks':checks,'job':job_id,'model':result['model'],'context':job['model_profile']['num_ctx'],'usage':result['usage'],'seconds':round(time.monotonic()-started,3),'response':message},indent=2))
