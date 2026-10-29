"""Observe installed manifest digests and verify weight blobs against frozen publisher metadata."""
import hashlib,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parent;sources=json.loads((ROOT/'source-metadata.json').read_text());report=json.loads((ROOT/'artifact-audit.json').read_text()) if (ROOT/'artifact-audit.json').exists() else {'version':'round6-artifact-audit.v1','models':{}}
mounts=json.loads(subprocess.check_output(['docker','inspect','narimato-ollama'],text=True))[0]['Mounts'];volume=pathlib.Path(next(x['Source'] for x in mounts if x['Destination']=='/root/.ollama'));manifests=volume/'models/manifests'
deadline=time.monotonic()+5400
while time.monotonic()<deadline:
 if (ROOT/'results.json').exists():
  result=json.loads((ROOT/'results.json').read_text())
  for row in result.get('models',[]):
   if row['model'] in report['models'] or not row.get('tag'):continue
   target=row['tag']['digest'].removeprefix('sha256:');source=next(s for s in sources if s['model']==row['model'])
   for path in manifests.rglob('*'):
    if not path.is_file():continue
    try:
     raw=path.read_bytes()
     model_path,tag=row['model'].removeprefix('https://').rsplit(':',1)
     if path.relative_to(manifests).as_posix().lower()!=(model_path+'/'+tag).lower():continue
     data=json.loads(raw);layers=[x for x in data['layers'] if x['mediaType'] in ['application/vnd.ollama.image.model','application/vnd.ollama.image.projector']]
     expected={x['sha256'] for x in source['artifacts'] if x.get('sha256')}
     actual={x['digest'].removeprefix('sha256:') for x in layers}
     report['models'][row['model']]={'reported_api_digest':target,'manifest_file_sha256':hashlib.sha256(raw).hexdigest(),'frozen_source_revision':source['revision'],'layers':layers,'all_weight_blobs_match_frozen_source':bool(actual) and actual<=expected}
    except (FileNotFoundError,ValueError):continue
  p=ROOT/'artifact-audit.tmp';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(ROOT/'artifact-audit.json')
  if result.get('finished_utc') and all(not m.get('tag') or m['model'] in report['models'] for m in result.get('models',[])):break
 time.sleep(5)
