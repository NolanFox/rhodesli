#!/usr/bin/env python3
"""Session 154 Track B Phase B2 — strengthen or falsify Bessie = 3009.

READ-ONLY. Computes:
  - Multi-frame triangulation: distance from target face (3009 in 02068) to
    each face in 01659 (second Belle Isle frame).
  - Kinship proximity: distance from 3009 to anchor centroids of Bessie-adjacent
    identities (children, grandchildren, sibling Albert) and to a non-Fox
    baseline cohort.

No mutations. Reuses single-linkage min-distance metric to match core.neighbors.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from scipy.spatial.distance import cdist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.embeddings_io import load_face_data

# .env may live in the main repo (when running from a worktree). Try both.
_env_local = PROJECT_ROOT / ".env"
_env_main = Path("/Users/nolanfox/rhodesli/.env")
if _env_local.exists():
    load_dotenv(_env_local)
elif _env_main.exists():
    load_dotenv(_env_main)
else:
    load_dotenv()

# --- Subjects ---
TARGET_FACE = "inbox_ed3f214545b9"  # Person 3009 back-right woman, 02068
PHOTO_01659_ID = "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045"
PHOTO_02068_ID = "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600"

# Identities of interest (from session 154 context.md key identity table + family knowledge)
BESSIE_IDENTITY = "b4a43575-9312-40ec-a574-85bf4294d0af"
ALBERT_IDENTITY = "85546ebf-75b9-4971-a9d4-b2ce2271bc19"  # Bessie's brother

# Bessie ancestors at her own anchors
BESSIE_ANCHORS = ["inbox_fad6b0654cc7", "inbox_0ae416754174"]

# Non-Fox baseline cohort: pick a known-CONFIRMED Rhodes/Capeluto identity
# Rachel Alhadeff Capeluto was the closest CONFIRMED in 153b (d=1.239), so
# we'll use her as one baseline. We'll also sample several CONFIRMED
# non-Fox identities for a fairer comparison.


def l2n(m):
    m = np.asarray(m, dtype=np.float32)
    if m.ndim == 1:
        m = m[None, :]
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n = np.where(n < 1e-12, 1.0, n)
    return m / n


def fetch_supabase_identities():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    sb = create_client(url, key)

    identities: list[dict] = []
    offset = 0
    page = 500
    while True:
        resp = (
            sb.table("identities")
            .select("identity_id,name,state,anchor_ids,merged_into")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        identities.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return identities, sb


def fetch_photo_faces(sb, photo_id: str) -> list[str]:
    r = sb.table("photo_faces").select("face_id").eq("photo_id", photo_id).execute()
    return [row["face_id"] for row in (r.data or []) if row.get("face_id")]


def main():
    print("=" * 72)
    print("SESSION 154 PHASE B2 — Bessie = 3009 strengthening / falsification")
    print("=" * 72)

    # 1. Load embeddings (fall back to main repo if worktree lacks them)
    main_repo = Path("/Users/nolanfox/rhodesli")
    main_path = PROJECT_ROOT / "data" / "embeddings.npy"
    if not main_path.exists():
        main_path = main_repo / "data" / "embeddings.npy"
    fader_path = PROJECT_ROOT / "data" / "fader_embeddings.npy"
    if not fader_path.exists():
        fader_path = main_repo / "data" / "fader_embeddings.npy"
    face_data = load_face_data(main_path)
    print(f"\nLoaded {len(face_data)} faces from main")
    if fader_path.exists():
        fader = load_face_data(fader_path)
        added = 0
        for fid, rec in fader.items():
            if fid not in face_data:
                face_data[fid] = rec
                added += 1
        print(f"Loaded {len(fader)} from fader ({added} new)")

    for fid, rec in face_data.items():
        mu = rec.get("mu")
        if mu is not None:
            rec["mu_norm"] = l2n(np.asarray(mu, dtype=np.float32))[0]

    if TARGET_FACE not in face_data:
        print(f"FATAL: target {TARGET_FACE} not in embeddings")
        sys.exit(1)

    target_mu = face_data[TARGET_FACE]["mu_norm"]

    # 2. Multi-frame triangulation
    print("\n" + "=" * 72)
    print("TEST 1 — Multi-frame triangulation (3009 vs faces in 01659)")
    print("=" * 72)
    identities, sb = fetch_supabase_identities()
    print(f"  fetched {len(identities)} identity rows")

    faces_01659 = fetch_photo_faces(sb, PHOTO_01659_ID)
    print(f"\n  photo 01659 has {len(faces_01659)} faces")

    test1_results = []
    for fid in faces_01659:
        if fid not in face_data:
            print(f"    {fid}: NOT in embeddings (skipping)")
            test1_results.append({"face_id": fid, "distance": None, "in_embeddings": False})
            continue
        mu = face_data[fid]["mu_norm"]
        d = float(np.linalg.norm(target_mu - mu))
        bbox = face_data[fid].get("bbox")
        # what identity claims this face?
        owner_id = None
        owner_name = None
        for row in identities:
            anc = row.get("anchor_ids") or []
            if isinstance(anc, str):
                try:
                    anc = json.loads(anc)
                except Exception:
                    anc = []
            if fid in anc:
                owner_id = row["identity_id"]
                owner_name = row["name"]
                break
        flag = ""
        if d < 0.85:
            flag = " ** SAME PERSON HIGH-CONFIDENCE"
        elif d < 1.10:
            flag = " * SAME PERSON LIKELY"
        print(f"    {fid}: d={d:.4f}  bbox={bbox}  owner={owner_name}{flag}")
        test1_results.append({
            "face_id": fid, "distance": d, "bbox": bbox,
            "in_embeddings": True, "owner_id": owner_id, "owner_name": owner_name,
        })

    # verdict
    same_person_hits = [r for r in test1_results if r.get("distance") is not None and r["distance"] < 1.10]
    high_conf_hits = [r for r in test1_results if r.get("distance") is not None and r["distance"] < 0.85]
    print(f"\n  TEST 1 verdict:")
    print(f"    same-person likely (d<1.10): {len(same_person_hits)}")
    print(f"    same-person high-conf (d<0.85): {len(high_conf_hits)}")

    # 3. Kinship proximity test
    print("\n" + "=" * 72)
    print("TEST 2 — Kinship proximity")
    print("=" * 72)

    # Build identity index
    by_id = {r["identity_id"]: r for r in identities}

    # Find Bessie-adjacent identities by name pattern
    bessie_kin_keywords = [
        "leona", "smilg",  # daughter Leona Fox Smilg
        "frances",  # daughter Frances (b. Jan 1918)
        "asnes",  # daughter Elizabeth Asnes (from first marriage ~1905)
        "elizabeth", "tischler",  # alternate naming for Elizabeth
        "isaackov",  # Bessie's husband family
    ]
    fox_sibling_ids = {
        ALBERT_IDENTITY: "Albert Fox (sibling)",
        BESSIE_IDENTITY: "Bessie Fox (subject — should rank ~46)",
    }
    # also add Charles, Roland, Esther Burd Fox (Albert's wife), Harshel
    # We'll find them by name pattern below.

    candidates_kin: dict[str, dict] = {}
    for row in identities:
        name = (row.get("name") or "").lower()
        iid = row["identity_id"]
        # explicit IDs
        if iid in fox_sibling_ids:
            candidates_kin[iid] = {**row, "category": fox_sibling_ids[iid]}
            continue
        # match keywords
        for kw in bessie_kin_keywords:
            if kw in name:
                candidates_kin[iid] = {**row, "category": f"name match: '{kw}'"}
                break
        # also Fox siblings by family name + state
        if (row.get("state") == "CONFIRMED"
            and ("fox" in name)
            and any(s in name for s in ["charles", "charlie", "roland", "harshel", "harry"])):
            candidates_kin[iid] = {**row, "category": "Fox sibling (name match)"}

    print(f"\n  Found {len(candidates_kin)} Bessie-adjacent identities to test")
    for iid, info in candidates_kin.items():
        print(f"    {iid[:8]}…  {info['name']}  state={info['state']}  reason={info['category']}")

    # Compute distance from target to each kin identity (single-linkage min over their anchors)
    print(f"\n  Distances from 3009 to each:")
    kin_distances = []
    for iid, info in candidates_kin.items():
        anc = info.get("anchor_ids") or []
        if isinstance(anc, str):
            try:
                anc = json.loads(anc)
            except Exception:
                anc = []
        avail = [a for a in anc if a in face_data]
        if not avail:
            print(f"    {info['name'][:40]:40s}  NO anchors in embeddings")
            kin_distances.append({"identity_id": iid, "name": info["name"], "category": info["category"], "distance": None, "n_anchors": 0})
            continue
        mus = np.vstack([face_data[a]["mu_norm"] for a in avail])
        d = cdist(target_mu[None, :], mus, metric="euclidean")[0]
        d_min = float(d.min())
        d_mean = float(d.mean())
        kin_distances.append({
            "identity_id": iid, "name": info["name"], "category": info["category"],
            "distance": d_min, "d_mean": d_mean, "n_anchors": len(avail),
        })
        print(f"    {info['name'][:40]:40s}  d_min={d_min:.4f}  d_mean={d_mean:.4f}  (n={len(avail)})")

    # Compute baseline: distance from target to a sample of CONFIRMED non-Fox identities
    print("\n  Baseline cohort (CONFIRMED non-Fox, non-Bessie-adjacent):")
    baseline_ids: list[dict] = []
    skip_ids = set(candidates_kin.keys()) | {BESSIE_IDENTITY, ALBERT_IDENTITY}
    for row in identities:
        if row["identity_id"] in skip_ids:
            continue
        if row.get("state") != "CONFIRMED":
            continue
        name = (row.get("name") or "").lower()
        if "fox" in name or "burd" in name or "isaackov" in name:
            continue
        baseline_ids.append(row)
    print(f"    {len(baseline_ids)} CONFIRMED non-Fox non-Bessie-kin identities")

    baseline_distances = []
    for row in baseline_ids:
        anc = row.get("anchor_ids") or []
        if isinstance(anc, str):
            try:
                anc = json.loads(anc)
            except Exception:
                anc = []
        avail = [a for a in anc if a in face_data]
        if not avail:
            continue
        mus = np.vstack([face_data[a]["mu_norm"] for a in avail])
        d = cdist(target_mu[None, :], mus, metric="euclidean")[0]
        baseline_distances.append(float(d.min()))

    if baseline_distances:
        b_arr = np.array(baseline_distances)
        print(f"    Baseline d_min stats: median={np.median(b_arr):.4f}, mean={b_arr.mean():.4f}, "
              f"min={b_arr.min():.4f}, p10={np.percentile(b_arr, 10):.4f}, p25={np.percentile(b_arr, 25):.4f}")

    # Compute full ranking to find rank of each kin identity
    print("\n  Full identity ranking (to compute kin ranks)…")
    all_distances = []
    for row in identities:
        iid = row["identity_id"]
        anc = row.get("anchor_ids") or []
        if isinstance(anc, str):
            try:
                anc = json.loads(anc)
            except Exception:
                anc = []
        avail = [a for a in anc if a in face_data]
        if not avail:
            continue
        mus = np.vstack([face_data[a]["mu_norm"] for a in avail])
        d_min = float(cdist(target_mu[None, :], mus, metric="euclidean")[0].min())
        all_distances.append({"identity_id": iid, "name": row["name"], "state": row["state"], "distance": d_min, "n_anchors": len(avail)})

    all_distances.sort(key=lambda x: x["distance"])
    rank_lookup = {r["identity_id"]: i + 1 for i, r in enumerate(all_distances)}
    total = len(all_distances)
    print(f"    {total} identities ranked in full")

    print(f"\n  Kin identity ranks vs full population of {total}:")
    print(f"    {'name':40s} {'distance':>9} {'rank':>6} {'pct':>7}")
    for k in kin_distances:
        if k.get("distance") is None:
            print(f"    {k['name'][:40]:40s} {'—':>9} {'—':>6} {'—':>7}")
            continue
        r = rank_lookup.get(k["identity_id"], -1)
        pct = 100.0 * r / total if r > 0 else -1
        flag = ""
        if r > 0 and r <= 50:
            flag = " ** TOP 50"
        elif r > 0 and r <= 100:
            flag = " * TOP 100"
        print(f"    {k['name'][:40]:40s} {k['distance']:>9.4f} {r:>6} {pct:>6.1f}%{flag}")

    # Verdict for test 2: count kin that landed in top-50 vs total ~2900 identities
    kin_in_top50 = sum(1 for k in kin_distances if k.get("distance") is not None
                      and rank_lookup.get(k["identity_id"], 9999) <= 50)
    kin_in_top100 = sum(1 for k in kin_distances if k.get("distance") is not None
                       and rank_lookup.get(k["identity_id"], 9999) <= 100)
    print(f"\n  TEST 2 verdict:")
    print(f"    kin identities in top-50: {kin_in_top50} / {len(kin_distances)} (need >= 2 for kinship signal)")
    print(f"    kin identities in top-100: {kin_in_top100} / {len(kin_distances)}")

    # 4. Write output payload
    out_path = PROJECT_ROOT / "docs" / "feedback" / "session-154-bessie-strengthening-data.json"
    payload = {
        "target_face": TARGET_FACE,
        "test_1_multiframe": {
            "photo_id": PHOTO_01659_ID,
            "results": test1_results,
            "same_person_likely_count": len(same_person_hits),
            "same_person_highconf_count": len(high_conf_hits),
        },
        "test_2_kinship": {
            "candidates_evaluated": len(kin_distances),
            "kin_distances": kin_distances,
            "rank_lookup": {k["identity_id"]: rank_lookup.get(k["identity_id"]) for k in kin_distances},
            "total_ranked_identities": total,
            "baseline_stats": {
                "n": len(baseline_distances),
                "median": float(np.median(baseline_distances)) if baseline_distances else None,
                "mean": float(np.mean(baseline_distances)) if baseline_distances else None,
                "min": float(np.min(baseline_distances)) if baseline_distances else None,
                "p10": float(np.percentile(baseline_distances, 10)) if baseline_distances else None,
                "p25": float(np.percentile(baseline_distances, 25)) if baseline_distances else None,
            },
            "kin_in_top50": kin_in_top50,
            "kin_in_top100": kin_in_top100,
        },
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {out_path}")
    print("\nDONE — see analysis in docs/feedback/session-154-bessie-strengthening.md")


if __name__ == "__main__":
    main()
