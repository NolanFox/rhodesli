#!/usr/bin/env python3
"""Seed life_events table with key Rhodes community events.

Usage:
    python scripts/seed_life_events.py [--dry-run]
"""

import argparse
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SEED_EVENTS = [
    {
        "event_type": "immigration",
        "title": "Jewish Community Expelled from Rhodes",
        "description": "The entire Jewish community of Rhodes (approximately 1,700 people) was deported by Nazi forces on July 23, 1944.",
        "location_name": "Rhodes, Greece",
        "lat": 36.4341,
        "lng": 28.2176,
        "event_date": "1944-07-23",
        "event_year": 1944,
        "date_precision": "exact",
    },
    {
        "event_type": "immigration",
        "title": "Arrival at Auschwitz-Birkenau",
        "description": "After a harrowing sea and train journey, the Jews of Rhodes arrived at Auschwitz-Birkenau on August 16, 1944.",
        "location_name": "Auschwitz-Birkenau, Poland",
        "lat": 50.0343,
        "lng": 19.1784,
        "event_date": "1944-08-16",
        "event_year": 1944,
        "date_precision": "exact",
    },
    {
        "event_type": "immigration",
        "title": "Early Rhodes Immigration to the Americas",
        "description": "Beginning in the early 1900s, Jews from Rhodes emigrated to the Americas, settling in communities in New York, Seattle, Los Angeles, Zimbabwe, and the Belgian Congo.",
        "location_name": "Various",
        "event_year": 1900,
        "date_precision": "year",
    },
    {
        "event_type": "holiday",
        "title": "La Cena — Passover Seder Tradition",
        "description": "The Rhodesli community maintained distinctive Sephardic Passover traditions, including unique Ladino songs and recipes.",
        "location_name": "Rhodes, Greece",
        "lat": 36.4341,
        "lng": 28.2176,
        "event_year": 1920,
        "date_precision": "year",
    },
    {
        "event_type": "reunion",
        "title": "Rhodes Jewish Community Reunion",
        "description": "Annual reunions of the Rhodes diaspora community, keeping alive connections between survivors and descendants.",
        "location_name": "Various cities",
        "event_year": 1960,
        "date_precision": "year",
    },
]


def main():
    parser = argparse.ArgumentParser(description="Seed life_events table")
    parser.add_argument("--dry-run", action="store_true", help="Print events without inserting")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — would insert:")
        for event in SEED_EVENTS:
            print(f"  - {event['title']} ({event.get('event_year', '?')})")
        return

    from app.supabase_data import get_supabase_client

    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)

    # Check for existing events to avoid duplicates
    existing = client.table("life_events").select("title").execute()
    existing_titles = {e["title"] for e in (existing.data or [])}

    inserted = 0
    for event in SEED_EVENTS:
        if event["title"] in existing_titles:
            print(f"  SKIP (exists): {event['title']}")
            continue

        result = client.table("life_events").insert(event).execute()
        if result.data:
            print(f"  INSERTED: {event['title']}")
            inserted += 1
        else:
            print(f"  FAILED: {event['title']}")

    print(f"\nDone. Inserted {inserted} events, skipped {len(SEED_EVENTS) - inserted}.")


if __name__ == "__main__":
    main()
