"""Build the English-only view without mutating historical mixed observations."""
import json,statistics

def build(root):
    source=json.loads((root/'results.json').read_text())
    extra=json.loads((root/'supplement-text.json').read_text()) if (root/'supplement-text.json').exists() else {'text':[]}
    result={'scope':'English text/chat only','source_files':['results.json','supplement-text.json'],'excluded':'hungarian_extraction and non-English chat samples','models':[]}
    for original in source['text']+extra['text']:
        model=json.loads(json.dumps(original))
        model['tests']=[case for case in model['tests'] if case['name']!='hungarian_extraction']
        model['chat_samples']=[case for case in model.get('chat_samples',[]) if case['language']=='en']
        cases=model['tests'];durations=[case['seconds'] for case in cases if case['ok']]
        model['summary']={'passed':sum(case['passed'] for case in cases),'total':len(cases),'json_valid':sum(case['json_valid'] for case in cases),'median_seconds':statistics.median(durations) if durations else None}
        result['models'].append(model)
    (root/'english-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result['models']
