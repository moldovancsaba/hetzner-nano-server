"""Factory evidence/outbox commit, causal projection and bounded gap tasks in isolated SQLite."""
import copy
import hashlib
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from exchange.factory import offer,project,gap_intent,rank,initialize
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


if __name__=='__main__':unittest.main()
