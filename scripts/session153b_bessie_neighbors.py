#!/usr/bin/env python3
"""Session 153b Phase 1A — targeted neighbors for 3009 (Bessie hypothesis).

Computes top-20 neighbors across ALL identities for face `inbox_ed3f214545b9`
(Person 3009, back-right woman in 02068 Detroit conservatory photo).

Also computes direct distance to Bessie's 2 anchors and Bessie's internal
self-consistency, per Session 153b prompt Phase 1A.

READ-ONLY against Supabase and local data.
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

TARGET_FACE = "inbox_ed3f214545b9"  # Person 3009 back-right woman, 02068
BESSIE_ANCHORS = [
    "inbox_fad6b0654cc7",  # FB photo age ~70s
    "inbox_0ae416754174",  # 02136 beach age ~60
]
BESSIE_IDENTITY = "b4a43575-9312-40ec-a574-85bf4294d0af"


def l2n(m):
    m = np.asarray(m, dtype=np.float32)
    if m.ndim == 1:
        m = m[None, :]
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n = np.where(n < 1e-12, 1.0, n)
    return m / n


def main():
    load_dotenv(PROJECT_ROOT / ".env")

    # Load face data (main + fader)
    main_path = PROJECT_ROOT / "data" / "embeddings.npy"
    fader_path = PROJECT_ROOT / "data" / "fader_embeddings.npy"

    face_data = load_face_data(main_path)
    print(f"Loaded {len(face_data)} faces from main")
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
        print(f"FATAL: {TARGET_FACE} not in embeddings")
        sys.exit(1)

    target_mu = face_data[TARGET_FACE]["mu_norm"]
    print(f"\nTarget face: {TARGET_FACE}")
    print(f"  embedding dim: {target_mu.shape}")

    # --- Direct comparison to Bessie anchors ---
    print("\n=== Direct distance to Bessie anchors ===")
    for anc in BESSIE_ANCHORS:
        if anc not in face_data:
            print(f"  {anc}: NOT in embeddings")
            continue
        mu = face_data[anc]["mu_norm"]
        d = float(np.linalg.norm(target_mu - mu))
        print(f"  3009 -> Bessie anchor {anc}: d = {d:.4f}")

    # Bessie internal consistency
    print("\n=== Bessie internal self-consistency ===")
    avail = [a for a in BESSIE_ANCHORS if a in face_data]
    if len(avail) >= 2:
        mus = np.vstack([face_data[a]["mu_norm"] for a in avail])
        dmat = cdist(mus, mus, metric="euclidean")
        for i, a in enumerate(avail):
            for j, b in enumerate(avail):
                if i < j:
                    print(f"  {a} <-> {b}: d = {dmat[i, j]:.4f}")

    # --- Load Supabase identities (paginated + small page size) ---
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        print("FATAL: no SUPABASE_URL / KEY")
        sys.exit(1)
    sb = create_client(url, key)

    print("\n=== Fetching identities (paginated, 500 per page) ===")
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
        print(f"  offset {offset}: +{len(batch)} (total {len(identities)})")
        if len(batch) < page:
            break
        offset += page

    # Resolve merges: follow merged_into to canonical
    by_id = {r["identity_id"]: r for r in identities}

    def canonical(iid, seen=None):
        seen = seen or set()
        if iid in seen:
            return iid
        seen.add(iid)
        row = by_id.get(iid)
        if not row:
            return iid
        tgt = row.get("merged_into")
        if not tgt or tgt == iid:
            return iid
        return canonical(tgt, seen)

    # Collect anchors per canonical identity
    anchors_by_id: dict[str, list[str]] = defaultdict(list)
    for row in identities:
        iid = row["identity_id"]
        anc = row.get("anchor_ids") or []
        if isinstance(anc, str):
            try:
                anc = json.loads(anc)
            except Exception:
                anc = []
        canon = canonical(iid)
        for fid in anc:
            if isinstance(fid, dict):
                fid = fid.get("face_id")
            if isinstance(fid, str) and fid in face_data:
                anchors_by_id[canon].append(fid)

    # Dedupe
    anchors_by_id = {k: list(dict.fromkeys(v)) for k, v in anchors_by_id.items()}

    print(f"\nCanonical identities with >=1 anchor: {sum(1 for v in anchors_by_id.values() if v)}")

    # Compute min-linkage distance from target to each identity
    print("\n=== Computing distances (single-linkage MIN, matches core.neighbors) ===")
    distances = []
    for iid, fids in anchors_by_id.items():
        if not fids:
            continue
        if iid == BESSIE_IDENTITY:
            # also include for reference
            pass
        try:
            mus = np.vstack([face_data[fid]["mu_norm"] for fid in fids])
        except Exception:
            continue
        d = cdist(target_mu[None, :], mus, metric="euclidean")[0]
        dmin = float(d.min())
        row = by_id.get(iid, {})
        distances.append({
            "identity_id": iid,
            "name": row.get("name", "?"),
            "state": row.get("state", "?"),
            "n_anchors": len(fids),
            "d_min": dmin,
            "d_mean": float(d.mean()),
        })

    distances.sort(key=lambda x: x["d_min"])

    print(f"\n=== Top-25 nearest identities to 3009 ({TARGET_FACE}) ===")
    print(f"{'rank':>4} {'d_min':>7} {'d_mean':>7} {'state':>10} {'n':>3} name")
    for i, r in enumerate(distances[:25], 1):
        marker = " <-- BESSIE" if r["identity_id"] == BESSIE_IDENTITY else ""
        print(
            f"{i:>4} {r['d_min']:>7.4f} {r['d_mean']:>7.4f} "
            f"{r['state']:>10} {r['n_anchors']:>3} {r['name'][:50]}{marker}"
        )

    # Find Bessie's position in the full ranking
    bessie_rank = None
    for i, r in enumerate(distances, 1):
        if r["identity_id"] == BESSIE_IDENTITY:
            bessie_rank = i
            break
    print(f"\nBessie Fox rank in full similarity list: {bessie_rank}")

    # Write compact results
    out_path = PROJECT_ROOT / "docs" / "feedback" / "session-153b-bessie-ml-output.json"
    payload = {
        "target_face": TARGET_FACE,
        "bessie_anchors": BESSIE_ANCHORS,
        "direct_distances": {
            anc: float(np.linalg.norm(target_mu - face_data[anc]["mu_norm"]))
            for anc in BESSIE_ANCHORS if anc in face_data
        },
        "bessie_internal": float(cdist(
            np.vstack([face_data[a]["mu_norm"] for a in avail]),
            np.vstack([face_data[a]["mu_norm"] for a in avail]),
            metric="euclidean",
        )[0, 1]) if len(avail) >= 2 else None,
        "bessie_rank_in_full_list": bessie_rank,
        "top_25_neighbors": distances[:25],
        "canonical_identities_indexed": sum(1 for v in anchors_by_id.values() if v),
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
