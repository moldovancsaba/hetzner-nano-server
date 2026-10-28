"""Check exported Falconsai logits and preprocessing against pinned source on synthetic inputs."""
import json
from pathlib import Path
import numpy as np,onnxruntime as ort,torch
from PIL import Image
from transformers import AutoImageProcessor,AutoModelForImageClassification
p=Path(__file__).resolve().parents[2]/'private/camera-specialists'
revision='96cb0d0342c7afb80cab76ecc58b265fa44da256'
model=AutoModelForImageClassification.from_pretrained('Falconsai/nsfw_image_detection',revision=revision,trust_remote_code=False).eval()
processor=AutoImageProcessor.from_pretrained('Falconsai/nsfw_image_detection',revision=revision,trust_remote_code=False,use_fast=False)
s=ort.InferenceSession(str(p/'falcon.onnx'),providers=['CPUExecutionProvider']);rows=[]
for seed in [11,29]:
 image=Image.fromarray(np.random.default_rng(seed).integers(0,256,(301,251,3),dtype=np.uint8));pixels=processor(images=image,return_tensors='pt')['pixel_values']
 manual=np.asarray(image.resize((224,224),Image.Resampling.BILINEAR),dtype=np.float32)/255;manual=(manual-.5)/.5;manual=manual.transpose(2,0,1)[None]
 with torch.no_grad():gold=model(pixel_values=pixels).logits.numpy()
 output=s.run(None,{'pixel_values':manual})[0];delta=float(np.max(np.abs(output-gold)));prep=float(np.max(np.abs(pixels.numpy()-manual)))
 rows.append({'seed':seed,'max_logit_error':delta,'max_preprocessor_error':prep});assert delta<1e-4 and prep<1e-6
out={'source_revision':revision,'synthetic_only':True,'checks':rows,'passed':True};(Path(__file__).resolve().parent/'export-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
