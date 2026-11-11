import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_paperclip_drift as drift
class ClassifyTests(unittest.TestCase):
 def test_equal_hashes_are_same_and_unrecorded_differences_are_drift(self):
  self.assertEqual(drift.classify({'a':'1','b':'2'},{'a':'1','b':'9'},{}),{'a':'SAME','b':'DRIFT'})
 def test_a_recorded_difference_is_known_only_while_both_hashes_still_match(self):
  accepted={'a':{'server':'9','repo':'2','reason':'x'}}
  self.assertEqual(drift.classify({'a':'2'},{'a':'9'},accepted),{'a':'KNOWN'})
  self.assertEqual(drift.classify({'a':'3'},{'a':'9'},accepted),{'a':'STALE'})
  self.assertEqual(drift.classify({'a':'2'},{'a':'8'},accepted),{'a':'STALE'})
 def test_a_file_missing_on_the_host_can_be_recorded_as_a_known_difference(self):
  self.assertEqual(drift.classify({'a':'2'},{},{'a':{'server':None,'repo':'2','reason':'x'}}),{'a':'KNOWN'})
class NormaliseTests(unittest.TestCase):
 def test_secret_header_values_never_reach_the_comparison(self):
  one=drift.normalise_caddy('\theader_up X-Jev-Ingress aaaa\n\theader_up Authorization Bearer bbbb\n\theader_up X-Real-IP {remote_host}\n')
  two=drift.normalise_caddy('\theader_up X-Jev-Ingress cccc\n\theader_up Authorization <redacted>\n\theader_up X-Real-IP {remote_host}\n')
  self.assertEqual(one,two);self.assertNotIn('aaaa',one);self.assertIn('{remote_host}',one)
 def test_a_changed_non_secret_header_is_still_a_difference(self):
  self.assertNotEqual(drift.normalise_caddy('header_up X-Real-IP {remote_host}'),drift.normalise_caddy('header_up X-Real-IP 1.2.3.4'))
 def test_inert_json_settings_and_key_order_do_not_count(self):
  host=json.dumps({'b':1,'a':{'keep':1,'inert':2},'old':3});repo=json.dumps({'a':{'keep':1},'b':1})
  self.assertEqual(drift.normalise_json(host,('a.inert','old')),drift.normalise_json(repo,('a.inert','old')))
  self.assertNotEqual(drift.normalise_json(json.dumps({'a':{'keep':2}}),()),drift.normalise_json(repo,()))
class BaselineTests(unittest.TestCase):
 def test_the_committed_baseline_names_a_reason_for_every_difference(self):
  accepted=json.loads((ROOT/'paperclip/drift-baseline.json').read_text())['accepted']
  for path,note in accepted.items():self.assertNotIn(note['reason'],('','unreviewed'),path)
 def test_every_mapped_repository_file_exists(self):
  missing=[r for r,_,_ in drift.mapping() if not (ROOT/r).is_file()]
  self.assertEqual(missing,[])
if __name__=='__main__':unittest.main()
