import base64,io,json,sys,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'moderation'))
import server
from policy import CATEGORIES

def image():
 out=io.BytesIO();Image.new('RGB',(20,20),'blue').save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()
class Tests(unittest.TestCase):
 def test_images(self):
  data,_,_=server.normalize_image(image());self.assertEqual(Image.open(io.BytesIO(data)).size,(20,20))
  for bad in ['abc','data:image/png;base64,abc',base64.b64encode(b'not an image').decode()]:
   with self.assertRaises(ValueError):server.normalize_image(bad)
 def test_animation_rejected(self):
  out=io.BytesIO();Image.new('RGB',(10,10),'red').save(out,format='PNG',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')])
  with self.assertRaises(ValueError):server.normalize_image(base64.b64encode(out.getvalue()).decode())
 def test_upstream_validation(self):
  cats={c:False for c in CATEGORIES};cats['weapons']=True
  class Response(io.BytesIO):
   pass
  def response(payload):return Response(json.dumps(payload).encode())
  def payload(parsed):return {'done':True,'done_reason':'stop','response':json.dumps(parsed)}
  with patch('server.urllib.request.urlopen',return_value=response(payload({'categories':cats,'evidence':'A gun.'} ))):
   r=server.infer(b'a');self.assertEqual(r['flags'],['weapons']);self.assertTrue(r['review_required']);self.assertEqual(r['automated_decision'],'none')
  for p in [payload({'categories':{},'evidence':''}),{'done':True,'done_reason':'length','response':'{}'}]:
   with patch('server.urllib.request.urlopen',return_value=response(p)):
    with self.assertRaises(ValueError):server.infer(b'a')
 def test_api(self):
  gate=threading.Event()
  def inference(_):gate.wait(2);raise ValueError('upstream failed')
  jobs=server.Jobs(inference);http=server.Server(('127.0.0.1',0),'x'*40,jobs);threading.Thread(target=http.serve_forever,daemon=True).start()
  def request(path,body=None,key='x'*40,idempotency=None):
   headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
   if idempotency:headers['Idempotency-Key']=idempotency
   req=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
   try:
    with urllib.request.urlopen(req) as r:return r.status,json.load(r)
   except urllib.error.HTTPError as r:return r.code,json.load(r)
  try:
   self.assertEqual(request('/v1/moderation/health',key='bad')[0],401)
   self.assertEqual(request('/v1/moderation/jobs',{'image_url':'https://example.org'})[0],400)
   self.assertEqual(request('/v1/moderation/health')[0],200)
   status,a=request('/v1/moderation/jobs',{'image_base64':image()},idempotency='same');self.assertEqual(status,202)
   status,b=request('/v1/moderation/jobs',{'image_base64':image()},idempotency='same');self.assertEqual(a['id'],b['id'])
   gate.set()
   for _ in range(50):
    _,row=request(a['status_url'])
    if row['status']=='failed':break
    time.sleep(.01)
   self.assertEqual(row['status'],'failed');self.assertNotIn('result',row)
   self.assertEqual(request('/v1/moderation/jobs/missing')[0],404)
  finally:gate.set();http.shutdown();http.server_close()
 def test_queue_capacity_idempotency_and_expiry(self):
  import queue
  jobs=server.Jobs.__new__(server.Jobs);jobs.lock=threading.Lock();jobs.rows={};jobs.pending=queue.Queue(maxsize=3)
  a,error=jobs.submit(b'a','hash-a','norm','id-a');self.assertIsNone(error)
  self.assertEqual(jobs.submit(b'a','hash-a','norm','id-a')[0],a)
  self.assertEqual(jobs.submit(b'b','hash-b','norm','id-a')[1],'conflict')
  jobs.submit(b'b','b','b');jobs.submit(b'c','c','c')
  self.assertEqual(jobs.submit(b'd','d','d')[1],'busy')
  jobs.rows[a].update(status='completed',finished_at=time.time()-server.TTL-1)
  self.assertIsNone(jobs.read(a))
 def test_nullable_result_still_requires_review(self):
  payload={'done':True,'done_reason':'stop','response':json.dumps({'categories':{c:None for c in CATEGORIES},'evidence':'Uncertain.'})}
  with patch('server.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
   result=server.infer(b'a');self.assertEqual(result['signal'],'uncertain');self.assertEqual(result['flags'],[]);self.assertTrue(result['review_required'])
if __name__=='__main__':unittest.main()
