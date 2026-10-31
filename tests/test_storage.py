"""Tests for model storage retention: storage.cleaner reasons (current default, top three, recent production
use, resident), shipped policy validation (three-day window), usage tracking that ignores test traffic,
and the maintenance lease blocking admission."""
import json,tempfile,threading,time,unittest
from pathlib import Path
from gateway.usage import UsageStore,LeaseStore
from gateway.server import Scheduler
from storage.cleaner import reasons,validate_storage,validate_usage

class Tests(unittest.TestCase):
 def setUp(self):
  self.now=2_000_000_000
  self.policy={'defaults':{'text_chat':'winner'},'models':{'winner':{'tasks':{'text_chat':{'rank':1}}},'third':{'tasks':{'image_recognition':{'rank':3}}},'old':{'tasks':{'text_chat':{'rank':6}}}}}
  self.usage={'version':'model-usage.v1','tracking_started_at':self.now-15*86400,'bootstrap_inventory':{'old':'digest'},'models':{}}
 def test_ranked_recent_and_resident(self):
  self.assertIn('current_default',reasons({'name':'winner'},self.policy,self.usage,set(),self.now))
  self.assertIn('top_three:image_recognition',reasons({'name':'third'},self.policy,self.usage,set(),self.now))
  self.assertEqual(reasons({'name':'old','digest':'digest'},self.policy,self.usage,set(),self.now),[])
  self.policy['models']['fourth']={'tasks':{'text_chat':{'rank':4}}}
  self.assertEqual(reasons({'name':'fourth'},self.policy,self.usage,set(),self.now),[])
  self.usage['models']['old']={'last_valid_request_at':self.now-3*86400}
  self.assertIn('production_request_within_3_days',reasons({'name':'old'},self.policy,self.usage,set(),self.now))
  self.usage['models']['old']={'last_valid_request_at':self.now-3*86400-1}
  self.assertEqual(reasons({'name':'old'},self.policy,self.usage,set(),self.now),[])
  self.assertIn('production_request_within_14_days',reasons({'name':'old'},self.policy,self.usage,set(),self.now,{'keep_production_request_days':14}))
  self.assertIn('resident_model',reasons({'name':'other'},self.policy,self.usage,{'other'},self.now))
 def test_bootstrap_only_existing_artifacts(self):
  self.usage['tracking_started_at']=self.now-13*86400
  grace={'initial_inventory_history_grace_days':14}
  self.assertIn('initial_14_day_history_grace',reasons({'name':'old','digest':'digest'},self.policy,self.usage,set(),self.now,grace))
  self.assertEqual(reasons({'name':'new-probe','digest':'different'},self.policy,self.usage,set(),self.now,grace),[])
  # Owner decision 2026-10-30: the policy file ends the grace, so a still-recent tracking start protects nothing.
  self.assertEqual(reasons({'name':'old','digest':'digest'},self.policy,self.usage,set(),self.now,{'initial_inventory_history_grace_days':0}),[])
  self.assertEqual(reasons({'name':'old','digest':'digest'},self.policy,self.usage,set(),self.now),[])
 def test_shipped_policy_is_valid_and_uses_the_three_day_window(self):
  shipped=validate_storage(json.loads((Path(__file__).resolve().parent.parent/'config'/'model-storage-policy.json').read_text()))
  self.assertEqual((shipped['keep_production_request_days'],shipped['initial_inventory_history_grace_days']),(3,0))
  for bad in ({'keep_production_request_days':0},{'keep_production_request_days':31},{'keep_production_request_days':'3'},{'initial_inventory_history_grace_days':-1},{'keep_top_per_task':2},{'automatic_weight_deletion':False}):
   with self.assertRaises(AssertionError):validate_storage({**shipped,**bad})
 def test_metadata_only_usage_and_tests_do_not_extend(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'usage.json';store=UsageStore(path,[{'name':'old','digest':'d'}]);before=path.read_bytes();store.record('old','d','test');self.assertEqual(before,path.read_bytes())
   store.record('old','d','production');data=json.loads(path.read_text());self.assertEqual(data['models']['old']['production_requests'],1)
   stamp=data['models']['old']['last_valid_request_at'];store.record('old','d','test');self.assertEqual(json.loads(path.read_text())['models']['old']['last_valid_request_at'],stamp)
   self.assertEqual(set(data['models']['old']),{'last_valid_request_at','production_requests','digest'})
   restarted=UsageStore(path,[]);self.assertEqual(restarted.read()['tracking_started_at'],data['tracking_started_at'])
 def test_only_admitted_production_jobs_extend_usage(self):
  with tempfile.TemporaryDirectory() as root:
   store=UsageStore(Path(root)/'usage.json');s=Scheduler(lambda *args:({},{}),usage=store)
   job,_=s.submit('classscout','text_chat',{},purpose='test');s.wait('classscout',job,2);self.assertEqual(store.read()['models'],{})
   job,_=s.submit('classscout','text_chat',{},idempotency='once',purpose='production');s.wait('classscout',job,2)
   again,error=s.submit('classscout','text_chat',{},idempotency='once',purpose='production');self.assertEqual(again,job)
   self.assertEqual(store.read()['models']['granite4:1b-h']['production_requests'],1)
 def test_lease_blocks_admission_and_busy_worker(self):
  gate=threading.Event();begun=threading.Event()
  def run(*args):begun.set();gate.wait(2);return {},{}
  s=Scheduler(run);lease=s.storage_lease('acquire');self.assertIsNotNone(lease)
  self.assertEqual(s.submit('classscout','text_chat',{})[1],'model_storage_maintenance')
  self.assertIsNone(s.storage_lease('release','wrong'))
  self.assertTrue(s.storage_lease('release',lease['lease']))
  job,_=s.submit('classscout','text_chat',{});begun.wait(1);self.assertIsNone(s.storage_lease('acquire'));gate.set();s.wait('classscout',job,2)
 def test_pre_cleanup_validation_cannot_admit_stale_work(self):
  s=Scheduler(lambda *args:({},{}));epoch=s.storage_epoch;lease=s.storage_lease('acquire');s.storage_lease('release',lease['lease'])
  self.assertEqual(s.submit('classscout','text_chat',{},expected_epoch=epoch)[1],'model_storage_maintenance')
 def test_cleanup_lease_survives_gateway_restart(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'lease.json';first=Scheduler(lambda *args:({},{}),maintenance_store=LeaseStore(path));lease=first.storage_lease('acquire')
   second=Scheduler(lambda *args:({},{}),maintenance_store=LeaseStore(path))
   self.assertEqual(second.submit('classscout','text_chat',{})[1],'model_storage_maintenance')
   self.assertTrue(second.storage_lease('release',lease['lease']));self.assertIsNone(LeaseStore(path).load())
 def test_usage_failure_refuses_untracked_work(self):
  class Broken:
   def record(self,*args):raise OSError()
  s=Scheduler(lambda *args:({},{}),usage=Broken());self.assertEqual(s.submit('classscout','text_chat',{})[1],'usage_tracking_unavailable')
  with self.assertRaises(Exception):validate_usage({'version':'bad'})
if __name__=='__main__':unittest.main()
