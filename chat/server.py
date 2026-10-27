import hashlib,hmac,json,os,secrets,threading,time,urllib.request,urllib.error
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs
ROOT=Path(__file__).parent
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
   if not 0<n<=16384:return self.send(413,'Request too large')
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
   data=json.loads(raw);messages=data['messages']
   if not isinstance(messages,list) or not messages or len(messages)>7:raise ValueError()
   for m in messages:
    if not isinstance(m,dict) or m.get('role') not in ['user','assistant'] or not isinstance(m.get('content'),str) or len(m['content'])>1800:raise ValueError()
   if messages[-1]['role']!='user':raise ValueError()
   # Bound recent context for this small model; reserve space for the reply.
   recent=[];size=0
   for m in reversed(messages):
    if size+len(m['content'])>2600:break
    recent.insert(0,{'role':m['role'],'content':m['content']});size+=len(m['content'])
   while recent and recent[0]['role']=='assistant':recent.pop(0)
  except Exception:return self.send(400,'{"error":"Please send a shorter message or start a new chat."}','application/json')
  if not WORKER.acquire(blocking=False):return self.send(429,'{"error":"Another reply is in progress. Try again shortly."}','application/json')
  try:
   payload={'model':'qwen3:1.7b','messages':[{'role':'system','content':'You are Pandora, a helpful conversational assistant. Answer clearly and briefly. Say when you are unsure.'}]+recent,'reasoning_effort':'none','stream':False,'max_tokens':256,'temperature':0.4}
   req=urllib.request.Request('http://127.0.0.1:8090/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+GATEWAY_KEY})
   with urllib.request.urlopen(req,timeout=110) as r:reply=json.load(r)['choices'][0]['message']['content']
   self.send(200,json.dumps({'reply':reply}), 'application/json')
  except Exception:self.send(503,'{"error":"The chat is unavailable right now. Please try again shortly."}','application/json')
  finally:WORKER.release()
ThreadingHTTPServer(('127.0.0.1',8088),Handler).serve_forever()
