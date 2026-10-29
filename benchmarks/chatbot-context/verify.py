"""Verify larger text contexts and Pandora history using synthetic content only."""
import http.cookiejar,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='https://chatbotapi.haho.ai'
keys=json.loads((ROOT/'private/api-keys.json').read_text())
checks=[];jobs=[]
def api(tenant,path,data=None,method=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers={'Authorization':'Bearer '+keys[tenant],'Content-Type':'application/json','X-Request-Purpose':'test'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as response:return response.code,json.load(response)
for tenant in ['classscout','habigoal','pandora','paperclip']:
 code,data=api(tenant,'/v1/models');assert code==200
 default=next(row for row in data['data'] if 'text_chat' in row['default_for'])
 assert default['rankings']['text_chat']['profile']['num_ctx']==8192
 if tenant=='classscout':
  qwen=next(row for row in data['data'] if row['id']=='qwen3:1.7b')
  assert qwen['rankings']['text_chat']['profile']['num_ctx']==2048 and 'text_chat' in qwen['selectable_for']
 checks.append({'check':tenant+' default advertises 8192 tokens','passed':True})
filler='Background record: public venue information was checked.\n'
schema={'type':'json_schema','json_schema':{'name':'context_check','strict':True,'schema':{'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}}}
prompt='Verified code: CEDAR852\n'+filler*300+'\nReturn the verified code in the field code.'
for tenant in ['classscout','habigoal','pandora']:
 code,submitted=api(tenant,'/v1/jobs',{'task':'text_chat','input':{'model':'auto','messages':[{'role':'user','content':prompt}],'response_format':schema,'max_tokens':64,'temperature':0}});assert code==202,(tenant,code,submitted)
 for _ in range(300):
  code,row=api(tenant,'/v1/jobs/'+submitted['id']);assert code==200
  if row['status'] in {'completed','failed'}:break
  time.sleep(1)
 assert row['status']=='completed',row
 result=row['result'];assert result['usage']['prompt_tokens']>2048
 assert row['model_profile']['num_ctx']==8192
 assert json.loads(result['choices'][0]['message']['content'])=={'code':'CEDAR852'}
 jobs.append({'tenant':tenant,'model':result['model'],'context':row['model_profile']['num_ctx'],'usage':result['usage'],'passed':True})
 api(tenant,'/v1/jobs/'+submitted['id'],method='DELETE')
 print(tenant+' larger-context request passed',flush=True)
secret=next(line.split(':',1)[1].strip() for line in (ROOT/'private/chat-access.txt').read_text().splitlines() if line.startswith('Secret:'))
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def chat(path,body,form=False):
 req=urllib.request.Request(BASE+path,data=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':BASE,'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json','X-Request-Purpose':'test'})
 try:
  with opener.open(req,timeout=300) as response:
   raw=response.read();return response.status,json.loads(raw) if response.headers.get_content_type()=='application/json' else None
 except urllib.error.HTTPError as response:
  raw=response.read();return response.code,json.loads(raw) if response.headers.get_content_type()=='application/json' else None
import urllib.parse
code,_=chat('/chat/login',urllib.parse.urlencode({'secret':secret}).encode(),form=True);assert code==200
code,error=chat('/chat/api',{'messages':[{'role':'user','content':'🙂'*16000}]})
assert code==400 and 'too long' in error['error'],(code,error)
checks.append({'check':'Pandora rejects oversized newest message without truncating it','passed':True})
messages=[{'role':'user','content':'Remember this exact synthetic verification code: BIRCH418'},{'role':'assistant','content':'I will use BIRCH418 as the verification code.'}]
for _ in range(4):messages += [{'role':'user','content':filler*65},{'role':'assistant','content':'Background noted.'}]
messages.append({'role':'user','content':'What was the verification code at the start? Reply with that code only.'})
started=time.monotonic();code,response=chat('/chat/api',{'messages':messages});assert code==200,(code,response)
assert 'BIRCH418' in response['reply']
assert response['context_tokens']==8192 and response['kept_messages']==11 and not response['history_trimmed']
assert response['usage']['prompt_tokens']>2048,response
checks.append({'check':'Pandora retains a fact beyond old six-message/2600-character history','passed':True,'messages_kept':response['kept_messages'],'context':response['context_tokens'],'usage':response['usage'],'seconds':round(time.monotonic()-started,3),'reply':response['reply']})
chat('/chat/logout',b'x=1',form=True)
(ROOT/'benchmarks/chatbot-context/public-verification.json').write_text(json.dumps({'checks':checks,'api_jobs':jobs},indent=2)+'\n')
print('Pandora 8K conversation and new-message validation passed',flush=True)
