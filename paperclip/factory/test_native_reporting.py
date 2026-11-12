"""Native report data stays company scoped and failure cannot become empty success."""
import json
import subprocess
import types
import unittest
from unittest.mock import patch
import native_reporting as reader
C='11111111-1111-1111-1111-111111111111'
I='22222222-2222-2222-2222-222222222222'
class NativeReportingTests(unittest.TestCase):
 def setUp(self):
  patcher=patch.object(reader.os,"geteuid",return_value=0);patcher.start();self.addCleanup(patcher.stop)
 def body(self):return {'version':1,'read_only':True,'company':C,'tasks':[{'id':I,'companyId':C,'identifier':'NAR-1','title':'Fixture','status':'done','createdAt':'2026-11-12T00:00:00Z','updatedAt':'2026-11-12T00:00:00Z'}]}
 def test_wrong_company_duplicate_and_missing_proof_are_refused(self):
  for kind in ['scope','duplicate','proof','unbounded-field']:
   value=self.body()
   if kind=='scope':value['tasks'][0]['companyId']=I
   elif kind=='duplicate':value['tasks']*=2
   elif kind=='proof':value['read_only']=False
   else:value['tasks'][0]['sourceText']='private'
   with self.subTest(kind=kind),self.assertRaises(ValueError):reader.validate(value,C)
 def test_verified_empty_result_is_distinct_from_failure(self):
  value=self.body();value['tasks']=[]
  self.assertEqual(reader.validate(value,C),[])
  with patch.object(reader.subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stdout='',stderr='private diagnostic')):
   with self.assertRaisesRegex(RuntimeError,'^Native reporting (unavailable|image changed)$'):reader.read_tasks_direct({'company_id':C})
 def test_timeout_and_wrong_response_fail_without_raw_diagnostics(self):
  for behavior in [subprocess.TimeoutExpired('private',25),types.SimpleNamespace(returncode=0,stdout='{}',stderr='private')]:
   with self.subTest(behavior=type(behavior).__name__),patch.object(reader.subprocess,'run') as run:
    def invoke(command,**kwargs):
     if command[:2]==['docker','inspect']:return types.SimpleNamespace(returncode=0,stdout=json.loads((reader.ROOT/'native_reporting_contract.json').read_text())['image'],stderr='')
     if isinstance(behavior,Exception):raise behavior
     return behavior
    run.side_effect=invoke
    with self.assertRaises(RuntimeError) as caught:reader.read_tasks_direct({'company_id':C})
    self.assertNotIn('private',str(caught.exception))
 def test_reader_preserves_the_full_verified_company_snapshot(self):
  value=self.body()
  with patch.object(reader.subprocess,'run',side_effect=[types.SimpleNamespace(returncode=0,stdout=json.loads((reader.ROOT/'native_reporting_contract.json').read_text())['image'],stderr=''),types.SimpleNamespace(returncode=0,stdout=json.dumps(value),stderr='')]) as run:
   self.assertEqual(reader.read_tasks_direct({'company_id':C}),value['tasks'])
  self.assertEqual(json.loads(run.call_args.kwargs['input'])['company'],C)

class PeerTests(unittest.TestCase):
 def test_company_and_operating_identity_are_both_required(self):
  from native_reporting_service import authorize
  for uid,request in [(500,{'version':1,'company':C}),(42,{'version':1,'company':I}),(42,{'version':1,'company':C,'command':'anything'}),(42,{'version':2,'company':C})]:
   with self.subTest(uid=uid,request=request),self.assertRaises(PermissionError):authorize(uid,request,C,42)
  authorize(42,{'version':1,'company':C},C,42)
 def test_partial_transport_cannot_become_an_empty_result(self):
  import socket
  a,b=socket.socketpair()
  try:
   b.sendall(b'xx');b.shutdown(socket.SHUT_WR)
   with self.assertRaisesRegex(RuntimeError,'ended early'):reader.receive(a,4)
  finally:a.close();b.close()

if __name__=='__main__':unittest.main()
