#!/opt/homebrew/bin/python3.11
import os, pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

def get_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("google-desktop-app-client_secret_23832640834-credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
    return build("drive", "v3", credentials=creds)

def main():
    svc = get_service()
    resp = svc.files().list(
        q="'root' in parents and trashed=false",
        spaces="drive",
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name, mimeType, shortcutDetails)",
        pageSize=200,
    ).execute()

    for f in resp.get("files", []):
        mt = f["mimeType"]
        line = f"{f['name']}  ({f['id']})  {mt}"
        if mt == "application/vnd.google-apps.shortcut":
            sd = f.get("shortcutDetails", {})
            line += f" -> shortcut to {sd.get('targetId')}"
        print(line)

if __name__ == "__main__":
    main()

