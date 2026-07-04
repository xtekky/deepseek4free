import json
from dsk.api import DeepSeekAPI

with open('dsk/cookies.json') as f:
    cookies = json.load(f)

token_raw = cookies['cookies']['userToken']
try:
    token = json.loads(token_raw)['value']
except Exception:
    token = token_raw

api = DeepSeekAPI(token)
chat_id = api.create_chat_session()
parent_id = None

print("Chat started. Type /exit to quit.\n")

while True:
    prompt = input("> ")
    if prompt.strip() == "/exit":
        break
    if not prompt.strip():
        continue

    for chunk in api.chat_completion(chat_id, prompt, parent_message_id=parent_id):
        if chunk['type'] == 'text':
            print(chunk['content'], end='', flush=True)
        elif chunk['type'] == 'meta':
            parent_id = chunk.get('parent_message_id')
    print("\n")
