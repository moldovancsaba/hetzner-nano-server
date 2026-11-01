"""Score the corrected continuation separately; leave historical results immutable."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'vision-evaluation'))
from scoring import recognition_summary, moderation_summary
from eligibility import recognition_complete, moderation_complete
r = json.loads((ROOT/'internvl-completion.json').read_text())
assert r.get('finished_utc') and r.get('restore', {}).get('ok'), 'Unfinished or unrestored run'
m = r['model']
recognition = recognition_summary({**m, 'status': 'completed' if recognition_complete(m) else 'failed'}, json.loads((ROOT/'recognition-manifest.json').read_text()))
moderation = None
if m.get('moderation'):
    moderation = moderation_summary({**m, 'tests': m['moderation'], 'status': 'completed' if moderation_complete(m) else 'failed'}, json.loads((ROOT/'moderation-manifest.json').read_text()))
summary = {'version': r['version'], 'started_utc': r['started_utc'], 'finished_utc': r['finished_utc'],
           'original_sha256': r['original_sha256'], 'recognition': recognition, 'moderation': moderation,
           'recognition_eligible': recognition_complete(m), 'moderation_eligible': moderation_complete(m),
           'scope': 'Same frozen public research suites; first nine cases preserved. Corrected continuation, no new model checkpoint. No twelve-reason/video claim.'}
(ROOT/'internvl-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({k: summary[k] for k in ['recognition_eligible','moderation_eligible']}))
