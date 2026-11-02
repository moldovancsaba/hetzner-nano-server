"""Factory exchange hooks preserve transaction ownership and original delivery requests."""
import contextlib
import hashlib
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import source_exchange as hooks


class HookTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'factory.sqlite3'
  self.settings={'offers_enabled':True,'policy_revision':'test-policy','projects':{'project':{'application':'classscout','client':'NYC'}}}
  self.page={'url':'https://fixture.example/program','text':'Fixture Studio','sha256':hashlib.sha256(b'Fixture Studio').hexdigest(),'fetched_at':time.time()}
  with self.database() as db:hooks.modules().initialize(db,create=True)
 @contextlib.contextmanager
 def database(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def test_disabled_hooks_do_not_touch_database_or_transport(self):
  with patch.object(hooks,'transport',side_effect=AssertionError('unexpected network')):
   self.assertEqual(hooks.coordinate(None,{},None,{}),{'state':'disabled'})
   self.assertIsNone(hooks.save_offer(None,{},None,None,None))
 def test_offer_is_part_of_the_callers_transaction(self):
  with self.database() as db:hooks.modules().initialize(db)
  with self.assertRaises(RuntimeError):
   with self.database() as db:
    hooks.save_offer(db,{'source_exchange':self.settings},{'id':'task','projectId':'project'},self.page,[])
    raise RuntimeError('injected evidence rollback')
  with self.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM exchange_source_outbox').fetchone()[0],0)
 def test_lost_offer_response_retries_original_bytes_and_operation(self):
  with self.database() as db:hooks.save_offer(db,{'source_exchange':self.settings},{'id':'task','projectId':'project'},self.page,[])
  seen=[]
  def send(settings,method,route,body,operation):
   seen.append((method,route,body,operation))
   if len(seen)==1:raise TimeoutError('lost response')
   return {'operation_id':operation,'state':'broker_saved'}
  with patch.object(hooks,'transport',side_effect=send):
   hooks.sync_offers(self.database,self.settings)
   with self.database() as db:db.execute('UPDATE exchange_source_outbox SET next_at=0')
   self.assertEqual(hooks.sync_offers(self.database,self.settings)['sent'],1)
  self.assertEqual(seen[0],seen[1])
 def test_invalid_receipt_retains_offer_and_dashboard_requires_commissioning(self):
  with self.database() as db:hooks.save_offer(db,{'source_exchange':self.settings},{'id':'task','projectId':'project'},self.page,[])
  with patch.object(hooks,'transport',return_value={'operation_id':'wrong','state':'broker_saved'}):hooks.sync_offers(self.database,self.settings)
  with self.database() as db:self.assertEqual(db.execute('SELECT state FROM exchange_source_outbox').fetchone()[0],'pending')
  with self.assertRaises(ValueError):hooks.dashboard_snapshot({})
 def test_event_claim_and_ack_fit_the_same_native_turn_after_a_long_poll_interval(self):
  import uuid
  from exchange.store import Store
  from exchange.contract import encode,iso
  scope={'application':'classscout','client':'NYC'};clock=[time.time()]
  broker=Store(Path(self.tmp.name)/'broker.sqlite3',clock=lambda:clock[0],initialize=True)
  inbox=str(uuid.uuid4());consumer={'id':'factory','clients':[scope],'scopes':['events:claim','status:read'],'inbox_ids':{'events':inbox}}
  producer={'id':'mac','clients':[scope],'scopes':['events:write']}
  event={'schema_version':'1.1','event_id':str(uuid.uuid4()),'scope':scope,'occurred_at':iso(clock[0]),'job_run_ref':'isolated-test','evaluation_id':str(uuid.uuid4()),'revision':1,'previous_event_id':None,'payload':{'event_type':'gap_report','candidate_ref':'candidate-ref','gap_fields':['address'],'evidence_fingerprint':'a'*64,'checker_version':'fixture','reason_code':'missing_address','source_url':'https://fixture.example/program'}}
  broker.mutation(producer,str(uuid.uuid4()),'/events',encode(event))
  def transport(settings,method,route,body=None,operation=None):
   if method=='GET':return broker.status(consumer)
   return json.loads(broker.mutation(consumer,operation,route,body)[1])
  settings={**self.settings,'events_enabled':True,'event_scope':scope,'event_inbox_id':inbox}
  with patch.object(hooks,'transport',side_effect=transport):
   hooks.event_turn(self.database,settings,limit=2)
   with broker.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM deliveries').fetchone()[0],0)
   clock[0]+=600
   with patch.object(hooks.time,'time',return_value=clock[0]):hooks.event_turn(self.database,settings,limit=2)
  with broker.connection() as db:self.assertIsNotNone(db.execute('SELECT acked FROM deliveries').fetchone()[0])
  with self.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM exchange_projection').fetchone()[0],1)

 def test_native_gap_lost_response_replays_exact_intent_and_checks_receipt(self):
  import uuid
  module=hooks.modules();scope={'application':'classscout','client':'NYC'}
  event={'schema_version':'1.1','event_id':str(uuid.uuid4()),'scope':scope,'occurred_at':'2026-11-02T12:00:00Z','job_run_ref':'fixture','evaluation_id':str(uuid.uuid4()),'revision':1,'previous_event_id':None,'payload':{'event_type':'gap_report','candidate_ref':'candidate-ref','gap_fields':['address'],'evidence_fingerprint':'a'*64,'checker_version':'fixture','reason_code':'missing_address','source_url':'https://fixture.example/program'}}
  with self.database() as db:module.project(db,event);module.gap_intent(db,event)
  seen=[]
  class Board:
   def call(self,route,body):
    seen.append(json.dumps(body,sort_keys=True))
    if len(seen)==1:raise TimeoutError('lost committed response')
    return {**body,'id':'native-task','companyId':'company'}
  settings={**self.settings,'gap_tasks_enabled':True};config={'company_id':'company','agents':{'researcher':{'role':'research'}}}
  self.assertEqual(hooks.deliver_gaps(self.database,settings,Board(),config)['delivered'],0)
  with self.database() as db:db.execute('UPDATE exchange_native_intents SET next_at=0')
  self.assertEqual(hooks.deliver_gaps(self.database,settings,Board(),config)['delivered'],1)
  self.assertEqual(seen[0],seen[1]);self.assertTrue(json.loads(seen[0])['allowDuplicate'])


if __name__=='__main__':unittest.main()
