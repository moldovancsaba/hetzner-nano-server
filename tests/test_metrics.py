"""Tests for gateway.metrics: history survives restart with test and production kept apart, no content or ids
are stored, pruning by age and event cap, job outcomes and timings, tenant-isolated /v1/usage, and
metrics failures never stopping inference."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from gateway.metrics import Metrics, route_name, open_metrics
from gateway.server import Scheduler, Server


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [2000000000.]
        self.metrics = Metrics(Path(self.tmp.name)/'metrics.sqlite3', lambda: self.clock[0])

    def tearDown(self):
        self.metrics.close()
        self.tmp.cleanup()

    def test_restart_preserves_history_and_tests_stay_separate(self):
        self.metrics.record('admitted', 'camera', 'test', task='image_moderation', model='vision')
        self.metrics.record('admitted', 'classscout', 'production', task='text_chat', model='text')
        reader = Metrics.readonly(self.metrics.path)
        try:
            result = reader.summary(12, now=self.clock[0])
            self.assertFalse(result['full_window_tracked'])
            self.assertEqual([(x['project'], x['purpose'], x['admitted']) for x in result['projects']],
                             [('camera','test',1), ('classscout','production',1)])
            self.assertEqual(reader.summary(12, tenant='camera', now=self.clock[0])['projects'][0]['models'], {'vision':1})
        finally:
            reader.close()

    def test_content_fields_and_route_ids_cannot_enter_storage(self):
        secret='private-photo-and-key-that-must-not-be-kept'
        self.metrics.record('admitted', 'camera', 'test', task='image_moderation', model='vision',
                            image=secret, prompt=secret, api_key=secret, job_id=secret)
        self.assertEqual(route_name('/v1/jobs/'+secret+'?token='+secret), '/v1/jobs/:id')
        self.assertNotIn(secret, json.dumps(self.metrics.summary()))
        for path in Path(self.tmp.name).iterdir():
            self.assertNotIn(secret.encode(), path.read_bytes())

    def test_age_and_event_cap_pruning_report_incomplete_coverage(self):
        for _ in range(4):
            self.metrics.record('admitted', 'camera', 'production')
            self.clock[0]+=1
        with patch('gateway.metrics.MAX_EVENTS', 2):
            self.metrics.prune()
        self.assertEqual(self.metrics.summary()['projects'][0]['admitted'], 2)
        self.clock[0]+=31*86400
        self.metrics.prune()
        self.assertEqual(self.metrics.summary()['projects'], [])

    def test_job_idempotency_outcomes_and_acknowledgement(self):
        gate=threading.Event()
        def runner(*args):
            gate.wait(2)
            return {}, {'unloaded_models':['old'], 'unload_wait_seconds':.03,
                        'model_load_seconds':.2, 'inference_wall_seconds':.5}
        scheduler=Scheduler(runner, metrics=self.metrics)
        job,_=scheduler.submit('camera','image_recognition',b'private-image','same',purpose='test')
        self.assertEqual(scheduler.submit('camera','image_recognition',b'private-image','same',purpose='test')[0],job)
        gate.set()
        self.assertEqual(scheduler.wait('camera',job,2)['status'],'completed')
        scheduler.delete('camera',job)
        result=self.metrics.summary()['projects'][0]
        self.assertEqual((result['admitted'],result['completed'],result['acknowledged'],result['model_switches']), (1,1,1,1))
        self.assertEqual(result['timings']['load_ms']['p50_ms'],200)

    def test_http_errors_and_usage_are_tenant_isolated(self):
        self.metrics.record('admitted','camera','production',model='vision')
        self.metrics.record('admitted','classscout','production',model='text')
        server=Server(('127.0.0.1',0),{'camera':'c'*40,'classscout':'s'*40},metrics=self.metrics)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            req=urllib.request.Request(base+'/v1/usage?hours=12',headers={'Authorization':'Bearer '+'c'*40,'X-Request-Purpose':'test'})
            with urllib.request.urlopen(req) as response:data=json.load(response)
            self.assertEqual({row['project'] for row in data['projects']},{'camera'})
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/v1/usage?token=secret')
        finally:
            server.shutdown();server.server_close()
        groups=self.metrics.summary()['projects']
        self.assertEqual(next(x for x in groups if x['project']=='unknown')['http_statuses'],{'401':1})

    def test_metrics_failure_does_not_stop_requests(self):
        self.metrics.db.close()
        self.assertFalse(self.metrics.record('admitted','camera'))
        self.assertEqual(self.metrics.failures,1)
        self.metrics.db=__import__('sqlite3').connect(str(self.metrics.path))

    def test_unavailable_store_does_not_stop_inference(self):
        parent=Path(self.tmp.name)/'not-a-directory';parent.write_text('fixture')
        metrics=open_metrics(parent/'metrics.sqlite3')
        self.assertFalse(metrics.available)
        scheduler=Scheduler(lambda *args: ({}, {}), metrics=metrics)
        job,error=scheduler.submit('classscout','text_chat',{},purpose='test')
        self.assertIsNone(error)
        self.assertEqual(scheduler.wait('classscout',job,2)['status'],'completed')
        self.assertEqual(scheduler.status('classscout')['metrics_write_failures'],1)


if __name__ == '__main__':unittest.main()
