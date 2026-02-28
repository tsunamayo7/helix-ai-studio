"""Submit r/LocalLLaMA post via Reddit OAuth2 API.

Uses a Reddit "script" app for OAuth2 password grant,
then submits via oauth.reddit.com/api/submit.

SETUP: Create a Reddit app at https://www.reddit.com/prefs/apps
  - Type: script
  - Name: HelixAIStudio
  - Redirect URI: http://localhost:8080
  - Save the client_id (under app name) and client_secret
  - Set environment variables:
    REDDIT_CLIENT_ID=<client_id>
    REDDIT_CLIENT_SECRET=<client_secret>
    REDDIT_USERNAME=Ok-Tap109
    REDDIT_PASSWORD=<password>
"""
import os
import json
import requests
from pathlib import Path

PROJECT = Path(__file__).parent.parent

body = (PROJECT / "scripts" / "reddit_localllama_body.txt").read_text(encoding="utf-8")
title = (
    "I built a desktop app that orchestrates Claude + your local Ollama "
    "models in a multi-phase pipeline (open source)"
)
FLAIR_ID = "ab9120c4-bf8e-11ed-ae5e-2eb8b7c7e10b"

print(f"Title: {len(title)} chars")
print(f"Body: {len(body)} chars")

# Get credentials
client_id = os.environ.get('REDDIT_CLIENT_ID', '')
client_secret = os.environ.get('REDDIT_CLIENT_SECRET', '')
username = os.environ.get('REDDIT_USERNAME', 'Ok-Tap109')
password = os.environ.get('REDDIT_PASSWORD', '')

if not client_id or not client_secret or not password:
    print("\nSetup required! Create a Reddit 'script' app:")
    print("  1. Go to https://www.reddit.com/prefs/apps")
    print("  2. Click 'create another app...' at the bottom")
    print("  3. Choose 'script' type")
    print("  4. Name: HelixAIStudio")
    print("  5. Redirect URI: http://localhost:8080")
    print("  6. Click 'create app'")
    print("  7. Set environment variables:")
    print("     set REDDIT_CLIENT_ID=<the ID under the app name>")
    print("     set REDDIT_CLIENT_SECRET=<the secret>")
    print(f"     set REDDIT_USERNAME={username}")
    print("     set REDDIT_PASSWORD=<your password>")
    print("\nThen re-run this script.")

    # Check if we already have credentials saved
    creds_file = PROJECT / "config" / "reddit_creds.json"
    if creds_file.exists():
        creds = json.loads(creds_file.read_text())
        client_id = creds.get('client_id', '')
        client_secret = creds.get('client_secret', '')
        password = creds.get('password', '')
        username = creds.get('username', username)
        print(f"\nFound saved credentials: client_id={'*' * len(client_id)}")
    else:
        print(f"\nNo saved credentials at {creds_file}")

if not client_id or not client_secret or not password:
    print("\nFATAL: Missing credentials. Exiting.")
    exit(1)

# --- OAuth2 Password Grant ---
print(f"\n=== OAuth2 Password Grant ===")
print(f"  Username: {username}")
print(f"  Client ID: {client_id[:8]}...")

auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
token_data = {
    'grant_type': 'password',
    'username': username,
    'password': password,
}
token_headers = {
    'User-Agent': 'web:HelixAIStudio:v11.9.4 (by /u/Ok-Tap109)',
}

try:
    token_resp = requests.post(
        'https://www.reddit.com/api/v1/access_token',
        auth=auth,
        data=token_data,
        headers=token_headers,
        timeout=15,
    )
    print(f"  Token status: {token_resp.status_code}")
    token_result = token_resp.json()

    if 'access_token' in token_result:
        access_token = token_result['access_token']
        print(f"  Access token: {len(access_token)} chars")
        print(f"  Token type: {token_result.get('token_type')}")
        print(f"  Scope: {token_result.get('scope')}")
        print(f"  Expires: {token_result.get('expires_in')}s")
    else:
        print(f"  Token error: {json.dumps(token_result, indent=2)}")
        exit(1)
except Exception as e:
    print(f"  Token request failed: {e}")
    exit(1)

# --- Verify identity ---
print(f"\n=== Verify identity ===")
api_headers = {
    'Authorization': f'Bearer {access_token}',
    'User-Agent': 'web:HelixAIStudio:v11.9.4 (by /u/Ok-Tap109)',
}
try:
    me_resp = requests.get(
        'https://oauth.reddit.com/api/v1/me',
        headers=api_headers,
        timeout=15,
    )
    me_data = me_resp.json()
    print(f"  Logged in as: {me_data.get('name')}")
    print(f"  Karma: {me_data.get('total_karma', 0)}")
except Exception as e:
    print(f"  /me failed: {e}")

# --- Submit ---
print(f"\n=== Submitting post ===")
submit_data = {
    'sr': 'LocalLLaMA',
    'kind': 'self',
    'title': title,
    'text': body,
    'flair_id': FLAIR_ID,
    'flair_text': 'Resources',
    'api_type': 'json',
    'resubmit': 'true',
    'nsfw': 'false',
    'spoiler': 'false',
}

try:
    resp = requests.post(
        'https://oauth.reddit.com/api/submit',
        headers={
            **api_headers,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data=submit_data,
        timeout=30,
    )
    print(f"  Status: {resp.status_code}")
    result = resp.json()
    print(f"  Response: {json.dumps(result, ensure_ascii=False, indent=2)[:2000]}")

    json_data = result.get('json', {})
    errors = json_data.get('errors', [])
    post_data = json_data.get('data', {})

    if errors:
        print(f"\n  ERRORS: {errors}")
    if post_data.get('url'):
        post_url = post_data['url']
        print(f"\n{'='*60}")
        print(f"POST SUCCESSFUL!")
        print(f"URL: {post_url}")
        print(f"{'='*60}")
    elif post_data.get('id'):
        post_url = f"https://www.reddit.com/r/LocalLLaMA/comments/{post_data['id']}"
        print(f"\n{'='*60}")
        print(f"POST SUCCESSFUL!")
        print(f"URL: {post_url}")
        print(f"{'='*60}")
    else:
        print("\n  No URL or ID in response. Post may have failed.")
except Exception as e:
    print(f"  Submit failed: {e}")
