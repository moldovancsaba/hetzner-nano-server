"""Reviewed project handoff holds mutations before local reservations or external effects."""
import copy
import unittest
from unittest.mock import patch

import destination_handoff as guard


class HandoffTests(unittest.TestCase):
 def config(self,application='management',client='padel-africa'):
  scope={'application':application,'client':client}
  return {'source_exchange':{'projects':{'project':scope},'destination_handoffs':{'project':{'scope':scope,'writer':'openclaw','writer_epoch':1,'review_ref':'reviewed-exact-authority'}}}}

 def test_each_client_is_held_only_for_its_own_exact_project(self):
  for app,clients in [('management',['padel-africa','sportolok']),('salesleadgenerator',['cogmap','seyu','dvsc'])]:
   for client in clients:
    config=self.config(app,client)
    with self.assertRaisesRegex(ValueError,'Destination writes are delegated'):guard.require_native_destination_writer(config,{'projectId':'project'},app,client)
    guard.require_native_destination_writer(config,{'projectId':'unrelated'},app,client)
    guard.require_native_destination_writer({}, {'projectId':'project'},app,client)

 def test_malformed_selected_authority_cannot_fall_back_to_native_writes(self):
  for change in ['scope','writer','epoch','boolean-epoch','review','project']:
   config=self.config();handoff=config['source_exchange']['destination_handoffs']['project']
   if change=='scope':handoff['scope']={'application':'management','client':'sportolok'}
   elif change=='writer':handoff['writer']='other'
   elif change=='epoch':handoff['writer_epoch']=0
   elif change=='boolean-epoch':handoff['writer_epoch']=True
   elif change=='review':handoff['review_ref']=''
   else:config['source_exchange']['projects']={}
   with self.subTest(change=change),self.assertRaisesRegex(ValueError,'requires review|does not match'):guard.require_native_destination_writer(config,{'projectId':'project'},'management','padel-africa')

 def test_mutation_entrypoints_hold_before_any_database_fetch_or_dependency(self):
  import engine_ops,racket_land,slg
  issue={'projectId':'project'}
  for call in [lambda:engine_ops.write_once(issue,None,self.config(),None,None,None,'padel-africa','intake',None,None),lambda:racket_land.run(issue,None,self.config(),None,None,None),lambda:slg.mutate(slg.Client('cogmap'),'slg_capture_lead',{},issue,None,self.config('salesleadgenerator','cogmap'),None,None)]:
   with self.assertRaisesRegex(ValueError,'Destination writes are delegated'):call()

 def test_cross_client_call_is_held_instead_of_honoring_another_clients_handoff(self):
  with self.assertRaisesRegex(ValueError,'does not match'):guard.require_native_destination_writer(self.config(),{'projectId':'project'},'management','sportolok')
