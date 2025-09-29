import os
import base64
import pickle
import json
import warnings
from email.message import EmailMessage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import googleapiclient.discovery_cache.base
from config.config import get_db_connection, get_db_cursor, release_db_connection



# Disable cache warnings
warnings.filterwarnings("ignore", ".*file_cache.*", module="googleapiclient.discovery_cache")

# Custom memory cache to replace file cache
class MemoryCache(googleapiclient.discovery_cache.base.Cache):
    def get(self, url):
        return None
    def set(self, url, content):
        pass

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))

# Path to client secrets / token json file
CLIENT_SECRETS_FILE = os.path.join(current_dir, 'client_secret.json')

# Load the configuration from JSON file
with open(CLIENT_SECRETS_FILE) as f:
    config = json.load(f)

# Get SCOPES from the JSON configuration with fallback to default
SCOPES = config['web'].get('gmail_scopes', ['https://www.googleapis.com/auth/gmail.send'])

# Get Credentials
def get_credentials():
    creds = None
    token_path = os.path.join(current_dir, 'token.pickle')
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save the credentials for next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


# Get influencers from database
def get_influencers(strategy_id):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    try:
        cursor.execute("""
            SELECT name, email, email_text 
            FROM influencers 
            WHERE strategy_id = %s AND email IS NOT NULL AND email_text IS NOT NULL
        """, (strategy_id,))
        
        influencers = []
        for name, email, email_text in cursor.fetchall():
            influencers.append({
                'name': name,
                'email': email,
                'email_text': email_text
            })
        
        return influencers
    except Exception as e:
        print(f"Database error: {str(e)}")
        return []
    finally:
        release_db_connection(conn)

# Send personalized emails
def send_influencer_emails(strategy_id):
    try:
        creds = get_credentials()
        service = build(
            'gmail', 
            'v1', 
            credentials=creds,
            cache=MemoryCache()
        )

        influencers = get_influencers(strategy_id)
        if not influencers:
            print("No influencers found with emails in the database")
            return False

        results = []
        for influencer in influencers:
            try:
                msg = EmailMessage()
                
                # Use the pre-generated email text from the strategy
                email_content = influencer['email_text']
                
                # Ensure proper line breaks
                email_content = email_content.replace('\n', '\r\n')
                
                msg.set_content(email_content)
                msg['To'] = influencer['email']
                msg['From'] = " Your email"
                msg['Subject'] = f"Partnership Opportunity with Your Brand - {influencer['name']}"

                encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()

                send_message = {
                    'raw': encoded_message
                }

                message = service.users().messages().send(
                    userId="me", 
                    body=send_message
                ).execute()
                
                results.append({
                    'influencer': influencer['name'],
                    'email': influencer['email'],
                    'status': 'success',
                    'message_id': message['id']
                })
                
                print(f"Email sent to {influencer['name']} at {influencer['email']}")
                
            except Exception as e:
                results.append({
                    'influencer': influencer['name'],
                    'email': influencer['email'],
                    'status': 'failed',
                    'error': str(e)
                })
                print(f"Failed to send email to {influencer['name']}: {str(e)}")

        return results
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False