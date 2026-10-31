"""Tests for exact() in benchmarks/non-english/hu-round1/score.py: JSON numbers cannot stand in for booleans
or null, int and float values differ, and accent changes or extra unsupported fields are mismatches."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('hu_scoring',Path(__file__).resolve().parents[1]/'benchmarks/non-english/hu-round1/score.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class StrictHungarianReferenceTests(unittest.TestCase):
 def test_json_numbers_cannot_masquerade_as_consent_or_null(self):
  self.assertFalse(module.exact({'share_allowed':0},{'share_allowed':False}))
  self.assertFalse(module.exact({'price':0},{'price':None}))
  self.assertFalse(module.exact({'ages':[5,8.0]},{'ages':[5,8]}))
 def test_accents_and_extra_unsupported_fields_are_checked(self):
  self.assertTrue(module.exact({'city':'Pécs'},{'city':'Pécs'}))
  self.assertFalse(module.exact({'city':'Pecs'},{'city':'Pécs'}))
  self.assertFalse(module.exact({'city':'Pécs','address':'Kitalált utca'},{'city':'Pécs'}))
