#!/usr/bin/env python3
"""
run_demo.py
Automated end-to-end pipeline demo for presentation.
Resets the simulation, runs data acquisition, syncs to sheet,
simulates user approvals, dispatches outreach, and shows updates.
"""

import os
import sys
import subprocess
import time
import csv

def print_header(title):
    print("\n" + "="*60)
    print(f" {title} ".center(60, "="))
    print("="*60)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "influencer_sheet_mock.csv")
    json_path = os.path.join(script_dir, "fetched_profiles.json")

    # 1. Reset old data
    print_header("Step 0: Resetting Simulation State")
    if os.path.exists(csv_path):
        os.remove(csv_path)
        print("Removed old simulated spreadsheet.")
    if os.path.exists(json_path):
        os.remove(json_path)
        print("Removed old fetched profiles JSON.")
    print("Clean state initialized.")
    time.sleep(1)

    # 2. Run Phase 1: Data Acquisition
    print_header("Phase 1: Running Data Acquisition (fetch_profiles.py)")
    print("Executing command: python fetch_profiles.py --min-followers 10000")
    result = subprocess.run(
        [sys.executable, "fetch_profiles.py", "--min-followers", "10000"],
        capture_output=True, text=True, cwd=script_dir
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    time.sleep(1)

    # 3. Run Phase 2: Storage Sync
    print_header("Phase 2: Syncing to Spreadsheet (sync_to_sheet.py)")
    print("Executing command: python sync_to_sheet.py --force-mock")
    result = subprocess.run(
        [sys.executable, "sync_to_sheet.py", "--force-mock"],
        capture_output=True, text=True, cwd=script_dir
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    time.sleep(1)

    # 4. Simulate human-in-the-loop review (Automatic approval of 2 candidates)
    print_header("Human-in-the-Loop: Simulating Row Approvals")
    print("Approving @alex_fitness and @travel_couple in the spreadsheet...")
    
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                # Approve these two for demonstration
                if row["username"] in ["alex_fitness", "travel_couple"]:
                    row["approvalStatus"] = "Yes"
                    print(f" -> Approved: @{row['username']} (ApprovalStatus = Yes)")
                rows.append(row)
        
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("Spreadsheet updated successfully with human review approvals.")
    else:
        print("Error: Simulated CSV file not found!")
        return
    time.sleep(1)

    # 5. Run Phase 3: Automated Outreach Dispatcher
    print_header("Phase 3: Dispatching Outreach (watch_and_send.py)")
    print("Executing command: python watch_and_send.py --force-mock")
    result = subprocess.run(
        [sys.executable, "watch_and_send.py", "--force-mock"],
        capture_output=True, text=True, cwd=script_dir
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    time.sleep(1)

    # 6. Print Final Spreadsheet Results
    print_header("Final Verification: Updated Spreadsheet State")
    with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if idx == 0:
                print(f"{row[0]:<15} | {row[1]:<15} | {row[4]:<22} | {row[9]:<14} | {row[10]:<10}")
                print("-" * 88)
            else:
                print(f"{row[0]:<15} | {row[1]:<15} | {row[4]:<22} | {row[9]:<14} | {row[10]:<10}")
                
    print("\n" + "="*60)
    print(" Demonstration Complete! ".center(60, "="))
    print("="*60)

if __name__ == "__main__":
    main()
