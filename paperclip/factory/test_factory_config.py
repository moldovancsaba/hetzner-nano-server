"""Guards the factory.json snapshot against settings that nothing reads: every key, and every key inside a settings
block, must appear as a quoted name in the factory's runtime code. A key that appears nowhere cannot change behaviour, so
it must not be written down as if it could. The scan is by name, so it catches orphans with distinctive names, not a
misspelt use of a common word."""
import json,pathlib,re,unittest
HERE=pathlib.Path(__file__).resolve().parent
# Maps of ids to names, not settings.
MAPS={'projects','agents'}
def runtime_source():
 """The factory's Python code that runs on the host, without tests and without provision.py (which writes the keys)."""
 return '\n'.join(p.read_text(encoding='utf8') for p in sorted(HERE.glob('*.py')) if not p.name.startswith('test_') and p.name!='provision.py')
def unread_keys(config,source=None):
 """Returns the dotted names of settings in config that no runtime code names."""
 source=runtime_source() if source is None else source;missing=[]
 def named(key):return re.search(r'''['"]'''+re.escape(key)+r'''['"]''',source) is not None
 for key,value in config.items():
  if not named(key):missing.append(key)
  if key not in MAPS and isinstance(value,dict):missing.extend(key+'.'+inner for inner in value if not named(inner))
 return missing
class FactoryConfigTests(unittest.TestCase):
 def test_snapshot_has_no_setting_that_nothing_reads(self):
  self.assertEqual(unread_keys(json.loads((HERE/'factory.json').read_text())),[])
 def test_an_unread_setting_is_reported_with_its_block(self):
  source="config.get('growth_mode',{}).get('enabled');config['projects']"
  self.assertEqual(unread_keys({'growth_mode':{'enabled':True,'campaign':'x'},'pilot_brand':'a','projects':{'id-1':'ClassScout'}},source),['growth_mode.campaign','pilot_brand'])
if __name__=='__main__':unittest.main()
