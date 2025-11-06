#!/opt/homebrew/bin/python3.11
# Dependencies
# Enable the Google Drive API in Google Cloud Console.
# Create an OAuth client ID (Desktop app) and download credentials.json.
# Put credentials.json in the same folder as this script.
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

from __future__ import print_function
import sys

from google_drive_auth import get_drive_service, READONLY_SCOPES


def _search_folder_under_parent(service, name, parent_id, id_only=False):
    """
    Search for a folder with a given name under a specific parent folder.
    Returns the folder dict (or None if not found).
    """
    safe_name = name.replace("'", r"\'")

    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )

    results = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType)",
            pageSize=10,
        )
        .execute()
    )

    folders = results.get("files", [])
    if not folders:
        return None

    # If multiple, just pick the first (they should be unique under a parent)
    folder = folders[0]
    if not id_only:
        print(f"Found: {folder['name']} (ID: {folder['id']}) under parent {parent_id}")

    return folder


def find_folder_id(service, name, id_only=False):
    """
    Global search for a folder by name (no path constraint).
    Returns the first matching folder ID, if any.
    """
    safe_name = name.replace("'", r"\'")

    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )

    results = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType)",
            pageSize=100,
        )
        .execute()
    )

    folders = results.get("files", [])
    if not folders:
        if not id_only:
            print(f"No folder found with name '{name}'")
        return None

    first_id = None

    for f in folders:
        folder_id = f["id"]

        if first_id is None:
            first_id = folder_id

        if not id_only:
            print(f"Found: {f['name']} (ID: {folder_id})")

    if first_id and not id_only:
        print(f"\nUsing folder ID: {first_id}")

    if id_only and first_id:
        print(first_id)

    return first_id


def find_folder_by_path(service, folder_path, id_only=False):
    """
    Resolve a folder by full path, e.g. "Parent/Sub/Target".

    - Starts at "My Drive" root
    - Walks each path component in order
    - Returns the ID of the final folder

    Example:
        "1415 Meridian/Receipts"
        "My Drive/1415 Meridian/Receipts"
    """
    # Split and clean components
    components = [c.strip() for c in folder_path.split("/") if c.strip()]

    if not components:
        if not id_only:
            print("Empty path provided.")
        return None

    # Optionally skip a leading "My Drive"
    if components[0].lower() in ("my drive", "mydrive"):
        components = components[1:]

    if not components:
        if not id_only:
            print("Path only contained 'My Drive' with no subfolders.")
        return None

    parent_id = "root"   # Google Drive "My Drive" root alias
    current_folder = None

    if not id_only:
        print(f"Resolving path from root: {folder_path}")

    for idx, name in enumerate(components):
        current_folder = _search_folder_under_parent(service, name, parent_id, id_only=id_only)
        if current_folder is None:
            if not id_only:
                partial = "/".join(components[: idx + 1])
                print(f"Path component not found: '{partial}'")
            return None

        parent_id = current_folder["id"]

    # At the end, parent_id is the ID of the final component folder
    folder_id = parent_id

    if not id_only:
        print(f"\nUsing folder ID for path '{folder_path}': {folder_id}")

    if id_only and folder_id:
        print(folder_id)

    return folder_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python find_folder.py <folder_name_or_path> [--id-only]")
        print("")
        print("Examples:")
        print('  python find_folder.py "Receipts"')
        print('  python find_folder.py "1415 Meridian/Receipts"')
        print('  python find_folder.py "My Drive/1415 Meridian/Receipts" --id-only')
        sys.exit(1)

    args = sys.argv[1:]
    id_only = False

    if "--id-only" in args:
        id_only = True
        args.remove("--id-only")

    target = args[0]

    service = get_drive_service(scopes=READONLY_SCOPES)

    # If the argument looks like a path (contains '/'), treat it as a full path.
    if "/" in target:
        find_folder_by_path(service, target, id_only=id_only)
    else:
        find_folder_id(service, target, id_only=id_only)

