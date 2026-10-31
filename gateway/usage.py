"""Durable model-demand metadata, never prompts, images, outputs or identities."""
import json,os,threading,time
from pathlib import Path

class UsageStore:
    def __init__(self,path,inventory=()):
        self.path=Path(path);self.lock=threading.Lock();self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists():self.read()
        else:
            self.save({'version':'model-usage.v1','tracking_started_at':time.time(),
                       'bootstrap_inventory':{row['name']:row.get('digest') for row in inventory},'models':{}})
    def read(self):
        data=json.loads(self.path.read_text())
        if data.get('version')!='model-usage.v1' or not isinstance(data['models'],dict):raise ValueError('Invalid usage store')
        return data
    def save(self,data):
        tmp=self.path.with_suffix('.tmp')
        with tmp.open('w') as handle:
            os.chmod(tmp,0o600);json.dump(data,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        tmp.replace(self.path)
        descriptor=os.open(self.path.parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    def record(self,model,digest,purpose):
        if purpose=='test':return
        with self.lock:
            data=self.read();previous=data['models'].get(model,{})
            data['models'][model]={'last_valid_request_at':time.time(),'production_requests':previous.get('production_requests',0)+1,'digest':digest}
            self.save(data)

class LeaseStore(UsageStore):
    """Private maintenance lease survives gateway restart while a deletion is in flight.

    Only the inherited atomic save() is used. read() and record() do not apply to a lease file (its format is
    not model-usage.v1); load() is its reader.
    """
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
    def load(self):
        if not self.path.exists():return None
        value=json.loads(self.path.read_text())
        if value is not None:
            if not isinstance(value,dict) or not isinstance(value.get('lease'),str) or not isinstance(value.get('expires_at'),(int,float)):
                raise ValueError('Invalid maintenance state')
        return value
