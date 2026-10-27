#!/usr/bin/env python3
"""Submit one local image and poll review signals; credentials never printed."""
import argparse,base64,json,os,secrets,time,urllib.request,urllib.error
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('image',type=Path);args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
key=os.environ.get('CAMERA_MODERATION_API_KEY')
if not key:key=json.loads((root/'private/api-keys.json').read_text())['camera']
base=os.environ.get('CAMERA_MODERATION_BASE_URL','https://chatbotapi.haho.ai/v1/moderation').rstrip('/')
def request(path,payload=None,idempotency=None):
 headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Request-Purpose':'test'}
 if idempotency:headers['Idempotency-Key']=idempotency
 req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
 with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
raw=args.image.read_bytes()
if len(raw)>4*1024*1024:raise SystemExit('Resize the image first: maximum 4 MiB and 16 megapixels.')
try:
 job=request('/jobs',{'image_base64':base64.b64encode(raw).decode()},secrets.token_urlsafe(18))
 for _ in range(150):
  row=request('/jobs/'+job['id'])
  if row['status'] in {'completed','failed'}:
   print(json.dumps(row,indent=2));raise SystemExit(0 if row['status']=='completed' else 1)
  time.sleep(2)
 raise SystemExit('Polling deadline reached; keep review pending and poll the same job later.')
except urllib.error.HTTPError as error:
 raise SystemExit('Service returned HTTP '+str(error.code)+'; keep human review pending.') from None
