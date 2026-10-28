import unittest
from scoring import object_labels,text_match,recognition_case,moderation_summary,wilson

class ScoringTests(unittest.TestCase):
    def test_equivalent_object_names_are_accepted(self):
        self.assertTrue({'cat','dog','couch'}<=object_labels(['two tabby cats','a canine','sofa']))
    def test_substrings_do_not_invent_classes(self):
        self.assertNotIn('car',object_labels(['carpet']))
        self.assertNotIn('person',object_labels(['mannequin']))
    def test_ocr_ignores_spacing_case_and_punctuation(self):
        self.assertTrue(text_match(['Nuts Enough!'],['nutsenough']))
        self.assertTrue(text_match(['LG'],['lg']))
        self.assertFalse(text_match(['16'],['6']))
        self.assertFalse(text_match(['Amato Cielo'],['amato gelato']))
    def test_invalid_service_response_does_not_get_absence_credit(self):
        case={'id':'x','task':'recognition','present_categories':['cat'],'allowed_categories':['cat'],'absent_categories':['dog']}
        row=recognition_case(case,{'status':'failed'})
        self.assertFalse(row['valid']);self.assertEqual(row['score'],0)
    def test_reference_unsupported_claim_reduces_f1(self):
        case={'id':'x','task':'recognition','present_categories':['cat'],'allowed_categories':['cat'],'absent_categories':['dog']}
        exact=recognition_case(case,{'status':'completed','result':{'objects':['tabby cat']}})
        wrong=recognition_case(case,{'status':'completed','result':{'objects':['cat','dog']}})
        self.assertEqual(exact['score'],1);self.assertLess(wrong['score'],1);self.assertEqual(wrong['known_negative_claims'],['dog'])
    def test_moderation_abstention_is_not_a_correct_negative(self):
        manifest={'categories':['weapons'],'cases':[{'id':'p','expected':{'weapons':True}},{'id':'n','expected':{'weapons':False}},{'id':'u','expected':{'weapons':None}}]}
        entry={'model':'test','status':'completed','tests':[{'id':i,'valid':True,'parsed':{'categories':{'weapons':None}},'seconds':1} for i in ['p','n','u']]}
        row=moderation_summary(entry,manifest);c=row['categories']['weapons']
        self.assertEqual(c['tp'],0);self.assertEqual(c['tn'],0);self.assertEqual(c['review_positive'],1);self.assertEqual(c['review_negative'],1);self.assertEqual(c['review_unknown'],1);self.assertEqual(row['macro_f2'],0)
    def test_invalid_positive_counts_as_missed_detection(self):
        manifest={'categories':['weapons'],'cases':[{'id':'p','expected':{'weapons':True}},{'id':'n','expected':{'weapons':False}}]}
        entry={'model':'test','status':'completed','tests':[{'id':'p','valid':False,'seconds':1},{'id':'n','valid':True,'parsed':{'categories':{'weapons':False}},'seconds':1}]}
        row=moderation_summary(entry,manifest)
        self.assertEqual(row['macro_f2'],0);self.assertEqual(row['categories']['weapons']['invalid_positive'],1)
    def test_small_positive_set_has_wide_uncertainty(self):
        low,high=wilson(1,1);self.assertLess(low,.3);self.assertAlmostEqual(high,1)

if __name__=='__main__':unittest.main()
