"""The automatic_quality_gate.enabled switch stops every automatic write: publication and refresh already check it, and
quality_gate.reserve now refuses for the paths that have no human mode (program updates, engine intake and publish,
Padel intake). With the switch off no request is sent, no packet is stored and the gate decision stays unused."""
import unittest
from unittest.mock import Mock,patch
import engine_ops,padel,program_updates as programs,quality_gate as q,worker
import test_delivery,test_openclaw_alignment,test_operations

HOLD='Automatic quality hold:'
class GateSwitchTests(unittest.TestCase):
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def rows(self,table):
  with worker.database() as db:return db.execute('SELECT count(*) FROM '+table).fetchone()[0]
 def test_reserve_refuses_unless_the_switch_is_exactly_true(self):
  q.record(worker.database,'p','program_update',{'valid':True})
  for config in [{},{'automatic_quality_gate':{}},{'automatic_quality_gate':{'enabled':False}},{'automatic_quality_gate':{'enabled':'yes'}},{'automatic_quality_gate':{'enabled':1}}]:
   with worker.database() as db,self.assertRaises(ValueError) as caught:q.reserve(db,'p',config)
   self.assertTrue(str(caught.exception).startswith(HOLD),str(caught.exception))
  with worker.database() as db:self.assertIsNone(db.execute('SELECT submitted_at FROM automatic_decisions WHERE packet_hash=?',('p',)).fetchone()[0])
 def test_a_refused_reservation_keeps_the_decision_for_when_the_switch_is_back_on(self):
  q.record(worker.database,'p','program_update',{'valid':True})
  with worker.database() as db,self.assertRaises(ValueError):q.reserve(db,'p',{'automatic_quality_gate':{'enabled':False}})
  with worker.database() as db:q.reserve(db,'p',{'automatic_quality_gate':{'enabled':True}})
  with worker.database() as db:self.assertIsNotNone(db.execute('SELECT submitted_at FROM automatic_decisions WHERE packet_hash=?',('p',)).fetchone()[0])
 def test_the_refusal_message_is_routed_by_the_worker_as_a_hold(self):
  # worker.py treats messages with this prefix as a policy hold: a comment and a blocked hand-off, not a failure loop.
  self.assertTrue(HOLD.startswith('Automatic quality hold'))
  import inspect;self.assertIn("'"+HOLD+"'",inspect.getsource(worker))
 def test_engine_writes_stop_when_the_switch_is_off(self):
  client=Mock();body={'id':'card-1'}
  config={'company_id':'company','engine_clients':{'padel-africa':True},'automatic_quality_gate':{'enabled':False}}
  with patch('engine_ops.execute_guard'),self.assertRaises(ValueError) as caught:engine_ops.write_once({'id':'i'},Mock(),config,worker.database,{},client,'padel-africa','intake',body,{'p':1})
  self.assertTrue(str(caught.exception).startswith(HOLD));client.call.assert_not_called();self.assertEqual(self.rows('engine_packets'),0)
  config['automatic_quality_gate']['enabled']=True
  client.call.return_value={'cardId':'card-1','created':True}
  with patch('engine_ops.execute_guard'):receipt,state=engine_ops.write_once({'id':'i'},Mock(),config,worker.database,{},client,'padel-africa','intake',body,{'p':1})
  self.assertEqual(state,'accepted');client.call.assert_called_once()
 def test_program_updates_stop_when_the_switch_is_off(self):
  h=test_openclaw_alignment.AlignmentTests();h.setUp()
  try:
   i,b,w,c,writer,public,current=h.program_scenario();config={**h.config,'automatic_quality_gate':{'enabled':False,'daily_write_limit':20}}
   with patch('program_updates.catalog.Catalog',return_value=public),self.assertRaises(ValueError) as caught:programs.run(i,b,config,w,worker.database,{'run_id':'r','agent_id':'pub'},c,writer)
   self.assertTrue(str(caught.exception).startswith(HOLD));writer.apply.assert_not_called();self.assertEqual(self.rows('program_packets'),0)
  finally:h.tearDown()
 def test_padel_intake_stops_when_the_switch_is_off(self):
  h=test_delivery.DeliveryTests();h.setUp()
  try:
   i,b,w,c=h.padel_scenario()
   with self.assertRaises(ValueError) as caught:padel.run(i,b,{'company_id':'company','automatic_quality_gate':{'enabled':False}},w,worker.database,{'run_id':'run','agent_id':'support'},c)
   self.assertTrue(str(caught.exception).startswith(HOLD));c.call.assert_not_called();self.assertEqual(self.rows('padel_packets'),0)
  finally:h.tearDown()
if __name__=='__main__':unittest.main()
