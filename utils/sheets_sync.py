"""
utils/sheets_sync.py
=====================
Syncs the application tracker to Google Sheets in real-time.
Works without running the laptop -- opens on phone via Google Sheets app.

Setup (one-time, 10 minutes):
1. Go to console.cloud.google.com
2. New project -> Enable Google Sheets API + Google Drive API
3. Create Service Account -> Download JSON key
4. Save JSON key to config/google_service_account.json
5. Create a new Google Sheet -> copy the Sheet ID from the URL
6. Share the sheet with the service account email (from the JSON file)
7. Add GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON to .env
"""

import os
import json
from datetime import datetime
from utils.logger import log

SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "config/google_service_account.json")


def is_configured() -> bool:
    """Check if Google Sheets is properly configured."""
    return bool(SHEETS_ID) and os.path.exists(SERVICE_ACCOUNT_JSON)


def get_client():
    """Get authenticated Google Sheets client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=scopes)
        return gspread.authorize(creds)
    except ImportError:
        log.warning("gspread not installed. Run: py -m pip install gspread google-auth")
        return None
    except Exception as e:
        log.error(f"Google Sheets auth failed: {e}")
        return None


def sync_tracker_to_sheets(tracker_df, sheet_name: str = "Job Tracker"):
    """
    Push the full application tracker DataFrame to Google Sheets.
    Creates the sheet if it doesn't exist.
    """
    if not is_configured():
        log.info("Google Sheets not configured -- skipping sync")
        return False

    client = get_client()
    if not client:
        return False

    try:
        spreadsheet = client.open_by_key(SHEETS_ID)

        # Get or create the worksheet
        try:
            ws = spreadsheet.worksheet(sheet_name)
            ws.clear()
        except Exception:
            ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=25)

        # Write headers + data
        if not tracker_df.empty:
            headers = list(tracker_df.columns)
            rows = tracker_df.fillna("").values.tolist()
            all_data = [headers] + [[str(v) for v in row] for row in rows]
            ws.update(all_data, value_input_option="RAW")

            # Format header row
            ws.format("1:1", {
                "backgroundColor": {"red": 0.04, "green": 0.09, "blue": 0.16},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER",
            })

            log.info(f"Google Sheets synced: {len(tracker_df)} rows -> {sheet_name}")
        return True

    except Exception as e:
        log.error(f"Google Sheets sync failed: {e}")
        return False


def sync_daily_summary_to_sheets(summary: dict, scan_name: str = "Morning"):
    """
    Push daily summary stats to a Summary sheet tab.
    """
    if not is_configured():
        return False

    client = get_client()
    if not client:
        return False

    try:
        spreadsheet = client.open_by_key(SHEETS_ID)

        try:
            ws = spreadsheet.worksheet("Daily Summary")
        except Exception:
            ws = spreadsheet.add_worksheet(title="Daily Summary", rows=500, cols=10)
            ws.update([["Date", "Scan", "Time", "Jobs Found", "APPLY",
                        "Investigate", "Emails Sent", "Applied", "Interviews", "Notes"]])

        # Append today's scan row
        row = [
            datetime.now().strftime("%Y-%m-%d"),
            scan_name,
            datetime.now().strftime("%I:%M %p"),
            summary.get("raw_jobs", 0),
            summary.get("apply", 0),
            summary.get("investigate", 0),
            summary.get("emails_generated", 0),
            summary.get("total_applied", 0),
            summary.get("interviews", 0),
            summary.get("notes", ""),
        ]
        ws.append_row(row)
        log.info(f"Daily summary synced to Google Sheets: {scan_name}")
        return True

    except Exception as e:
        log.error(f"Summary sync failed: {e}")
        return False


def setup_google_sheets_instructions():
    """Print setup instructions if not configured."""
    print("""
=== GOOGLE SHEETS SETUP (one-time, ~10 minutes) ===

1. Go to: console.cloud.google.com
   - Create new project (name it anything)
   - Enable: Google Sheets API + Google Drive API

2. Create Service Account:
   - IAM & Admin -> Service Accounts -> Create
   - Role: Editor
   - Keys -> Add Key -> JSON -> Download
   - Save as: config/google_service_account.json

3. Create Google Sheet:
   - Go to sheets.google.com -> New blank sheet
   - Name it: "Cybersecurity Job Tracker"
   - Copy the Sheet ID from the URL:
     docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit

4. Share the sheet:
   - Click Share -> paste the service account email
     (found inside your JSON file as "client_email")
   - Give Editor access

5. Add to your .env file:
   GOOGLE_SHEETS_ID=paste_your_sheet_id_here
   GOOGLE_SERVICE_ACCOUNT_JSON=config/google_service_account.json

6. Install the required library:
   py -m pip install gspread google-auth

Done! The sheet will auto-sync every time the scanner runs.
You can view it on your phone via the Google Sheets app.
""")
