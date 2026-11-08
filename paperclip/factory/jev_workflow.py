"""Factory-owned probability assistance; existing authorization remains binding."""
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
from workflow_partner import WorkflowPartner,sha
CONFIG=Path('/etc/jev-paperclip.json')

def partner():return WorkflowPartner(json.loads(CONFIG.read_text()) if CONFIG.exists() else {'mode':'off'})

def check(database,packet,kind,proof,pages,identity_name=None):
    p=partner()
    if p.mode=='off':return {'state':'off'}
    case=None
    # One bounded field per gate check; never average into a page-safety probability.
    labels={'name':'The provider is named {}.','activities':'The provider offers these activities: {}.','price':'The stated price information is: {}.','opening_hours':'The stated opening hours are: {}.'}
    facts=list(proof.get('facts',[]))
    if identity_name and isinstance(identity_name,str):
        for page in pages:
            start=page.get('text','').find(identity_name)
            if start>=0:facts.append({'field':'name','value':identity_name,'quote':page['text'][max(0,start-100):start+len(identity_name)+200]});break
    for fact in facts:
        field=fact.get('field');quote=fact.get('quote','');value=fact.get('value')
        if field not in labels or not isinstance(quote,str) or not 1<=len(quote)<=8000 or not isinstance(value,str) or not value or re.search(r'@|Bearer\s|sk_[A-Za-z0-9]',quote):continue
        source=next((page for page in pages if quote in page.get('text','')),None)
        if not source:continue
        fetched=float(source['fetched_at'])
        if not 0<=time.time()-fetched<3600:raise ValueError('JEV evidence not checked: source expired')
        case=p.assess(operation=kind,reference=packet,url=source['url'],quote=quote,claim=labels[field].format(value),retrieved_at=datetime.fromtimestamp(fetched,timezone.utc).isoformat(),source_version=source['sha256'])
        break
    if case is None:raise ValueError('Automatic quality hold: JEV requires an eligible original fact quote for additional evidence review')
    with database() as db:
        db.execute('CREATE TABLE IF NOT EXISTS jev_workflow_cases(packet TEXT PRIMARY KEY,case_json TEXT,updated REAL)')
        db.execute('INSERT INTO jev_workflow_cases VALUES(?,?,?) ON CONFLICT(packet) DO UPDATE SET case_json=excluded.case_json,updated=excluded.updated',(packet,json.dumps(case),time.time()))
    if case['additional_evidence']:raise ValueError('Automatic quality hold: JEV evidence support below client threshold or not checked; research this fact before retry')
    return {'state':case['state'],'model_version':case.get('receipt',{}).get('model_version'),'policy_version':case['policy_version']}

def outcome(database,packet,state):
    p=partner()
    if p.mode=='off':return
    with database() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='jev_workflow_cases'").fetchone():return
        row=db.execute('SELECT case_json FROM jev_workflow_cases WHERE packet=?',(packet,)).fetchone()
    if row:p.record(json.loads(row[0]),state)
