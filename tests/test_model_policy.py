"""Tests for ModelCatalog and the generated model policy: policy matches promote_rankings.build, defaults follow
rankings, missing, wrong-job, unknown and changed-digest models are refused, discovery listing, hot
reload and per-tenant context profiles."""
import copy,json,tempfile,unittest
from pathlib import Path
from gateway.catalog import ModelCatalog,SelectionError
from gateway.server import POLICY_PATH
from scripts.promote_rankings import build

class Tests(unittest.TestCase):
 def setUp(self):
  self.policy=json.loads(POLICY_PATH.read_text())
  self.inventory=[{'name':name,'digest':entry['tested_digest']} for name,entry in self.policy['models'].items()]
 def test_generated_policy_current_and_defaults(self):
  self.assertEqual(build(),self.policy)
  source=json.loads((POLICY_PATH.parents[1]/'config/ranking-sources.json').read_text())
  rankings=json.loads((POLICY_PATH.parents[1]/source['english_and_images']).read_text())
  self.assertEqual(self.policy['defaults']['text_chat'],rankings['english'][0]['model'])
  self.assertEqual(self.policy['defaults']['image_recognition'],rankings['image'][0]['model'])
  self.assertEqual(self.policy['models'][self.policy['defaults']['image_moderation']]['tasks']['image_moderation']['rank'],1)
 def test_missing_default_never_silently_falls_back(self):
  inventory=[m for m in self.inventory if m['name']!='granite4:1b-h'];c=ModelCatalog(POLICY_PATH,lambda:{'models':inventory})
  with self.assertRaises(SelectionError) as exc:c.select('text_chat','auto')
  self.assertEqual(exc.exception.code,'default_model_not_installed')
  self.assertEqual(c.select('text_chat','qwen3:0.6b')['model'],'qwen3:0.6b')
 def test_wrong_job_unknown_and_changed_digest_blocked(self):
  c=ModelCatalog(POLICY_PATH,lambda:{'models':self.inventory})
  for task,model in [('text_chat','random:70b'),('image_moderation','granite4:1b-h'),('image_moderation','qwen3:0.6b')]:
   with self.assertRaises(SelectionError):c.select(task,model)
  changed=copy.deepcopy(self.inventory);changed[0]['digest']='changed'
  c=ModelCatalog(POLICY_PATH,lambda:{'models':changed})
  with self.assertRaises(SelectionError) as exc:c.select('text_chat','auto')
  self.assertEqual(exc.exception.code,'model_artifact_changed_since_test')
 def test_discovery_lists_installed_unapproved_and_permission_filters(self):
  c=ModelCatalog(POLICY_PATH,lambda:{'models':self.inventory+[{'name':'not-tested:3b','digest':'other'}]})
  _,rows=c.records(['image_recognition','image_moderation'])
  self.assertEqual(next(r for r in rows if r['id']=='granite4:1b-h')['selectable_for'],[])
  self.assertEqual(next(r for r in rows if r['id']=='not-tested:3b')['blocked_reason'],'not_tested_for_your_jobs')
  self.assertIn('image_recognition',next(r for r in rows if r['id']==self.policy['defaults']['image_recognition'])['selectable_for'])
 def test_policy_hot_reload(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'policy.json';path.write_text(json.dumps(self.policy));c=ModelCatalog(path,lambda:{'models':self.inventory})
   changed=copy.deepcopy(self.policy);changed['defaults']['text_chat']='qwen3:0.6b';changed['policy_id']='new-ranked-policy';path.write_text(json.dumps(changed))
   self.assertEqual(c.select('text_chat','auto')['model'],'qwen3:0.6b')
 def test_context_profiles_are_scoped_to_configured_consumers(self):
  with tempfile.TemporaryDirectory() as root:
   policy=copy.deepcopy(self.policy)
   model=policy['defaults']['text_chat']
   policy['models'][model]['tasks']['text_chat'].setdefault('tenant_profiles',{})['paperclip']={'num_ctx':8192,'num_batch':128}
   path=Path(root)/'policy.json';path.write_text(json.dumps(policy));c=ModelCatalog(path,lambda:{'models':self.inventory})
   self.assertEqual(c.select('text_chat','auto',tenant='paperclip')['model_profile']['num_ctx'],8192)
   self.assertEqual(c.select('text_chat','auto',tenant='classscout')['model_profile']['num_ctx'],8192)
   self.assertEqual(c.select('text_chat','auto',tenant='another_app')['model_profile']['num_ctx'],2048)
   _,rows=c.records(['text_chat'],tenant='paperclip')
   self.assertEqual(next(row for row in rows if row['id']==model)['rankings']['text_chat']['profile']['num_ctx'],8192)
   self.assertEqual(next(row for row in rows if row['id']=='qwen3:1.7b')['selectable_for'],[])
   with self.assertRaises(SelectionError):c.select('text_chat','qwen3:1.7b',tenant='paperclip')
 def test_new_default_requires_verified_context_but_explicit_pin_keeps_legacy_profile(self):
  with tempfile.TemporaryDirectory() as root:
   policy=copy.deepcopy(self.policy);policy['defaults']['text_chat']='qwen3:0.6b'
   path=Path(root)/'policy.json';path.write_text(json.dumps(policy));c=ModelCatalog(path,lambda:{'models':self.inventory})
   with self.assertRaises(SelectionError) as exc:c.select('text_chat','auto',tenant='classscout')
   self.assertEqual(exc.exception.code,'default_context_profile_not_verified')
   self.assertEqual(c.select('text_chat','qwen3:0.6b',tenant='classscout')['model_profile']['num_ctx'],2048)
if __name__=='__main__':unittest.main()
