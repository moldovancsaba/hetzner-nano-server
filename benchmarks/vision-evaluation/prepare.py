"""Prepare a deterministic private evaluation subset; never import live Camera data."""
import base64,collections,hashlib,json,pathlib,random,sys,urllib.request
from concurrent.futures import ThreadPoolExecutor
ROOT=pathlib.Path(__file__).resolve().parents[2];PRIVATE=ROOT/'private/vision-evaluation';OUT=PRIVATE/'images';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from moderation.server import normalize_image
from PIL import Image,ImageDraw
SEED=20261028
source=json.loads((PRIVATE/'instances_val2017.json').read_text());cats={x['id']:x['name'] for x in source['categories']};byname={v:k for k,v in cats.items()};annotations=collections.defaultdict(list)
for a in source['annotations']:annotations[a['image_id']].append(a)
licenses={x['id']:x for x in source['licenses']};rng=random.Random(SEED);images=source['images'].copy();rng.shuffle(images)
targets=['cat','dog','bird','horse','car','bicycle','bus','train','sports ball','tennis racket','skateboard','surfboard','bottle','cup','pizza','banana','chair','couch','bed','laptop','cell phone','clock','vase','teddy bear']
cases=[];used=set()
for target in targets:
    candidates=[]
    for image in images:
        if image['id'] in used or image['license'] not in [4,5]:continue
        aa=annotations[image['id']];group=[a for a in aa if a['category_id']==byname[target]];size=image['width']*image['height']
        if not group or len(group)>5 or len(aa)>25 or any(a.get('iscrowd') for a in aa):continue
        if min(a['bbox'][2]*a['bbox'][3]/size for a in group)<.012:continue
        candidates.append(image)
    assert candidates, 'No eligible image for '+target
    image=candidates[0];used.add(image['id']);aa=annotations[image['id']];area=image['width']*image['height'];present={cats[a['category_id']] for a in aa}
    major=sorted({cats[a['category_id']] for a in aa if a['bbox'][2]*a['bbox'][3]/area>=.04})
    negatives=[c for c in ['cat','dog','elephant','airplane','bus','bicycle','banana','laptop'] if c not in present];rng.shuffle(negatives)
    cases.append({'id':'coco-'+str(image['id']),'task':'recognition','phase':'selection' if len(cases)<6 else 'holdout','file':'coco-'+str(image['id'])+'.jpg','source':'COCO2017 validation','source_id':image['id'],'source_url':image['flickr_url'],'download_url':'https://huggingface.co/datasets/merve/coco/resolve/main/val2017/'+image['file_name'],'license':licenses[image['license']],'primary_object':target,'count':len([a for a in aa if cats[a['category_id']]==target]),'present_categories':major,'allowed_categories':sorted(present),'absent_categories':negatives[:3],'label_status':'source_annotation_pending_visual_review'})

vqa=json.loads((PRIVATE/'textvqa-val.json').read_text())['data'];rng.shuffle(vqa);ocr=[];used=set()
for row in vqa:
    answers=collections.Counter(a.strip().lower() for a in row['answers']);answer,n=answers.most_common(1)[0]
    if n<6 or len(answer)>35 or row['image_id'] in used:continue
    if not any(k in row['question'].lower() for k in ['brand','written','word','number','name','sign','text','letter','label','year','say','read']):continue
    if not answer.isascii() or not any(c.isalnum() for c in answer) or answer in ['yes','no','none','nothing','unanswerable']:continue
    used.add(row['image_id']);ocr.append({'id':'textvqa-'+str(row['question_id']),'task':'ocr_vqa','phase':'selection' if len(ocr)<2 else 'holdout','file':'textvqa-'+str(row['question_id'])+'.jpg','source':'TextVQA 0.5.1 validation / OpenImages','source_id':row['question_id'],'source_url':row['flickr_original_url'],'download_url':row['flickr_300k_url'],'fallback_url':'https://s3.amazonaws.com/open-images-dataset/train/'+row['image_id']+'.jpg','license':{'name':'TextVQA CC BY 4.0; source OpenImages/Flickr image rights apply','url':'https://textvqa.org/textvqa/dataset/'},'question':row['question'],'answers':dict(answers),'majority_answer':answer,'label_status':'source_consensus_pending_visual_review'})
    if len(ocr)==8:break
cases+=ocr
def download(case):
    target=OUT/case['file']
    if target.exists():return
    error=None
    for url in [case['download_url'],case.get('fallback_url')]:
        if not url:continue
        try:
            with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(12*1024*1024)
            # Normalize using the real service preprocessing; full originals are not retained.
            data,_,_=normalize_image(base64.b64encode(raw).decode());target.write_bytes(data);return
        except Exception as e:error=type(e).__name__
    raise RuntimeError(case['id']+' download failed '+str(error))
with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download,cases))
for case in cases:
    case.pop('download_url',None);case.pop('fallback_url',None);case['sha256']=hashlib.sha256((OUT/case['file']).read_bytes()).hexdigest()
manifest={'version':'vision-evaluation.v1','seed':SEED,'purpose':'evaluation only; no training approval','recognition':cases,'moderation':[],'label_review':'Pending; freeze reviewed labels before candidate inference.'}
(PRIVATE/'manifest-draft.json').write_text(json.dumps(manifest,indent=2)+'\n')
for start in range(0,len(cases),8):
    sheet=Image.new('RGB',(1200,720),'white');draw=ImageDraw.Draw(sheet)
    for i,c in enumerate(cases[start:start+8]):
        im=Image.open(OUT/c['file']);im.thumbnail((290,290));x=(i%4)*300;y=(i//4)*360;sheet.paste(im,(x,y));text=c['id']+' '+c.get('primary_object',c.get('majority_answer',''))+' '+str(c.get('count',''));draw.text((x+3,y+295),text,fill='black');draw.text((x+3,y+315),str(c.get('present_categories',c.get('question','')))[:45],fill='black')
    sheet.save(PRIVATE/f'review-recognition-{start//8}.jpg')
print('Prepared',len(cases),'distinct recognition/OCR images, pending label review.')
