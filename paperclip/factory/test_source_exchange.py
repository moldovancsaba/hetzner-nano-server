"""Factory exchange hooks preserve transaction ownership and original delivery requests."""
import contextlib
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import source_exchange as hooks


class HookTests(unittest.TestCase):
 def test_systemd_read_only_credentials_are_accepted_only_in_managed_directory(self):
  directory=Path(tempfile.mkdtemp(dir=self.tmp.name));token=directory/'exchange-token';token.write_text('x'*48);token.chmod(0o440);directory.chmod(0o550)
  with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(directory)}):
   self.assertEqual(hooks.credential_token({'token_file':str(token)}),'x'*48)
  with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(directory/'other')}):
   with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(token)})
  directory.chmod(0o700)

 def test_managed_credentials_refuse_shared_writes_public_reads_and_symlinks(self):
  directory=Path(tempfile.mkdtemp(dir=self.tmp.name));token=directory/'exchange-token';token.write_text('x'*48)
  with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(directory)}):
   for mode in [0o444,0o460,0o640]:
    token.chmod(mode)
    with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(token)})
   token.chmod(0o440);directory.chmod(0o770)
   with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(token)})
   directory.chmod(0o700);link=directory/'linked';link.symlink_to(token)
   with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(link)})

 def test_private_file_credentials_remain_supported_without_managed_environment(self):
  token=Path(self.tmp.name)/'private-token';token.write_text('x'*48);token.chmod(0o600)
  with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':''}):
   self.assertEqual(hooks.credential_token({'token_file':str(token)}),'x'*48)
   token.write_text('x'*513)
   with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(token)})

 def test_nonregular_credential_is_refused_before_opening_or_network(self):
  fifo=Path(self.tmp.name)/'not-a-token';os.mkfifo(fifo)
  with patch.object(hooks.os,'open',side_effect=AssertionError('must refuse before opening FIFO')):
   with self.assertRaises(ValueError):hooks.credential_token({'token_file':str(fifo)})
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

 def test_multiple_event_scopes_receive_fair_claims_with_same_turn_acknowledgments(self):
  import uuid
  from exchange.store import Store
  from exchange.contract import encode,iso
  now=time.time();scopes=[{'application':'classscout','client':client} for client in ['NYC','BOS']]
  inbox=str(uuid.uuid4());broker=Store(Path(self.tmp.name)/'multi-broker.sqlite3',initialize=True)
  reader={'id':'factory','clients':scopes,'scopes':['events:claim','status:read'],'inbox_ids':{'events':inbox}}
  writer={'id':'mac','clients':scopes,'scopes':['events:write']}
  for scope in scopes:
   for i in range(5):
    event={'schema_version':'1.1','event_id':str(uuid.uuid4()),'scope':scope,'occurred_at':iso(now),'job_run_ref':'fixture','evaluation_id':str(uuid.uuid4()),'revision':1,'previous_event_id':None,'payload':{'event_type':'gap_report','candidate_ref':'candidate-'+str(i),'gap_fields':['address'],'evidence_fingerprint':'a'*64,'checker_version':'fixture','reason_code':'missing-address'}}
    broker.mutation(writer,str(uuid.uuid4()),'/events',encode(event))
  claimed=[]
  def transport(settings,method,route,body=None,operation=None):
   if method=='GET':return broker.status(reader)
   if route=='/events/claim':claimed.append(json.loads(body)['scope']['client'])
   return json.loads(broker.mutation(reader,operation,route,body)[1])
  settings={**self.settings,'events_enabled':True,'event_scopes':scopes,'event_inbox_id':inbox}
  with patch.object(hooks,'transport',side_effect=transport):
   hooks.event_turn(self.database,settings)
   with broker.connection() as db:
    self.assertEqual(db.execute('SELECT count(*) FROM deliveries').fetchone()[0],5)
    self.assertEqual(db.execute('SELECT count(*) FROM deliveries WHERE acked IS NOT NULL').fetchone()[0],5)
   hooks.event_turn(self.database,settings)
  self.assertEqual(claimed[:2],['NYC','BOS'])
  with broker.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM deliveries WHERE acked IS NULL').fetchone()[0],0)

 def test_exhausted_turn_budget_does_not_start_transport(self):
  settings={**self.settings,'events_enabled':True,'event_scope':{'application':'classscout','client':'NYC'},'_deadline':time.monotonic()-1}
  with patch.object(hooks,'transport',side_effect=AssertionError('budget exhausted')):
   self.assertEqual(hooks.event_turn(self.database,settings),{'completed':0})

 def test_verified_page_handoff_offers_evidence_without_a_model_or_search(self):
  path=Path(self.tmp.name)/'factory.json';path.write_text(json.dumps({'source_exchange':self.settings}))
  facts=[{'field':'name','value':'Fixture Studio','quote':'Fixture Studio'}]
  with patch.dict('os.environ',{'FACTORY_CONFIG':str(path)}),patch('evidence.literal_facts',return_value=facts):
   packet=hooks.save_verified_page(self.database,{'issue_id':'native-search-task','project_id':'project'},self.page)
  self.assertIsNotNone(packet)
  with self.database() as db:body=json.loads(db.execute('SELECT body FROM exchange_source_outbox').fetchone()[0])
  self.assertEqual(body['producer_task_ref'],'native-search-task')
  self.assertEqual(body['claims'][0]['quote'],'Fixture Studio')

 def test_disabled_verified_page_export_never_opens_database(self):
  path=Path(self.tmp.name)/'factory.json';path.write_text(json.dumps({'source_exchange':{}}))
  with patch.dict('os.environ',{'FACTORY_CONFIG':str(path)}):
   self.assertIsNone(hooks.save_verified_page(None,{'issue_id':'native','project_id':'project'},self.page))


 def handoff_config(self):
  scope={'application':'classscout','client':'NYC'}
  return {'source_exchange':{'projects':{'project':scope},'destination_handoffs':{'project':{'scope':scope,'writer':'openclaw','writer_epoch':1,'review_ref':'isolated-handoff-review'}}}}

 def test_handoff_blocks_all_three_writer_entries_before_any_dependency_work(self):
  import publishing,refresh,program_updates
  from unittest.mock import Mock
  issue={'projectId':'project'};config=self.handoff_config()
  for module in [publishing,refresh,program_updates]:
   with self.subTest(module=module.__name__):
    dependency=Mock(side_effect=AssertionError('handoff must precede native work'))
    args=[issue,dependency,config,dependency,dependency]
    kwargs={'execution':None} if module is publishing else {'execution':{}}
    with self.assertRaisesRegex(ValueError,'delegated'):module.run(*args,**kwargs)
    dependency.assert_not_called()

 def test_handoff_is_project_scoped_and_never_follows_source_shadow_alone(self):
  hooks.require_native_catalog_writer({'source_exchange':self.settings},{'projectId':'project'})
  hooks.require_native_catalog_writer(self.handoff_config(),{'projectId':'different-project'})
  with self.assertRaisesRegex(ValueError,'delegated'):hooks.require_native_catalog_writer(self.handoff_config(),{'projectId':'project'})

 def test_invalid_handoff_scope_or_missing_review_cannot_allow_the_old_writer(self):
  for change in [{'scope':{'application':'classscout','client':'BOS'}},{'review_ref':''},{'writer_epoch':True},{'writer':'paperclip'}]:
   config=self.handoff_config();config['source_exchange']['destination_handoffs']['project'].update(change)
   with self.subTest(change=change):
    with self.assertRaises(ValueError):hooks.require_native_catalog_writer(config,{'projectId':'project'})


if __name__=='__main__':unittest.main()
