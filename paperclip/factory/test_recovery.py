"""Regression for native monitors consuming policy before invoking a process adapter."""
import json,pathlib,tempfile,unittest
from unittest.mock import patch,Mock
import worker

class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state.start();worker.initialize()
 def tearDown(self):self.state.stop();self.tmp.cleanup()
 def test_real_execute_contract_resumes_after_native_monitor_was_consumed(self):
  company='00000000-0000-4000-8000-000000000001';agent='00000000-0000-4000-8000-000000000002';issueid='00000000-0000-4000-8000-000000000003'
  runid=['00000000-0000-4000-8000-000000000004']
  issue={'id':issueid,'companyId':company,'projectId':'project','title':'[Factory test] Native resume','description':'https://example.org/kids','status':'todo','assigneeAgentId':agent,'identifier':'TEST-1','executionPolicy':None}
  config={'company_id':company,'projects':{'project':'ClassScout'},'agents':{agent:{'role':'research'}},'reviewer_user_id':'local-board'}
  path=pathlib.Path(self.tmp.name)/'config.json';path.write_text(json.dumps(config));board=Mock()
  def call(url,body=None,method=None):
   if url=='/agents/me':return {'id':agent,'companyId':company}
   if url.startswith('/heartbeat-runs/'):return {'id':runid[0],'agentId':agent,'companyId':company,'status':'running','contextSnapshot':{'issueId':issueid,'wakeReason':'issue_monitor_due'}}
   if url=='/issues/'+issueid and body is None:return dict(issue)
   if url.endswith('/checkout'):issue['status']='in_progress';return dict(issue)
   if url.endswith('/comments'):return {'id':'comment'}
   if url=='/issues/'+issueid and method=='PATCH':issue.update(body);return dict(issue)
   raise AssertionError((url,body,method))
  board.call.side_effect=call
  maintenance=ValueError('Service returned HTTP 503: {"error": {"code": "model_storage_maintenance"}}')
  result={'markdown':'Source verified','entities':[],'metrics':[]}
  with patch.object(worker,'CONFIG_PATH',path),patch.object(worker,'Board',return_value=board),patch.object(worker,'research',side_effect=[maintenance,result]) as research,patch('search_workflow.quality_for_search_source'),patch('worker.time.time',return_value=1000):
   first=worker.execute({'run_id':runid[0],'agent_id':agent,'company_id':company,'agent_token':'x'*50});self.assertEqual(first['stage'],'model_waiting')
   self.assertEqual(issue['status'],'in_review');self.assertEqual(issue['assigneeAgentId'],agent)
   issue['executionPolicy']['monitor']=None # Paperclip consumes the monitor before dispatch.
   runid[0]='00000000-0000-4000-8000-000000000005'
   with patch('worker.time.time',return_value=1301):
    second=worker.execute({'run_id':runid[0],'agent_id':agent,'company_id':company,'agent_token':'x'*50})
   self.assertEqual(second['stage'],'research_review');self.assertEqual(research.call_count,2);self.assertIsNone(issue['assigneeAgentId']);self.assertEqual(issue['assigneeUserId'],'local-board')
   self.assertEqual(research.call_args.args[-1],'test')
  with worker.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM model_waits').fetchone()[0],0)
 def test_wait_cannot_replay_ordinary_review_or_cross_agent_work(self):
  issue={'id':'issue','assigneeAgentId':'agent'};self.assertFalse(worker.model_wait_due(issue,'agent'))
  with patch('worker.time.time',return_value=1000):worker.model_wait_policy(issue,'research','"code": "model_storage_maintenance"')
  with patch('worker.time.time',return_value=1200):self.assertFalse(worker.model_wait_due(issue,'agent'))
  with patch('worker.time.time',return_value=1301):
   self.assertTrue(worker.model_wait_due(issue,'agent'));self.assertFalse(worker.model_wait_due(issue,'other'))
 def test_retry_counter_survives_missing_monitor_and_restart(self):
  issue={'id':'issue','assigneeAgentId':'agent'}
  for i in range(12):
   policy=worker.model_wait_policy(issue,'research','"code": "model_storage_maintenance"');self.assertIn('wait '+str(i+1)+'/12',policy['monitor']['notes']);worker.initialize()
  self.assertIsNone(worker.model_wait_policy(issue,'research','"code": "model_storage_maintenance"'))
if __name__=='__main__':unittest.main()
