import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gateway import metrics
POLICY=json.loads((ROOT/'config/model-policy.json').read_text())
ROUTES=json.loads((ROOT/'config/job-routes.json').read_text())['routes']
CONTEXT=json.loads((ROOT/'config/runtime-context-profiles.json').read_text())
BATCH=('management','sportolok')
class TenantConfigTests(unittest.TestCase):
 def test_every_text_tenant_has_a_verified_8k_profile_and_minimum(self):
  tasks=POLICY['models'][POLICY['defaults']['text_chat']]['tasks']['text_chat']
  for tenant in ROUTES['text_chat']['tenants']:
   self.assertEqual(tasks['tenant_profiles'][tenant]['num_ctx'],8192,tenant)
   self.assertEqual(POLICY['tenant_context_minimums'][tenant]['text_chat'],8192,tenant)
   self.assertEqual(CONTEXT['tenant_context_minimums'][tenant]['text_chat'],8192,tenant)
   self.assertIn(tenant,[p.get('tenant') for p in CONTEXT['profiles']],tenant)
 def test_the_batch_engines_share_the_core_queue_and_are_recorded_by_name(self):
  for tenant in BATCH:
   self.assertIn(tenant,ROUTES['text_chat']['tenants']);self.assertIn(tenant,metrics.TENANTS)
  self.assertNotIn('camera',BATCH)
 def test_batch_engines_get_no_image_or_hungarian_route(self):
  for task in ('image_moderation','image_recognition','text_chat_hu'):
   for tenant in BATCH:self.assertNotIn(tenant,ROUTES[task]['tenants'])
if __name__=='__main__':unittest.main()
