"""Daily points expire by age on both hosts; the last verified recovery remains protected."""
import datetime,gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('backup_retention',Path(__file__).parents[1]/'backup_retention.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
NOW=datetime.datetime(2026,11,6,10,tzinfo=datetime.timezone.utc).timestamp()

class RetentionTests(unittest.TestCase):
 def add(self,root,stamp,*,verified=True,mac=False):
  path=root/('paperclip-recovery-'+stamp+'.tar.gz');path.write_bytes(stamp.encode())
  if verified:
   marker=path.with_suffix('.verified.json') if mac else path.with_name(path.name+'.verified.json');marker.write_text(json.dumps({'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
  return path

 def test_server_and_mac_expire_seven_days_by_age_not_count(self):
  for mac in [False,True]:
   with self.subTest(mac=mac),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);old=self.add(root,'20261030T090000Z',mac=mac);within=self.add(root,'20261031T090000Z',mac=mac);latest=self.add(root,'20261106T090000Z',mac=mac)
    result=module.prune(root,now=NOW,apply=True);self.assertEqual(result['retention_days'],7);self.assertFalse(old.exists());self.assertTrue(within.exists());self.assertTrue(latest.exists());self.assertEqual(result['retained'],2)

 def test_a_verified_new_daily_point_replaces_its_earlier_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);old=self.add(root,'20261106T020000Z');latest=self.add(root,'20261106T090000Z');pending=self.add(root,'20261107T093000Z',verified=False)
   result=module.prune(root,now=NOW,apply=True);self.assertFalse(old.exists());self.assertTrue(latest.exists());self.assertTrue(pending.exists());self.assertEqual(result['removed'][0]['reason'],'newer-verified-daily-point')

 def test_no_verified_backup_or_changed_latest_prevents_deletion(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);old=self.add(root,'20261001T090000Z',verified=False)
   with self.assertRaises(ValueError):module.prune(root,now=NOW,apply=True)
   self.assertTrue(old.exists());latest=self.add(root,'20261106T090000Z');latest.write_bytes(b'changed')
   with self.assertRaises(ValueError):module.prune(root,now=NOW,apply=True)
   self.assertTrue(old.exists())

 def test_last_verified_point_and_unknown_files_survive_dry_run_and_expiry(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);latest=self.add(root,'20261001T090000Z');unknown=root/'manual-unknown.tar.gz';unknown.write_bytes(b'unknown')
   module.prune(root,now=NOW,apply=True);self.assertTrue(latest.exists());self.assertTrue(unknown.exists())

 def test_hourly_sql_history_reduces_to_daily_points_after_full_backup_verification(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for stamp in ['20261001-090000','20261105-020000','20261105-090000','20261106-090000']:(root/('paperclip-'+stamp+'.sql.gz')).write_bytes(gzip.compress(b'complete SQL fixture'))
   result=module.prune_sql(root,now=NOW,apply=True);self.assertEqual(result['retained'],2);self.assertTrue((root/'paperclip-20261106-090000.sql.gz').exists());self.assertFalse((root/'paperclip-20261105-020000.sql.gz').exists())

 def test_calendar_boundaries_cannot_retain_an_eighth_daily_point(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for age in range(8):
    captured=datetime.datetime.fromtimestamp(NOW-age*86400+60,datetime.timezone.utc);self.add(root,captured.strftime('%Y%m%dT%H%M%SZ'))
   self.assertEqual(module.prune(root,now=NOW,apply=True)['retained'],7)

if __name__=='__main__':unittest.main()
