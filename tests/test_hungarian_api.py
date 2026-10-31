"""Tests for the Hungarian text path in gateway.server: hungarian_text_input enforces a UTF-8 byte budget and
refuses tools and excess output; Runner uses the native chat endpoint with the non-thinking profile
and configured context size."""
import unittest
from gateway.server import hungarian_text_input
class HungarianBudgetTests(unittest.TestCase):
 def value(self,content='Segíts röviden magyarul.',**extra):
  return {'messages':[{'role':'user','content':content}],'max_tokens':192,**extra}
 def test_utf8_byte_budget_accepts_hungarian_and_rejects_oversized_sources(self):
  profile={'num_ctx':2048,'num_batch':32}
  self.assertEqual(hungarian_text_input(self.value(), 'hu:1b',profile)['max_tokens'],192)
  with self.assertRaisesRegex(ValueError,'1000-byte'):
   hungarian_text_input(self.value('ő'*600),'hu:1b',profile)
 def test_unbenchmarked_tools_and_excess_output_are_refused(self):
  profile={'num_ctx':2048,'num_batch':32}
  for value in [self.value(tools=[{'type':'function'}]),self.value(max_tokens=512)]:
   with self.assertRaises(ValueError):hungarian_text_input(value,'hu:1b',profile)

class HungarianRunnerTests(unittest.TestCase):
 def test_hungarian_uses_native_text_path_and_honors_non_thinking_profile(self):
  from unittest.mock import patch
  from gateway.server import Runner
  class Catalog:
   def profile(self,task,model):return {'num_ctx':2048,'num_batch':32,'max_image_edge':640,'think':False}
  calls=[]
  def native(path,body=None,timeout=120):
   calls.append((path,body))
   if path=='/api/ps':return {'models':[]}
   self.assertEqual(path,'/api/chat')
   return {'done':True,'model':'hu:test','message':{'role':'assistant','content':'Kész.'},'done_reason':'stop','prompt_eval_count':3,'eval_count':2}
  with patch('gateway.server.native',native):
   result,_=Runner(Catalog())('text_chat_hu',{'model':'hu:test','messages':[{'role':'user','content':'Segíts magyarul.'}],'temperature':0,'max_tokens':128},'hu:test')
  self.assertEqual(result['choices'][0]['message']['content'],'Kész.')
  request=calls[-1][1];self.assertFalse(request['think']);self.assertEqual(request['options']['num_ctx'],2048)
if __name__=='__main__':unittest.main()
