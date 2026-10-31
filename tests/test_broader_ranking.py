"""Tests for scripts.promote_rankings.build on a synthetic fixture: the current cohort wins without mixing
legacy scores, legacy moderators are neither promoted nor kept by the cleaner, mixed moderation methods
fail closed, and the thinking control must be boolean."""
import json,tempfile,unittest
from pathlib import Path
from scripts.promote_rankings import build
from storage.cleaner import reasons

class BroaderRankingTests(unittest.TestCase):
    def fixture(self,root):
        (root/'config').mkdir()
        def write(name,value):(root/name).write_text(json.dumps(value))
        sources={'english_and_images':'ranking.json','moderation':'moderation.json','moderation_raw':'raw.json','digest_evidence':['digests.json'],'legacy_screening':'legacy.json','legacy_moderation':'legacy-mod.json','legacy_moderation_raw':'legacy-raw.json'}
        write('config/ranking-sources.json',sources)
        write('ranking.json',{'english':[{'model':'text:1b','passed':14}],'image':[{'model':'current:1b','benchmark_version':'vision-evaluation.v1','readiness_score':.7,'tested_profile':{'think':False}}]})
        write('legacy.json',{'image':[{'model':'legacy:1b','schema_passed':5,'schema_total':5}]})
        def row(model,balanced):
            # Same four images, two classes: the frequent-class specialist has
            # four true positives but misses the rare class and raises alarms.
            cats=({'weapons':{'tp':1,'tn':0,'fp':0},'hateWords':{'tp':1,'tn':2,'fp':0}} if balanced else {'weapons':{'tp':4,'tn':0,'fp':0},'hateWords':{'tp':0,'tn':0,'fp':3}})
            return {'model':model,'status':'completed','total':4,'valid':3 if balanced else 4,'ranking_eligible':True,'ranking_metric':'macro_f2','benchmark_version':'vision-evaluation.v1','macro_f2':(5/17+1)/2 if balanced else .5,'macro_specificity':2/3 if balanced else 0,'macro_detection_recall':.625 if balanced else .5,'tested_profile':{},'categories':cats}
        write('moderation.json',[row('frequent:1b',False),row('balanced:1b',True)])
        write('raw.json',{'models':[{'model':model,'tests':[{'seconds':1}]*4} for model in ['frequent:1b','balanced:1b']]})
        write('legacy-mod.json',[{'model':'old:1b','status':'completed','valid':25,'total':25,'categories':{'weapons':{'tp':20,'tn':5,'fp':0}}}])
        write('legacy-raw.json',{'models':[]})
        write('digests.json',[{'name':name,'digest':str(i)*64} for i,name in enumerate(['text:1b','current:1b','legacy:1b','frequent:1b','balanced:1b','old:1b'],1)])
    def test_current_cohort_wins_without_mixing_old_scores(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);policy=build(root)
            self.assertEqual(policy['defaults']['image_recognition'],'current:1b')
            legacy=policy['models']['legacy:1b']['tasks']['image_recognition']
            self.assertEqual(legacy['ranking_tier'],'legacy_screening_not_comparable');self.assertIsNone(legacy['current_rank']);self.assertGreater(legacy['rank'],5)
            self.assertEqual(policy['defaults']['image_moderation'],'balanced:1b')
            self.assertEqual(policy['models']['balanced:1b']['tasks']['image_moderation']['metrics']['valid'],3)
            self.assertIs(policy['models']['current:1b']['tasks']['image_recognition']['profile']['think'],False)
    def test_legacy_moderator_is_not_promoted_by_large_old_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);policy=build(root)
            legacy=policy['models']['old:1b']['tasks']['image_moderation']
            self.assertEqual(legacy['ranking_tier'],'legacy_screening_not_comparable');self.assertGreater(legacy['rank'],5)
            usage={'tracking_started_at':0,'models':{},'bootstrap_inventory':{}}
            self.assertEqual(reasons({'name':'old:1b','digest':'6'*64},policy,usage,set(),40*86400),[])
    def test_mixed_moderation_methods_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);path=root/'moderation.json';rows=json.loads(path.read_text());rows[0].pop('ranking_metric');path.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,'Mixed moderation'):build(root)
    def test_profile_control_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);path=root/'ranking.json';rows=json.loads(path.read_text());rows['image'][0]['tested_profile']['think']='false';path.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,'thinking control'):build(root)

if __name__=='__main__':unittest.main()
