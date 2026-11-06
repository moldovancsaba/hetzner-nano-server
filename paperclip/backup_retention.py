"""Seven days of daily recovery points; prune only after a verified newer point exists."""
import datetime
import hashlib
import gzip
import json
import re
import time
from pathlib import Path
from zoneinfo import ZoneInfo

PATTERN=re.compile(r'paperclip-recovery-(\d{8}T\d{6}Z)\.tar\.gz')
RETENTION_SECONDS=7*86400

def digest(path):
 result=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
 return result.hexdigest()

def prune(directory,*,now=None,apply=False):
 root=Path(directory);now=time.time() if now is None else now
 if root.is_symlink() or root.stat().st_mode&0o077:raise ValueError('Private backup directory required')
 rows=[]
 for path in root.iterdir():
  match=PATTERN.fullmatch(path.name)
  if not match or path.is_symlink() or not path.is_file():continue
  captured=datetime.datetime.strptime(match[1],'%Y%m%dT%H%M%SZ').replace(tzinfo=datetime.timezone.utc)
  markers=[path.with_name(path.name+'.verified.json'),path.with_suffix('.verified.json')];verified=None
  for marker in markers:
   if marker.is_file() and not marker.is_symlink() and marker.stat().st_size<65536:
    value=json.loads(marker.read_text());sha=value.get('sha256','')
    if re.fullmatch('[a-f0-9]{64}',sha):verified=sha;break
  rows.append({'path':path,'captured':captured.timestamp(),'day':captured.astimezone(ZoneInfo('Europe/Budapest')).date().isoformat(),'markers':markers,'sha256':verified})
 verified=sorted([row for row in rows if row['sha256']],key=lambda row:row['captured'],reverse=True)
 if not verified:raise ValueError('A verified recovery point is required before retention cleanup')
 latest=verified[0]
 if digest(latest['path'])!=latest['sha256']:raise ValueError('Latest verified recovery point changed')
 daily={}
 for row in verified:daily.setdefault(row['day'],row['path'].name)
 retained_days=set(sorted(daily,reverse=True)[:7])
 removed=[]
 for row in rows:
  if row is latest:continue
  expired=row['captured']<=now-RETENTION_SECONDS or bool(row['sha256'] and row['day'] not in retained_days)
  superseded=bool(row['sha256'] and daily.get(row['day'])!=row['path'].name)
  if not (expired or superseded):continue
  if apply:
   row['path'].unlink()
   for marker in row['markers']:
    if marker.is_file() and not marker.is_symlink():marker.unlink()
  removed.append({'name':row['path'].name,'reason':'older-than-seven-days' if expired else 'newer-verified-daily-point'})
 return {'retention_days':7,'daily_recovery_points':True,'latest_protected':latest['path'].name,'removed':removed,'applied':apply,'retained':len(rows)-len(removed)}

def prune_sql(directory,*,now=None,apply=False):
 root=Path(directory);now=time.time() if now is None else now;pattern=re.compile(r'paperclip-(\d{8}-\d{6})\.sql\.gz');rows=[]
 if root.is_symlink():raise ValueError('Original native SQL directory required')
 for path in root.iterdir():
  match=pattern.fullmatch(path.name)
  if not match or path.is_symlink() or not path.is_file():continue
  captured=datetime.datetime.strptime(match[1],'%Y%m%d-%H%M%S').replace(tzinfo=datetime.timezone.utc)
  rows.append({'path':path,'captured':captured.timestamp(),'day':captured.astimezone(ZoneInfo('Europe/Budapest')).date().isoformat()})
 if not rows:raise ValueError('Native SQL recovery point required')
 rows.sort(key=lambda row:row['captured'],reverse=True);latest=rows[0];daily={}
 with gzip.open(latest['path'],'rb') as stream:
  while stream.read(1024*1024):pass
 for row in rows:daily.setdefault(row['day'],row['path'].name)
 retained_days=set(sorted(daily,reverse=True)[:7])
 removed=[]
 for row in rows[1:]:
  if row['captured']<=now-RETENTION_SECONDS or row['day'] not in retained_days or daily[row['day']]!=row['path'].name:
   if apply:row['path'].unlink()
   removed.append(row['path'].name)
 return {'retention_days':7,'daily_sql_points':True,'retained':len(rows)-len(removed),'removed':removed,'applied':apply}
