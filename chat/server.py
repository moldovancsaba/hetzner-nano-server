"""Pandora personal-chat HTTP service on 127.0.0.1:8088, path /chat/. A correct password (SHA-256 compared with CHAT_PASSWORD_HASH) sets a session cookie that gates the page and API;
POSTs must carry the expected Origin. Each chat request becomes a text_chat job on the local gateway (key from GATEWAY_PANDORA_KEY), polled until done, then deleted.
Only one reply runs at a time; others get 429."""
import hashlib,hmac,json,os,secrets,sys,threading,time,urllib.request,urllib.error
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs
ROOT=Path(__file__).parent
sys.path.insert(0, '/opt/narimato-gateway')
sys.path.insert(0, str(ROOT))
from context import prepare
GATEWAY_KEY=os.environ['GATEWAY_PANDORA_KEY']
PASSWORD_HASH=os.environ['CHAT_PASSWORD_HASH']
SESSION=secrets.token_urlsafe(48)
WORKER=threading.BoundedSemaphore(1)
ORIGIN='https://chatbotapi.haho.ai'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def send(self,status,body,kind='text/html; charset=utf-8',headers=None):
  body=body.encode() if isinstance(body,str) else body
  self.send_response(status)
  for k,v in {'Content-Type':kind,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",**(headers or {})}.items(): self.send_header(k,v)
  self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def authorized(self):
  try:
   c=SimpleCookie(self.headers.get('Cookie',''));v=c.get('pandora_access');return bool(v and hmac.compare_digest(v.value,SESSION))
  except Exception:return False
 def do_GET(self):
  if self.path not in ['/chat/','/chat']:return self.send(404,'Not found')
  self.send(200,(ROOT/('index.html' if self.authorized() else 'login.html')).read_bytes())
 def do_POST(self):
  if self.headers.get('Origin')!=ORIGIN:return self.send(403,'Forbidden')
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=256*1024:return self.send(413,'Request too large')
   raw=self.rfile.read(n)
  except Exception:return self.send(400,'Invalid request')
  if self.path=='/chat/login':
   given=parse_qs(raw.decode()).get('secret',[''])[0].strip()
   if hmac.compare_digest(hashlib.sha256(given.encode()).hexdigest(),PASSWORD_HASH):
    return self.send(303,'',headers={'Location':'/chat/','Set-Cookie':'pandora_access='+SESSION+'; Path=/chat; Max-Age=2592000; Secure; HttpOnly; SameSite=Strict'})
   time.sleep(.6)
   return self.send(401,(ROOT/'login.html').read_text().replace('</form>','<p class="note" role="alert">That is not the secret.</p></form>'))
  if self.path=='/chat/logout':return self.send(303,'',headers={'Location':'/chat/','Set-Cookie':'pandora_access=; Path=/chat; Max-Age=0; Secure; HttpOnly; SameSite=Strict'})
  if self.path!='/chat/api':return self.send(404,'Not found')
  if not self.authorized():return self.send(401,'{"error":"Please unlock Pandora again."}','application/json')
  try:
   data=json.loads(raw)
   payload,kept,trimmed,input_tokens=prepare(data['messages'])
   purpose=self.headers.get('X-Request-Purpose','production')
   if purpose not in ['production','test']:raise ValueError('Invalid request purpose')
  except (ValueError,KeyError,TypeError) as error:
   return self.send(400,json.dumps({'error':str(error) if isinstance(error,ValueError) else 'Invalid conversation.'}),'application/json')
  if not WORKER.acquire(blocking=False):return self.send(429,'{"error":"Another reply is in progress. Try again shortly."}','application/json')
  try:
   def gateway(path,body=None,method=None):
    request=urllib.request.Request('http://127.0.0.1:8090'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','Authorization':'Bearer '+GATEWAY_KEY,'X-Request-Purpose':purpose},method=method)
    with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
   submitted=gateway('/v1/jobs',{'task':'text_chat','input':payload})
   job_id=submitted['id'];deadline=time.monotonic()+900
   while time.monotonic()<deadline:
    row=gateway('/v1/jobs/'+job_id)
    if row['status']=='completed':
     completion=row['result'];break
    if row['status']=='failed':raise RuntimeError('Generation did not complete')
    time.sleep(.5)
   else:raise TimeoutError('Chat job deadline exceeded')
   reply=completion['choices'][0]['message']['content']
   self.send(200,json.dumps({'reply':reply,'model':completion.get('model'),'context_tokens':row['model_profile']['num_ctx'],'kept_messages':kept,'history_trimmed':trimmed,'usage':completion.get('usage')}), 'application/json')
   try:gateway('/v1/jobs/'+job_id,method='DELETE')
   except Exception:pass
  except Exception:self.send(503,'{"error":"The chat is unavailable right now. Please try again shortly."}','application/json')
  finally:WORKER.release()
ThreadingHTTPServer(('127.0.0.1',8088),Handler).serve_forever()
