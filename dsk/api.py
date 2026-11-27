from curl_cffi import requests
from typing import Optional, Dict, Any, Generator, Literal
import json
from .pow import DeepSeekPOW
import sys
from pathlib import Path
import subprocess
import time

try:
    from importlib.metadata import version as get_version
except ImportError:
    get_version = None

ThinkingMode = Literal['detailed', 'simple', 'disabled']
SearchMode = Literal['enabled', 'disabled']

class DeepSeekError(Exception):
    """Base exception for all DeepSeek API errors"""
    pass

class AuthenticationError(DeepSeekError):
    """Raised when authentication fails"""
    pass

class RateLimitError(DeepSeekError):
    """Raised when API rate limit is exceeded"""
    pass

class NetworkError(DeepSeekError):
    """Raised when network communication fails"""
    pass

class CloudflareError(DeepSeekError):
    """Raised when Cloudflare blocks the request"""
    pass

class APIError(DeepSeekError):
    """Raised when API returns an error response"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class DeepSeekAPI:
    BASE_URL = "https://chat.deepseek.com/api/v0"

    def __init__(self, auth_token: str):
        if not auth_token or not isinstance(auth_token, str):
            raise AuthenticationError("Invalid auth token provided")

        # Check curl_cffi version
        if get_version is not None:
            try:
                curl_cffi_version = get_version('curl_cffi')
                if curl_cffi_version != '0.8.1b9':
                    print("\033[93mWarning: DeepSeek API requires curl-cffi version 0.8.1b9", file=sys.stderr)
                    print("Please install the correct version using: pip install curl-cffi==0.8.1b9\033[0m", file=sys.stderr)
            except Exception:
                print("\033[93mWarning: curl-cffi not found. Please install version 0.8.1b9:", file=sys.stderr)
                print("pip install curl-cffi==0.8.1b9\033[0m", file=sys.stderr)
        else:
            print("\033[93mWarning: Cannot verify curl-cffi version. Please ensure curl-cffi==0.8.1b9 is installed\033[0m", file=sys.stderr)

        self.auth_token = auth_token
        self.pow_solver = DeepSeekPOW()
        self.cookies = {}
        self._load_cookies()

    def _load_cookies(self):
        """Load cookies from JSON file"""
        cookies_path = Path(__file__).parent / 'cookies.json'
        try:
            if cookies_path.exists():
                with open(cookies_path, 'r') as f:
                    cookie_data = json.load(f)
                    self.cookies = cookie_data.get('cookies', {})
            else:
                self.cookies = {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"\033[93mWarning: Could not load cookies from {cookies_path}: {e}\033[0m", file=sys.stderr)
            self.cookies = {}

    def _get_headers(self, pow_response: Optional[str] = None) -> Dict[str, str]:
        """Get request headers with optional PoW response"""
        headers = {
            'accept': '*/*',
            'accept-language': 'en,fr-FR;q=0.9,fr;q=0.8,es-ES;q=0.7,es;q=0.6,en-US;q=0.5,am;q=0.4,de;q=0.3',
            'authorization': f'Bearer {self.auth_token}',
            'content-type': 'application/json',
            'origin': 'https://chat.deepseek.com',
            'referer': 'https://chat.deepseek.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
            'x-app-version': '20250120.1',
            'x-client-locale': 'en_US',
            'x-client-platform': 'web',
        }
        if pow_response:
            headers['x-ds-pow-response'] = pow_response
        return headers

    def _refresh_cookies(self) -> None:
        """Run the cookie refresh script and reload cookies"""
        try:
            script_path = Path(__file__).parent / 'bypass.py'
            subprocess.run([sys.executable, script_path], check=True)
            time.sleep(2)
            self._load_cookies()
        except Exception as e:
            print(f"\033[93mWarning: Failed to refresh cookies: {e}\033[0m", file=sys.stderr)

    def _make_request(self, method: str, endpoint: str, json_data: Dict[str, Any], pow_required: bool = False) -> Any:
        """Make a request to the API with retry logic"""
        url = f"{self.BASE_URL}{endpoint}"
        retry_count = 0
        max_retries = 2

        while retry_count < max_retries:
            try:
                headers = self._get_headers()
                if pow_required:
                    challenge = self._get_pow_challenge()
                    pow_response = self.pow_solver.solve_challenge(challenge)
                    headers = self._get_headers(pow_response)

                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    cookies=self.cookies,
                    impersonate='chrome120',
                    timeout=None
                )

                # Check if we hit Cloudflare protection
                if "<!DOCTYPE html>" in response.text and "Just a moment" in response.text:
                    print("\033[93mWarning: Cloudflare protection detected. Bypassing...\033[0m", file=sys.stderr)
                    if retry_count < max_retries - 1:
                        self._refresh_cookies()
                        retry_count += 1
                        continue

                # Handle other response codes
                if response.status_code == 401:
                    raise AuthenticationError("Invalid or expired authentication token")
                elif response.status_code == 429:
                    raise RateLimitError("API rate limit exceeded")
                elif response.status_code >= 500:
                    raise APIError(f"Server error occurred: {response.text}", response.status_code)
                elif response.status_code != 200:
                    raise APIError(f"API request failed: {response.text}", response.status_code)

                return response.json()

            except requests.exceptions.RequestException as e:
                raise NetworkError(f"Network error occurred: {str(e)}")
            except json.JSONDecodeError:
                raise APIError("Invalid JSON response from server")

        raise APIError("Failed to bypass Cloudflare protection after multiple attempts")

    def _get_pow_challenge(self) -> Dict[str, Any]:
        """Get PoW challenge from server"""
        try:
            response = self._make_request(
                'POST',
                '/chat/create_pow_challenge',
                {'target_path': '/api/v0/chat/completion'}
            )
            return response['data']['biz_data']['challenge']
        except KeyError:
            raise APIError("Invalid challenge response format from server")

    def create_chat_session(self) -> str:
        """Creates a new chat session and returns the session ID"""
        try:
            response = self._make_request(
                'POST',
                '/chat_session/create',
                {'character_id': None}
            )
            return res.json()["data"]["biz_data"]["chat_session"]["id"]
        except KeyError:
            raise APIError("Invalid session creation response format from server")

    def chat_completion(self,
                       chat_session_id: str,
                       prompt: str,
                       parent_message_id: Optional[str] = None,
                       thinking_enabled: bool = True,
                       search_enabled: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        Send a message and get streaming response

        Args:
            chat_session_id (str): The ID of the chat session
            prompt (str): The message to send
            parent_message_id (Optional[str]): ID of the parent message for threading
            thinking_enabled (bool): Whether to show the thinking process
            search_enabled (bool): Whether to enable web search

        Returns:
            Generator[Dict[str, Any], None, None]: Yields message chunks with content and type

        Raises:
            AuthenticationError: If the authentication token is invalid
            RateLimitError: If the API rate limit is exceeded
            NetworkError: If a network error occurs
            APIError: If any other API error occurs
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        if not chat_session_id or not isinstance(chat_session_id, str):
            raise ValueError("Chat session ID must be a non-empty string")

        json_data = {
            'chat_session_id': chat_session_id,
            'parent_message_id': parent_message_id,
            'prompt': prompt,
            'ref_file_ids': [],
            'thinking_enabled': thinking_enabled,
            'search_enabled': search_enabled,
            'character_id': None,
            'device_id': ""
        }

        try:
            challenge = self._get_pow_challenge()
            pow_response = self.pow_solver.solve_challenge(challenge)

            response = requests.post(
                f"{self.BASE_URL}/chat/completion",
                headers=self._get_headers(pow_response=pow_response),
                json=json_data,
                cookies=self.cookies,
                impersonate='chrome120',
                stream=True,
                timeout=None
            )

            if response.status_code != 200:
                error_text = next(response.iter_lines(), b'').decode('utf-8', 'ignore')
                if response.status_code == 401:
                    raise AuthenticationError("Invalid or expired authentication token")
                elif response.status_code == 429:
                    raise RateLimitError("API rate limit exceeded")
                else:
                    raise APIError(f"API request failed: {error_text}", response.status_code)

            for chunk in response.iter_lines():
                if not chunk:
                    continue

                try:
                    line_str = chunk.decode('utf-8', 'ignore').strip()
                    if not line_str.startswith('data: '):
                        continue

                    data_str = line_str[6:]
                    if data_str == '[DONE]':
                        break

                    data = json.loads(data_str)

                    if 'v' in data and isinstance(data['v'], str):
                        val = data['v']
                        if "Observation:" in val:
                            break
                        if data.get('o') == 'SET':
                            continue

                        yield {
                            'content': val,
                            'type': 'text',
                            'finish_reason': None
                        }

                    if data.get('p') == 'response/status' and data.get('v') == 'FINISHED':
                        break

                except Exception:
                    continue

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error occurred during streaming: {str(e)}")
