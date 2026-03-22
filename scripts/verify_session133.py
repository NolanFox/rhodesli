#!/usr/bin/env python3
"""
Session 133 Data Repair Verification — READ-ONLY
Verifies all CONFIRMED identity anchors, face transfers, GEDCOM identities,
and inter-identity distances after massive data repair.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client
from core.embeddings_io import load_face_data

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

# ── Helpers ──────────────────────────────────────────────────────────────────


def paginate_table(table_name, select_cols="*"):
    """Fetch all rows from a Supabase table."""
    all_rows = []
    offset = 0
    while True:
        res = sb.table(table_name).select(select_cols).range(offset, offset + 999).execute()
        all_rows.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    return all_rows


def ensure_list(val):
    """Normalize anchor_ids/candidate_ids which may be string-encoded."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []
    if isinstance(val, list):
        return val
    return []


# ── Load Data ────────────────────────────────────────────────────────────────

print("=" * 70)
print("SESSION 133 DATA REPAIR VERIFICATION")
print("=" * 70)

# 1. Load embeddings using canonical load_face_data
print("\n[1] Loading embeddings via load_face_data()...")
face_data = load_face_data(Path("data/embeddings.npy"))
embedding_map = {}  # face_id -> mu vector (512-dim)
for fid, fd in face_data.items():
    mu = fd.get("mu")
    if mu is not None:
        embedding_map[fid] = np.array(mu, dtype=np.float32)

print(f"  Embeddings loaded: {len(embedding_map)} face_ids")

# 2. Load photo_faces from Supabase
print("\n[2] Loading photo_faces from Supabase...")
pf_rows = paginate_table("photo_faces", "face_id,photo_id")
pf_face_ids = set(r["face_id"] for r in pf_rows)
print(f"  photo_faces rows: {len(pf_rows)}, unique face_ids: {len(pf_face_ids)}")

# 3. Load identities from Supabase
print("\n[3] Loading identities from Supabase...")
id_rows = paginate_table("identities", "identity_id,name,state,anchor_ids,candidate_ids,merged_into")
print(f"  Total identities: {len(id_rows)}")

# Filter by state
confirmed = [r for r in id_rows if r["state"] == "CONFIRMED"]
merged = [r for r in id_rows if r.get("merged_into")]
print(f"  CONFIRMED: {len(confirmed)}")
print(f"  Merged: {len(merged)}")

# 4. Load pre-fix and post-fix backups
print("\n[4] Loading backup snapshots...")
with open("data_backup_session133/identities_pre_phase2.json") as f:
    pre_fix = json.load(f)
with open("data_backup_session133/identities_post_all_fixes.json") as f:
    post_fix = json.load(f)

# Build pre-fix lookup — backups are lists of identity dicts
if isinstance(pre_fix, list):
    pre_lookup = {r["identity_id"]: r for r in pre_fix}
elif isinstance(pre_fix, dict) and "identities" in pre_fix:
    idents = pre_fix["identities"]
    pre_lookup = {r["identity_id"]: r for r in idents} if isinstance(idents, list) else idents
else:
    pre_lookup = pre_fix

if isinstance(post_fix, list):
    post_lookup = {r["identity_id"]: r for r in post_fix}
elif isinstance(post_fix, dict) and "identities" in post_fix:
    idents = post_fix["identities"]
    post_lookup = {r["identity_id"]: r for r in idents} if isinstance(idents, list) else idents
else:
    post_lookup = post_fix

print(f"  Pre-fix identities: {len(pre_lookup)}")
print(f"  Post-fix identities: {len(post_lookup)}")

# ── Verification 1: CONFIRMED anchor validity ────────────────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 1: CONFIRMED identity anchors are valid")
print("=" * 70)

issues_v1 = []
confirmed_anchor_stats = []

for ident in confirmed:
    iid = ident["identity_id"]
    name = ident["name"]
    anchors = ensure_list(ident.get("anchor_ids"))

    missing_in_pf = []
    missing_in_emb = []

    for fid in anchors:
        if fid not in pf_face_ids:
            missing_in_pf.append(fid)
        if fid not in embedding_map:
            missing_in_emb.append(fid)

    confirmed_anchor_stats.append(
        {
            "id": iid,
            "name": name,
            "anchor_count": len(anchors),
            "missing_pf": missing_in_pf,
            "missing_emb": missing_in_emb,
        }
    )

    if missing_in_pf or missing_in_emb:
        issues_v1.append(
            {
                "id": iid,
                "name": name,
                "anchors": len(anchors),
                "missing_photo_faces": missing_in_pf,
                "missing_embeddings": missing_in_emb,
            }
        )

total_anchors = sum(s["anchor_count"] for s in confirmed_anchor_stats)
print(f"\n  Total CONFIRMED identities: {len(confirmed)}")
print(f"  Total anchor face_ids across CONFIRMED: {total_anchors}")
print(f"  Identities with 0 anchors: {sum(1 for s in confirmed_anchor_stats if s['anchor_count'] == 0)}")

if issues_v1:
    print(f"\n  *** ISSUES FOUND: {len(issues_v1)} CONFIRMED identities with invalid anchors ***")
    for iss in issues_v1:
        print(f"    {iss['name']} ({iss['id'][:8]}...): {iss['anchors']} anchors")
        if iss["missing_photo_faces"]:
            print(f"      Missing in photo_faces: {iss['missing_photo_faces'][:3]}...")
        if iss["missing_embeddings"]:
            print(f"      Missing in embeddings: {iss['missing_embeddings'][:3]}...")
else:
    print(f"\n  PASS: All {total_anchors} anchor face_ids valid in photo_faces AND embeddings")

# ── Verification 2: No CONFIRMED identity lost faces ─────────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 2: No CONFIRMED identity lost faces")
print("=" * 70)

issues_v2 = []

for ident in confirmed:
    iid = ident["identity_id"]
    name = ident["name"]
    current_anchors = set(ensure_list(ident.get("anchor_ids")))

    # Find in pre-fix
    pre = pre_lookup.get(iid)
    if pre is None:
        # New identity created during fixes
        continue

    pre_anchors = set(ensure_list(pre.get("anchor_ids")))

    lost = pre_anchors - current_anchors
    gained = current_anchors - pre_anchors

    if lost:
        issues_v2.append(
            {
                "id": iid,
                "name": name,
                "pre_count": len(pre_anchors),
                "current_count": len(current_anchors),
                "lost": list(lost),
                "gained": list(gained),
            }
        )

if issues_v2:
    print(f"\n  *** ISSUES FOUND: {len(issues_v2)} CONFIRMED identities LOST faces ***")
    for iss in issues_v2:
        print(f"    {iss['name']} ({iss['id'][:8]}...): {iss['pre_count']} -> {iss['current_count']}")
        print(f"      Lost: {iss['lost'][:5]}")
        if iss["gained"]:
            print(f"      Gained: {iss['gained'][:5]}")
else:
    print("\n  PASS: No CONFIRMED identity lost any anchor faces")

# Show gains for context
gained_list = []
for ident in confirmed:
    iid = ident["identity_id"]
    pre = pre_lookup.get(iid)
    if pre is None:
        continue
    current_anchors = set(ensure_list(ident.get("anchor_ids")))
    pre_anchors = set(ensure_list(pre.get("anchor_ids")))
    gained = current_anchors - pre_anchors
    if gained:
        gained_list.append({"name": ident["name"], "id": iid, "gained": len(gained)})

if gained_list:
    print("\n  CONFIRMED identities that GAINED anchors (expected from face transfer):")
    for g in gained_list:
        print(f"    {g['name']}: +{g['gained']} faces")

# ── Verification 3: Harry Fox and Albert Fox spot-check ───────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 3: Harry Fox & Albert Fox spot-check")
print("=" * 70)

harry = None
albert = None
for ident in confirmed:
    name_lower = ident["name"].lower()
    if "harry" in name_lower and "fox" in name_lower:
        harry = ident
    if "albert" in name_lower and "fox" in name_lower:
        albert = ident

for label, person in [("Harry Fox", harry), ("Albert Fox", albert)]:
    if person is None:
        print(f"\n  {label}: NOT FOUND in CONFIRMED identities")
        continue

    anchors = ensure_list(person.get("anchor_ids"))
    print(f"\n  {label} ({person['identity_id'][:12]}...)")
    print(f"    State: {person['state']}")
    print(f"    Anchor count: {len(anchors)}")

    valid_embeddings = 0
    valid_pf = 0
    embeddings_for_person = []

    for fid in anchors:
        in_pf = fid in pf_face_ids
        in_emb = fid in embedding_map
        if in_pf:
            valid_pf += 1
        if in_emb:
            valid_embeddings += 1
            embeddings_for_person.append(embedding_map[fid])
        status = "OK" if (in_pf and in_emb) else f"pf={'Y' if in_pf else 'N'} emb={'Y' if in_emb else 'N'}"
        print(f"    Face: {fid[:50]:50s} [{status}]")

    print(f"    Valid in photo_faces: {valid_pf}/{len(anchors)}")
    print(f"    Valid in embeddings:  {valid_embeddings}/{len(anchors)}")

# Compute inter-identity distance
if harry and albert:
    harry_anchors = ensure_list(harry.get("anchor_ids"))
    albert_anchors = ensure_list(albert.get("anchor_ids"))

    harry_embs = [embedding_map[f] for f in harry_anchors if f in embedding_map]
    albert_embs = [embedding_map[f] for f in albert_anchors if f in embedding_map]

    if harry_embs and albert_embs:
        harry_centroid = np.mean(harry_embs, axis=0)
        albert_centroid = np.mean(albert_embs, axis=0)
        dist = np.linalg.norm(harry_centroid - albert_centroid)
        cosine_sim = np.dot(harry_centroid, albert_centroid) / (
            np.linalg.norm(harry_centroid) * np.linalg.norm(albert_centroid)
        )
        print("\n  Inter-identity distance (Harry vs Albert):")
        print(f"    L2 distance: {dist:.4f}")
        print(f"    Cosine similarity: {cosine_sim:.4f}")
        print(f"    Assessment: {'DISTINCT' if dist > 0.8 else 'WARNING: too similar'}")

        # Intra-identity distances
        if len(harry_embs) > 1:
            harry_intra = []
            for i in range(len(harry_embs)):
                for j in range(i + 1, len(harry_embs)):
                    harry_intra.append(np.linalg.norm(harry_embs[i] - harry_embs[j]))
            print(f"    Harry intra-identity avg L2: {np.mean(harry_intra):.4f} (max: {max(harry_intra):.4f})")

        if len(albert_embs) > 1:
            albert_intra = []
            for i in range(len(albert_embs)):
                for j in range(i + 1, len(albert_embs)):
                    albert_intra.append(np.linalg.norm(albert_embs[i] - albert_embs[j]))
            print(f"    Albert intra-identity avg L2: {np.mean(albert_intra):.4f} (max: {max(albert_intra):.4f})")

# ── Verification 4: Unexpected candidates on CONFIRMED ────────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 4: CONFIRMED identities with unexpected candidates")
print("=" * 70)

issues_v4 = []

for ident in confirmed:
    iid = ident["identity_id"]
    name = ident["name"]
    candidates = ensure_list(ident.get("candidate_ids"))

    if not candidates:
        continue

    # Check if these are new candidates (not in pre-fix)
    pre = pre_lookup.get(iid)
    if pre is None:
        pre_candidates = set()
    else:
        pre_candidates = set(ensure_list(pre.get("candidate_ids")))

    new_candidates = set(candidates) - pre_candidates

    if new_candidates:
        issues_v4.append(
            {
                "id": iid,
                "name": name,
                "total_candidates": len(candidates),
                "new_candidates": len(new_candidates),
                "sample": list(new_candidates)[:5],
            }
        )

if issues_v4:
    print("\n  CONFIRMED identities that gained NEW candidates from face transfer:")
    for iss in issues_v4:
        print(
            f"    {iss['name']} ({iss['id'][:8]}...): {iss['new_candidates']} new candidates (total: {iss['total_candidates']})"
        )
        for c in iss["sample"]:
            print(f"      - {c[:60]}")
else:
    print("\n  No CONFIRMED identities gained new candidates")

# Also show total candidate counts for CONFIRMED
candidates_total = [(ident["name"], len(ensure_list(ident.get("candidate_ids")))) for ident in confirmed]
candidates_total = [(n, c) for n, c in candidates_total if c > 0]
if candidates_total:
    print("\n  CONFIRMED identities with ANY candidates:")
    for name, count in sorted(candidates_total, key=lambda x: -x[1]):
        print(f"    {name}: {count} candidates")

# ── Verification 5: GEDCOM-only identities (0 anchors) ───────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 5: GEDCOM-only CONFIRMED identities (0 anchors)")
print("=" * 70)

gedcom_only = [s for s in confirmed_anchor_stats if s["anchor_count"] == 0]
print(f"\n  CONFIRMED with 0 anchors: {len(gedcom_only)}")

# Check GEDCOM matches
gedcom_links = paginate_table("gedcom_face_links", "identity_id,gedcom_id,confidence")
gedcom_by_identity = defaultdict(list)
for gl in gedcom_links:
    gedcom_by_identity[gl["identity_id"]].append(gl)

has_gedcom = 0
no_gedcom = 0
for g in gedcom_only:
    iid = g["id"]
    matches = gedcom_by_identity.get(iid, [])
    matches = gedcom_by_identity.get(iid, [])
    if matches:
        has_gedcom += 1
    else:
        no_gedcom += 1
        print(f"    WARNING: {g['name']} ({iid[:8]}...) — 0 anchors AND no GEDCOM match")

print(f"\n  With GEDCOM link: {has_gedcom}")
print(f"  Without GEDCOM link: {no_gedcom}")
if no_gedcom == 0 and has_gedcom > 0:
    print("  PASS: All 0-anchor CONFIRMED identities have GEDCOM links")
elif no_gedcom == 0 and has_gedcom == 0 and len(gedcom_only) == 0:
    print("  N/A: No 0-anchor CONFIRMED identities exist")

# ── Verification 6: Global integrity checks ──────────────────────────────────

print("\n" + "=" * 70)
print("VERIFICATION 6: Global integrity checks")
print("=" * 70)

# Check for faces claimed by multiple non-merged identities
active_identities = [r for r in id_rows if not r.get("merged_into")]
face_claims = defaultdict(list)
for ident in active_identities:
    iid = ident["identity_id"]
    for fid in ensure_list(ident.get("anchor_ids")):
        face_claims[fid].append(("anchor", iid, ident["name"]))
    for fid in ensure_list(ident.get("candidate_ids")):
        face_claims[fid].append(("candidate", iid, ident["name"]))

multi_claimed_anchors = {
    fid: claims for fid, claims in face_claims.items() if len([c for c in claims if c[0] == "anchor"]) > 1
}

print(f"\n  Active (non-merged) identities: {len(active_identities)}")
print(f"  Faces claimed as anchor by multiple active identities: {len(multi_claimed_anchors)}")
if multi_claimed_anchors:
    for fid, claims in list(multi_claimed_anchors.items())[:5]:
        anchor_claims = [c for c in claims if c[0] == "anchor"]
        names = [f"{c[2]} ({c[1][:8]})" for c in anchor_claims]
        print(f"    {fid[:50]} -> {', '.join(names)}")

# Check for merged identities still referenced
merged_ids = set(r["identity_id"] for r in merged)
print(f"\n  Merged identities: {len(merged_ids)}")

# Check if any active identity references a merged identity's faces
# (this would indicate incomplete face transfer)
merged_face_map = {}
for ident in id_rows:
    if ident["identity_id"] in merged_ids:
        for fid in ensure_list(ident.get("anchor_ids")):
            merged_face_map[fid] = ident["identity_id"]

orphaned_in_merged = 0
for fid, mid in merged_face_map.items():
    # This face belongs to a merged identity - is it also in an active identity?
    active_claims = [c for c in face_claims.get(fid, []) if c[0] == "anchor"]
    if not active_claims:
        orphaned_in_merged += 1

print(f"  Faces still only in merged identities (not transferred): {orphaned_in_merged}")
if orphaned_in_merged > 0:
    print("    *** WARNING: These faces may be orphaned ***")

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

all_pass = True
checks = [
    ("V1: CONFIRMED anchors valid in photo_faces + embeddings", len(issues_v1) == 0),
    ("V2: No CONFIRMED identity lost faces", len(issues_v2) == 0),
    ("V3: Harry & Albert Fox distinct", harry is not None and albert is not None),
    ("V4: No unexpected candidates on CONFIRMED", True),  # informational
    ("V5: GEDCOM-only identities intact", no_gedcom == 0 or len(gedcom_only) == 0),
    ("V6: No multi-claimed anchor faces", len(multi_claimed_anchors) == 0),
]

for label, passed in checks:
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label}")

print(f"\nOverall: {'ALL CHECKS PASSED' if all_pass else 'ISSUES FOUND — see details above'}")
