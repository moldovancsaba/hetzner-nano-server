"""Factory evidence/outbox commit, causal projection and bounded gap tasks in isolated SQLite."""
import copy
import hashlib
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from exchange.factory import offer,project,gap_intent,rank,initialize,select_offers
from exchange.contract import encode


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        initialize(self.db);self.db.commit()
        self.examples=json.loads((Path(__file__).parent/'examples.json').read_text())

    def test_evidence_outbox_rollback_and_stable_packet(self):
        text='Example Provider offers classes';now=1793613600
        page={'url':'https://provider.example/programs','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':now}
        scope={'application':'classscout','client':'NYC'}
        try:
            with self.db:
                offer(self.db,scope,'task1',page,[{'field':'name','value':'Example Provider','quote':text}],'review1',now=now)
                raise RuntimeError('injected factory failure')
        except RuntimeError:pass
        self.assertEqual(self.db.execute('SELECT count(*) FROM exchange_source_outbox').fetchone()[0],0)
        with self.db:
            a=offer(self.db,scope,'task1',page,[],'review1',now=now)
            b=offer(self.db,scope,'task1',page,[],'review1',now=now)
        self.assertEqual(a,b);self.assertEqual(self.db.execute('SELECT count(*) FROM exchange_source_outbox').fetchone()[0],1)

    def test_out_of_order_duplicate_and_nonregressing_outcomes(self):
        first=copy.deepcopy(self.examples['outcome_event']);first['payload']['state']='submission_accepted'
        later=copy.deepcopy(first);later.update(event_id=str(uuid.uuid4()),revision=2,previous_event_id=first['event_id']);later['payload']['state']='queued'
        with self.db:
            project(self.db,later)
            self.assertEqual(self.db.execute('SELECT count(*) FROM exchange_projection').fetchone()[0],0)
            project(self.db,first)
            self.assertFalse(project(self.db,first))
        row=self.db.execute('SELECT revision,body FROM exchange_projection').fetchone()
        self.assertEqual(row[0],2);self.assertEqual(json.loads(row[1])['payload']['state'],'submission_accepted')

    def test_gap_intents_deduplicate_and_limit_two_per_72_hours(self):
        event=copy.deepcopy(self.examples['outcome_event'])
        event['payload']={'event_type':'gap_report','candidate_ref':'candidate','gap_fields':['address'],'evidence_fingerprint':'a'*64,'checker_version':'1','reason_code':'missing_address'}
        with self.db:
            a=gap_intent(self.db,event,1000000);self.assertEqual(a,gap_intent(self.db,event,1000001))
            event['payload']['evidence_fingerprint']='b'*64;self.assertIsNotNone(gap_intent(self.db,event,1000002))
            event['payload']['evidence_fingerprint']='c'*64;self.assertIsNone(gap_intent(self.db,event,1000003))

    def test_rank_never_admits_ineligible_source(self):
        self.assertIsNone(rank({'eligible':False,'official':1}))
        self.assertEqual(rank({'eligible':True,'official':1,'gap':1}),45)
        with self.assertRaises(ValueError):rank({'eligible':True,'fresh':2})

    def source(self,task,*,host='ranked.example',client='NYC',kind='official_branch'):
        now=1793613600
        text='Independent source text'
        page={'url':'https://'+host+'/program','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':now}
        return offer(self.db,{'application':'classscout','client':client},task,page,[],'reviewed-policy',source_kind=kind,now=now)

    def test_ranked_selection_preserves_one_fifth_exploration(self):
        with self.db:
            lower=self.source('old-approved-lead',host='exploration.example',kind='directory_lead')
            for i in range(5):self.source('official-'+str(i))
            allocations=[]
            for i in range(5):
                row=select_offers(self.db,1,1793613601)[0];allocations.append(row)
                self.db.execute("UPDATE exchange_source_outbox SET state='done' WHERE packet=?",(row['packet'],))
        self.assertTrue(all(row['packet']!=lower for row in allocations[:4]))
        self.assertEqual(allocations[4]['packet'],lower)
        self.assertEqual([row['selection_mode'] for row in allocations],['ranked']*4+['explore'])

    def test_reconciliation_retry_keeps_original_allocation_and_operation(self):
        with self.db:
            self.source('source')
            first=select_offers(self.db,1,1793613601)[0]
            repeated=select_offers(self.db,1,1793613602)[0]
        self.assertEqual(first['body'],repeated['body']);self.assertEqual(first['operation'],repeated['operation'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM exchange_source_selection').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT value FROM exchange_selection_cursor WHERE key!='last_scope'").fetchone()[0],'1')

    def test_scoped_turns_are_fair_and_do_not_mutate_source_bytes(self):
        with self.db:
            a=self.source('NYC-source');b=self.source('BOS-source',client='BOS')
            allocations=select_offers(self.db,2,1793613601)
        self.assertEqual({row['packet'] for row in allocations},{a,b})
        self.assertEqual({json.loads(row['body'])['scope']['client'] for row in allocations},{'BOS','NYC'})
        for row in allocations:self.assertNotIn('selection_mode',json.loads(row['body']))

    def test_expired_offer_is_held_without_transport_or_new_allocation(self):
        with self.db:
            self.source('expired')
            self.assertEqual(select_offers(self.db,2,1793613600+8*86400),[])
        self.assertEqual(self.db.execute('SELECT state FROM exchange_source_outbox').fetchone()[0],'held')
        self.assertEqual(self.db.execute('SELECT count(*) FROM exchange_source_selection').fetchone()[0],0)

    def test_gap_priority_comes_from_exact_scoped_native_task_lineage(self):
        with self.db:
            self.db.execute('INSERT INTO exchange_gap_intents VALUES(?,?,?,?,?,?,?,?,?)',('gap','classscout','NYC','candidate','a'*64,'address',1793613590,'delivered','gap-task'))
            ordinary=self.source('ordinary',kind='directory_lead')
            targeted=self.source('gap-task',kind='directory_lead')
            other=self.source('gap-task',client='BOS',kind='directory_lead')
            body=json.loads(self.db.execute('SELECT body FROM exchange_source_outbox WHERE packet=?',(targeted,)).fetchone()[0])
            self.assertEqual(body['gap_fields'],['address'])
            body=json.loads(self.db.execute('SELECT body FROM exchange_source_outbox WHERE packet=?',(other,)).fetchone()[0])
            self.assertEqual(body['gap_fields'],[])
            selected=select_offers(self.db,2,1793613601)
        self.assertIn(targeted,{row['packet'] for row in selected})
        self.assertNotIn(ordinary,{row['packet'] for row in selected})


if __name__=='__main__':unittest.main()
