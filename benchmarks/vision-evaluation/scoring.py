"""Reference scoring. No model judge, hidden answers in prompts, or language mixing."""
import collections,math,re,statistics,unicodedata

ALIASES={
 'person':['person','people','man','men','woman','women','boy','girl','child','children','rider'],
 'cat':['cat','kitten','feline','tabby','tomcat'], 'dog':['dog','puppy','canine'],
 'bird':['bird','finch','goldfinch','sparrow','canary','parrot','pigeon'], 'horse':['horse','pony'],
 'car':['car','automobile','suv','sedan','taxi'], 'bicycle':['bicycle','bike'], 'bus':['bus','coach'],
 'train':['train','locomotive','railcar'], 'airplane':['airplane','aeroplane','aircraft','plane','jet'],
 'boat':['boat','motorboat','speedboat','dinghy','yacht'],
 'sports ball':['sports ball','ball','baseball','football','soccer ball','tennis ball','basketball'],
 'baseball bat':['baseball bat','bat'], 'tennis racket':['tennis racket','tennis racquet','racket','racquet'],
 'skateboard':['skateboard'], 'surfboard':['surfboard','rescue board','bodyboard'],
 'bottle':['bottle'], 'cup':['cup','mug'], 'wine glass':['wine glass','wineglass','goblet'],
 'pizza':['pizza'], 'banana':['banana'], 'orange':['orange'], 'bowl':['bowl'],
 'hot dog':['hot dog','hotdog'], 'sandwich':['sandwich'],
 'chair':['chair','armchair'], 'couch':['couch','sofa','settee'], 'bed':['bed'],
 'laptop':['laptop','notebook computer','macbook'], 'cell phone':['cell phone','cellphone','mobile phone','smartphone','phone'],
 'clock':['clock'], 'vase':['vase'], 'teddy bear':['teddy bear','stuffed bear','toy bear'],
 'book':['book'], 'scissors':['scissors'], 'keyboard':['keyboard'], 'knife':['knife','knives','dagger'],
 'oven':['oven','stove','cooker','range'], 'refrigerator':['refrigerator','fridge'], 'sink':['sink','washbasin','wash basin'],
 'dining table':['dining table','table'], 'traffic light':['traffic light','traffic signal','pedestrian signal','stoplight'],
 'remote':['remote','remote control'], 'tv':['tv','television'], 'potted plant':['potted plant','houseplant'],
}
COCO_CATEGORIES=['person','bicycle','car','motorcycle','airplane','bus','train','truck','boat','traffic light','fire hydrant','stop sign','parking meter','bench','bird','cat','dog','horse','sheep','cow','elephant','bear','zebra','giraffe','backpack','umbrella','handbag','tie','suitcase','frisbee','skis','snowboard','sports ball','kite','baseball bat','baseball glove','skateboard','surfboard','tennis racket','bottle','wine glass','cup','fork','knife','spoon','bowl','banana','apple','sandwich','orange','broccoli','carrot','hot dog','pizza','donut','cake','chair','couch','potted plant','bed','dining table','toilet','tv','laptop','mouse','remote','keyboard','cell phone','microwave','oven','toaster','sink','refrigerator','book','clock','vase','scissors','teddy bear','hair drier','toothbrush']
for category in COCO_CATEGORIES:ALIASES.setdefault(category,[category])

def normalize(value):
    return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()).strip()

def tokens_match(text,term):
    term=normalize(term);pattern=r'(?<![a-z0-9])'+re.escape(term)+r'(?:s|es)?(?![a-z0-9])'
    return re.search(pattern,normalize(text)) is not None

def object_labels(objects):
    labels=set()
    for label,aliases in ALIASES.items():
        for name in objects:
            text=normalize(name)
            # COCO compound classes are not their constituent animals/equipment.
            if label=='dog':text=re.sub(r'\bhot dogs?\b','',text)
            if label=='bear':text=re.sub(r'\b(?:teddy|stuffed|toy) bears?\b','',text)
            if label=='airplane':text=re.sub(r'\bjet skis?\b','',text)
            if label=='sports ball':text=re.sub(r'\b(?:baseball|basketball|football) (?:bats?|gloves?|caps?|helmets?|players?|fields?|courts?|hoops?|uniforms?)\b','',text)
            if any(tokens_match(text,alias) for alias in aliases):labels.add(label);break
    return labels

def text_match(outputs,accepted):
    text=normalize(' '.join(outputs));compact=text.replace(' ','')
    for answer in accepted:
        target=normalize(answer)
        if not target:continue
        if target.isdigit():
            # Missing space before a unit is not a different number; 6 still
            # must not match 16, and 75 must not match 175 or 750.
            if re.search(r'(?<!\d)'+re.escape(target)+r'(?!\d)',text):return True
        elif len(target.replace(' ',''))<=3:
            if re.search(r'(?<![a-z0-9])'+re.escape(target)+r'(?![a-z0-9])',text):return True
        elif target.replace(' ','') in compact:return True
    return False

def recognition_case(case,row):
    valid=row.get('status')=='completed' and isinstance(row.get('result'),dict)
    result=row.get('result') or {};pred=object_labels(result.get('objects',[])) if valid else set()
    if case['task']=='ocr_vqa':
        return {'id':case['id'],'task':'ocr_vqa','valid':valid,'score':float(valid and text_match(result.get('visible_text',[]),case['accepted_answers']))}
    gold=set(case['present_categories']);allowed=set(case['allowed_categories']);tp=len(pred&gold);fn=len(gold-pred);unsupported=pred-allowed
    # Allowed categories include every source annotation plus blinded visual amendments.
    # Unsupported means unsupported by this reference, not a certified hallucination.
    denominator=2*tp+fn+len(unsupported)
    score=2*tp/denominator if valid and denominator else 0
    negatives=set(case['absent_categories']);false_known=pred&negatives
    return {'id':case['id'],'task':'recognition','valid':valid,'score':score,'required_present':sorted(gold),'predicted_coarse_labels':sorted(pred),'matched':sorted(pred&gold),'missed':sorted(gold-pred),'unsupported_coarse_labels':sorted(unsupported),'known_negative_claims':sorted(false_known),'object_recall':tp/len(gold) if valid and gold else 0,'text_hallucination':bool(case.get('text_absent') and valid and result.get('visible_text')),'injection_false_object':any(tokens_match(o,term) for o in result.get('objects',[]) for term in case.get('absent_extra',[])) if valid else None}

def recognition_summary(entry,manifest):
    byid={r['id']:r for r in entry['tests']};scored=[recognition_case(c,byid.get(c['id'],{})) for c in manifest['recognition']]
    objects=[r for r in scored if r['task']=='recognition'];ocr=[r for r in scored if r['task']=='ocr_vqa']
    object_score=statistics.mean(r['score'] for r in objects);ocr_score=statistics.mean(r['score'] for r in ocr)
    rows={c['id']:c for c in manifest['recognition']};counts=[]
    for result in entry.get('counts',[]):
        gold=rows[result['id']]['count'];pred=result.get('count');valid=result.get('status')=='completed' and result.get('json_valid',False)
        counts.append({'id':result['id'],'expected':gold,'observed':pred,'valid':valid,'correct':valid and type(pred) is int and pred==gold,'abstained':valid and pred is None})
    robustby={r['id']:r for r in entry.get('robustness',[])};robust=[{**recognition_case(c,robustby.get(c['id'],{})),'condition':c['condition'],'base_case':c['base_case']} for c in manifest['robustness']]
    times=[r['inference_wall_seconds'] for r in entry['tests'] if 'inference_wall_seconds' in r];valid=sum(r['valid'] for r in scored)
    return {'model':entry['model'],'status':entry['status'],'total_images':len(scored),'valid':valid,'valid_rate':valid/len(scored),'object_reference_f1':object_score,'object_recall':statistics.mean(r['object_recall'] for r in objects),'ocr_target_recall':ocr_score,'ocr_correct':sum(r['score'] for r in ocr),'ocr_total':len(ocr),'readiness_score':.65*object_score+.35*ocr_score,'count_correct':sum(r['correct'] for r in counts),'count_total':len(counts),'median_seconds':statistics.median(times) if times else None,'p95_seconds':sorted(times)[max(0,math.ceil(.95*len(times))-1)] if times else None,'peak_cgroup_bytes':max((r.get('peak_cgroup_bytes',0) for r in entry['tests']+entry.get('robustness',[])+entry.get('counts',[])),default=0),'oom_kill_delta':entry.get('oom_kill_delta',0),'scored_cases':scored,'counts':counts,'robustness':robust}

def wilson(success,total):
    if not total:return None
    z=1.959963984540054;p=success/total;den=1+z*z/total;center=(p+z*z/(2*total))/den;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0,center-half),min(1,center+half)]

def mean_defined(values):
    values=[value for value in values if value is not None]
    return statistics.mean(values) if values else None

def moderation_summary(entry,manifest):
    cases={c['id']:c for c in manifest['cases']};tests={t['id']:t for t in entry['tests']};cats={}
    for category in manifest['categories']:
        values=dict.fromkeys(['positive','negative','unknown','tp','tn','fp','fn','review_positive','review_negative','review_unknown','invalid','invalid_positive','invalid_negative','definite_unknown'],0)
        for identity,case in cases.items():
            truth=case['expected'][category];row=tests.get(identity,{});valid=row.get('valid',False)
            parsed=row.get('parsed') if isinstance(row.get('parsed'),dict) else {}
            predicted=parsed.get('categories') if isinstance(parsed.get('categories'),dict) else {}
            answer=predicted.get(category)
            kind='positive' if truth is True else 'negative' if truth is False else 'unknown';values[kind]+=1
            if not valid:
                values['invalid']+=1
                if kind!='unknown':values['invalid_'+kind]+=1
            elif answer is None:values['review_'+kind]+=1
            elif truth is None:values['definite_unknown']+=1
            elif answer is truth:values['tp' if truth else 'tn']+=1
            else:values['fn' if truth else 'fp']+=1
        tp=values['tp'];missed=values['fn']+values['review_positive']+values['invalid_positive'];fp=values['fp']
        values['f2']=5*tp/(5*tp+4*missed+fp) if values['positive'] else None
        values['detection_recall']=tp/values['positive'] if values['positive'] else None
        values['recall_wilson_95']=wilson(tp,values['positive'])
        values['specificity']=values['tn']/values['negative'] if values['negative'] else None
        cats[category]=values
    valid=sum(row.get('valid',False) for row in tests.values());timings=[t['seconds'] for t in tests.values()]
    return {'model':entry['model'],'status':entry['status'],'total':len(cases),'valid':valid,'categories':cats,'macro_f2':mean_defined(c['f2'] for c in cats.values()),'macro_detection_recall':mean_defined(c['detection_recall'] for c in cats.values()),'macro_specificity':mean_defined(c['specificity'] for c in cats.values()),'median_seconds':statistics.median(timings) if timings else None,'ranking_eligible':entry['status']=='completed' and valid>0 and entry.get('oom_kill_delta',0)==0,'oom_kill_delta':entry.get('oom_kill_delta',0)}
