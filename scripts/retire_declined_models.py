"""Server-only: remove explicitly declined, inactive, unpinned weights; retain evidence."""
import argparse,datetime,json,pathlib,shutil,subprocess,urllib.request
ROOT=pathlib.Path('/opt/narimato-ai')
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:11434'+path,timeout=10) as r:return json.load(r)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
 policy=json.loads(pathlib.Path('/opt/narimato-gateway/config/model-policy.json').read_text())
 storage=json.loads((ROOT/'model-storage-policy.json').read_text());index=json.loads(pathlib.Path('/opt/narimato-discovery/tested-models.json').read_text())
 declined={row['model']:row for row in index['models'] if row.get('decision',{}).get('state')=='declined_current_environment'}
 protected=set(policy['defaults'].values())|set(storage['pinned_alternatives']);installed=get('/api/tags')['models'];active={row['name'] for row in get('/api/ps')['models']}
 plan=[row for row in installed if row['name'] in declined]
 if any(row['name'] in protected or row['name'] in active for row in plan):raise SystemExit('Refusing to delete a default, pinned or active model')
 report={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'apply':args.apply,'before_free_bytes':shutil.disk_usage('/').free,'declined':[]}
 out=ROOT/('declined-cleanup-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
 def save():
  temp=out.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');temp.chmod(0o600);temp.replace(out)
 save()
 for row in plan:
  entry={'model':row['name'],'digest':row['digest'],'reported_weight_bytes':row.get('size'),'decision':declined[row['name']]['decision'],'evidence':declined[row['name']].get('evidence',[])}
  report['declined'].append(entry);save()
  if args.apply:
   result=subprocess.run(['docker','exec','narimato-ollama','ollama','rm',row['name']],capture_output=True,timeout=120);entry['removed']=result.returncode==0
  save()
 report['after_free_bytes']=shutil.disk_usage('/').free;report['remaining_inventory']=get('/api/tags')
 save()
 print(json.dumps({'audit':str(out),'models':len(plan),'removed':sum(x.get('removed',False) for x in report['declined']),'free_gib':round(report['after_free_bytes']/1024**3,2)}))
