#!/opt/homebrew/bin/python3.11
# Dependencies
# Enable the Google Drive API in Google Cloud Console.
# Create an OAuth client ID (Desktop app) and download credentials.json.
# Put credentials.json in the same folder as this script.
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

from __future__ import print_function
import os.path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Common scope sets
READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
UPLOAD_SCOPES   = ["https://www.googleapis.com/auth/drive.file"]
# (You could also use "https://www.googleapis.com/auth/drive"
#  if you truly need full access.)

def get_drive_service(
    scopes=None,
    credentials_file="google-desktop-app-client_secret_23832640834-credentials.json",
    token_file=None,
):
    """
    Create and return a Google Drive API service instance.

    - scopes: list of OAuth scopes to request
    - credentials_file: client secrets JSON from Google Cloud Console
    - token_file: JSON file where the OAuth token is stored

    If token_file is not provided, we derive a filename from the first scope.
    """
    if scopes is None:
        scopes = READONLY_SCOPES

    # Derive a default token filename if not provided
    if token_file is None:
        # make a simple deterministic name from the first scope
        key = scopes[0].split("/")[-1]  # e.g. 'drive.metadata.readonly'
        token_file = f"token-{key}.json"

    creds = None

    # Load existing credentials if present
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    # If no valid credentials, or scopes changed / are missing, run the OAuth flow
    if not creds or not creds.valid:
        need_new_flow = True

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # After refresh, check if current creds cover desired scopes
                if not scopes or set(scopes).issubset(set(creds.scopes or [])):
                    need_new_flow = False
            except Exception:
                need_new_flow = True

        if need_new_flow:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=0)

        # Save the credentials for later use
        with open(token_file, "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)

