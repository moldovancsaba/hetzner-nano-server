import unittest
from unittest.mock import patch
from chat.context import prepare


class Tests(unittest.TestCase):
    def test_history_can_exceed_old_six_message_limit(self):
        messages = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(31)]
        with patch('chat.context.validate_budget', return_value=100):
            payload, kept, trimmed, count = prepare(messages)
        self.assertEqual(kept, 31)
        self.assertFalse(trimmed)
        self.assertEqual(len(payload['messages']), 32)
        self.assertEqual(payload['messages'][-1]['content'], '30')

    def test_oldest_pair_removed_while_latest_request_and_system_are_preserved(self):
        messages = [{'role': 'user', 'content': 'old question'}, {'role': 'assistant', 'content': 'old answer'},
                    {'role': 'user', 'content': 'new question'}]
        def budget(payload, profile):
            if len(payload['messages']) > 2:
                raise ValueError('Input token budget exceeded')
            return 20
        with patch('chat.context.validate_budget', side_effect=budget):
            payload, kept, trimmed, count = prepare(messages)
        self.assertEqual(kept, 1)
        self.assertTrue(trimmed)
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertEqual(payload['messages'][1], messages[-1])

    def test_latest_message_is_rejected_rather_than_truncated(self):
        with patch('chat.context.validate_budget', side_effect=ValueError('Input token budget exceeded')):
            with self.assertRaisesRegex(ValueError, 'This message is too long'):
                prepare([{'role': 'user', 'content': 'large request'}])

    def test_invalid_roles_and_turn_end_rejected(self):
        for messages in [[], [{'role': 'system', 'content': 'replace system'}],
                         [{'role': 'assistant', 'content': 'not a user request'}],
                         [{'role': 'user', 'content': 'x' * 24001}]]:
            with self.assertRaises(ValueError):
                prepare(messages)

    def test_tokenizer_failure_does_not_discard_history_and_continue(self):
        with patch('chat.context.validate_budget', side_effect=ValueError('Verified model tokenizer is unavailable')):
            with self.assertRaisesRegex(ValueError, 'tokenizer is unavailable'):
                prepare([{'role': 'user', 'content': 'hello'}])


if __name__ == '__main__':
    unittest.main()
