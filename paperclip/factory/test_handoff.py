"""Tests for classscout_handoff.plan: it proposes a missing contact value but never mutates the catalog, and
yields no operations for conflicting values, claimed listings, new providers, failed quality or
opening-hours facts."""
import unittest
from classscout_handoff import plan
class HandoffTests(unittest.TestCase):
 def batch(self,name='Brooklyn Music Factory',facts=None):return {'parent':{'identifier':'NAR-11'},'providers':[{'name':name,'url':'https://brooklynmusicfactory.com/','research_identifier':'NAR-13','research_status':'in_review','quality_status':'in_review','quality_review':{'status':'ready_for_human_review'},'draft':{'facts':facts or [{'field':'phone','value':'(877) 767-3560','quote':'Call (877) 767-3560'}]}}]}
 def row(self,**extra):return {'id':'prov-tinyout-brooklyn-music-factory','website':'https://www.brooklynmusicfactory.com/',**extra}
 def test_matching_phone_is_noop(self):self.assertEqual(plan(self.batch(),[self.row(phone='+18777673560')])['packets'][0]['status'],'verified_no_contact_change')
 def test_missing_phone_can_be_proposed_but_never_written(self):
  r=plan(self.batch(),[self.row()]);self.assertEqual(r['catalog_mutations'],0);self.assertEqual(r['packets'][0]['operations'][0]['patch'],{'phone':'(877) 767-3560'});self.assertEqual(r['packets'][0]['status'],'awaiting_owner_review')
 def test_conflicting_contact_is_not_overwritten(self):self.assertEqual(plan(self.batch(),[self.row(phone='212-111-2222')])['packets'][0]['operations'],[])
 def test_claimed_listing_not_patched(self):self.assertEqual(plan(self.batch(),[self.row(claimStatus='claimed')])['packets'][0]['operations'],[])
 def test_new_listing_not_invented(self):self.assertEqual(plan(self.batch(name='New Provider'),[])['packets'][0]['operations'],[])
 def test_failed_quality_blocks_intake(self):
  b=self.batch();b['providers'][0]['quality_status']='blocked';self.assertEqual(plan(b,[self.row()])['packets'][0]['operations'],[])
 def test_opening_hours_never_become_class_schedule(self):
  b=self.batch(facts=[{'field':'opening_hours','value':'9-5','quote':'Open 9-5'}]);self.assertEqual(plan(b,[self.row()])['packets'][0]['operations'],[])
if __name__=='__main__':unittest.main()
