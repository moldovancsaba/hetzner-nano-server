"""Low-volume mixed-workload HTTPS verification; only neutral test data."""
import base64,json,time,urllib.request,urllib.error,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];keys=json.loads((ROOT/'private/api-keys.json').read_text());BASE='https://chatbotapi.haho.ai'
checks=[]
def request(path,tenant='classscout',data=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+keys[tenant],'Content-Type':'application/json','X-Request-Purpose':'test'})
 try:
  with urllib.request.urlopen(req,timeout=115) as r:
   raw=r.read().decode();return r.status,raw if r.headers.get('Content-Type','').startswith('text/event-stream') else json.loads(raw)
 except urllib.error.HTTPError as r:
  try:body=json.load(r)
  except Exception:body={}
  return r.code,body

def check(name,path,tenant,expected,data=None):
 code,body=request(path,tenant,data);checks.append({'name':name,'status':code,'expected':expected,'passed':code==expected});assert code==expected,(name,code,body);return body
report={'scope':'Transport, routing and isolation verification; semantic text-probe accuracy recorded independently.','checks':checks,'jobs':[]}
try:
 for tenant,tasks in [('classscout',{'text_chat'}),('habigoal',{'text_chat'}),('camera',{'image_recognition','image_moderation'})]:
  allowed=check(tenant+' task discovery','/v1/job-types',tenant,200);assert set(allowed['job_types'])==tasks
 check('Camera cannot submit text','/v1/jobs','camera',403,{'task':'text_chat','input':{'messages':[{'role':'user','content':'Hi'}]}})
 check('ClassScout cannot submit images','/v1/jobs','classscout',403,{'task':'image_recognition','input':{'image_base64':'a'}})
 check('Arbitrary model rejected','/v1/chat/completions','classscout',400,{'model':'arbitrary:70b','messages':[{'role':'user','content':'Hi'}]})
 encoded=base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode()
 text={'messages':[{'role':'user','content':'Return JSON with exactly one property ready set to true.'}],'max_tokens':32,'response_format':{'type':'json_object'}}
 submitted=[]
 for tenant,task,value in [('classscout','text_chat',text),('camera','image_moderation',{'image_base64':encoded}),('camera','image_recognition',{'image_base64':encoded}),('habigoal','text_chat',text)]:
  job=check('Submit '+tenant+' '+task,'/v1/jobs',tenant,202,{'task':task,'input':value});submitted.append((tenant,task,job['id']))
 report['queue_during_work']=check('Shared queue visibility','/v1/queue','classscout',200)
 check('Cross-service result isolation','/v1/jobs/'+submitted[0][2],'camera',404)
 for tenant,task,job_id in submitted:
  for _ in range(100):
   code,row=request('/v1/jobs/'+job_id,tenant);assert code==200
   if row['status'] in ['completed','failed']:break
   time.sleep(2)
  assert row['status']=='completed',(task,row)
  assert row['model']=={'text_chat':'granite4:1b-h','image_recognition':'hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0','image_moderation':'hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0'}[task]
  if task=='text_chat':
   parsed=json.loads(row['result']['choices'][0]['message']['content']);assert isinstance(parsed,dict)
   row['semantic_text_probe']={'expected':{'ready':True},'correct':parsed=={'ready':True}}
  if task=='image_moderation':assert row['result']['review_required'] is True
  report['jobs'].append(row)
 for previous,current in zip(report['jobs'],report['jobs'][1:]):assert previous['finished_at']<=current['started_at']
 checks.append({'name':'FIFO timestamps prove no overlapping mixed jobs','passed':True})
 code,body=request('/v1/chat/completions','habigoal',{'messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16,'stream':True});assert code==200 and 'data: [DONE]' in body
 checks.append({'name':'Buffered streaming compatibility','passed':True})
 check('Pandora uses the same authenticated queue','/v1/chat/completions','pandora',200,{'messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16})
 report['final_queue']=check('Queue drained','/v1/queue','classscout',200)
 assert report['final_queue']['queued']==0
 report['passed']=True
finally:
 (ROOT/os.environ.get('GATEWAY_VERIFICATION_OUTPUT','results/gateway/public-verification.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'mixed_jobs':len(report['jobs']),'switches':report['final_queue']['counters']['switches']}))
