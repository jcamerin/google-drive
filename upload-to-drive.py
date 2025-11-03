#!/opt/homebrew/bin/python3.11
# Dependencies
# pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

"""
Upload a file to Google Drive into a (possibly nested) folder path.

- Always starts at *your* My Drive root ("root")
- Path like:  "1415 Meridian/Receipts"
- Reuses existing folders (even if spacing/case is a bit different)
- Follows shortcuts to real folders
- Creates missing folders
- Makes uploaded file "anyone with the link can view"
"""

from __future__ import print_function
import os
import sys
import pickle

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 1) keep drive.file, it’s enough for files/folders you create
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

# if your JSON is named differently, change this:
CLIENT_SECRET_FILE = "google-desktop-app-client_secret_23832640834-credentials.json"
TOKEN_FILE = "token.pickle"


# ------------------------
# Auth
# ------------------------
def authenticate():
    """Authenticate and return an authorized Drive service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            # desktop flow (localhost)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


# ------------------------
# Helpers
# ------------------------
def _normalize_name(s: str) -> str:
    """
    Normalize a Drive folder name so "1415  Meridian", "1415 Meridian ",
    and "1415 Meridian" (nbspace) all compare equal.
    """
    # split() with no arg collapses whitespace (space, nbspace, tabs)
    return " ".join(s.split()).strip().lower()


def _list_child_folders_and_shortcuts(service, parent_id: str):
    """
    List all *direct* children of a parent that are either:
      - a real folder
      - a shortcut (we'll check if it points to a folder)
    """
    q = (
        f"'{parent_id}' in parents and trashed=false and "
        "("
        "mimeType='application/vnd.google-apps.folder' or "
        "mimeType='application/vnd.google-apps.shortcut'"
        ")"
    )
    resp = service.files().list(
        q=q,
        spaces="drive",
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name, mimeType, shortcutDetails)",
        pageSize=100,
    ).execute()
    return resp.get("files", [])


def find_existing_folder_in_parent(service, name: str, parent_id: str = "root"):
    """
    Try to find a child under parent_id whose *displayed name*, once normalized,
    matches the name the user typed.

    Returns the *real target folder id* if it's:
      - a folder, or
      - a shortcut to a folder
    Otherwise returns None.
    """
    target_norm = _normalize_name(name)
    children = _list_child_folders_and_shortcuts(service, parent_id)

    for item in children:
        item_name = item.get("name", "")
        if _normalize_name(item_name) != target_norm:
            continue

        mime = item.get("mimeType")
        # case 1: real folder
        if mime == "application/vnd.google-apps.folder":
            return item["id"]

        # case 2: shortcut -> see if shortcut target is folder
        if mime == "application/vnd.google-apps.shortcut":
            sc = item.get("shortcutDetails", {})
            target_id = sc.get("targetId")
            if target_id:
                target = service.files().get(
                    fileId=target_id,
                    fields="id, mimeType",
                    supportsAllDrives=True,
                ).execute()
                if (
                    target.get("mimeType")
                    == "application/vnd.google-apps.folder"
                ):
                    return target_id

    return None


def create_folder_in_parent(service, name: str, parent_id: str = "root") -> str:
    """Create a new folder under parent_id and return its id."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    print(f"🆕 Created folder '{name}' under {parent_id} -> {folder['id']}")
    return folder["id"]


def ensure_folder_path(service, folder_path: str) -> str:
    """
    Ensure a path like "1415 Meridian/Receipts" exists directly under *your* My Drive.
    Always starts at 'root'.
    """
    parts = [p for p in folder_path.replace("\\", "/").split("/") if p.strip()]
    parent_id = "root"

    for part in parts:
        existing_id = find_existing_folder_in_parent(service, part, parent_id)
        if existing_id:
            parent_id = existing_id
        else:
            parent_id = create_folder_in_parent(service, part, parent_id)

    return parent_id


def upload_file(service, file_path: str, folder_id: str | None = None) -> str:
    """Upload a file to Drive, optionally into folder_id, and return the shareable link."""
    file_name = os.path.basename(file_path)
    metadata = {"name": file_name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    file_id = uploaded["id"]

    # make it viewable by link
    permission = {"type": "anyone", "role": "reader"}
    service.permissions().create(
        fileId=file_id,
        body=permission,
        supportsAllDrives=True,
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"


def looks_like_drive_id(s: str) -> bool:
    # heuristic: long, no slashes, no extension
    if "/" in s or "\\" in s:
        return False
    if len(s) >= 20 and "." not in s:
        return True
    return False


# ------------------------
# main
# ------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_to_drive.py <file_path> [folder_path_or_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    folder_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(file_path):
        print(f"Error: file '{file_path}' does not exist.")
        sys.exit(1)

    service = authenticate()

    final_folder_id = None
    if folder_arg:
        if looks_like_drive_id(folder_arg):
            # user passed a folder ID directly
            final_folder_id = folder_arg
        else:
            # user passed a path like "1415 Meridian/Receipts"
            final_folder_id = ensure_folder_path(service, folder_arg)

    link = upload_file(service, file_path, final_folder_id)

    print("\n✅ File uploaded successfully.")
    print(f"🔗 Shareable link: {link}")
    if final_folder_id:
        print(f"📂 Uploaded into folder (id): {final_folder_id}")


if __name__ == "__main__":
    main()

