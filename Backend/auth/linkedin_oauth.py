import base64
import secrets
from datetime import datetime
from cryptography.fernet import Fernet
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import requests
import urllib.parse
import os

# Configuration - move these to your config file or environment variables
LINKEDIN_CONFIG = {
    'client_id': os.getenv("LINKEDIN_CLIENT_ID"),
    'client_secret': os.getenv("LINKEDIN_CLIENT_SECRET"),
    'redirect_uri': os.getenv("LINKEDIN_REDIRECT_URI"),
    'auth_url': os.getenv("LINKEDIN_AUTH_URL"),
    'token_url': os.getenv("LINKEDIN_TOKEN_URL"),
    'profile_url': os.getenv("LINKEDIN_PROFILE_URL"),
    'scopes': os.getenv("LINKEDIN_SCOPES").split(",")
}

class LinkedInOAuth:
    def __init__(self, encryption_key: bytes):
        self.cipher_suite = Fernet(encryption_key)

    def _encrypt_token(self, token: str) -> str:
        """Securely encrypt access token"""
        if not token:
            raise ValueError("Token cannot be empty")
        encrypted = self.cipher_suite.encrypt(token.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Securely decrypt access token"""
        if not encrypted_token:
            raise ValueError("Encrypted token cannot be empty")
        try:
            decrypted = self.cipher_suite.decrypt(base64.urlsafe_b64decode(encrypted_token.encode()))
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Token decryption failed: {str(e)}")

    def get_auth_url(self) -> str:
        """Generate LinkedIn authorization URL"""
        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        params = {
            'response_type': 'code',
            'client_id': LINKEDIN_CONFIG['client_id'],
            'redirect_uri': LINKEDIN_CONFIG['redirect_uri'],
            'state': state,
            'scope': ' '.join(LINKEDIN_CONFIG['scopes'])
        }
        return f"{LINKEDIN_CONFIG['auth_url']}?{urllib.parse.urlencode(params)}"

    async def handle_callback(self, request: Request, db_conn) -> dict:
        """Handle LinkedIn OAuth callback and return user data"""
        # Validate callback parameters
        if request.query_params.get('error'):
            error_desc = request.query_params.get('error_description', 'No description')
            raise HTTPException(400, f"LinkedIn error: {error_desc}")

        code = request.query_params.get('code')
        if not code:
            raise HTTPException(400, "Missing authorization code")

        # Exchange code for token
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': LINKEDIN_CONFIG['redirect_uri'],
            'client_id': LINKEDIN_CONFIG['client_id'],
            'client_secret': LINKEDIN_CONFIG['client_secret']
        }

        try:
            response = requests.post(
                LINKEDIN_CONFIG['token_url'],
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            response.raise_for_status()
            token_result = response.json()
        except Exception as e:
            raise HTTPException(500, f"Token exchange failed: {str(e)}")

        if 'access_token' not in token_result:
            raise HTTPException(400, "Invalid token response")

        # Get user profile
        try:
            profile_response = requests.get(
                LINKEDIN_CONFIG['profile_url'],
                headers={
                    'Authorization': f'Bearer {token_result["access_token"]}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
        except Exception as e:
            raise HTTPException(500, f"Profile fetch failed: {str(e)}")

        if 'sub' not in profile_data:
            raise HTTPException(400, "Invalid profile data")

        # Process profile data
        user_id = profile_data['sub']
        full_name = profile_data.get('name') or \
                   f"{profile_data.get('given_name', '')} {profile_data.get('family_name', '')}".strip() or \
                   f"LinkedIn User {user_id}"
        email = profile_data.get('email', '')

        return {
            'platform': 'linkedin',
            'account_id': user_id,
            'account_name': full_name,
            'access_token': self._encrypt_token(token_result['access_token']),
            'email': email
        }