"""Token-budgeted native chat for measured larger-context model profiles."""
import functools
import hashlib
import json
import os
import secrets
import time
from pathlib import Path


# One hash-pinned Granite tokenizer counts tokens for every model on an extended-context profile, so counts for
# other models are approximate. If the file is missing or its hash differs, input is refused rather than admitted.
@functools.lru_cache(maxsize=1)
def tokenizer():
    from tokenizers import Tokenizer
    path = Path(os.environ.get('GRANITE_TOKENIZER_PATH', '/opt/narimato-gateway/tokenizers/granite4-h-1b.json'))
    if hashlib.sha256(path.read_bytes()).hexdigest() != 'e2bad66439538cb4d5a7580680932432ed9ece9d3b8577e675512bdf11599253':
        raise ValueError('Verified model tokenizer is unavailable; input was not admitted')
    return Tokenizer.from_file(str(path))


def validate_budget(data, profile):
    # Count serialized roles, content, tool calls and schemas, then reserve room
    # for Ollama's model template and the entire requested output. Reject rather
    # than asking Ollama to silently drop the beginning of an oversized prompt.
    serialized = json.dumps({k: data[k] for k in ('messages', 'tools') if k in data}, ensure_ascii=False)
    count = len(tokenizer().encode(serialized, add_special_tokens=False).ids)
    maximum = profile['num_ctx'] - data['max_tokens'] - 1536
    if count > maximum:
        raise ValueError(f'Input token budget exceeded: {count} > {maximum}; shorten source excerpts or history')
    return count


def native_request(data, profile):
    try:
        return _native_request(data, profile)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Invalid message, tool call or response format') from error


def _native_request(data, profile):
    messages = json.loads(json.dumps(data['messages']))
    for message in messages:
        message.pop('tool_call_id', None)
        if 'name' in message and message['role'] == 'tool':
            message['tool_name'] = message.pop('name')
        for tool in message.get('tool_calls', []):
            args = tool['function']['arguments']
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                raise ValueError('Tool arguments must be a JSON object')
            tool['function']['arguments'] = args
            tool.pop('id', None)
            tool.pop('type', None)
    request = {'model': data['model'], 'messages': messages, 'stream': False,
               'think': False, 'keep_alive': '30m',
               'options': {'num_ctx': profile['num_ctx'], 'num_batch': profile['num_batch'],
                           'num_predict': data['max_tokens'], 'temperature': data['temperature']}}
    tools = data.get('tools')
    choice = data.get('tool_choice', 'auto')
    if tools and choice != 'none':
        if isinstance(choice, dict):
            name = choice.get('function', {}).get('name')
            tools = [tool for tool in tools if tool.get('function', {}).get('name') == name]
            if not tools:
                raise ValueError('Named tool is not defined')
        request['tools'] = tools
    response_format = data.get('response_format')
    if response_format:
        if response_format.get('type') == 'json_object':
            request['format'] = 'json'
        elif response_format.get('type') == 'json_schema':
            request['format'] = response_format['json_schema']['schema']
        elif response_format.get('type') != 'text':
            raise ValueError('Unsupported response format')
    return request


def completion(response, request):
    if not response.get('done') or not isinstance(response.get('message'), dict):
        raise ValueError('Incomplete native response')
    message = dict(response['message'])
    message.pop('thinking', None)
    calls = message.get('tool_calls', [])
    allowed = {tool['function']['name'] for tool in request.get('tools', [])}
    for call in calls:
        if call.get('function', {}).get('name') not in allowed:
            raise ValueError('Model returned an undefined tool')
        call['id'] = 'call_' + secrets.token_hex(12)
        call['type'] = 'function'
        call['function']['arguments'] = json.dumps(call['function']['arguments'], ensure_ascii=False)
    prompt = response.get('prompt_eval_count', 0)
    generated = response.get('eval_count', 0)
    return {'id': 'chatcmpl-' + secrets.token_hex(12), 'object': 'chat.completion',
            'created': int(time.time()), 'model': response['model'],
            'choices': [{'index': 0, 'message': message,
                         'finish_reason': 'length' if response.get('done_reason') == 'length' else 'tool_calls' if calls else 'stop'}],
            'usage': {'prompt_tokens': prompt, 'completion_tokens': generated, 'total_tokens': prompt + generated}}
