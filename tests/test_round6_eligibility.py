"""Protect language/task separation and refuse partial image-suite promotion."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('round6_eligibility',Path(__file__).resolve().parents[1]/'benchmarks/round6/eligibility.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SuiteEligibility(unittest.TestCase):
 def test_hungarian_error_does_not_penalize_english(self):
  self.assertTrue(module.english_complete({'status':'failed','english_status':'completed','tests':[{}]*14,'error':'Hungarian repetition safeguard'}))
 def test_partial_english_is_not_complete(self):
  self.assertFalse(module.english_complete({'status':'completed','tests':[{}]*13}))
 def test_format_stop_has_no_recognition_rank(self):
  self.assertFalse(module.recognition_complete({'status':'failed','tests':[{}]*3,'moderation':[{}]*41}))
 def test_completed_moderation_survives_recognition_failure(self):
  self.assertTrue(module.moderation_complete({'status':'failed','tests':[{}]*3,'moderation':[{}]*41}))
 def test_recognition_requires_all_three_modules_and_no_oom(self):
  entry={'tests':[{}]*32,'robustness':[{}]*9,'counts':[{}]*8}
  self.assertTrue(module.recognition_complete(entry));entry['counts'][0]={'oom_kill_delta':1};self.assertFalse(module.recognition_complete(entry))
if __name__=='__main__':unittest.main()
