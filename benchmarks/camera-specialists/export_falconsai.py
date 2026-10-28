"""Export pinned public weights with the installed standard Transformers ViT implementation."""
import hashlib,json
from pathlib import Path
import torch
from transformers import AutoImageProcessor,AutoModelForImageClassification
ROOT=Path(__file__).resolve().parents[2]/'private/camera-specialists';ROOT.mkdir(parents=True,exist_ok=True)
repo='Falconsai/nsfw_image_detection';revision='96cb0d0342c7afb80cab76ecc58b265fa44da256'
model=AutoModelForImageClassification.from_pretrained(repo,revision=revision,trust_remote_code=False).eval()
processor=AutoImageProcessor.from_pretrained(repo,revision=revision,trust_remote_code=False);processor.save_pretrained(ROOT/'falcon')
class Logits(torch.nn.Module):
 def __init__(self,model):super().__init__();self.model=model
 def forward(self,pixel_values):return self.model(pixel_values=pixel_values).logits
path=ROOT/'falcon.onnx'
with torch.no_grad():torch.onnx.export(Logits(model),torch.zeros(1,3,224,224),str(path),input_names=['pixel_values'],output_names=['logits'],opset_version=17,dynamo=False)
(ROOT/'falcon-export.json').write_text(json.dumps({'model':repo,'revision':revision,'onnx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'torch':torch.__version__,'labels':model.config.id2label},indent=2)+'\n')
print('Exported',path.stat().st_size,flush=True)
