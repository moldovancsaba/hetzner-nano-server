"""Build a frozen follow-up using the original Hungarian cases and synthetic role probes."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
original=ROOT.parent/'hu-round1/fixtures.json'
d=json.loads(original.read_text());d['prior_fixture_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
# These are synthetic developer-authored examples, not customer conversations.
tree=ast.parse(Path('/Users/Shared/Projects/habi/worker/evaluations/hungarian_route.py').read_text())
cases=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CASES' for t in n.targets))
for name,prompt in cases:
 d['cases'].append({'id':'habi-'+name,'kind':'client_regression','prompt':prompt,'criteria':['Assistant addresses the coach about Csaba, without claiming to be the coach or Csaba.','Preserves stated temporal scope and correction; does not fabricate a date, cause or fact.','Concise natural Hungarian response to the latest message.']})
d['followup_scope']='Original frozen 24 structured + 6 chat cases; five separate synthetic Habi regressions, not part of original gate.'
(ROOT/'fixtures.json').write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
plan={'scope':'Hungarian-only Apertus Mini follow-up; no English/default changes without passing the original gate.','models':['hf.co/mradermacher/Apertus-v1.1-0.5B-Instruct-GGUF:Q4_K_M','hf.co/mradermacher/Apertus-v1.1-1.5B-Instruct-GGUF:Q4_K_M'],'settings':{'num_ctx':4096,'num_batch':8,'num_predict':192,'temperature':0,'memory_mib':2800},'model_profiles':{},'provenance':{'0.5B':{'upstream':'swiss-ai/Apertus-v1.1-0.5B-Instruct','upstream_revision':'a140fd61fb57422c36a26301caea17edee799874','gguf_revision':'31edc86ab60e89f4f9ce18a0549ab6f2fc0cf7dc'},'1.5B':{'upstream':'swiss-ai/Apertus-v1.1-1.5B-Instruct','upstream_revision':'9e9d01154446a645d30f04174cf1515a38058be7','gguf_revision':'cec44a8c27def2fad9785a3c6a8209f8d6fbda30'}}}
(ROOT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Frozen',len(d['cases']),'cases')
