"""Download public research candidates for blinded manual moderation-label review."""
import base64,csv,hashlib,io,json,pathlib,sys,urllib.request
from concurrent.futures import ThreadPoolExecutor
ROOT=pathlib.Path(__file__).resolve().parents[2];PRIVATE=ROOT/'private/vision-evaluation';OUT=PRIVATE/'images';sys.path.insert(0,str(ROOT))
from moderation.server import normalize_image
from PIL import Image,ImageDraw
rows=list(csv.DictReader((PRIVATE/'moderation-source.csv').open()));old={c['file'] for c in json.loads((ROOT/'benchmarks/moderation/manifest.json').read_text())['cases']};chosen=[];seen=set()
for category,count in [('alcohol',6),('drugs',6),('weapons',6),('violence',6),('nudity',8)]:
    eligible=[r for r in rows if r[category]=='1' and r['name'] not in old and r['name'] not in seen and (category!='violence' or r['weapons']=='0')]
    for row in eligible[:count]:
        seen.add(row['name']);chosen.append({'id':'harmful-'+row['name'].split('.')[0],'file':'harmful-'+row['name'].split('.')[0]+'.jpg','source':'onullusoy/harmful-contents test split; research/noncommercial','source_url':'https://huggingface.co/datasets/onullusoy/harmful-contents','source_file':row['name'],'download_url':'https://huggingface.co/datasets/onullusoy/harmful-contents/resolve/main/data/test/'+row['name'],'source_labels':{k:row[k] for k in ['alcohol','drugs','weapons','nudity','sexy','violence']},'selection_stratum':category,'label_status':'pending_blinded_visual_review'})
commons=json.loads((PRIVATE/'commons-gestures.json').read_text())
for page in commons.get('query',{}).get('pages',{}).values():
    if page['title'] not in ['File:The gesture02.jpg','File:Woman showing middle finger.jpg','File:Middle finger and plastic cups.jpg']:continue
    info=page['imageinfo'][0];meta=info.get('extmetadata',{});idx=str(page['pageid'])
    chosen.append({'id':'commons-'+idx,'file':'commons-'+idx+'.jpg','source':'Wikimedia Commons photograph','source_url':info.get('descriptionurl'),'download_url':info.get('thumburl',info['url']),'license':{k:meta.get(k,{}).get('value') for k in ['LicenseShortName','LicenseUrl','Artist','Credit']},'selection_stratum':'middleFinger','label_status':'pending_blinded_visual_review'})
def download(case):
    path=OUT/case['file']
    if path.exists():return
    req=urllib.request.Request(case['download_url'],headers={'User-Agent':'HabigoalResearch/1.0 (image evaluation)'})
    with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(12*1024*1024)
    im=Image.open(io.BytesIO(raw));im.thumbnail((640,640));buffer=io.BytesIO();im.convert('RGB').save(buffer,format='JPEG',quality=95)
    data,_,_=normalize_image(base64.b64encode(buffer.getvalue()).decode());path.write_bytes(data)
def guarded(case):
    try:download(case);return None
    except Exception as error:return {'id':case['id'],'error_type':type(error).__name__}
with ThreadPoolExecutor(max_workers=4) as pool:excluded=[x for x in pool.map(guarded,chosen) if x]
(PRIVATE/'moderation-download-exclusions.json').write_text(json.dumps(excluded,indent=2)+'\n')
chosen=[c for c in chosen if (OUT/c['file']).exists()]
for case in chosen:case.pop('download_url',None);case['sha256']=hashlib.sha256((OUT/case['file']).read_bytes()).hexdigest()
(PRIVATE/'moderation-draft.json').write_text(json.dumps(chosen,indent=2)+'\n')
for start in range(0,len(chosen),8):
    sheet=Image.new('RGB',(1200,720),'white');draw=ImageDraw.Draw(sheet)
    for i,case in enumerate(chosen[start:start+8]):
        im=Image.open(OUT/case['file']);im.thumbnail((290,290));x=i%4*300;y=i//4*360;sheet.paste(im,(x,y));draw.text((x+3,y+300),case['id']+' '+case['selection_stratum'],fill='black')
    sheet.save(PRIVATE/f'review-moderation-{start//8}.jpg')
print('Prepared',len(chosen),'new moderation research candidates; not labelled yet.')
