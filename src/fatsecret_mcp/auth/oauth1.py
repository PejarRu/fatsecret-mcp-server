"""
OAuth 1.0 authentication for FatSecret MCP server.
Implements the complete OAuth 1.0 three-legged flow for authentication with FatSecret Platform API.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from pathlib import Path

from oauthlib.oauth1 import SIGNATURE_TYPE_BODY
from requests_oauthlib import OAuth1Session


class OAuth1Authenticator:
    """
    OAuth 1.0 authenticator for FatSecret Platform API.
    
    This class implements the complete OAuth 1.0 three-legged flow as specified in the FatSecret Platform API documentation.
    It handles:
    - Generating OAuth signatures
    - Creating authorization headers
    - Exchanging request tokens for access tokens
    - Managing token storage and refresh
    """

    def __init__(self, consumer_key: str, consumer_secret: str):
        """
        Initialize the OAuth 1.0 authenticator.
        
        Args:
            consumer_key: FatSecret consumer key
            consumer_secret: FatSecret consumer secret
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token = None
        self.token_secret = None
        self.verifier = None
        self.authorized = False
        self.request_token = None
        self.request_token_secret = None
        self.token_path = Path(os.getenv("FATSECRET_TOKEN_PATH", "/app/data/oauth_tokens.json"))
        self._load_tokens()

    def _load_tokens(self) -> None:
        if not self.token_path.exists():
            return
        data = json.loads(self.token_path.read_text(encoding="utf-8"))
        self.token = data.get("oauth_token")
        self.token_secret = data.get("oauth_token_secret")
        self.request_token = data.get("request_token")
        self.request_token_secret = data.get("request_token_secret")
        self.authorized = bool(self.token and self.token_secret)

    def _save_tokens(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(
            json.dumps(
                {
                    "oauth_token": self.token,
                    "oauth_token_secret": self.token_secret,
                    "request_token": self.request_token,
                    "request_token_secret": self.request_token_secret,
                }
            ),
            encoding="utf-8",
        )
        self.token_path.chmod(0o600)

    def generate_signature(self, method: str, url: str, params: dict, token_secret: str = None) -> str:
        """
        Generate OAuth 1.0 HMAC-SHA1 signature.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL for the API request
            params: Dictionary of parameters
            token_secret: Token secret (if available)
            
        Returns:
            Base64-encoded HMAC-SHA1 signature
        """
        # Ensure parameters are sorted
        param_string = urllib.parse.urlencode(sorted(params.items()))

        # Encode URL for signature base
        encoded_url = urllib.parse.quote(url, safe='')

        # Create signature base string
        signature_base = f"{method}&{encoded_url}&{param_string}"

        # Generate signing key
        if token_secret:
            signing_key = f"{self.consumer_secret}&{token_secret}"
        else:
            signing_key = f"{self.consumer_secret}&"

        # Generate HMAC-SHA1 hash
        hashed = hmac.new(signing_key.encode(), signature_base.encode(), hashlib.sha1)
        signature = base64.b64encode(hashed.digest()).decode()

        return signature

    def get_authorization_header(self, method: str, url: str, params: dict, token_secret: str = None) -> dict:
        """
        Generate OAuth 1.0 authorization header.
        
        Args:
            method: HTTP method
            url: Full URL for the API request
            params: Dictionary of parameters
            token_secret: Token secret (if available)
            
        Returns:
            Dictionary with Authorization header
        """
        # Generate OAuth parameters
        nonce = str(int(time.time() * 1000))
        timestamp = str(int(time.time()))

        oauth_params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_nonce": nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": timestamp,
            "oauth_version": "1.0"
        }

        # Add token if available
        if token_secret and self.token:
            oauth_params["oauth_token"] = self.token

        # Generate signature
        signature = self.generate_signature(method, url, {**params, **oauth_params}, token_secret)
        oauth_params["oauth_signature"] = signature

        # Create authorization header
        auth_header = "OAuth " + ", ".join([f'{k}="{v}"' for k, v in oauth_params.items()])

        return {"Authorization": auth_header}

    def get_request_token(self, callback_url: str = None) -> tuple[str, str]:
        """
        Get OAuth request token.
        
        Args:
            callback_url: Optional callback URL for OAuth callback
            
        Returns:
            Tuple of (request_token, request_token_secret)
            
        Raises:
            Exception: If unable to get request token
        """
        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            callback_uri=callback_url or "oob",
            signature_type=SIGNATURE_TYPE_BODY,
        )
        response_params = session.fetch_request_token(
            "https://authentication.fatsecret.com/oauth/request_token"
        )
        request_token = response_params.get("oauth_token")
        request_token_secret = response_params.get("oauth_token_secret")
        if not request_token or not request_token_secret:
            raise ValueError("FatSecret did not return a valid OAuth request token")

        self.request_token = request_token
        self.request_token_secret = request_token_secret
        self._save_tokens()

        return request_token, request_token_secret

    def authorize_user(self, verifier: str) -> bool:
        """
        Exchange OAuth verifier for access token.
        
        Args:
            verifier: OAuth verifier code from user authorization
            
        Returns:
            True if authorization successful, False otherwise
        """
        if not self.request_token or not self.request_token_secret:
            raise ValueError("Request token not obtained")

        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.request_token,
            resource_owner_secret=self.request_token_secret,
            verifier=verifier,
            signature_type=SIGNATURE_TYPE_BODY,
        )
        response_params = session.fetch_access_token(
            "https://authentication.fatsecret.com/oauth/access_token"
        )
        access_token = response_params.get("oauth_token")
        access_token_secret = response_params.get("oauth_token_secret")

        if access_token and access_token_secret:
            self.token = access_token
            self.token_secret = access_token_secret
            self.verifier = None
            self.authorized = True
            self.request_token = None
            self.request_token_secret = None
            self._save_tokens()
            return True
        else:
            return False

    def make_authenticated_request(self, method: str, endpoint: str, params: dict = None,
                                 token_secret: str = None) -> dict:
        """
        Make an authenticated request to the FatSecret API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "/food/search")
            params: Dictionary of request parameters
            token_secret: Token secret (if different from stored token)
            
        Returns:
            API response as dictionary
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        url = f"https://platform.fatsecret.com/rest{endpoint}"
        params = params or {}
        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.token,
            resource_owner_secret=token_secret or self.token_secret,
        )
        request_kwargs = {"timeout": 30}
        if method.upper() == "GET":
            request_kwargs["params"] = params
        else:
            request_kwargs["data"] = params
        response = session.request(method.upper(), url, **request_kwargs)
        response.raise_for_status()
        return response.json()

    def is_authorized(self) -> bool:
        """Check if the authenticator is authorized."""
        return self.authorized and self.token and self.token_secret


# Global authenticator instance
_authenticator = None


def get_authenticator() -> OAuth1Authenticator:
    """
    Get or create the global authenticator instance.
    
    Returns:
        OAuth1Authenticator instance
        
    Raises:
        ValueError: If consumer credentials are not set in environment variables
    """
    global _authenticator

    if _authenticator is None:
        consumer_key = os.getenv("FATSECRET_CONSUMER_KEY")
        consumer_secret = os.getenv("FATSECRET_CONSUMER_SECRET")

        if not consumer_key or not consumer_secret:
            raise ValueError(
                "FATSECRET_CONSUMER_KEY and FATSECRET_CONSUMER_SECRET must be set in environment variables. "
                "Please create a .env file with these values."
            )

        _authenticator = OAuth1Authenticator(consumer_key, consumer_secret)

    return _authenticator


def start_oauth_flow() -> dict:
    """
    Start the OAuth 1.0 flow.
    
    Returns:
        Dictionary containing authorization URL and request token
    """
    authenticator = get_authenticator()

    # Get request token
    request_token, request_token_secret = authenticator.get_request_token()

    # Create authorization URL
    auth_url = (
        f"https://authentication.fatsecret.com/oauth/authorize?"
        f"oauth_token={request_token}"
    )

    return {
        "authorization_url": auth_url,
        "request_token": request_token,
        "request_token_secret": request_token_secret
    }


def complete_oauth_flow(verifier: str) -> bool:
    """
    Complete the OAuth 1.0 flow.
    
    Args:
        verifier: OAuth verifier code from user authorization
        
    Returns:
        True if authorization successful, False otherwise
    """
    authenticator = get_authenticator()

    return authenticator.authorize_user(verifier)


def make_api_call(endpoint: str, params: dict = None) -> dict:
    """
    Make an authenticated API call using the current authenticator.
    
    Args:
        endpoint: API endpoint
        params: Dictionary of parameters
        
    Returns:
        API response as dictionary
        
    Raises:
        ValueError: If not authorized
        requests.exceptions.RequestException: If request fails
    """
    authenticator = get_authenticator()

    if not authenticator.is_authorized():
        raise ValueError("Application is not authorized. Please complete OAuth flow first.")

    return authenticator.make_authenticated_request("GET", endpoint, params)


def get_current_month_range() -> tuple[str, str]:
    """
    Get current month date range for filtering (last 3 months).
    
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    from datetime import datetime, timedelta

    today = datetime.now()
    start_date = today - timedelta(days=89)  # Approximately 3 months

    return (
        start_date.strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d")
    )
