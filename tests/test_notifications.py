"""Tests for operations.notifications.deliver_pending: no email without a state change, a retry sends an
identical payload and is not repeated once delivered, and unconfigured email is reported and never
attempted."""
import unittest
from operations.notifications import deliver_pending

SETTINGS={'MONITOR_EMAIL_ENABLED':'true','MONITOR_EMAIL_TO':'operator@example.invalid','MONITOR_EMAIL_FROM':'ops@example.invalid',
          'MONITOR_EMAIL_KEY':'test-sending-key','MONITOR_INSTANCE':'test-instance'}


class NotificationTests(unittest.TestCase):
    def test_no_startup_or_healthy_email(self):
        calls=[];state={'changes':[]}
        deliver_pending(state,{},SETTINGS,lambda *args:calls.append(args),now=100)
        self.assertEqual(calls,[]);self.assertTrue(state['notification']['configured'])

    def test_retry_has_identical_payload_and_key_then_no_duplicate(self):
        change={'revision':1,'at':100,'state':'alert','severity':'critical','message':'Gateway unavailable.'}
        calls=[]
        def broken(*args):calls.append(args);raise TimeoutError()
        state={'changes':[change]};deliver_pending(state,{},SETTINGS,broken,now=100)
        self.assertEqual(state['notification']['last_error'],'TimeoutError')
        previous=state;state={'changes':[change]}
        deliver_pending(state,previous,SETTINGS,lambda *args:calls.append(args),now=131)
        self.assertEqual(calls[0],calls[1]);self.assertEqual(state['notification']['delivered_through'],1)
        deliver_pending(state,state,SETTINGS,lambda *args:calls.append(args),now=200)
        self.assertEqual(len(calls),2)

    def test_unconfigured_mail_is_visible_and_never_attempted(self):
        state={'changes':[{'revision':1,'at':100,'state':'alert','severity':'warning','message':'Low storage.'}]}
        deliver_pending(state,{}, {'MONITOR_EMAIL_ENABLED':'true'},lambda *args:self.fail('must not send'),now=100)
        self.assertFalse(state['notification']['configured'])
        self.assertEqual(state['notification']['last_error'],'email_not_configured')


if __name__=='__main__':unittest.main()
