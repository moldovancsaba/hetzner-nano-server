import unittest
import io
import urllib.error
from unittest.mock import patch
from operations.monitor import evaluate, advance, track_oom
from operations.external_watchdog import reachable


def healthy():
    return {'gateway_reachable':True,'metrics_readable':True,'disk_free_gib':7,
            'services':{'gateway':True},'queue':{'status':'ok'},'usage':{'projects':[]}}


class MonitorTests(unittest.TestCase):
    def test_debounce_notify_once_and_recover(self):
        data=healthy();data['disk_free_gib']=3;observed=evaluate(data);state={}
        for n in range(2):
            state=advance(state,observed,n);self.assertEqual(state['revision'],0)
        state=advance(state,observed,3);self.assertEqual(state['revision'],1)
        for n in range(4,10):state=advance(state,observed,n)
        self.assertEqual(state['revision'],1)
        for n in range(10,13):state=advance(state,{},n)
        self.assertEqual(state['revision'],2);self.assertEqual(state['active_alerts'],{})
        self.assertEqual([r['state'] for r in state['changes']],['alert','recovered'])

    def test_test_failures_and_planned_maintenance_are_not_client_incidents(self):
        data=healthy();data['queue']['model_storage_maintenance']=True
        group={'project':'camera','purpose':'test','completed':0,'failed':20,'errors':{'model_storage_maintenance':20},'timings':{}}
        data['usage']['projects']=[group];self.assertEqual(evaluate(data),{})
        group.update(purpose='production',completed=5,failed=0,timings={'duration_ms':{'p95_ms':1000}})
        self.assertEqual(evaluate(data),{})

    def test_actual_failure_rate_and_long_queue_raise_separate_alerts(self):
        data=healthy();data['queue']['oldest_wait_seconds']=75
        data['usage']['projects']=[{'project':'classscout','purpose':'production','completed':2,'failed':3,
            'errors':{'analysis_unavailable':3},'timings':{'duration_ms':{'p95_ms':90000}}}]
        self.assertEqual(set(evaluate(data)),{'queue_delay','failures_classscout'})

    def test_historical_oom_flag_expires_but_new_counter_events_alert(self):
        previous={'active_alerts':{'runtime_oom':{'first_seen_at':100}},'snapshot':{'runtime_id':'same','oom_kill_count':1}}
        data=healthy();data.update(runtime_id='same',oom_kill_count=1,oom_killed=True);data['services']['native_container']=True
        result=track_oom(previous,data,1000)
        self.assertFalse(result['oom_killed']);self.assertTrue(result['historical_oom_killed'])
        data=healthy();data.update(runtime_id='same',oom_kill_count=2,oom_killed=True)
        result=track_oom(previous,data,1000);self.assertTrue(result['oom_killed'])
        next_data=healthy();next_data.update(runtime_id='same',oom_kill_count=2,oom_killed=True)
        self.assertFalse(track_oom({'snapshot':result},next_data,1301)['oom_killed'])

    def test_stopped_oom_container_does_not_look_recovered(self):
        data=healthy();data.update(oom_killed=True,oom_kill_count=None);data['services']['native_container']=False
        self.assertTrue(track_oom({},data,1000)['oom_killed'])

    def test_healthy_service_has_no_alert(self):self.assertEqual(evaluate(healthy()),{})

    def test_external_check_needs_no_project_key_and_marks_itself_as_test(self):
        error=urllib.error.HTTPError('https://example.invalid',401,'unauthorized',{},io.BytesIO(b'{"error":{"code":"unauthorized"}}'))
        with patch('operations.external_watchdog.urllib.request.urlopen', side_effect=error) as request:
            self.assertTrue(reachable())
            headers=dict(request.call_args.args[0].header_items())
            self.assertNotIn('Authorization',headers)
            self.assertEqual(headers['X-request-purpose'],'test')


if __name__=='__main__':unittest.main()
