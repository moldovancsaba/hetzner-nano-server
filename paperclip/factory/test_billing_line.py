"""The dashboard's inference billing line follows the metered Segmind ledger instead of always saying the models are free."""
import time,unittest
import business_metrics,segmind,worker,test_operations

FREE={'billing':'Free local models','metered_calls_24h':None,'metered_cost_24h':None}
ON={'remote_llm':{'enabled':True}}
class BillingLineTests(unittest.TestCase):
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def line(self,config):return business_metrics.billing_line(worker.database,config,time.time()-86400)
 def test_lane_off_or_misconfigured_is_free_local_models(self):
  for config in [{},{'remote_llm':{'enabled':False}},{'remote_llm':{'enabled':True,'daily_calls':-1}}]:self.assertEqual(self.line(config),FREE)
 def test_lane_on_without_calls_says_so(self):
  result=self.line(ON);self.assertEqual(result['metered_calls_24h'],0);self.assertEqual(result['metered_cost_24h'],0)
  self.assertEqual(result['billing'],'Free local models; metered Segmind lane on (no calls in 24 h)')
 def test_calls_in_the_last_day_are_counted_from_the_ledger(self):
  limits=segmind.settings(ON);ledger=segmind.Ledger(worker.database)
  ledger.finish(ledger.reserve(limits,'one','m',100),'succeeded',200,0.0123)
  ledger.finish(ledger.reserve(limits,'two','m',100),'failed',500)
  ledger.reserve(limits,'three','m',100)
  result=self.line(ON)
  # A failed call costs nothing; an unconfirmed one counts at its ceiling (0.10), as in the allowance itself.
  self.assertEqual((result['metered_calls_24h'],result['metered_cost_24h']),(3,0.1123))
  self.assertEqual(result['billing'],'Free local models plus metered Segmind: 3 calls, $0.1123 in 24 h')
 def test_calls_older_than_a_day_are_left_out(self):
  limits=segmind.settings(ON);ledger=segmind.Ledger(worker.database,lambda:time.time()-3*86400)
  ledger.finish(ledger.reserve(limits,'old','m',100),'succeeded',200,0.05)
  self.assertEqual(self.line(ON)['metered_calls_24h'],0)
 def test_the_operations_snapshot_carries_the_line(self):
  free=business_metrics.operating_snapshot(worker.database,{'projects':{}},[],agents=[])['inference']
  self.assertEqual(free['billing'],'Free local models')
  limits=segmind.settings(ON);ledger=segmind.Ledger(worker.database);ledger.finish(ledger.reserve(limits,'one','m',100),'succeeded',200,0.02)
  on=business_metrics.operating_snapshot(worker.database,ON,[],agents=[])['inference']
  self.assertEqual(on['billing'],'Free local models plus metered Segmind: 1 call, $0.02 in 24 h')
if __name__=='__main__':unittest.main()
