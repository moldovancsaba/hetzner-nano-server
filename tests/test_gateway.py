import base64,io,json,threading,time,unittest,urllib.request,urllib.error
from unittest.mock import patch
from PIL import Image
from gateway.server import Scheduler,Server,Runner,ROUTES,UpstreamUncertain,text_input

def completion():
 return {'id':'test','created':1,'model':'qwen3:1.7b','object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':'READY'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}

def wait(s,tenant,job):return s.wait(tenant,job,3)
class Tests(unittest.TestCase):
 def test_fifo_one_active_and_isolation(self):
  gate=threading.Event();begun=threading.Event();seen=[];active=0;maximum=0
  def run(task,payload,model):
   nonlocal active,maximum
   active+=1;maximum=max(maximum,active);seen.append(task);begun.set();gate.wait(2);active-=1
   return completion(),{'target_model':model,'unloaded_models':[]}
  s=Scheduler(run)
  a,_=s.submit('classscout','text_chat',{});begun.wait(1)
  b,_=s.submit('camera','image_moderation',b'a')
  c,_=s.submit('habigoal','text_chat',{})
  self.assertIsNone(s.read('camera',a));self.assertEqual(s.read('camera',b)['queue_position'],1)
  self.assertEqual(s.read('habigoal',c)['queue_position'],2)
  gate.set()
  for tenant,job in [('classscout',a),('camera',b),('habigoal',c)]:self.assertEqual(wait(s,tenant,job)['status'],'completed')
  self.assertEqual(seen,['text_chat','image_moderation','text_chat']);self.assertEqual(maximum,1)
 def test_timeout_opens_circuit_and_fails_waiting(self):
  gate=threading.Event();begun=threading.Event()
  def run(*args):begun.set();gate.wait(2);raise UpstreamUncertain()
  s=Scheduler(run);a,_=s.submit('camera','image_moderation',b'a');begun.wait(1);b,_=s.submit('classscout','text_chat',{})
  gate.set();self.assertEqual(wait(s,'camera',a)['error']['code'],'upstream_state_unknown')
  self.assertEqual(wait(s,'classscout',b)['status'],'failed');self.assertEqual(s.submit('camera','image_moderation',b'x')[1],'upstream_unavailable')
 def test_tenant_capacity_idempotency_and_expiry(self):
  gate=threading.Event();begun=threading.Event()
  def run(*args):begun.set();gate.wait(2);return {},{}
  s=Scheduler(run);a,_=s.submit('camera','image_moderation',b'a','repeat',{'image_sha256':'a'});begun.wait(1)
  self.assertEqual(s.submit('camera','image_moderation',b'a','repeat',{'image_sha256':'a'})[0],a)
  self.assertEqual(s.submit('camera','image_moderation',b'a','repeat',{'image_sha256':'b'})[1],'conflict')
  for _ in range(3):self.assertIsNone(s.submit('camera','image_moderation',b'a')[1])
  self.assertEqual(s.submit('camera','image_moderation',b'a')[1],'busy')
  b,_=s.submit('classscout','text_chat',{},'repeat');self.assertNotEqual(a,b)
  with s.cv:s.rows[b]['created_at']-=181
  self.assertEqual(s.read('classscout',b)['error']['code'],'queue_deadline_exceeded');gate.set()
 def test_switch_unloads_before_inference(self):
  calls=[]
  def native(path,body=None,timeout=None):
   calls.append((path,body))
   if path=='/api/ps':return {'models':[{'name':'old-model'}]} if len(calls)==1 else {'models':[]}
   if path=='/api/generate':return {'done':True}
   return completion()
  with patch('gateway.server.native',side_effect=native):
   result,switch=Runner()('text_chat',{},'qwen3:1.7b')
  self.assertEqual([x[0] for x in calls],['/api/ps','/api/generate','/api/ps','/v1/chat/completions']);self.assertEqual(switch['unloaded_models'],['old-model'])
 def test_text_limits(self):
  for data in [{'messages':[{'role':'user','content':[{'type':'image_url'}]}]}, {'messages':[]}, {'messages':[{'role':'user','content':'Hi'}],'model':'giant:70b'}, {'messages':[{'role':'user','content':'Hi'}],'max_tokens':513}]:
   with self.assertRaises(ValueError):text_input(data,'qwen3:1.7b')
 def test_http_permissions_async_chat_and_sse(self):
  s=Scheduler(lambda *args:(completion(),{'unloaded_models':[]}))
  http=Server(('127.0.0.1',0),{'camera':'c'*40,'classscout':'t'*40},s);threading.Thread(target=http.serve_forever,daemon=True).start()
  def req(path,body=None,key='t'*40):
   request=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
   try:
    with urllib.request.urlopen(request) as r:return r.status,r.read().decode()
   except urllib.error.HTTPError as r:return r.code,r.read().decode()
  try:
   self.assertEqual(req('/v1/queue',key='wrong')[0],401)
   self.assertEqual(req('/v1/models',key='c'*40)[0],401)
   self.assertEqual(req('/v1/moderation/health')[0],401)
   self.assertEqual(req('/v1/jobs',{'task':'image_recognition','input':{'image_base64':'a'}})[0],403)
   self.assertEqual(json.loads(req('/v1/job-types',key='c'*40)[1])['job_types'].keys(),{'image_recognition','image_moderation'})
   body={'messages':[{'role':'user','content':'Hi'}]}
   code,data=req('/v1/jobs',{'task':'text_chat','input':body});self.assertEqual(code,202);job=json.loads(data)['id'];self.assertEqual(req('/v1/jobs/'+job,key='c'*40)[0],404)
   self.assertEqual(req('/v1/chat/completions',body)[0],200)
   code,data=req('/v1/chat/completions',{**body,'stream':True});self.assertEqual(code,200);self.assertIn('data: [DONE]',data);self.assertIn('chat.completion.chunk',data)
  finally:http.shutdown();http.server_close()
if __name__=='__main__':unittest.main()
