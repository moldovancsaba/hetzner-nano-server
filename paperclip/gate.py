"""Password-only front door. Caddy checks every request, including WebSocket handshakes."""
import asyncio, collections, hashlib, hmac, os, secrets, time
from pathlib import Path
from aiohttp import web

ORIGIN = 'https://paperclip.haho.ai'
PASSWORD_HASH = os.environ['ACCESS_PASSWORD_HASH']
SIGNING_KEY = os.environ['ACCESS_SIGNING_KEY'].encode()
COOKIE = '__Host-paperclip_access'
PAGE = Path(__file__).with_name('login.html').read_text()
ATTEMPTS = collections.OrderedDict()
TTL = 30 * 86400

def valid(request):
    try:
        value = request.cookies.get(COOKIE, '')
        expiry, nonce, signature = value.split('.')
        payload = expiry + '.' + nonce
        return int(expiry) > time.time() and hmac.compare_digest(signature, hmac.new(SIGNING_KEY, payload.encode(), hashlib.sha256).hexdigest())
    except (ValueError, TypeError):
        return False

@web.middleware
async def headers(request, handler):
    response = await handler(request)
    response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin'})
    if response.content_type == 'text/html':
        response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

async def login(request):
    if request.method == 'GET':
        return web.Response(text=PAGE, content_type='text/html')
    if request.headers.get('Origin') != ORIGIN:
        return web.Response(status=403, text='Forbidden')
    ip = request.headers.get('X-Real-IP', request.remote)
    now = time.monotonic()
    attempts = [t for t in ATTEMPTS.pop(ip, []) if now-t < 900]
    ATTEMPTS[ip] = attempts
    while len(ATTEMPTS) > 4096:
        ATTEMPTS.popitem(last=False)
    if len(attempts) >= 10:
        return web.Response(status=429, text='Too many attempts. Please try again in 15 minutes.', headers={'Retry-After':'900'})
    attempts.append(now)
    data = await request.post()
    password = str(data.get('secret', '')).strip()
    if not hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), PASSWORD_HASH):
        await asyncio.sleep(.6)
        return web.Response(status=401, text=PAGE.replace('</form>', '<p class="note" role="alert">That is not the secret.</p></form>'), content_type='text/html')
    ATTEMPTS.pop(ip, None)
    payload = str(int(time.time()) + TTL) + '.' + secrets.token_hex(24)
    token = payload + '.' + hmac.new(SIGNING_KEY, payload.encode(), hashlib.sha256).hexdigest()
    response = web.Response(status=303, headers={'Location':'/'})
    response.set_cookie(COOKIE, token, max_age=TTL, secure=True, httponly=True, samesite='Strict', path='/')
    return response

async def check(request):
    if not valid(request):
        uri = request.headers.get('X-Forwarded-Uri', '/')
        if uri.startswith(('/api', '/mcp')) or request.headers.get('Upgrade', '').lower() == 'websocket':
            return web.json_response({'error':'Unlock Paperclip first.'}, status=401)
        return web.Response(status=303, headers={'Location':'/_access/login'})
    method = request.headers.get('X-Forwarded-Method', 'GET').upper()
    origin = request.headers.get('Origin')
    if (origin and origin != ORIGIN) or (method not in {'GET','HEAD','OPTIONS'} and origin != ORIGIN):
        return web.Response(status=403, text='Forbidden origin')
    return web.Response(status=204)

async def logout(request):
    if request.headers.get('Origin') != ORIGIN:
        return web.Response(status=403, text='Forbidden')
    response = web.Response(status=303, headers={'Location':'/_access/login'})
    response.del_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='Strict')
    return response

app = web.Application(middlewares=[headers], client_max_size=4096)
app.router.add_get('/_access/login', login)
app.router.add_post('/_access/login', login)
app.router.add_get('/_access/check', check)
app.router.add_post('/_access/logout', logout)
web.run_app(app, host='127.0.0.1', port=8088, access_log=None, print=None)
