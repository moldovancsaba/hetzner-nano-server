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
   names=['opt/narimato-factory/worker.py','opt/narimato-factory/factory.json','opt/narimato-factory/workflows.json','opt/narimato-paperclip/.env','etc/paperclip-access.env','etc/caddy/Caddyfile','opt/narimato-paperclip/data/backups/native.sql']
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

 def test_modern_factory_cannot_acknowledge_or_prune_without_complete_dashboard(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,h=self.archive(tmp)
   import io
   for missing in [True,False]:
    modern=pathlib.Path(tmp)/('modern-'+str(missing)+'.tar.gz')
    with tarfile.open(path) as original,tarfile.open(modern,'w:gz') as archive:
     for member in original.getmembers():
      if member.name!='opt/narimato-factory/worker.py':archive.addfile(member,original.extractfile(member) if member.isfile() else None)
     files={'opt/narimato-factory/worker.py':b'SOURCE_EXCHANGE_DASHBOARD',
            'opt/source-exchange/dashboard/index.html':b'<html><script src="/factory/exchange/assets/main.js"></script><link href="/factory/exchange/assets/main.css"></html>',
            'opt/source-exchange/dashboard/assets/main.css':b'body{}'}
     if not missing:files['opt/source-exchange/dashboard/assets/main.js']=b'console.log(1)'
     for name,data in files.items():
      info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
    digest=hashlib.sha256(modern.read_bytes()).hexdigest()
    if missing:
     with self.assertRaisesRegex(ValueError,'Dashboard recovery assets missing'):backup.verify(modern,digest)
    else:self.assertEqual(backup.verify(modern,digest)['dashboard_assets_verified'],2)

 def test_proxy_import_cannot_be_acknowledged_without_its_private_configuration(self):
  with tempfile.TemporaryDirectory() as tmp:
   source,_=self.archive(tmp);target=pathlib.Path(tmp)/'proxy.tar.gz'
   with tarfile.open(source) as original,tarfile.open(target,'w:gz') as archive:
    for member in original.getmembers():
     if member.name=='etc/caddy/Caddyfile':
      body=b'import /etc/caddy/source-exchange-dashboard.caddy';member.size=len(body);archive.addfile(member,io.BytesIO(body))
     else:archive.addfile(member,original.extractfile(member) if member.isfile() else None)
   with self.assertRaisesRegex(ValueError,'proxy recovery configuration missing'):
    backup.verify(target,hashlib.sha256(target.read_bytes()).hexdigest())

 def test_native_reader_dependencies_must_survive_recovery_capture(self):
  with tempfile.TemporaryDirectory() as tmp:
   source,_=self.archive(tmp);target=pathlib.Path(tmp)/'reader.tar.gz'
   with tarfile.open(source) as original,tarfile.open(target,'w:gz') as archive:
    for member in original.getmembers():archive.addfile(member,original.extractfile(member) if member.isfile() else None)
    body=b'native_reporting.read_tasks(config)';member=tarfile.TarInfo('opt/narimato-factory/business_metrics.py');member.size=len(body);archive.addfile(member,io.BytesIO(body))
   with self.assertRaisesRegex(ValueError,'Native reporting recovery component missing'):backup.verify(target,hashlib.sha256(target.read_bytes()).hexdigest())
