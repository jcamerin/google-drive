#!/opt/homebrew/bin/python3.11
# Dependencies
#pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
# Enabled GCloud Google Sheets API
#
# Usage: add_grouped_row.py \
#  --spreadsheet-id 1AbCDeFGhiJKlmNoPqRS_tUVwxyz1234567890 \
#  --sheet-name "Receipts" \
#  --row-group-name "Meriwether Pest & Wildlife" \
#  --date "2025-11-06" \
#  --vendor "Meriwether Pest & Wildlife" \
#  --amount 125.50 \
#  --method "Amex" \
#  --receipt "https://drive.google.com/file/d/1WXYZabc123456789/view?usp=sharing" \
#  --description "Quarterly pest control service"

import argparse

from googleapiclient.discovery import build

# Use your existing auth helper
from google_drive_auth import get_drive_service

# Only need Sheets scope now
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_sheets_service():
    """
    Use google_drive_auth.get_drive_service to run the OAuth flow with
    Sheets scope, then reuse the same credentials to build a Sheets API service.
    """
    drive_service = get_drive_service(scopes=SHEETS_SCOPES)

    # Extract the underlying credentials from the drive service
    http_obj = getattr(drive_service, "_http", None)
    creds = getattr(http_obj, "credentials", None) if http_obj is not None else None
    if creds is None:
        raise RuntimeError(
            "Could not extract credentials from Drive service returned by "
            "google_drive_auth.get_drive_service()."
        )

    sheets_service = build("sheets", "v4", credentials=creds)
    return sheets_service


def append_to_group(
    sheets_service,
    spreadsheet_id,
    sheet_name,
    header_row,
    date,
    vendor,
    amount,
    method,
    receipt,
    description,
):
    """
    Append a row to the 'table' whose header is at header_row in the given sheet.

    The range 'SheetName!A<header_row>:F<header_row>' is treated as the table header.
    The API appends after the last non-empty row in that table, inserting a new row
    (inside the existing row group, assuming the group covers the table).
    """

    # No conversion of the receipt URL – write it exactly as provided
    values = [[date, vendor, amount, method, receipt, description]]

    # Anchor at the header row for this group (columns A–F)
    range_for_table = f"{sheet_name}!A{header_row}:F{header_row}"

    body = {"values": values}

    result = (
        sheets_service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_for_table,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )

    updates = result.get("updates", {})
    updated_cells = updates.get("updatedCells", 0)
    updated_range = updates.get("updatedRange", "UNKNOWN")

    print(f"Appended 1 row ({updated_cells} cells) into range: {updated_range}")


def find_header_row_by_name(sheets_service, spreadsheet_id, sheet_name, group_name):
    """
    Find the row number of the header that matches group_name (case-insensitive).
    Searches the first column (A) of the sheet.
    """
    range_to_scan = f"{sheet_name}!A1:A1000"  # adjust upper bound if needed
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_to_scan
    ).execute()
    values = result.get("values", [])
    for i, row in enumerate(values, start=1):  # 1-based row numbers
        if row and row[0].strip().lower() == group_name.strip().lower():
            return i
    raise ValueError(f"Group name '{group_name}' not found in column A of sheet '{sheet_name}'.")


def main():
    parser = argparse.ArgumentParser(
        description="Append a row to a specific row group/table in a Google Sheet."
    )

    parser.add_argument(
        "--spreadsheet-id",
        required=True,
        help="The ID of the Google Sheet (from the URL).",
    )
    parser.add_argument(
        "--sheet-name",
        required=True,
        help="The name of the worksheet/tab (e.g., 'Sheet1' or 'Expenses').",
    )
    parser.add_argument(
        "--row-group-name",
        required=True,
        help="Name of the row group (header text in column A).",
    )

    # Data fields
    parser.add_argument("--date", required=True, help="Date value for the row.")
    parser.add_argument("--vendor", required=True, help="Vendor/Merchant.")
    parser.add_argument("--amount", required=True, help="Amount (number or text).")
    parser.add_argument("--method", required=True, help="Payment method.")
    parser.add_argument(
        "--receipt",
        required=True,
        help="Receipt value (Google Drive share link or any text).",
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Description of the transaction.",
    )

    args = parser.parse_args()

    sheets_service = get_sheets_service()

    header_row_by_name = find_header_row_by_name(
        sheets_service,
        args.spreadsheet_id,
        args.sheet_name,
        args.row_group_name,
    )

    append_to_group(
        sheets_service=sheets_service,
        spreadsheet_id=args.spreadsheet_id,
        sheet_name=args.sheet_name,
        header_row=header_row_by_name,
        date=args.date,
        vendor=args.vendor,
        amount=args.amount,
        method=args.method,
        receipt=args.receipt,
        description=args.description,
    )


if __name__ == "__main__":
    main()

