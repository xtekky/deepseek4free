import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import RequestException
from dsk.api import (
    DeepSeekAPI,
    DeepSeekError,
    AuthenticationError,
    RateLimitError,
    NetworkError,
    CloudflareError,
    APIError
)

class TestDeepSeekAPIInitialization:
    """Tests for DeepSeekAPI initialization"""
    
    def test_valid_initialization(self, valid_auth_token):
        """Test successful initialization with valid token"""
        with patch("dsk.api.DeepSeekPOW"):
            api = DeepSeekAPI(valid_auth_token)
            assert api.auth_token == valid_auth_token
            assert isinstance(api.cookies, dict)
    
    def test_invalid_token_empty(self):
        """Test initialization with empty token"""
        with pytest.raises(AuthenticationError, match="Invalid auth token provided"):
            DeepSeekAPI("")
    
    def test_invalid_token_none(self):
        """Test initialization with None token"""
        with pytest.raises(AuthenticationError, match="Invalid auth token provided"):
            DeepSeekAPI(None)
    
    def test_invalid_token_type(self):
        """Test initialization with invalid token type"""
        with pytest.raises(AuthenticationError, match="Invalid auth token provided"):
            DeepSeekAPI(12345)

class TestLoadCookies:
    """Tests for loading cookies"""
    
    def test_load_cookies_from_file(self, tmp_path, valid_auth_token, mock_cookies):
        """Test loading cookies from file"""
        cookies_path = tmp_path / "cookies.json"
        cookies_path.write_text(json.dumps({"cookies": mock_cookies}))
        
        with patch("dsk.api.Path.__truediv__", return_value=cookies_path):
            with patch("dsk.api.DeepSeekPOW"):
                api = DeepSeekAPI(valid_auth_token)
                assert api.cookies == mock_cookies
    
    def test_load_cookies_file_not_exists(self, tmp_path, valid_auth_token):
        """Test when cookies.json file does not exist"""
        with patch("dsk.api.Path.__truediv__", return_value=tmp_path / "nonexistent.json"):
            with patch("dsk.api.DeepSeekPOW"):
                api = DeepSeekAPI(valid_auth_token)
                assert api.cookies == {}
    
    def test_load_cookies_invalid_json(self, tmp_path, valid_auth_token):
        """Test when cookies.json contains invalid JSON"""
        cookies_path = tmp_path / "cookies.json"
        cookies_path.write_text("invalid json content {")
        
        with patch("dsk.api.Path.__truediv__", return_value=cookies_path):
            with patch("dsk.api.DeepSeekPOW"):
                api = DeepSeekAPI(valid_auth_token)
                assert api.cookies == {}

class TestGetHeaders:
    """Tests for generating headers"""
    
    def test_get_headers_without_pow(self, api_instance):
        """Test generating headers without PoW response"""
        headers = api_instance._get_headers()
        assert headers['authorization'] == f'Bearer {api_instance.auth_token}'
        assert headers['content-type'] == 'application/json'
        assert 'x-ds-pow-response' not in headers
    
    def test_get_headers_with_pow(self, api_instance):
        """Test generating headers with PoW response"""
        pow_response = "test_pow_response"
        headers = api_instance._get_headers(pow_response)
        assert headers['x-ds-pow-response'] == pow_response
        assert headers['authorization'] == f'Bearer {api_instance.auth_token}'

class TestMakeRequest:
    """Tests for internal _make_request method"""
    
    @patch('dsk.api.requests')
    def test_successful_request(self, mock_requests, api_instance):
        """Test successful request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = ""
        mock_requests.request.return_value = mock_response
        
        result = api_instance._make_request('GET', '/test', {})
        assert result == {"success": True}
    
    @patch('dsk.api.requests')
    def test_authentication_error(self, mock_requests, api_instance):
        """Test authentication error 401"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_requests.request.return_value = mock_response
        
        with pytest.raises(AuthenticationError, match="Invalid or expired authentication token"):
            api_instance._make_request('GET', '/test', {})
    
    @patch('dsk.api.requests')
    def test_rate_limit_error(self, mock_requests, api_instance):
        """Test rate limit error 429"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_requests.request.return_value = mock_response
        
        with pytest.raises(RateLimitError, match="API rate limit exceeded"):
            api_instance._make_request('GET', '/test', {})
    
    @patch('dsk.api.requests')
    def test_server_error(self, mock_requests, api_instance):
        """Test server error 500"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests.request.return_value = mock_response
        
        with pytest.raises(APIError, match="Server error occurred"):
            api_instance._make_request('GET', '/test', {})
    
    @patch('dsk.api.requests')
    def test_network_error(self, mock_requests, api_instance):
        """Test network error"""
        mock_requests.request.side_effect = Exception("Connection failed")
        
        with pytest.raises(NetworkError, match="Network error occurred"):
            api_instance._make_request('GET', '/test', {})
    
    @patch('dsk.api.requests')
    def test_cloudflare_protection(self, mock_requests, api_instance):
        """Test Cloudflare protection detection"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<!DOCTYPE html>Just a moment..."
        mock_requests.request.return_value = mock_response
        
        with patch.object(api_instance, '_refresh_cookies') as mock_refresh:
            with pytest.raises(APIError, match="Failed to bypass Cloudflare protection"):
                api_instance._make_request('GET', '/test', {}, pow_required=False)

class TestGetPowChallenge:
    """Tests for getting PoW challenge"""
    
    @patch('dsk.api.DeepSeekAPI._make_request')
    def test_successful_challenge(self, mock_make_request, api_instance):
        """Test successful PoW challenge retrieval"""
        mock_response = {
            "data": {
                "biz_data": {
                    "challenge": {
                        "algorithm": "SHA3-256",
                        "challenge": "abc123",
                        "salt": "salt123"
                    }
                }
            }
        }
        mock_make_request.return_value = mock_response
        
        challenge = api_instance._get_pow_challenge()
        assert challenge["algorithm"] == "SHA3-256"
        assert challenge["challenge"] == "abc123"
    
    @patch('dsk.api.DeepSeekAPI._make_request')
    def test_challenge_invalid_response(self, mock_make_request, api_instance):
        """Test invalid PoW challenge response"""
        mock_make_request.return_value = {"invalid": "response"}
        
        with pytest.raises(APIError, match="Response 'data' field is None"):
            api_instance._get_pow_challenge()

class TestCreateChatSession:
    """Tests for creating chat session"""
    
    @patch('dsk.api.DeepSeekAPI._make_request')
    def test_create_session_success(self, mock_make_request, api_instance):
        """Test successful session creation"""
        mock_make_request.return_value = {
            "data": {
                "biz_data": {
                    "id": "session_12345"
                }
            }
        }
        
        session_id = api_instance.create_chat_session()
        assert session_id == "session_12345"
        mock_make_request.assert_called_once_with(
            'POST',
            '/chat_session/create',
            {'character_id': None}
        )
    
    @patch('dsk.api.DeepSeekAPI._make_request')
    def test_create_session_invalid_response(self, mock_make_request, api_instance):
        """Test invalid response during session creation"""
        mock_make_request.return_value = {"data": {}}
        
        with pytest.raises(APIError, match="Response 'biz_data' field is None"):
            api_instance.create_chat_session()

class TestChatCompletion:
    """Tests for chat_completion method"""
    
    @patch('dsk.api.DeepSeekAPI._get_pow_challenge')
    @patch('dsk.api.DeepSeekPOW.solve_challenge')
    @patch('dsk.api.requests.post')
    def test_chat_completion_streaming(self, mock_post, mock_solve, mock_challenge, api_instance):
        """Test successful streaming response"""
        mock_challenge.return_value = {"challenge": "test"}
        mock_solve.return_value = "pow_response"
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        def iter_lines():
            yield b'data: {"v": "Hello", "o": "ADD"}'
            yield b'data: {"v": " world", "o": "ADD"}'
            yield b'data: {"v": "!", "o": "ADD"}'
            yield b'data: {"p": "response/status", "v": "FINISHED"}'
        
        mock_response.iter_lines = iter_lines
        mock_post.return_value = mock_response
        
        generator = api_instance.chat_completion(
            chat_session_id="session_123",
            prompt="Test message",
            thinking_enabled=True,
            search_enabled=False
        )
        
        results = list(generator)
        assert len(results) > 0
        assert results[0]['type'] == 'text'
        assert 'content' in results[0]
    
    @patch('dsk.api.DeepSeekAPI._get_pow_challenge')
    @patch('dsk.api.DeepSeekPOW.solve_challenge')
    @patch('dsk.api.requests.post')
    def test_chat_completion_with_invalid_prompt(self, mock_post, mock_solve, mock_challenge, api_instance):
        """Test with invalid prompt"""
        mock_challenge.return_value = {"challenge": "test"}
        mock_solve.return_value = "pow_response"
        
        with pytest.raises(ValueError, match="Prompt must be a non-empty string"):
            list(api_instance.chat_completion("session_123", ""))
        
        with pytest.raises(ValueError, match="Prompt must be a non-empty string"):
            list(api_instance.chat_completion("session_123", None))
    
    @patch('dsk.api.DeepSeekAPI._get_pow_challenge')
    @patch('dsk.api.DeepSeekPOW.solve_challenge')
    @patch('dsk.api.requests.post')
    def test_chat_completion_with_invalid_session(self, mock_post, mock_solve, mock_challenge, api_instance):
        """Test with invalid session ID"""
        mock_challenge.return_value = {"challenge": "test"}
        mock_solve.return_value = "pow_response"
        
        with pytest.raises(ValueError, match="Chat session ID must be a non-empty string"):
            list(api_instance.chat_completion("", "Test"))
        
        with pytest.raises(ValueError, match="Chat session ID must be a non-empty string"):
            list(api_instance.chat_completion(None, "Test"))
    
    @patch('dsk.api.DeepSeekAPI._get_pow_challenge')
    @patch('dsk.api.DeepSeekPOW.solve_challenge')
    @patch('dsk.api.requests.post')
    def test_chat_completion_authentication_error(self, mock_post, mock_solve, mock_challenge, api_instance):
        """Test authentication error during streaming"""
        mock_challenge.return_value = {"challenge": "test"}
        mock_solve.return_value = "pow_response"
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.iter_lines = lambda: iter([b'Unauthorized'])
        mock_post.return_value = mock_response
        
        with pytest.raises(AuthenticationError):
            list(api_instance.chat_completion("session_123", "Test"))
    
    @patch('dsk.api.DeepSeekAPI._get_pow_challenge')
    @patch('dsk.api.DeepSeekPOW.solve_challenge')
    @patch('dsk.api.requests.post')
    def test_chat_completion_network_error(self, mock_post, mock_solve, mock_challenge, api_instance):
        """Test network error during streaming"""
        mock_challenge.return_value = {"challenge": "test"}
        mock_solve.return_value = "pow_response"
        mock_post.side_effect = RequestException("Network error")
        
        with pytest.raises(NetworkError, match="Network error occurred during streaming"):
            list(api_instance.chat_completion("session_123", "Test"))

class TestRefreshCookies:
    """Tests for refreshing cookies"""
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_refresh_cookies_success(self, mock_sleep, mock_subprocess, api_instance):
        """Test successful cookie refresh"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        with patch.object(api_instance, '_load_cookies') as mock_load:
            api_instance._refresh_cookies()
            mock_subprocess.assert_called_once()
            mock_load.assert_called_once()
    
    @patch('subprocess.run')
    @patch('time.sleep')
    def test_refresh_cookies_failure(self, mock_sleep, mock_subprocess, api_instance):
        """Test cookie refresh failure"""
        mock_subprocess.side_effect = Exception("Script failed")
        
        with patch('builtins.print') as mock_print:
            api_instance._refresh_cookies()
            mock_print.assert_called()
            assert "Failed to refresh cookies" in mock_print.call_args[0][0]

class TestErrorHandling:
    """Tests for error handling"""
    
    def test_authentication_error_creation(self):
        """Test authentication error creation"""
        error = AuthenticationError("Invalid token")
        assert isinstance(error, DeepSeekError)
        assert str(error) == "Invalid token"
    
    def test_rate_limit_error_creation(self):
        """Test rate limit error creation"""
        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, DeepSeekError)
    
    def test_network_error_creation(self):
        """Test network error creation"""
        error = NetworkError("Connection lost")
        assert isinstance(error, DeepSeekError)
    
    def test_cloudflare_error_creation(self):
        """Test Cloudflare error creation"""
        error = CloudflareError("Cloudflare blocked")
        assert isinstance(error, DeepSeekError)
    
    def test_api_error_with_status_code(self):
        """Test API error creation with status code"""
        error = APIError("Server error", 503)
        assert error.status_code == 503
        assert str(error) == "Server error"