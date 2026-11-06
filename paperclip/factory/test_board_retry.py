"""Board.call retries a PATCH that Paperclip answers with a transient 5xx, and nothing else. Run: python3 -m unittest test_board_retry"""
import unittest
from unittest.mock import patch

import worker


class BoardRetryTests(unittest.TestCase):
    def board(self):
        return worker.Board('token', 'run-1')

    def test_a_patch_that_failed_with_500_is_retried_and_the_result_returned(self):
        outcomes = [RuntimeError('Service returned HTTP 500: {"error":"Internal server error"}'), {'status': 'done'}]
        with patch('worker.request_json', side_effect=outcomes) as call, patch('worker.time.sleep') as sleep:
            self.assertEqual(self.board().call('/issues/i', {'status': 'done'}, 'PATCH'), {'status': 'done'})
        self.assertEqual(call.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_the_second_retry_waits_longer_and_a_third_failure_is_raised(self):
        error = RuntimeError('Service returned HTTP 503: unavailable')
        with patch('worker.request_json', side_effect=[error, error, error]) as call, patch('worker.time.sleep') as sleep:
            with self.assertRaises(RuntimeError):
                self.board().call('/issues/i', {'status': 'done'}, 'PATCH')
        self.assertEqual(call.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 5])

    def test_a_conflict_or_a_client_error_is_not_retried(self):
        for message in ('Service returned HTTP 409: {"error":"Issue run ownership conflict"}', 'Service returned HTTP 403: no', 'Service returned HTTP 404: no'):
            with patch('worker.request_json', side_effect=RuntimeError(message)) as call, patch('worker.time.sleep') as sleep:
                with self.assertRaises(RuntimeError):
                    self.board().call('/issues/i', {'status': 'done'}, 'PATCH')
            self.assertEqual(call.call_count, 1, message)
            sleep.assert_not_called()

    def test_only_a_patch_is_retried(self):
        for method in (None, 'POST'):
            with patch('worker.request_json', side_effect=RuntimeError('Service returned HTTP 500: x')) as call, patch('worker.time.sleep') as sleep:
                with self.assertRaises(RuntimeError):
                    self.board().call('/issues/i/comments', {'body': 'x'}, method)
            self.assertEqual(call.call_count, 1)
            sleep.assert_not_called()

    def test_a_successful_call_is_made_once(self):
        with patch('worker.request_json', return_value={'ok': True}) as call, patch('worker.time.sleep') as sleep:
            self.assertEqual(self.board().call('/issues/i', {'status': 'done'}, 'PATCH'), {'ok': True})
        self.assertEqual(call.call_count, 1)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
