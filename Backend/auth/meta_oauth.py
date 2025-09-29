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
META_CONFIG = {
    'app_id': os.getenv("META_APP_ID"),
    'app_secret': os.getenv("META_APP_SECRET"),
    'redirect_uri': os.getenv("META_REDIRECT_URI"),
    'auth_url': os.getenv("META_AUTH_URL"),
    'token_url': os.getenv("META_TOKEN_URL"),
    'user_info_url': os.getenv("META_USER_INFO_URL"),
    'pages_url': os.getenv("META_PAGES_URL"),
    'scopes': os.getenv("META_SCOPES").split(",")
}

class MetaOAuth:
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
        """Generate Facebook authorization URL"""
        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        params = {
            'client_id': META_CONFIG['app_id'],
            'redirect_uri': META_CONFIG['redirect_uri'],
            'state': state,
            'scope': ','.join(META_CONFIG['scopes']),
            'response_type': 'code',
            'config_id': "751210967557520"  # Your business configuration ID
        }
        return f"{META_CONFIG['auth_url']}?{urllib.parse.urlencode(params)}"

    async def handle_callback(self, request: Request, db_conn) -> dict:
        """Handle Facebook OAuth callback and return user data"""
        # Validate callback parameters
        if request.query_params.get('error'):
            error_desc = request.query_params.get('error_description', 'No description')
            raise HTTPException(400, f"Facebook error: {error_desc}")

        code = request.query_params.get('code')
        if not code:
            raise HTTPException(400, "Missing authorization code")

        # Exchange code for token
        token_params = {
            'client_id': META_CONFIG['app_id'],
            'client_secret': META_CONFIG['app_secret'],
            'redirect_uri': META_CONFIG['redirect_uri'],
            'code': code
        }

        try:
            # Get user access token
            response = requests.get(
                META_CONFIG['token_url'],
                params=token_params,
                timeout=10
            )
            response.raise_for_status()
            token_result = response.json()
        except Exception as e:
            raise HTTPException(500, f"Token exchange failed: {str(e)}")

        if 'access_token' not in token_result:
            raise HTTPException(400, "Invalid token response")

        user_access_token = token_result['access_token']

        # Get user profile
        try:
            profile_response = requests.get(
                META_CONFIG['user_info_url'],
                params={
                    'fields': 'id,name,email',
                    'access_token': user_access_token
                },
                timeout=10
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
        except Exception as e:
            raise HTTPException(500, f"Profile fetch failed: {str(e)}")

        if 'id' not in profile_data:
            raise HTTPException(400, "Invalid profile data")

        # Get pages and Instagram accounts
        try:
            pages_response = requests.get(
                META_CONFIG['pages_url'],
                params={
                    'fields': 'id,name,access_token,category',
                    'access_token': user_access_token
                },
                timeout=10
            )
            pages_response.raise_for_status()
            pages_data = pages_response.json().get('data', [])
        except Exception as e:
            raise HTTPException(500, f"Pages fetch failed: {str(e)}")

        accounts = []
        fb_user_id = profile_data['id']
        fb_user_name = profile_data.get('name', 'Facebook User')

        for page in pages_data:
            page_id = page['id']
            page_name = page['name']
            page_token = page['access_token']

            # Get Instagram account if connected
            instagram_id = None
            instagram_name = None
            try:
                ig_response = requests.get(
                    f"https://graph.facebook.com/v22.0/{page_id}",
                    params={
                        'fields': 'instagram_business_account{id,username,name}',
                        'access_token': page_token
                    },
                    timeout=10
                )
                ig_response.raise_for_status()
                ig_data = ig_response.json()
                
                if 'instagram_business_account' in ig_data:
                    instagram_id = ig_data['instagram_business_account']['id']
                    instagram_name = (
                        f"{ig_data['instagram_business_account'].get('username', '')} "
                        f"({ig_data['instagram_business_account'].get('name', '')})"
                    )
            except Exception:
                pass  # Instagram not connected or error fetching

            accounts.append({
                'platform': 'facebook',
                'account_id': fb_user_id,
                'account_name': page_name,
                'access_token': self._encrypt_token(page_token),
                'user_access_token': self._encrypt_token(user_access_token),
                'page_id': page_id,
                'instagram_id': instagram_id,
                'instagram_name': instagram_name
            })

            if instagram_id:
                accounts.append({
                    'platform': 'instagram',
                    'account_id': fb_user_id,
                    'account_name': instagram_name,
                    'access_token': self._encrypt_token(page_token),
                    'user_access_token': self._encrypt_token(user_access_token),
                    'page_id': page_id,
                    'instagram_id': instagram_id
                })

        return {
            'user_id': fb_user_id,
            'user_name': fb_user_name,
            'user_email': profile_data.get('email'),
            'accounts': accounts
        }