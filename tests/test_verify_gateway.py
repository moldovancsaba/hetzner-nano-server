"""Tests for scripts/verify_gateway.py's expectations: job types per service and ranked defaults are read from
config/job-routes.json and config/model-policy.json, and importing the script has no side effects (no key file
read, no network). The script itself sends requests to production and is never run by the tests."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import verify_gateway as verify

ROUTES={
    'text_chat':{'tenants':['classscout','pandora']},
    'image_moderation':{'tenants':['camera']},
    'image_recognition':{'tenants':['camera']},
}


class Tests(unittest.TestCase):
    def test_import_has_no_side_effects(self):
        self.assertEqual(verify.keys,{})
        self.assertEqual(verify.checks,[])

    def test_expectations_are_the_repository_files(self):
        routes,defaults,policy_id=verify.expectations()
        self.assertEqual(routes,json.loads((ROOT/'config/job-routes.json').read_text())['routes'])
        policy=json.loads((ROOT/'config/model-policy.json').read_text())
        self.assertEqual((defaults,policy_id),(policy['defaults'],policy['policy_id']))

    def test_every_routed_job_type_has_a_ranked_default(self):
        routes,defaults,_=verify.expectations()
        self.assertEqual(set(routes)-set(defaults),set())

    def test_tasks_for_follows_the_routes(self):
        self.assertEqual(verify.tasks_for(ROUTES,'classscout'),{'text_chat'})
        self.assertEqual(verify.tasks_for(ROUTES,'camera'),{'image_moderation','image_recognition'})
        self.assertEqual(verify.tasks_for(ROUTES,'nobody'),set())

    def test_denied_task_is_one_the_service_cannot_use(self):
        for tenant in ['classscout','camera']:
            self.assertNotIn(verify.denied_task(ROUTES,tenant),verify.tasks_for(ROUTES,tenant))
        routes,_,_=verify.expectations()
        for tenant in ['classscout','habigoal','camera']:
            self.assertNotIn(verify.denied_task(routes,tenant),verify.tasks_for(routes,tenant))

    def test_sample_input_matches_the_job_kind(self):
        self.assertEqual(verify.sample_input('image_moderation','a'),{'image_base64':'a'})
        self.assertIn('messages',verify.sample_input('text_chat','a'))


if __name__=='__main__':
    unittest.main()
