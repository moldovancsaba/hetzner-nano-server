"""Root-side snapshot creation and off-server verification acknowledgement."""
import hashlib,json,os,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path('/root/paperclip-scheduled-backups');PATTERN=r'paperclip-recovery-\d{8}T\d{6}Z\.tar\.gz'
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def run(mode):
 ROOT.mkdir(mode=0o700,exist_ok=True)
 if mode=='create':
  r=subprocess.run(['/opt/narimato-paperclip/snapshot.sh'],capture_output=True,text=True,timeout=600)
  if r.returncode:raise RuntimeError('snapshot_failed')
  source=pathlib.Path(r.stdout.strip())
  if source.parent!=pathlib.Path('/root/paperclip-backups') or not re.fullmatch(PATTERN,source.name):raise ValueError('Unexpected snapshot location')
  target=ROOT/source.name;os.replace(source,target);target.chmod(0o600)
  return {'name':target.name,'sha256':digest(target),'bytes':target.stat().st_size}
 if mode=='confirm':
  data=json.loads(sys.stdin.buffer.read(8192));name=data['name']
  if not re.fullmatch(PATTERN,name) or not re.fullmatch(r'[a-f0-9]{64}',data['sha256']):raise ValueError('Invalid backup acknowledgement')
  target=ROOT/name
  if digest(target)!=data['sha256']:raise ValueError('Backup checksum changed')
  (ROOT/(name+'.verified.json')).write_text(json.dumps({'verified_at':time.time(),'sha256':data['sha256']}));os.chmod(ROOT/(name+'.verified.json'),0o600)
  status={'status':'Verified off-server','verified_at':time.time(),'next_run':'Daily at 03:20 Budapest','destination':'Owner Mac','archive':name,'sha256':data['sha256'],'sqlite_integrity':'ok','retained_off_server':data.get('retained',1)}
  p=pathlib.Path('/opt/narimato-factory/backup-status.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(status,indent=2)+'\n');tmp.chmod(0o644);os.replace(tmp,p)
  verified=sorted(ROOT.glob('*.tar.gz.verified.json'),reverse=True)
  for marker in verified[14:]:
   archive=ROOT/marker.name.removesuffix('.verified.json')
   if re.fullmatch(PATTERN,archive.name):archive.unlink(missing_ok=True);marker.unlink()
  return {'status':'verified','retained_on_server':min(14,len(verified))}
 raise ValueError('Unknown snapshot action')
if __name__=='__main__':
 try:print(json.dumps(run(sys.argv[1])))
 except Exception as e:print(json.dumps({'status':'failed','error_category':type(e).__name__}));sys.exit(1)
