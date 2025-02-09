from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, NetworkError, APIError
import sys, os
from typing import Generator, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def print_response(chunks: Generator[Dict[str, Any], None, None]) -> None:
    """Helper function to print response chunks in a clean format"""
    thinking_lines = []
    text_content = []

    try:
        for chunk in chunks:
            if chunk['type'] == 'thinking':
                if chunk['content'] and chunk['content'] not in thinking_lines:
                    thinking_lines.append(chunk['content'])
            elif chunk['type'] == 'text':
                text_content.append(chunk['content'])
    except KeyError as e:
        print(f"❌ Error: Malformed response chunk - missing key {str(e)}")
        return

    if thinking_lines:
        print("\n🤔 Thinking:")
        for line in thinking_lines:
            print(f"  • {line}")
        print()

    print("💬 Response:")
    print(''.join(text_content))
    print()

def run_chat_example(api: DeepSeekAPI, title: str, prompt: str, thinking_enabled: bool = True, search_enabled: bool = False) -> None:
    """Run a chat example with error handling"""
    print(f"\n{title}")
    print("-" * 80)

    try:
        chunks = api.chat_completion(
            api.create_chat_session(),
            prompt,
            thinking_enabled=thinking_enabled,
            search_enabled=search_enabled
        )
        print_response(chunks)

    except AuthenticationError as e:
        print(f"❌ Authentication Error: {str(e)}")
        print("Please check your authentication token and try again.")
        sys.exit(1)
    except RateLimitError as e:
        print(f"❌ Rate Limit Error: {str(e)}")
        print("Please wait a moment before making more requests.")
    except NetworkError as e:
        print(f"❌ Network Error: {str(e)}")
        print("Please check your internet connection and try again.")
    except APIError as e:
        print(f"❌ API Error: {str(e)}")
        if e.status_code:
            print(f"Status code: {e.status_code}")
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")
        print("Please report this issue if it persists.")

def main():
    try:
        # Initialize the API with your auth token
        api = DeepSeekAPI(os.getenv("DEEPSEEK_AUTH_TOKEN"))

        # # Example 1: With thinking and web search
        # run_chat_example(
        #     api,
        #     "Example 1: Latest quantum computing developments (with thinking and search)",
        #     "What are the latest developments in quantum computing?",
        #     thinking_enabled=True,
        #     search_enabled=True
        # )

        # # Example 2: With thinking only
        # run_chat_example(
        #     api,
        #     "Example 2: Python explanation (with thinking)",
        #     "Explain how Python's context managers (with statement) work",
        #     thinking_enabled=True
        # )

        # Example 3: Without thinking
        run_chat_example(
            api,
            "Example 3: Simple calculation (no thinking)",
            "What is 2+2?",
            thinking_enabled=False
        )

    except KeyboardInterrupt:
        print("\n\n⚠️ Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()