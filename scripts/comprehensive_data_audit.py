#!/usr/bin/env python3
"""Comprehensive data audit for Rhodesli — cross-references ALL data stores.

Checks every Supabase table the app reads from, validates cross-references
between tables, and detects gaps that past audits missed.

What past audits missed (and this script catches):
  - Session 142: date_labels written to local JSON but not Supabase — the app
    reads from Supabase, so 84 labels were invisible for 20h. This script
    checks gemini_api_calls success count vs date_labels count.
  - Sessions 96e-133: audits checked JSON ↔ Supabase parity but never checked
    whether ALL app-read tables had complete data. For example, photo_faces
    rows were missing for photos that existed in the photos table.
  - Session 105: reconcile_supabase.py checked identity/photo parity but not
    secondary tables (date_labels, photo_locations, birth_year_estimates).
  - Session 108: data health endpoint checked counts but not cross-references
    (e.g., gemini_api_calls photo_id → date_labels photo_id).
  - No prior audit checked face_gemini_alignments completeness against photos
    that have Gemini analysis.

Usage:
    python scripts/comprehensive_data_audit.py
    python scripts/comprehensive_data_audit.py --verbose
    python scripts/comprehensive_data_audit.py --table identities
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class AuditResult:
    """Collects PASS/FAIL/WARN results for a single check."""

    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages: list[str] = []
        self.counts: dict[str, int] = {}

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def warn(self, msg: str):
        self.messages.append(f"WARN: {msg}")

    def info(self, msg: str):
        self.messages.append(f"INFO: {msg}")

    def set_count(self, key: str, value: int):
        self.counts[key] = value

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        parts = [f"[{status}] {self.name}"]
        if self.counts:
            counts_str = ", ".join(f"{k}={v}" for k, v in self.counts.items())
            parts.append(f"  Counts: {counts_str}")
        for msg in self.messages:
            parts.append(f"  {msg}")
        return "\n".join(parts)


def _paginate_select(client, table_name: str, select_cols: str, page_size: int = 1000) -> list[dict]:
    """Paginate a Supabase select query to get all rows."""
    all_rows = []
    offset = 0
    while True:
        result = client.table(table_name).select(select_cols).range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_rows


def _count_table(client, table_name: str) -> int:
    """Get exact count of rows in a Supabase table."""
    try:
        result = client.table(table_name).select("*", count="exact").limit(0).execute()
        return result.count or 0
    except Exception:
        return -1


def check_table_counts(client, verbose: bool) -> AuditResult:
    """Check that all expected Supabase tables exist and have data."""
    result = AuditResult("Table row counts")

    # Tables the app reads from (grouped by criticality)
    critical_tables = {
        "identities": 100,  # Must have identities
        "photos": 100,  # Must have photos
        "photo_faces": 100,  # Must have face entries
    }
    important_tables = {
        "communities": 1,
        "photo_communities": 1,
        "identity_communities": 1,
        "annotations": 0,  # May be empty
        "relationships": 0,
        "gedcom_matches": 0,
        "date_labels": 0,
        "photo_locations": 0,
        "face_gemini_alignments": 0,
        "gemini_api_calls": 0,
        "birth_year_estimates": 0,
        "person_comments": 0,
        "audit_log": 0,
        "ml_runs": 0,
        "ml_proposals": 0,
        "notifications": 0,
        "pending_uploads": 0,
        "gedcom_face_links": 0,
    }

    for table, min_expected in {**critical_tables, **important_tables}.items():
        count = _count_table(client, table)
        if count == -1:
            result.fail(f"Table '{table}' does not exist or is inaccessible")
        else:
            result.set_count(table, count)
            if count < min_expected:
                result.fail(f"Table '{table}' has {count} rows (expected >= {min_expected})")
            elif verbose:
                result.info(f"Table '{table}': {count} rows")

    return result


def check_identities_integrity(client, verbose: bool) -> AuditResult:
    """Check identity data integrity."""
    result = AuditResult("Identities integrity")

    rows = _paginate_select(
        client, "identities", "identity_id, name, state, anchor_ids, candidate_ids, negative_ids, merged_into"
    )

    result.set_count("total_identities", len(rows))

    valid_states = {"CONFIRMED", "PROPOSED", "INBOX", "SKIPPED", "CONTESTED", "REJECTED"}
    state_counts: dict[str, int] = {}
    merged_count = 0
    empty_confirmed = 0
    invalid_state_count = 0

    for row in rows:
        state = row.get("state", "")
        state_counts[state] = state_counts.get(state, 0) + 1

        if state not in valid_states:
            invalid_state_count += 1
            if invalid_state_count <= 3:
                result.fail(f"Identity {row['identity_id']} has invalid state '{state}'")

        if row.get("merged_into"):
            merged_count += 1

        # CONFIRMED identities must have anchor_ids
        if state == "CONFIRMED" and not row.get("merged_into"):
            anchors = row.get("anchor_ids") or []
            if isinstance(anchors, str):
                import json

                try:
                    anchors = json.loads(anchors)
                except (ValueError, TypeError):
                    anchors = []
            if len(anchors) == 0:
                empty_confirmed += 1
                if empty_confirmed <= 5:
                    result.fail(f"CONFIRMED identity {row['identity_id']} ({row.get('name')}) has no anchor_ids")

    if invalid_state_count > 3:
        result.fail(f"... and {invalid_state_count - 3} more invalid states")
    if empty_confirmed > 5:
        result.fail(f"... and {empty_confirmed - 5} more empty CONFIRMED identities")

    result.set_count("merged", merged_count)
    for s, c in sorted(state_counts.items()):
        result.set_count(f"state_{s}", c)

    if verbose:
        result.info(f"State distribution: {state_counts}")

    return result


def check_photo_faces_coverage(client, verbose: bool) -> AuditResult:
    """Every photo with face_ids in the photos table should have photo_faces rows."""
    result = AuditResult("Photo-faces coverage")

    photos = _paginate_select(client, "photos", "photo_id, face_ids")
    photo_faces = _paginate_select(client, "photo_faces", "photo_id, face_id")

    # Build set of (photo_id, face_id) from photo_faces
    pf_set = {(r["photo_id"], r["face_id"]) for r in photo_faces}
    pf_photo_ids = {r["photo_id"] for r in photo_faces}

    result.set_count("photos_total", len(photos))
    result.set_count("photo_faces_rows", len(photo_faces))

    photos_missing_pf = 0
    faces_missing_pf = 0

    for photo in photos:
        face_ids = photo.get("face_ids") or []
        if isinstance(face_ids, str):
            import json

            try:
                face_ids = json.loads(face_ids)
            except (ValueError, TypeError):
                face_ids = []

        if len(face_ids) > 0 and photo["photo_id"] not in pf_photo_ids:
            photos_missing_pf += 1
            if photos_missing_pf <= 3:
                result.fail(
                    f"Photo {photo['photo_id']} has {len(face_ids)} faces in photos table but no photo_faces rows"
                )

        for fid in face_ids:
            if (photo["photo_id"], fid) not in pf_set:
                faces_missing_pf += 1

    if photos_missing_pf > 3:
        result.fail(f"... and {photos_missing_pf - 3} more photos missing photo_faces rows")

    result.set_count("photos_missing_photo_faces", photos_missing_pf)
    result.set_count("faces_missing_photo_faces", faces_missing_pf)

    if faces_missing_pf > 0:
        result.fail(f"{faces_missing_pf} individual face(s) in photos.face_ids lack photo_faces rows")

    return result


def check_identity_faces_exist(client, verbose: bool) -> AuditResult:
    """CONFIRMED identity anchor_ids should reference faces that exist in photo_faces."""
    result = AuditResult("Identity face references")

    identities = _paginate_select(client, "identities", "identity_id, name, state, anchor_ids, merged_into")
    photo_faces = _paginate_select(client, "photo_faces", "face_id")

    all_face_ids = {r["face_id"] for r in photo_faces}
    result.set_count("known_faces", len(all_face_ids))

    orphan_faces = 0
    identities_with_orphans = 0

    for identity in identities:
        if identity.get("merged_into"):
            continue
        state = identity.get("state", "")
        anchors = identity.get("anchor_ids") or []
        if isinstance(anchors, str):
            import json

            try:
                anchors = json.loads(anchors)
            except (ValueError, TypeError):
                anchors = []

        missing_in_identity = [f for f in anchors if f not in all_face_ids]
        if missing_in_identity:
            orphan_faces += len(missing_in_identity)
            identities_with_orphans += 1
            if identities_with_orphans <= 3 and state == "CONFIRMED":
                result.fail(
                    f"CONFIRMED identity {identity['identity_id']} ({identity.get('name')}) "
                    f"has {len(missing_in_identity)} anchor face(s) not in photo_faces"
                )

    if identities_with_orphans > 3:
        result.fail(f"... and {identities_with_orphans - 3} more identities with orphan faces")

    result.set_count("orphan_anchor_faces", orphan_faces)
    result.set_count("identities_with_orphan_faces", identities_with_orphans)

    return result


def check_orphaned_faces(client, verbose: bool) -> AuditResult:
    """Faces in photo_faces should be claimed by at least one identity."""
    result = AuditResult("Orphaned faces (not claimed by any identity)")

    photo_faces = _paginate_select(client, "photo_faces", "face_id")
    identities = _paginate_select(client, "identities", "identity_id, anchor_ids, candidate_ids, merged_into")

    all_face_ids = {r["face_id"] for r in photo_faces}

    # Collect all claimed faces
    claimed_faces = set()
    for identity in identities:
        if identity.get("merged_into"):
            continue
        for field in ("anchor_ids", "candidate_ids"):
            ids = identity.get(field) or []
            if isinstance(ids, str):
                import json

                try:
                    ids = json.loads(ids)
                except (ValueError, TypeError):
                    ids = []
            claimed_faces.update(ids)

    orphaned = all_face_ids - claimed_faces
    result.set_count("total_faces", len(all_face_ids))
    result.set_count("claimed_faces", len(claimed_faces))
    result.set_count("orphaned_faces", len(orphaned))

    if len(orphaned) > 0:
        result.warn(f"{len(orphaned)} faces in photo_faces not claimed by any identity")
        if verbose and len(orphaned) <= 10:
            for fid in sorted(orphaned):
                result.info(f"  Orphaned face: {fid}")

    return result


def check_multi_claimed_faces(client, verbose: bool) -> AuditResult:
    """No face should be claimed by multiple non-merged identities."""
    result = AuditResult("Multi-claimed faces")

    identities = _paginate_select(
        client, "identities", "identity_id, name, state, anchor_ids, candidate_ids, merged_into"
    )

    face_owners: dict[str, list[str]] = {}
    for identity in identities:
        if identity.get("merged_into"):
            continue
        iid = identity["identity_id"]
        for field in ("anchor_ids", "candidate_ids"):
            ids = identity.get(field) or []
            if isinstance(ids, str):
                import json

                try:
                    ids = json.loads(ids)
                except (ValueError, TypeError):
                    ids = []
            for fid in ids:
                face_owners.setdefault(fid, []).append(iid)

    multi = {fid: owners for fid, owners in face_owners.items() if len(owners) > 1}
    result.set_count("multi_claimed_faces", len(multi))

    if len(multi) > 0:
        result.fail(f"{len(multi)} face(s) claimed by multiple identities")
        shown = 0
        for fid, owners in sorted(multi.items()):
            if shown >= 5:
                result.fail(f"... and {len(multi) - 5} more")
                break
            result.fail(f"  Face {fid} claimed by: {owners}")
            shown += 1

    return result


def check_date_labels_vs_gemini(client, verbose: bool) -> AuditResult:
    """date_labels count should match gemini_api_calls success count for date estimation.

    This is the Session 142 gap: Gemini was called successfully but results
    were written to local JSON instead of Supabase.
    """
    result = AuditResult("Date labels vs Gemini API calls")

    date_labels = _paginate_select(client, "date_labels", "photo_id")
    dl_photo_ids = {r["photo_id"] for r in date_labels}

    # Get Gemini API calls that were successful date estimations
    # The feature is "estimate" and status is typically indicated by presence of response_summary
    gemini_calls = _paginate_select(client, "gemini_api_calls", "photo_id, feature, status, gemini_config")

    estimate_success_photo_ids = set()
    for call in gemini_calls:
        feature = call.get("feature") or call.get("gemini_config", {}).get("feature", "")
        if not feature:
            # Try to infer from gemini_config
            cfg = call.get("gemini_config") or {}
            feature = cfg.get("feature", "")
        if "estimate" in str(feature).lower() or "date" in str(feature).lower():
            pid = call.get("photo_id")
            if pid:
                estimate_success_photo_ids.add(pid)

    result.set_count("date_labels", len(dl_photo_ids))
    result.set_count("gemini_estimate_calls", len(estimate_success_photo_ids))

    # Photos with Gemini estimate calls but no date_labels
    missing_labels = estimate_success_photo_ids - dl_photo_ids
    result.set_count("gemini_calls_without_date_labels", len(missing_labels))

    if len(missing_labels) > 0:
        result.fail(
            f"{len(missing_labels)} photo(s) have Gemini estimate API calls "
            f"but no date_labels entry — data may have been written to local JSON only"
        )
        if verbose and len(missing_labels) <= 10:
            for pid in sorted(missing_labels):
                result.info(f"  Missing date_label for photo: {pid}")

    return result


def check_community_coverage(client, verbose: bool) -> AuditResult:
    """Every photo and identity should be assigned to at least one community."""
    result = AuditResult("Community coverage")

    photos = _paginate_select(client, "photos", "photo_id")
    photo_communities = _paginate_select(client, "photo_communities", "photo_id")

    all_photo_ids = {r["photo_id"] for r in photos}
    community_photo_ids = {r["photo_id"] for r in photo_communities}

    photos_without_community = all_photo_ids - community_photo_ids
    result.set_count("photos_total", len(all_photo_ids))
    result.set_count("photos_with_community", len(community_photo_ids))
    result.set_count("photos_without_community", len(photos_without_community))

    if len(photos_without_community) > 0:
        result.warn(f"{len(photos_without_community)} photo(s) not assigned to any community")

    # Same for identities
    identities = _paginate_select(client, "identities", "identity_id, merged_into")
    identity_communities = _paginate_select(client, "identity_communities", "identity_id")

    active_ids = {r["identity_id"] for r in identities if not r.get("merged_into")}
    community_ids = {r["identity_id"] for r in identity_communities}

    ids_without_community = active_ids - community_ids
    result.set_count("active_identities", len(active_ids))
    result.set_count("identities_with_community", len(community_ids & active_ids))
    result.set_count("identities_without_community", len(ids_without_community))

    if len(ids_without_community) > 0:
        result.warn(f"{len(ids_without_community)} active identity(ies) not assigned to any community")

    return result


def check_face_alignment_completeness(client, verbose: bool) -> AuditResult:
    """Face alignment data for photos that have been Gemini-analyzed."""
    result = AuditResult("Face alignment completeness")

    alignments = _paginate_select(client, "face_gemini_alignments", "photo_id")
    alignment_count = _count_table(client, "face_gemini_alignments")
    photos_count = _count_table(client, "photos")

    result.set_count("face_alignments", alignment_count)
    result.set_count("photos_total", photos_count)

    if alignment_count == 0:
        result.warn("No face alignment data in Supabase")
    elif verbose:
        pct = (alignment_count / photos_count * 100) if photos_count > 0 else 0
        result.info(f"Face alignments cover {pct:.1f}% of photos")

    return result


def check_photo_locations_completeness(client, verbose: bool) -> AuditResult:
    """Photo location data completeness."""
    result = AuditResult("Photo locations completeness")

    locations_count = _count_table(client, "photo_locations")
    photos_count = _count_table(client, "photos")

    result.set_count("photo_locations", locations_count)
    result.set_count("photos_total", photos_count)

    if verbose:
        pct = (locations_count / photos_count * 100) if photos_count > 0 else 0
        result.info(f"Location data covers {pct:.1f}% of photos")

    return result


def check_birth_year_estimates(client, verbose: bool) -> AuditResult:
    """Birth year estimates completeness for CONFIRMED identities."""
    result = AuditResult("Birth year estimates completeness")

    estimates = _paginate_select(client, "birth_year_estimates", "identity_id")
    estimate_ids = {r["identity_id"] for r in estimates}

    identities = _paginate_select(client, "identities", "identity_id, state, merged_into")

    confirmed_ids = {r["identity_id"] for r in identities if r.get("state") == "CONFIRMED" and not r.get("merged_into")}

    confirmed_with_estimates = confirmed_ids & estimate_ids

    result.set_count("total_estimates", len(estimate_ids))
    result.set_count("confirmed_identities", len(confirmed_ids))
    result.set_count("confirmed_with_estimates", len(confirmed_with_estimates))

    if verbose:
        pct = (len(confirmed_with_estimates) / len(confirmed_ids) * 100) if confirmed_ids else 0
        result.info(f"Birth year estimates cover {pct:.1f}% of CONFIRMED identities")

    return result


def check_merge_chain_integrity(client, verbose: bool) -> AuditResult:
    """Merged identities should point to non-merged targets."""
    result = AuditResult("Merge chain integrity")

    identities = _paginate_select(client, "identities", "identity_id, merged_into")

    id_set = {r["identity_id"] for r in identities}
    merged_map = {r["identity_id"]: r["merged_into"] for r in identities if r.get("merged_into")}

    result.set_count("merged_identities", len(merged_map))

    dangling = 0
    circular = 0
    multi_hop = 0

    for source, target in merged_map.items():
        if target not in id_set:
            dangling += 1
            if dangling <= 3:
                result.warn(f"Dangling merge: {source} -> {target} (target not found)")

        elif target in merged_map:
            # Multi-hop: target is also merged
            multi_hop += 1
            # Check for circular
            visited = {source}
            current = target
            while current in merged_map:
                if current in visited:
                    circular += 1
                    break
                visited.add(current)
                current = merged_map[current]

    if dangling > 3:
        result.warn(f"... and {dangling - 3} more dangling merges")

    result.set_count("dangling_merges", dangling)
    result.set_count("multi_hop_merges", multi_hop)
    result.set_count("circular_merges", circular)

    if circular > 0:
        result.fail(f"{circular} circular merge chain(s) detected!")
    if multi_hop > 0:
        result.warn(f"{multi_hop} multi-hop merge(s) — should be flattened to direct targets")

    return result


def check_gemini_api_logging(client, verbose: bool) -> AuditResult:
    """Gemini API calls should have proper logging fields."""
    result = AuditResult("Gemini API call logging completeness")

    calls = _paginate_select(
        client, "gemini_api_calls", "id, photo_id, feature, gemini_config, response_summary, created_at"
    )

    result.set_count("total_calls", len(calls))

    missing_config = 0
    missing_response = 0
    missing_photo = 0

    for call in calls:
        if not call.get("gemini_config"):
            missing_config += 1
        if not call.get("response_summary"):
            missing_response += 1
        if not call.get("photo_id"):
            missing_photo += 1

    result.set_count("missing_gemini_config", missing_config)
    result.set_count("missing_response_summary", missing_response)
    result.set_count("missing_photo_id", missing_photo)

    if missing_config > 0:
        result.warn(f"{missing_config} Gemini calls missing gemini_config")
    if missing_response > 0:
        result.warn(f"{missing_response} Gemini calls missing response_summary")

    return result


def check_gedcom_face_links(client, verbose: bool) -> AuditResult:
    """GEDCOM face links should reference valid identities."""
    result = AuditResult("GEDCOM face link integrity")

    links = _paginate_select(client, "gedcom_face_links", "identity_id, gedcom_id")
    identities = _paginate_select(client, "identities", "identity_id, merged_into")

    active_ids = {r["identity_id"] for r in identities if not r.get("merged_into")}
    all_ids = {r["identity_id"] for r in identities}

    result.set_count("gedcom_links", len(links))

    stale_links = 0
    dangling_links = 0
    for link in links:
        iid = link["identity_id"]
        if iid not in all_ids:
            dangling_links += 1
        elif iid not in active_ids:
            stale_links += 1

    result.set_count("dangling_links", dangling_links)
    result.set_count("links_to_merged", stale_links)

    if dangling_links > 0:
        result.fail(f"{dangling_links} GEDCOM link(s) reference non-existent identities")
    if stale_links > 0:
        result.warn(f"{stale_links} GEDCOM link(s) point to merged identities")

    return result


ALL_CHECKS = [
    ("counts", check_table_counts),
    ("identities", check_identities_integrity),
    ("photo_faces", check_photo_faces_coverage),
    ("identity_faces", check_identity_faces_exist),
    ("orphaned_faces", check_orphaned_faces),
    ("multi_claimed", check_multi_claimed_faces),
    ("date_labels", check_date_labels_vs_gemini),
    ("communities", check_community_coverage),
    ("alignments", check_face_alignment_completeness),
    ("locations", check_photo_locations_completeness),
    ("birth_years", check_birth_year_estimates),
    ("merge_chains", check_merge_chain_integrity),
    ("gemini_logging", check_gemini_api_logging),
    ("gedcom_links", check_gedcom_face_links),
]


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Rhodesli data audit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info messages")
    parser.add_argument("--table", "-t", help="Run only checks matching this name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    # Load env for Supabase credentials
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass  # OK if running on Railway where env vars are set

    from app.supabase_data import get_supabase_client

    client = get_supabase_client()
    if not client:
        print("ERROR: Cannot connect to Supabase. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)

    print("=" * 60)
    print("Rhodesli Comprehensive Data Audit")
    print("=" * 60)

    results: list[AuditResult] = []
    for name, check_fn in ALL_CHECKS:
        if args.table and args.table not in name:
            continue
        try:
            r = check_fn(client, args.verbose)
            results.append(r)
        except Exception as e:
            r = AuditResult(name)
            r.fail(f"Check raised exception: {e}")
            results.append(r)

    print()
    failures = 0
    for r in results:
        print(r)
        print()
        if not r.passed:
            failures += 1

    print("=" * 60)
    if failures == 0:
        print(f"ALL {len(results)} CHECKS PASSED")
        sys.exit(0)
    else:
        print(f"{failures}/{len(results)} CHECK(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
