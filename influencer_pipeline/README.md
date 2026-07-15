# Influencer Outreach Automation Pipeline

A modular Python prototype designed to automate the influencer outreach workflow: 
**Data Acquisition (Mocked/Cleaned) → Database/Human-in-the-Loop Review → Automated Outreach Dispatch.**

This pipeline is built for maximum resilience. It includes a **Simulation Mode** that runs against a local CSV spreadsheet file, allowing full end-to-end testing and verification without requiring Google Sheets or SMTP credentials.

---

## 1. System Architecture Overview

The automation workflow is split into three decoupled scripts representing distinct phases:

```mermaid
graph TD
    A[sample_profiles.json] -->|Loads & Filters| B(fetch_profiles.py)
    B -->|Outputs JSON| C[fetched_profiles.json]
    C -->|Reads & Merges| D(sync_to_sheet.py)
    D -->|Real API or Fallback CSV| E{Spreadsheet DB}
    
    subgraph Human Review (Spreadsheet)
        E -->|Mark Yes/No| F[Human Approval Dashboard]
    end

    F -->|Polls Approved & Uncontacted| G(watch_and_send.py)
    G -->|Update 'contacted' to Yes| E
    G -->|Has Email| H[Send Gmail SMTP Email]
    G -->|No Email| I[Log DM Fallback]
```

1. **Phase 1: Data Acquisition (`fetch_profiles.py`)**
   - Simulates querying a data-provider API by loading records from `sample_profiles.json`.
   - Cleans the raw attributes, computes the `engagementRate` dynamically if it's missing (using mock likes and comments), filters based on command-line criteria (region, followers, and keywords), and saves the results to `fetched_profiles.json`.
2. **Phase 2: Storage & Sync (`sync_to_sheet.py`)**
   - Connects to a Google Sheet (using `gspread`) or falls back to a simulated spreadsheet (`influencer_sheet_mock.csv`).
   - Merges the incoming profiles: new profiles are appended as `Pending` approval and `No` contacted, while existing profiles have their metrics updated **without** overwriting their current human approval or contacted statuses.
3. **Phase 3: Automated Outreach (`watch_and_send.py`)**
   - Polls the spreadsheet for influencers marked `approvalStatus = Yes` and `contacted = No`.
   - Sends a personalized outreach email via SMTP (Gmail App Password) or falls back to logging a direct message (DM) outreach when no email is available.
   - Immediately updates the spreadsheet row's `contacted` column to `Yes` after each individual outreach attempt to prevent double-contacting.

---

## 2. Core Resilience Design & Logic

### Missing-Data Resilience (Phase 1 & 3)
- **Safe Field Extraction**: Every attribute extraction in `fetch_profiles.py` is wrapped in try-except blocks. If a profile is incomplete or missing fields, it defaults to `"Not specified"` rather than raising an exception.
- **Robust Parsing (`safe_cast`)**: Follower and post counts are stripped of formatting (commas, spaces) and cast to integers. If a field contains invalid data (e.g. `followers = "Fifty Thousand"`), it defaults to `"Not specified"` and flags a parser warning without crashing.
- **Calculated Metrics**: If the raw data does not contain `engagementRate`, the script looks for `likes` and `comments` fields. If they are available and followers is a valid non-zero integer, it computes the engagement rate dynamically (`((likes + comments) / followers) * 100`) and formats it as a percentage string (e.g. `4.44%`).
- **Missing Email Routing**: In `watch_and_send.py`, if an approved influencer has no email (i.e. `"Not specified"`), the system catches this and routes them to a **DM Fallback** queue, logging the exact message template to send via Instagram Direct Message.

### Duplicate-Contact Prevention (Phase 2 & 3)
- **Metrics Merging (Sync)**: When syncing new crawl data to the spreadsheet, `sync_to_sheet.py` checks for duplicates by `username`. If a username already exists, the script updates the metrics (followers, posts, etc.) but **preserves** the existing `approvalStatus` and `contacted` cells.
- **Atomic State Updates (Outreach)**: `watch_and_send.py` does not wait for the entire batch to complete before updating statuses. Immediately after an email is sent or a DM fallback is logged, the script executes a write to mark `contacted = Yes` for that specific row. This ensures that if the script crashes, runs out of memory, or has an SMTP socket error halfway through, no influencer is ever messaged twice.

---

## 3. Handling Platform Constraints & Production Scale

In a production-ready environment, you must account for API rate limits and platform restrictions:

### Instagram Data Acquisition
- **Platform ToS**: Direct scraping of Instagram violates their terms of service and results in IP blocks and account bans. 
- **Production Solution**: Swap Phase 1 with a licensed data aggregator API like **Modash**, **Phyllo**, or licensed scraper tools (e.g. **Apify's Instagram Scraper**).
- **Evasion & Throttling**: If using custom scraper scrapers, integrate proxy rotators (e.g. ScrapingBee), rotate headers/User-Agents, add random delays (jitter of 5–15 seconds) between profile hits, and implement exponential backoff on HTTP `429 Too Many Requests` responses.

### Google Sheets API Limits
- **Limits**: Google Sheets API allows 300 read/write requests per project per minute.
- **Production Solution**: 
  - Construct **Batch Updates**: Instead of calling `update_cell` for every record, `sync_to_sheet.py` aggregates cell updates into a single `batch_update()` payload and adds new profiles using `append_rows()`.
  - Use cache or local databases to diff changes before writing to Sheets.

### SMTP & Outreach limits
- **Gmail Limits**: Gmail App Passwords restrict outgoing mail to 500 emails/day (2000/day for Google Workspace).
- **Production Solution**: 
  - Swap SMTP for dedicated transactional email APIs like **SendGrid**, **Mailgun**, or **Amazon SES**.
  - Ensure **CAN-SPAM & GDPR Compliance**: Include unsubscribe links, verify domain records (SPF, DKIM, DMARC), and validate email existence before sending to prevent bounces.

---

## 4. Setup & Running the Local Prototype

### Step 1: Install Dependencies
Ensure you have Python 3.8+ installed. Navigate to the pipeline directory and install dependencies:
```bash
pip install -r requirements.txt
```

### Step 2: Running in Simulation Mode (No Credentials)
Simulation mode runs the entire pipeline end-to-end using a local CSV file (`influencer_sheet_mock.csv`) acting as the spreadsheet.

1. **Acquire Profiles (Phase 1)**
   Run the data acquisition script to extract and filter profiles from `sample_profiles.json` (e.g., filtering for profiles with at least 10k followers in any region):
   ```bash
   python fetch_profiles.py --min-followers 10000
   ```
   This creates `fetched_profiles.json` and prints the extraction summary.

2. **Sync to Spreadsheet (Phase 2)**
   Run the sync script. Since no Google credentials exist, it falls back to **Simulation Mode** and creates `influencer_sheet_mock.csv`:
   ```bash
   python sync_to_sheet.py
   ```
   All 10 profiles are saved into the CSV with `approvalStatus = Pending` and `contacted = No`.

3. **Human Review (Manual Simulation)**
   Open `influencer_sheet_mock.csv` in Excel, Notepad, or VS Code. 
   To approve profiles for outreach, change the `approvalStatus` for some rows (e.g. `alex_fitness` and `travel_couple`) from `Pending` to `Yes`. Save the file.

4. **Dispatch Outreach (Phase 3)**
   Run the outreach script:
   ```bash
   python watch_and_send.py
   ```
   The script reads the CSV, finds the approved rows, generates personalized emails or logs DM fallbacks, and writes back `contacted = Yes` immediately. Running it a second time will print "No pending approved influencers found", showing duplicate-contact prevention is working.

---

## 5. Google Sheets & Gmail SMTP Credentials Setup

For a live production run, configure actual Google Sheets and Gmail integrations:

### A. Google Sheets API Integration
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new Project.
3. Search for and enable the **Google Sheets API** and the **Google Drive API**.
4. Navigate to **IAM & Admin > Service Accounts** and click **Create Service Account**.
5. Give the account a name, assign the Role to **Project > Editor**, and proceed.
6. Under the created Service Account, go to the **Keys** tab, click **Add Key > Create New Key**, select **JSON**, and download the file.
7. Rename this file to `service_account.json` and place it in the `/influencer_pipeline` directory.
8. **CRITICAL STEP**: Open your Google Sheet in your web browser. Share the sheet (click the Share button) with the service account's email address (found in your `service_account.json` as `client_email`) with **Editor** permissions.

### B. Gmail App Password Integration
1. Go to your Google Account settings.
2. Ensure **2-Step Verification** is enabled under the Security tab.
3. Under 2-Step Verification, scroll to the bottom and click on **App passwords**.
4. Generate a new App Password (select 'Other (Custom name)' and enter "Influencer Outreach").
5. Copy the 16-character code provided.

### C. Configure Environment Variables
Create a file named `.env` in the `/influencer_pipeline` directory:
```env
# Google Sheets Setup
GOOGLE_SHEETS_CREDENTIALS_PATH=service_account.json
GOOGLE_SHEET_NAME="Influencer Outreach"

# Gmail SMTP Setup
EMAIL_USER=your_gmail_address@gmail.com
EMAIL_PASS=your_16_character_app_password
```

Once `.env` and `service_account.json` are present, running `sync_to_sheet.py` and `watch_and_send.py` will automatically connect to your real Google Sheet and send actual outreach emails!
