"""Tests that the monitor's and the external watchdog's test-marked GET /v1/queue polls are not stored as metrics
events, while production-marked requests, other routes and other statuses still are."""
import tempfile,unittest
from pathlib import Path
from gateway.metrics import Metrics,is_liveness_poll


def stored(metrics):
    return metrics.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]


class LivenessPollTests(unittest.TestCase):
    def test_only_the_two_poll_signatures_match(self):
        self.assertTrue(is_liveness_poll('GET','/v1/queue','test',200))
        self.assertTrue(is_liveness_poll('GET','/v1/queue','test',401))
        for args in [('GET','/v1/queue','production',200),('GET','/v1/queue','test',429),('GET','/v1/queue','test',503),
                     ('GET','/v1/usage','test',200),('GET','/v1/jobs/:id','test',200),('POST','/v1/queue','test',200),
                     ('GET','/v1/queue','invalid',200),(None,None,'test',None)]:
            self.assertFalse(is_liveness_poll(*args),args)

    def test_polls_are_not_stored_and_are_not_write_failures(self):
        with tempfile.TemporaryDirectory() as root:
            metrics=Metrics(Path(root)/'metrics.sqlite3')
            try:
                for status,tenant in [(200,'classscout'),(401,'unknown')]:
                    self.assertFalse(metrics.record('http',tenant,'test',route='/v1/queue',method='GET',http_status=status))
                self.assertEqual(stored(metrics),0);self.assertEqual(metrics.failures,0)
            finally:metrics.close()

    def test_other_traffic_is_still_stored(self):
        with tempfile.TemporaryDirectory() as root:
            metrics=Metrics(Path(root)/'metrics.sqlite3')
            try:
                for purpose,route,status in [('production','/v1/queue',200),('test','/v1/queue',429),('test','/v1/usage',200),('test','/v1/jobs/:id',200)]:
                    self.assertTrue(metrics.record('http','classscout',purpose,route=route,method='GET',http_status=status))
                self.assertTrue(metrics.record('admitted','classscout','test',task='text_chat',model='m'))
                self.assertEqual(stored(metrics),5)
                report={g['purpose']:g for g in metrics.summary(1)['projects']}
                self.assertEqual(report['test']['http_requests'],3);self.assertEqual(report['production']['http_requests'],1)
            finally:metrics.close()

    def test_the_report_says_polls_are_left_out(self):
        with tempfile.TemporaryDirectory() as root:
            metrics=Metrics(Path(root)/'metrics.sqlite3')
            try:self.assertTrue(any('GET /v1/queue' in note for note in metrics.summary(1)['notes']))
            finally:metrics.close()


if __name__=='__main__':unittest.main()
