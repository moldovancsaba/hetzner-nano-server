"""Socket-activated, peer-authenticated company read model; no selectable commands."""
import json
from pathlib import Path
import pwd
import socket
import struct
import sys
import uuid

import native_reporting


def authorize(peer_uid,request,company,factory_uid):
 if peer_uid not in {0,factory_uid}:raise PermissionError('Reporting peer refused')
 if set(request)!={'version','company'} or request['version']!=1 or request['company']!=company:raise PermissionError('Reporting scope refused')


def main():
 stream=socket.socket(fileno=0)
 peer_uid=struct.unpack('3i',stream.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
 factory_uid=pwd.getpwnam('narimato-factory').pw_uid
 if peer_uid not in {0,factory_uid}:return
 stream.settimeout(30)
 raw=bytearray()
 while not raw.endswith(b'\n'):
  chunk=stream.recv(1)
  if not chunk or len(raw)>=1024:raise ValueError('Reporting request incomplete')
  raw.extend(chunk)
 try:
  config=json.loads((Path(__file__).parent/'factory.json').read_text());company=str(uuid.UUID(config['company_id']))
  authorize(peer_uid,json.loads(raw),company,factory_uid)
  rows=native_reporting.read_tasks_direct(config,container='narimato-paperclip')
  reply={'ok':True,'snapshot':{'version':1,'read_only':True,'company':company,'tasks':rows}}
 except Exception:reply={'ok':False,'error':'native_reporting_unavailable'}
 body=json.dumps(reply,separators=(',',':')).encode()
 if len(body)>native_reporting.MAX_BYTES:body=b'{"ok":false,"error":"native_reporting_unavailable"}'
 stream.sendall(struct.pack('!I',len(body))+body)


if __name__=='__main__':main()
