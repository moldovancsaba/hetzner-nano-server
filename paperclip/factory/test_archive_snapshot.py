"""A complete recovery point does not replicate all hourly SQL snapshots in every daily archive."""
import gzip,importlib.util,os,tarfile,tempfile,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('archive_snapshot',Path(__file__).parents[1]/'archive_snapshot.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class SnapshotArchiveTests(unittest.TestCase):
 def test_latest_complete_sql_and_persistent_state_are_kept_without_live_database(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);root.chmod(0o700);history=root/module.SQL_HISTORY;history.mkdir(parents=True);db=root/module.DATABASE;db.mkdir(parents=True);(db/'live').write_text('not a backup')
   for name,age in [('paperclip-old.sql.gz',100),('paperclip-current.sql.gz',0)]:
    path=history/name;path.write_bytes(gzip.compress(os.urandom(2000)));os.utime(path,(time.time()-age,time.time()-age))
   config=root/'opt/narimato-paperclip/data/instances/default/private-key';config.write_text('persistent fixture key');output=root/'recovery.tar.gz'
   result=module.create(root,output,['opt/narimato-paperclip/data'],time.time()-5)
   self.assertEqual(result['sql_snapshots_included'],1)
   with tarfile.open(output) as archive:
    names=archive.getnames();self.assertIn(str(config.relative_to(root)),names);self.assertIn(module.SQL_HISTORY+'/paperclip-current.sql.gz',names);self.assertNotIn(module.SQL_HISTORY+'/paperclip-old.sql.gz',names);self.assertNotIn(module.DATABASE+'/live',names)
   self.assertEqual(output.stat().st_mode&0o777,0o600)
   with self.assertRaises(ValueError):module.create(root,output,['opt/narimato-paperclip/data'],0)

 def test_absent_or_incomplete_fresh_dump_cannot_create_a_recovery_point(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);root.chmod(0o700);history=root/module.SQL_HISTORY;history.mkdir(parents=True)
   with self.assertRaises(ValueError):module.create(root,root/'missing.tar.gz',['opt/narimato-paperclip/data'],time.time())
   (history/'paperclip-invalid.sql.gz').write_bytes(b'x'*2000)
   with self.assertRaises(OSError):module.create(root,root/'invalid.tar.gz',['opt/narimato-paperclip/data'],0)

if __name__=='__main__':unittest.main()
