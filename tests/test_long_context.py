import json
import unittest
from unittest.mock import Mock, patch

from gateway.long_context import completion, native_request, validate_budget
from gateway.server import Runner, UpstreamError, text_input

PROFILE = {'num_ctx': 8192, 'num_batch': 128, 'max_output_tokens': 1024, 'timeout_seconds': 900}
TOOL = {'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}


class Tests(unittest.TestCase):
    def test_larger_input_is_counted_and_output_reserved(self):
        data = {'messages': [{'role': 'user', 'content': 'large source ' * 4000}], 'max_tokens': 1024}
        counter = Mock()
        counter.encode.return_value.ids = range(5000)
        with patch('gateway.long_context.tokenizer', return_value=counter):
            result = text_input(data, 'granite4:1b-h', PROFILE)
            self.assertEqual(result['max_tokens'], 1024)
            counter.encode.return_value.ids = range(6000)
            with self.assertRaisesRegex(ValueError, 'token budget exceeded'):
                text_input(data, 'granite4:1b-h', PROFILE)
        with self.assertRaises(ValueError):
            text_input(data, 'granite4:1b-h')

    def test_tool_schemas_are_in_the_count(self):
        counter = Mock()
        counter.encode.return_value.ids = range(100)
        data = {'messages': [{'role': 'user', 'content': 'Hi'}], 'tools': [TOOL], 'max_tokens': 256}
        with patch('gateway.long_context.tokenizer', return_value=counter):
            validate_budget(data, PROFILE)
        self.assertIn('lookup', counter.encode.call_args.args[0])

    def test_native_roundtrip_preserves_tool_arguments_and_token_usage(self):
        data = {'model': 'granite4:1b-h', 'messages': [
            {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': 'call_old', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{"id": 7}'}}]},
            {'role': 'tool', 'tool_call_id': 'call_old', 'name': 'lookup', 'content': 'Verified'}],
            'tools': [TOOL], 'max_tokens': 512, 'temperature': 0}
        request = native_request(data, PROFILE)
        self.assertEqual(request['options']['num_ctx'], 8192)
        self.assertEqual(request['messages'][0]['tool_calls'][0]['function']['arguments'], {'id': 7})
        self.assertEqual(data['messages'][0]['tool_calls'][0]['id'], 'call_old')
        response = {'model': data['model'], 'done': True, 'prompt_eval_count': 14000, 'eval_count': 20,
                    'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'lookup', 'arguments': {'id': 8}}}]}}
        result = completion(response, request)
        self.assertEqual(result['usage']['total_tokens'], 14020)
        self.assertEqual(result['choices'][0]['finish_reason'], 'tool_calls')
        self.assertEqual(json.loads(result['choices'][0]['message']['tool_calls'][0]['function']['arguments']), {'id': 8})
        response['message']['tool_calls'][0]['function']['name'] = 'undefined'
        with self.assertRaises(ValueError):
            completion(response, request)

    def test_malformed_tool_arguments_rejected_before_generation(self):
        data = {'model': 'granite4:1b-h', 'messages': [{'role': 'assistant', 'tool_calls': [
            {'function': {'name': 'lookup', 'arguments': '[]'}}]}], 'max_tokens': 256, 'temperature': 0}
        with self.assertRaises(ValueError):
            native_request(data, PROFILE)

    def test_runtime_uses_measured_profile_and_required_tool_fails_closed(self):
        catalog = Mock()
        catalog.profile.return_value = PROFILE
        response = {'model': 'granite4:1b-h', 'done': True, 'message': {'role': 'assistant', 'content': 'guessed'}}
        data = {'model': 'granite4:1b-h', 'messages': [{'role': 'user', 'content': 'Look up'}],
                'tools': [TOOL], 'tool_choice': 'required', 'max_tokens': 256, 'temperature': 0}
        with patch('gateway.server.native', side_effect=[{'models': []}, response]) as native:
            with self.assertRaises(UpstreamError):
                Runner(catalog)('text_chat', data, 'granite4:1b-h')
            self.assertEqual(native.call_args.args[0], '/api/chat')
            self.assertEqual(native.call_args.kwargs['timeout'], 900)


if __name__ == '__main__':
    unittest.main()
