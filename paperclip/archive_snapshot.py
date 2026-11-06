"""One recovery point contains one completed native SQL snapshot, never its rolling history."""
import argparse
import gzip
import os
import tarfile
from pathlib import Path

DATABASE='opt/narimato-paperclip/data/instances/default/db'
SQL_HISTORY='opt/narimato-paperclip/data/instances/default/data/backups'

def create(root,output,paths,since):
 root=Path(root).resolve();output=Path(output)
 if output.exists() or not output.is_absolute() or output.parent.stat().st_mode&0o077:raise ValueError('New private recovery artifact required')
 candidates=[p for p in (root/SQL_HISTORY).glob('paperclip-*.sql.gz') if p.is_file() and not p.is_symlink() and p.stat().st_mtime>=since and p.stat().st_size>1000]
 if not candidates:raise ValueError('Fresh completed native SQL snapshot required')
 sql=max(candidates,key=lambda p:(p.stat().st_mtime,p.name));selected=str(sql.relative_to(root))
 with gzip.open(sql,'rb') as stream:
  while stream.read(1024*1024):pass
 for name in paths:
  if Path(name).is_absolute() or '..' in Path(name).parts or not (root/name).exists():raise ValueError('Existing explicit recovery component required')
 included=False
 def select(info):
  nonlocal included
  name=info.name.rstrip('/')
  if name==DATABASE or name.startswith(DATABASE+'/'):return None
  if name.startswith(SQL_HISTORY+'/'):
   if name!=selected:return None
   included=True
  return info
 fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'wb') as raw:
   with tarfile.open(fileobj=raw,mode='w:gz') as archive:
    for name in paths:archive.add(root/name,arcname=name,filter=select)
   raw.flush();os.fsync(raw.fileno())
  if not included:raise ValueError('SQL snapshot was not included in recovery artifact')
 except BaseException:
  # Preserve an incomplete artifact for inspection; never replace a previous recovery point.
  raise
 return {'sql_snapshot':sql.name,'sql_snapshots_included':1,'rolling_sql_history_included':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default='/');parser.add_argument('--output',required=True);parser.add_argument('--since',required=True,type=float);parser.add_argument('paths',nargs='+');args=parser.parse_args()
 create(args.root,args.output,args.paths,args.since)
