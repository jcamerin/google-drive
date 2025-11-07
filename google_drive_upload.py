#!/opt/homebrew/bin/python3.11
# Dependencies
# Enable the Google Drive API in Google Cloud Console.
# Create an OAuth client ID (Desktop app) and download credentials.json.
# Put credentials.json in the same folder as this script.
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
#
# Usage:
#   python upload-to-drive.py /path/to/file
#   python upload-to-drive.py /path/to/file "Parent/SubFolder"
#   python upload-to-drive.py /path/to/file <folderId>
#
# If a folder path is provided (contains '/'), it is resolved using find_folder.py.
# If a plain string (no '/'), it is treated as a folder ID (e.g., from find_folder.py --id-only).

import os
import sys
from typing import Optional

from googleapiclient.http import MediaFileUpload

from google_drive_auth import get_drive_service, UPLOAD_SCOPES
from google_drive_find_folder import find_folder_by_path  # reuse your existing folder lookup


def upload_file(service, file_path: str, folder_id: Optional[str] = None) -> str:
    """
    Upload a file to Google Drive.

    - If folder_id is provided, the file is created inside that folder.
    - Returns a shareable "anyone with the link can view" URL.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)

    file_metadata = {"name": file_name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(file_path, resumable=True)

    print(f"⬆️  Uploading '{file_name}' to Google Drive...")

    created = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, parents, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id = created["id"]

    # Make it "anyone with the link can view"
    print("🔐 Setting permission: anyone with the link can view...")
    service.permissions().create(
        fileId=file_id,
        body={
            "type": "anyone",
            "role": "reader",
        },
        fields="id",
    ).execute()

    link = created.get(
        "webViewLink", f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    )
    return link


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python upload-to-drive.py /path/to/file")
        print('  python upload-to-drive.py /path/to/file "Parent/SubFolder"')
        print("  python upload-to-drive.py /path/to/file <folderId>")
        sys.exit(1)

    file_path = sys.argv[1]
    folder_arg = sys.argv[2] if len(sys.argv) >= 3 else None

    service = get_drive_service(scopes=UPLOAD_SCOPES)

    folder_id = None

    if folder_arg:
        # If it looks like a path (has '/'), let find_folder.py resolve it.
        if "/" in folder_arg:
            print(f"📁 Resolving folder path via find_folder.py: {folder_arg}")
            folder_id = find_folder_by_path(service, folder_arg, id_only=True)
            if not folder_id:
                print(f"❌ Folder path not found: {folder_arg}")
                sys.exit(1)
        else:
            # Otherwise, assume it's already a folder ID (e.g. from find_folder.py --id-only)
            folder_id = folder_arg
            print(f"📌 Using provided folder ID: {folder_id}")

    link = upload_file(service, file_path, folder_id)

    print("\n✅ File uploaded successfully.")
    print(f"🔗 Shareable link: {link}")
    if folder_id:
        print(f"📂 Uploaded into folder (id): {folder_id}")


if __name__ == "__main__":
    main()

