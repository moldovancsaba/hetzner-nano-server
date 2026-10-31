"""Tests for the gateway's admission limits and queue report: the per-tenant limit that status() reports is the
one submit enforces (Paperclip 1, others 4), and status() reports the active job's native-call timeout so the
monitor can tell a long legitimate job from a stuck one. Needs Pillow because gateway.server imports it."""
import threading,unittest
try:
    from gateway.server import Scheduler,tenant_limit,job_timeout,QUEUE_CAPACITY,NATIVE_TIMEOUT
    HAVE_SERVER=True
except ModuleNotFoundError as error:
    if error.name!='PIL':raise
    HAVE_SERVER=False
needs_pillow=unittest.skipUnless(HAVE_SERVER,'Pillow is not installed, so gateway.server cannot be imported')

EXTENDED={'_runtime_profile':{'num_ctx':8192,'timeout_seconds':900}}


@needs_pillow
class TenantLimitTests(unittest.TestCase):
    def test_paperclip_gets_one_and_everyone_else_four(self):
        self.assertEqual(tenant_limit('paperclip'),1)
        for tenant in ['classscout','habigoal','camera','pandora','unknown']:
            self.assertEqual(tenant_limit(tenant),4)

    def test_status_reports_the_limit_that_submit_enforces(self):
        gate=threading.Event();begun=threading.Event()
        def run(*args):begun.set();gate.wait(3);return {},{}
        s=Scheduler(run)
        try:
            self.assertEqual(s.status('paperclip')['per_service_limit'],1)
            self.assertEqual(s.status('classscout')['per_service_limit'],4)
            self.assertEqual(s.status('classscout')['queue_capacity'],QUEUE_CAPACITY)
            first,_=s.submit('paperclip','text_chat',{});begun.wait(1)
            self.assertEqual(s.submit('paperclip','text_chat',{'x':1})[1],'busy')
            for n in range(4):self.assertIsNone(s.submit('classscout','text_chat',{'n':n})[1])
            self.assertEqual(s.submit('classscout','text_chat',{'n':9})[1],'busy')
            self.assertEqual(s.status('paperclip')['own_pending'],1)
            self.assertEqual(s.status('classscout')['own_pending'],4)
        finally:gate.set()


@needs_pillow
class JobTimeoutTests(unittest.TestCase):
    def test_only_extended_context_text_has_its_own_timeout(self):
        self.assertEqual(job_timeout('text_chat',EXTENDED),900)
        self.assertEqual(job_timeout('text_chat',{'_runtime_profile':{'num_ctx':2048,'timeout_seconds':900}}),NATIVE_TIMEOUT)
        self.assertEqual(job_timeout('text_chat',{}),NATIVE_TIMEOUT)
        self.assertEqual(job_timeout('text_chat_hu',EXTENDED),NATIVE_TIMEOUT)
        self.assertEqual(job_timeout('image_moderation',b'image'),NATIVE_TIMEOUT)
        self.assertEqual(job_timeout('image_recognition',EXTENDED),NATIVE_TIMEOUT)

    def test_a_malformed_profile_falls_back_to_the_default(self):
        for profile in [None,'x',{'num_ctx':8192},{'num_ctx':8192,'timeout_seconds':'900'}]:
            self.assertEqual(job_timeout('text_chat',{'_runtime_profile':profile}),NATIVE_TIMEOUT)

    def test_status_reports_the_active_jobs_timeout_and_hides_the_private_field(self):
        gate=threading.Event();begun=threading.Event()
        def run(*args):begun.set();gate.wait(3);return {},{}
        s=Scheduler(run)
        try:
            idle=s.status('classscout');self.assertIsNone(idle['active_timeout_seconds']);self.assertEqual(idle['active_for_seconds'],0)
            job,_=s.submit('classscout','text_chat',dict(EXTENDED));begun.wait(1)
            self.assertEqual(s.status('classscout')['active_timeout_seconds'],900)
            self.assertNotIn('_timeout',s.read('classscout',job))
        finally:gate.set()
        s.wait('classscout',job,3);self.assertIsNone(s.status('classscout')['active_timeout_seconds'])
        gate.clear();begun.clear()
        try:
            job,_=s.submit('classscout','text_chat',{});begun.wait(1)
            self.assertEqual(s.status('classscout')['active_timeout_seconds'],NATIVE_TIMEOUT)
        finally:gate.set()


if __name__=='__main__':unittest.main()
