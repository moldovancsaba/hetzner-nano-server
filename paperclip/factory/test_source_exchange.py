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


if __name__=='__main__':unittest.main()
