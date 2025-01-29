# DeepSeek4Free

A Python package for interacting with the DeepSeek AI chat API. This package provides a clean interface to interact with DeepSeek's chat model, with support for streaming responses, thinking process visibility, and web search capabilities.

### Learn how to reverse engineer private api's !!
- and reverse wasm like it was required here
- [whop.com/reverser-academy](https://whop.com/reverser-academy/) (beta)

## ✨ Features

- 🔄 **Streaming Responses**: Real-time interaction with token-by-token output
- 🤔 **Thinking Process**: Optional visibility into the model's reasoning steps
- 🔍 **Web Search**: Optional integration for up-to-date information
- 💬 **Session Management**: Persistent chat sessions with conversation history
- ⚡ **Efficient PoW**: WebAssembly-based proof of work implementation
- 🛡️ **Error Handling**: Comprehensive error handling with specific exceptions
- ⏱️ **No Timeouts**: Designed for long-running conversations without timeouts
- 🧵 **Thread Support**: Parent message tracking for threaded conversations

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/deepseek4free.git
cd deepseek4free
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## 🔑 Authentication

To use this package, you need a DeepSeek auth token. Here's how to obtain it:

### Method 1: From LocalStorage (Recommended)

<img width="1150" alt="image" src="https://github.com/user-attachments/assets/b4e11650-3d1b-4638-956a-c67889a9f37e" />

1. Visit [chat.deepseek.com](https://chat.deepseek.com)
2. Log in to your account
3. Open browser developer tools (F12 or right-click > Inspect)
4. Go to Application tab (if not visible, click >> to see more tabs)
5. In the left sidebar, expand "Local Storage"
6. Click on "https://chat.deepseek.com"
7. Find the key named `userToken`
8. Copy `"value"` - this is your authentication token

### Method 2: From Network Tab

Alternatively, you can get the token from network requests:

1. Visit [chat.deepseek.com](https://chat.deepseek.com)
2. Log in to your account
3. Open browser developer tools (F12)
4. Go to Network tab
5. Make any request in the chat
6. Find the request headers
7. Copy the `authorization` token (without 'Bearer ' prefix)

## 📚 Usage

### Basic Example

```python
from dsk.api import DeepSeekAPI

# Initialize with your auth token
api = DeepSeekAPI("YOUR_AUTH_TOKEN")

# Create a new chat session
chat_id = api.create_chat_session()

# Simple chat completion
prompt = "What is Python?"
for chunk in api.chat_completion(chat_id, prompt):
    if chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
```

### Advanced Features

#### Thinking Process Visibility

The thinking process shows the model's reasoning steps:

```python
# With thinking process enabled
for chunk in api.chat_completion(
    chat_id,
    "Explain quantum computing",
    thinking_enabled=True
):
    if chunk['type'] == 'thinking':
        print(f"🤔 Thinking: {chunk['content']}")
    elif chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
```

#### Web Search Integration

Enable web search for up-to-date information:

```python
# With web search enabled
for chunk in api.chat_completion(
    chat_id,
    "What are the latest developments in AI?",
    thinking_enabled=True,
    search_enabled=True
):
    if chunk['type'] == 'thinking':
        print(f"🔍 Searching: {chunk['content']}")
    elif chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
```

#### Threaded Conversations

Create threaded conversations by tracking parent messages:

```python
# Start a conversation
chat_id = api.create_chat_session()

# Send initial message
parent_id = None
for chunk in api.chat_completion(chat_id, "Tell me about neural networks"):
    if chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
    elif 'message_id' in chunk:
        parent_id = chunk['message_id']

# Send follow-up question in the thread
for chunk in api.chat_completion(
    chat_id,
    "How do they compare to other ML models?",
    parent_message_id=parent_id
):
    if chunk['type'] == 'text':
        print(chunk['content'], end='', flush=True)
```

### Error Handling

The package provides specific exceptions for different error scenarios:

```python
from dsk.api import (
    DeepSeekAPI, 
    AuthenticationError,
    RateLimitError,
    NetworkError,
    APIError
)

try:
    api = DeepSeekAPI("YOUR_AUTH_TOKEN")
    chat_id = api.create_chat_session()
    
    for chunk in api.chat_completion(chat_id, "Your prompt here"):
        if chunk['type'] == 'text':
            print(chunk['content'], end='', flush=True)
            
except AuthenticationError:
    print("Authentication failed. Please check your token.")
except RateLimitError:
    print("Rate limit exceeded. Please wait before making more requests.")
except NetworkError:
    print("Network error occurred. Check your internet connection.")
except APIError as e:
    print(f"API error occurred: {str(e)}")
```

### Helper Functions

For cleaner output handling, you can use helper functions like in `example.py`:

```python
def print_response(chunks):
    """Helper function to print response chunks in a clean format"""
    thinking_lines = []
    text_content = []
    
    for chunk in chunks:
        if chunk['type'] == 'thinking':
            if chunk['content'] not in thinking_lines:
                thinking_lines.append(chunk['content'])
                print(f"🤔 {chunk['content']}")
        elif chunk['type'] == 'text':
            text_content.append(chunk['content'])
            print(chunk['content'], end='', flush=True)
```

## 🧪 Response Format

The API returns chunks in the following format:

```python
{
    'type': str,        # 'thinking' or 'text'
    'content': str,     # The actual content
    'finish_reason': str,  # 'stop' when response is complete
    'message_id': str   # (optional) For threaded conversations
}
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. Here are some ways you can contribute:

- 🐛 Report bugs
- ✨ Request features
- 📝 Improve documentation
- 🔧 Submit bug fixes
- 🎨 Add examples

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This package is unofficial and not affiliated with DeepSeek. Use it responsibly and in accordance with DeepSeek's terms of service.

## 🔗 Related Projects

- [DeepSeek Chat](https://chat.deepseek.com) - Official DeepSeek chat interface
- [Example Projects](example.py) - More usage examples
