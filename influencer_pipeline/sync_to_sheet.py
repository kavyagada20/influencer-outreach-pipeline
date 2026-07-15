#!/usr/bin/env python3
"""
sync_to_sheet.py
Phase 2: Storage & Human-in-the-Loop Review

Connects to Google Sheets via gspread. If credentials are missing,
it falls back to Simulation Mode using a local CSV file.
Prevents duplicate entries and preserves user review statuses.
"""

import os
import sys
import json
import csv
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# The columns required by the marketing workflow
HEADERS = [
    "username", "fullName", "followers", "posts", "email", 
    "phoneNumber", "engagementRate", "profileUrl", "externalUrl", 
    "approvalStatus", "contacted"
]

def load_fetched_profiles(json_path):
    """Loads the matched profiles JSON from Phase 1."""
    if not os.path.exists(json_path):
        print(f"Error: Fetched profiles file '{json_path}' not found.", file=sys.stderr)
        print("Please run fetch_profiles.py first to generate this file.", file=sys.stderr)
        sys.exit(1)
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}", file=sys.stderr)
        sys.exit(1)

def run_simulation(profiles, csv_path):
    """Simulates Google Sheets updates using a local CSV file."""
    print("\n--- Running in SIMULATION MODE ---")
    print(f"Spreadsheet simulated via local CSV: {os.path.abspath(csv_path)}")

    # 1. Read existing rows
    existing_rows = []
    username_to_row = {} # Maps username -> index in existing_rows list

    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # Verify headers match
                if reader.fieldnames and all(h in reader.fieldnames for h in HEADERS):
                    for idx, row in enumerate(reader):
                        existing_rows.append(row)
                        username_to_row[row["username"]] = idx
                else:
                    print("Warning: CSV headers mismatch. Overwriting with correct format.")
        except Exception as e:
            print(f"Warning: Failed to read existing CSV ({e}). Creating new.")

    added_count = 0
    updated_count = 0
    skipped_count = 0

    # 2. Sync profiles
    for p in profiles:
        username = p["username"]
        
        # Prepare the row data
        row_data = {
            "username": username,
            "fullName": p.get("fullName", "Not specified"),
            "followers": str(p.get("followers", "Not specified")),
            "posts": str(p.get("posts", "Not specified")),
            "email": p.get("email", "Not specified"),
            "phoneNumber": p.get("phoneNumber", "Not specified"),
            "engagementRate": p.get("engagementRate", "Not specified"),
            "profileUrl": p.get("profileUrl", "Not specified"),
            "externalUrl": p.get("externalUrl", "Not specified")
        }

        if username in username_to_row:
            # Update case: Keep existing approvalStatus and contacted columns
            existing_idx = username_to_row[username]
            existing_profile = existing_rows[existing_idx]
            
            # Check if values actually changed to avoid redundant writes
            changed = False
            for key in HEADERS[:-2]:  # compare all fields except approvalStatus and contacted
                if existing_profile.get(key) != row_data[key]:
                    existing_profile[key] = row_data[key]
                    changed = True
            
            if changed:
                updated_count += 1
                print(f"Updated profile metrics for: @{username}")
            else:
                skipped_count += 1
        else:
            # Add case: Default approvalStatus to Pending and contacted to No
            row_data["approvalStatus"] = "Pending"
            row_data["contacted"] = "No"
            existing_rows.append(row_data)
            username_to_row[username] = len(existing_rows) - 1
            added_count += 1
            print(f"Added new profile: @{username} (Pending approval)")

    # 3. Write back to CSV
    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(existing_rows)
        print("\n--- Simulation Sync Complete ---")
        print(f"Added:   {added_count}")
        print(f"Updated: {updated_count}")
        print(f"Skipped (No changes): {skipped_count}")
        print(f"Total rows in simulated sheet: {len(existing_rows)}")
        print("---------------------------------\n")
    except Exception as e:
        print(f"Error saving to simulated sheet: {e}", file=sys.stderr)
        sys.exit(1)

def run_google_sheets(profiles, creds_path, sheet_name):
    """Syncs profiles to a real Google Sheet using gspread."""
    print("\n--- Connecting to Google Sheets API ---")
    print(f"Credential Path: {os.path.abspath(creds_path)}")
    print(f"Target Sheet:    {sheet_name}")

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Error: gspread or google-auth is not installed.", file=sys.stderr)
        print("Please run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        print("Falling back to Simulation Mode as a safety measure.", file=sys.stderr)
        return False

    try:
        # Open the spreadsheet, create it if it doesn't exist (if sharing permission allows)
        try:
            sh = client.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"Spreadsheet '{sheet_name}' not found. Attempting to create it...")
            sh = client.create(sheet_name)
            # Sharing credentials instructions are printed in README
            print(f"Created new spreadsheet '{sheet_name}'. Note: You must share this sheet with your service account email.")

        wks = sh.sheet1
    except Exception as e:
        print(f"Failed to access sheet '{sheet_name}': {e}", file=sys.stderr)
        print("Please verify the spreadsheet name and that the service account is shared on it.", file=sys.stderr)
        print("Falling back to Simulation Mode.", file=sys.stderr)
        return False

    try:
        # Read all rows in sheet
        all_values = wks.get_all_values()
        
        # Setup sheet headers if empty
        if not all_values:
            wks.append_row(HEADERS)
            all_values = [HEADERS]
            
        header_row = all_values[0]
        # Map headers to column index (0-based)
        header_map = {h: idx for idx, h in enumerate(header_row)}
        
        # Verify headers match requirements
        for h in HEADERS:
            if h not in header_map:
                print(f"Warning: Sheet is missing column '{h}'. Appending it.")
                # Add missing column
                wks.update_cell(1, len(header_row) + 1, h)
                header_row.append(h)
                header_map[h] = len(header_row) - 1

        # Build index mapping username -> row number (1-based sheet index)
        username_col_idx = header_map["username"]
        username_to_row_num = {}
        for row_idx, row in enumerate(all_values[1:], start=2):
            if len(row) > username_col_idx:
                username_to_row_num[row[username_col_idx]] = row_idx

        added_count = 0
        updated_count = 0
        skipped_count = 0

        # Construct batch updates to reduce API calls (extremely crucial for rate limits!)
        # We will collect cell updates and run them in batch if modifying existing rows
        cell_updates = []
        rows_to_append = []

        for p in profiles:
            username = p["username"]
            
            # Formulate full row list matching header positions
            row_data = ["" for _ in HEADERS]
            row_data[header_map["username"]] = username
            row_data[header_map["fullName"]] = p.get("fullName", "Not specified")
            row_data[header_map["followers"]] = str(p.get("followers", "Not specified"))
            row_data[header_map["posts"]] = str(p.get("posts", "Not specified"))
            row_data[header_map["email"]] = p.get("email", "Not specified")
            row_data[header_map["phoneNumber"]] = p.get("phoneNumber", "Not specified")
            row_data[header_map["engagementRate"]] = p.get("engagementRate", "Not specified")
            row_data[header_map["profileUrl"]] = p.get("profileUrl", "Not specified")
            row_data[header_map["externalUrl"]] = p.get("externalUrl", "Not specified")

            if username in username_to_row_num:
                # Update case: Compare existing row cell values
                row_num = username_to_row_num[username]
                existing_row = all_values[row_num - 1]
                
                changed = False
                # Update columns excluding approvalStatus and contacted
                for h in HEADERS[:-2]:
                    col_idx = header_map[h]
                    new_val = row_data[col_idx]
                    old_val = existing_row[col_idx] if col_idx < len(existing_row) else ""
                    
                    if str(old_val) != str(new_val):
                        # Queue cell update: row_num, col_num (1-based), new value
                        cell_updates.append({
                            'range': gspread.utils.rowcol_to_a1(row_num, col_idx + 1),
                            'values': [[new_val]]
                        })
                        changed = True
                
                if changed:
                    updated_count += 1
                    print(f"Queued metrics update for existing influencer: @{username}")
                else:
                    skipped_count += 1
            else:
                # Add case: set default columns
                row_data[header_map["approvalStatus"]] = "Pending"
                row_data[header_map["contacted"]] = "No"
                rows_to_append.append(row_data)
                added_count += 1
                print(f"Queued new influencer: @{username}")

        # Execute updates in batches
        if cell_updates:
            wks.batch_update(cell_updates)
            
        if rows_to_append:
            wks.append_rows(rows_to_append)

        print("\n--- Google Sheets Sync Complete ---")
        print(f"Added:   {added_count}")
        print(f"Updated: {updated_count}")
        print(f"Skipped (No changes): {skipped_count}")
        print("------------------------------------\n")
        return True

    except Exception as e:
        print(f"Error during Google Sheets operation: {e}", file=sys.stderr)
        print("Falling back to Simulation Mode.", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Sync fetched profiles to Google Sheets or Local CSV simulation.")
    parser.add_argument("--input", type=str, default="fetched_profiles.json", help="Path to fetched profiles JSON")
    parser.add_argument("--sheet-name", type=str, default=None, help="Name of Google Sheet (defaults to env GOOGLE_SHEET_NAME)")
    parser.add_argument("--creds", type=str, default=None, help="Path to Google Service Account JSON (defaults to env GOOGLE_SHEETS_CREDENTIALS_PATH)")
    parser.add_argument("--csv-fallback", type=str, default="influencer_sheet_mock.csv", help="Simulated CSV filename")
    parser.add_argument("--force-mock", action="store_true", help="Force run in simulation mode")

    args = parser.parse_args()

    profiles = load_fetched_profiles(args.input)

    # Determine credentials path
    creds_path = args.creds or os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH") or "service_account.json"
    sheet_name = args.sheet_name or os.getenv("GOOGLE_SHEET_NAME") or "Influencer Outreach"

    # Decide mode of operation
    use_google = False
    if not args.force_mock:
        if os.path.exists(creds_path):
            use_google = True
        else:
            print(f"Service account credentials not found at '{creds_path}'.")

    if use_google:
        success = run_google_sheets(profiles, creds_path, sheet_name)
        if not success:
            run_simulation(profiles, args.csv_fallback)
    else:
        run_simulation(profiles, args.csv_fallback)

if __name__ == "__main__":
    main()
