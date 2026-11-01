"""Compare recorded ARM64 predictions to the original timm implementation offline."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PRIVATE=ROOT.parents[1]/'private/camera-specialists-round2'
os.environ['HF_HOME']=str(PRIVATE/'source-cache')
import torch,timm,numpy as np
from safetensors.torch import load_file
from huggingface_hub import hf_hub_download
from PIL import Image
p=json.loads((ROOT/'plan.json').read_text());r=json.loads((ROOT/'results.json').read_text())
assert r.get('finished_utc') and r.get('restore')
weight=Path(hf_hub_download(p['model'],p['weights']['name'],revision=p['revision'],local_files_only=True));assert hashlib.sha256(weight.read_bytes()).hexdigest()==p['weights']['sha256']
torch.set_num_threads(2);model=timm.create_model(p['architecture'],pretrained=False,num_classes=2).eval();model.load_state_dict(load_file(weight),strict=True)
transform=timm.data.create_transform(input_size=(3,384,384),interpolation='bicubic',crop_pct=1.0,mean=(.5,.5,.5),std=(.5,.5,.5),is_training=False)
recorded={t['id']:t for t in r['models'][0]['tests']};checks=[]
for case in json.loads((ROOT/'manifest.json').read_text())['cases']:
 im=Image.open(ROOT.parents[1]/'private/vision-evaluation/images'/case['file']).convert('RGB')
 with torch.no_grad():score=float(model(transform(im).unsqueeze(0)).softmax(-1)[0,p['nsfw_index']])
 row=recorded[case['id']];error=abs(score-row['nsfw_score']);assert error<1e-5,(case['id'],error)
 assert row['detected']==(score>=p['threshold'])
 checks.append({'id':case['id'],'absolute_score_error':error,'decision_matched':True})
(ROOT/'server-parity.json').write_text(json.dumps({'passed':True,'images':len(checks),'maximum_score_error':max(c['absolute_score_error'] for c in checks),'reference':'Original timm CPU scores versus recorded Hetzner ARM64 ONNX results; no additional server inference','checks':checks},indent=2)+'\n')
print('41/41 recorded server predictions match original model')
