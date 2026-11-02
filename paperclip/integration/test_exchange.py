"""Isolated exchange faults: leases, byte replay, authorization, durability and recovery."""
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from exchange.contract import Contract, ExchangeError, encode, iso
from exchange.store import Store
from exchange.server import Application, Server

SCOPE = {'application': 'classscout', 'client': 'NYC'}


def uid():
    return str(uuid.uuid4())


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1793613600.0
        self.path = Path(self.tmp.name) / 'exchange.sqlite3'
        self.store = Store(self.path, clock=lambda: self.now)
        self.pc = {'id': 'paperclip', 'clients': [SCOPE], 'scopes': ['sources:write', 'events:claim', 'operations:read', 'status:read'], 'inbox_ids': {'events': uid()}}
        self.oc = {'id': 'openclaw', 'clients': [SCOPE], 'scopes': ['sources:claim', 'events:write', 'operations:read', 'status:read'], 'inbox_ids': {'sources': uid()}}
        self.example = json.loads((Path(__file__).parent / 'examples.json').read_text())

    def offer(self):
        value = copy.deepcopy(self.example['source_offer'])
        value.update(packet_id=uid(), fetched_at=iso(self.now), expires_at=iso(self.now + 86400))
        return value

    def call(self, principal, route, value, op=None):
        status, raw = self.store.mutation(principal, op or uid(), route, encode(value))
        return status, json.loads(raw)

    def claim(self, principal=None, route='/deliveries/claim', op=None):
        p = principal or self.oc
        generation = self.store.status(p)['broker_generation']
        value = {'scope': SCOPE, 'inbox_id': p['inbox_ids']['sources' if route.startswith('/deliveries') else 'events'], 'broker_generation': generation, 'limit': 5, 'lease_seconds': 120}
        return self.call(p, route, value, op)

    def receipt(self, item, principal=None, route='/deliveries', op=None):
        p = principal or self.oc
        value = {'scope': SCOPE, 'inbox_id': p['inbox_ids']['sources' if route=='/deliveries' else 'events'], 'broker_generation': item['broker_generation'], 'lease_token': item['lease_token'], 'local_receipt_id': uid(), 'disposition': 'received', 'reason_code': 'inbox_committed', 'local_reference': 'test-inbox'}
        return value, self.call(p, route + '/' + item['delivery_id'] + '/receipt', value, op)

    def test_original_bytes_and_principal_route_binding(self):
        value, operation = self.offer(), uid()
        raw = encode(value)
        original = self.store.mutation(self.pc, operation, '/source-offers', raw)
        self.assertEqual(original, self.store.mutation(self.pc, operation, '/source-offers', raw))
        with self.assertRaises(ExchangeError) as error:
            self.store.mutation(self.pc, operation, '/source-offers', json.dumps(value, indent=2).encode())
        self.assertEqual(error.exception.code, 'idempotency_conflict')
        lookup = self.store.operation(self.pc, operation)
        self.assertEqual(lookup['request_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(lookup['response'], json.loads(original[1]))
        with self.assertRaises(ExchangeError):
            self.store.operation(self.oc, operation)

    def test_packet_dedup_across_transport_keys_and_body_conflict(self):
        value = self.offer()
        _, a = self.call(self.pc, '/source-offers', value)
        _, b = self.call(self.pc, '/source-offers', value)
        self.assertEqual(a['resource_id'], b['resource_id'])
        value['branch_hint'] = 'changed'
        with self.assertRaises(ExchangeError):
            self.call(self.pc, '/source-offers', value)

    def test_claim_loss_replays_original_expired_lease_then_new_claim(self):
        self.call(self.pc, '/source-offers', self.offer())
        operation = uid()
        _, a = self.claim(op=operation)
        self.now += 121
        _, b = self.claim(op=operation)
        self.assertEqual(a, b)
        _, c = self.claim()
        self.assertNotEqual(a['items'][0]['lease_token'], c['items'][0]['lease_token'])
        with self.assertRaises(ExchangeError) as e:
            self.receipt(a['items'][0])
        self.assertEqual(e.exception.code, 'stale_lease')

    def test_receipt_replay_survives_lease_expiry_restart(self):
        self.call(self.pc, '/source-offers', self.offer())
        _, claim = self.claim()
        operation = uid()
        value, (_, saved) = self.receipt(claim['items'][0], op=operation)
        self.now += 200
        self.store = Store(self.path, clock=lambda: self.now)
        _, replay = self.call(self.oc, '/deliveries/'+claim['items'][0]['delivery_id']+'/receipt', value, operation)
        self.assertEqual(saved, replay)
        self.assertEqual(self.claim()[1]['items'], [])

    def test_receipt_does_not_free_processing_capacity(self):
        self.store.capacity = 1
        self.call(self.pc, '/source-offers', self.offer())
        _, claim = self.claim()
        self.receipt(claim['items'][0])
        self.assertEqual(self.store.status(self.pc)['source_pending'], 1)
        with self.assertRaises(ExchangeError) as e:
            self.call(self.pc, '/source-offers', self.offer())
        self.assertEqual(e.exception.code, 'capacity_hold')
        event = copy.deepcopy(self.example['outcome_event'])
        event['event_id'], event['evaluation_id'] = uid(), uid()
        event['payload']['packet_id'] = claim['items'][0]['offer']['packet_id']
        event['payload']['state'] = 'rejected'
        self.call(self.oc, '/events', event)
        self.call(self.pc, '/source-offers', self.offer())

    def test_future_expired_unknown_recipe_and_duplicate_json_fail(self):
        value = self.offer(); value['expires_at'] = iso(self.now - 1)
        with self.assertRaises(ExchangeError):self.call(self.pc, '/source-offers', value)
        value = self.offer();value['fetched_at'] = iso(self.now + 3600)
        with self.assertRaises(ExchangeError):self.call(self.pc, '/source-offers', value)
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'\xff', b'{}'*40000]:
            with self.assertRaises(ExchangeError):self.store.contract.parse(raw)
        value = self.offer();value['extraction_recipe_id'] = 'unknown'
        with self.assertRaises(ExchangeError):self.call(self.pc, '/source-offers', value)
        value=self.offer();self.call(self.pc,'/source-offers',value)
        event=copy.deepcopy(self.example['outcome_event']);event['payload']['packet_id']=value['packet_id'];event['occurred_at']=iso(self.now+301)
        with self.assertRaises(ExchangeError):self.call(self.oc,'/events',event)

    def test_scope_and_consumer_identity_fences(self):
        value = self.offer();value['scope'] = {'application':'classscout','client':'LA'}
        with self.assertRaises(ExchangeError):self.call(self.pc, '/source-offers', value)
        self.call(self.pc, '/source-offers', self.offer())
        other = copy.deepcopy(self.oc);other['inbox_ids']['sources'] = uid()
        _, claim = self.claim(other)
        with self.assertRaises(ExchangeError):self.receipt(claim['items'][0])
        generation = self.store.status(self.oc)['broker_generation']
        with self.store.transaction() as db:db.execute("UPDATE meta SET value=? WHERE key='generation'", (uid(),))
        body={'scope':SCOPE,'inbox_id':self.oc['inbox_ids']['sources'],'broker_generation':generation,'limit':1,'lease_seconds':120}
        with self.assertRaises(ExchangeError):self.call(self.oc,'/deliveries/claim',body)

    def test_concurrent_duplicated_delivery_has_one_lease(self):
        value=self.offer();operation=uid()
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies=list(pool.map(lambda _:self.call(self.pc,'/source-offers',value,operation),range(8)))
        self.assertTrue(all(v==replies[0] for v in replies))
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies=list(pool.map(lambda _:self.claim(),range(8)))
        self.assertEqual(sum(len(r[1]['items']) for r in replies),1)

    def test_failed_commit_does_not_leave_message_without_operation(self):
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER reject_commit BEFORE INSERT ON operations BEGIN SELECT RAISE(ABORT,'injected disk failure'); END")
        with self.assertRaises(sqlite3.Error):self.call(self.pc,'/source-offers',self.offer())
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM operations').fetchone()[0],0)

    def test_private_backup_is_consistent_and_refuses_overwrite(self):
        operation=uid();self.call(self.pc,'/source-offers',self.offer(),operation)
        target=Path(self.tmp.name)/'backup.sqlite3';self.store.backup(target)
        recovered=Store(target,clock=lambda:self.now)
        self.assertEqual(recovered.operation(self.pc,operation),self.store.operation(self.pc,operation))
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        with self.assertRaises(ValueError):self.store.backup(target)

    def test_machine_auth_browser_and_capability_rejection(self):
        token='x'*40
        principal={**self.pc,'token_sha256':hashlib.sha256(token.encode()).hexdigest()}
        app=Application(self.store,[principal])
        for authorization,origin in [(None,None),('Bearer '+'y'*40,None),('Bearer '+token,'https://paperclip.haho.ai')]:
            with self.assertRaises(ExchangeError):app.authenticate(authorization,origin)
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Idempotency-Key':uid()}
        self.assertEqual(app.dispatch('GET','/status',headers)[0],200)
        with self.assertRaises(ExchangeError):app.dispatch('POST','/events',headers,b'{}')
        with self.assertRaises(ValueError):Server(('0.0.0.0',9091),app)

    def test_readback_cannot_publish_card_or_private_lead(self):
        event=copy.deepcopy(self.example['outcome_event'])
        event['payload']={'event_type':'delivery_readback','packet_id':uid(),'destination_operation_id':uid(),'readback':{'destination_type':'ingest_card','destination_id':'card','checked_at':iso(self.now),'result':'found_matching','publication':'public','verification_ref':'test','checked_fields':['name'],'content_revision':'v1'}}
        with self.assertRaises(ExchangeError):self.store.contract.validate('OutcomeEvent',event)
        readback=event['payload']['readback'];readback.update(destination_type='provider',publication='not_public',content_revision=None)
        with self.assertRaises(ExchangeError):self.store.contract.validate('OutcomeEvent',event)
        readback.update(content_revision='revision',checked_fields=[])
        with self.assertRaises(ExchangeError):self.store.contract.validate('OutcomeEvent',event)

    def test_snapshot_waits_for_causal_predecessor_and_keeps_scoped_history_private(self):
        from exchange.snapshot import snapshot
        offer=self.offer();self.call(self.pc,'/source-offers',offer)
        _,claimed=self.claim();self.receipt(claimed['items'][0])
        first=copy.deepcopy(self.example['outcome_event']);first.update(event_id=uid(),evaluation_id=uid(),revision=1,previous_event_id=None,occurred_at=iso(self.now))
        first['payload'].update(packet_id=offer['packet_id'],candidate_ref='candidate:branch',state='queued',qualified=None)
        second=copy.deepcopy(first);second.update(event_id=uid(),revision=2,previous_event_id=first['event_id'])
        second['payload'].update(state='submission_accepted',qualified=True,destination_operation_id=uid())
        self.call(self.oc,'/events',second)
        row=snapshot(self.store,self.oc)['clients'][0]
        self.assertEqual(row['openclaw']['accepted_operations'],0);self.assertEqual(row['exchange']['events_waiting'],1)
        self.assertIn('feedback_waiting',{item['phase'] for item in row['timeline']})
        self.call(self.oc,'/events',first)
        value=snapshot(self.store,self.oc);row=value['clients'][0]
        self.store.contract.validate('AggregateSnapshot',value)
        self.assertEqual(row['openclaw']['accepted_operations'],1);self.assertEqual(row['openclaw']['qualified'],1)
        self.assertEqual(row['exchange']['events_waiting'],0)
        self.assertTrue({'source_offered','intake_received','queued','submission_accepted'}.issubset({item['phase'] for item in row['timeline']}))
        raw=json.dumps(value);self.assertNotIn(offer['source_url'],raw)
        for claim in offer['claims']:self.assertNotIn(claim['quote'],raw)
        other=snapshot(self.store,{**self.oc,'clients':[{'application':'classscout','client':'BOS'}]})
        self.assertNotIn(offer['packet_id'],json.dumps(other));self.assertEqual(other['clients'][0]['timeline'],[])
        bad=copy.deepcopy(value);bad['clients'][0]['openclaw']['qualified']=-1
        with self.assertRaises(ExchangeError):self.store.contract.validate('AggregateSnapshot',bad)
        bad=copy.deepcopy(value);bad['clients'][0]['timeline'][0]['source_text']='Private payload must not be exported'
        with self.assertRaises(ExchangeError):self.store.contract.validate('AggregateSnapshot',bad)

    def test_snapshot_bounds_history_and_does_not_clear_uncertainty_on_queued_feedback(self):
        from exchange.snapshot import snapshot
        offer=self.offer();self.call(self.pc,'/source-offers',offer)
        evaluation=uid();previous=None
        for revision in range(1,26):
            event=copy.deepcopy(self.example['outcome_event']);event.update(event_id=uid(),evaluation_id=evaluation,revision=revision,previous_event_id=previous,occurred_at=iso(self.now))
            event['payload'].update(packet_id=offer['packet_id'],candidate_ref='candidate:one',state='uncertain' if revision==1 else 'queued',qualified=None)
            self.call(self.oc,'/events',event);previous=event['event_id'];self.now+=1
        value=snapshot(self.store,self.oc)['clients'][0]
        self.assertEqual(value['openclaw']['uncertain_evaluations'],1)
        self.assertEqual(len(value['timeline']),20)


if __name__=='__main__':
    unittest.main()
