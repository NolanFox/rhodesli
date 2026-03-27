#!/usr/bin/env python3
"""
PRD-059 Phase 2: Event Grouping for Temporal Co-occurrence Analysis.

Groups dated photos containing Esther Burd Fox or Albert Fox into "events"
based on temporal proximity (±2 years) and shared faces. Identifies frequent
unidentified companions and tracks their age trajectories.

Usage:
    python scripts/event_grouping.py
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ESTHER_ID = "65207728-9ee6-48c1-be68-a2da23354caf"
ALBERT_ID = "85546ebf-75b9-4971-a9d4-b2ce2271bc19"
YEAR_TOLERANCE = 2
FREQUENT_COMPANION_THRESHOLD = 2

ROOT = Path(__file__).resolve().parent.parent
DATE_LABELS_PATH = ROOT / "rhodesli_ml" / "data" / "date_labels.json"
PHOTO_INDEX_PATH = ROOT / "data" / "photo_index.json"
OUTPUT_PATH = ROOT / "rhodesli_ml" / "data" / "event_groups.json"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_date_labels():
    """Load gemini_batch_full date labels."""
    with open(DATE_LABELS_PATH) as f:
        data = json.load(f)
    labels = data.get("labels", [])
    return {l["photo_id"]: l for l in labels if l.get("source_method") == "gemini_batch_full"}


def load_photo_index():
    """Load photo_index.json."""
    with open(PHOTO_INDEX_PATH) as f:
        return json.load(f)


def load_identities_from_supabase():
    """Load all identities from Supabase and build lookup maps."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set", file=sys.stderr)
        sys.exit(1)

    sb = create_client(url, key)

    all_identities = []
    offset = 0
    while True:
        r = (
            sb.table("identities")
            .select("identity_id,name,state,anchor_ids,candidate_ids")
            .range(offset, offset + 999)
            .execute()
        )
        all_identities.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000

    # Build face_id -> identity_id map
    face_to_identity = {}
    identity_lookup = {}
    for ident in all_identities:
        iid = ident["identity_id"]
        identity_lookup[iid] = ident
        for fid in ident.get("anchor_ids") or []:
            face_to_identity[fid] = iid
        for fid in ident.get("candidate_ids") or []:
            if fid not in face_to_identity:
                face_to_identity[fid] = iid

    return identity_lookup, face_to_identity


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_photos_for_person(person_id, face_to_identity, face_to_photo):
    """Get all photo_ids containing a given person."""
    photo_ids = set()
    for face_id, identity_id in face_to_identity.items():
        if identity_id == person_id and face_id in face_to_photo:
            photo_ids.add(face_to_photo[face_id])
    return photo_ids


def build_photo_face_identities(photo_id, photos, face_to_photo_inv, face_to_identity):
    """For a photo, return list of (face_id, identity_id_or_None, name_or_None)."""
    photo = photos.get(photo_id, {})
    face_ids = photo.get("face_ids", [])
    result = []
    for fid in face_ids:
        iid = face_to_identity.get(fid)
        result.append((fid, iid))
    return result


def group_into_events(dated_photos, face_to_photo, photos, face_to_identity):
    """
    Group photos into events using 5-year sliding windows.

    Union-find with ±2 year tolerance creates transitive snowball chains
    (Lesson 115): A(1920)-B(1922)-C(1924)-D(1926) all merge into one mega-event
    spanning 6+ years. Instead, we use fixed 5-year windows (centered on each
    half-decade) which produce stable, non-snowballing groups.

    Within each window, photos are further split by whether they share at least
    one identified person. Photos sharing identities form a connected sub-event;
    isolated photos become singletons.
    """
    # Build photo_id -> set of identity_ids
    photo_identities = {}
    for pid, label in dated_photos.items():
        photo = photos.get(pid, {})
        face_ids = photo.get("face_ids", [])
        identities = set()
        for fid in face_ids:
            iid = face_to_identity.get(fid)
            if iid:
                identities.add(iid)
        photo_identities[pid] = identities

    # Determine year range
    years = [
        label.get("best_year_estimate")
        for label in dated_photos.values()
        if label.get("best_year_estimate") is not None
    ]
    if not years:
        return []

    min_year = min(years)
    max_year = max(years)

    # Create 5-year windows: 1915-1919, 1920-1924, etc.
    window_start = (min_year // 5) * 5
    windows = []
    while window_start <= max_year:
        windows.append((window_start, window_start + 4))
        window_start += 5

    all_groups = []
    for w_start, w_end in windows:
        # Photos in this window
        window_photos = [
            (pid, label)
            for pid, label in dated_photos.items()
            if label.get("best_year_estimate") is not None and w_start <= label["best_year_estimate"] <= w_end
        ]
        if not window_photos:
            continue

        # Within the window, use union-find on shared identities
        n = len(window_photos)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            pid_i = window_photos[i][0]
            ids_i = photo_identities.get(pid_i, set())
            for j in range(i + 1, n):
                pid_j = window_photos[j][0]
                ids_j = photo_identities.get(pid_j, set())
                if ids_i & ids_j:
                    union(i, j)

        groups = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(i)

        for indices in groups.values():
            all_groups.append([window_photos[i] for i in indices])

    return all_groups


def analyze_events(
    event_groups,
    photos,
    face_to_identity,
    identity_lookup,
    date_labels,
):
    """Analyze each event group for faces, identifications, companions."""
    results = []

    for group in event_groups:
        photo_ids = [pid for pid, _ in group]
        years = [label.get("best_year_estimate") for _, label in group if label.get("best_year_estimate") is not None]
        date_range = [min(years), max(years)] if years else None

        # Collect all faces in the group
        all_faces = {}  # face_id -> list of (photo_id, face_analysis_entry or None)
        for pid, label in group:
            photo = photos.get(pid, {})
            face_ids = photo.get("face_ids", [])
            face_analysis = label.get("face_analysis", [])

            for idx, fid in enumerate(face_ids):
                if fid not in all_faces:
                    all_faces[fid] = []
                fa_entry = face_analysis[idx] if idx < len(face_analysis) else None
                all_faces[fid].append(
                    {
                        "photo_id": pid,
                        "year": label.get("best_year_estimate"),
                        "face_analysis": fa_entry,
                    }
                )

        # Classify faces
        identified = {}
        unidentified = {}
        for fid, appearances in all_faces.items():
            iid = face_to_identity.get(fid)
            if iid:
                ident = identity_lookup.get(iid, {})
                name = ident.get("name", "Unknown")
                is_named = not name.startswith("Unidentified Person")
                if is_named:
                    identified[fid] = {
                        "identity_id": iid,
                        "name": name,
                        "appearances": len(appearances),
                    }
                else:
                    unidentified[fid] = {
                        "identity_id": iid,
                        "name": name,
                        "appearances": len(appearances),
                    }
            else:
                unidentified[fid] = {
                    "identity_id": None,
                    "name": None,
                    "appearances": len(appearances),
                }

        contains_esther = any(face_to_identity.get(fid) == ESTHER_ID for fid in all_faces)
        contains_albert = any(face_to_identity.get(fid) == ALBERT_ID for fid in all_faces)

        results.append(
            {
                "photo_ids": photo_ids,
                "num_photos": len(photo_ids),
                "date_range": date_range,
                "contains_esther": contains_esther,
                "contains_albert": contains_albert,
                "total_faces": len(all_faces),
                "identified_count": len(identified),
                "unidentified_count": len(unidentified),
                "identified_faces": identified,
                "unidentified_faces": unidentified,
                "all_face_ids": list(all_faces.keys()),
            }
        )

    return results


def find_frequent_companions(
    event_results,
    face_to_identity,
    identity_lookup,
    date_labels,
    photos,
):
    """
    Find unidentified people appearing in 3+ event groups alongside Esther or Albert.
    Aggregates by identity_id (not face_id) since each face_id is unique per photo,
    but multiple face_ids may belong to the same unidentified identity cluster.
    Tracks age trajectory for each companion.
    """
    # Filter to events containing Esther or Albert
    target_events = [e for e in event_results if e["contains_esther"] or e["contains_albert"]]

    # Aggregate unidentified faces by identity_id (or face_id if no identity)
    # Count distinct event groups per identity
    identity_event_count = defaultdict(int)
    identity_event_details = defaultdict(list)
    identity_face_ids = defaultdict(set)  # identity_key -> set of face_ids

    for event in target_events:
        # Track which identities we've already counted for this event
        seen_identities = set()
        for fid, info in event["unidentified_faces"].items():
            iid = info.get("identity_id") or fid  # use face_id as key if no identity
            identity_face_ids[iid].add(fid)
            if iid not in seen_identities:
                seen_identities.add(iid)
                identity_event_count[iid] += 1
                identity_event_details[iid].append(
                    {
                        "date_range": event["date_range"],
                        "photo_ids": event["photo_ids"],
                        "with_esther": event["contains_esther"],
                        "with_albert": event["contains_albert"],
                    }
                )

    # Build age trajectory for frequent companions
    frequent = []
    for iid, count in sorted(identity_event_count.items(), key=lambda x: -x[1]):
        if count < FREQUENT_COMPANION_THRESHOLD:
            continue

        face_ids = identity_face_ids[iid]

        # Collect age estimates across all photos containing any of this identity's faces
        age_trajectory = []
        for photo_id, photo in photos.items():
            photo_face_ids = set(photo.get("face_ids") or [])
            matching = face_ids & photo_face_ids
            if not matching:
                continue
            label = date_labels.get(photo_id)
            if not label:
                continue
            year = label.get("best_year_estimate")
            face_analysis = label.get("face_analysis", [])
            for fid in matching:
                if fid in photo.get("face_ids", []):
                    face_idx = photo["face_ids"].index(fid)
                    if face_idx < len(face_analysis):
                        fa = face_analysis[face_idx]
                        age_trajectory.append(
                            {
                                "year": year,
                                "estimated_age": fa.get("estimated_age"),
                                "gender": fa.get("gender"),
                                "description": fa.get("description"),
                                "photo_id": photo_id,
                                "face_id": fid,
                            }
                        )

        age_trajectory.sort(key=lambda x: x.get("year") or 0)

        ident = identity_lookup.get(iid, {})
        ident_name = ident.get("name") if ident else None

        frequent.append(
            {
                "identity_id": iid if iid in identity_lookup else None,
                "identity_name": ident_name,
                "face_ids": sorted(face_ids),
                "num_faces": len(face_ids),
                "event_group_count": count,
                "event_details": identity_event_details[iid],
                "age_trajectory": age_trajectory,
            }
        )

    return frequent


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_summary(event_results, frequent_companions, identity_lookup):
    """Print human-readable summary to stdout."""
    target_events = [e for e in event_results if e["contains_esther"] or e["contains_albert"]]

    print("=" * 72)
    print("PRD-059 Phase 2: Event Grouping Report")
    print("=" * 72)
    print()
    print(f"Total event groups from dated photos: {len(event_results)}")
    print(f"Events containing Esther or Albert:   {len(target_events)}")
    print()

    # Sort by date
    target_events.sort(key=lambda e: (e["date_range"] or [9999])[0])

    for i, event in enumerate(target_events, 1):
        dr = event["date_range"]
        dr_str = f"{dr[0]}-{dr[1]}" if dr and dr[0] != dr[1] else str(dr[0]) if dr else "?"
        who = []
        if event["contains_esther"]:
            who.append("Esther")
        if event["contains_albert"]:
            who.append("Albert")

        print(
            f"  Event {i}: ~{dr_str} | {event['num_photos']} photo(s) | "
            f"{who} | {event['identified_count']} identified, "
            f"{event['unidentified_count']} unidentified faces"
        )

        # Show identified people (deduplicated by name)
        seen_names = set()
        for fid, info in event["identified_faces"].items():
            name = info["name"]
            if name not in seen_names:
                seen_names.add(name)
                print(f"    ✓ {name}")

    print()
    print("-" * 72)
    print(
        f"Frequent Companions (unidentified faces in {FREQUENT_COMPANION_THRESHOLD}+ event groups with Esther/Albert):"
    )
    print("-" * 72)

    if not frequent_companions:
        print("  None found.")
    else:
        for comp in frequent_companions:
            name = comp["identity_name"] or f"(unknown — {comp['num_faces']} face(s))"
            print(f"\n  {name}")
            print(f"    Appears in {comp['event_group_count']} event groups, {comp['num_faces']} face(s)")
            if comp["age_trajectory"]:
                print(f"    Age trajectory ({len(comp['age_trajectory'])} data points):")
                for at in comp["age_trajectory"]:
                    age = at.get("estimated_age", "?")
                    year = at.get("year", "?")
                    gender = at.get("gender", "?")
                    desc = (at.get("description") or "")[:80]
                    print(f"      ~{year}: age ~{age} ({gender}) — {desc}")

    print()
    print("=" * 72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("Loading date labels...")
    date_labels = load_date_labels()
    print(f"  {len(date_labels)} dated photos (gemini_batch_full)")

    print("Loading photo index...")
    pi = load_photo_index()
    photos = pi.get("photos", {})
    face_to_photo = pi.get("face_to_photo", {})
    print(f"  {len(photos)} photos, {len(face_to_photo)} face-to-photo mappings")

    print("Loading identities from Supabase...")
    identity_lookup, face_to_identity = load_identities_from_supabase()
    print(f"  {len(identity_lookup)} identities, {len(face_to_identity)} face mappings")

    # Find photos containing Esther or Albert that have date labels
    esther_photos = get_photos_for_person(ESTHER_ID, face_to_identity, face_to_photo)
    albert_photos = get_photos_for_person(ALBERT_ID, face_to_identity, face_to_photo)
    target_photos = esther_photos | albert_photos

    # Intersection with dated photos
    dated_target = {pid: date_labels[pid] for pid in target_photos if pid in date_labels}
    print(f"\nPhotos with Esther: {len(esther_photos)} total, {len(esther_photos & set(date_labels))} dated")
    print(f"Photos with Albert: {len(albert_photos)} total, {len(albert_photos & set(date_labels))} dated")
    print(f"Combined dated photos (union): {len(dated_target)}")

    if not dated_target:
        print("No dated photos found for Esther or Albert. Exiting.")
        return

    # Group into events
    print("\nGrouping into events...")
    raw_groups = group_into_events(dated_target, face_to_photo, photos, face_to_identity)
    print(f"  {len(raw_groups)} event groups formed")

    # Analyze events
    print("Analyzing events...")
    event_results = analyze_events(raw_groups, photos, face_to_identity, identity_lookup, date_labels)

    # Find frequent companions
    print("Finding frequent companions...")
    frequent_companions = find_frequent_companions(
        event_results, face_to_identity, identity_lookup, date_labels, photos
    )
    print(f"  {len(frequent_companions)} frequent companions found")

    # Build output
    output = {
        "metadata": {
            "esther_id": ESTHER_ID,
            "albert_id": ALBERT_ID,
            "year_tolerance": YEAR_TOLERANCE,
            "frequent_companion_threshold": FREQUENT_COMPANION_THRESHOLD,
            "total_dated_photos": len(date_labels),
            "esther_dated_photos": len(esther_photos & set(date_labels)),
            "albert_dated_photos": len(albert_photos & set(date_labels)),
            "combined_dated_photos": len(dated_target),
        },
        "event_groups": event_results,
        "frequent_companions": frequent_companions,
    }

    # Write output
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nOutput written to {OUTPUT_PATH}")

    # Print summary
    print()
    print_summary(event_results, frequent_companions, identity_lookup)


if __name__ == "__main__":
    main()
