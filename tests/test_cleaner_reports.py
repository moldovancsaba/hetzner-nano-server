"""Tests for pruning the cleaner's own reports: old cleanup-<UTC>.json files go, latest.json and any report that
removed a model stay, a dry run prunes nothing, and the retention value is validated and shipped in the policy."""
import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from storage import cleaner
from storage.cleaner import prune_reports,validate_storage,REPORT_DAYS

ROOT=Path(__file__).resolve().parent.parent
DAY=86400


def write(path,report,age_days,now):
    path.write_text(json.dumps(report));os.utime(path,(now-age_days*DAY,now-age_days*DAY))


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name);self.now=time.time()
    def tearDown(self):self.tmp.cleanup()
    def names(self):return sorted(p.name for p in self.state.iterdir())

    def test_old_reports_are_deleted_and_recent_ones_kept(self):
        write(self.state/'cleanup-old.json',{'models':[{'model':'a','decision':'keep'}]},31,self.now)
        write(self.state/'cleanup-edge.json',{'models':[]},29.9,self.now)
        write(self.state/'cleanup-new.json',{'models':[]},0,self.now)
        self.assertEqual(prune_reports(self.state,30,self.now),1)
        self.assertEqual(self.names(),['cleanup-edge.json','cleanup-new.json'])

    def test_latest_and_unrelated_files_are_never_touched(self):
        for name in ['latest.json','notes.txt','cleanup-old.tmp']:write(self.state/name,{},400,self.now)
        self.assertEqual(prune_reports(self.state,30,self.now),0)
        self.assertEqual(self.names(),['cleanup-old.tmp','latest.json','notes.txt'])

    def test_a_report_that_removed_a_model_is_kept_as_the_audit_trail(self):
        write(self.state/'cleanup-removal.json',{'models':[{'model':'a','decision':'remove','removed':True}]},90,self.now)
        write(self.state/'cleanup-failed-removal.json',{'models':[{'model':'a','decision':'remove','removed':False}]},90,self.now)
        self.assertEqual(prune_reports(self.state,30,self.now),1)
        self.assertEqual(self.names(),['cleanup-removal.json'])

    def test_unreadable_reports_are_kept(self):
        (self.state/'cleanup-broken.json').write_text('{not json');os.utime(self.state/'cleanup-broken.json',(0,0))
        write(self.state/'cleanup-list.json',[1,2],90,self.now)
        write(self.state/'cleanup-rows.json',{'models':['x']},90,self.now)
        self.assertEqual(prune_reports(self.state,30,self.now),0)
        self.assertEqual(len(self.names()),3)

    def test_a_missing_directory_prunes_nothing(self):
        self.assertEqual(prune_reports(self.state/'absent',30,self.now),0)


class MainTests(unittest.TestCase):
    """cleaner.main with no installed models: it must prune only when applying, using the policy's retention."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.state=self.root/'state';self.state.mkdir()
        self.now=time.time()
        shipped=json.loads((ROOT/'config'/'model-storage-policy.json').read_text())
        (self.root/'usage.json').write_text(json.dumps({'version':'model-usage.v1','tracking_started_at':self.now-DAY,'bootstrap_inventory':{},'models':{}}))
        (self.root/'policy.json').write_text(json.dumps({'policy_id':'p','defaults':{'text_chat':'m'},'models':{'m':{'tasks':{'text_chat':{'rank':1}}}}}))
        self.storage=shipped;self.write_storage()
        write(self.state/'cleanup-old.json',{'models':[]},10,self.now)
    def tearDown(self):self.tmp.cleanup()
    def write_storage(self):(self.root/'storage.json').write_text(json.dumps(self.storage))

    def run_main(self,apply):
        paths={'/var/lib/narimato-gateway/model-usage.json':self.root/'usage.json','/opt/narimato-gateway/config/model-policy.json':self.root/'policy.json','/opt/narimato-ai/model-storage-policy.json':self.root/'storage.json'}
        def fake_path(*parts):return paths.get(str(parts[0]),Path(*parts)) if parts else Path()
        def fake_request(url,payload=None,key=None,timeout=15):
            if url.endswith('/internal/model-storage'):return {'lease':'lease'}
            return {'models':[]}
        with patch.object(cleaner,'Path',fake_path),patch.object(cleaner,'request',fake_request),patch.dict(os.environ,{'GATEWAY_MAINTENANCE_KEY':'k'}):
            return cleaner.main(apply,self.state)

    def test_applying_prunes_with_the_policy_retention_and_records_the_count(self):
        self.storage['keep_cleanup_report_days']=7;self.write_storage()
        report=self.run_main(True)
        self.assertEqual((report['status'],report['reports_pruned']),('completed',1))
        self.assertNotIn('cleanup-old.json',[p.name for p in self.state.iterdir()])
        self.assertTrue((self.state/'latest.json').exists())
        self.assertEqual(json.loads((self.state/'latest.json').read_text())['reports_pruned'],1)

    def test_a_dry_run_prunes_nothing(self):
        self.storage['keep_cleanup_report_days']=7;self.write_storage()
        report=self.run_main(False)
        self.assertEqual(report['status'],'completed');self.assertNotIn('reports_pruned',report)
        self.assertIn('cleanup-old.json',[p.name for p in self.state.iterdir()])

    def test_the_default_applies_when_the_policy_does_not_set_a_value(self):
        del self.storage['keep_cleanup_report_days'];self.write_storage()
        self.assertEqual(self.run_main(True)['reports_pruned'],0)
        self.assertIn('cleanup-old.json',[p.name for p in self.state.iterdir()])


class PolicyTests(unittest.TestCase):
    def test_shipped_policy_sets_a_valid_report_retention(self):
        shipped=validate_storage(json.loads((ROOT/'config'/'model-storage-policy.json').read_text()))
        self.assertEqual(shipped['keep_cleanup_report_days'],REPORT_DAYS)

    def test_report_retention_is_bounded_but_optional(self):
        shipped=json.loads((ROOT/'config'/'model-storage-policy.json').read_text())
        without={k:v for k,v in shipped.items() if k!='keep_cleanup_report_days'}
        validate_storage(without);validate_storage({**shipped,'keep_cleanup_report_days':7});validate_storage({**shipped,'keep_cleanup_report_days':365})
        for bad in (0,6,366,'30',None,2.5):
            with self.assertRaises(AssertionError):validate_storage({**shipped,'keep_cleanup_report_days':bad})


if __name__=='__main__':unittest.main()
