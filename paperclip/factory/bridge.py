"""Paperclip process-adapter bridge. Run credentials never reach stdout or model prompts."""
import json,os,sys,urllib.request,urllib.error
required=['PAPERCLIP_RUN_ID','PAPERCLIP_AGENT_ID','PAPERCLIP_COMPANY_ID','PAPERCLIP_API_KEY']
if any(not os.environ.get(key) for key in required):
 print('Factory bridge requires a Paperclip agent run.',file=sys.stderr);sys.exit(1)
body={'run_id':os.environ[required[0]],'agent_id':os.environ[required[1]],'company_id':os.environ[required[2]],'agent_token':os.environ[required[3]]}
request=urllib.request.Request('http://127.0.0.1:9089/run',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(request,timeout=900) as response:result=json.load(response)
 print(json.dumps(result))
except urllib.error.HTTPError as error:
 try:detail=json.loads(error.read(4096)).get('error','Factory task failed')
 except Exception:detail='Factory task failed'
 print(detail,file=sys.stderr);sys.exit(1)
except Exception as error:
 print('Factory bridge unavailable: '+type(error).__name__,file=sys.stderr);sys.exit(1)
