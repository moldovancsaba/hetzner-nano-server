"""Live access checks. Reads the existing private password without displaying it."""
import json, subprocess, urllib.parse, socket, ssl, base64, os
from pathlib import Path
BASE='https://paperclip.haho.ai'
secret=next(line.split(':',1)[1].strip() for line in (Path(__file__).resolve().parents[1]/'private/chat-access.txt').read_text().splitlines() if line.startswith('Secret:'))
cookie=None
results=[]
def call(path, method='GET', data=None, origin=None, extra=None):
    args=['curl','--silent','--show-error','--max-time','30','--resolve','paperclip.haho.ai:443:2.29.113.132','--request',method,'--dump-header','-']
    if cookie:args+=['--header','Cookie: '+cookie]
    if origin:args+=['--header','Origin: '+origin]
    for h in extra or []:args+=['--header',h]
    if data is not None:args+=['--data-binary','@-']
    args+=[BASE+path]
    raw=subprocess.check_output(args,input=data if data is not None else b'')
    head,body=raw.split(b'\r\n\r\n',1)
    lines=head.decode().splitlines()
    status=int(lines[0].split()[1]);headers={k.lower():v.strip() for k,v in (line.split(':',1) for line in lines[1:] if ':' in line)}
    return status,headers,body

def expect(label,response,status):
    assert response[0]==status,(label,response[0],status,response[2][:200])
    results.append({'check':label,'status':status,'passed':True})

expect('locked home redirects',call('/'),303)
expect('login screen',call('/_access/login'),200)
expect('API locked',call('/api/companies'),401)
expect('spoofed forwarded headers cannot bypass gate',call('/api/companies',extra=['X-Forwarded-Uri: /','X-Forwarded-Method: GET','X-Real-IP: 127.0.0.1']),401)
expect('login rejects missing origin',call('/_access/login','POST',b'secret=wrong'),403)
expect('wrong password rejected',call('/_access/login','POST',b'secret=wrong',BASE),401)
response=call('/_access/login','POST',urllib.parse.urlencode({'secret':secret}).encode(),BASE)
expect('Pandora password accepted',response,303)
set_cookie=response[1]['set-cookie']
assert all(x in set_cookie for x in ['Secure','HttpOnly','SameSite=Strict','Path=/'])
cookie=set_cookie.split(';',1)[0]
expect('unlocked UI',call('/'),200)
health=call('/api/health');expect('application health',health,200)
expect('board company access',call('/api/companies'),200)
expect('cross-origin mutation blocked',call('/api/companies','POST',b'{}','https://example.com'),403)
expect('mutation without origin blocked',call('/api/companies','POST',b'{}'),403)
companies=json.loads(call('/api/companies')[2])
assert any(c['name']=='Narimato' for c in companies)
company_id=next(c['id'] for c in companies if c['name']=='Narimato')
for label, ws_cookie, expected in [('live updates connect',cookie,101),('locked live updates blocked','',401)]:
    with socket.create_connection(('2.29.113.132',443),timeout=15) as connection:
        with ssl.create_default_context().wrap_socket(connection,server_hostname='paperclip.haho.ai') as stream:
            key=base64.b64encode(os.urandom(16)).decode()
            request=(f'GET /api/companies/{company_id}/events/ws HTTP/1.1\r\nHost: paperclip.haho.ai\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\nOrigin: {BASE}\r\nCookie: {ws_cookie}\r\n\r\n')
            stream.sendall(request.encode())
            status=int(stream.recv(4096).split(b'\r\n',1)[0].split()[1])
            assert status==expected,(label,status)
            results.append({'check':label,'status':status,'passed':True})
expect('logout',call('/_access/logout','POST',b'x=1',BASE),303)
cookie='__Host-paperclip_access=tampered'
expect('tampered session rejected',call('/api/companies'),401)
print(json.dumps({'checks':results,'health':json.loads(health[2])},indent=2))
