"""Freeze narrow NSFW specialist evaluation; never use live Camera images."""
import hashlib,json,shutil,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1];PRIVATE=REPO/'private/camera-specialists';PRIVATE.mkdir(exist_ok=True)
manifest=json.loads((REPO/'benchmarks/vision-evaluation/moderation-manifest.json').read_text())
plan={'version':'camera-specialists.v1','threshold':0.5,'threshold_selection':'Fixed before inference; scores are not calibrated probabilities. No test-set threshold tuning.','scope':'41 frozen public research images; binary NSFW maps only to union of nudity/sexualContent, not to all Camera reasons. No explicit-sex certification or customer accuracy claim.','models':[{'model':'Falconsai/nsfw_image_detection','revision':'96cb0d0342c7afb80cab76ecc58b265fa44da256','file':'falcon.onnx','processor':'falcon/preprocessor_config.json','export':'Standard Transformers ViT FP32 export, no model-provided code'},{'model':'AdamCodd/vit-base-nsfw-detector','revision':'8587de998f441aac03fdd57a85d2e4cb808c7d64','file':'adam.onnx','processor':'adam-processor.json','artifact':'onnx/model_quantized.onnx'}]}
(ROOT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
inputs=PRIVATE/'inputs';inputs.mkdir(exist_ok=True)
for c in manifest['cases']:
 path=REPO/'private/vision-evaluation/images'/c['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==c['sha256'],c['id'];shutil.copyfile(path,inputs/c['file'])
repo='AdamCodd/vit-base-nsfw-detector';revision=plan['models'][1]['revision']
for target,source in [('adam.onnx','onnx/model_quantized.onnx'),('adam-processor.json','onnx/preprocessor_config.json')]:
 path=PRIVATE/target
 if not path.exists():urllib.request.urlretrieve('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+source,path)
print('Prepared',len(manifest['cases']),'verified research images')
