import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research.collect import hf,router,classify,parameters,collect
class Tests(unittest.TestCase):
 def test_normalize_score_and_known_models(self):
  row=hf({'id':'Qwen/Qwen3-0.6B-GGUF','sha':'new','tags':['gguf','license:apache-2.0'],'pipeline_tag':'text-generation'},['Qwen'])
  self.assertEqual(row['parameter_billions'],.6);self.assertTrue(row['publisher_verified_by_allowlist'])
  candidate=classify(row,[]);self.assertGreaterEqual(candidate['screening_score'],30)
  known=classify(row,[{'model':'qwen3:0.6b','canonical':'qwen306b','outcomes':['ran'],'evidence':['test']}]);self.assertEqual(known['test_status'],'known_model_family_verify_revision')
  huge=classify(hf({'id':'other/Model-70B-GGUF','tags':['gguf']},[]),[]);self.assertLess(huge['screening_score'],0)
 def test_out_of_scope_small_model_is_not_shortlisted(self):
  row=classify(hf({'id':'ibm-granite/granite-speech-470m','pipeline_tag':'automatic-speech-recognition','tags':['license:apache-2.0']},['ibm-granite']),[])
  self.assertEqual(row['possible_workstreams'],['out_of_scope']);self.assertLess(row['screening_score'],30)
 def test_hosted_listing_not_local_eligibility(self):
  row=classify(router({'id':'provider/tiny-1b','architecture':{'input_modalities':['image','text']}}),[])
  self.assertFalse(row['local_runtime_verified']);self.assertEqual(row['runtime_eligibility'],'unverified')
 def test_failed_sources_preserve_registry(self):
  config={'trusted_hf_authors':[],'hf_recent_gguf_limit':1,'hf_recent_vision_limit':1,'max_response_bytes':1024,'snapshot_days':30,'snapshot_budget_bytes':1024*1024,'shortlist_limit':10,'max_registry_records':100}
  def metadata(url,limit):
   if 'huggingface' in url:return json.dumps([{'id':'author/tiny-1b-GGUF','tags':['gguf','license:mit']}]).encode()
   raise OSError('unavailable')
  with tempfile.TemporaryDirectory() as root:
   with patch('research.collect.fetch',side_effect=metadata),patch('research.collect.urllib.request.urlopen',side_effect=OSError()):first=collect(Path(root),config,{'models':[]})
   self.assertEqual(first['status'],'degraded');self.assertEqual(first['registry_models'],1)
   with patch('research.collect.fetch',side_effect=OSError()),patch('research.collect.urllib.request.urlopen',side_effect=OSError()):second=collect(Path(root),config,{'models':[]})
   self.assertEqual(second['status'],'failed');self.assertEqual(second['registry_models'],1);self.assertTrue((Path(root)/'last-success.json').exists())
if __name__=='__main__':unittest.main()
