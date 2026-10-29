"""Export only this batch's public business draft facts and quality evidence."""
import json,sqlite3,pathlib
root=pathlib.Path('/opt/narimato-factory');batch=json.loads((root/'batch-20261028.json').read_text());db=sqlite3.connect('/var/lib/narimato-factory/factory.sqlite3');db.row_factory=sqlite3.Row
rework_path=root/'rework-bmf-20261028.json'
if rework_path.exists():
 rework=json.loads(rework_path.read_text())
 if rework.get('quality_status')=='in_review':
  p=next(p for p in batch['providers'] if p['name']=='Brooklyn Music Factory');p['previous_attempt']={k:p.get(k) for k in ['research_id','research_identifier','quality_id','quality_identifier','draft_id','url']};p.update({k:rework[k] for k in ['research_id','research_identifier','research_status','quality_id','quality_identifier','quality_status','draft_id','url']});p['rework_reason']=rework['previous_result']
for p in batch['providers']:
 if not p.get('draft_id'):continue
 row=db.execute('SELECT id,name,status,source_url,updated_at FROM entities WHERE id=?',(p['draft_id'],)).fetchone()
 if row:
  draft=dict(row);draft['facts']=[dict(x) for x in db.execute('SELECT f.field,f.value,f.quote,s.url,s.sha256,s.fetched_at FROM facts f JOIN sources s ON s.id=f.source_id WHERE f.entity_id=? ORDER BY f.field',(p['draft_id'],))];p['draft']=draft
 row=db.execute('SELECT report FROM quality_reviews WHERE entity_id=? ORDER BY created_at DESC LIMIT 1',(p['draft_id'],)).fetchone()
 if row:p['quality_review']=json.loads(row['report'])
 runs=db.execute('SELECT role,status,started_at,finished_at,result,error FROM runs WHERE issue_id IN (?,?) ORDER BY started_at',(p['research_id'],p.get('quality_id',''))).fetchall();p['runs']=[dict(x) for x in runs]
(root/'batch-20261028-export.json').write_text(json.dumps(batch,indent=2)+'\n');print(json.dumps({'batch':batch['parent']['identifier'],'status':batch['status'],'providers':len(batch['providers']),'drafts':sum('draft' in p for p in batch['providers'])}))
