#!/opt/homebrew/bin/python3.11
# Dependencies
# Enable the Google Drive API in Google Cloud Console.
# Create an OAuth client ID (Desktop app) and download credentials.json.
# Put credentials.json in the same folder as this script.
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

from __future__ import print_function
import sys

from google_drive_auth import get_drive_service, READONLY_SCOPES


def find_document_id(service, name, id_only=False):
    """
    Find a non-folder document by name.

    - Follows shortcuts and uses the target file's ID
    - Deduplicates by real document ID
    - Optionally prints ID only (for scripting) when id_only=True
    """
    # Escape single quotes for the query
    safe_name = name.replace("'", r"\'")

    query = (
        f"name = '{safe_name}' "
        f"and mimeType != 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )

    results = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, shortcutDetails(targetId))",
            pageSize=100,
        )
        .execute()
    )

    files = results.get("files", [])
    if not files:
        if not id_only:
            print(f"No document found with name '{name}'")
        return None

    seen_real_ids = set()
    first_real_id = None

    for f in files:
        mime_type = f.get("mimeType")
        is_shortcut = mime_type == "application/vnd.google-apps.shortcut"

        # Resolve shortcuts
        if is_shortcut:
            real_id = f.get("shortcutDetails", {}).get("targetId")
            if not real_id:
                # Fallback in case shortcutDetails is missing for some reason
                real_id = f["id"]
        else:
            real_id = f["id"]

        # Deduplicate by real ID
        if real_id in seen_real_ids:
            continue
        seen_real_ids.add(real_id)

        # Remember the first real ID encountered
        if first_real_id is None:
            first_real_id = real_id

        if not id_only:
            suffix = " (via shortcut)" if is_shortcut else ""
            print(f"Found: {f['name']} (ID: {real_id}){suffix}")

    if first_real_id and not id_only:
        print(f"\nUsing document ID: {first_real_id}")

    if id_only and first_real_id:
        # For scripting/piping: output only the ID
        print(first_real_id)

    return first_real_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_document.py <document_name> [--id-only]")
        sys.exit(1)

    # Extract arguments
    args = sys.argv[1:]
    id_only = False
    if "--id-only" in args:
        id_only = True
        args.remove("--id-only")

    search_name = args[0]

    service = get_drive_service(scopes=READONLY_SCOPES)
    find_document_id(service, search_name, id_only=id_only)

