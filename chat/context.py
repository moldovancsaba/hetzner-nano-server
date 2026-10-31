"""Keep the newest complete conversation turns within the measured token budget."""
from gateway.long_context import validate_budget

# Mirrors the verified 8192-token text profile in config/model-policy.json. It is not read from the policy, so
# change both together.
PROFILE = {'num_ctx': 8192}
SYSTEM = 'You are Pandora, a helpful assistant on a privately hosted AI service. Your name in this chat is Pandora: introduce yourself as Pandora when asked who you are. Distinguish your display name from the underlying model. Never invent the model developer or model identity. Answer clearly and briefly. Say when you are unsure.'


def prepare(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= 31:
        raise ValueError('Please start a new chat or send fewer messages.')
    for message in messages:
        if (not isinstance(message, dict) or message.get('role') not in {'user', 'assistant'}
                or not isinstance(message.get('content'), str) or len(message['content']) > 24000):
            raise ValueError('Please shorten your message.')
    if messages[-1]['role'] != 'user' or not messages[-1]['content'].strip():
        raise ValueError('Please enter a message.')
    recent = [{'role': message['role'], 'content': message['content']} for message in messages]
    while recent:
        while recent and recent[0]['role'] == 'assistant':
            recent.pop(0)
        if not recent:
            break
        payload = {'model': 'auto', 'messages': [{'role': 'system', 'content': SYSTEM}] + recent,
                   'reasoning_effort': 'none', 'stream': False, 'max_tokens': 256, 'temperature': .4}
        try:
            count = validate_budget(payload, PROFILE)
            return payload, len(recent), len(recent) != len(messages), count
        except ValueError as error:
            if 'token budget exceeded' not in str(error):
                raise
            if len(recent) == 1:
                raise ValueError('This message is too long. Please shorten it or split it into parts.') from error
            recent.pop(0)
    raise ValueError('Please enter a message.')
