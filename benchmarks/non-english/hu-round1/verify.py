"""Authenticated public API smoke checks, never a Hungarian quality certificate."""
import json,pathlib,time,urllib.request,urllib.error,uuid
ROOT=pathlib.Path(__file__).resolve().parents[3];keys=json.loads((ROOT/'private/api-keys.json').read_text());checks=[]
base='https://chatbotapi.haho.ai/v1'
def call(path,tenant='classscout',data=None,method=None,missing=False):
 h={'Content-Type':'application/json','X-Request-Purpose':'test'}
 if not missing:h['Authorization']='Bearer '+keys[tenant]
 if data is not None:h['Idempotency-Key']='hu-verification-'+uuid.uuid4().hex
 req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=h,method=method)
 for _ in range(120):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   if e.code in [429,503] and data is not None:time.sleep(2);continue
   return e.code,json.load(e)
 raise TimeoutError('No admission')
def check(name,value):checks.append({'name':name,'passed':bool(value)});assert value,name
def job(tenant,body):
 code,j=call('/jobs',tenant,body);check('Admission '+tenant+' '+body['task'],code==202)
 for _ in range(300):
  _,row=call('/jobs/'+j['id'],tenant)
  if row.get('status') in ['completed','failed']:break
  time.sleep(2)
 check('Completed '+tenant+' '+body['task'],row.get('status')=='completed')
 code,_=call('/jobs/'+j['id'],tenant,method='DELETE');check('Consumed result deleted',code==200)
 code,_=call('/jobs/'+j['id'],tenant);check('Deleted result unavailable',code==404)
 return row
code,_=call('/models',missing=True);check('Missing key refused',code==401)
for tenant in ['classscout','habigoal','paperclip','pandora']:
 code,d=call('/job-types',tenant);check(tenant+' Hungarian discovery',code==200 and 'text_chat_hu' in d['job_types']);check(tenant+' experimental flag',d['job_types']['text_chat_hu']['experimental'] is True)
code,_=call('/jobs','camera',{'task':'text_chat_hu','input':{'messages':[{'role':'user','content':'Szia!'}]}});check('Camera cannot invoke Hungarian text',code==403)
body={'task':'text_chat_hu','model':'auto','input':{'messages':[{'role':'user','content':'Budapesten lakom, két gyermekem van. Add vissza a city és children mezőket JSON-ként.'}],'temperature':0,'max_tokens':64,'response_format':{'type':'json_schema','json_schema':{'name':'hu_test','schema':{'type':'object','properties':{'city':{'type':'string'},'children':{'type':'integer'}},'required':['city','children'],'additionalProperties':False}}}}}
r=job('classscout',body);expected=json.loads((ROOT/'config/model-policy.json').read_text())['defaults']['text_chat_hu'];check('Ranked experimental model honored',r['model']==expected);check('Measured low-memory profile honored',r['model_profile']['num_ctx']==1024 and r['model_profile']['num_batch']==8)
content=json.loads(r['result']['choices'][0]['message']['content']);check('Schema-constrained synthetic example correct',content=={'city':'Budapest','children':2})
r=job('paperclip',{'task':'text_chat_hu','model':'auto','input':{'messages':[{'role':'user','content':'Írd le ezt az egy szót: KÉSZ'}],'max_tokens':16,'temperature':0}});check('Paperclip Hungarian profile stays short',r['model_profile']['num_ctx']==1024)
r=job('classscout',{'task':'text_chat','model':'auto','input':{'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':16}});check('English default/context preserved',r['model']=='granite4:1b-h' and r['model_profile']['num_ctx']==8192)
code,_=call('/jobs','classscout',{'task':'text_chat_hu','input':{'messages':[{'role':'user','content':'ő'*900}]}});check('Oversized Hungarian input refused',code==400)
out={'passed':True,'policy_id':json.loads((ROOT/'config/model-policy.json').read_text())['policy_id'],'experimental':True,'checks':checks}
(ROOT/'benchmarks/non-english/hu-round1/public-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'passed':True,'checks':len(checks)}))
