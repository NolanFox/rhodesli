"""Session 154 Track C2 — Irving anchor verification.

Computes embedding distance from the seated-LEFT face in 02068 (Detroit Belle
Isle Conservatory group photo) to each of Irving Israel Fox's 8 confirmed
anchors. Cross-checks against Albert and Harshel/Harry Fox to establish a
sibling baseline.

Inputs (read-only):
- data/embeddings.npy      : (N,) ndarray of dicts with 'filename', 'face_id',
                              'embeddings', 'bbox'
- data/identities.json     : registry containing anchor_ids per identity_id

Outputs: prints a markdown-ready table to stdout.

Usage:
    /Users/nolanfox/rhodesli/venv/bin/python3 scripts/session154_irving_verification.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---- constants ----------------------------------------------------------

REPO = Path("/Users/nolanfox/rhodesli/.claude/worktrees/agent-acf583d52162223d0")
EMB_PATH = REPO / "data" / "embeddings.npy"
IDS_PATH = REPO / "data" / "identities.json"

# Photo: 02068_p_13akf5twbc3600.jpg -- Detroit Belle Isle Conservatory ~1917
SEATED_LEFT_FACE_ID = "inbox_c0710382a050"  # x1=475, leftmost seated (per bbox audit)
SEATED_CENTER_FACE_ID = "inbox_e507a54f204a"  # G — misassigned to Harry
SEATED_RIGHT_FACE_ID = "inbox_b87b53e1ee20"   # rightmost (Albert)

# Identity UUIDs from session-154-context.md
IRVING_ID = "7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41"
ALBERT_ID = "85546ebf-75b9-4971-a9d4-b2ce2271bc19"
HARSHEL_ID = "d74cb556-6d44-4288-ade3-1cc8fa2b45a6"  # registry "Harry Fox"
BESSIE_ID = "b4a43575-9312-40ec-a574-85bf4294d0af"

# ---- helpers ------------------------------------------------------------


def l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0 or not math.isfinite(n):
        return v
    return v / n


def emb_for(face_id: str, by_face_id: dict[str, np.ndarray]) -> np.ndarray | None:
    return by_face_id.get(face_id)


def pairwise_distances(target: np.ndarray, anchors: list[tuple[str, np.ndarray]]) -> list[tuple[str, float]]:
    out = []
    t = l2_normalize(target.astype(np.float64).flatten())
    for fid, anc in anchors:
        a = l2_normalize(anc.astype(np.float64).flatten())
        d = float(np.linalg.norm(t - a))
        out.append((fid, d))
    return out


# ---- main --------------------------------------------------------------


def main() -> int:
    if not EMB_PATH.exists():
        print(f"ERROR: missing {EMB_PATH}", file=sys.stderr)
        return 2
    if not IDS_PATH.exists():
        print(f"ERROR: missing {IDS_PATH}", file=sys.stderr)
        return 2

    emb = np.load(EMB_PATH, allow_pickle=True)
    print(f"# Loaded {len(emb)} embedding entries", file=sys.stderr)

    # Index by face_id (preferred) AND by (filename, bbox) fallback.
    # Embeddings file uses PFE: vector key is "mu" (not "embeddings"). Legacy
    # entries without face_id get synthetic IDs `<stem>:face<N>` matching
    # core/embeddings_io.py:generate_face_id().
    by_face_id: dict[str, np.ndarray] = {}
    by_filename: dict[str, list[dict[str, Any]]] = {}
    filename_face_counts: dict[str, int] = {}
    skipped = 0
    for entry in emb:
        try:
            fn = str(entry.get("filename", "")) if hasattr(entry, "get") else ""
            if not fn:
                skipped += 1
                continue
            face_index = filename_face_counts.get(fn, 0)
            filename_face_counts[fn] = face_index + 1
            fid = str(entry.get("face_id") or f"{Path(fn).stem}:face{face_index}")
            mu = entry.get("mu")
            if mu is None:
                # fallback to legacy "embedding"/"embeddings" keys
                mu = entry.get("embedding") or entry.get("embeddings")
            if mu is None:
                skipped += 1
                continue
            vec = np.asarray(mu).flatten()
            by_face_id[fid] = vec
            by_filename.setdefault(fn, []).append({"face_id": fid, "vec": vec, "bbox": entry.get("bbox")})
        except Exception as e:  # noqa: BLE001
            print(f"# WARN entry error: {e}", file=sys.stderr)
            skipped += 1
    print(f"# Indexed {len(by_face_id)} faces, skipped {skipped}", file=sys.stderr)

    # Load identity rosters from Supabase (single source of truth per AD-135 +
    # data-layer.md). Local `data/identities.json` is stale — Codex's 153 audit
    # noted Irving has no local anchors; Supabase has 8.
    from dotenv import load_dotenv  # noqa: PLC0415
    import os  # noqa: PLC0415

    load_dotenv("/Users/nolanfox/rhodesli/.env")
    from supabase import create_client  # noqa: PLC0415

    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"))

    def anchors_for(identity_id: str) -> list[str]:
        r = sb.table("identities").select("anchor_ids,name,state,merged_into").eq("identity_id", identity_id).execute()
        if not r.data:
            return []
        anc = r.data[0].get("anchor_ids", []) or []
        if isinstance(anc, str):
            try:
                anc = json.loads(anc)
            except Exception:  # noqa: BLE001
                anc = []
        return list(anc) if isinstance(anc, list) else []

    irving_anchors = anchors_for(IRVING_ID)
    albert_anchors = anchors_for(ALBERT_ID)
    harshel_anchors = anchors_for(HARSHEL_ID)
    bessie_anchors = anchors_for(BESSIE_ID)

    print("\n## Identity rosters\n")
    print(f"- Irving Fox ({IRVING_ID}): {len(irving_anchors)} anchors")
    print(f"- Albert Fox ({ALBERT_ID}): {len(albert_anchors)} anchors")
    print(f"- Harry Fox / Harshel ({HARSHEL_ID}): {len(harshel_anchors)} anchors")
    print(f"- Bessie Fox ({BESSIE_ID}): {len(bessie_anchors)} anchors")

    # Pull seated-left embedding
    target_vec = by_face_id.get(SEATED_LEFT_FACE_ID)
    if target_vec is None:
        print(f"ERROR: seated-left face {SEATED_LEFT_FACE_ID} not found in embeddings", file=sys.stderr)
        return 3

    # Helper: produce anchor embeddings + brief source description
    def anchor_pairs(anchor_ids: list[str]) -> list[tuple[str, np.ndarray, str]]:
        rows: list[tuple[str, np.ndarray, str]] = []
        for aid in anchor_ids:
            v = by_face_id.get(aid)
            src_filename = ""
            if v is None:
                # try fallback: scan all embeddings for face_id (already indexed). give up if missing.
                pass
            else:
                # find filename for description
                for fn, lst in by_filename.items():
                    for r in lst:
                        if r["face_id"] == aid:
                            src_filename = fn
                            break
                    if src_filename:
                        break
            if v is not None:
                rows.append((aid, v, src_filename))
            else:
                print(f"# WARN: anchor {aid} embedding missing", file=sys.stderr)
        return rows

    irving_pairs = anchor_pairs(irving_anchors)
    albert_pairs = anchor_pairs(albert_anchors)
    harshel_pairs = anchor_pairs(harshel_anchors)
    bessie_pairs = anchor_pairs(bessie_anchors)

    # ---- Main: distance from seated-LEFT to Irving anchors -----------------
    print("\n## Distance: seated-LEFT (`inbox_c0710382a050`, 02068) → Irving's anchors\n")
    print("| # | Face ID | Source photo | L2 distance |")
    print("|---:|---|---|---:|")
    irv_distances = []
    for i, (aid, vec, fn) in enumerate(irving_pairs, start=1):
        d = float(np.linalg.norm(l2_normalize(target_vec.astype(np.float64).flatten()) - l2_normalize(vec.astype(np.float64).flatten())))
        irv_distances.append(d)
        print(f"| {i} | `{aid}` | {fn or '?'} | {d:.4f} |")

    if irv_distances:
        d_min = min(irv_distances)
        d_mean = sum(irv_distances) / len(irv_distances)
        d_med = float(np.median(np.array(irv_distances)))
        print(f"\n**Summary (Irving):** min={d_min:.4f} mean={d_mean:.4f} median={d_med:.4f} (n={len(irv_distances)})")

    # ---- Cross-sibling baseline -----------------------------------------
    def best_to(target: np.ndarray, pairs: list[tuple[str, np.ndarray, str]]) -> tuple[float, float, float, int]:
        if not pairs:
            return float("nan"), float("nan"), float("nan"), 0
        ds = []
        for _aid, v, _fn in pairs:
            ds.append(float(np.linalg.norm(l2_normalize(target.astype(np.float64).flatten()) - l2_normalize(v.astype(np.float64).flatten()))))
        return min(ds), sum(ds) / len(ds), float(np.median(np.array(ds))), len(ds)

    print("\n## Cross-sibling baseline (seated-LEFT → siblings)\n")
    print("| Identity | Anchors | min | mean | median |")
    print("|---|---:|---:|---:|---:|")
    for label, pairs in [("Irving Fox", irving_pairs), ("Albert Fox", albert_pairs), ("Harry Fox / Harshel", harshel_pairs), ("Bessie Fox", bessie_pairs)]:
        mn, mu, md, n = best_to(target_vec, pairs)
        print(f"| {label} | {n} | {mn:.4f} | {mu:.4f} | {md:.4f} |")

    # ---- Verdict heuristics ---------------------------------------------
    # Reference: Albert↔Irving min = 1.095 from Codex baseline (per session-154 prompt).
    if irv_distances:
        d_min = min(irv_distances)
        d_mean = sum(irv_distances) / len(irv_distances)
        if d_min < 0.95 and d_mean < 1.10:
            verdict = "STRONG"
        elif d_min < 1.10:
            verdict = "GOOD"
        elif d_min < 1.20:
            verdict = "POSSIBLE"
        else:
            verdict = "WEAK"
        print(f"\n**Verdict (heuristic, scaled to Codex Albert↔Irving baseline=1.095):** {verdict}")

    # ---- Sanity: also report seated-CENTER and seated-RIGHT for context ----
    print("\n## Sanity check — same analysis for seated-CENTER and seated-RIGHT\n")
    for label, fid in [
        ("seated-CENTER (mystery man, was 'Harry Fox' anchor G)", SEATED_CENTER_FACE_ID),
        ("seated-RIGHT (expected Albert)", SEATED_RIGHT_FACE_ID),
    ]:
        t = by_face_id.get(fid)
        if t is None:
            print(f"- {label} `{fid}`: NOT FOUND in embeddings")
            continue
        print(f"\n### {label} `{fid}`\n")
        print("| Identity | Anchors | min | mean | median |")
        print("|---|---:|---:|---:|---:|")
        for label2, pairs in [("Irving Fox", irving_pairs), ("Albert Fox", albert_pairs), ("Harry Fox / Harshel", harshel_pairs), ("Bessie Fox", bessie_pairs)]:
            mn, mu, md, n = best_to(t, pairs)
            print(f"| {label2} | {n} | {mn:.4f} | {mu:.4f} | {md:.4f} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
