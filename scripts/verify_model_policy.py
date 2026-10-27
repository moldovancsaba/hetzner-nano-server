"""Bounded live checks of ranked defaults, installed discovery and explicit overrides."""
import base64,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];keys=json.loads((ROOT/'private/api-keys.json').read_text());base='https://chatbotapi.haho.ai/v1';checks=[];report={'checks':checks}
def request(path,tenant='classscout',body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Request-Purpose':'test','Authorization':'Bearer '+keys[tenant]})
 try:
  with urllib.request.urlopen(req,timeout=115) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as response:return response.code,json.load(response)
def check(name,path,tenant='classscout',body=None,expected=200):
 status,data=request(path,tenant,body);checks.append({'name':name,'status':status,'expected':expected,'passed':status==expected});assert status==expected,(name,status,data);return data
def poll(job,tenant):
 for _ in range(100):
  status,row=request('/jobs/'+job['id'],tenant)
  assert status==200
  if row['status'] in ['completed','failed']:break
  time.sleep(2)
 assert row['status']=='completed',row
 return row
try:
 text=check('Text installed discovery','/models');camera=check('Camera installed discovery','/models','camera');report['text_discovery']=text;report['camera_discovery']=camera
 assert text['defaults']['text_chat']=='granite4:1b-h'
 assert camera['defaults']['image_recognition']=='hf.co/LiquidAI/LFM2-VL-450M-GGUF:Q8_0'
 assert camera['defaults']['image_moderation']=='hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0'
 assert any(not row['selectable_for'] for row in camera['data'])
 check('Wrong-task override blocked','/jobs','camera',{'task':'image_moderation','model':'granite4:1b-h','input':{'image_base64':'a'}},400)
 check('Untested override blocked','/chat/completions','classscout',{'model':'unapproved:70b','messages':[{'role':'user','content':'Hi'}]},400)
 auto=check('Auto text follows ranking','/chat/completions',body={'model':'auto','messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16});assert auto['model']=='granite4:1b-h';report['auto_text']=auto
 explicit=check('Explicit Qwen is a real override','/chat/completions',body={'model':'qwen3:0.6b','messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16});assert explicit['model']=='qwen3:0.6b';report['explicit_text']=explicit
 legacy=check('Explicit former alias selects actual Qwen','/chat/completions',body={'model':'qwen3:1.7b','messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16});assert legacy['model']=='qwen3:1.7b';report['explicit_former_alias']=legacy
 encoded=base64.b64encode((ROOT/'benchmarks/round3/cats.png').read_bytes()).decode();jobs=[]
 for task,model in [('image_recognition','auto'),('image_recognition','hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q8_0'),('image_moderation','auto')]:
  job=check('Submit '+task+' '+model,'/jobs','camera',{'task':task,'model':model,'input':{'image_base64':encoded}},202);jobs.append((task,model,job))
 report['image_jobs']=[]
 for task,requested,job in jobs:
  row=poll(job,'camera');expected=camera['defaults'][task] if requested=='auto' else requested;assert row['model']==expected and row['result']['model']==expected;report['image_jobs'].append(row)
 final=check('Restore ranking default','/chat/completions',body={'messages':[{'role':'user','content':'Say READY.'}],'max_tokens':16});assert final['model']=='granite4:1b-h'
 report['passed']=True
finally:(ROOT/'results/model-policy/public-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'installed_models':len(text['data']),'selectable_text':sum(bool(m['selectable_for']) for m in text['data']),'selectable_camera':sum(bool(m['selectable_for']) for m in camera['data'])}))
