"""Tests for paperclip/snapshot.sh: the recovery bundle must hold every credential file the factory service loads, and the
factory snapshot must be taken before the bundle is written. A service environment file added without a bundle entry
leaves a restore without that secret."""
import pathlib,re,unittest
HERE=pathlib.Path(__file__).resolve().parent
script=HERE.parent/'snapshot.sh'
if not script.exists():script=pathlib.Path('/opt/narimato-paperclip/snapshot.sh')
class SnapshotTests(unittest.TestCase):
 def test_every_service_environment_file_is_in_the_bundle(self):
  unit=(HERE/'narimato-factory.service').read_text();text=script.read_text()
  files=re.findall(r'^EnvironmentFile=-?/(\S+)$',unit,re.M);self.assertIn('etc/paperclip-segmind.env',files)
  self.assertEqual([f for f in files if f not in text],[])
 def test_optional_environment_files_are_added_only_when_present(self):
  text=script.read_text()
  for name in ['classscout','brave','segmind','padel','slg']:self.assertRegex(text,r'if \[ -f /etc/paperclip-'+name+r'\.env \]; then\n  set -- "\$@" etc/paperclip-'+name+r'\.env\nfi')
 def test_bundle_is_written_after_the_factory_snapshot(self):
  text=script.read_text();self.assertLess(text.index('worker.py backup'),text.index('tar --exclude'))
if __name__=='__main__':unittest.main()
