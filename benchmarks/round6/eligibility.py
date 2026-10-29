"""Independent suite completion; another language/task cannot invalidate a completed suite."""
def english_complete(entry):
 return entry.get('english_status',entry.get('status'))=='completed' and len(entry.get('tests',[]))==14

def recognition_complete(entry):
 return all(len(entry.get(field,[]))==count and not any(t.get('oom_kill_delta',0) for t in entry.get(field,[])) for field,count in [('tests',32),('robustness',9),('counts',8)])

def moderation_complete(entry):
 return len(entry.get('moderation',[]))==41 and not any(t.get('oom_kill_delta',0) for t in entry.get('moderation',[]))
