#!/usr/bin/env python3
"""
fetch_profiles.py
Phase 1: Data Acquisition (Mocked/Simulated)

Loads and filters influencer candidates from sample_profiles.json.
Design allows swapping in a real data provider API in the future.
"""

import os
import json
import argparse
import sys

def safe_cast(val, cast_type, default=None):
    """Safely cast a value to a given type, returning default if casting fails."""
    if val is None or val == "":
        return default
    try:
        # Strip any formatting like commas or spaces if casting to number
        if cast_type in (int, float) and isinstance(val, str):
            val = val.replace(",", "").strip()
        return cast_type(val)
    except (ValueError, TypeError):
        return default

def get_profiles(region=None, min_followers=None, max_followers=None, keywords=None):
    """
    Loads candidates from sample_profiles.json and filters them.
    Implements robust field extraction to prevent crashes.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "sample_profiles.json")
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.", file=sys.stderr)
        return []

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_profiles = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}", file=sys.stderr)
        return []

    matched_profiles = []
    total_processed = 0
    skipped_errors = 0
    skipped_filters = 0

    for idx, raw in enumerate(raw_profiles):
        total_processed += 1
        username = "Unknown"
        try:
            # 1. Critical Field Extraction: Username
            # If username is missing, we cannot track this influencer.
            username = raw.get("username")
            if not username:
                raise ValueError("Missing critical field: 'username'")
            
            # 2. Resilient Field Extractions
            fullName = raw.get("fullName", "Not specified")
            if fullName is None:
                fullName = "Not specified"
                
            followers = safe_cast(raw.get("followers"), int, default="Not specified")
            posts = safe_cast(raw.get("posts"), int, default="Not specified")
            email = raw.get("email") or "Not specified"
            phoneNumber = raw.get("phoneNumber") or "Not specified"
            profileUrl = raw.get("profileUrl") or "Not specified"
            externalUrl = raw.get("externalUrl") or "Not specified"
            
            # Region and Biography are used for filtering
            profile_region = raw.get("region") or "Not specified"
            biography = raw.get("biography") or ""

            # 3. Calculate engagementRate if not present
            engagementRate = raw.get("engagementRate")
            if not engagementRate or engagementRate == "Not specified":
                likes = safe_cast(raw.get("likes"), int)
                comments = safe_cast(raw.get("comments"), int)
                
                if (likes is not None and comments is not None and 
                        isinstance(followers, int) and followers > 0):
                    er_val = ((likes + comments) / followers) * 100
                    engagementRate = f"{er_val:.2f}%"
                else:
                    engagementRate = "Not specified"
            
            # Verify if this profile is marked as private
            is_private = raw.get("private", False)

            # Ensure we default none values
            if not email or email == "null":
                email = "Not specified"
            if not phoneNumber or phoneNumber == "null":
                phoneNumber = "Not specified"
            if not externalUrl or externalUrl == "null":
                externalUrl = "Not specified"

            # Check for bad data that would block filtering
            if followers == "Not specified" and (min_followers is not None or max_followers is not None):
                raise ValueError(f"Followers field is invalid or missing, blocking range filter evaluation")

            # 4. Filter Evaluation
            # Region filter
            if region and region.lower() != "any":
                if profile_region.lower() != region.lower():
                    skipped_filters += 1
                    continue

            # Follower range filter
            if min_followers is not None:
                if followers == "Not specified" or followers < min_followers:
                    skipped_filters += 1
                    continue
            if max_followers is not None:
                if followers == "Not specified" or followers > max_followers:
                    skipped_filters += 1
                    continue

            # Keywords filter (checks biography, username, fullName)
            if keywords:
                # If keywords is a string, split by comma
                if isinstance(keywords, str):
                    kw_list = [k.strip().lower() for k in keywords.split(",")]
                else:
                    kw_list = [k.lower() for k in keywords]
                
                bio_lower = biography.lower()
                username_lower = username.lower()
                name_lower = fullName.lower()
                
                # Check if any keyword matches
                match_found = False
                for kw in kw_list:
                    if kw in bio_lower or kw in username_lower or kw in name_lower:
                        match_found = True
                        break
                
                if not match_found:
                    skipped_filters += 1
                    continue

            # Formulate result matching required schema
            parsed_profile = {
                "username": username,
                "fullName": fullName,
                "followers": followers,
                "posts": posts,
                "email": email,
                "phoneNumber": phoneNumber,
                "engagementRate": engagementRate,
                "profileUrl": profileUrl,
                "externalUrl": externalUrl
            }
            matched_profiles.append(parsed_profile)

        except Exception as e:
            print(f"Warning: Failed to extract/process profile index {idx} (username: {username}). Error: {e}", file=sys.stderr)
            skipped_errors += 1

    print("\n--- Extraction Summary ---")
    print(f"Total Profiles Processed: {total_processed}")
    print(f"Skipped due to Errors:   {skipped_errors}")
    print(f"Skipped by Filters:      {skipped_filters}")
    print(f"Successfully Matched:    {len(matched_profiles)}")
    print("--------------------------\n")

    return matched_profiles

def main():
    parser = argparse.ArgumentParser(description="Acquire and filter influencer profiles (Mocked).")
    parser.add_argument("--region", type=str, default=None, help="Filter by region (e.g. US, UK, IN)")
    parser.add_argument("--min-followers", type=int, default=None, help="Minimum follower count")
    parser.add_argument("--max-followers", type=int, default=None, help="Maximum follower count")
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords to filter bios/names")
    parser.add_argument("--output", type=str, default="fetched_profiles.json", help="Path to save matched profiles JSON")

    args = parser.parse_args()

    profiles = get_profiles(
        region=args.region,
        min_followers=args.min_followers,
        max_followers=args.max_followers,
        keywords=args.keywords
    )

    # Save to file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, args.output)
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2)
        print(f"Saved {len(profiles)} profiles to {output_path}")
    except Exception as e:
        print(f"Error saving profiles to file: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
