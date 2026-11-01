"""Pinned safetensors to ONNX using standard timm; no repository code execution."""
import hashlib, json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PRIVATE=ROOT.parents[1]/'private/camera-specialists-round2'
os.environ['HF_HOME']=str(PRIVATE/'source-cache')
import numpy as np
import torch, timm, onnxruntime as ort
from safetensors.torch import load_file
from huggingface_hub import hf_hub_download
from PIL import Image
plan=json.loads((ROOT/'plan.json').read_text()); torch.set_num_threads(2)
weight=Path(hf_hub_download(plan['model'],plan['weights']['name'],revision=plan['revision']))
assert hashlib.sha256(weight.read_bytes()).hexdigest()==plan['weights']['sha256']
model=timm.create_model(plan['architecture'],pretrained=False,num_classes=2).eval()
model.load_state_dict(load_file(weight),strict=True)
path=PRIVATE/'marqo.onnx'
with torch.no_grad():
 torch.onnx.export(model,torch.zeros(1,3,384,384),str(path),input_names=['pixel_values'],output_names=['logits'],opset_version=17,dynamo=False)
# Use the publisher's declared timm preprocessing as the reference.
reference=timm.data.create_transform(input_size=(3,384,384),interpolation='bicubic',crop_pct=1.0,mean=(.5,.5,.5),std=(.5,.5,.5),is_training=False)
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
rows=[]
for case in json.loads((ROOT/'manifest.json').read_text())['cases']:
 image_path=ROOT.parents[1]/'private/vision-evaluation/images'/case['file']
 assert hashlib.sha256(image_path.read_bytes()).hexdigest()==case['sha256']
 image=Image.open(image_path).convert('RGB'); x=reference(image).unsqueeze(0)
 with torch.no_grad(): expected=model(x).numpy()
 actual=session.run(None,{'pixel_values':x.numpy()})[0]
 error=float(np.max(np.abs(expected-actual)))
 assert np.allclose(expected,actual,rtol=1e-4,atol=1e-4), (case['id'],error)
 rows.append({'id':case['id'],'maximum_logit_error':error})
audit={'model':plan['model'],'revision':plan['revision'],'source_sha256':plan['weights']['sha256'],'onnx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'onnx_bytes':path.stat().st_size,'torch':torch.__version__,'timm':timm.__version__,'onnxruntime':ort.__version__,'labels':plan['label_names'],'preprocessing':plan['preprocessing'],'parity_images':len(rows),'maximum_logit_error':max(r['maximum_logit_error'] for r in rows),'checks':rows,'scope':'Export parity only, local Mac CPU; benchmark latency measured separately on ARM64 Hetzner.'}
(ROOT/'export-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print('Export verified on',len(rows),'public research images',flush=True)
