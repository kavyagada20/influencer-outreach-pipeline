#!/usr/bin/env python3
"""
watch_and_send.py
Phase 3: Automated Outreach Dispatcher

Polls the spreadsheet (Google Sheets or mock CSV fallback).
Finds rows with approvalStatus == "Yes" AND contacted == "No".
Dispatches personalized emails (via SMTP) or logs DM fallback,
then immediately marks them as contacted.
"""

import os
import sys
import time
import csv
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

HEADERS = [
    "username", "fullName", "followers", "posts", "email", 
    "phoneNumber", "engagementRate", "profileUrl", "externalUrl", 
    "approvalStatus", "contacted"
]

def get_email_template(username, fullname, er):
    """Generates a personalized outreach email body."""
    # Handle default name case
    display_name = fullname if fullname != "Not specified" else "there"
    
    subject = f"Collaboration Opportunity with The Bored Monkey: @{username}"
    
    # Custom message referencing the engagement rate
    er_mention = f"outstanding engagement rate of {er}" if er != "Not specified" else "awesome content"
    
    body = f"""Hi {display_name},

My name is Alex from The Bored Monkey, and I came across your Instagram profile @{username}.

We were really impressed by your posts and your {er_mention}! We believe your audience aligns perfectly with our brand, and we would love to discuss a potential sponsorship/collaboration for our upcoming product campaign.

Are you open to discussing this? If so, please let us know your standard rates and packages.

Best regards,

Alex Johnson
Influencer Relations Team
The Bored Monkey
"""
    return subject, body

def send_real_email(to_email, username, fullname, er):
    """Sends a real email using smtplib and environment variables credentials."""
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASS")

    if not email_user or not email_pass:
        raise ValueError("SMTP credentials (EMAIL_USER/EMAIL_PASS) missing from environment variables.")

    subject, body = get_email_template(username, fullname, er)

    # Setup the MIME message
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Connect to SMTP Server (Gmail default)
    # Using SSL on port 465 or STARTTLS on port 587
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(email_user, email_pass)
    server.send_message(msg)
    server.quit()
    
    print(f"Successfully sent email outreach to {to_email}")

def process_outreach_row(row_data):
    """
    Attempts outreach for a single row.
    Returns True if outreach succeeded (email sent or DM logged), False otherwise.
    """
    username = row_data.get("username")
    fullname = row_data.get("fullName", "Not specified")
    email = row_data.get("email", "Not specified")
    er = row_data.get("engagementRate", "Not specified")

    if email != "Not specified":
        try:
            # Check if SMTP details are configured
            email_user = os.getenv("EMAIL_USER")
            email_pass = os.getenv("EMAIL_PASS")
            
            if email_user and email_pass:
                print(f"Sending real email to {email} (@{username})...")
                send_real_email(email, username, fullname, er)
            else:
                # Mock sending email (Simulation print)
                subject, body = get_email_template(username, fullname, er)
                print(f"\n[SIMULATION EMAIL] Sending email to {email} (@{username})")
                print(f"Subject: {subject}")
                print(f"Body:\n{body}")
                print("-" * 40 + "\n")
            return True
        except Exception as e:
            print(f"Error sending email to @{username} ({email}): {e}", file=sys.stderr)
            return False
    else:
        # Fallback to direct message (DM) logging
        print(f"[DM FALLBACK LOG] Username: @{username} has no email. Logging DM outreach:")
        print(f"  --> DM to @{username}: 'Hey {fullname or username}, we love your content! We couldn't find your email, but we'd love to collaborate. Drop us a DM or email if you are interested!'")
        return True

def run_simulation(csv_path):
    """Polls/processes a local mock CSV sheet."""
    if not os.path.exists(csv_path):
        print(f"Error: Mock CSV file '{csv_path}' not found. Run sync_to_sheet.py first.", file=sys.stderr)
        return

    # Read current data
    rows = []
    try:
        with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for r in reader:
                rows.append(r)
    except Exception as e:
        print(f"Error reading local CSV file: {e}", file=sys.stderr)
        return

    # Verify column headers
    if not fieldnames or not all(h in fieldnames for h in HEADERS):
        print("Error: Mock CSV headers do not match expected format.", file=sys.stderr)
        return

    processed_any = False
    for idx, row in enumerate(rows):
        if row.get("approvalStatus") == "Yes" and row.get("contacted") == "No":
            username = row.get("username")
            print(f"\nFound approved influencer to contact: @{username}")
            
            # Outreach attempt
            outreach_success = process_outreach_row(row)
            
            if outreach_success:
                # Update status immediately after sending to guarantee no double outreach
                try:
                    row["contacted"] = "Yes"
                    # Write entire CSV back immediately to persist state
                    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    print(f"Status updated in simulated sheet: @{username} -> contacted='Yes'")
                    processed_any = True
                except Exception as e:
                    print(f"Error updating CSV status for @{username}: {e}", file=sys.stderr)
            else:
                print(f"Outreach failed for @{username}, status remains 'No'.")
                
    if not processed_any:
        print("No pending approved influencers found.")

def run_google_sheets(creds_path, sheet_name):
    """Polls/processes a real Google Sheet."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Error: gspread or google-auth not installed.", file=sys.stderr)
        return False

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        sh = client.open(sheet_name)
        wks = sh.sheet1
    except Exception as e:
        print(f"Failed to authenticate/access Google Sheet: {e}", file=sys.stderr)
        return False

    try:
        # Get all sheet data
        all_values = wks.get_all_values()
        if not all_values:
            print("Google Sheet is empty.")
            return True

        header_row = all_values[0]
        header_map = {h: idx for idx, h in enumerate(header_row)}

        # Validate headers
        for col_name in ["username", "email", "fullName", "engagementRate", "approvalStatus", "contacted"]:
            if col_name not in header_map:
                print(f"Error: Missing required column '{col_name}' in Google Sheet.", file=sys.stderr)
                return True

        username_idx = header_map["username"]
        email_idx = header_map["email"]
        fullname_idx = header_map["fullName"]
        er_idx = header_map["engagementRate"]
        approval_idx = header_map["approvalStatus"]
        contacted_idx = header_map["contacted"]

        processed_any = False
        # Read starting from row index 2 (row 1 is header)
        for idx, row in enumerate(all_values[1:], start=2):
            # Check length to prevent index error
            if (len(row) > max(approval_idx, contacted_idx) and
                    row[approval_idx] == "Yes" and row[contacted_idx] == "No"):
                
                username = row[username_idx]
                fullname = row[fullname_idx] if fullname_idx < len(row) else "Not specified"
                email = row[email_idx] if email_idx < len(row) else "Not specified"
                er = row[er_idx] if er_idx < len(row) else "Not specified"

                row_data = {
                    "username": username,
                    "fullName": fullname,
                    "email": email,
                    "engagementRate": er
                }

                print(f"\nFound approved influencer to contact: @{username}")
                
                # Outreach attempt
                outreach_success = process_outreach_row(row_data)

                if outreach_success:
                    # Update cell immediately to prevent double messaging
                    try:
                        # Column numbers are 1-based index
                        wks.update_cell(idx, contacted_idx + 1, "Yes")
                        print(f"Status updated in Google Sheet: @{username} -> contacted='Yes'")
                        processed_any = True
                    except Exception as e:
                        print(f"Error updating contacted status in sheet for @{username}: {e}", file=sys.stderr)
                else:
                    print(f"Outreach failed for @{username}, status remains 'No'.")

        if not processed_any:
            print("No pending approved influencers found.")
        return True

    except Exception as e:
        print(f"Error during Google Sheets dispatch processing: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Watch spreadsheet and dispatch influencer outreach.")
    parser.add_argument("--sheet-name", type=str, default=None, help="Name of Google Sheet (defaults to env GOOGLE_SHEET_NAME)")
    parser.add_argument("--creds", type=str, default=None, help="Path to Google Service Account JSON")
    parser.add_argument("--csv-fallback", type=str, default="influencer_sheet_mock.csv", help="Simulated CSV filename")
    parser.add_argument("--poll", action="store_true", help="Run in continuous polling loop")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    parser.add_argument("--force-mock", action="store_true", help="Force run in simulation mode")

    args = parser.parse_args()

    creds_path = args.creds or os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH") or "service_account.json"
    sheet_name = args.sheet_name or os.getenv("GOOGLE_SHEET_NAME") or "Influencer Outreach"

    # Decide mode of operation
    use_google = False
    if not args.force_mock:
        if os.path.exists(creds_path):
            use_google = True

    print("Influencer Outreach Dispatcher initialized.")
    if use_google:
        print(f"Operating Mode: Real Google Sheets ('{sheet_name}')")
    else:
        print(f"Operating Mode: SIMULATION MODE (CSV: '{args.csv_fallback}')")

    if args.poll:
        print(f"Polling enabled. Checking for updates every {args.interval} seconds. Press Ctrl+C to stop.")
        try:
            while True:
                if use_google:
                    success = run_google_sheets(creds_path, sheet_name)
                    if not success:
                        print("Google Sheet access failed. Polling mock CSV file instead.")
                        run_simulation(args.csv_fallback)
                else:
                    run_simulation(args.csv_fallback)
                
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nPolling stopped by user.")
    else:
        # Single run (useful for cron jobs)
        print("Single execution run.")
        if use_google:
            success = run_google_sheets(creds_path, sheet_name)
            if not success:
                run_simulation(args.csv_fallback)
        else:
            run_simulation(args.csv_fallback)

if __name__ == "__main__":
    main()
