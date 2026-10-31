"""Tests that the monitor's stuck-inference alert follows the active job's own time limit, as reported by the
gateway, instead of one fixed five minutes."""
import unittest
from operations.monitor import evaluate,stuck_after,STUCK_FLOOR_SECONDS,STUCK_GRACE_SECONDS


def snapshot(**queue):
    return {'gateway_reachable':True,'metrics_readable':True,'disk_free_gib':7,'services':{'gateway':True},
            'queue':{'status':'ok',**queue},'usage':{'projects':[]}}


class StuckThresholdTests(unittest.TestCase):
    def test_threshold_is_the_reported_limit_plus_grace_with_a_floor(self):
        self.assertEqual(stuck_after({}),STUCK_FLOOR_SECONDS)
        self.assertEqual(stuck_after({'active_timeout_seconds':120}),STUCK_FLOOR_SECONDS)
        self.assertEqual(stuck_after({'active_timeout_seconds':900}),900+STUCK_GRACE_SECONDS)

    def test_unusable_reports_use_the_floor(self):
        for value in [None,'900',True,0,-5,float('nan')]:
            self.assertEqual(stuck_after({'active_timeout_seconds':value}),STUCK_FLOOR_SECONDS,value)

    def test_a_job_without_a_reported_limit_is_stuck_after_five_minutes(self):
        self.assertNotIn('inference_stuck',evaluate(snapshot(active_for_seconds=300)))
        self.assertIn('inference_stuck',evaluate(snapshot(active_for_seconds=301)))

    def test_a_long_job_inside_its_limit_is_not_stuck(self):
        self.assertNotIn('inference_stuck',evaluate(snapshot(active_for_seconds=700,active_timeout_seconds=900)))
        self.assertNotIn('inference_stuck',evaluate(snapshot(active_for_seconds=1020,active_timeout_seconds=900)))

    def test_a_job_past_its_limit_and_grace_is_stuck(self):
        alerts=evaluate(snapshot(active_for_seconds=1021,active_timeout_seconds=900))
        self.assertEqual(alerts['inference_stuck']['severity'],'critical')
        self.assertIn('1020 seconds',alerts['inference_stuck']['message'])

    def test_a_short_job_keeps_the_old_five_minute_rule(self):
        self.assertIn('inference_stuck',evaluate(snapshot(active_for_seconds=301,active_timeout_seconds=120)))
        self.assertNotIn('inference_stuck',evaluate(snapshot(active_for_seconds=299,active_timeout_seconds=120)))


if __name__=='__main__':unittest.main()
