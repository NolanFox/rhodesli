"""Session 154 Track B Phase B1 — resolve Harry Fox face-ID discrepancy.

READ-ONLY. No mutations. Compares:
- data/embeddings.npy (read-only, frozen)
- Supabase photo_faces (READ)
- Supabase identities (READ)
- data/identities.json (read-only, frozen for read)

Resolves whether `inbox_1fea75...` (Codex audit) or `inbox_2bc31a40c34a`
(Session 153 breakthrough doc) is the actual face F in the F+G cluster.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

PHOTO_ID_DETROIT = "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600"
HARRY_IDENTITY_ID = "d74cb556-6d44-4288-ade3-1cc8fa2b45a6"
CONTESTED_IDS = ["inbox_1fea75", "inbox_2bc31a40c34a"]
TARGET_3009_FACE = "inbox_ed3f214545b9"  # back-right standing woman


def main() -> None:
    print("=" * 70)
    print("SESSION 154 PHASE B1 — Harry Face-ID Resolution")
    print("=" * 70)

    # 1. embeddings.npy
    print("\n[1/5] Loading embeddings.npy (read-only)…")
    embs = np.load(ROOT / "data" / "embeddings.npy", allow_pickle=True)
    print(f"      Loaded {len(embs)} embedding entries")

    # collect all face IDs that exist
    all_face_ids: set[str] = set()
    npy_face_records = []
    for e in embs:
        # face_id may be explicit (inbox style) or generated from filename + idx
        fid = e.get("face_id") if hasattr(e, "get") else None
        if not fid:
            # legacy: filename:faceN
            fname = e.get("filename") if hasattr(e, "get") else None
            # we can't reconstruct without knowing the index ordering, so skip
            continue
        all_face_ids.add(fid)
        npy_face_records.append(e)
    print(f"      {len(all_face_ids)} distinct inbox-style face_ids in embeddings.npy")

    # search for contested IDs
    print("\n[2/5] Searching contested IDs in embeddings.npy…")
    matches = {}
    for prefix in CONTESTED_IDS:
        hits = [fid for fid in all_face_ids if fid.startswith(prefix)]
        matches[prefix] = hits
        print(f"      Prefix '{prefix}': {len(hits)} hit(s) → {hits[:3]}")

    # 3. supabase
    print("\n[3/5] Querying Supabase photo_faces for the Detroit photo…")
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    client = create_client(url, key)

    pf = (
        client.table("photo_faces")
        .select("face_id, photo_id, bbox, det_score, quality")
        .eq("photo_id", PHOTO_ID_DETROIT)
        .execute()
    )
    rows = pf.data or []
    print(f"      photo_faces rows for Detroit photo: {len(rows)}")
    detroit_face_ids: list[str] = []
    for r in rows:
        fid = r.get("face_id")
        bbox = r.get("bbox")
        detroit_face_ids.append(fid)
        print(f"        face_id={fid!r:50s}  bbox={bbox}  det={r.get('det_score')} q={r.get('quality')}")

    # cross-reference with embeddings.npy for bbox + filename info
    print("\n      Detroit faces enriched from embeddings.npy:")
    detroit_bboxes: dict[str, tuple] = {}
    for e in embs:
        if not hasattr(e, "get"):
            continue
        fid = e.get("face_id")
        if fid in detroit_face_ids:
            bbox = e.get("bbox")
            fname = e.get("filename")
            quality = e.get("quality")
            det = e.get("det_score")
            detroit_bboxes[fid] = bbox
            qstr = f"{quality:.2f}" if quality is not None else "None"
            print(f"        {fid}: bbox={bbox}, fname={fname}, q={qstr}, det={det}")

    print("\n[4/5] Cross-checking contested IDs against Detroit photo_faces…")
    for prefix in CONTESTED_IDS:
        present = [fid for fid in detroit_face_ids if fid and fid.startswith(prefix)]
        print(f"      Prefix '{prefix}' in Detroit photo: {present}")

    # 5. Harry identity anchors
    print("\n[5/5] Querying Harry Fox identity (anchor_ids)…")
    ident = (
        client.table("identities")
        .select("*")
        .eq("identity_id", HARRY_IDENTITY_ID)
        .execute()
    )
    irow = (ident.data or [None])[0]
    if not irow:
        print("      ERROR: Harry identity not found in Supabase!")
        return
    print(f"      Identity name: {irow.get('name')}")
    print(f"      State: {irow.get('state')}")

    # anchors may be JSONB or list-of-strings
    anchors_raw = irow.get("anchor_ids")
    if isinstance(anchors_raw, str):
        try:
            anchors = json.loads(anchors_raw)
        except Exception:
            anchors = list(anchors_raw)
    else:
        anchors = anchors_raw or []
    print(f"      anchor_ids count: {len(anchors)}")
    for a in anchors:
        print(f"        - {a}")

    # for each anchor, find which photo it belongs to
    print("\n      Per-anchor photo lookup:")
    anchor_photo_lookup: dict[str, dict] = {}
    if anchors:
        # batch query photo_faces
        batch = (
            client.table("photo_faces")
            .select("face_id, photo_id, bbox")
            .in_("face_id", anchors)
            .execute()
        )
        for r in batch.data or []:
            anchor_photo_lookup[r["face_id"]] = r

    # also cross-reference with embeddings.npy for bbox/filename
    npy_lookup = {}
    for e in embs:
        if hasattr(e, "get"):
            fid = e.get("face_id")
            if fid in anchors:
                npy_lookup[fid] = {"bbox": e.get("bbox"), "filename": e.get("filename")}

    for a in anchors:
        info = anchor_photo_lookup.get(a)
        npy_info = npy_lookup.get(a, {})
        if info:
            print(f"        {a} → photo {info['photo_id']}")
            print(f"           bbox(supabase)={info.get('bbox')} bbox(npy)={npy_info.get('bbox')} fname={npy_info.get('filename')}")
        else:
            print(f"        {a} → NO photo_faces row found (POTENTIAL DIVERGENCE) npy={npy_info}")

    # which anchors come from the Detroit photo?
    print("\n      Anchors sourced from Detroit photo 02068:")
    detroit_anchors = [
        a for a in anchors if anchor_photo_lookup.get(a, {}).get("photo_id") == PHOTO_ID_DETROIT
    ]
    for a in detroit_anchors:
        info = anchor_photo_lookup[a]
        npy_info = npy_lookup.get(a, {})
        print(f"        - {a}  bbox(npy)={npy_info.get('bbox')}")

    print("\n      Contested IDs cross-check vs anchor list:")
    for prefix in CONTESTED_IDS:
        in_anchors = [a for a in anchors if a and a.startswith(prefix)]
        print(f"        Prefix '{prefix}' in Harry anchor_ids: {in_anchors}")

    # also check the Bessie target face for sanity
    print(f"\n      Sanity: Bessie target {TARGET_3009_FACE} present in Detroit photo? "
          f"{TARGET_3009_FACE in detroit_face_ids}")

    # also fetch 01659's photo_faces for cross-check
    print("\n      Bonus: photo 01659 face IDs (for B2 multi-frame test)…")
    photo_01659_id = "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045"
    pf2 = (
        client.table("photo_faces")
        .select("face_id, photo_id, bbox")
        .eq("photo_id", photo_01659_id)
        .execute()
    )
    rows_01659 = pf2.data or []
    print(f"      photo_faces rows for 01659: {len(rows_01659)}")
    face_01659_ids: list[str] = []
    for r in rows_01659:
        fid = r.get("face_id")
        face_01659_ids.append(fid)
        npy_info = next((e for e in embs if hasattr(e, "get") and e.get("face_id") == fid), None)
        bbox_npy = npy_info.get("bbox") if npy_info else None
        print(f"        face_id={fid!r}  bbox(npy)={bbox_npy}")
    print(f"      Is 1fea75ce2caf in 01659? {('inbox_1fea75ce2caf' in face_01659_ids)}")

    print("\n" + "=" * 70)
    print("DONE — see analysis in docs/feedback/session-154-harry-face-id-resolution.md")
    print("=" * 70)


if __name__ == "__main__":
    main()
