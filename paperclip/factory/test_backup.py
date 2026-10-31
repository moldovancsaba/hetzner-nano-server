"""Tests for backup.verify on synthetic tar.gz archives: the checksum must match, a missing required
component (Caddyfile) is refused, the embedded SQLite file passes an integrity check, and compressed
native SQL backups are counted."""
import gzip,hashlib,importlib.util,io,pathlib,sqlite3,tarfile,tempfile,unittest
module_path=pathlib.Path(__file__).resolve().parents[1]/'backup.py'
if not module_path.exists():module_path=pathlib.Path('/opt/narimato-paperclip/backup.py')
spec=importlib.util.spec_from_file_location('paperclip_backup',module_path);backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
class BackupTests(unittest.TestCase):
 def archive(self,root,missing=False,compressed=False):
  db=pathlib.Path(root)/'factory.sqlite3'
  with sqlite3.connect(db) as c:c.execute('CREATE TABLE proof(id TEXT)')
  path=pathlib.Path(root)/'backup.tar.gz'
  with tarfile.open(path,'w:gz') as t:
   names=['opt/narimato-factory/factory.json','opt/narimato-factory/workflows.json','opt/narimato-paperclip/.env','etc/paperclip-access.env','etc/caddy/Caddyfile','opt/narimato-paperclip/data/backups/native.sql']
   if missing:names.remove('etc/caddy/Caddyfile')
   for name in names:
    data=b'x'*1200 if name.endswith('.sql') else b'{}'
    if name.endswith('.sql') and compressed:data=gzip.compress(b'x'*5000000);name+='.gz'
    info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
   t.add(db,arcname='root/paperclip-backups/factory-20260101.sqlite3')
  return path,hashlib.sha256(path.read_bytes()).hexdigest()
 def test_verified_archive_checks_sql_components_and_sqlite(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,h=self.archive(tmp);self.assertEqual(backup.verify(path,h)['sqlite_integrity'],'ok')
 def test_checksum_mismatch_refuses_archive(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,h=self.archive(tmp)
   with self.assertRaises(ValueError):backup.verify(path,'0'*64)
 def test_missing_component_is_not_a_complete_recovery_bundle(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,h=self.archive(tmp,True)
   with self.assertRaises(ValueError):backup.verify(path,h)

 def test_native_compressed_sql_backup_is_verified(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,h=self.archive(tmp,compressed=True);self.assertEqual(backup.verify(path,h)['native_sql_backups'],1)
