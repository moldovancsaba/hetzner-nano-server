"""Hot-reloaded ranking policy intersected with actual installed tested artifacts."""
import copy,json,threading,time
from pathlib import Path

class SelectionError(Exception):
    def __init__(self,code,status=400):
        self.code,self.status=code,status
        super().__init__(code)

class ModelCatalog:
    def __init__(self,path,inventory):
        self.path=Path(path);self.inventory=inventory;self.lock=threading.Lock();self.cached=None;self.cached_at=0
    def policy(self):
        try:
            policy=json.loads(self.path.read_text())
            assert policy['version']=='ranked-model-policy.v1'
            for task,model in policy['defaults'].items():assert task in policy['models'][model]['tasks']
            return policy
        except Exception:raise SelectionError('model_policy_unavailable',503) from None
    def installed(self):
        with self.lock:
            if self.cached is None or time.monotonic()-self.cached_at>3:
                try:self.cached=self.inventory()['models'];self.cached_at=time.monotonic()
                except Exception:raise SelectionError('model_inventory_unavailable',503) from None
            return copy.deepcopy(self.cached)
    def records(self,allowed_tasks):
        policy=self.policy();tested={name.lower():entry for name,entry in policy['models'].items()};rows=[]
        for item in self.installed():
            entry=tested.get(item['name'].lower());eligible=entry is not None and item.get('digest')==entry['tested_digest']
            tasks={task:meta for task,meta in (entry or {}).get('tasks',{}).items() if task in allowed_tasks}
            selectable=sorted(tasks) if eligible else []
            rows.append({'id':item['name'],'object':'model','owned_by':'local','installed':True,'digest':item.get('digest'),
                         'size_bytes':item.get('size'),'selectable_for':selectable,
                         'default_for':[task for task in selectable if policy['defaults'][task].lower()==item['name'].lower()],
                         'rankings':tasks,'blocked_reason':None if selectable else 'artifact_changed_since_test' if entry and not eligible else 'not_tested_for_your_jobs'})
        return policy,rows
    def select(self,task,requested=None):
        policy=self.policy();automatic=requested is None or requested in {'auto',task}
        model=policy['defaults'][task] if automatic else requested
        if not isinstance(model,str):raise SelectionError('invalid_model')
        entry=next((entry for name,entry in policy['models'].items() if name.lower()==model.lower()),None)
        if entry is None or task not in entry['tasks']:raise SelectionError('model_not_tested_for_job')
        actual=next((x for x in self.installed() if x['name'].lower()==entry['id'].lower()),None)
        if not actual:raise SelectionError('default_model_not_installed' if automatic else 'model_not_installed',503 if automatic else 400)
        if actual.get('digest')!=entry['tested_digest']:raise SelectionError('model_artifact_changed_since_test',503)
        return {'model':actual['name'],'selection':'auto' if automatic else 'explicit','model_policy_id':policy['policy_id'],'model_digest':actual['digest'],'model_profile':entry['tasks'][task]['profile']}
    def profile(self,task,model):
        self.select(task,model)
        policy=self.policy()
        entry=next(v for k,v in policy['models'].items() if k.lower()==model.lower())
        return entry['tasks'][task]['profile']
