import json
from dsk.api import DeepSeekAPI

with open('dsk/cookies.json') as f:
    cookies = json.load(f)

token_raw = cookies['cookies']['userToken']
try:
    token = json.loads(token_raw)['value']
except (json.JSONDecodeError, KeyError, TypeError):
    token = token_raw
api = DeepSeekAPI(token)

chat_id = api.create_chat_session()

prompt = "What is Python?"
for chunk in api.chat_completion(chat_id, prompt):
    if chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
print()
