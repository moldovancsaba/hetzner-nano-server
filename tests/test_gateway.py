"""Tests for the gateway: Scheduler FIFO with one active job, tenant isolation, circuit on upstream timeout,
capacity, idempotency, expiry and delete; Runner model switching; explicit versus auto model choice;
text limits; HTTP permissions, async jobs and SSE.

Model names come from config/model-policy.json, so a new ranked default needs no edit here.
Dependencies: Pillow (imported by gateway.server). The text-job HTTP test also needs the `tokenizers` package and
the hash-pinned Granite tokenizer file (GRANITE_TOKENIZER_PATH, default /opt/narimato-gateway/tokenizers/granite4-h-1b.json,
see gateway/long_context.py) because a ClassScout text job runs on the 8K profile and is token-counted; without
them that one test is skipped and says why. The permission and discovery HTTP test does not need the tokenizer."""
import base64,io,json,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from gateway.server import Scheduler,Server,Runner,ROUTES,UpstreamUncertain,text_input,POLICY_PATH
from gateway.catalog import ModelCatalog,SelectionError
from gateway.long_context import tokenizer

def catalog():
 policy=json.loads(POLICY_PATH.read_text())
 return ModelCatalog(POLICY_PATH,lambda:{"models":[{"name":name,"digest":entry["tested_digest"]} for name,entry in policy["models"].items()]})

POLICY=json.loads(POLICY_PATH.read_text())
TEXT_DEFAULT=POLICY['defaults']['text_chat']
# Any other model ranked for text_chat is a valid explicit choice; take the best one that is not the default.
TEXT_ALTERNATIVE=min((name for name,entry in POLICY['models'].items() if 'text_chat' in entry['tasks'] and name!=TEXT_DEFAULT),key=lambda name:POLICY['models'][name]['tasks']['text_chat']['rank'])
def tokenizer_ready():
 try:tokenizer();return True
 except Exception:return False

def completion():
 return {'id':'test','created':1,'model':TEXT_DEFAULT,'object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':'READY'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}

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
 def test_delete_isolated_cancels_queued_and_purges_result(self):
  gate=threading.Event();begun=threading.Event();seen=[]
  def run(task,payload,model):
   seen.append(payload);begun.set();gate.wait(2);return completion(),{}
  s=Scheduler(run);a,_=s.submit('classscout','text_chat',{'first':True});begun.wait(1);b,_=s.submit('camera','image_recognition',b'image')
  self.assertEqual(s.delete('habigoal',a),'not_found');self.assertEqual(s.delete('classscout',a),'running')
  self.assertEqual(s.delete('camera',b),'deleted');self.assertIsNone(s.read('camera',b));gate.set()
  self.assertEqual(wait(s,'classscout',a)['status'],'completed');self.assertEqual(s.delete('classscout',a),'deleted');self.assertIsNone(s.read('classscout',a));self.assertEqual(len(seen),1)
 def test_deleted_last_result_has_no_idle_worker_reference(self):
  import gc,weakref
  references=[]
  class Content(dict):pass
  def run(*args):
   value=Content(answer='test-only');references.append(weakref.ref(value));return value,{}
  s=Scheduler(run);job,_=s.submit('classscout','text_chat',{})
  with s.cv:event=s.rows[job]['_event']
  event.wait(2)
  for _ in range(100):
   if s.status('classscout')['active_task'] is None:break
   time.sleep(.005)
  self.assertEqual(s.delete('classscout',job),'deleted');gc.collect();self.assertIsNone(references[0]())
 def test_terminal_expiry(self):
  s=Scheduler(lambda *args:({},{}));job,_=s.submit('classscout','text_chat',{});wait(s,'classscout',job)
  with s.cv:s.rows[job]['finished_at']-=301
  self.assertIsNone(s.read('classscout',job))
 def test_switch_unloads_before_inference(self):
  calls=[]
  def native(path,body=None,timeout=None):
   calls.append((path,body))
   if path=='/api/ps':return {'models':[{'name':'old-model'}]} if len(calls)==1 else {'models':[]}
   if path=='/api/generate':return {'done':True}
   return completion()
  with patch('gateway.server.native',side_effect=native):
   result,switch=Runner()('text_chat',{},TEXT_DEFAULT)
  self.assertEqual([x[0] for x in calls],['/api/ps','/api/generate','/api/ps','/v1/chat/completions']);self.assertEqual(switch['unloaded_models'],['old-model'])
 def test_explicit_model_is_real_choice(self):
  selected=catalog().select('text_chat',TEXT_ALTERNATIVE)
  self.assertEqual(selected['model'],TEXT_ALTERNATIVE);self.assertEqual(selected['selection'],'explicit')
  self.assertEqual(catalog().select('text_chat','auto')['model'],TEXT_DEFAULT)
 def test_text_limits(self):
  for data in [{'messages':[{'role':'user','content':[{'type':'image_url'}]}]}, {'messages':[]}, {'messages':[{'role':'user','content':'Hi'}],'model':'giant:70b'}, {'messages':[{'role':'user','content':'Hi'}],'max_tokens':513}]:
   with self.assertRaises(ValueError):text_input(data,TEXT_DEFAULT)
 def client(self):
  s=Scheduler(lambda *args:(completion(),{'unloaded_models':[]}))
  http=Server(('127.0.0.1',0),{'camera':'c'*40,'classscout':'t'*40,'habigoal':'h'*40,'pandora':'p'*40},s,catalog=catalog());threading.Thread(target=http.serve_forever,daemon=True).start()
  self.addCleanup(http.server_close);self.addCleanup(http.shutdown)
  def req(path,body=None,key='t'*40,method=None):
   request=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None,method=method)
   try:
    with urllib.request.urlopen(request) as r:return r.status,r.read().decode()
   except urllib.error.HTTPError as r:return r.code,r.read().decode()
  return req
 def test_http_permissions_and_discovery(self):
  req=self.client()
  self.assertEqual(req('/v1/queue',key='wrong')[0],401)
  self.assertEqual(req('/v1/models',key='c'*40)[0],200)
  self.assertEqual(req('/v1/moderation/health')[0],401)
  self.assertEqual(req('/v1/jobs',{'task':'image_recognition','input':{'image_base64':'a'}})[0],403)
  self.assertEqual(json.loads(req('/v1/job-types',key='c'*40)[1])['job_types'].keys(),{'image_recognition','image_moderation'})
 def test_discovery_matches_what_verify_gateway_expects(self):
  # scripts/verify_gateway.py derives its expectations from the same files; this keeps that derivation honest.
  import sys;sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
  import verify_gateway;routes,defaults,policy_id=verify_gateway.expectations();req=self.client()
  for tenant,key in [('classscout','t'*40),('habigoal','h'*40),('camera','c'*40),('pandora','p'*40)]:
   found=json.loads(req('/v1/job-types',key=key)[1])
   self.assertEqual(set(found['job_types']),verify_gateway.tasks_for(routes,tenant),tenant);self.assertEqual(found['policy_id'],policy_id)
   self.assertEqual({task:spec['model'] for task,spec in found['job_types'].items()},{task:defaults[task] for task in found['job_types']},tenant)
 @unittest.skipUnless(tokenizer_ready(),'the verified Granite tokenizer is not available (see the module docstring); text jobs cannot be admitted without it')
 def test_http_async_chat_and_sse(self):
  req=self.client();body={'messages':[{'role':'user','content':'Hi'}]}
  code,data=req('/v1/jobs',{'task':'text_chat','input':body});self.assertEqual(code,202);job=json.loads(data)['id'];self.assertEqual(req('/v1/jobs/'+job,key='c'*40)[0],404)
  self.assertEqual(req('/v1/chat/completions',body)[0],200)
  code,data=req('/v1/chat/completions',{**body,'stream':True});self.assertEqual(code,200);self.assertIn('data: [DONE]',data);self.assertIn('chat.completion.chunk',data)
  self.assertEqual(req('/v1/jobs/'+job,method='DELETE')[0],200);self.assertEqual(req('/v1/jobs/'+job)[0],404)
if __name__=='__main__':unittest.main()
