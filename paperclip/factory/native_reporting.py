"""Company-scoped native issue read model; no operational read reconciliation."""
import json
import socket
import struct
import os
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parent
MAX_BYTES=33554432
FIELDS={'id','companyId','identifier','title','description','status','parentId','projectId','assigneeAgentId','assigneeUserId','createdAt','updatedAt','completedAt','blockedTransitionAt'}


def validate(value,company):
 if value.get('version')!=1 or value.get('read_only') is not True or value.get('company')!=company:raise ValueError('Native report scope or read-only proof missing')
 rows=value.get('tasks')
 if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Native report rows invalid')
 seen=set()
 for row in rows:
  if not isinstance(row,dict) or set(row)-FIELDS or row.get('companyId')!=company:raise ValueError('Native report company scope invalid')
  identity=str(uuid.UUID(row['id']))
  if identity in seen:raise ValueError('Native report repeats a task')
  seen.add(identity)
  if not all(isinstance(row.get(k),str) for k in ['title','identifier','status','createdAt','updatedAt']):raise ValueError('Native report task fields incomplete')
  if row.get('description') is not None and not isinstance(row['description'],str):raise ValueError('Native report description invalid')
 return rows


def read_tasks_direct(config,container=None):
 company=str(uuid.UUID(config['company_id']))
 if os.geteuid()!=0:raise PermissionError('Direct native reporting requires the local reporting bridge')
 container=container or os.environ.get('FACTORY_NATIVE_CONTAINER','narimato-paperclip')
 if container not in {'narimato-paperclip','paperclip-recovery-drill'}:raise ValueError('Native reporting container not allowed')
 script=(ROOT/'native_reporting.mjs').read_text()
 contract=json.loads((ROOT/'native_reporting_contract.json').read_text())
 payload=json.dumps({'company':company,'contract':contract})
 # Only the company and pinned contract enter stdin; credentials stay in the container.
 command=['docker','exec','-i','-u','node','-w','/app',container,'node','--max-old-space-size=512','--import','./server/node_modules/tsx/dist/loader.mjs','--input-type=module','-e',script]
 try:
  image=subprocess.run(['docker','inspect',container,'--format','{{.Image}}'],capture_output=True,text=True,timeout=5)
  if image.returncode or image.stdout.strip()!=contract['image']:raise RuntimeError('Native reporting image changed')
  result=subprocess.run(command,input=payload,capture_output=True,text=True,timeout=180 if container=='paperclip-recovery-drill' else 25)
 except subprocess.TimeoutExpired:raise RuntimeError('Native reporting timed out') from None
 if result.returncode or len(result.stdout.encode())>MAX_BYTES:raise RuntimeError('Native reporting unavailable')
 try:return validate(json.loads(result.stdout),company)
 except (KeyError,TypeError,ValueError):raise RuntimeError('Native reporting response invalid') from None


def receive(stream,size):
 data=bytearray()
 while len(data)<size:
  chunk=stream.recv(size-len(data))
  if not chunk:raise RuntimeError('Native reporting connection ended early')
  data.extend(chunk)
 return bytes(data)


def read_tasks(config):
 if os.geteuid()==0:return read_tasks_direct(config)
 company=str(uuid.UUID(config['company_id']))
 try:
  with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as stream:
   stream.settimeout(25);stream.connect('/run/narimato-reporting/read.sock')
   stream.sendall(json.dumps({'version':1,'company':company}).encode()+b'\n')
   size=struct.unpack('!I',receive(stream,4))[0]
   if not 0<size<=MAX_BYTES:raise ValueError('Native reporting response too large')
   value=json.loads(receive(stream,size))
   if value.get('ok') is not True:raise RuntimeError('Native reporting unavailable')
   return validate(value['snapshot'],company)
 except (OSError,ValueError,KeyError,TypeError) as error:raise RuntimeError('Native reporting connection unavailable') from None
