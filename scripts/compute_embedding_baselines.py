#!/usr/bin/env python3
"""
Compute stratified embedding-distance baselines for Rhodesli's face archive.

Addresses the Codex P1 finding against session-153-corrective-analysis.md
(docs/feedback/session-153-codex-audit.md): the prior analysis mixed
same-person, sibling, spouse, and cross-family baselines into a single
narrative, reported arithmetic that did not add up (3,285 + 328 = 3,319),
and quoted an Albert↔Esther spouse minimum of d=1.089 without noting that
it is almost certainly a co-photographed-contamination artifact rather
than a calibration signal.

This script is READ-ONLY against Supabase. It never modifies core/neighbors.py
and uses the same distance function (L2 over L2-normalized PFE μ vectors) that
``core.neighbors`` uses, computed locally.

Strata computed:
  - same_person          — two faces of one confirmed identity from DIFFERENT photos
  - sibling              — two confirmed identities that share a FAMC (same parents)
  - parent_child         — one parent + one child, per GEDCOM family structure
  - spouse               — two confirmed identities married per GEDCOM (shared FAMS)
  - stranger             — random cross-family pairs (no shared family at all)

For each stratum we report: N, min, p10, median, p90, max, plus a "clean"
version of spouse and sibling that removes co-photographed face pairs
(faces appearing in the same photo, OR whose identities co-appear in
any photo).

Usage:
    python scripts/compute_embedding_baselines.py \\
        --output docs/feedback/session-153-embedding-baselines.md

Optional flags:
    --max-pairs 500       cap per stratum (default 500)
    --seed 42             reproducibility (default 42)
    --json results.json   also dump raw percentiles as JSON
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from scipy.spatial.distance import cdist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.embeddings_io import load_face_data  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAIN_EMBEDDINGS = PROJECT_ROOT / "data" / "embeddings.npy"
EXTRA_EMBEDDINGS = [PROJECT_ROOT / "data" / "fader_embeddings.npy"]
SUPABASE_PAGE_SIZE = 1000

PERCENTILES = (0, 10, 50, 90, 100)  # min, p10, median, p90, max


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization (defensive copy)."""
    m = np.asarray(matrix, dtype=np.float32)
    if m.ndim == 1:
        m = m[None, :]
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    return m / norms


def pair_distance(a: np.ndarray, b: np.ndarray) -> float:
    """L2 Euclidean distance between two L2-normalized vectors."""
    return float(np.linalg.norm(a - b))


@dataclass
class PairSummary:
    name: str
    n: int = 0
    min: float = float("nan")
    p10: float = float("nan")
    median: float = float("nan")
    p90: float = float("nan")
    max: float = float("nan")
    distances: list[float] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_values(cls, name: str, values: list[float], notes: str = "") -> "PairSummary":
        if not values:
            return cls(name=name, notes=notes)
        arr = np.asarray(values, dtype=np.float64)
        quantiles = np.percentile(arr, PERCENTILES)
        return cls(
            name=name,
            n=len(values),
            min=float(quantiles[0]),
            p10=float(quantiles[1]),
            median=float(quantiles[2]),
            p90=float(quantiles[3]),
            max=float(quantiles[4]),
            distances=sorted(values),
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_all_face_data() -> dict[str, dict]:
    """Union of main + extra embedding files, keyed by face_id."""
    if not MAIN_EMBEDDINGS.exists():
        raise FileNotFoundError(MAIN_EMBEDDINGS)

    face_data = load_face_data(MAIN_EMBEDDINGS)
    logger.info("Loaded %d faces from %s", len(face_data), MAIN_EMBEDDINGS.name)

    for extra in EXTRA_EMBEDDINGS:
        if not extra.exists():
            continue
        extra_data = load_face_data(extra)
        new_faces = 0
        for fid, payload in extra_data.items():
            if fid not in face_data:
                face_data[fid] = payload
                new_faces += 1
        logger.info(
            "Loaded %d faces from %s (%d new)",
            len(extra_data),
            extra.name,
            new_faces,
        )

    # Pre-normalize mu vectors once; keep "mu_norm" alongside
    for fid, rec in face_data.items():
        mu = rec.get("mu")
        if mu is None:
            continue
        rec["mu_norm"] = l2_normalize(np.asarray(mu, dtype=np.float32))[0]
    return face_data


def get_supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY/ANON_KEY required")
    return create_client(url, key)


def fetch_all(sb, table: str, columns: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            sb.table(table).select(columns).range(offset, offset + SUPABASE_PAGE_SIZE - 1).execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE
    return rows


def load_identities(sb) -> list[dict]:
    rows = fetch_all(
        sb,
        "identities",
        "identity_id,name,state,anchor_ids,candidate_ids,merged_into,metadata",
    )
    logger.info("Loaded %d identity rows from Supabase", len(rows))
    return rows


def load_photo_faces(sb) -> list[dict]:
    rows = fetch_all(sb, "photo_faces", "face_id,photo_id")
    logger.info("Loaded %d photo_faces rows", len(rows))
    return rows


def load_gedcom_links(sb) -> dict[str, str]:
    resp = sb.table("gedcom_face_links").select("identity_id,gedcom_id").execute()
    return {r["identity_id"]: r["gedcom_id"] for r in (resp.data or []) if r.get("gedcom_id")}


def load_gedcom_individuals(sb) -> dict[str, dict]:
    rows = fetch_all(
        sb,
        "gedcom_individuals",
        "gedcom_id,name,family_as_child_json,family_as_spouse_json,is_current",
    )
    out: dict[str, dict] = {}
    for row in rows:
        if not row.get("is_current"):
            continue
        gid = row.get("gedcom_id")
        if not gid:
            continue
        out[gid] = row
    return out


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------


def resolve_identity_anchors(
    identities: list[dict], face_data: dict[str, dict]
) -> dict[str, list[str]]:
    """
    Return anchor face lists per canonical (non-merged) identity.

    Merges are resolved: anchors from identities that have merged_into=X are
    appended to X's anchor list. Only faces present in face_data survive.
    """
    by_id = {r["identity_id"]: r for r in identities}

    # Follow merged_into chains to a terminal canonical id
    def canonical(iid: str, _seen: set[str] | None = None) -> str:
        _seen = _seen or set()
        if iid in _seen:
            return iid  # cycle guard
        _seen.add(iid)
        row = by_id.get(iid)
        if not row:
            return iid
        target = row.get("merged_into")
        if not target or target == iid:
            return iid
        return canonical(target, _seen)

    anchors: dict[str, list[str]] = defaultdict(list)
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
                anchors[canon].append(fid)

    # Dedupe while preserving order
    return {iid: list(dict.fromkeys(fids)) for iid, fids in anchors.items()}


# ---------------------------------------------------------------------------
# GEDCOM family graph
# ---------------------------------------------------------------------------


def build_family_graph(
    gedcom_links: dict[str, str],
    gedcom_individuals: dict[str, dict],
) -> dict:
    """
    Produce:
      identity_to_gedcom: identity_id -> gedcom_id
      gedcom_to_identity: gedcom_id -> set(identity_id)  (usually 1-to-1)
      identity_families_as_child: identity_id -> set(FAMC xrefs)
      identity_families_as_spouse: identity_id -> set(FAMS xrefs)
      identity_shares_family: identity_id -> set(all family xrefs they touch)
    """
    identity_to_gedcom = dict(gedcom_links)
    gedcom_to_identity: dict[str, set[str]] = defaultdict(set)
    for iid, gid in identity_to_gedcom.items():
        gedcom_to_identity[gid].add(iid)

    fam_child: dict[str, set[str]] = {}
    fam_spouse: dict[str, set[str]] = {}
    fam_all: dict[str, set[str]] = {}
    for iid, gid in identity_to_gedcom.items():
        indi = gedcom_individuals.get(gid)
        if not indi:
            continue
        famc = set(indi.get("family_as_child_json") or [])
        fams = set(indi.get("family_as_spouse_json") or [])
        fam_child[iid] = famc
        fam_spouse[iid] = fams
        fam_all[iid] = famc | fams

    return {
        "identity_to_gedcom": identity_to_gedcom,
        "gedcom_to_identity": dict(gedcom_to_identity),
        "fam_child": fam_child,
        "fam_spouse": fam_spouse,
        "fam_all": fam_all,
    }


# ---------------------------------------------------------------------------
# Co-photograph adjacency
# ---------------------------------------------------------------------------


def build_co_photo_maps(
    photo_faces: list[dict],
    anchors: dict[str, list[str]],
) -> dict:
    """
    face_to_photo: face_id -> photo_id  (picks first; 1 row per face is expected)
    identity_photos: identity_id -> set(photo_id)
    identity_co_identities: identity_id -> set(identity_id) that share >=1 photo
    """
    face_to_photo: dict[str, str] = {}
    for row in photo_faces:
        fid = row.get("face_id")
        pid = row.get("photo_id")
        if fid and pid and fid not in face_to_photo:
            face_to_photo[fid] = pid

    identity_photos: dict[str, set[str]] = defaultdict(set)
    photo_to_identities: dict[str, set[str]] = defaultdict(set)
    for iid, fids in anchors.items():
        for fid in fids:
            pid = face_to_photo.get(fid)
            if pid:
                identity_photos[iid].add(pid)
                photo_to_identities[pid].add(iid)

    identity_co_identities: dict[str, set[str]] = defaultdict(set)
    for pid, ids in photo_to_identities.items():
        if len(ids) < 2:
            continue
        ids_list = list(ids)
        for a in ids_list:
            for b in ids_list:
                if a != b:
                    identity_co_identities[a].add(b)

    return {
        "face_to_photo": face_to_photo,
        "identity_photos": dict(identity_photos),
        "identity_co_identities": {k: set(v) for k, v in identity_co_identities.items()},
    }


# ---------------------------------------------------------------------------
# Stratum samplers
# ---------------------------------------------------------------------------


def sample_same_person_pairs(
    anchors: dict[str, list[str]],
    face_data: dict[str, dict],
    face_to_photo: dict[str, str],
    max_pairs: int,
    rng: random.Random,
) -> tuple[list[float], dict]:
    """
    Two faces of the SAME confirmed identity from DIFFERENT photos.
    Returns (distances, diagnostics).
    """
    distances: list[float] = []
    same_photo_skipped = 0
    identities_contributing = 0
    for iid, fids in anchors.items():
        if len(fids) < 2:
            continue
        pairs = []
        for i in range(len(fids)):
            for j in range(i + 1, len(fids)):
                fa, fb = fids[i], fids[j]
                pa = face_to_photo.get(fa)
                pb = face_to_photo.get(fb)
                if pa and pb and pa == pb:
                    same_photo_skipped += 1
                    continue
                pairs.append((fa, fb))
        if not pairs:
            continue
        identities_contributing += 1
        # Cap per-identity so we don't drown in one high-anchor identity
        rng.shuffle(pairs)
        per_id_cap = 20
        for fa, fb in pairs[:per_id_cap]:
            va = face_data[fa].get("mu_norm")
            vb = face_data[fb].get("mu_norm")
            if va is None or vb is None:
                continue
            distances.append(pair_distance(va, vb))

    rng.shuffle(distances)
    distances = distances[:max_pairs]
    return distances, {
        "same_photo_skipped": same_photo_skipped,
        "identities_contributing": identities_contributing,
    }


def _identity_pairs_for_relation(
    relation: str,
    fam_graph: dict,
) -> list[tuple[str, str]]:
    """Enumerate identity pairs for sibling / parent_child / spouse."""
    fam_child = fam_graph["fam_child"]
    fam_spouse = fam_graph["fam_spouse"]
    gedcom_to_identity = fam_graph["gedcom_to_identity"]

    pairs: set[tuple[str, str]] = set()
    # Build family -> members dicts
    family_children: dict[str, set[str]] = defaultdict(set)
    for iid, fams in fam_child.items():
        for fam in fams:
            family_children[fam].add(iid)
    family_spouses: dict[str, set[str]] = defaultdict(set)
    for iid, fams in fam_spouse.items():
        for fam in fams:
            family_spouses[fam].add(iid)

    if relation == "sibling":
        for _fam, members in family_children.items():
            members = [m for m in members if m]
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = sorted([members[i], members[j]])
                    pairs.add((a, b))
    elif relation == "spouse":
        for _fam, members in family_spouses.items():
            members = [m for m in members if m]
            if len(members) >= 2:
                for i in range(len(members)):
                    for j in range(i + 1, len(members)):
                        a, b = sorted([members[i], members[j]])
                        pairs.add((a, b))
    elif relation == "parent_child":
        for fam, children in family_children.items():
            parents = family_spouses.get(fam, set())
            for parent in parents:
                for child in children:
                    if parent == child:
                        continue
                    a, b = sorted([parent, child])
                    pairs.add((a, b))
    else:
        raise ValueError(f"unknown relation {relation}")

    _ = gedcom_to_identity  # not currently used but retained for future expansion
    return list(pairs)


def sample_relation_pairs(
    relation: str,
    anchors: dict[str, list[str]],
    face_data: dict[str, dict],
    fam_graph: dict,
    co_photo_maps: dict,
    max_pairs: int,
    rng: random.Random,
    include_cophoto: bool,
) -> tuple[list[float], dict]:
    """
    Pairs of DIFFERENT identities with the given relation.
    Per pair we use the MIN distance across all face-face pairs
    (matches core.neighbors single-linkage semantics).

    If include_cophoto=False, pairs whose identities co-appear in any
    photo (or whose sampled faces are in the same photo) are dropped.
    """
    face_to_photo = co_photo_maps["face_to_photo"]
    identity_co_identities = co_photo_maps["identity_co_identities"]

    id_pairs = _identity_pairs_for_relation(relation, fam_graph)
    rng.shuffle(id_pairs)

    distances: list[float] = []
    contaminated_pairs: list[tuple[str, str, float]] = []
    attempted = 0
    for a, b in id_pairs:
        fa_list = anchors.get(a) or []
        fb_list = anchors.get(b) or []
        if not fa_list or not fb_list:
            continue
        is_cophoto = b in identity_co_identities.get(a, set())
        if is_cophoto and not include_cophoto:
            # Compute anyway to quantify contamination, but don't count it
            pass
        attempted += 1
        mat_a = np.vstack(
            [face_data[fid]["mu_norm"] for fid in fa_list if face_data[fid].get("mu_norm") is not None]
        )
        mat_b = np.vstack(
            [face_data[fid]["mu_norm"] for fid in fb_list if face_data[fid].get("mu_norm") is not None]
        )
        if mat_a.size == 0 or mat_b.size == 0:
            continue
        dmat = cdist(mat_a, mat_b, metric="euclidean")
        # For the "clean" mode we also want to drop face-level same-photo pairs:
        if not include_cophoto:
            # Mask out entries whose two faces live in the same photo
            for i, fa in enumerate(fa_list):
                pa = face_to_photo.get(fa)
                if not pa:
                    continue
                for j, fb in enumerate(fb_list):
                    if face_to_photo.get(fb) == pa:
                        dmat[i, j] = np.inf
            if not np.isfinite(dmat).any():
                # entire pair was co-photo at face level
                contaminated_pairs.append((a, b, float("nan")))
                continue
        min_d = float(dmat.min())
        if is_cophoto and not include_cophoto:
            contaminated_pairs.append((a, b, min_d))
            continue
        distances.append(min_d)
        if len(distances) >= max_pairs:
            break

    return distances, {
        "relation": relation,
        "include_cophoto": include_cophoto,
        "identity_pairs_attempted": attempted,
        "identity_pairs_kept": len(distances),
        "contaminated_dropped": len(contaminated_pairs),
        "cophoto_sample": [
            {"a": a, "b": b, "dist": d}
            for a, b, d in contaminated_pairs[:20]
        ],
    }


def sample_stranger_pairs(
    anchors: dict[str, list[str]],
    face_data: dict[str, dict],
    fam_graph: dict,
    co_photo_maps: dict,
    max_pairs: int,
    rng: random.Random,
) -> tuple[list[float], dict]:
    """
    Random cross-family pairs. Both identities must have >=1 face.
    Excludes: same identity, any shared family, any co-photographed identity pair.
    """
    ids_with_faces = [iid for iid, fids in anchors.items() if fids]
    fam_all = fam_graph["fam_all"]
    identity_co_identities = co_photo_maps["identity_co_identities"]

    distances: list[float] = []
    tried = 0
    max_tries = max_pairs * 20
    while len(distances) < max_pairs and tried < max_tries:
        tried += 1
        a, b = rng.sample(ids_with_faces, 2)
        shared = fam_all.get(a, set()) & fam_all.get(b, set())
        if shared:
            continue
        if b in identity_co_identities.get(a, set()):
            continue
        fa_list = anchors[a]
        fb_list = anchors[b]
        fa = rng.choice(fa_list)
        fb = rng.choice(fb_list)
        va = face_data[fa].get("mu_norm")
        vb = face_data[fb].get("mu_norm")
        if va is None or vb is None:
            continue
        distances.append(pair_distance(va, vb))

    return distances, {"attempts": tried}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_summary(summary: PairSummary) -> str:
    if summary.n == 0:
        return f"| {summary.name} | 0 | — | — | — | — | — |"
    return (
        f"| {summary.name} | {summary.n} | "
        f"{summary.min:.3f} | {summary.p10:.3f} | {summary.median:.3f} | "
        f"{summary.p90:.3f} | {summary.max:.3f} |"
    )


def derive_thresholds(
    same_person: PairSummary,
    stranger: PairSummary,
    sibling_clean: PairSummary,
    spouse_clean: PairSummary,
) -> dict:
    """
    Derive tier thresholds from stratum percentiles.

    Intent (same-person-oriented):
      STRONG  <= same_person.p90      (90% of same-person pairs fall here)
      GOOD    <= same_person.max      (upper edge of observed same-person range)
      POSSIBLE <= min(sibling_clean.p10, stranger.p10)
      UNLIKELY > that
    """

    def _or_nan(value: float) -> float:
        return value if value == value else float("nan")

    strong = _or_nan(same_person.p90)
    good = _or_nan(same_person.max)
    sib_p10 = _or_nan(sibling_clean.p10)
    stranger_p10 = _or_nan(stranger.p10)
    possible = float(np.nanmin([sib_p10, stranger_p10])) if not np.isnan(sib_p10) or not np.isnan(stranger_p10) else float("nan")
    return {
        "strong_le": strong,
        "good_le": good,
        "possible_le": possible,
    }


def write_report(
    output_path: Path,
    summaries: dict[str, PairSummary],
    diagnostics: dict,
    thresholds: dict,
    inventory: dict,
    seed: int,
    max_pairs: int,
) -> None:
    lines: list[str] = []
    lines.append("# Session 153 — Embedding Distance Baselines (Recalibration)")
    lines.append("")
    lines.append(
        "Replaces the mixed-baseline numbers in "
        "[docs/feedback/session-153-corrective-analysis.md](session-153-corrective-analysis.md) § 9"
    )
    lines.append(
        f"per Codex P1 in [docs/feedback/session-153-codex-audit.md](session-153-codex-audit.md)."
    )
    lines.append("")
    lines.append(
        f"Reproduce: `python scripts/compute_embedding_baselines.py --output {output_path}`"
    )
    lines.append(f"Seed: `{seed}` · Max pairs per stratum: `{max_pairs}` · Supabase: READ-ONLY")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "- **Distance metric:** Euclidean distance (`scipy.spatial.distance.cdist`, "
        "`metric='euclidean'`) over **L2-normalized PFE μ vectors**. This matches "
        "`core.neighbors.find_nearest_neighbors` (FROZEN). On L2-unit vectors, "
        "`d = sqrt(2 · (1 - cos_sim))`, range `[0, 2]`."
    )
    lines.append(
        "- **Face inventory:** `data/embeddings.npy` (main) merged with "
        "`data/fader_embeddings.npy`. Inbox-style entries carry `face_id`; "
        "legacy entries get `{filename-stem}:face{idx}` via `core.embeddings_io`."
    )
    lines.append(
        "- **Identity inventory:** all rows from `identities` Supabase table, "
        "paginated. Merged identities are folded into their canonical target "
        "(following `merged_into` chains) so same-person pairs include anchors "
        "transferred by admin merges."
    )
    lines.append(
        "- **Family graph:** `gedcom_face_links` → `gedcom_individuals.family_as_child_json` "
        "(FAMC xrefs) and `family_as_spouse_json` (FAMS xrefs). Only "
        "`is_current = true` snapshots are used."
    )
    lines.append("- **Strata:**")
    lines.append(
        "  - `same_person` — two anchor faces of one CONFIRMED identity from "
        "**DIFFERENT photos** (same-photo pairs excluded; they are near-identical "
        "embeddings by construction and inflate the \"good\" tail)."
    )
    lines.append(
        "  - `sibling` — two CONFIRMED identities with an overlapping FAMC set "
        "(share at least one parental family). Distance = MIN over all face-face "
        "pairs between the two identities (single-linkage, matching `core.neighbors`)."
    )
    lines.append(
        "  - `parent_child` — one spouse in a family F paired with each child "
        "in F (same MIN semantics)."
    )
    lines.append(
        "  - `spouse` — two identities sharing a FAMS xref."
    )
    lines.append(
        "  - `stranger` — random identity pairs with **zero** shared family xrefs "
        "(FAMC or FAMS) AND no co-photograph relationship."
    )
    lines.append(
        "- **Co-photograph contamination filter:** two identities are "
        "\"co-photographed\" if any of their anchor faces share a `photo_id` in "
        "`photo_faces`. For `sibling` / `spouse` / `parent_child` we report BOTH:"
    )
    lines.append(
        "  - **raw** — no filter; face-level and identity-level co-photos allowed."
    )
    lines.append(
        "  - **clean** — identity-level co-photographed pairs dropped entirely, "
        "and any face-level same-photo cell in the distance matrix is set to ∞ "
        "before taking the MIN. This is the calibration number."
    )
    lines.append("")

    lines.append("## Inventory")
    lines.append("")
    lines.append(f"- Faces with embeddings (union of sources): **{inventory['faces_total']}**")
    lines.append(f"  - from `data/embeddings.npy`: {inventory['faces_main']}")
    lines.append(
        f"  - extra from `data/fader_embeddings.npy` "
        f"(new face_ids only): {inventory['faces_extra']}"
    )
    lines.append(f"- Identity rows (all states, all communities): **{inventory['identities_total']}**")
    lines.append(
        f"- Canonical identities with ≥1 anchor face in embeddings: "
        f"**{inventory['identities_with_anchors']}**"
    )
    lines.append(
        f"- GEDCOM face links: **{inventory['gedcom_links']}** · "
        f"GEDCOM individuals (current): **{inventory['gedcom_individuals']}**"
    )
    lines.append("")
    lines.append(
        "> The prior analysis wrote `3,285 + 328 = 3,319`. Actual: "
        f"`{inventory['faces_main']} + {inventory['faces_extra']} = "
        f"{inventory['faces_main'] + inventory['faces_extra']}`. Not all 328 Fader "
        "rows are new — any face_id already present in the main file is deduped."
    )
    lines.append("")

    lines.append("## Distance Percentiles by Stratum")
    lines.append("")
    lines.append("| Stratum | N | min | p10 | median | p90 | max |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    ordered = [
        "same_person",
        "sibling_raw",
        "sibling_clean",
        "parent_child_raw",
        "parent_child_clean",
        "spouse_raw",
        "spouse_clean",
        "stranger",
    ]
    for key in ordered:
        if key in summaries:
            lines.append(format_summary(summaries[key]))
    lines.append("")

    # Cophoto diagnostics
    lines.append("## Co-Photograph Contamination Diagnostic")
    lines.append("")
    for key in ("sibling", "spouse", "parent_child"):
        raw = summaries.get(f"{key}_raw")
        clean = summaries.get(f"{key}_clean")
        diag = diagnostics.get(f"{key}_clean", {})
        cophoto_count = diag.get("contaminated_dropped", 0)
        if not raw or not clean:
            continue
        if raw.n == 0 or clean.n == 0:
            lines.append(f"- **{key}**: insufficient data (raw N={raw.n}, clean N={clean.n}).")
            continue
        delta_min = clean.min - raw.min
        delta_p10 = clean.p10 - raw.p10
        lines.append(
            f"- **{key}**: {cophoto_count} identity pairs dropped as co-photographed. "
            f"min rises from {raw.min:.3f} → {clean.min:.3f} (Δ={delta_min:+.3f}); "
            f"p10 rises from {raw.p10:.3f} → {clean.p10:.3f} (Δ={delta_p10:+.3f})."
        )
    lines.append("")
    lines.append(
        "> Codex flagged the Albert↔Esther spouse min of `d=1.089` as a likely "
        "co-photo artifact. This holds up: the raw spouse stratum includes pairs "
        "whose anchor faces literally appear in the same photo, which drags the "
        "minimum toward the same-person tail. Only the **_clean_** spouse numbers "
        "should be cited for calibration; do NOT use them as a positive-class signal."
    )
    lines.append("")

    lines.append("## Tier Threshold Proposal")
    lines.append("")
    lines.append(
        "The prior session used `<0.85 STRONG | 0.85-1.0 GOOD | 1.0-1.1 POSSIBLE | "
        ">1.1 UNLIKELY`. Those numbers were eyeballed from a mixed baseline and "
        "should be replaced with percentile-grounded thresholds:"
    )
    lines.append("")
    lines.append(
        "| Tier | Rule | Value |"
    )
    lines.append("|---|---|---:|")
    lines.append(
        f"| **STRONG** | `d ≤ same_person.p90` | **≤ {thresholds['strong_le']:.3f}** |"
    )
    lines.append(
        f"| **GOOD** | `d ≤ same_person.max` | **≤ {thresholds['good_le']:.3f}** |"
    )
    lines.append(
        f"| **POSSIBLE** | `d ≤ min(sibling_clean.p10, stranger.p10)` "
        f"| **≤ {thresholds['possible_le']:.3f}** |"
    )
    lines.append("| **UNLIKELY** | otherwise | — |")
    lines.append("")
    lines.append(
        "Interpretation:"
    )
    lines.append(
        "- **STRONG** — a match at this distance is inside the top 90% of actually-"
        "same-person pairs observed in this archive."
    )
    lines.append(
        "- **GOOD** — still within the _observed_ same-person envelope, but near "
        "the tail (expect some cross-age / cross-pose mispredictions)."
    )
    lines.append(
        "- **POSSIBLE** — below the 10th-percentile of known non-same-person "
        "pairs (sibling or stranger, whichever is tighter). Worth manual review, "
        "but embedding evidence alone is _not_ confirmation."
    )
    lines.append(
        "- **UNLIKELY** — not calibration-supported as a same-person match. Use "
        "only with independent evidence (GEDCOM, event context, manual review)."
    )
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- **Cross-age pairs are underrepresented.** For example, Bessie Fox's "
        "anchors are all from age ~60+; same-person pairs spanning child-vs-adult "
        "of the SAME person are rare in our archive. The `same_person` percentiles "
        "above therefore understate the distance you should expect when comparing "
        "an identity's old anchors to a candidate face from decades earlier. "
        "Future work: a stratified `same_person_cross_decade` stratum once we "
        "have enough multi-decade anchor sets."
    )
    lines.append(
        "- **Sibling stratum is Fox-family-heavy.** Most CONFIRMED identities with "
        "GEDCOM FAMC overlap are in the Fox sibling cluster (one parental family). "
        "Sibling distance distribution may not generalize to sibling pairs in "
        "Sephardic Rhodes families with different phenotypes."
    )
    lines.append(
        "- **Single-linkage MIN over face-pairs** matches production matching "
        "semantics, which means an identity with many high-variance anchors gets "
        "a more favorable min — it's not an i.i.d. sample of \"one face per person.\""
    )
    lines.append(
        "- **Stranger stratum requires GEDCOM coverage** to reliably exclude relatives. "
        "Identities without a GEDCOM link are treated as having no family, so some "
        "\"strangers\" may actually be unknown relatives. This mildly deflates "
        "stranger distances."
    )
    lines.append(
        "- **Spouse stratum is small** by construction (each FAMS has ≤2 members) "
        "and, even cleaned of co-photo contamination, lives at cross-family-baseline "
        "territory. It is not useful as a matching signal in either direction."
    )
    lines.append("")

    lines.append("## Provenance")
    lines.append("")
    lines.append(
        f"- Script: `scripts/compute_embedding_baselines.py` · seed={seed} · "
        f"max_pairs={max_pairs}"
    )
    lines.append(
        "- Supabase tables read: `identities`, `photo_faces`, `gedcom_face_links`, "
        "`gedcom_individuals` (all `SELECT`-only)."
    )
    lines.append(
        "- Distance function mirrors `core.neighbors.find_nearest_neighbors` "
        "(FROZEN): `cdist(A, B, metric='euclidean')` over L2-normalized μ."
    )
    for key in ordered:
        diag = diagnostics.get(key)
        if diag:
            brief = {k: v for k, v in diag.items() if k != "cophoto_sample"}
            lines.append(f"- `{key}` diagnostics: `{brief}`")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s (%d lines)", output_path, len(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "feedback" / "session-153-embedding-baselines.md",
    )
    parser.add_argument("--max-pairs", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", type=Path, default=None, help="optional raw JSON dump")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    load_dotenv(PROJECT_ROOT / ".env")
    rng = random.Random(args.seed)

    # Load face data
    face_data = load_all_face_data()
    faces_main = len(load_face_data(MAIN_EMBEDDINGS))
    faces_extra = len(face_data) - faces_main

    # Supabase
    sb = get_supabase_client()
    identities = load_identities(sb)
    photo_faces = load_photo_faces(sb)
    gedcom_links = load_gedcom_links(sb)
    gedcom_individuals = load_gedcom_individuals(sb)

    anchors = resolve_identity_anchors(identities, face_data)
    logger.info(
        "Anchors resolved: %d canonical identities with >=1 face",
        len([iid for iid, fids in anchors.items() if fids]),
    )

    fam_graph = build_family_graph(gedcom_links, gedcom_individuals)
    co_photo_maps = build_co_photo_maps(photo_faces, anchors)

    # Strata
    summaries: dict[str, PairSummary] = {}
    diagnostics: dict[str, dict] = {}

    sp_dists, sp_diag = sample_same_person_pairs(
        anchors, face_data, co_photo_maps["face_to_photo"], args.max_pairs, rng
    )
    summaries["same_person"] = PairSummary.from_values("same_person", sp_dists)
    diagnostics["same_person"] = sp_diag

    for relation in ("sibling", "parent_child", "spouse"):
        for clean in (False, True):
            tag = f"{relation}_{'clean' if clean else 'raw'}"
            dists, diag = sample_relation_pairs(
                relation,
                anchors,
                face_data,
                fam_graph,
                co_photo_maps,
                args.max_pairs,
                random.Random(args.seed + hash(tag) % 10_000),
                include_cophoto=(not clean),
            )
            summaries[tag] = PairSummary.from_values(tag, dists)
            diagnostics[tag] = diag

    stranger_dists, stranger_diag = sample_stranger_pairs(
        anchors, face_data, fam_graph, co_photo_maps, args.max_pairs,
        random.Random(args.seed + 1),
    )
    summaries["stranger"] = PairSummary.from_values("stranger", stranger_dists)
    diagnostics["stranger"] = stranger_diag

    thresholds = derive_thresholds(
        summaries["same_person"],
        summaries["stranger"],
        summaries.get("sibling_clean", PairSummary(name="sibling_clean")),
        summaries.get("spouse_clean", PairSummary(name="spouse_clean")),
    )

    inventory = {
        "faces_main": faces_main,
        "faces_extra": faces_extra,
        "faces_total": len(face_data),
        "identities_total": len(identities),
        "identities_with_anchors": len([iid for iid, fids in anchors.items() if fids]),
        "gedcom_links": len(gedcom_links),
        "gedcom_individuals": len(gedcom_individuals),
    }

    write_report(
        args.output,
        summaries,
        diagnostics,
        thresholds,
        inventory,
        args.seed,
        args.max_pairs,
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "seed": args.seed,
            "max_pairs": args.max_pairs,
            "inventory": inventory,
            "thresholds": thresholds,
            "strata": {
                k: {
                    "n": v.n,
                    "min": v.min,
                    "p10": v.p10,
                    "median": v.median,
                    "p90": v.p90,
                    "max": v.max,
                    "distances": v.distances,
                }
                for k, v in summaries.items()
            },
            "diagnostics": diagnostics,
        }
        args.json.write_text(json.dumps(payload, indent=2, default=str))
        logger.info("Wrote raw JSON to %s", args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
