"""
Page routes extracted from app/main.py.

Core page rendering routes: /, /about, /help, /health, /photos, /people,
/collections, /map, /timeline, /tree, /connect, /photo/* detail pages,
/identify/* identification flow, and associated helpers.
"""

import json
import logging
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from html import escape as _html_escape
from pathlib import Path as _Path
from urllib.parse import quote, urlencode

from fasthtml.common import *
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse

from core.ui_safety import ensure_utf8_display

from app.main import rt
from app.utils import photo_url, _section_for_state
from app.rate_limit import check_rate_limit

import app.main as _main_mod

logger = logging.getLogger(__name__)

# =============================================================================
# ROUTES - HEALTH CHECK
# =============================================================================


_supabase_last_ping: float = 0.0
_SUPABASE_PING_INTERVAL: int = 3600  # seconds
_SITEMAP_CACHE_TTL_SECONDS: int = 3600
_SITEMAP_URL_LIMIT: int = 5000
_sitemap_cache_ts: float = 0.0
_sitemap_cache_site_url: str = ""
_sitemap_cache_body: str = ""


def _ping_supabase() -> str:
    """Lightweight Supabase ping to prevent free-tier inactivity pause.

    Throttled to once per hour (_SUPABASE_PING_INTERVAL seconds).
    Returns status string: 'ok', 'skipped', 'not_configured', or 'error:...'
    """
    global _supabase_last_ping

    now = time.time()
    if now - _supabase_last_ping < _SUPABASE_PING_INTERVAL:
        return "skipped"

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return "not_configured"
    try:
        import httpx

        resp = httpx.get(
            f"{url}/auth/v1/health",
            headers={"apikey": key},
            timeout=5.0,
        )
        _supabase_last_ping = now
        return "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
    except Exception as e:
        return f"error:{e}"


def _timeline_eligible_photo_ids(
    search_docs: list[dict],
    photo_cache: dict,
    *,
    start: int | None = None,
    end: int | None = None,
    collection: str = "",
) -> set[str]:
    """Return photo IDs that can actually appear on the timeline for the current filters."""

    eligible_photo_ids = set()
    for doc in search_docs:
        photo_id = doc.get("cache_photo_id", doc.get("photo_id", ""))
        year = doc.get("best_year_estimate") or doc.get("estimated_decade")
        if not photo_id or not year:
            continue
        if start and year < start:
            continue
        if end and year > end:
            continue
        photo_collection = (photo_cache or {}).get(photo_id, {}).get("collection", "")
        if collection and photo_collection != collection:
            continue
        eligible_photo_ids.add(photo_id)
    return eligible_photo_ids


def _build_timeline_person_filter_items(
    confirmed_identities: list[dict],
    photo_reg,
    eligible_photo_ids: set[str],
    selected_person_ids: set[str],
) -> list[dict]:
    """Build timeline person filter options from people with at least one visible timeline photo."""

    items = []
    for ident in confirmed_identities:
        iid = ident["identity_id"]
        face_ids = [
            f if isinstance(f, str) else f.get("face_id", "")
            for f in ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        ]
        timeline_photo_ids = {pid for pid in photo_reg.get_photos_for_faces(face_ids) if pid in eligible_photo_ids}
        if not timeline_photo_ids:
            continue
        items.append(
            {
                "id": iid,
                "name": ensure_utf8_display(ident.get("name", "")),
                "count": len(timeline_photo_ids),
                "selected": iid in selected_person_ids,
            }
        )
    return items


def _check_data_parity(json_photo_count: int, json_identity_count: int) -> dict:
    """Compare JSON and Supabase data counts. Session 105.

    Returns a dict with counts and sync status for the health endpoint.
    """
    result = {
        "photos_json": json_photo_count,
        "identities_json": json_identity_count,
        "photos_pg": None,
        "identities_pg": None,
        "synced": None,
    }
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            result["error"] = "supabase_not_configured"
            return result

        # Count photos in Supabase
        pg_photos = sb.table("photos").select("photo_id", count="exact").execute()
        result["photos_pg"] = pg_photos.count if pg_photos.count is not None else len(pg_photos.data or [])

        # Count identities in Supabase
        pg_ids = sb.table("identities").select("identity_id", count="exact").execute()
        result["identities_pg"] = pg_ids.count if pg_ids.count is not None else len(pg_ids.data or [])

        # Check sync status
        photo_diff = abs(result["photos_json"] - (result["photos_pg"] or 0))
        id_diff = abs(result["identities_json"] - (result["identities_pg"] or 0))

        if photo_diff == 0 and id_diff == 0:
            result["synced"] = True
        else:
            result["synced"] = False
            result["photo_diff"] = photo_diff
            result["identity_diff"] = id_diff
            # Log warnings/errors based on severity
            total = max(json_photo_count + json_identity_count, 1)
            pct = (photo_diff + id_diff) / total * 100
            if pct > 5:
                logging.error(
                    f"DATA PARITY ERROR: photos JSON={json_photo_count} PG={result['photos_pg']}, "
                    f"identities JSON={json_identity_count} PG={result['identities_pg']} ({pct:.1f}% mismatch)"
                )
            elif photo_diff + id_diff > 0:
                logging.warning(
                    f"Data parity warning: photos JSON={json_photo_count} PG={result['photos_pg']}, "
                    f"identities JSON={json_identity_count} PG={result['identities_pg']}"
                )
    except Exception as e:
        result["error"] = str(e)

    return result


def _sitemap_xml(site_url: str, paths: list[str]) -> str:
    """Render a minimal XML sitemap from already-normalized paths."""
    locs = []
    for path in paths:
        loc = f"{site_url}{path}"
        locs.append(f"  <url><loc>{_html_escape(loc, quote=True)}</loc></url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(locs)
        + "\n</urlset>\n"
    )


def _build_sitemap_xml(site_url: str) -> str:
    """Build the cached public sitemap, falling back to homepage-only on data errors."""
    paths = ["/"]
    seen = set(paths)
    truncated = False

    def add_path(path: str) -> bool:
        if path in seen:
            return True
        if len(paths) >= _SITEMAP_URL_LIMIT:
            return False
        seen.add(path)
        paths.append(path)
        return True

    try:
        for path in ("/tools/estimate", "/tools/compare", "/help"):
            add_path(path)

        registry = _main_mod.load_registry()
        for identity in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED):
            display_name = identity.get("display_name") or identity.get("name")
            if identity.get("merged_into") or not _main_mod.IdentityRegistry._is_real_name(display_name):
                continue
            identity_id = str(identity.get("identity_id") or "")
            if not identity_id:
                continue
            if not add_path(f"/person/{quote(identity_id, safe='')}"):
                truncated = True
                break

        if not truncated:
            if _main_mod._photo_cache is None:
                _main_mod._build_caches()
            for photo_id in (_main_mod._photo_cache or {}):
                if not add_path(f"/photo/{quote(str(photo_id), safe='')}"):
                    truncated = True
                    break
    except Exception:
        logger.exception("Sitemap data access failed; returning homepage-only sitemap")
        return _sitemap_xml(site_url, ["/"])

    # Keep the sitemap under the search-engine practical limit and our route budget.
    if truncated:
        logger.info("Sitemap capped at %s URLs", _SITEMAP_URL_LIMIT)

    return _sitemap_xml(site_url, paths)


@rt("/robots.txt")
def robots_txt():
    """Public crawler policy."""
    site_url = _main_mod.SITE_URL.rstrip("/")
    return PlainTextResponse(
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "Disallow: /admin",
                "Disallow: /api",
                "Disallow: /login",
                f"Sitemap: {site_url}/sitemap.xml",
                "",
            ]
        )
    )


@rt("/sitemap.xml")
def sitemap_xml():
    """Public XML sitemap for organic discovery."""
    global _sitemap_cache_body, _sitemap_cache_site_url, _sitemap_cache_ts

    site_url = _main_mod.SITE_URL.rstrip("/")
    now = time.time()
    if (
        _sitemap_cache_body
        and _sitemap_cache_site_url == site_url
        and now - _sitemap_cache_ts < _SITEMAP_CACHE_TTL_SECONDS
    ):
        return Response(content=_sitemap_cache_body, media_type="application/xml")

    body = _build_sitemap_xml(site_url)
    _sitemap_cache_body = body
    _sitemap_cache_site_url = site_url
    _sitemap_cache_ts = now
    return Response(content=body, media_type="application/xml")


def _prioritize_discovery_routes():
    """Move dotted discovery routes ahead of FastHTML's dotted static catch-all."""
    priority_paths = {"/robots.txt", "/sitemap.xml"}
    priority_routes = []
    other_routes = []
    for route in _main_mod.app.routes:
        if getattr(route, "path", None) in priority_paths:
            priority_routes.append(route)
        else:
            other_routes.append(route)
    _main_mod.app.routes[:] = priority_routes + other_routes


_prioritize_discovery_routes()


@rt("/health")
def health():
    """Health check endpoint for Railway deployment."""
    registry = _main_mod.load_registry()

    # Count photos from photo_index.json
    photo_count = 0
    photo_index_path = _main_mod.data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))

    # Check ML pipeline availability
    ml_available = False
    try:
        import cv2  # noqa: F811
        from insightface.app import FaceAnalysis  # noqa: F401

        ml_available = True
    except ImportError:
        pass

    # Check date estimation model
    date_model_status = "unavailable"
    try:
        from rhodesli_ml.date_inference.inference import (
            is_date_model_available,
            get_backend as date_backend,
        )

        if is_date_model_available():
            date_model_status = f"ready ({date_backend()})"
    except ImportError:
        pass

    # Check calibration model
    calibration_status = "unavailable"
    try:
        from rhodesli_ml.calibration.inference import (
            is_calibration_available,
            get_backend as cal_backend,
        )

        if is_calibration_available():
            calibration_status = f"ready ({cal_backend()})"
    except ImportError:
        pass

    # AD-162: Report disk space in health check for monitoring
    disk_info = {}
    try:
        import shutil as _shutil_health

        total, used, free = _shutil_health.disk_usage("/")
        disk_info = {
            "total_mb": round(total / (1024 * 1024)),
            "free_mb": round(free / (1024 * 1024)),
            "used_pct": round((used / total) * 100, 1),
        }
        # Also check the volume mount if it exists (separate from root FS)
        storage_dir = os.environ.get("STORAGE_DIR", "")
        if storage_dir and Path(storage_dir).exists():
            vt, vu, vf = _shutil_health.disk_usage(storage_dir)
            disk_info["volume"] = {
                "mount": storage_dir,
                "total_mb": round(vt / (1024 * 1024)),
                "free_mb": round(vf / (1024 * 1024)),
                "used_pct": round((vu / vt) * 100, 1),
            }
    except Exception:
        disk_info = {"error": "unavailable"}

    # Session 105: Data parity check — compare JSON and Supabase counts
    # Use include_merged=True to match Supabase which stores all identities
    data_parity = _check_data_parity(photo_count, len(registry.list_identities(include_merged=True)))
    served_photo_count = data_parity.get("photos_pg") if data_parity.get("photos_pg") is not None else photo_count

    return {
        "status": "ok",
        "identities": len(registry.list_identities()),
        # photos is the served Supabase count; JSON backup count is in data_parity["photos_json"].
        "photos": served_photo_count,
        "processing_enabled": _main_mod.PROCESSING_ENABLED,
        "ml_pipeline": "ready" if ml_available else "unavailable",
        "date_model": date_model_status,
        "calibration_model": calibration_status,
        "supabase": _main_mod._ping_supabase(),
        "disk": disk_info,
        "data_parity": data_parity,
    }


_landing_stats_cache = None
_landing_stats_ts = 0


def _compute_landing_stats() -> dict:
    """Compute live stats for the landing page (cached for 2 minutes)."""
    global _landing_stats_cache, _landing_stats_ts
    now = time.time()
    if _landing_stats_cache and now - _landing_stats_ts < 120:
        return _landing_stats_cache
    registry = _main_mod.load_registry()
    _main_mod._build_caches()
    all_identities = registry.list_identities()
    confirmed = registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
    inbox = registry.list_identities(state=_main_mod.IdentityState.INBOX)
    proposed = registry.list_identities(state=_main_mod.IdentityState.PROPOSED)
    total_faces = sum(len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", [])) for i in all_identities)
    skipped = registry.list_identities(state=_main_mod.IdentityState.SKIPPED)
    needs_help = sum(len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", [])) for i in inbox + proposed + skipped)
    # Collect confirmed names for display
    named_people = [i["name"] for i in confirmed if not i["name"].startswith("Unidentified")]
    # Collect a few unidentified faces for the "Can you help?" teaser
    crop_files = _main_mod.get_crop_files()
    unidentified_faces = []
    unid_identities = [i for i in inbox + proposed if not i.get("merged_into")]
    random.shuffle(unid_identities)
    for identity in unid_identities[:12]:
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        if face_ids:
            url = _main_mod.resolve_face_image_url(face_ids[0], crop_files)
            if url:
                unidentified_faces.append(
                    {
                        "identity_id": identity["identity_id"],
                        "crop_url": url,
                    }
                )
        if len(unidentified_faces) >= 6:
            break
    # Source collections
    sources = set()
    if _main_mod._photo_cache:
        for pd in _main_mod._photo_cache.values():
            src = pd.get("source", "")
            if src:
                sources.add(src)
    result = {
        "photo_count": len(_main_mod._photo_cache) if _main_mod._photo_cache else 0,
        "named_count": len(confirmed),
        "confirmed_count": len(confirmed),
        "total_faces": total_faces,
        "needs_help": needs_help,
        "named_people": named_people,
        "unidentified_faces": unidentified_faces,
        "sources": sorted(sources),
    }
    _landing_stats_cache = result
    _landing_stats_ts = now
    return result


def _get_featured_photos(limit: int = 8) -> list:
    """Pick photos that have confirmed/named identities for the landing page hero.

    Returns richer data including face bounding boxes and photo dimensions
    for the interactive hover effect on the landing page.
    """
    registry = _main_mod.load_registry()
    confirmed = registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
    _main_mod._build_caches()
    if not _main_mod._photo_cache:
        return []

    dim_cache = _main_mod._load_photo_dimensions_cache()

    # Build map of face_id -> identity name
    face_to_name = {}
    confirmed_face_ids = set()
    for identity in confirmed:
        name = identity.get("name", "")
        if name.startswith("Unidentified"):
            name = ""
        for fid in identity.get("anchor_ids", []) + identity.get("candidate_ids", []):
            confirmed_face_ids.add(fid)
            if name:
                face_to_name[fid] = name

    # Prefer landscape photos with many faces and confirmed identities
    scored_photos = []
    for photo_id, photo_data in _main_mod._photo_cache.items():
        faces = photo_data.get("faces", [])
        num_faces = len(faces)
        confirmed_count = sum(1 for f in faces if f.get("face_id") in confirmed_face_ids)
        filename = photo_data.get("filename")
        if not filename:
            continue
        dims = dim_cache.get(filename) or dim_cache.get(Path(filename).name)
        w, h = dims if dims else (0, 0)
        is_landscape = w > h if w and h else False
        # Skip photos without cached dimensions (can't render face boxes)
        if w == 0 or h == 0:
            continue
        # Score: prefer landscape, more faces, more confirmed
        score = (confirmed_count * 3) + num_faces + (2 if is_landscape else 0)
        if num_faces >= 2:  # Only show photos with multiple people
            scored_photos.append((score, photo_id))

    scored_photos.sort(key=lambda x: x[0], reverse=True)
    featured_photo_ids = [pid for _, pid in scored_photos[:limit]]

    # If not enough, fill with any multi-face photos
    if len(featured_photo_ids) < limit:
        for photo_id in _main_mod._photo_cache:
            if photo_id not in featured_photo_ids:
                faces = _main_mod._photo_cache[photo_id].get("faces", [])
                if len(faces) >= 1:
                    featured_photo_ids.append(photo_id)
                    if len(featured_photo_ids) >= limit:
                        break

    results = []
    for pid in featured_photo_ids[:limit]:
        if pid not in _main_mod._photo_cache:
            continue
        pdata = _main_mod._photo_cache[pid]
        filename = pdata.get("filename")
        if not filename:
            continue
        dims = dim_cache.get(filename) or dim_cache.get(Path(filename).name)
        w, h = dims if dims else (0, 0)
        faces = pdata.get("faces", [])

        face_boxes = []
        for face in faces:
            fid = face.get("face_id", "")
            bbox = face.get("bbox", [])
            if bbox and w > 0 and h > 0:
                # Convert bbox from pixel coords to percentages
                x1, y1, x2, y2 = bbox
                face_boxes.append(
                    {
                        "left": round(x1 / w * 100, 2),
                        "top": round(y1 / h * 100, 2),
                        "width": round((x2 - x1) / w * 100, 2),
                        "height": round((y2 - y1) / h * 100, 2),
                        "name": face_to_name.get(fid, ""),
                    }
                )

        results.append(
            {
                "id": pid,
                "url": photo_url(filename),
                "width": w,
                "height": h,
                "face_count": len(face_boxes),
                "face_boxes": face_boxes,
            }
        )
    return results


def _community_landing_page(community: dict, slug: str):
    """Render a community-specific landing page for non-Rhodes communities.

    Shows community name, subtitle, and stats. For new communities with no content,
    shows an inviting empty state.
    """
    community_name = community.get("name") or slug.replace("-", " ").title()
    title = community.get("landing_title") or community_name
    subtitle = community.get("landing_subtitle") or community.get("subtitle") or "A heritage photo archive"
    nav_prefix = _main_mod.community_url_prefix(slug)

    # Get community-specific stats using photo-derived identity set (AD-216)
    photo_count = 0
    identity_count = 0
    help_count = 0
    community_photo_ids = _main_mod._get_community_photo_ids(community)
    community_identity_ids = _main_mod._get_community_identity_ids(community)
    if community_photo_ids is not None:
        photo_count = len(community_photo_ids)
    if community_identity_ids is not None:
        identity_count = len(community_identity_ids)
        registry = _main_mod.load_registry()
        help_count = sum(
            1
            for ident in registry.list_identities()
            if ident.get("identity_id") in community_identity_ids
            and not ident.get("merged_into")
            and ident.get("state") in ("INBOX", "PROPOSED", "SKIPPED")
        )

    has_content = photo_count > 0

    og_image_url = ""
    try:
        if community_photo_ids:
            first_photo_id = next(iter(sorted(community_photo_ids)))
            first_photo = _main_mod.get_photo_metadata(first_photo_id) or {}
            photo_path = first_photo.get("path") or first_photo.get("filename", "")
            if not photo_path:
                photo_registry = _main_mod.load_photo_registry()
                photo_path = photo_registry.get_photo_path(first_photo_id) or ""
            if photo_path:
                get_photo_url = getattr(_main_mod, "get_photo_url", _main_mod.storage.get_photo_url)
                og_image_url = get_photo_url(photo_path)
    except Exception:
        og_image_url = ""

    # Build stats row
    stats_row = (
        Div(
            Div(
                Span(str(photo_count), cls="text-3xl font-bold text-amber-300"),
                Span(" photos", cls="text-slate-400 ml-1"),
                cls="text-center",
            ),
            Div(
                Span(str(identity_count), cls="text-3xl font-bold text-amber-300"),
                Span(" identities", cls="text-slate-400 ml-1"),
                cls="text-center",
            ),
            cls="flex gap-12 justify-center mb-8",
        )
        if has_content
        else None
    )

    # Description section for all communities
    description = community.get("description", "")
    description_section = (
        Div(
            P(
                description,
                cls="text-slate-300 max-w-2xl mx-auto text-center mb-8",
            ),
        )
        if description
        else Div(
            P(
                "A community photo archive for preserving and identifying heritage photographs. "
                "Upload photos, identify faces, and connect with your community's history.",
                cls="text-slate-400 max-w-2xl mx-auto text-center mb-8",
                data_testid="community-description",
            ),
        )
    )

    # Empty state for communities with no photos yet
    empty_state = (
        Div(
            Div(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 text-amber-400/40 mx-auto mb-4" '
                    'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">'
                    '<path stroke-linecap="round" stroke-linejoin="round" '
                    'd="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409'
                    "a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 "
                    '00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v13.5A1.5 1.5 0 003.75 21z"/></svg>'
                ),
                H3("This archive is just getting started", cls="text-xl font-serif text-amber-200 mb-2"),
                P(
                    "Photos will appear here as they are uploaded and processed.",
                    cls="text-slate-400 max-w-md mx-auto mb-6",
                ),
                # Upload CTA for admins (visible to all, auth checked on click)
                A(
                    "Upload Photos",
                    href=f"{nav_prefix}/upload",
                    cls="inline-block px-6 py-3 bg-amber-600 hover:bg-amber-500 text-white rounded-lg "
                    "font-medium transition-all active:scale-95 mr-3",
                    data_testid="upload-cta",
                ),
                cls="text-center py-12",
            ),
            # Tools section — always available regardless of archive content
            Div(
                P("While this archive grows, try our ML-powered tools:", cls="text-slate-400 mb-4"),
                Div(
                    A(
                        "Date & Location Estimator",
                        href="/tools/estimate",
                        cls="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 text-amber-200 "
                        "rounded-lg text-sm transition-colors",
                    ),
                    A(
                        "Face Compare",
                        href="/tools/compare",
                        cls="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 text-amber-200 "
                        "rounded-lg text-sm transition-colors",
                    ),
                    cls="flex gap-3 justify-center",
                ),
                cls="text-center pt-6 border-t border-slate-700/50",
            ),
            cls="bg-slate-800/50 rounded-xl border border-slate-700/50 p-8",
        )
        if not has_content
        else None
    )

    content_section = (
        Div(
            Div(
                P("How you can help", cls="text-sm sm:text-xs uppercase tracking-[0.28em] text-amber-300/70 mb-3"),
                H3(
                    "Start with the archive, not a dead end",
                    cls="text-2xl md:text-3xl font-display text-white mb-3",
                ),
                P(
                    (
                        f"{help_count} people still need names in this archive. "
                        "Browse the photos, identify faces, or contribute more family history."
                    )
                    if help_count
                    else "Browse the photos, explore the people already identified, or contribute more family history.",
                    cls="text-slate-300 max-w-2xl mx-auto mb-6",
                ),
                Div(
                    A(
                        "Do you recognize anyone?",
                        href=f"{nav_prefix}/help",
                        cls="inline-flex items-center justify-center px-6 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg font-semibold transition-all shadow-[0_0_15px_rgba(245,158,11,0.4)] hover:scale-105 active:scale-95",
                    ),
                    A(
                        "Browse Photos",
                        href=f"{nav_prefix}/photos",
                        cls="inline-flex items-center justify-center px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-all active:scale-95",
                    ),
                    A(
                        "People",
                        href=f"{nav_prefix}/people",
                        cls="inline-flex items-center justify-center px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg font-medium transition-colors border border-slate-700",
                    ),
                    A(
                        "Share or Upload Photos",
                        href=f"{nav_prefix}/upload",
                        cls="inline-flex items-center justify-center px-6 py-3 bg-transparent hover:bg-slate-800/60 text-slate-200 rounded-lg font-medium transition-colors border border-slate-700",
                    ),
                    cls="flex flex-wrap justify-center gap-3",
                ),
                cls="bg-slate-800/50 rounded-xl border border-slate-700/50 p-8 mt-8",
                data_testid="community-contribution-widget",
            ),
            cls="text-center mt-6",
        )
        if has_content
        else None
    )

    return (
        Title(title),
        *_main_mod.og_tags(
            community_name,
            description or subtitle,
            image_url=og_image_url,
            canonical_url=f"/c/{slug}/",
        ),
        Div(
            # Hero section
            Div(
                H1(title, cls="text-4xl md:text-5xl font-serif font-bold text-amber-100 mb-4"),
                P(
                    f"We need your help identifying faces in the {community_name}.",
                    cls="text-xl md:text-2xl text-amber-100/90 font-medium max-w-3xl mx-auto mb-10",
                ),
                description_section,
                stats_row,
                empty_state,
                content_section,
                cls="text-center py-16 px-6",
            ),
            cls="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900",
            data_testid="community-landing",
            data_community=slug,
        ),
    )


def _platform_root_page(auth_enabled: bool = False, sess=None):
    """Render a neutral platform root with explicit archive choices."""
    from app.supabase_data import get_community_by_slug, load_communities

    communities = load_communities() or []
    by_slug = {c.get("slug"): c for c in communities if c.get("slug")}
    if "rhodes" not in by_slug:
        rhodes = get_community_by_slug("rhodes")
        if rhodes:
            by_slug["rhodes"] = rhodes

    ordered = sorted(
        by_slug.values(),
        key=lambda c: (0 if c.get("slug") == "rhodes" else 1, c.get("name", c.get("slug", "")).lower()),
    )

    archive_cards = []
    total_photos = 0
    total_identities = 0
    featured_image = ""
    for community in ordered:
        slug = community.get("slug", "")
        if not slug:
            continue
        archive_href = f"/c/{slug}/"
        browse_href = f"/c/{slug}/photos"
        help_href = f"/c/{slug}/help"
        photo_ids = _main_mod._get_community_photo_ids(community)
        identity_ids = _main_mod._get_community_identity_ids(community)
        photo_count = len(photo_ids) if photo_ids is not None else 0
        identity_count = len(identity_ids) if identity_ids is not None else 0
        total_photos += photo_count
        total_identities += identity_count
        if not featured_image and photo_ids:
            first_photo_id = next(iter(photo_ids), "")
            first_photo = _main_mod.get_photo_metadata(first_photo_id)
            if first_photo:
                featured_image = _main_mod.storage.get_photo_url(first_photo.get("filename", ""))

        archive_cards.append(
            Div(
                Div(
                    Span("Featured public archive", cls="text-[11px] uppercase tracking-[0.24em] text-amber-300/70")
                    if slug == "rhodes"
                    else Span("Community archive", cls="text-[11px] uppercase tracking-[0.24em] text-slate-400"),
                    H3(
                        community.get("landing_title") or community.get("name", slug.replace("-", " ").title()),
                        cls="text-2xl font-display text-white mt-3",
                    ),
                    P(
                        community.get("landing_subtitle") or "A heritage photo archive on Rhodesli.",
                        cls="text-slate-300 mt-2",
                    ),
                    cls="mb-6",
                ),
                Div(
                    Div(
                        Span(str(photo_count), cls="block text-2xl font-semibold text-amber-200"),
                        Span("photos", cls="text-sm sm:text-xs uppercase tracking-[0.2em] text-slate-500"),
                        cls="rounded-lg border border-slate-700/70 bg-slate-900/50 px-4 py-3",
                    ),
                    Div(
                        Span(str(identity_count), cls="block text-2xl font-semibold text-amber-200"),
                        Span("people", cls="text-sm sm:text-xs uppercase tracking-[0.2em] text-slate-500"),
                        cls="rounded-lg border border-slate-700/70 bg-slate-900/50 px-4 py-3",
                    ),
                    cls="grid grid-cols-2 gap-3 mb-6",
                ),
                Div(
                    A(
                        "Enter Archive",
                        href=archive_href,
                        cls="inline-flex items-center justify-center px-5 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg font-semibold transition-colors",
                    ),
                    A(
                        "Do you recognize anyone?",
                        href=help_href,
                        cls="inline-flex items-center justify-center px-5 py-3 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg border border-slate-700 font-medium transition-colors",
                    ),
                    A(
                        "Browse Photos",
                        href=browse_href,
                        cls="inline-flex items-center justify-center px-5 py-3 bg-transparent hover:bg-slate-800/60 text-slate-200 rounded-lg border border-slate-700 font-medium transition-colors",
                    ),
                    cls="flex flex-wrap gap-3",
                ),
                cls="rounded-2xl border border-slate-700/70 bg-slate-900/55 p-6 transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:border-slate-600",
                data_testid="archive-card",
                data_archive_slug=slug,
            )
        )

    featured_photos = _main_mod._get_featured_photos(4)
    if not featured_image and featured_photos:
        featured_image = featured_photos[0].get("url", "")
    showcase_cards = []
    for photo in featured_photos:
        showcase_cards.append(
            Div(
                Img(
                    src=photo["url"],
                    alt="Featured archive photograph",
                    loading="lazy",
                    cls="h-full w-full object-cover",
                ),
                cls="hero-card aspect-[4/5] overflow-hidden rounded-2xl border border-amber-900/30 bg-slate-900/40",
            )
        )

    description = (
        "Rhodesli is the platform shell for archive-specific heritage photographs and family photo collections. "
        "Choose an archive explicitly, then browse, identify faces, and contribute history without losing context."
    )

    nav_items = [
        A("Compare", href="/tools/compare", cls="text-slate-200 hover:text-white transition-colors"),
        A("Estimate", href="/tools/estimate", cls="text-slate-200 hover:text-white transition-colors"),
        A("About", href="/about", cls="text-slate-200 hover:text-white transition-colors"),
    ]
    if auth_enabled:
        user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        if user:
            nav_items.append(
                A(
                    "Go to Archive",
                    href="/c/rhodes/",
                    cls="inline-flex items-center px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors font-medium",
                )
            )
        else:
            nav_items.append(
                A(
                    "Sign In",
                    href="/login",
                    cls="inline-flex items-center px-4 py-2 border border-amber-700/60 text-amber-200 hover:text-amber-100 hover:bg-amber-900/20 rounded-lg transition-colors",
                )
            )

    return (
        Title("Rhodesli — Community Archives"),
        *_main_mod.og_tags(
            "Rhodesli — Community Archives",
            description,
            image_url=featured_image,
            canonical_url="/",
        ),
        Style(
            """
            html, body { margin: 0; min-height: 100%; }
            body { background: linear-gradient(180deg, #1c1917 0%, #292524 48%, #1c1917 100%); overflow-x: hidden; }
            .landing-container { overflow-x: hidden; max-width: 100vw; }
            .landing-container * { box-sizing: border-box; }
            .landing-container img { max-width: 100%; }
            .platform-grid { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
            .platform-mosaic { grid-template-columns: repeat(4, minmax(0, 1fr)); }
            @media (max-width: 900px) { .platform-mosaic { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
            @media (max-width: 640px) { .platform-mosaic { grid-template-columns: repeat(1, minmax(0, 1fr)); } }
            """
        ),
        Main(
            Div(
                Div(
                    A("Rhodesli", href="/", cls="text-xl font-bold text-white tracking-tight"),
                    Div(*nav_items, cls="flex items-center gap-6 text-sm"),
                    cls="mx-auto flex max-w-6xl items-center justify-between px-6 py-5",
                ),
                cls="border-b border-slate-800/80",
            ),
            Section(
                Div(
                    Div(
                        Span("Platform", cls="text-sm sm:text-xs uppercase tracking-[0.32em] text-amber-300/80"),
                        H1(
                            "Choose an archive, then help preserve it.",
                            cls="mt-4 text-4xl md:text-6xl font-display text-white leading-tight",
                        ),
                        P(
                            "Rhodesli keeps platform, archive, and contribution contexts distinct. "
                            "Pick the archive you mean to explore so browsing, identifying, and sharing stay coherent.",
                            cls="mt-5 max-w-3xl text-xl sm:text-lg text-slate-300",
                        ),
                        Div(
                            A(
                                "Browse the Rhodes demo archive",
                                href="/c/rhodes/",
                                cls="inline-flex items-center justify-center px-6 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg font-semibold transition-colors",
                            ),
                            A(
                                "Jump to the archive directory",
                                href="#archive-directory",
                                cls="inline-flex items-center justify-center px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg border border-slate-700 font-medium transition-colors",
                            ),
                            cls="mt-8 flex flex-wrap gap-3",
                        ),
                        Div(
                            Div(
                                Span(str(len(archive_cards)), cls="block text-3xl font-semibold text-amber-200"),
                                Span("archives", cls="text-sm sm:text-xs uppercase tracking-[0.2em] text-slate-500"),
                            ),
                            Div(
                                Span(str(total_photos), cls="block text-3xl font-semibold text-amber-200"),
                                Span("photos", cls="text-sm sm:text-xs uppercase tracking-[0.2em] text-slate-500"),
                            ),
                            Div(
                                Span(str(total_identities), cls="block text-3xl font-semibold text-amber-200"),
                                Span("people", cls="text-sm sm:text-xs uppercase tracking-[0.2em] text-slate-500"),
                            ),
                            cls="mt-10 grid grid-cols-3 gap-4 max-w-2xl",
                            id="stats",
                        ),
                        cls="max-w-3xl",
                    ),
                    Div(
                        Div(*showcase_cards, cls="grid platform-mosaic gap-4") if showcase_cards else None,
                        Div(
                            P(
                                "Featured public archive",
                                cls="text-sm sm:text-xs uppercase tracking-[0.28em] text-amber-300/70",
                            ),
                            H2("Jewish Community of Rhodes", cls="mt-3 text-2xl font-display text-white"),
                            P(
                                "The Rhodes archive remains the clearest public example of the platform. "
                                "It stays available as an explicit demo path, not the silent default.",
                                cls="mt-3 text-slate-300",
                            ),
                            cls="mt-6",
                        ),
                        cls="mt-12 lg:mt-0",
                    ),
                    cls="mx-auto grid max-w-6xl gap-12 px-6 py-16 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.95fr)]",
                    id="hero",
                    data_testid="platform-root",
                ),
            ),
            Section(
                Div(
                    Div(
                        Span(
                            "Archive directory", cls="text-sm sm:text-xs uppercase tracking-[0.28em] text-amber-300/70"
                        ),
                        H2("Enter the archive you actually mean to use.", cls="mt-3 text-3xl font-display text-white"),
                        P(
                            "This removes the old Rhodes-by-default ambiguity. Each archive keeps its own landing page, help flow, and share context.",
                            cls="mt-3 max-w-3xl text-slate-300",
                        ),
                        cls="mb-8",
                    ),
                    Div(*archive_cards, cls="grid platform-grid gap-5", id="archive-directory"),
                    cls="mx-auto max-w-6xl px-6 pb-16",
                ),
            ),
            cls="landing-container",
        ),
    )


def landing_page(stats, featured_photos, nav_prefix: str = ""):
    """Render the public landing page for the Rhodesli heritage archive.

    This page is only shown to anonymous visitors. Logged-in users are
    redirected to the dashboard by the GET / route handler.
    """
    auth_enabled = _main_mod.is_auth_enabled()

    # Build hero photo cards with face detection overlay data
    hero_cards = []
    for i, p in enumerate(featured_photos[:6]):
        # Build face detection overlay boxes (shown on hover)
        face_overlays = []
        for box in p.get("face_boxes", []):
            name = box.get("name", "")
            face_overlays.append(
                Div(
                    Span(name, cls="face-label") if name else None,
                    cls="face-box",
                    style=f"left:{box['left']}%;top:{box['top']}%;width:{box['width']}%;height:{box['height']}%;",
                )
            )
        # Determine grid span for visual variety
        span_cls = ""
        if i == 0:
            span_cls = "md:col-span-2 md:row-span-2"

        hero_cards.append(
            Div(
                Img(
                    src=p["url"],
                    alt="Archival photograph from the Jewish community of Rhodes",
                    loading="eager" if i < 2 else "lazy",
                    cls="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105",
                    onerror="this.closest('.hero-card').style.display='none'",
                ),
                # Face detection overlay
                Div(*face_overlays, cls="face-overlay") if face_overlays else None,
                # Face count badge
                Div(
                    Span(f"{p['face_count']} faces detected", cls="text-sm sm:text-xs"),
                    cls="absolute bottom-2 right-2 bg-black/70 text-amber-200 px-4 py-3 sm:px-2 sm:py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300",
                )
                if p.get("face_count", 0) > 0
                else None,
                cls=f"hero-card group relative overflow-hidden {span_cls}",
            )
        )

    # "Can you help?" mystery faces
    mystery_faces = []
    for face in stats.get("unidentified_faces", []):
        mystery_faces.append(
            A(
                Img(
                    src=face["crop_url"],
                    alt="Unidentified person from the Rhodes archive",
                    loading="lazy",
                    cls="w-full h-full object-cover rounded-full border-2 border-amber-400/50 hover:border-amber-300 transition-all duration-300 hover:scale-110",
                ),
                href=f"{nav_prefix}/identify/{face['identity_id']}",
                cls="block w-20 h-20 md:w-24 md:h-24 rounded-full overflow-hidden flex-shrink-0",
            )
        )

    # Navigation bar
    _nav_cls = "text-amber-100/70 hover:text-amber-50 transition-colors font-serif tracking-wide text-sm md:text-base ui99-landing-nav"
    nav_items = [
        A("Photos", href=f"{nav_prefix}/photos", cls=_nav_cls),
        A("Collections", href=f"{nav_prefix}/collections", cls=_nav_cls),
        A("People", href=f"{nav_prefix}/people", cls=_nav_cls),
        A("Map", href=f"{nav_prefix}/map", cls=_nav_cls),
        A("Timeline", href=f"{nav_prefix}/timeline", cls=_nav_cls),
        Span("|", cls="text-amber-900/40 hidden md:inline"),
        A("Tree", href=f"{nav_prefix}/tree", cls=_nav_cls),
        A("Compare", href="/tools/compare", cls=_nav_cls),
        A("About", href="/about", cls=_nav_cls),
        A(
            "Recognize Anyone?",
            href=f"{nav_prefix}/help",
            cls="text-amber-400 hover:text-amber-300 font-serif font-medium text-sm md:text-base transition-colors border border-amber-800/50 hover:bg-amber-900/20 px-3 py-1 rounded-sm ml-2",
        ),
    ]
    if auth_enabled:
        nav_items.append(
            A(
                "Sign In",
                href="/login",
                cls="text-amber-500 hover:text-amber-400 font-serif transition-colors text-sm md:text-base ml-2",
            )
        )

    # Named people for the ticker / display
    named_people = stats.get("named_people", [])

    landing_style = Style("""
        /* ============ LANDING PAGE STYLES ============ */
        html, body { height: 100%; margin: 0; }
        body { background-color: #1a1511; overflow-x: hidden; max-width: 100vw; }
        /* UX-134: Prevent horizontal overflow on mobile */
        .landing-container { overflow-x: hidden; max-width: 100vw; width: 100%; }
        .landing-container * { box-sizing: border-box; }
        .landing-container img { max-width: 100%; }
        .landing-container .hero-mosaic img { max-width: none; }

        /* Warm sepia/archival color palette */
        .landing-bg { background: linear-gradient(180deg, #1a1511 0%, #1e1a15 40%, #1a1511 100%); }

        /* Hero mosaic grid */
        .hero-mosaic {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: repeat(2, 200px);
            gap: 3px;
        }
        @media (max-width: 767px) {
            .hero-mosaic {
                grid-template-columns: repeat(2, 1fr);
                grid-template-rows: repeat(3, 160px);
            }
            .hero-mosaic .md\\:col-span-2 { grid-column: span 2; }
            .hero-mosaic .md\\:row-span-2 { grid-row: span 1; }
        }
        @media (min-width: 768px) {
            .hero-mosaic {
                grid-template-rows: repeat(2, 220px);
            }
        }
        @media (min-width: 1024px) {
            .hero-mosaic {
                grid-template-rows: repeat(2, 260px);
            }
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            background: #2a241e;
        }
        .hero-card::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to bottom, transparent 60%, rgba(26, 21, 17, 0.6) 100%);
            pointer-events: none;
        }

        /* Face detection overlay */
        .face-overlay {
            position: absolute;
            inset: 0;
            opacity: 0;
            transition: opacity 0.4s ease;
            z-index: 5;
        }
        .hero-card:hover .face-overlay {
            opacity: 1;
        }
        .face-box {
            position: absolute;
            border: 2px solid rgba(251, 191, 36, 0.8);
            border-radius: 3px;
            box-shadow: 0 0 8px rgba(251, 191, 36, 0.3);
            min-width: 44px;
            min-height: 44px;
            /* Center around face when bbox is smaller than minimum */
            transform: translate(
                min(0px, calc((100% - 44px) / 2)),
                min(0px, calc((100% - 44px) / 2))
            );
        }
        .face-box:hover {
            transform: scale(1.2);
            z-index: 50;
            transition: transform 0.15s ease;
        }
        .face-label {
            position: absolute;
            bottom: -22px;
            left: 50%;
            transform: translateX(-50%);
            display: inline-block;
            white-space: nowrap;
            font-size: 11px;
            color: #fbbf24;
            background: rgba(0, 0, 0, 0.8);
            padding: 1px 6px;
            border-radius: 3px;
            max-width: 120px;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Sepia film border on hero */
        .hero-frame {
            border: 3px solid #3d3428;
            border-radius: 4px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5), inset 0 0 40px rgba(0, 0, 0, 0.2);
            position: relative;
        }
        .hero-frame::before {
            content: '';
            position: absolute;
            inset: -1px;
            border: 1px solid rgba(251, 191, 36, 0.1);
            border-radius: 5px;
            pointer-events: none;
            z-index: 10;
        }

        /* Stat counter animation */
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #f5e6d3;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #a09080;
            margin-top: 0.5rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .stat-card {
            text-align: center;
            padding: 1.5rem 1rem;
            background: rgba(61, 52, 40, 0.3);
            border: 1px solid rgba(61, 52, 40, 0.5);
            border-radius: 8px;
            transition: transform 0.2s, border-color 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: rgba(251, 191, 36, 0.3);
        }

        /* Name ticker / scroll */
        .names-scroll {
            display: flex;
            gap: 2rem;
            animation: scroll-names 30s linear infinite;
            width: max-content;
            max-width: none;
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            align-items: center;
        }
        @keyframes scroll-names {
            from { transform: translateX(0); }
            to { transform: translateX(-50%); }
        }
        .names-track {
            position: relative;
            width: 100%;
            max-width: 100%;
            min-height: 1.75rem;
            overflow: hidden;
            mask-image: linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%);
            -webkit-mask-image: linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%);
        }
        @media (max-width: 767px) {
            .names-track {
                display: none;
            }
        }

        /* Animations */
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up { animation: fade-in-up 0.8s ease-out both; }
        .delay-1 { animation-delay: 0.15s; }
        .delay-2 { animation-delay: 0.3s; }
        .delay-3 { animation-delay: 0.45s; }
        .delay-4 { animation-delay: 0.6s; }

        @keyframes gentle-pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        .animate-gentle-pulse { animation: gentle-pulse 3s ease-in-out infinite; }

        /* CTA buttons */
        .btn-ui99-primary {
            display: inline-block;
            padding: 0.875rem 2.5rem;
            background: linear-gradient(135deg, #b45309 0%, #d97706 100%);
            color: #fff;
            font-weight: 600;
            font-family: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif;
            letter-spacing: 0.025em;
            border-radius: 4px;
            border: 1px solid #f59e0b;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            text-decoration: none;
            font-size: 1.125rem;
            box-shadow: 0 4px 14px rgba(180, 83, 9, 0.4), inset 0 1px 0 rgba(255,255,255,0.2);
        }
        .btn-ui99-primary:hover {
            background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            box-shadow: 0 6px 20px rgba(180, 83, 9, 0.6), inset 0 1px 0 rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }
        .btn-ui99-secondary {
            display: inline-block;
            padding: 0.875rem 2.5rem;
            border: 1px solid #78350f;
            background: rgba(69, 26, 3, 0.5);
            color: #fcd34d;
            font-weight: 500;
            font-family: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif;
            letter-spacing: 0.025em;
            border-radius: 4px;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            text-decoration: none;
            font-size: 1.125rem;
            backdrop-filter: blur(4px);
        }
        .btn-ui99-secondary:hover {
            border-color: #b45309;
            background: rgba(120, 53, 15, 0.7);
            color: #fffbeb;
            transform: translateY(-2px);
            box-shadow: 0 4px 14px rgba(120, 53, 15, 0.4);
        }

        /* About section separator */
        .ornament {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin: 0 auto;
            max-width: 200px;
        }
        .ornament::before, .ornament::after {
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(to right, transparent, #5d4e3c, transparent);
        }

        /* Mystery face glow */
        .mystery-face-ring {
            position: relative;
        }
        .mystery-face-ring::before {
            content: '';
            position: absolute;
            inset: -3px;
            border-radius: 50%;
            background: conic-gradient(from 0deg, #fbbf24, #b45309, #fbbf24);
            opacity: 0;
            transition: opacity 0.3s;
            z-index: -1;
        }
        .mystery-face-ring:hover::before {
            opacity: 0.6;
            animation: gentle-pulse 2s ease-in-out infinite;
        }

        /* Responsive adjustments */
        @media (max-width: 640px) {
            .stat-number { font-size: 1.75rem; }
            .stat-card { padding: 1rem 0.5rem; }
            /* UX-134: Mobile button sizing */
            .btn-ui99-primary, .btn-ui99-secondary {
                padding: 0.75rem 1.5rem;
                font-size: 1rem;
                width: 100%;
                text-align: center;
            }
        }
        /* UX-134: Constrain all sections on mobile */
        @media (max-width: 767px) {
            .landing-container section,
            .landing-container nav,
            .landing-container footer {
                max-width: 100vw;
                overflow-x: hidden;
            }
            /* Landing nav title truncation */
            .ui99-landing-title {
                font-size: 1.75rem !important;
                word-break: break-word;
            }
            .ui99-landing-body {
                font-size: 1rem !important;
            }
        }

        /* ============================================================
           MOBILE RESPONSIVE STYLES
           ============================================================ */
        @media (max-width: 767px) {
            .main-content {
                margin-left: 0 !important;
                padding-top: 56px;
            }
            .main-content .main-inner {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1rem;
            }
            .focus-card-layout {
                flex-direction: column !important;
                gap: 1rem !important;
            }
            .focus-card-layout .focus-thumbnail {
                width: 100% !important;
            }
            .focus-card-layout .focus-thumbnail > div {
                width: 100% !important;
                height: auto !important;
                aspect-ratio: 1 / 1;
                max-width: 200px;
                margin: 0 auto;
            }
            .focus-actions {
                flex-wrap: wrap !important;
            }
            .focus-actions button {
                flex: 1 1 auto;
                min-width: 80px;
            }
            .section-header {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.75rem;
            }
            .filter-bar {
                flex-direction: column !important;
                align-items: stretch !important;
                gap: 0.5rem !important;
            }
            .filter-bar .ml-auto {
                margin-left: 0;
            }
            .identity-card-header {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.5rem;
            }
            .neighbors-sidebar .flex.items-center {
                flex-wrap: wrap;
            }
            #toast-container {
                left: 1rem;
                right: 1rem;
                max-width: none;
            }
        }
        @media (min-width: 768px) and (max-width: 1023px) {
            .main-content {
                margin-left: 0 !important;
                padding-top: 56px;
            }
            .main-content .main-inner {
                padding-left: 2rem;
                padding-right: 2rem;
            }
        }
        @media (max-width: 1023px) {
            .mobile-header {
                display: flex !important;
            }
        }
        @media (min-width: 1024px) {
            .mobile-header {
                display: none !important;
            }
            .main-content {
                margin-left: 16rem;
            }
        }
    """)

    landing_script = Script("""
        // Animated counter for stats
        document.addEventListener('DOMContentLoaded', function() {
            var counters = document.querySelectorAll('[data-count]');
            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var el = entry.target;
                        var target = parseInt(el.getAttribute('data-count'));
                        var duration = 1500;
                        var start = 0;
                        var startTime = null;
                        function step(timestamp) {
                            if (!startTime) startTime = timestamp;
                            var progress = Math.min((timestamp - startTime) / duration, 1);
                            // Ease out cubic
                            var eased = 1 - Math.pow(1 - progress, 3);
                            el.textContent = Math.floor(eased * target).toLocaleString();
                            if (progress < 1) {
                                requestAnimationFrame(step);
                            } else {
                                el.textContent = target.toLocaleString();
                            }
                        }
                        requestAnimationFrame(step);
                        observer.unobserve(el);
                    }
                });
            }, {threshold: 0.3});
            counters.forEach(function(c) { observer.observe(c); });
        });
    """)

    # Duplicate names list for seamless scroll effect
    names_display = named_people + named_people if named_people else []

    # OG meta tags for social sharing
    _og_hero_url = f"{_main_mod.SITE_URL}/static/crops/landing-hero.jpg"
    if featured_photos:
        _hero_url = featured_photos[0].get("url", "")
        _og_hero_url = _hero_url if _hero_url.startswith("http") else f"{_main_mod.SITE_URL}{_hero_url}"
    _og_desc = f"A living archive of {stats['photo_count']} photographs and {stats['named_count']} identified people from the Jewish community of Rhodes. Help us preserve our shared heritage."

    return (
        Title("Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(property="og:title", content="Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(property="og:description", content=_og_desc),
        Meta(property="og:image", content=_og_hero_url),
        Meta(property="og:url", content=_main_mod.SITE_URL),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="Rhodesli -- Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content="Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(name="twitter:description", content=_og_desc),
        Meta(name="twitter:image", content=_og_hero_url),
        Meta(name="description", content=_og_desc),
        landing_style,
        landing_script,
        Div(
            # Navigation
            Nav(
                Div(
                    Div(
                        Span(
                            "Rhodesli",
                            cls="text-xl md:text-2xl font-bold text-amber-50 tracking-wide font-display ui99-title",
                        ),
                        Span(
                            "Heritage Archive",
                            cls="text-sm sm:text-xs text-amber-500/80 ml-2 hidden md:inline tracking-[0.2em] uppercase font-mono",
                        ),
                        cls="flex items-baseline",
                    ),
                    Div(*nav_items, cls="hidden sm:flex items-center gap-4 md:gap-6"),
                    cls="max-w-6xl mx-auto px-4 md:px-6 py-5 flex items-center justify-between flex-wrap gap-3",
                ),
                cls="border-b border-amber-900/20 bg-[#16120e]/95 backdrop-blur-md sticky top-0 z-50",
            ),
            # Hero section
            Section(
                Div(
                    # Headline area
                    Div(
                        Div(
                            Div(cls="ornament mb-8"),
                            H1(
                                Span("Preserving the faces and stories", cls="block"),
                                Span("of the Jewish Community of Rhodes", cls="block text-amber-400 mt-2"),
                                cls="text-4xl md:text-6xl lg:text-7xl font-bold text-amber-50 leading-tight tracking-tight font-display ui99-landing-title drop-shadow-lg",
                            ),
                            P(
                                "For over 450 years, a Sephardic community thrived on the island of Rhodes \u2014 speaking Ladino, "
                                "preserving ancient traditions, and filling the Juderia with life. In July 1944, nearly all were "
                                "deported to Auschwitz. Only 151 survived. This archive uses face recognition to reconnect their "
                                "descendants with the faces and stories that remain.",
                                cls="text-xl sm:text-lg md:text-xl text-amber-100/70 mt-8 max-w-3xl mx-auto leading-relaxed font-serif ui99-landing-body",
                            ),
                            # CTA buttons
                            Div(
                                A("Start Exploring", href="/photos", cls="btn-ui99-primary"),
                                A("Do you recognize anyone?", href="/help", cls="btn-ui99-secondary"),
                                cls="mt-10 flex flex-col sm:flex-row flex-wrap gap-4 sm:gap-5 justify-center items-center",
                            ),
                            cls="text-center animate-fade-in-up",
                        ),
                        cls="py-12 md:py-20 px-4 md:px-6",
                    ),
                    # Photo mosaic with face detection hover
                    Div(
                        Div(*hero_cards, cls="hero-mosaic"),
                        # Instruction hint
                        P(
                            "Hover over photos to reveal face detection",
                            cls="text-center text-amber-400/40 text-sm sm:text-xs mt-3 tracking-wide uppercase animate-gentle-pulse",
                        ),
                        cls="hero-frame animate-fade-in-up delay-1",
                    )
                    if hero_cards
                    else None,
                    cls="max-w-5xl mx-auto",
                ),
                id="hero",
                cls="pt-4 pb-8 md:pb-12",
            ),
            # Names ticker -- confirmed identities scrolling
            Section(
                Div(
                    P(
                        "Identified so far",
                        cls="text-center text-amber-400/50 text-sm sm:text-xs tracking-widest uppercase mb-3",
                    ),
                    Div(
                        Div(
                            *[
                                Span(name, cls="text-amber-200/70 whitespace-nowrap text-sm md:text-base")
                                for name in names_display
                            ],
                            cls="names-scroll",
                        ),
                        cls="names-track",
                    ),
                    cls="max-w-5xl mx-auto",
                ),
                cls="py-6 px-4 border-y border-amber-900/20",
            )
            if named_people
            else None,
            # Progress dashboard (FE-053) — prominent identification progress
            Section(
                Div(
                    # Progress headline
                    Div(
                        H2(
                            Span(str(stats["named_count"]), cls="text-amber-200"),
                            " of ",
                            Span(str(stats["total_faces"]), cls="text-amber-100/80"),
                            " faces identified",
                            cls="text-xl md:text-2xl font-bold text-amber-50 text-center",
                        ),
                        P(
                            "Help us name the rest \u2014 every identification preserves irreplaceable history.",
                            cls="text-amber-100/40 text-center text-sm mt-2",
                        ),
                        cls="mb-6",
                    ),
                    # Progress bar
                    Div(
                        Div(
                            cls="h-full bg-gradient-to-r from-amber-600 to-amber-400 rounded-full transition-all duration-1000",
                            style=f"width: {min(100, int(stats['named_count'] / max(1, stats['total_faces']) * 100))}%",
                        ),
                        cls="w-full max-w-lg mx-auto h-3 bg-amber-900/30 rounded-full overflow-hidden border border-amber-900/40",
                    ),
                    Div(
                        Span(
                            f"{min(100, int(stats['named_count'] / max(1, stats['total_faces']) * 100))}% complete",
                            cls="text-amber-400/60 text-sm sm:text-xs",
                        ),
                        cls="text-center mt-2",
                    ),
                    cls="max-w-4xl mx-auto animate-fade-in-up",
                ),
                cls="py-8 md:py-10 px-4 md:px-6",
            ),
            # Stats section
            Section(
                Div(
                    Div(
                        Div(
                            Div("0", cls="stat-number", **{"data-count": str(stats["photo_count"])}),
                            Div("archival photos", cls="stat-label"),
                            cls="stat-card animate-fade-in-up",
                        ),
                        Div(
                            Div("0", cls="stat-number", **{"data-count": str(stats["named_count"])}),
                            Div("people identified", cls="stat-label"),
                            cls="stat-card animate-fade-in-up delay-1",
                        ),
                        Div(
                            Div("0", cls="stat-number", **{"data-count": str(stats["total_faces"])}),
                            Div("faces detected by AI", cls="stat-label"),
                            cls="stat-card animate-fade-in-up delay-2",
                        ),
                        Div(
                            Div("0", cls="stat-number", **{"data-count": str(stats["needs_help"])}),
                            Div("awaiting identification", cls="stat-label"),
                            cls="stat-card animate-fade-in-up delay-3",
                        ),
                        cls="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4",
                    ),
                    cls="max-w-4xl mx-auto",
                ),
                id="stats",
                cls="py-12 md:py-16 px-4 md:px-6",
            ),
            # Get Involved CTAs — prominent action buttons for visitors
            Section(
                Div(
                    Div(cls="ornament mb-6"),
                    H2("Get Involved", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-8"),
                    Div(
                        A(
                            Div(
                                Div("Do you recognize anyone?", cls="text-xl sm:text-lg font-semibold font-serif"),
                                P(
                                    "Your knowledge preserves irreplaceable history.",
                                    cls="text-sm text-amber-200/60 mt-2 leading-relaxed",
                                ),
                                cls="text-center",
                            ),
                            href=f"{nav_prefix}/help",
                            cls="block px-8 py-6 bg-gradient-to-br from-amber-700/40 to-amber-900/30 hover:from-amber-700/60 hover:to-amber-800/40 text-amber-50 rounded-xl text-center transition-all duration-300 border border-amber-700/30 hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-900/20 hover:-translate-y-0.5",
                            data_testid="cta-help-identify",
                        ),
                        A(
                            Div(
                                Div("Compare a Face", cls="text-xl sm:text-lg font-semibold font-serif"),
                                P(
                                    "Upload a photo and let AI find matches across the archive.",
                                    cls="text-sm text-amber-200/60 mt-2 leading-relaxed",
                                ),
                                cls="text-center",
                            ),
                            href="/tools/compare",
                            cls="block px-8 py-6 bg-gradient-to-br from-amber-700/40 to-amber-900/30 hover:from-amber-700/60 hover:to-amber-800/40 text-amber-50 rounded-xl text-center transition-all duration-300 border border-amber-700/30 hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-900/20 hover:-translate-y-0.5",
                            data_testid="cta-compare-face",
                        ),
                        A(
                            Div(
                                Div("Explore the Archive", cls="text-xl sm:text-lg font-semibold font-serif"),
                                P(
                                    "Browse photos, people, and collections from over nine decades.",
                                    cls="text-sm text-amber-200/60 mt-2 leading-relaxed",
                                ),
                                cls="text-center",
                            ),
                            href=f"{nav_prefix}/people",
                            cls="block px-8 py-6 bg-gradient-to-br from-amber-700/40 to-amber-900/30 hover:from-amber-700/60 hover:to-amber-800/40 text-amber-50 rounded-xl text-center transition-all duration-300 border border-amber-700/30 hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-900/20 hover:-translate-y-0.5",
                            data_testid="cta-explore-archive",
                        ),
                        cls="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-4xl mx-auto",
                    ),
                    cls="max-w-5xl mx-auto",
                    data_testid="visitor-cta-section",
                ),
                id="get-involved",
                cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-900/8 to-transparent",
            ),
            # Feature entry points — clear paths to explore the archive
            Section(
                Div(
                    Div(cls="ornament mb-6"),
                    H2("Explore the Archive", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-8"),
                    Div(
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/></svg>'
                                ),
                                H3("Browse Photos", cls="text-base font-semibold text-amber-100 mb-1"),
                                P(
                                    f"{stats['photo_count']} photos from 9 decades",
                                    cls="text-amber-100/40 text-sm sm:text-xs",
                                ),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href="/photos",
                            cls="block",
                        ),
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/></svg>'
                                ),
                                H3("People", cls="text-base font-semibold text-amber-100 mb-1"),
                                P(
                                    f"{stats['named_count']} identified people",
                                    cls="text-amber-100/40 text-sm sm:text-xs",
                                ),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href="/people",
                            cls="block",
                        ),
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"/></svg>'
                                ),
                                H3("Map", cls="text-base font-semibold text-amber-100 mb-1"),
                                P("See where families settled", cls="text-amber-100/40 text-sm sm:text-xs"),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href="/map",
                            cls="block",
                        ),
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg>'
                                ),
                                H3("Timeline", cls="text-base font-semibold text-amber-100 mb-1"),
                                P("Watch the story unfold", cls="text-amber-100/40 text-sm sm:text-xs"),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href=f"{nav_prefix}/timeline",
                            cls="block",
                        ),
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/></svg>'
                                ),
                                H3("Family Tree", cls="text-base font-semibold text-amber-100 mb-1"),
                                P("Interactive genealogy", cls="text-amber-100/40 text-sm sm:text-xs"),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href="/tree",
                            cls="block",
                        ),
                        A(
                            Div(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>'
                                ),
                                H3("Compare", cls="text-base font-semibold text-amber-100 mb-1"),
                                P("Upload a photo, find matches", cls="text-amber-100/40 text-sm sm:text-xs"),
                                cls="p-5 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-500/40 hover:bg-amber-900/20 transition-all h-full",
                            ),
                            href="/tools/compare",
                            cls="block",
                        ),
                        cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 md:gap-4",
                    ),
                    cls="max-w-4xl mx-auto",
                    data_testid="feature-cards",
                ),
                id="explore",
                cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-900/5 to-transparent",
            ),
            # "Can you help?" mystery faces section
            Section(
                Div(
                    Div(
                        H2(
                            "Can you identify these faces?",
                            cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-3",
                        ),
                        P(
                            "Our AI has detected these faces across the archive, but we do not know who they are. "
                            "If you recognize anyone, your knowledge is priceless.",
                            cls="text-amber-100/50 text-center max-w-xl mx-auto text-sm md:text-base",
                        ),
                        cls="mb-8",
                    ),
                    # Mystery face circles
                    Div(
                        *[Div(face, cls="mystery-face-ring") for face in mystery_faces],
                        cls="flex justify-center gap-5 md:gap-8 flex-wrap",
                    )
                    if mystery_faces
                    else None,
                    Div(
                        A("Do you recognize anyone?", href="/help", cls="btn-ui99-primary mt-8 inline-block"),
                        A(
                            f"See all {stats['needs_help']} →",
                            href="/help",
                            cls="text-amber-400/60 hover:text-amber-300 text-sm ml-4 mt-8 inline-block font-serif",
                        ),
                        cls="text-center",
                    ),
                    cls="max-w-3xl mx-auto",
                ),
                id="identify",
                cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-900/10 to-transparent",
            )
            if mystery_faces
            else None,
            # How it works
            Section(
                Div(
                    Div(cls="ornament mb-8"),
                    H2("How It Works", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-10"),
                    Div(
                        Div(
                            Div(Span("01", cls="text-3xl font-bold text-amber-500/30"), cls="mb-3"),
                            H3("Scan & Detect", cls="text-xl sm:text-lg font-semibold text-amber-100 mb-2"),
                            P(
                                "Advanced face detection AI scans archival photographs, finding and isolating every face "
                                "across decades of family photos.",
                                cls="text-amber-100/50 text-sm leading-relaxed",
                            ),
                            cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors",
                        ),
                        Div(
                            Div(Span("02", cls="text-3xl font-bold text-amber-500/30"), cls="mb-3"),
                            H3("Match & Group", cls="text-xl sm:text-lg font-semibold text-amber-100 mb-2"),
                            P(
                                "Facial embeddings connect the same person across different photos, even spanning decades. "
                                "The system proposes identity clusters for human review.",
                                cls="text-amber-100/50 text-sm leading-relaxed",
                            ),
                            cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors",
                        ),
                        Div(
                            Div(Span("03", cls="text-3xl font-bold text-amber-500/30"), cls="mb-3"),
                            H3("Name & Preserve", cls="text-xl sm:text-lg font-semibold text-amber-100 mb-2"),
                            P(
                                "Community members who recognize a face can name them, adding irreplaceable human knowledge. "
                                "Every identification is preserved for future generations.",
                                cls="text-amber-100/50 text-sm leading-relaxed",
                            ),
                            cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors",
                        ),
                        cls="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6",
                    ),
                    cls="max-w-5xl mx-auto",
                ),
                id="how-it-works",
                cls="py-12 md:py-16 px-4 md:px-6",
            ),
            # About section
            Section(
                Div(
                    Div(cls="ornament mb-8"),
                    H2("About This Archive", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-6"),
                    Div(
                        P(
                            "After the expulsion from Spain in 1492, Sephardic families settled on the island of Rhodes, "
                            "building a vibrant community in the walled quarter known as ",
                            Em("La Juderia"),
                            ". They spoke Ladino \u2014 a form of medieval Spanish interwoven with Hebrew, Arabic, Greek, "
                            "and Turkish \u2014 and preserved centuries of folklore, ballads, and traditions in remarkable "
                            "isolation. By 1920, over 4,000 Jews called Rhodes home, a quarter of the town\u2019s population. "
                            "The ",
                            Em("Kahal Shalom"),
                            " synagogue and the great ",
                            Em("Kal Grande"),
                            " stood at the heart of communal life, the latter housing an 800-year-old Torah scroll.",
                            cls="text-amber-100/60 leading-relaxed mb-4",
                        ),
                        P(
                            "Beginning in the early 20th century, Rhodesli Jews emigrated in waves \u2014 first to nearby "
                            "communities, then further abroad as the Italian occupation of 1912 and the racial laws "
                            "of 1938 uprooted families. Chain migration carried them to Seattle and Los Angeles, Montgomery "
                            "and Atlanta, Buenos Aires and S\u00e3o Paulo, and communities across Africa and beyond. "
                            "In July 1944, the Germans deported nearly all 1,800 remaining Jews to Auschwitz. Only 151 "
                            "survived. About 40 more were saved by the Turkish consul, who vouched for their citizenship.",
                            cls="text-amber-100/60 leading-relaxed mb-4",
                        ),
                        P(
                            "Rhodesli is a digital preservation project that uses AI face recognition to reconnect "
                            "descendants with the faces in these photographs. The images come from family collections "
                            "around the world. Every face you identify \u2014 every name you recognize, every story you "
                            "share \u2014 helps preserve what the survivors and their descendants have fought to keep alive.",
                            cls="text-amber-100/60 leading-relaxed mb-4",
                        ),
                        A(
                            "Read more about the project \u2192",
                            href="/about",
                            cls="text-amber-300/70 hover:text-amber-200 text-sm inline-block",
                        ),
                        cls="max-w-2xl mx-auto text-center",
                    ),
                    cls="max-w-5xl mx-auto",
                ),
                id="about",
                cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-950/20 to-transparent",
            ),
            # Bottom CTA
            Section(
                Div(
                    H2("Every name matters", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-3"),
                    P(
                        f"{stats['needs_help']} faces are awaiting identification. Your family knowledge can bring them home.",
                        cls="text-amber-100/50 text-center mb-8 max-w-lg mx-auto",
                    ),
                    Div(
                        A("Start Exploring", href=f"{nav_prefix}/?section=photos", cls="btn-ui99-primary"),
                        A("Browse People", href=f"{nav_prefix}/?section=confirmed", cls="btn-ui99-secondary"),
                        cls="flex flex-col sm:flex-row flex-wrap gap-4 justify-center items-center",
                    ),
                    cls="max-w-3xl mx-auto text-center",
                ),
                id="cta",
                cls="py-12 md:py-16 px-4 md:px-6",
            ),
            # Footer
            Footer(
                Div(
                    Div(cls="ornament mb-4"),
                    P("Rhodesli", cls="text-amber-200/40 text-sm text-center font-semibold tracking-wide"),
                    P(
                        "Preserving the photographic heritage of the Jewish Community of Rhodes",
                        cls="text-amber-100/25 text-sm sm:text-xs text-center mt-1",
                    ),
                    P(
                        A("About Rhodesli", href="/about", cls="text-amber-200/40 hover:text-amber-200 underline"),
                        " · Built with care. No generative AI -- only forensic face matching.",
                        cls="text-amber-100/20 text-sm sm:text-xs text-center mt-3",
                    ),
                    cls="max-w-6xl mx-auto px-6 py-8",
                ),
                cls="border-t border-amber-900/20",
            ),
            cls="min-h-screen landing-bg landing-container overflow-x-hidden w-full",
        ),
    )


@rt("/about")
def get(request=None):
    """About page: history, how to help, how it works, roles, dynamic stats."""
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    stats = _main_mod._compute_landing_stats()

    return (
        Title("About Rhodesli"),
        Style("""
            .about-bg { background: linear-gradient(180deg, #1a1511 0%, #1e1a15 40%, #1a1511 100%); }
            .about-section { max-width: 48rem; margin: 0 auto; }
            .faq-q { cursor: pointer; }
            .faq-q:hover { color: #fbbf24; }
        """),
        Main(
            # Navigation bar
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(
                        A(
                            "Photos",
                            href="/photos",
                            cls="text-slate-300 hover:text-white text-sm font-medium transition-colors",
                        ),
                        A(
                            "People",
                            href="/people",
                            cls="text-slate-300 hover:text-white text-sm font-medium transition-colors",
                        ),
                        A(
                            "Timeline",
                            href=f"{nav_prefix}/timeline",
                            cls="text-slate-300 hover:text-white text-sm font-medium transition-colors",
                        ),
                        A("About", href="/about", cls="text-white text-sm font-medium"),
                        cls="hidden sm:flex items-center gap-6",
                    ),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            # Title
            Div(
                H1("About Rhodesli", cls="text-3xl font-serif font-bold text-amber-100 mb-2"),
                Div(cls="w-16 h-0.5 bg-amber-400/40 mb-6"),
                cls="max-w-3xl mx-auto px-6 pt-8",
            ),
            # The Community
            Div(
                H2("The Community", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "For over two thousand years, a Jewish community flourished on the island of Rhodes, "
                    "at the crossroads of the Aegean. After the expulsion from Spain in 1492, Sephardic families "
                    "settled in the walled quarter known as ",
                    Em("La Juderia"),
                    ", bringing with them the Ladino language, rabbinical traditions, and a vibrant culture of "
                    "merchants, craftsmen, and scholars. By the late 19th century, the community numbered several "
                    "thousand \u2014 the second largest religious group on the island. Six synagogues stood in "
                    "La Juderia, and the narrow arched streets rang with Judeo-Spanish songs and the bustle "
                    "of the ",
                    Em("cortijos"),
                    ", the shared courtyards where families gathered.",
                    cls="text-slate-300 leading-relaxed mb-4",
                ),
                cls="about-section px-6 mb-10",
            ),
            # The Diaspora
            Div(
                H2("The Diaspora", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "Beginning in the early 20th century, Rhodesli Jews emigrated in waves \u2014 first to the "
                    "nearby communities of Kos, Milas, and Bodrum, then further abroad as the Italian occupation "
                    "of 1912 and later the racial laws of 1938 uprooted families. Chain migration carried them "
                    "to specific cities worldwide: Seattle and Los Angeles on the American West Coast; Montgomery, "
                    "Atlanta, and New York in the East; Buenos Aires and S\u00e3o Paulo in South America; "
                    "Elizabethville and Salisbury in Central and Southern Africa; Alexandria and Cairo; and "
                    "communities in Havana, Asheville, Israel, Brussels, and Miami.",
                    cls="text-slate-300 leading-relaxed mb-4",
                ),
                P(
                    "The Holocaust of July 1944 devastated those who remained \u2014 of the 1,673 Jews deported "
                    "from Rhodes and Kos to Auschwitz, only 151 survived.",
                    cls="text-slate-300 leading-relaxed",
                ),
                cls="about-section px-6 mb-10",
            ),
            # The Project
            Div(
                H2("The Project", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "Rhodesli is a digital preservation project that uses machine learning to reconnect faces "
                    "and stories scattered across family collections worldwide. By combining AI face detection "
                    "with the living memory of community descendants, we are building a searchable archive that "
                    "bridges generations. Every identification you make \u2014 every name you recognize, every "
                    "story you share \u2014 helps preserve this heritage.",
                    cls="text-slate-300 leading-relaxed mb-4",
                ),
                P(
                    f"The archive currently contains {stats['photo_count']} photographs with "
                    f"{stats['total_faces']} faces detected by AI. {stats['named_count']} people have "
                    f"been positively identified so far, with {stats['needs_help']} faces still awaiting "
                    f"identification.",
                    cls="text-slate-400 leading-relaxed italic",
                ),
                cls="about-section px-6 mb-10",
            ),
            # How to Help
            Div(
                H2("How to Help", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("1", cls="text-amber-400 font-bold text-xl sm:text-lg mr-3"),
                        Div(
                            Span("Browse and identify", cls="text-slate-200 font-medium"),
                            P(
                                "Look through the photo archive. If you recognize a face, suggest a name. "
                                "Your family knowledge is irreplaceable.",
                                cls="text-slate-400 text-sm mt-1",
                            ),
                        ),
                        cls="flex items-start mb-4",
                    ),
                    Div(
                        Span("2", cls="text-amber-400 font-bold text-xl sm:text-lg mr-3"),
                        Div(
                            Span("Suggest names", cls="text-slate-200 font-medium"),
                            P(
                                "Use the 'Suggest Name' button on any unidentified face. Even partial "
                                "information helps \u2014 a last name, a family branch, or a generation.",
                                cls="text-slate-400 text-sm mt-1",
                            ),
                        ),
                        cls="flex items-start mb-4",
                    ),
                    Div(
                        Span("3", cls="text-amber-400 font-bold text-xl sm:text-lg mr-3"),
                        Div(
                            Span("Upload family photos", cls="text-slate-200 font-medium"),
                            P(
                                "If you have photographs from the Rhodesli community, upload them to grow "
                                "the archive. All uploads are reviewed before being added.",
                                cls="text-slate-400 text-sm mt-1",
                            ),
                        ),
                        cls="flex items-start mb-4",
                    ),
                    Div(
                        Span("4", cls="text-amber-400 font-bold text-xl sm:text-lg mr-3"),
                        Div(
                            Span("Add context", cls="text-slate-200 font-medium"),
                            P(
                                "Add dates, locations, occasions, and stories to photographs and identities. "
                                "Context turns a photograph into a piece of history.",
                                cls="text-slate-400 text-sm mt-1",
                            ),
                        ),
                        cls="flex items-start mb-4",
                    ),
                ),
                cls="about-section px-6 mb-10",
            ),
            # How It Works
            Div(
                H2("How It Works", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("Detect", cls="text-amber-400 font-semibold"),
                        P(
                            " \u2014 AI scans uploaded photographs and detects every face, creating a "
                            "mathematical fingerprint for each one.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                    Div(
                        Span("Group", cls="text-amber-400 font-semibold"),
                        P(
                            " \u2014 The system compares fingerprints across all photos and proposes "
                            "clusters: faces that likely belong to the same person.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                    Div(
                        Span("Verify", cls="text-amber-400 font-semibold"),
                        P(
                            " \u2014 Community members review these proposals. Confirmations strengthen "
                            "the system. Corrections help it learn. Nothing is permanent \u2014 every "
                            "decision can be undone.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                ),
                cls="about-section px-6 mb-10",
            ),
            # Roles
            Div(
                H2("Roles", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("Visitors", cls="text-slate-200 font-medium"),
                        P(
                            " can browse the entire archive freely without an account \u2014 every photograph, "
                            "every identified person, every face detection.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                    Div(
                        Span("Contributors", cls="text-slate-200 font-medium"),
                        P(
                            " can suggest names, upload photos, and add annotations. All suggestions "
                            "are reviewed by an admin before being applied.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                    Div(
                        Span("Admins", cls="text-slate-200 font-medium"),
                        P(
                            " review community suggestions, confirm identities, merge duplicates, "
                            "and manage the archive.",
                            cls="text-slate-400 text-sm inline",
                        ),
                        cls="mb-3",
                    ),
                ),
                cls="about-section px-6 mb-10",
            ),
            # FAQ
            Div(
                H2("Frequently Asked Questions", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        H3("Is this generative AI?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P(
                            "No. Rhodesli uses forensic face matching only \u2014 it compares mathematical "
                            "fingerprints of real faces. It never generates, invents, or fabricates anything.",
                            cls="text-slate-400 text-sm mb-4",
                        ),
                    ),
                    Div(
                        H3("Can I undo mistakes?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P(
                            "Yes. Confirmations, rejections, and merges can all be undone. The system keeps "
                            "full history. No data is ever permanently deleted.",
                            cls="text-slate-400 text-sm mb-4",
                        ),
                    ),
                    Div(
                        H3("Do I need an account to browse?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P(
                            "No. The entire archive is publicly browsable. An account is only needed to "
                            "submit suggestions, upload photos, or add annotations.",
                            cls="text-slate-400 text-sm mb-4",
                        ),
                    ),
                    Div(
                        H3("How can I contribute photos?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P(
                            "Sign up with an invite code, then use the Upload page to add photographs. "
                            "All uploads are reviewed before being added to the archive.",
                            cls="text-slate-400 text-sm mb-4",
                        ),
                    ),
                ),
                cls="about-section px-6 mb-10",
            ),
            # Footer
            Div(
                P(
                    "Built with care. No generative AI \u2014 only forensic face matching.",
                    cls="text-amber-100/30 text-sm sm:text-xs text-center",
                ),
                cls="about-section px-6 py-8 border-t border-amber-900/20",
            ),
            cls="min-h-screen about-bg",
        ),
    )


def _personalized_discovery_banner(
    interest_surnames: list[str], confirmed_list: list, crop_files: set, counts: dict, nav_prefix: str = ""
) -> Div:
    """Render a personalized discovery banner showing people matching user's interest surnames.

    Shown at top of Needs Help section when user selected surnames during onboarding.
    """
    from core.registry import _load_surname_variants

    variant_lookup = _load_surname_variants()

    # Expand surnames to include variants
    target_names = set()
    for surname in interest_surnames:
        target_names.add(surname.lower())
        variants = variant_lookup.get(surname.lower(), [])
        target_names.update(variants)

    # Find matching confirmed identities
    matches = []
    for identity in confirmed_list:
        name = (identity.get("name") or "").strip()
        if not name or name.startswith("Unidentified"):
            continue
        name_words = [w.lower() for w in name.split()]
        if any(w in target_names for w in name_words):
            face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            crop_url = _main_mod.resolve_face_image_url(face_ids[0], crop_files) if face_ids else None
            if crop_url:
                matches.append(
                    {
                        "name": name,
                        "crop_url": crop_url,
                        "identity_id": identity["identity_id"],
                    }
                )

    if not matches:
        return Div()  # Empty — no banner

    # Show up to 5 matching people as a horizontal strip
    people_thumbs = []
    for m in matches[:5]:
        people_thumbs.append(
            A(
                Div(
                    Img(
                        src=m["crop_url"],
                        alt=m["name"],
                        cls="w-12 h-12 rounded-full object-cover border-2 border-amber-400/50",
                    ),
                    Span(m["name"].split()[0], cls="text-sm sm:text-xs text-slate-400 mt-1 truncate w-14 text-center"),
                    cls="flex flex-col items-center",
                ),
                href=f"{nav_prefix}/?section=confirmed&current={m['identity_id']}",
                cls="hover:opacity-80 transition-opacity",
            )
        )

    surnames_display = " & ".join(interest_surnames[:3])
    more = f" +{len(interest_surnames) - 3}" if len(interest_surnames) > 3 else ""

    return Div(
        Div(
            Div(
                P(f"People from the {surnames_display}{more} families", cls="text-sm font-medium text-amber-200"),
                P(f"{len(matches)} identified \u2014 can you help find more?", cls="text-sm sm:text-xs text-slate-400"),
                cls="flex-1",
            ),
            Div(*people_thumbs, cls="flex gap-3"),
            cls="flex items-center gap-4",
        ),
        A(
            "View all \u2192",
            href=f"{nav_prefix}/?section=confirmed",
            cls="text-sm sm:text-xs text-amber-400 hover:text-amber-300 mt-2 inline-block",
        ),
        cls="bg-amber-900/20 border border-amber-700/30 rounded-lg p-4 mb-4",
    )


@rt("/")
def get(
    section: str = None,
    view: str = "focus",
    current: str = None,
    filter_source: str = "",
    filter_collection: str = "",
    sort_by: str = "newest",
    confirmed_filter: str = "all",
    filter: str = "",
    media_filter: str = "all",
    request=None,
    sess=None,
):
    """
    Landing page (no section) or Command Center (with section parameter).
    Public access -- anyone can view. Action buttons shown only to admins.
    Logged-in users with no section go to the triage dashboard.
    """
    # Track user activity for SWR bot guard (egress reduction)
    _main_mod.touch_user_activity()
    user = _main_mod.get_current_user(sess or {})

    # Read interest surnames from cookie for personalization
    interest_surnames = []
    if request:
        raw = request.cookies.get("rhodesli_interest_surnames", "")
        if raw:
            from urllib.parse import unquote

            interest_surnames = [s.strip() for s in unquote(raw).split(",") if s.strip()]

    # If no section specified:
    # - Logged-in users: go to inbox if items exist, otherwise Needs Help
    # - Anonymous users see the public landing page
    # Community-aware landing page (PRD-035)
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    community = getattr(request.state, "community", None) if request else None
    community_prefixed = getattr(request.state, "community_prefixed", False) if request else False

    if section is None:
        # Explicit archive entry: show that archive's landing for anonymous users.
        # Root "/" stays neutral and does not silently default to Rhodes.
        if community_prefixed and community is not None:
            user_is_admin_check = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
            if not user_is_admin_check:
                if community_slug == "rhodes":
                    stats = _main_mod._compute_landing_stats()
                    featured_photos = _main_mod._get_featured_photos(8)
                    return (
                        HttpHeader("Cache-Control", "public, s-maxage=120, max-age=60"),
                        _main_mod.landing_page(stats, featured_photos, nav_prefix=nav_prefix),
                    )
                return _community_landing_page(community, community_slug)

        if user is not None:
            # Smart redirect: skip empty inbox, go to Needs Help
            registry_check = _main_mod.load_registry()
            inbox_count = len(registry_check.list_identities(state=_main_mod.IdentityState.INBOX))
            proposed_count = len(registry_check.list_identities(state=_main_mod.IdentityState.PROPOSED))
            if inbox_count + proposed_count > 0:
                section = "to_review"
            else:
                section = "skipped"  # Needs Help — always has items to review
        else:
            return (
                HttpHeader("Cache-Control", "public, s-maxage=120, max-age=60"),
                _platform_root_page(auth_enabled=_main_mod.is_auth_enabled(), sess=sess),
            )

    user_is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True

    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Fetch all identity states
    inbox = registry.list_identities(state=_main_mod.IdentityState.INBOX)
    proposed = registry.list_identities(state=_main_mod.IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
    skipped_list = registry.list_identities(state=_main_mod.IdentityState.SKIPPED)
    rejected = registry.list_identities(state=_main_mod.IdentityState.REJECTED)
    contested = registry.list_identities(state=_main_mod.IdentityState.CONTESTED)

    # Apply community filter for non-Rhodes communities (PRD-035)
    community_identity_ids = _main_mod._get_community_identity_ids(community)
    if community_identity_ids is not None:
        inbox = [i for i in inbox if i.get("identity_id") in community_identity_ids]
        proposed = [i for i in proposed if i.get("identity_id") in community_identity_ids]
        confirmed_list = [i for i in confirmed_list if i.get("identity_id") in community_identity_ids]
        skipped_list = [i for i in skipped_list if i.get("identity_id") in community_identity_ids]
        rejected = [i for i in rejected if i.get("identity_id") in community_identity_ids]
        contested = [i for i in contested if i.get("identity_id") in community_identity_ids]

    # Combine into 4 workflow sections
    to_review = inbox + proposed  # Items needing attention
    dismissed = rejected + contested  # Items explicitly dismissed

    # Sort each section
    to_review.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    confirmed_list.sort(key=lambda x: (x.get("name") or "", x.get("updated_at", "")))
    skipped_list.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    dismissed.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    # Canonical sidebar counts (single source of truth)
    counts = _main_mod._compute_sidebar_counts(registry, community=community)

    # Validate section parameter
    valid_sections = ("to_review", "confirmed", "skipped", "rejected", "photos")
    if section not in valid_sections:
        section = "to_review"

    if confirmed_filter not in {"all", "tree_unlinked", "tree_linked", "needs_name"}:
        confirmed_filter = "all"

    # Validate view parameter
    if view not in ("focus", "browse", "match"):
        view = "focus"

    # Personalized discovery banner when user has interest surnames
    discovery_banner = None
    if interest_surnames and section == "skipped":
        discovery_banner = _main_mod._personalized_discovery_banner(
            interest_surnames, confirmed_list, crop_files, counts, nav_prefix=nav_prefix
        )

    # Render the appropriate section
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    if section == "to_review":
        main_content = _main_mod.render_to_review_section(
            to_review,
            crop_files,
            view,
            counts,
            current_id=current,
            is_admin=user_is_admin,
            sort_by=sort_by,
            triage_filter=filter,
            nav_prefix=nav_prefix,
        )
    elif section == "confirmed":
        main_content = _main_mod.render_confirmed_section(
            confirmed_list,
            crop_files,
            counts,
            is_admin=user_is_admin,
            sort_by=sort_by,
            nav_prefix=nav_prefix,
            confirmed_filter=confirmed_filter,
        )
    elif section == "skipped":
        skipped_view = view if view in ("focus", "browse") else "focus"
        main_content = _main_mod.render_skipped_section(
            skipped_list,
            crop_files,
            counts,
            is_admin=user_is_admin,
            view_mode=skipped_view,
            current_id=current,
            nav_prefix=nav_prefix,
        )
    elif section == "photos":
        main_content = _main_mod.render_photos_section(
            counts,
            registry,
            crop_files,
            filter_source,
            sort_by,
            filter_collection,
            media_filter,
            community=community,
            nav_prefix=nav_prefix,
        )
    else:  # rejected
        main_content = _main_mod.render_rejected_section(
            dismissed, crop_files, counts, is_admin=user_is_admin, nav_prefix=nav_prefix
        )

    # Prepend discovery banner to main content if present
    if discovery_banner:
        main_content = Div(discovery_banner, main_content)

    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
            overflow-x: hidden;
        }
        body {
            background-color: #0f172a;
        }
        @keyframes fade-in {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slide-out-right {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(100px); }
        }
        @keyframes card-enter {
            from { opacity: 0; transform: scale(0.97) translateY(8px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes card-exit {
            from { opacity: 1; transform: scale(1); }
            to { opacity: 0; transform: scale(0.97) translateY(-8px); }
        }
        .animate-fade-in {
            animation: fade-in 0.3s ease-out;
        }
        .animate-slide-out {
            animation: slide-out-right 0.3s ease-in forwards;
        }
        .animate-card-enter {
            animation: card-enter 0.35s ease-out;
        }
        /* HTMX swap transitions for focus card */
        #focus-card {
            animation: card-enter 0.35s ease-out;
        }
        /* Match mode pair transition */
        .match-pair {
            animation: card-enter 0.35s ease-out;
        }
        .htmx-indicator {
            display: none;
        }
        .htmx-request .htmx-indicator,
        .htmx-request.htmx-indicator {
            display: inline;
        }
        /* Block-level indicators (compare/estimate spinners) */
        div.htmx-request.htmx-indicator,
        .htmx-request div.htmx-indicator {
            display: block;
        }
        /* Disable submit button while processing */
        form.htmx-request button[type="submit"] {
            opacity: 0.5;
            pointer-events: none;
        }
        /* Keyboard focus states */
        button:focus-visible {
            outline: 2px solid #0ea5e9;
            outline-offset: 2px;
        }
        /* Card state transitions */
        .identity-card {
            transition: all 0.2s ease-out;
        }
        .identity-card:hover {
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }
        /* Darkroom theme - monospace for data */
        .font-data {
            font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
        }
        /* Archival display font — serif for headings (DD-001) */
        .font-display {
            font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
        }
        /* Archival face card — warm tones evoking physical photographs (DD-002) */
        .face-card-archival {
            background: linear-gradient(145deg, #2a241e 0%, #1e1a15 100%);
            border: 1px solid #3d3428;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(61, 52, 40, 0.2);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        .face-card-archival:hover {
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 6px rgba(61, 52, 40, 0.3);
            transform: translateY(-1px);
        }
        /* Archival identity card — warm border with photograph feel (DD-002) */
        .identity-card-archival {
            background: linear-gradient(180deg, #1e1a15 0%, #1a1714 100%);
            border: 1px solid #3d3428;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
        }
        .identity-card-archival:hover {
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(61, 52, 40, 0.4);
        }
        /* Expansion panel for inline Find Similar (AD-194) */
        .expansion-panel:empty {
            display: none;
        }
        .expansion-panel:not(:empty) {
            grid-column: 1 / -1;
            padding: 1.25rem;
            background: rgba(30, 26, 21, 0.95);
            border: 1px solid rgba(61, 52, 40, 0.5);
            border-radius: 0.5rem;
            animation: panel-fade-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        @keyframes panel-fade-in {
            from { opacity: 0; transform: translateY(-8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .expansion-panel .similar-faces {
            display: flex;
            gap: 1rem;
            overflow-x: auto;
            padding: 0.5rem 0;
            scroll-snap-type: x mandatory;
            -webkit-overflow-scrolling: touch;
        }
        .expansion-panel .similar-face-tile {
            flex: 0 0 auto;
            width: 160px;
            scroll-snap-align: start;
        }
        .expansion-panel .panel-close {
            cursor: pointer;
            opacity: 0.6;
            transition: opacity 0.2s;
        }
        .expansion-panel .panel-close:hover {
            opacity: 1;
        }
        /* Card highlight when Find Similar is active */
        .identity-card {
            transition: transform 0.3s ease, border-color 0.3s ease;
        }
        .identity-card.find-similar-active {
            border: 2px solid rgba(212, 165, 116, 0.5);
            transform: scale(1.02);
            z-index: 1;
        }
        /* Visual modernization — hover states, transitions, feedback */
        .identity-card-archival,
        .face-card-archival {
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        button:active, a.btn:active, [data-action]:active {
            transform: scale(0.97);
            transition: transform 0.1s ease;
        }
        /* HTMX loading indicator */
        .htmx-request .htmx-indicator {
            opacity: 1;
        }
        .htmx-indicator {
            opacity: 0;
            transition: opacity 0.2s ease-in;
        }
        /* Smooth focus ring for keyboard navigation */
        button:focus-visible, a:focus-visible {
            outline: 2px solid rgba(99, 102, 241, 0.7);
            outline-offset: 2px;
            border-radius: 4px;
        }
        /* Photo card frame — evoking a mounted print (DD-002) */
        .photo-card-frame {
            background: #2a241e;
            border: 1px solid #3d3428;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3), inset 0 0 0 1px rgba(245, 230, 211, 0.03);
        }
        /* Collapsible sidebar */
        .sidebar-container {
            width: 15rem;
            transition: width 0.2s ease, transform 0.3s ease;
        }
        .sidebar-container.collapsed {
            width: 3.5rem;
        }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results {
            display: none;
        }
        .sidebar-container.collapsed .sidebar-nav-item {
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
        }
        .sidebar-container.collapsed .sidebar-icon {
            margin: 0;
        }
        .sidebar-container.collapsed .sidebar-chevron {
            transform: rotate(180deg);
        }
        .sidebar-container.collapsed .sidebar-collapse-btn {
            margin: 0 auto;
        }
        .sidebar-search-results:not(:empty) {
            position: absolute;
            left: 0.75rem;
            right: 0.75rem;
            top: 100%;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            max-height: 300px;
            overflow-y: auto;
            z-index: 50;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        /* Mobile responsive sidebar */
        @media (max-width: 767px) {
            #sidebar {
                width: 15rem !important;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
            }
            #sidebar.open {
                transform: translateX(0);
            }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content {
                margin-left: 0 !important;
            }
        }
        @media (min-width: 768px) {
            #sidebar { transform: translateX(0); }
        }
        @media (min-width: 1024px) {
            .main-content {
                margin-left: 15rem;
                transition: margin-left 0.2s ease;
            }
            .main-content.sidebar-collapsed {
                margin-left: 3.5rem;
            }
        }
    """)

    # Mobile header (shown only on small screens)
    _main_mod.mobile_header = Div(
        Button(
            # Hamburger icon
            Svg(
                Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
            ),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center",
            aria_label="Toggle sidebar menu",
        ),
        Span("Rhodesli", cls="text-xl sm:text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30",
    )

    # Sidebar overlay for mobile
    sidebar_overlay = Div(
        onclick="closeSidebar()", cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )

    # Sidebar toggle script (mobile open/close + desktop collapse/expand)
    sidebar_script = Script("""
        // Mobile: open/close sidebar
        function toggleSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.toggle('open');
            sb.classList.toggle('-translate-x-full');
            ov.classList.toggle('hidden');
        }
        function closeSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.remove('open');
            sb.classList.add('-translate-x-full');
            ov.classList.add('hidden');
        }
        // Desktop: collapse/expand sidebar
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        // Restore sidebar state from localStorage on page load
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
            // Close search results when clicking outside
            document.addEventListener('click', function(e) {
                var search = document.querySelector('.sidebar-search');
                var results = document.getElementById('sidebar-search-results');
                if (search && results && !search.contains(e.target)) {
                    results.innerHTML = '';
                }
            });
        })();
    """)

    # Mobile bottom tab navigation (lg:hidden)
    # COMMUNITY-008: Use community prefix so links stay within the community context
    _nav_prefix = _main_mod.community_url_prefix(community_slug)
    mobile_tabs = Nav(
        A(
            Svg(
                Path(d="M4 6h16M4 10h16M4 14h16M4 18h16"),
                cls="w-5 h-5",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
                stroke_width="2",
                stroke_linecap="round",
            ),
            Span("Photos", cls="text-[10px]"),
            href=f"{_nav_prefix}/?section=photos",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
            f"{'text-indigo-400' if section == 'photos' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"),
                cls="w-5 h-5",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
                stroke_width="2",
                stroke_linecap="round",
                stroke_linejoin="round",
            ),
            Span("People", cls="text-[10px]"),
            href=f"{_nav_prefix}/?section=confirmed&view=browse",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
            f"{'text-emerald-400' if section == 'confirmed' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(
                    d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                ),
                cls="w-5 h-5",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
                stroke_width="2",
                stroke_linecap="round",
                stroke_linejoin="round",
            ),
            Span("Matches", cls="text-[10px]"),
            href=f"{_nav_prefix}/?section=to_review&view=focus",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
            f"{'text-amber-400' if section == 'to_review' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"),
                cls="w-5 h-5",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
                stroke_width="2",
                stroke_linecap="round",
                stroke_linejoin="round",
            ),
            Span("Search", cls="text-[10px]"),
            href=f"{_nav_prefix}/?section=confirmed&view=browse",
            cls="flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] text-slate-400 hover:text-slate-200",
            onclick="toggleSidebar(); setTimeout(function() { var s = document.querySelector('#sidebar input[type=search]'); if (s) s.focus(); }, 300); return false;",
        ),
        cls="fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 flex items-center justify-around py-1 z-40 lg:hidden",
        id="mobile-tabs",
    )

    return (
        Title("Rhodesli Identity System"),
        style,
        Div(
            # Toast container for notifications
            _main_mod.toast_container(),
            # Mobile header
            _main_mod.mobile_header,
            # Sidebar overlay (mobile backdrop)
            sidebar_overlay,
            # Sidebar (fixed)
            _main_mod.sidebar(counts, section, user=user, community_slug=community_slug, community=community),
            # Main content (offset for sidebar, bottom padding for mobile tabs)
            Main(
                # First-time welcome banner (non-blocking, dismissible)
                _main_mod._welcome_banner() if not user else None,
                # Admin dashboard banner (only for admins)
                _main_mod._admin_dashboard_banner(counts, section) if user_is_admin else None,
                Div(main_content, cls="max-w-6xl mx-auto px-4 sm:px-8 py-6 pb-20 lg:pb-6"),
                cls="main-content min-h-screen overflow-x-hidden ui99-workstation",
            ),
            # Mobile bottom tabs
            mobile_tabs,
            # Photo modal (unified lightbox for all photo viewing)
            _main_mod.photo_modal(),
            # Side-by-side comparison modal for merge evaluation
            _main_mod.compare_modal(),
            # Login modal (shown when unauthenticated user triggers protected action)
            _main_mod.login_modal(),
            # Guest-or-login modal container (swapped in by annotation submit)
            Div(id="guest-or-login-modal"),
            # Styled confirmation modal (replaces native browser confirm())
            _main_mod.confirm_modal(),
            sidebar_script,
            # Client-side instant name filter with fuzzy matching (FE-030/FE-031/FE-033)
            Script("""
            (function() {
                // Levenshtein edit distance for fuzzy name matching
                function levenshtein(a, b) {
                    if (a.length < b.length) return levenshtein(b, a);
                    if (b.length === 0) return a.length;
                    var prev = [];
                    for (var j = 0; j <= b.length; j++) prev[j] = j;
                    for (var i = 1; i <= a.length; i++) {
                        var curr = [i];
                        for (var j = 1; j <= b.length; j++) {
                            var cost = a[i-1] === b[j-1] ? 0 : 1;
                            curr[j] = Math.min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost);
                        }
                        prev = curr;
                    }
                    return prev[b.length];
                }
                // Fuzzy match: exact substring OR Levenshtein distance <= threshold per word
                function fuzzyMatch(query, name) {
                    if (!query) return true;
                    if (name.indexOf(query) !== -1) return true;
                    var words = name.split(/\\s+/);
                    var maxDist = query.length <= 8 ? 2 : 3;
                    for (var w = 0; w < words.length; w++) {
                        if (levenshtein(query, words[w]) <= maxDist) return true;
                    }
                    return false;
                }
                var filterTimer = null;
                function sidebarFilterCards(query) {
                    // Filter both standalone cards and wrapper divs (Needs Help has card+hint wrappers)
                    var cards = document.querySelectorAll('.identity-card, .identity-card-wrapper');
                    var q = (query || '').toLowerCase().trim();
                    for (var i = 0; i < cards.length; i++) {
                        var name = cards[i].getAttribute('data-name') || '';
                        if (fuzzyMatch(q, name)) {
                            cards[i].style.display = '';
                        } else {
                            cards[i].style.display = 'none';
                        }
                    }
                }
                var input = document.getElementById('sidebar-search-input');
                if (input) {
                    input.addEventListener('input', function() {
                        var val = this.value;
                        clearTimeout(filterTimer);
                        filterTimer = setTimeout(function() {
                            sidebarFilterCards(val);
                        }, 150);
                    });
                }
                // Expose for testing
                window.sidebarFilterCards = sidebarFilterCards;
            })();
        """),
            # Hash-based scroll + highlight for search result navigation
            Script("""
            (function() {
                if (window.location.hash) {
                    var target = document.querySelector(window.location.hash);
                    if (target) {
                        target.scrollIntoView({behavior: 'smooth', block: 'center'});
                        target.classList.add('ring-2', 'ring-blue-400');
                        setTimeout(function() {
                            target.classList.remove('ring-2', 'ring-blue-400');
                        }, 2000);
                    }
                }
            })();
        """),
            # Global share utility functions (used by share buttons on all pages)
            Script("""
            function _sharePhotoUrl(url, shareTitle, shareText) {
                // Always copy to clipboard first (desktop-friendly).
                // On mobile, also offer native share sheet after copying.
                _copyAndToast(url);
                var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                if (isMobile && navigator.share) {
                    var shareData = { url: url };
                    if (shareTitle) shareData.title = shareTitle;
                    if (shareText) shareData.text = shareText;
                    navigator.share(shareData).catch(function() {});
                }
            }
            function _copyAndToast(url) {
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(function() {
                        _showShareToast('Link copied!');
                    }).catch(function() { _showShareToast('Could not copy link'); });
                } else {
                    var input = document.createElement('input');
                    input.value = url;
                    document.body.appendChild(input);
                    input.select();
                    document.execCommand('copy');
                    document.body.removeChild(input);
                    _showShareToast('Link copied!');
                }
            }
            function _showShareToast(message) {
                var existing = document.getElementById('share-toast');
                if (existing) existing.remove();
                var toast = document.createElement('div');
                toast.id = 'share-toast';
                toast.textContent = message;
                toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
                document.body.appendChild(toast);
                setTimeout(function() { toast.style.opacity = '0'; }, 2000);
                setTimeout(function() { toast.remove(); }, 2500);
            }
        """),
            # Global event delegation for lightbox/photo navigation (BUG-001 fix).
            # ONE listener on document handles all nav clicks and keyboard events.
            # This never needs rebinding because it's on document, not swapped DOM.
            Script("""
            // --- Global event delegation for photo/lightbox navigation ---
            // Click delegation: dispatch based on data-action attribute
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('[data-action]');
                if (!btn) return;
                var action = btn.getAttribute('data-action');

                // Share photo/page (used across all surfaces)
                if (action === 'share-photo') {
                    var url = btn.getAttribute('data-share-url') || '';
                    if (url && !url.startsWith('http')) {
                        url = window.location.origin + url;
                    }
                    var shareTitle = btn.getAttribute('data-share-title') || '';
                    var shareText = btn.getAttribute('data-share-text') || '';
                    _sharePhotoUrl(url || window.location.href, shareTitle, shareText);
                    return;
                }

                // Toggle face overlay visibility
                if (action === 'toggle-face-overlays') {
                    var overlays = document.querySelectorAll('.face-overlay');
                    var legend = document.getElementById('face-overlay-legend');
                    var isHidden = btn.getAttribute('data-overlays-hidden') === 'true';
                    overlays.forEach(function(el) {
                        el.style.display = isHidden ? '' : 'none';
                    });
                    if (legend) legend.style.display = isHidden ? '' : 'none';
                    btn.setAttribute('data-overlays-hidden', isHidden ? 'false' : 'true');
                    btn.textContent = isHidden ? 'Hide Faces' : 'Show Faces';
                    return;
                }

                // Photo modal prev/next (Photos grid browsing)
                if (action === 'photo-nav-prev' || action === 'photo-nav-next') {
                    e.preventDefault();
                    var navUrl = btn.getAttribute('data-nav-url');
                    if (navUrl) {
                        htmx.ajax('GET', navUrl, {target:'#photo-modal-content', swap:'innerHTML'});
                    } else {
                        var idx = parseInt(btn.getAttribute('data-nav-idx'), 10);
                        if (typeof photoNavTo === 'function' && !isNaN(idx)) {
                            photoNavTo(idx);
                        }
                    }
                    return;
                }

                // Identity photo lightbox prev/next — HTMX handles these via
                // hx-get. data-action is for keyboard delegation below.

                // Face cycling on identity cards (prev/next arrows)
                if (action === 'face-cycle-prev' || action === 'face-cycle-next') {
                    e.preventDefault();
                    e.stopPropagation();
                    var card = btn.closest('[data-cycle-urls]');
                    if (!card) return;
                    var urls = card.getAttribute('data-cycle-urls').split('|');
                    var idx = parseInt(card.getAttribute('data-cycle-index') || '0', 10);
                    if (action === 'face-cycle-prev') {
                        idx = (idx - 1 + urls.length) % urls.length;
                    } else {
                        idx = (idx + 1) % urls.length;
                    }
                    card.setAttribute('data-cycle-index', idx);
                    var img = card.querySelector('[data-cycle-img]');
                    if (img) img.src = urls[idx];
                    // Update dot indicators
                    var dots = card.querySelectorAll('[data-dot-index]');
                    dots.forEach(function(dot) {
                        var di = parseInt(dot.getAttribute('data-dot-index'), 10);
                        dot.className = 'w-1.5 h-1.5 rounded-full transition-all duration-200 '
                            + (di === idx ? 'bg-white' : 'bg-white/40');
                    });
                    return;
                }
            });

            // Keyboard delegation: one global listener, reads DOM for current state.
            // Priority: modals first, then suppress in text fields, then mode shortcuts.

            // Undo stack: stores last 10 actions for Z-key undo
            if (!window._undoStack) window._undoStack = [];

            // Capture undo data before HTMX actions fire
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('[data-undo-type]');
                if (btn) {
                    var undoInfo = {
                        type: btn.getAttribute('data-undo-type'),
                        url: btn.getAttribute('data-undo-url') || '',
                        identity: btn.getAttribute('data-undo-identity') || '',
                        ts: Date.now()
                    };
                    window._undoStack.push(undoInfo);
                    if (window._undoStack.length > 10) window._undoStack.shift();
                }
            }, true);

            document.addEventListener('keydown', function(e) {
                // --- Modal navigation (highest priority) ---
                // Unified photo modal (handles both photo grid browsing and identity photo browsing)
                var photoModal = document.getElementById('photo-modal');
                if (photoModal && !photoModal.classList.contains('hidden')) {
                    if (e.key === 'ArrowLeft') {
                        // Try photo grid nav first, then identity lightbox nav
                        var prev = document.querySelector('[data-action="photo-nav-prev"]');
                        if (prev) { prev.click(); e.preventDefault(); }
                        else {
                            var lbPrev = document.querySelector('[data-action="lightbox-prev"]');
                            if (lbPrev) { lbPrev.click(); e.preventDefault(); }
                            else if (typeof photoNavTo === 'function' && window._photoNavIdx > 0) {
                                photoNavTo(window._photoNavIdx - 1); e.preventDefault();
                            }
                        }
                    } else if (e.key === 'ArrowRight') {
                        var next = document.querySelector('[data-action="photo-nav-next"]');
                        if (next) { next.click(); e.preventDefault(); }
                        else {
                            var lbNext = document.querySelector('[data-action="lightbox-next"]');
                            if (lbNext) { lbNext.click(); e.preventDefault(); }
                            else if (typeof photoNavTo === 'function' && window._photoNavIdx < (window._photoNavIds||[]).length - 1) {
                                photoNavTo(window._photoNavIdx + 1); e.preventDefault();
                            }
                        }
                    } else if (e.key === 'Escape') {
                        photoModal.classList.add('hidden'); e.preventDefault();
                    }
                    return;
                }

                // --- Suppress shortcuts when typing in INPUT or TEXTAREA ---
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

                // --- Ignore when modifier keys are held (Cmd+R, Ctrl+S, etc.) ---
                if (e.metaKey || e.ctrlKey || e.altKey) return;

                // --- Z = Undo last action (works in all focus modes) ---
                if (e.key === 'z' || e.key === 'Z') {
                    e.preventDefault();
                    if (!window._undoStack || window._undoStack.length === 0) return;
                    var last = window._undoStack.pop();
                    if (last.type === 'skip' && last.url) {
                        // Session 153: inline skip pill provides a restore URL. POST
                        // to it and refresh the page so the overlay shows INBOX state.
                        fetch(last.url, {method: 'POST', headers: {'HX-Request': 'true'}}).then(function(r) {
                            if (r.ok) { window.location.reload(); }
                        });
                    } else if (last.type === 'skip') {
                        // Legacy skip (skipped focus mode): no restore URL, navigate
                        // back to the skipped identity so admin can re-review.
                        window.location.href = '/?section=skipped&view=focus&current=' + last.identity;
                    } else if (last.url) {
                        // Merge/reject undo: POST to undo endpoint, then reload focus on that identity
                        fetch(last.url, {method: 'POST', headers: {'HX-Request': 'true'}}).then(function() {
                            window.location.href = '/?section=skipped&view=focus&current=' + last.identity;
                        });
                    }
                    return;
                }

                // --- Match mode shortcuts: Y=Same, N=Different, S=Skip ---
                var matchBtn = null;
                if (e.key === 'y' || e.key === 'Y') matchBtn = document.getElementById('match-btn-same');
                else if (e.key === 'n' || e.key === 'N') matchBtn = document.getElementById('match-btn-diff');
                else if (e.key === 's' || e.key === 'S') matchBtn = document.getElementById('match-btn-skip');
                if (matchBtn) { e.preventDefault(); matchBtn.click(); return; }

                // --- Focus mode shortcuts ---
                // Skipped focus mode: Y=Same Person, N=Not Same, Enter=I Know Them, S=Skip, Z=Undo
                // Inbox focus mode: C=Confirm, S=Skip, R=Reject, F=Find Similar
                var focusBtn = null;
                var isSkippedFocus = document.querySelector('[data-focus-mode="skipped"]');
                if (isSkippedFocus) {
                    if (e.key === 'y' || e.key === 'Y') focusBtn = document.getElementById('focus-btn-confirm');
                    else if (e.key === 'n' || e.key === 'N') focusBtn = document.getElementById('focus-btn-reject');
                    else if (e.key === 'Enter') focusBtn = document.getElementById('focus-btn-name');
                    else if (e.key === 's' || e.key === 'S') focusBtn = document.getElementById('focus-btn-skip');
                } else {
                    if (e.key === 'c' || e.key === 'C') focusBtn = document.getElementById('focus-btn-confirm');
                    else if (e.key === 's' || e.key === 'S') focusBtn = document.getElementById('focus-btn-skip');
                    else if (e.key === 'r' || e.key === 'R') focusBtn = document.getElementById('focus-btn-reject');
                    else if (e.key === 'f' || e.key === 'F') focusBtn = document.getElementById('focus-btn-similar');
                }
                if (focusBtn) { e.preventDefault(); focusBtn.click(); return; }
            });
        """),
            # Community-aware link rewriting: ensures internal navigation stays within community context
            Script(f"""
            (function() {{
                var communityPrefix = '{_main_mod.community_url_prefix(community_slug)}';
                if (!communityPrefix) return;  // Rhodes/default — no rewriting needed

                function rewriteLinks(root) {{
                    root.querySelectorAll('a[href^="/?section="], a[href^="/admin/"], a[href^="/person/"], a[href^="/photo/"], a[href^="/help"]').forEach(function(a) {{
                        var h = a.getAttribute('href');
                        if (h && !h.startsWith(communityPrefix) && !h.startsWith('/tools/') && !h.startsWith('/static/')) {{
                            a.setAttribute('href', communityPrefix + h);
                        }}
                    }});
                    // Also rewrite hx-get and hx-post URLs that bypass community middleware
                    root.querySelectorAll('[hx-get^="/api/"], [hx-post^="/api/"]').forEach(function(el) {{
                        ['hx-get', 'hx-post'].forEach(function(attr) {{
                            var v = el.getAttribute(attr);
                            if (v && v.startsWith('/api/') && !v.startsWith(communityPrefix)) {{
                                el.setAttribute(attr, communityPrefix + v);
                            }}
                        }});
                    }});
                }}

                // Rewrite on initial load
                rewriteLinks(document.body);

                // Rewrite after HTMX swaps (new content may have bare URLs)
                document.body.addEventListener('htmx:afterSwap', function(e) {{
                    if (e.detail && e.detail.target) rewriteLinks(e.detail.target);
                }});
            }})();
            """)
            if community_slug and community_slug != "rhodes"
            else None,
            cls="h-full",
        ),
    )


# =============================================================================
# ROUTES - PHOTO CONTEXT NAVIGATOR (LIGHT TABLE)
# =============================================================================


@rt("/api/photo/{photo_id}")
def get(photo_id: str):
    """
    Get photo metadata with face bounding boxes.

    Returns JSON with:
    - photo_url: Static path to the photo
    - image_width, image_height: Original dimensions
    - faces: List of face objects with bbox, face_id, display_name, identity_id
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return JSONResponse(
            {"error": "Photo not found", "photo_id": photo_id},
            status_code=404,
        )

    # Get image dimensions for face overlay positioning
    width, height = _main_mod.get_photo_dimensions(photo["filename"])
    if width == 0 or height == 0:
        return JSONResponse(
            {"error": "Could not read photo dimensions", "photo_id": photo_id},
            status_code=404,
        )

    # Build face list with identity information
    registry = _main_mod.load_registry()
    faces = []

    for face_data in photo["faces"]:
        face_id = face_data["face_id"]
        if not _main_mod.has_displayable_face_bbox(face_data):
            continue
        bbox = face_data["bbox"]  # [x1, y1, x2, y2]

        # Find identity for this face
        identity = _main_mod.get_identity_for_face(registry, face_id)

        # Convert bbox from [x1, y1, x2, y2] to {x, y, w, h}
        x1, y1, x2, y2 = bbox
        # UI BOUNDARY: sanitize display_name for safe JSON rendering
        raw_display_name = identity.get("name", "Unidentified") if identity else "Unidentified"
        face_obj = {
            "face_id": face_id,
            "bbox": {
                "x": x1,
                "y": y1,
                "w": x2 - x1,
                "h": y2 - y1,
            },
            "display_name": ensure_utf8_display(raw_display_name),
            "identity_id": identity["identity_id"] if identity else None,
            "is_selected": False,
        }
        faces.append(face_obj)

    return JSONResponse(
        {
            "photo_url": photo_url(photo["filename"]),
            "image_width": width,
            "image_height": height,
            "faces": faces,
        }
    )


@rt("/api/photo/{photo_id}/collection")
def post(photo_id: str, sess, collection: str = ""):
    """
    Update a photo's collection (classification) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    registry_photo_id = _main_mod.resolve_photo_registry_photo_id(photo_id, photo_reg)
    photo_path = photo_reg.get_photo_path(registry_photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    previous_collection = (_main_mod.get_photo_metadata(photo_id) or {}).get("collection", "")
    updated_collection = collection.strip()
    photo_reg.set_collection(registry_photo_id, updated_collection)
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    _main_mod.log_user_action(
        "UPDATE_PHOTO_COLLECTION",
        photo_id=photo_id,
        previous_collection=previous_collection or "",
        new_collection=updated_collection or "",
        admin=user.email if user else "admin",
    )
    return Div(
        Span(f"Collection updated to: {updated_collection or '(none)'}", cls="text-sm text-emerald-400"),
        id=f"collection-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source")
def post(photo_id: str, sess, source: str = ""):
    """
    Update a photo's source (provenance/origin) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    registry_photo_id = _main_mod.resolve_photo_registry_photo_id(photo_id, photo_reg)
    photo_path = photo_reg.get_photo_path(registry_photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    previous_source = (_main_mod.get_photo_metadata(photo_id) or {}).get("source", "")
    updated_source = source.strip()
    photo_reg.set_source(registry_photo_id, updated_source)
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    _main_mod.log_user_action(
        "UPDATE_PHOTO_SOURCE",
        photo_id=photo_id,
        previous_source=previous_source or "",
        new_source=updated_source or "",
        admin=user.email if user else "admin",
    )
    return Div(
        Span(f"Source updated to: {updated_source or '(none)'}", cls="text-sm text-emerald-400"),
        id=f"source-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source-url")
def post(photo_id: str, sess, source_url: str = ""):
    """
    Update a photo's source URL (citation link).

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    registry_photo_id = _main_mod.resolve_photo_registry_photo_id(photo_id, photo_reg)
    photo_path = photo_reg.get_photo_path(registry_photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    previous_source_url = (_main_mod.get_photo_metadata(photo_id) or {}).get("source_url", "")
    updated_source_url = source_url.strip()
    photo_reg.set_source_url(registry_photo_id, updated_source_url)
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    _main_mod.log_user_action(
        "UPDATE_PHOTO_SOURCE_URL",
        photo_id=photo_id,
        previous_source_url=previous_source_url or "",
        new_source_url=updated_source_url or "",
        admin=user.email if user else "admin",
    )
    if updated_source_url:
        return Div(
            Span("Source URL: ", cls="text-slate-500 text-sm"),
            A(
                updated_source_url,
                href=updated_source_url,
                target="_blank",
                rel="noopener",
                cls="text-indigo-400 hover:text-indigo-300 underline text-sm",
            ),
            id=f"source-url-status-{photo_id}",
        )
    return Div(
        Span("Source URL cleared", cls="text-sm text-emerald-400"),
        id=f"source-url-status-{photo_id}",
    )


def _load_corrections_log() -> dict:
    """Load corrections log. Creates file if it doesn't exist."""
    corrections_path = _main_mod.data_path / "corrections_log.json"
    if not corrections_path.exists():
        return {"schema_version": 1, "corrections": []}
    try:
        with open(corrections_path) as f:
            return json.load(f)
    except Exception:
        return {"schema_version": 1, "corrections": []}


def _save_corrections_log(data: dict):
    """Save corrections log atomically."""
    corrections_path = _main_mod.data_path / "corrections_log.json"
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(_main_mod.data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(corrections_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _load_photo_bytes(photo_id: str, filename: str) -> bytes | None:
    """Load photo image bytes from local filesystem or R2."""
    # Try local filesystem first
    local_path = Path("raw_photos") / filename
    if local_path.exists():
        return local_path.read_bytes()

    # Try R2
    if _main_mod.storage.is_r2_mode():
        try:
            import urllib.request

            url = _main_mod.storage.get_photo_url(filename)
            req = urllib.request.Request(url, headers={"User-Agent": "Rhodesli/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as e:
            logging.warning(f"Failed to load photo from R2: {e}")

    return None


def _normalize_gallery_sort(sort_by: str | None) -> str:
    """Return a supported person-gallery sort key."""
    if sort_by in {"date_asc", "date_desc", "uploaded_desc", "uploaded_asc"}:
        return sort_by
    return "date_asc"


def _parse_gallery_year(value) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _parse_gallery_uploaded_timestamp(value) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _build_gallery_sort_meta(photo_id: str, photo_meta: dict | None, date_labels: dict) -> dict:
    """Build a stable sort meta record for person-gallery photos."""
    photo_meta = photo_meta or {}
    year = _parse_gallery_year((date_labels.get(photo_id) or {}).get("best_year_estimate"))
    if year is None:
        year = _parse_gallery_year(photo_meta.get("date_taken"))
    uploaded_ts = _parse_gallery_uploaded_timestamp(photo_meta.get("created_at") or photo_meta.get("updated_at"))
    return {
        "year": year,
        "has_year": year is not None,
        "uploaded_ts": uploaded_ts,
        "has_uploaded_ts": uploaded_ts is not None,
    }


def _gallery_sort_key(sort_by: str, sort_meta: dict, stable: str):
    """Sort key shared by person/photo gallery views."""
    year = sort_meta["year"] if sort_meta["has_year"] else 0
    uploaded_ts = sort_meta["uploaded_ts"] if sort_meta["has_uploaded_ts"] else 0.0
    if sort_by == "date_desc":
        return (0 if sort_meta["has_year"] else 1, -year, -uploaded_ts, stable)
    if sort_by == "uploaded_desc":
        return (
            0 if sort_meta["has_uploaded_ts"] else 1,
            -uploaded_ts,
            year if sort_meta["has_year"] else 9999,
            stable,
        )
    if sort_by == "uploaded_asc":
        return (
            0 if sort_meta["has_uploaded_ts"] else 1,
            uploaded_ts,
            year if sort_meta["has_year"] else 9999,
            stable,
        )
    return (0 if sort_meta["has_year"] else 1, year if sort_meta["has_year"] else 9999, uploaded_ts, stable)


def _ordered_identity_photo_ids(registry, identity_id: str, sort_by: str = "date_asc") -> tuple[list[str], str]:
    """Return ordered unique photo IDs for a person's gallery context."""
    if not identity_id:
        return [], ""

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return [], ""

    display_name = ensure_utf8_display(identity.get("name", "")) or "Person"
    all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_id_strings = []
    for face_entry in all_faces:
        fid = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")
        if fid:
            face_id_strings.append(fid)

    # Build the photo set in the CANONICAL photo-view ID space so that the
    # membership check (photo_id in this set) matches the IDs the photo page,
    # face overlays, and entry links use. Resolving per-face via
    # get_photo_id_for_face (which reads _face_to_photo_cache, canonical space)
    # is the authoritative resolver; get_photos_for_faces returns durable
    # PhotoRegistry (inbox_*) IDs which do NOT match the viewer's ID space and
    # silently broke person-scoped navigation (FB-004, Session 165, Lesson 25).
    # Canonicalize EVERY resolved pid (not just the fallback path): the
    # _face_to_photo_cache backing get_photo_id_for_face can hold raw registry
    # (inbox_*) IDs, so a mixed mapping would otherwise leak non-canonical IDs
    # into the set and break the membership check (Codex P2, Session 165).
    ordered_photo_ids = []
    seen_photo_ids = set()
    for fid in face_id_strings:
        pid = _main_mod.get_photo_id_for_face(fid)
        if not pid:
            continue
        pid = _main_mod.canonical_photo_id(pid)
        if pid and pid not in seen_photo_ids:
            seen_photo_ids.add(pid)
            ordered_photo_ids.append(pid)

    # Fallback: if the face→photo cache yielded nothing (e.g. cold cache),
    # use the PhotoRegistry resolver and normalize each ID to canonical space.
    if not ordered_photo_ids:
        try:
            photo_registry = _main_mod.load_photo_registry()
            for pid in photo_registry.get_photos_for_faces(face_id_strings):
                canonical = _main_mod.canonical_photo_id(pid)
                if canonical and canonical not in seen_photo_ids:
                    seen_photo_ids.add(canonical)
                    ordered_photo_ids.append(canonical)
        except Exception:
            ordered_photo_ids = []

    if not ordered_photo_ids:
        return [], display_name

    date_labels = _main_mod._load_date_labels()
    normalized_sort = _normalize_gallery_sort(sort_by)
    ordered_photo_ids = sorted(
        ordered_photo_ids,
        key=lambda pid: _gallery_sort_key(
            normalized_sort,
            _build_gallery_sort_meta(pid, _main_mod.get_photo_metadata(pid), date_labels),
            pid,
        ),
    )
    return ordered_photo_ids, display_name


def photo_view_content(
    photo_id: str,
    selected_face_id: str = None,
    is_partial: bool = False,
    prev_id: str = None,
    next_id: str = None,
    nav_idx: int = -1,
    nav_total: int = 0,
    identity_id: str = None,
    sort_by: str = "date_asc",
    is_admin: bool = False,
    from_compare: bool = False,
    seq_mode: bool = False,
    from_queue: bool = False,
    community_slug: str = "rhodes",
) -> tuple:
    """
    Build the photo view content with face overlays.

    Optional navigation context for prev/next arrows:
    - prev_id/next_id: Photo IDs for adjacent photos
    - nav_idx/nav_total: Position counter for "X of Y" display
    - identity_id: Compute navigation from identity's unique photos

    Returns FastHTML elements for the photo viewer.
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        error_content = Div(
            P("Photo not found", cls="text-red-400 font-bold"),
            P(f"ID: {photo_id}", cls="text-slate-400 text-sm font-data"),
            cls="text-center p-8",
        )
        return (error_content,) if is_partial else (Title("Photo Not Found"), error_content)

    # Get image dimensions for face overlay positioning
    # This handles inbox uploads which are stored outside raw_photos/
    width, height = _main_mod.get_photo_dimensions(photo["filename"])

    # If dimensions aren't available (e.g., R2 mode without cached dimensions),
    # we can still show the photo - just without face overlays
    has_dimensions = width > 0 and height > 0

    registry = _main_mod.load_registry()
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    sort_by = _normalize_gallery_sort(sort_by)
    context_identity_id = identity_id
    context_photo_ids, context_person_name = _ordered_identity_photo_ids(registry, context_identity_id, sort_by)
    # Normalize the incoming photo_id to canonical space so the membership check
    # below matches regardless of which entry link (faces gallery → canonical,
    # photos gallery → inbox_*) the viewer arrived from (Session 165, Lesson 25).
    canonical_pid = _main_mod.canonical_photo_id(photo_id)

    # Identity-based navigation: when identity_id is provided and no explicit
    # prev/next, compute navigation from the identity's unique photo list.
    # The `not prev_id and not next_id` guard preserves explicit-nav-wins
    # (compare modal, seq-mode, direct callers) — only collection-leak via the
    # identity entry point is corrected here.
    if (
        context_identity_id
        and context_photo_ids
        and not prev_id
        and not next_id
        and canonical_pid in context_photo_ids
    ):
        idx = context_photo_ids.index(canonical_pid)
        if idx > 0:
            prev_id = context_photo_ids[idx - 1]
        if idx < len(context_photo_ids) - 1:
            next_id = context_photo_ids[idx + 1]
        nav_idx = idx
        nav_total = len(context_photo_ids)

    # Pre-pass: identify unidentified faces for sequential mode + "Name These Faces" button
    # Sort by left-to-right bbox position for natural left-to-right naming order
    unidentified_face_ids = []
    total_face_count = len(photo.get("faces", []))
    for fd in photo.get("faces", []):
        fid = fd["face_id"]
        ident = _main_mod.get_identity_for_face(registry, fid)
        ident_state = ident.get("state", "INBOX") if ident else None
        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
        is_named = ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified")
        if not is_named:
            unidentified_face_ids.append(fid)

    # Sort unidentified faces left-to-right by bbox x1
    def _face_x1(fid):
        for fd in photo.get("faces", []):
            if fd["face_id"] == fid:
                bbox = fd.get("bbox", [0, 0, 0, 0])
                return bbox[0] if bbox else 0
        return 0

    unidentified_face_ids.sort(key=_face_x1)
    seq_active_face_id = unidentified_face_ids[0] if (seq_mode and unidentified_face_ids) else None
    identified_count = total_face_count - len(unidentified_face_ids)
    missing_face_artifacts = sum(1 for fd in photo.get("faces", []) if fd.get("missing_artifacts"))
    missing_face_label = "record" if missing_face_artifacts == 1 else "records"
    missing_face_verb = "lacks" if missing_face_artifacts == 1 else "lack"

    from urllib.parse import quote as _url_quote, urlencode as _url_encode

    context_query = {}
    if context_identity_id:
        context_query["identity_id"] = context_identity_id
        context_query["sort_by"] = sort_by
    context_query_suffix = f"&{_url_encode(context_query)}" if context_query else ""
    seq_query_suffix = f"&seq=1{context_query_suffix}" if seq_mode else context_query_suffix
    action_context_suffix = (
        f"&context_identity_id={context_identity_id}&sort_by={sort_by}" if context_identity_id else ""
    )

    def _partial_photo_url(
        target_photo_id: str,
        *,
        selected_face: str | None = None,
        prev_photo_id: str | None = None,
        next_photo_id: str | None = None,
        nav_index: int | None = None,
        nav_size: int | None = None,
        seq_active: bool = False,
    ) -> str:
        params = {}
        if selected_face:
            params["face"] = selected_face
        if prev_photo_id:
            params["prev_id"] = prev_photo_id
        if next_photo_id:
            params["next_id"] = next_photo_id
        if nav_index is not None and nav_index >= 0:
            params["nav_idx"] = nav_index
        if nav_size is not None and nav_size > 0:
            params["nav_total"] = nav_size
        if context_identity_id:
            params["identity_id"] = context_identity_id
            params["sort_by"] = sort_by
        if seq_active:
            params["seq"] = "1"
        query_string = _url_encode(params)
        return (
            f"{nav_prefix}/photo/{target_photo_id}/partial?{query_string}"
            if query_string
            else f"{nav_prefix}/photo/{target_photo_id}/partial"
        )

    next_seq_photo_id = None
    next_seq_unidentified_count = 0
    seq_queue_summary = None
    if seq_mode and context_photo_ids and canonical_pid in context_photo_ids:
        unresolved_counts = {}
        for queued_photo_id in context_photo_ids:
            queue_photo = _main_mod.get_photo_metadata(queued_photo_id) or {}
            unresolved = 0
            for queued_face in queue_photo.get("faces", []):
                queued_identity = _main_mod.get_identity_for_face(registry, queued_face.get("face_id", ""))
                queued_state = queued_identity.get("state", "INBOX") if queued_identity else None
                queued_name = queued_identity.get("name", "Unidentified") if queued_identity else "Unidentified"
                if queued_state != "CONFIRMED" or queued_name.startswith("Unidentified"):
                    unresolved += 1
            unresolved_counts[queued_photo_id] = unresolved

        current_queue_index = context_photo_ids.index(canonical_pid)
        unresolved_photo_count = sum(1 for count in unresolved_counts.values() if count > 0)
        seq_queue_summary = (
            f"{context_person_name}: photo {current_queue_index + 1} of {len(context_photo_ids)}"
            f" · {unresolved_photo_count} photo{'s' if unresolved_photo_count != 1 else ''} still need review"
        )
        if not unidentified_face_ids:
            for queued_photo_id in context_photo_ids[current_queue_index + 1 :]:
                queued_unresolved = unresolved_counts.get(queued_photo_id, 0)
                if queued_unresolved > 0:
                    next_seq_photo_id = queued_photo_id
                    next_seq_unidentified_count = queued_unresolved
                    break

    # Build face overlays with CSS percentages for responsive scaling
    # Only if we have dimensions (needed for percentage calculations)
    face_overlays = []
    if has_dimensions:
        for face_data in photo["faces"]:
            if not _main_mod.has_displayable_face_bbox(face_data):
                continue
            face_id = face_data["face_id"]
            face_id_encoded = _url_quote(face_id, safe="")
            bbox = face_data["bbox"]  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = bbox

            # Convert to percentages for responsive positioning
            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            # Get identity info
            identity = _main_mod.get_identity_for_face(registry, face_id)
            # UI BOUNDARY: sanitize display_name for safe rendering
            raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
            display_name = ensure_utf8_display(raw_name)
            face_identity_id = identity["identity_id"] if identity else None

            # Calculate age at time of photo if both birth year and photo year exist
            age_at_photo = None
            if face_identity_id and identity and identity.get("state") == "CONFIRMED":
                birth_year, by_source, _ = _main_mod._get_birth_year(
                    face_identity_id,
                    identity,
                    include_unreviewed=False,
                )
                if birth_year:
                    # Get photo year from date labels or photo metadata
                    date_labels = _main_mod._load_date_labels()
                    date_label = date_labels.get(photo_id, {})
                    photo_year = date_label.get("best_year_estimate")
                    if not photo_year:
                        date_taken = photo.get("date_taken", "")
                        if date_taken and len(str(date_taken)) >= 4:
                            try:
                                photo_year = int(str(date_taken)[:4])
                            except (ValueError, TypeError):
                                pass
                    if photo_year:
                        age_at_photo = int(photo_year) - birth_year

            # Determine section based on identity state for navigation
            if identity:
                state = identity.get("state", "INBOX")
                nav_section = _section_for_state(state)
            else:
                state = None
                nav_section = "to_review"

            # Determine if this face is selected
            is_selected = face_id == selected_face_id

            # Build the overlay div with status-based colors
            overlay_classes = "face-overlay absolute cursor-pointer transition-all"
            status_badge = None
            if is_selected:
                overlay_classes += " border-2 border-amber-500 bg-amber-500/20"
            elif state == "CONFIRMED":
                overlay_classes += (
                    " border-2 border-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20 hover:border-emerald-300"
                )
                status_badge = Span(
                    "\u2713",
                    cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-emerald-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center pointer-events-none",
                )
            elif state == "SKIPPED":
                overlay_classes += (
                    " border-2 border-amber-500 bg-amber-500/10 hover:bg-amber-500/20 hover:border-amber-300"
                )
                status_badge = Span(
                    "\u23ed",
                    cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-amber-500 text-white text-[8px] rounded-full flex items-center justify-center pointer-events-none",
                )
            elif state in ("REJECTED", "CONTESTED"):
                overlay_classes += " border-2 border-red-500 bg-red-500/10 hover:bg-red-500/20 hover:border-red-300"
                status_badge = Span(
                    "\u2717",
                    cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center pointer-events-none",
                )
            elif state == "PROPOSED":
                overlay_classes += (
                    " border-2 border-indigo-400 bg-indigo-400/10 hover:bg-indigo-400/20 hover:border-indigo-300"
                )
            else:
                # INBOX or unassigned — dashed border signals "needs attention"
                overlay_classes += (
                    " border-2 border-dashed border-slate-400 bg-slate-400/5 hover:bg-slate-400/15 hover:border-white"
                )

            # Tag dropdown for this face (hidden by default)
            tag_dropdown_id = f"tag-dropdown-{face_id.replace(':', '-').replace(' ', '_')}"
            tag_results_id = f"tag-results-{face_id.replace(':', '-').replace(' ', '_')}"

            # Click handler: confirmed faces navigate to identity card;
            # all other faces open the tag dropdown.
            if state == "CONFIRMED" and face_identity_id:
                tag_script = (
                    f"on click halt the event's bubbling "
                    f"then add .hidden to #photo-modal "
                    f"then go to url '{nav_prefix}/person/{face_identity_id}'"
                )
            else:
                tag_script = (
                    f"on click halt the event's bubbling "
                    f"then set dropdowns to <div.tag-dropdown/> in closest .photo-viewer "
                    f"then for dd in dropdowns "
                    f"  if dd.id is not '{tag_dropdown_id}' add .hidden to dd end "
                    f"end "
                    f"then toggle .hidden on #{tag_dropdown_id} "
                    f"then set el to first <input/> in #{tag_dropdown_id} "
                    f"then if el call el.focus()"
                )

            tag_placeholder = "Type name to tag..." if is_admin else "Who is this person?"
            is_seq_active = seq_mode and face_id == seq_active_face_id
            seq_param = "&seq=1" if seq_mode else ""
            # UX-073: Enter key submits first result in dropdown
            # Enter triggers HTMX fetch immediately (bypassing 300ms debounce),
            # then waits for htmx:afterSettle before clicking — no timing hacks.
            _enter_handler = (
                f"on keydown[key=='Enter'] halt the event "
                f"then set firstBtn to first <button/> in #{tag_results_id} "
                f"then if firstBtn click firstBtn "
                f"else wait for htmx:afterSettle from #{tag_results_id} "
                f"then set firstBtn to first <button/> in #{tag_results_id} "
                f"then if firstBtn click firstBtn end"
            )
            _focus_handler = "on load focus() me" if is_seq_active else ""
            _hyperscript_val = f"{_enter_handler} {_focus_handler}".strip()
            tag_search_input = Input(
                type="text",
                placeholder=tag_placeholder,
                cls="w-full px-4 py-3 sm:px-2 sm:py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                hx_get=(
                    f"{nav_prefix}/api/face/tag-search?face_id={face_id_encoded}{seq_param}{action_context_suffix}"
                ),
                hx_trigger="keyup changed delay:180ms, keydown[key=='Enter']",
                hx_target=f"#{tag_results_id}",
                hx_include="this",
                name="q",
                autocomplete="off",
                **{"_": _hyperscript_val},
            )
            # In seq mode, "Close" becomes "Done" and exits sequential mode
            if seq_mode:
                close_btn = Button(
                    "Done",
                    cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 ml-auto",
                    hx_get=_partial_photo_url(photo_id),
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    type="button",
                )
            else:
                close_btn = Button(
                    "Close",
                    cls="text-sm sm:text-xs text-slate-400 hover:text-slate-300 ml-auto",
                    **{"_": f"on click add .hidden to #{tag_dropdown_id}"},
                    type="button",
                )
            dropdown_hidden = "" if is_seq_active else "hidden "
            tag_dropdown = Div(
                # Search input
                tag_search_input,
                # Results container (pre-populated with existing suggestions if any)
                Div(
                    *_main_mod._existing_suggestions_for_identity(face_identity_id, face_id_encoded),
                    id=tag_results_id,
                    cls="mt-1 max-h-48 overflow-y-auto",
                ),
                # Bottom actions
                Div(
                    Button(
                        "Go to Face Card",
                        cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300",
                        **{
                            "_": f"on click add .hidden to #photo-modal then go to url '{nav_prefix}/person/{face_identity_id}'"
                        }
                        if face_identity_id
                        else {},
                        type="button",
                    )
                    if (face_identity_id and not seq_mode)
                    else None,
                    # FB-048: View Person link in seq mode
                    A(
                        "View Person \u2192",
                        href=f"{nav_prefix}/person/{face_identity_id}",
                        cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300",
                        target="_blank",
                    )
                    if (face_identity_id and seq_mode)
                    else None,
                    # UX-075: Skip button in sequential mode
                    Button(
                        "Ignore Stranger \u2192",
                        cls="text-sm sm:text-xs text-amber-400 hover:text-amber-300 px-2 py-0.5 rounded border border-amber-500/30 hover:bg-amber-500/10",
                        hx_post=(
                            f"{nav_prefix}/api/face/quick-action?identity_id={face_identity_id}"
                            f"&action=skip&photo_id={photo_id}&seq=1{action_context_suffix}"
                        ),
                        hx_target="#photo-modal-content",
                        hx_swap="innerHTML",
                        title="Mark this face as background noise or defer it for later review",
                        data_testid="seq-ignore-stranger",
                        type="button",
                    )
                    if (seq_mode and face_identity_id)
                    else None,
                    close_btn,
                    cls="flex items-center justify-between mt-2 pt-1 border-t border-slate-700",
                ),
                id=tag_dropdown_id,
                cls=f"{dropdown_hidden}tag-dropdown absolute top-full left-0 mt-1 w-56 sm:w-64 bg-slate-800 border border-slate-600 "
                "rounded-lg shadow-xl p-2 z-20",
                **{"_": "on click halt the event's bubbling"},  # Prevent clicks inside from closing
            )

            # Build inline quick-action buttons for admin users
            # Only for actionable states (INBOX, PROPOSED, SKIPPED)
            quick_actions = None
            if is_admin and face_identity_id and state in ("INBOX", "PROPOSED", "SKIPPED"):
                action_btns = []
                # Session 138 FB-006: Confirm enabled for all (including unidentified)
                action_btns.append(
                    Button(
                        "\u2713",
                        cls="w-6 h-6 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm sm:text-xs "
                        "flex items-center justify-center",
                        hx_post=(
                            f"{nav_prefix}/api/face/quick-action?identity_id={face_identity_id}"
                            f"&action=confirm&photo_id={photo_id}{action_context_suffix}{seq_param}"
                        ),
                        hx_target="#photo-modal-content",
                        hx_swap="innerHTML",
                        title="Confirm",
                        type="button",
                        **{"_": "on click halt the event's bubbling"},
                    )
                )
                # Reject button
                action_btns.append(
                    Button(
                        "\u2717",
                        cls="w-6 h-6 rounded-full bg-red-600 hover:bg-red-500 text-white text-sm sm:text-xs "
                        "flex items-center justify-center",
                        hx_post=(
                            f"{nav_prefix}/api/face/quick-action?identity_id={face_identity_id}"
                            f"&action=reject&photo_id={photo_id}{action_context_suffix}{seq_param}"
                        ),
                        hx_target="#photo-modal-content",
                        hx_swap="innerHTML",
                        title="Reject",
                        type="button",
                        **{"_": "on click halt the event's bubbling"},
                    )
                )
                # Session 153: Skip pill is OUTSIDE the face bbox (not mixed in
                # with Confirm/Reject) so mis-clicks on the face don't flip the
                # identity to SKIPPED. Larger hitbox (36x36 min) + text label
                # + hx_confirm + data-undo-* for Z-key undo.
                skip_pill = None
                if state in ("INBOX", "PROPOSED"):
                    _skip_url = (
                        f"{nav_prefix}/api/face/quick-action?identity_id={face_identity_id}"
                        f"&action=skip&photo_id={photo_id}{action_context_suffix}{seq_param}"
                    )
                    _restore_url = f"{nav_prefix}/api/identity/{face_identity_id}/restore"
                    skip_pill = Button(
                        Span("Skip", cls="text-xs sm:text-sm font-semibold tracking-wide"),
                        cls=(
                            "skip-pill absolute -bottom-10 left-1/2 -translate-x-1/2 "
                            "min-h-[36px] min-w-[72px] px-3 py-1.5 rounded-full bg-amber-500 "
                            "hover:bg-amber-400 text-white shadow-lg "
                            "opacity-0 group-hover:opacity-100 transition-opacity z-10 "
                            "flex items-center justify-center whitespace-nowrap"
                        ),
                        hx_post=_skip_url,
                        hx_target="#photo-modal-content",
                        hx_swap="innerHTML",
                        hx_confirm="Skip this face? You can restore from the person page.",
                        title="Skip this face — defer for later review (you can restore from the person page)",
                        type="button",
                        data_testid=f"face-skip-pill-{face_identity_id}",
                        # Feed the Z-undo stack with a restore URL so the accidental
                        # skip can be reversed with Z or the toast Undo button.
                        **{
                            "data-undo-type": "skip",
                            "data-undo-identity": face_identity_id,
                            "data-undo-url": _restore_url,
                            "data-undo-label": "Restore accidentally skipped person",
                            "_": "on click halt the event's bubbling",
                        },
                    )
                quick_actions = Div(
                    Div(
                        *action_btns,
                        cls="quick-actions absolute bottom-1 left-1/2 -translate-x-1/2 flex gap-1 "
                        "opacity-0 group-hover:opacity-100 transition-opacity z-10",
                    ),
                    skip_pill,
                )

            # Name label: always visible for confirmed, hover for others
            if state == "CONFIRMED":
                # Always-visible name label — position above or below based on face location
                # Synced with public page logic (UX review fix: prevents label-box overlap)
                label_text = display_name
                if age_at_photo is not None and age_at_photo >= 0:
                    label_text = f"{display_name}, ~{age_at_photo}"
                # Place label above face if face is in bottom 85% of image (avoids overlap with boxes below)
                name_above = (top_pct + height_pct) > 85
                name_pos_cls = "-top-5" if name_above else "bottom-0"
                name_label = Span(
                    label_text,
                    cls=f"absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-white text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[10rem] truncate",
                )
                hover_tooltip = None
            else:
                # Hover tooltip for non-confirmed
                name_label = None
                hover_tooltip = Span(
                    display_name,
                    cls="absolute -top-8 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none",
                )

            # In sequential mode, highlight the active face
            seq_highlight = ""
            if is_seq_active:
                seq_highlight = " ring-2 ring-indigo-400 ring-offset-1 ring-offset-black/50"

            _overlay_style = (
                f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;"
            )
            # Face labels: confirmed faces visible for ALL users, others admin-only
            if not is_admin and state != "CONFIRMED":
                _overlay_style += " display: none;"
            overlay = Div(
                hover_tooltip,
                name_label,
                status_badge,
                quick_actions,
                tag_dropdown,
                cls=f"{overlay_classes}{seq_highlight} group",
                style=_overlay_style,
                title=display_name,
                data_face_id=face_id,
                data_identity_id=face_identity_id or "",
                **{"_": tag_script},
            )
            face_overlays.append(overlay)

    # Build navigation buttons (for Photos section browsing)
    nav_prev = None
    nav_next = None
    nav_counter = None
    nav_keyboard_script = None

    if prev_id or next_id or (nav_total > 0):
        # Build navigation buttons with data-action attributes for event delegation.
        # The global delegation handler (in the page layout) reads data-action,
        # data-nav-idx, and data-nav-url to dispatch navigation. This pattern
        # survives HTMX content swaps because the listener is on document, not
        # on the swapped DOM nodes.
        if prev_id:
            prev_url = _partial_photo_url(
                prev_id,
                nav_index=nav_idx - 1,
                nav_size=nav_total,
                seq_active=seq_mode,
            )
            nav_prev = Button(
                Span("\u25c0", cls="text-xl"),
                cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white "
                "w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
                type="button",
                title="Previous photo",
                id="photo-nav-prev",
                data_action="photo-nav-prev",
                data_nav_idx=str(nav_idx - 1),
                data_nav_url=prev_url,
            )
        if next_id:
            next_url = _partial_photo_url(
                next_id,
                nav_index=nav_idx + 1,
                nav_size=nav_total,
                seq_active=seq_mode,
            )
            nav_next = Button(
                Span("\u25b6", cls="text-xl"),
                cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white "
                "w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
                type="button",
                title="Next photo",
                id="photo-nav-next",
                data_action="photo-nav-next",
                data_nav_idx=str(nav_idx + 1),
                data_nav_url=next_url,
            )
        # Boundary indicators for first/last photo
        if not prev_id and nav_total > 1:
            nav_prev = Div(
                Span("\u25c0", cls="text-xl opacity-30"),
                cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/30 text-white/30 "
                "w-12 h-12 rounded-full flex items-center justify-center z-10 cursor-default",
                title="First photo",
            )
        if not next_id and nav_total > 1:
            nav_next = Div(
                Span("\u25b6", cls="text-xl opacity-30"),
                cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/30 text-white/30 "
                "w-12 h-12 rounded-full flex items-center justify-center z-10 cursor-default",
                title="Last photo",
            )
        if nav_idx >= 0 and nav_total > 0:
            nav_counter = Span(f"{nav_idx + 1} / {nav_total}", cls="text-slate-400 text-sm ml-auto")
        # No per-swap keyboard script needed — the global event delegation
        # handler in the page layout handles ArrowLeft/ArrowRight/Escape.

    # "Back to Compare" button when opened from compare modal
    back_to_compare = None
    if from_compare:
        back_to_compare = Div(
            Button(
                "\u2190 Back to Compare",
                cls="text-sm text-indigo-400 hover:text-indigo-300 px-5 py-4 sm:px-3 sm:py-1.5 rounded border border-indigo-500/30 hover:border-indigo-400/50 transition-colors",
                **{"_": "on click add .hidden to #photo-modal then remove .hidden from #compare-modal"},
                type="button",
            ),
            cls="mb-3",
        )

    # "Name These Faces" button (admin only, 2+ unidentified, not already in seq mode)
    name_faces_banner = None
    if is_admin and len(unidentified_face_ids) >= 2 and not seq_mode:
        name_faces_banner = Div(
            Button(
                f"Name These Faces ({len(unidentified_face_ids)} unidentified)",
                cls="text-sm px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors",
                hx_get=_partial_photo_url(photo_id, seq_active=True),
                hx_target="#photo-modal-content",
                hx_swap="innerHTML",
                type="button",
            ),
            cls="mb-2",
        )

    # Sequential mode progress banner
    seq_banner = None
    if seq_mode and is_admin:
        remaining = len(unidentified_face_ids)
        if remaining > 0:
            seq_banner = Div(
                Div(
                    Span(
                        f"Naming faces: {identified_count} of {total_face_count} identified", cls="text-sm text-white"
                    ),
                    Span(seq_queue_summary, cls="text-[11px] text-indigo-200/80") if seq_queue_summary else None,
                    Span(
                        "Enter picks the top name. Ignore Stranger marks background noise as skipped.",
                        cls="text-[11px] text-slate-300/80",
                    ),
                    cls="flex flex-col gap-0.5",
                ),
                Div(
                    Div(
                        style=f"width: {(identified_count / total_face_count * 100) if total_face_count > 0 else 0:.0f}%",
                        cls="h-full bg-indigo-500 rounded-full transition-all",
                    ),
                    cls="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden mx-3",
                ),
                Button(
                    "Done",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2.5 sm:py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
                    hx_get=_partial_photo_url(photo_id),
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    type="button",
                ),
                cls="flex items-center gap-2 mb-2 px-3 py-2 bg-indigo-900/30 border border-indigo-500/30 rounded-lg",
            )
        elif next_seq_photo_id:
            next_seq_url = _partial_photo_url(next_seq_photo_id, seq_active=True)
            seq_banner = Div(
                Div(
                    Span("Photo complete.", cls="text-sm text-emerald-300 font-medium"),
                    Span(
                        f"Advancing to the next photo with {next_seq_unidentified_count} unresolved "
                        f"face{'s' if next_seq_unidentified_count != 1 else ''}.",
                        cls="text-[11px] text-slate-300/80",
                    ),
                    Span(seq_queue_summary, cls="text-[11px] text-emerald-200/80") if seq_queue_summary else None,
                    cls="flex flex-col gap-0.5",
                ),
                Button(
                    "Open next photo now",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2.5 sm:py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors ml-auto",
                    hx_get=next_seq_url,
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    type="button",
                ),
                Div(
                    hx_get=next_seq_url,
                    hx_trigger="load delay:250ms",
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    cls="hidden",
                    data_testid="seq-auto-advance",
                ),
                cls="flex items-center gap-2 mb-2 px-3 py-2 bg-emerald-900/30 border border-emerald-500/30 rounded-lg",
            )
        else:
            seq_banner = Div(
                Div(
                    Span("All faces identified!", cls="text-sm text-emerald-300 font-medium"),
                    Span(seq_queue_summary, cls="text-[11px] text-emerald-200/80") if seq_queue_summary else None,
                    cls="flex flex-col gap-0.5",
                ),
                Button(
                    "Done",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2.5 sm:py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors ml-auto",
                    hx_get=_partial_photo_url(photo_id),
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    type="button",
                ),
                cls="flex items-center gap-2 mb-2 px-3 py-2 bg-emerald-900/30 border border-emerald-500/30 rounded-lg",
            )

    # Main content
    content = Div(
        back_to_compare,
        seq_banner,
        name_faces_banner,
        Div(
            f"Archived note: {missing_face_artifacts} face {missing_face_label} "
            f"{missing_face_verb} current overlay coordinates. The photo is intact; only the live overlay is unavailable.",
            cls="mb-2 px-3 py-2 text-sm sm:text-xs text-slate-300 bg-slate-900/60 border border-slate-700/60 rounded-lg",
        )
        if missing_face_artifacts
        else None,
        # Photo container with overlays and nav arrows
        Div(
            Img(src=photo_url(photo["filename"]), alt=photo["filename"], cls="max-w-full h-auto"),
            *face_overlays,
            # Face overlay legend
            Div(
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-emerald-500 mr-0.5"),
                Span("Identified", cls="text-slate-400 mr-2"),
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-amber-500 mr-0.5"),
                Span("Help Identify", cls="text-slate-400 mr-2"),
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-dashed border-slate-400 mr-0.5"),
                Span("New", cls="text-slate-400"),
                cls="absolute bottom-1 right-1 bg-black/60 rounded px-2 py-0.5 flex items-center gap-0.5 text-[10px] face-overlay-legend",
                id="face-overlay-legend",
                style="" if is_admin else "display: none;",
            )
            if face_overlays
            else None,
            nav_prev,
            nav_next,
            cls="relative inline-block max-w-full",
        ),
        # Photo info
        Div(
            Div(
                P(photo["filename"], cls="text-slate-300 text-sm font-data font-medium"),
                nav_counter,
                Span(
                    Button(
                        "Hide Faces" if is_admin else "Show Faces",
                        cls="text-sm sm:text-xs text-slate-400 hover:text-slate-200 transition-colors",
                        type="button",
                        data_action="toggle-face-overlays",
                        id="face-overlay-toggle",
                        data_overlays_hidden="false" if is_admin else "true",
                    )
                    if face_overlays
                    else None,
                    _main_mod.share_button(photo_id, style="link", label="Share"),
                    A(
                        "View Photo \u2192",
                        href=(
                            f"{nav_prefix}/photo/{photo_id}?identity_id={context_identity_id}&sort_by={sort_by}"
                            if context_identity_id
                            else f"{nav_prefix}/photo/{photo_id}"
                        ),
                        cls="text-sm font-medium text-indigo-400 hover:text-indigo-300 underline",
                        target="_blank",
                        rel="noopener",
                    ),
                    cls="ml-auto flex items-center gap-3",
                ),
                cls="flex items-center gap-2",
            ),
            P(
                f"{len(photo['faces'])} face{'s' if len(photo['faces']) != 1 else ''} detected",
                cls="text-slate-400 text-sm",
            ),
            P(
                f"{width} x {height} px" if has_dimensions else "Dimensions unavailable",
                cls="text-slate-500 text-sm sm:text-xs font-data",
            ),
            P("(Face overlays require cached dimensions)", cls="text-slate-600 text-sm sm:text-xs italic")
            if not has_dimensions and photo["faces"]
            else None,
            # Upload provenance (uploaded by / added to archive date) — admin-only
            _main_mod._build_upload_provenance_line(photo, is_admin=is_admin),
            # Collection / Source / Source URL display
            Div(
                P(
                    Span("Collection: ", cls="text-slate-500"),
                    Span(photo.get("collection", ""), cls="text-slate-300"),
                    cls="text-sm sm:text-xs",
                )
                if photo.get("collection")
                else None,
                P(
                    Span("Source: ", cls="text-slate-500"),
                    Span(photo.get("source", ""), cls="text-slate-300"),
                    cls="text-sm sm:text-xs",
                )
                if photo.get("source")
                else None,
                P(
                    Span("Source URL: ", cls="text-slate-500"),
                    A(
                        photo.get("source_url", ""),
                        href=photo.get("source_url", ""),
                        target="_blank",
                        rel="noopener",
                        cls="text-indigo-400 hover:text-indigo-300 underline",
                    ),
                    cls="text-sm sm:text-xs",
                )
                if photo.get("source_url")
                else None,
                cls="mt-1 space-y-0.5",
            )
            if photo.get("collection") or photo.get("source") or photo.get("source_url")
            else None,
            # Stored photo metadata (BE-012)
            _main_mod._photo_metadata_display(photo),
            # Photo annotations display + form (AN-002–AN-006)
            _main_mod._photo_annotations_section(photo_id, is_admin),
            # AI Analysis metadata panel (date estimate, scene, tags, evidence)
            _main_mod._build_ai_analysis_section(photo_id, is_admin),
            # Face alignment descriptions (PRD-015 coordinate bridging)
            _main_mod._build_face_alignment_section(photo_id, is_admin),
            cls="mt-4",
        ),
        nav_keyboard_script,
        cls="photo-viewer p-2 sm:p-4 overflow-x-hidden",
    )

    if is_partial:
        return (content,)

    # Full page with styling
    style = Style("""
        .face-overlay {
            box-sizing: border-box;
            min-width: 44px;
            min-height: 44px;
        }
        .face-overlay:hover {
            z-index: 50;
            transform: scale(1.2);
            transition: transform 0.15s ease;
        }
    """)
    back_href = (
        f"{nav_prefix}/person/{context_identity_id}?view=photos&sort_by={sort_by}"
        if context_identity_id and context_person_name
        else f"{nav_prefix}/?section=to_review"
    )
    back_label = (
        f"Back to {context_person_name}" if context_identity_id and context_person_name else "Back to Review Queue"
    )
    heading = "Speed Loop" if seq_mode else "Photo Context"
    subtitle = (
        "Stay in flow while naming faces. Enter accepts the top suggestion and ignored faces stay reversible."
        if seq_mode
        else "Review this photo with full face context."
    )

    # "Back to Review Queue" escape hatch (when entering Speed Loop from cluster review)
    back_to_queue_link = None
    if from_queue and seq_mode and is_admin:
        back_to_queue_link = A(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>'
            ),
            "Back to Review Queue",
            href=f"{nav_prefix}/admin/upload-review?mode=speed",
            cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg transition-colors inline-flex items-center",
            data_testid="back-to-review-queue",
        )

    return (
        Title(f"{heading} - {photo['filename']}"),
        style,
        Main(
            # Back button
            Div(
                A(f"< {back_label}", href=back_href, cls="text-slate-400 hover:text-slate-300 inline-block"),
                back_to_queue_link,
                cls="flex items-center gap-4 mb-2",
            )
            if back_to_queue_link
            else A(f"< {back_label}", href=back_href, cls="text-slate-400 hover:text-slate-300 mb-2 inline-block"),
            H1(heading, cls="text-2xl font-serif font-bold text-white mb-1"),
            P(subtitle, cls="text-sm text-slate-400 mb-4"),
            Div(content, id="photo-modal-content"),
            cls="p-4 md:p-8 max-w-6xl mx-auto bg-slate-900 min-h-screen",
        ),
    )


def _check_merged_identity(identity_id: str, registry) -> tuple:
    """Returns (is_merged, canonical_id) — use to guard POST identity operations.

    UX-038: POST operations on merged-away identities should redirect to the
    canonical identity instead of silently succeeding on stale data.
    """
    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return False, None
    if identity and identity.get("merged_into"):
        return True, identity["merged_into"]
    return False, None


def _share_script():
    """Reusable share script for standalone public pages."""
    return Script("""
        function _sharePhotoUrl(url, shareTitle, shareText) {
            _copyAndToast(url);
            var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            if (isMobile && navigator.share) {
                var shareData = { url: url };
                if (shareTitle) shareData.title = shareTitle;
                if (shareText) shareData.text = shareText;
                navigator.share(shareData).catch(function() {});
            }
        }
        function _copyAndToast(url) {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(url).then(function() {
                    _showShareToast('Link copied!');
                }).catch(function() { _showShareToast('Could not copy link'); });
            } else {
                var input = document.createElement('input');
                input.value = url;
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                document.body.removeChild(input);
                _showShareToast('Link copied!');
            }
        }
        function _showShareToast(message) {
            var existing = document.getElementById('share-toast');
            if (existing) existing.remove();
            var toast = document.createElement('div');
            toast.id = 'share-toast';
            toast.textContent = message;
            toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
            document.body.appendChild(toast);
            setTimeout(function() { toast.style.opacity = '0'; }, 2000);
            setTimeout(function() { toast.remove(); }, 2500);
        }
        document.addEventListener('click', function(e) {
            var shareBtn = e.target.closest('[data-action="share-photo"]');
            if (shareBtn) {
                var url = shareBtn.getAttribute('data-share-url') || window.location.href;
                var shareTitle = shareBtn.getAttribute('data-share-title') || '';
                var shareText = shareBtn.getAttribute('data-share-text') || '';
                _sharePhotoUrl(url, shareTitle, shareText);
            }
        });
    """)


_identification_responses_cache = None


def _load_identification_responses() -> dict:
    """Load identification responses from data file."""
    global _identification_responses_cache
    if _identification_responses_cache is not None:
        return _identification_responses_cache
    resp_path = _main_mod.data_path / "identification_responses.json"
    default = {"schema_version": 1, "responses": []}
    if resp_path.exists():
        try:
            with open(resp_path, encoding="utf-8") as f:
                _identification_responses_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _identification_responses_cache = default
    else:
        _identification_responses_cache = default
    return _identification_responses_cache


def _save_identification_responses(data: dict):
    """Save identification responses atomically."""
    global _identification_responses_cache
    resp_path = _main_mod.data_path / "identification_responses.json"
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(_main_mod.data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(resp_path))
        _identification_responses_cache = data
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@rt("/help")
def get(sess=None, request=None):
    """
    Public 'Help Needed' page — top 50 unidentified faces sorted by quality.

    No authentication required. Shows face cards with CTAs to identify.
    Drives the growth loop: visitor -> recognize face -> share -> more visitors.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    community_prefixed = getattr(request.state, "community_prefixed", False) if request else False
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    community_identity_ids = _main_mod._get_community_identity_ids(community if community_prefixed else None)

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Collect unidentified identities (INBOX, PROPOSED, SKIPPED; not merged)
    unid_identities = []
    for ident in registry.list_identities():
        identity_id = ident.get("identity_id", "")
        if community_identity_ids is not None and identity_id not in community_identity_ids:
            continue
        if ident.get("merged_into"):
            continue
        state = ident.get("state", "")
        if state not in ("INBOX", "PROPOSED", "SKIPPED"):
            continue
        name = ident.get("name", "")
        if state == "CONFIRMED" and not name.startswith("Unidentified"):
            continue
        face_ids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        if not face_ids:
            continue
        best_fid = _main_mod.get_best_face_id(face_ids)
        if not best_fid:
            best_fid = face_ids[0] if isinstance(face_ids[0], str) else face_ids[0].get("face_id", "")
        crop_url = _main_mod.resolve_face_image_url(best_fid, crop_files) if crop_files else None
        if not crop_url:
            continue
        quality = _main_mod.get_face_quality(best_fid) or 0.0
        photo_id = _main_mod.get_photo_id_for_face(best_fid)
        collection = ""
        if photo_id and _main_mod._photo_cache:
            pm = _main_mod._photo_cache.get(photo_id, {})
            collection = pm.get("collection", "")
        unid_identities.append(
            {
                "identity_id": identity_id,
                "crop_url": crop_url,
                "quality": quality,
                "collection": collection,
            }
        )

    # Sort by quality (highest first), take top 50
    unid_identities.sort(key=lambda x: x["quality"], reverse=True)
    unid_identities = unid_identities[:50]

    # Build face cards (Gap 3: consistent actions across all views)
    face_cards = []
    for item in unid_identities:
        _iid = item["identity_id"]
        face_cards.append(
            Div(
                A(
                    Div(
                        Img(
                            src=item["crop_url"],
                            alt="Unidentified person",
                            cls="w-full h-full object-cover",
                            loading="lazy",
                        ),
                        cls="aspect-square overflow-hidden",
                    ),
                    Div(
                        P("Do you recognize this person?", cls="text-sm sm:text-xs text-amber-300/80 font-medium mb-1"),
                        P(item["collection"], cls="text-[10px] text-slate-500 leading-snug")
                        if item["collection"]
                        else None,
                        cls="p-2.5",
                    ),
                    href=f"{nav_prefix}/identify/{_iid}",
                    cls="block",
                ),
                Div(
                    A(
                        "Similar",
                        href=f"{nav_prefix}/people/{_iid}/similar",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 py-2 px-3 inline-flex items-center min-h-[44px] sm:min-h-0 sm:py-0 sm:px-0",
                    ),
                    Span("|", cls="text-[10px] text-slate-600"),
                    A(
                        "Profile",
                        href=f"{nav_prefix}/person/{_iid}",
                        cls="text-xs text-slate-400 hover:text-slate-300 py-2 px-3 inline-flex items-center min-h-[44px] sm:min-h-0 sm:py-0 sm:px-0",
                    ),
                    cls="flex items-center justify-center gap-1.5 px-2.5 pb-2",
                ),
                cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden hover:border-amber-500/50 transition-colors group",
                data_testid="help-face-card",
            )
        )

    nav_links = _main_mod._public_nav_links(active="help", user=user, community_slug=community_slug)
    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
    is_non_rhodes_community = bool(community and community_slug != "rhodes" and not community.get("is_default"))
    community_display_name = (
        community.get("name", "").strip()
        if is_non_rhodes_community
        else "Rhodes Jewish community"
    )
    if not community_display_name:
        community_display_name = "this community"
    help_og_image = unid_identities[0].get("crop_url", "") if unid_identities else ""
    footer_description = (
        f"Preserving the memory of {community_display_name}"
        if is_non_rhodes_community
        else "Preserving the memory of the Jewish community of Rhodes"
    )

    empty_state = Div(
        Div(
            H2("All faces have been identified!", cls="text-xl font-serif text-white mb-2"),
            P("Thank you to everyone who contributed their knowledge.", cls="text-slate-400 text-sm"),
            A(
                "Browse the archive",
                href=f"{nav_prefix}/photos",
                cls="text-indigo-400 hover:text-indigo-300 text-sm mt-4 inline-block",
            ),
            cls="text-center",
        ),
        cls="py-20",
    )

    return (
        Title("Help Identify \u2014 Rhodesli Heritage Archive"),
        *_main_mod.og_tags(
            "Help Identify People \u2014 Rhodesli",
            f"{len(unid_identities)} faces from the {community_display_name} need your help.",
            image_url=help_og_image,
            canonical_url=f"{nav_prefix}/help",
        ),
        page_style,
        Main(
            _main_mod._public_page_nav(
                nav_links, active="help", user=user, community_slug=community_slug, max_w="max-w-6xl"
            ),
            Section(
                Div(
                    H1("Help Us Identify", cls="text-3xl font-serif font-bold text-white mb-2"),
                    P(
                        f"{len(unid_identities)} face{'s' if len(unid_identities) != 1 else ''} awaiting identification. "
                        "If you recognize anyone, click to share what you know.",
                        cls="text-slate-400 text-sm",
                    ),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-6",
                ),
            ),
            Section(
                Div(
                    Div(
                        *face_cards,
                        cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4",
                    )
                    if face_cards
                    else empty_state,
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-sm sm:text-xs text-slate-500 mb-1 font-serif"),
                    P(
                        footer_description,
                        cls="text-[10px] text-slate-600 italic",
                    ),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/identify/{person_id}")
def get(person_id: str, submitted: str = "", name: str = "", sess=None, request=None):
    """
    Shareable 'Can you identify this person?' page.

    No authentication required. Shows the face, source photos, best matches,
    and a simple response form. This is the URL you share in Facebook groups
    and family chats to crowdsource identification.

    Query params for submission persistence (Gap 5):
    - submitted: "true" if user just submitted an identification
    - name: the name they submitted
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    community_name = (
        community.get("name")
        if isinstance(community, dict) and community.get("name")
        else (
            "Rhodes Jewish Heritage Archive" if community_slug == "rhodes" else community_slug.replace("-", " ").title()
        )
    )

    registry = _main_mod.load_registry()
    identity = _main_mod._safe_get_identity(registry, person_id)

    # FB-153: Determine identity's actual community (may differ from URL community)
    if identity and community:
        comm_ids = _main_mod._get_community_identity_ids(community)
        if comm_ids is not None and person_id not in comm_ids:
            from app.supabase_data import get_community_by_slug, load_communities

            all_communities = load_communities() or []
            for c in all_communities:
                if c.get("slug") == community_slug:
                    continue
                other_ids = _main_mod._get_community_identity_ids(c)
                if other_ids and person_id in other_ids:
                    community_name = c.get("name", c.get("slug", "").replace("-", " ").title())
                    break
    # UX-038: Redirect merged identities to canonical person
    if identity and identity.get("merged_into"):
        return RedirectResponse(f"{nav_prefix}/identify/{identity['merged_into']}", status_code=301)
    if not identity:
        html_404 = to_xml(Title("Person Not Found")) + to_xml(
            Main(
                Div(H2("Person not found", cls="text-xl text-white"), cls="text-center py-20"),
                cls="min-h-screen bg-slate-900",
            )
        )
        return HTMLResponse(html_404, status_code=404)

    display_name = ensure_utf8_display(identity.get("name", "Unknown"))
    state = identity.get("state", "INBOX")
    is_identified = state == "CONFIRMED" and not display_name.startswith("Unidentified")

    # If already identified, redirect to person page
    if is_identified:
        return RedirectResponse(f"{nav_prefix}/person/{person_id}", status_code=303)

    # Get face crops and photos
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_id_strings = [f if isinstance(f, str) else f.get("face_id", "") for f in all_face_ids]
    photo_reg = _main_mod.load_photo_registry()
    photo_ids = list(photo_reg.get_photos_for_faces(face_id_strings))
    crop_files = _main_mod.get_crop_files()
    best_face_id = _main_mod.get_best_face_id(all_face_ids)
    avatar_url = _main_mod.resolve_face_image_url(best_face_id, crop_files) if best_face_id and crop_files else None

    # Build face image
    # Link to first source photo
    _first_photo_id = photo_ids[0] if photo_ids else None
    _source_photo_link = (
        A(
            "View source photo \u2192",
            href=f"{nav_prefix}/photo/{_first_photo_id}",
            cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 mt-2 inline-block",
            data_testid="view-source-photo-link",
        )
        if _first_photo_id
        else None
    )

    face_section = Div(
        Img(
            src=avatar_url,
            alt="Unidentified person",
            cls="w-48 h-48 sm:w-64 sm:h-64 rounded-md object-cover border border-amber-900/40 shadow-md shadow-black/40 mx-auto ui99-face-crop",
        )
        if avatar_url
        else Div(
            Span("?", cls="text-6xl text-amber-900/30 font-serif"),
            cls="w-48 h-48 rounded-md bg-amber-900/5 border border-amber-900/20 flex items-center justify-center mx-auto",
        ),
        _source_photo_link,
        cls="mb-8 text-center",
    )

    # Source photos — build face-to-photo cards with thumbnails (UX-042)
    _main_mod._build_caches()
    photo_cards = []
    _seen_photo_ids = set()
    for fid_entry in all_face_ids:
        fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
        face_photo_id = _main_mod.get_photo_id_for_face(fid)
        if not face_photo_id or face_photo_id in _seen_photo_ids:
            continue
        _seen_photo_ids.add(face_photo_id)
        pm = (_main_mod._photo_cache or {}).get(face_photo_id, {})
        if not pm:
            pm = photo_reg._photos.get(face_photo_id, {})
        photo_path = pm.get("path", "")
        if not photo_path:
            continue
        photo_url = _main_mod.storage.get_photo_url(photo_path)
        crop_url = _main_mod.resolve_face_image_url(fid, crop_files) if crop_files else None
        collection = pm.get("collection", "")
        photo_cards.append(
            A(
                Div(
                    Img(src=photo_url, alt="Source photo", cls="w-full h-40 object-cover rounded-lg"),
                    Img(
                        src=crop_url,
                        alt="Face crop",
                        cls="absolute bottom-2 left-2 w-12 h-12 rounded-lg object-cover border-2 border-amber-500/50 shadow-md",
                    )
                    if crop_url
                    else None,
                    cls="relative",
                ),
                P(collection, cls="text-sm sm:text-xs text-slate-500 mt-1 leading-snug") if collection else None,
                P("See full photo \u2192", cls="text-sm sm:text-xs text-indigo-400 mt-1"),
                href=f"{nav_prefix}/photo/{face_photo_id}",
                cls="block hover:opacity-80 transition-opacity",
                data_testid="source-photo-card",
            )
        )

    # Fallback: if face-to-photo mapping didn't produce cards, use photo_ids
    if not photo_cards:
        for pid in photo_ids[:4]:
            pm = (_main_mod._photo_cache or {}).get(pid, {})
            if not pm:
                pm = photo_reg._photos.get(pid, {})
            photo_path = pm.get("path", "")
            if photo_path:
                photo_url = _main_mod.storage.get_photo_url(photo_path)
                collection = pm.get("collection", "")
                photo_cards.append(
                    A(
                        Img(src=photo_url, alt="Source photo", cls="w-full h-40 object-cover rounded-lg"),
                        P(collection, cls="text-sm sm:text-xs text-slate-500 mt-1 leading-snug")
                        if collection
                        else None,
                        P("See full photo \u2192", cls="text-sm sm:text-xs text-indigo-400 mt-1"),
                        href=f"{nav_prefix}/photo/{pid}",
                        cls="block hover:opacity-80 transition-opacity",
                        data_testid="source-photo-card",
                    )
                )

    photos_section = (
        Div(
            H3("Appears in these photos", cls="text-sm font-semibold text-slate-400 mb-3"),
            Div(*photo_cards, cls="grid grid-cols-2 sm:grid-cols-4 gap-3"),
            cls="mb-10",
            data_testid="source-photos-section",
        )
        if photo_cards
        else None
    )

    # Best matches (nearest neighbors)
    match_cards = []
    try:
        from core.neighbors import find_nearest_neighbors

        if face_id_strings:
            neighbors = find_nearest_neighbors(face_id_strings[0], k=3)
            for n_face_id, dist in neighbors:
                n_ident = _main_mod.get_identity_for_face(registry, n_face_id)
                if n_ident and n_ident.get("identity_id") != person_id:
                    n_name = ensure_utf8_display(n_ident.get("name", "Unknown"))
                    n_crop = _main_mod.resolve_face_image_url(n_face_id, crop_files) if crop_files else None
                    n_id = n_ident.get("identity_id", "")
                    match_cards.append(
                        A(
                            Img(src=n_crop, alt=n_name, cls="w-20 h-20 rounded-xl object-cover")
                            if n_crop
                            else Div(
                                Span("?", cls="text-xl text-slate-500"),
                                cls="w-20 h-20 rounded-xl bg-slate-800 flex items-center justify-center",
                            ),
                            P(
                                n_name if not n_name.startswith("Unidentified") else "Unknown",
                                cls="text-sm sm:text-xs text-slate-300 mt-1 text-center truncate w-20",
                            ),
                            href=f"{nav_prefix}/identify/{person_id}/match/{n_id}",
                            cls="flex flex-col items-center hover:opacity-80 transition-opacity",
                        )
                    )
    except Exception:
        pass

    matches_section = (
        Div(
            H3("Possible matches", cls="text-sm font-semibold text-slate-400 mb-3"),
            Div(*match_cards, cls="flex gap-4 justify-center"),
            cls="mb-10",
        )
        if match_cards
        else None
    )

    # Response form — different for admin vs logged-in vs anonymous
    is_admin = user and user.is_admin if user else False
    user_email = user.email if user else ""

    # Admin gets direct apply option
    form_heading = "You're an admin — apply this name directly?" if is_admin else "Do you recognize this person?"
    submit_label = "Apply Name" if is_admin else "Yes, I know this person!"
    submit_cls = "w-full " + (
        "py-3 px-5 font-semibold rounded-md transition-all bg-gradient-to-r from-amber-700 to-amber-600 "
        "hover:from-amber-600 hover:to-amber-500 text-white font-serif shadow-sm shadow-amber-950/30 "
        "border border-amber-500/40"
        if not is_admin
        else "py-3 font-semibold rounded-md transition-colors bg-indigo-600 hover:bg-indigo-500 text-white font-serif"
    )

    _input_cls = "w-full px-4 py-2.5 bg-[#1e1b18] border border-amber-900/40 rounded-md text-amber-50 placeholder-amber-900/40 focus:border-amber-500/50 focus:outline-none font-serif transition-colors"
    _label_cls = "text-sm text-amber-100/60 font-serif tracking-wide block mb-1.5"

    # Hide email field for logged-in users (auto-filled from session)
    email_field = (
        Div(
            Label("Your email (optional, for follow-up)", fr="resp_email", cls=_label_cls),
            Input(
                type="email",
                name="email",
                id="resp_email",
                value=user_email,
                placeholder="you@example.com",
                cls=_input_cls,
            ),
            cls="mb-6",
        )
        if not user
        else None
    )

    form_section = Div(
        H3(form_heading, cls="text-xl font-display font-medium text-amber-50 mb-5 text-center"),
        Form(
            Input(type="hidden", name="person_id", value=person_id),
            Div(
                Label("Their name", fr="resp_name", cls=_label_cls),
                Input(
                    type="text",
                    name="name",
                    id="resp_name",
                    placeholder="e.g., Sarah Capeluto",
                    cls=_input_cls,
                ),
                cls="mb-4",
            ),
            Div(
                Label("How do you know?", fr="resp_relationship", cls=_label_cls),
                Input(
                    type="text",
                    name="relationship",
                    id="resp_relationship",
                    placeholder="e.g., She's my grandmother",
                    cls=_input_cls,
                ),
                cls="mb-5",
            ),
            email_field,
            Button(submit_label, type="submit", cls=submit_cls),
            hx_post=f"{nav_prefix}/api/identify/{person_id}/respond",
            hx_target="#identify-response-area",
            hx_swap="innerHTML",
        ),
        id="identify-response-area",
        cls="bg-amber-900/5 rounded-lg p-7 border border-amber-900/20 max-w-md mx-auto shadow-sm",
    )

    # Gap 5: Submission persistence — show success banner if submitted=true query param
    from urllib.parse import unquote_plus

    submitted_name = unquote_plus(name) if name else ""
    if submitted == "true":
        submission_banner = Div(
            Div(
                P("Thank you!", cls="text-xl sm:text-lg font-semibold text-emerald-400 mb-1"),
                P(
                    f'Your identification of this person as "{submitted_name}" has been submitted for review.'
                    if submitted_name
                    else "Your identification has been submitted for review.",
                    cls="text-slate-300 text-sm",
                ),
                P("An admin will review your suggestion shortly.", cls="text-slate-500 text-sm sm:text-xs mt-2"),
                cls="bg-emerald-900/20 border border-emerald-800/50 rounded-xl p-6 text-center",
            ),
            id="submission-success-banner",
            cls="max-w-md mx-auto mb-6",
            data_testid="submission-success-banner",
        )
        # Replace the form with the success banner
        form_section = Div(submission_banner, form_section)

    # Admin enrichment panel — name input, merge search, GEDCOM link
    admin_enrichment = None
    if is_admin:
        _admin_input_cls = (
            "w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white "
            "placeholder-slate-400 focus:outline-none focus:border-indigo-500"
        )
        admin_enrichment = Div(
            H3("Admin Tools", cls="text-xl sm:text-lg font-semibold text-indigo-300 mb-4"),
            # Current identity info
            Div(
                P(f"Identity: {display_name}", cls="text-sm text-slate-300"),
                P(
                    f"State: {state} \u00b7 {len(all_face_ids)} face{'s' if len(all_face_ids) != 1 else ''}",
                    cls="text-sm sm:text-xs text-slate-500 mt-1",
                ),
                cls="mb-4 p-3 bg-slate-800/50 border border-slate-700 rounded-lg",
            ),
            # Name input with save
            Div(
                Label("Name this person:", cls="text-sm text-slate-300 block mb-1.5"),
                Div(
                    Input(
                        type="text",
                        name="new_name",
                        placeholder="Enter name...",
                        value="" if display_name.startswith("Unidentified") else display_name,
                        cls=_admin_input_cls,
                        id="admin-identify-name-input",
                    ),
                    Button(
                        "Apply",
                        cls="ml-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors",
                        hx_post=f"{nav_prefix}/api/identify/{person_id}/respond",
                        hx_target="#admin-enrichment-result",
                        hx_swap="innerHTML",
                        hx_include="#admin-identify-name-input",
                    ),
                    cls="flex items-center",
                ),
                Div(id="admin-enrichment-result", cls="mt-2"),
                cls="mb-4",
            ),
            # Merge search
            Div(
                Label("Merge with existing person:", cls="text-sm text-slate-300 block mb-1.5"),
                Input(
                    type="text",
                    name="q",
                    placeholder="Search confirmed identities...",
                    cls=_admin_input_cls,
                    hx_get=f"{nav_prefix}/api/cluster-review/search-identities?source_id={person_id}&offset=0&community_slug={community_slug}",
                    hx_target="#admin-merge-results",
                    hx_swap="innerHTML",
                    hx_trigger="keyup changed delay:300ms",
                ),
                Div(id="admin-merge-results", cls="mt-2 space-y-2"),
                cls="mb-4",
            ),
            # GEDCOM link button
            Div(
                A(
                    "Link to GEDCOM Record",
                    href=f"{nav_prefix}/person/{person_id}?from=admin",
                    cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                    data_testid="identify-gedcom-link",
                ),
                cls="mb-2",
            ),
            cls="mt-8 p-6 bg-indigo-900/20 border border-indigo-500/30 rounded-xl max-w-md mx-auto",
            data_testid="identify-admin-enrichment",
        )

    # Share button
    share_url = f"{_main_mod.SITE_URL}{nav_prefix}/identify/{person_id}"
    share_btn = Button(
        "Share to help identify",
        cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
        data_action="share-photo",
        data_share_url=share_url,
        data_share_title="Can you identify this person?",
        data_share_text=f"Help us identify this person in {community_name}.",
    )

    # OG tags — include collection context for better social sharing
    og_image = avatar_url or ""
    if og_image and not og_image.startswith("http"):
        og_image = f"{_main_mod.SITE_URL}{og_image}"
    _og_collection = ""
    if photo_ids:
        _pm = (_main_mod._photo_cache or {}).get(photo_ids[0], {})
        _og_collection = _pm.get("collection", "")
    _og_title = f"Help identify this person from {community_name}"
    _og_desc = (
        f"This photo is from {_og_collection}. Can you help us identify who this is?"
        if _og_collection
        else f"Help us identify this person from {community_name}. Share with family members who might recognize them."
    )
    og_meta = (
        Meta(property="og:title", content=_og_title),
        Meta(property="og:description", content=_og_desc),
        Meta(property="og:image", content=og_image),
        Meta(property="og:url", content=share_url),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="Rhodesli \u2014 Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content=_og_title),
        Meta(name="twitter:description", content=_og_desc),
        Meta(name="twitter:image", content=og_image),
    )

    # "Explore the Archive" section — pull visitors deeper into the app
    explore_links = []
    if len(photo_ids) > 1:
        explore_links.append(
            A(
                f"See all {len(photo_ids)} photos of this person",
                href=f"{nav_prefix}/identify/{person_id}#photos",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
        )
    explore_links.extend(
        [
            A(
                "Browse all photos",
                href=f"{nav_prefix}/photos",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
            A(
                "View identified people",
                href=f"{nav_prefix}/people",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
            A(
                "Explore the timeline",
                href=f"{nav_prefix}/timeline",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
        ]
    )
    # Gap 4: Compare CTA on identify page
    compare_suggestion = Div(
        P("Have a photo that might be this person?", cls="text-sm text-slate-400 mb-2"),
        A(
            "Compare faces with our photo tool",
            href=f"{nav_prefix}/tools/compare",
            cls="text-amber-300 hover:text-amber-200 text-sm font-medium",
            data_testid="identify-compare-cta",
        ),
        cls="text-center mt-6 mb-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-4 py-3",
    )
    explore_section = Div(
        compare_suggestion,
        H3("Explore the Archive", cls="text-xl sm:text-lg font-serif font-semibold text-white text-center mb-4 mt-6"),
        P(
            f"Hundreds of photos from {community_name} await identification.",
            cls="text-sm text-slate-400 text-center mb-5",
        ),
        Div(*explore_links, cls="flex flex-wrap justify-center gap-3"),
        cls="mt-10 pt-6 border-t border-slate-700/30",
    )

    nav_links = _main_mod._public_nav_links(user=user, community_slug=community_slug)
    page_style = Style("html, body { margin: 0; } body { background-color: #16120e; }")

    return (
        Title("Can you identify this person? — Rhodesli"),
        *og_meta,
        page_style,
        Main(
            # Navigation
            Nav(
                Div(
                    A(
                        Span(
                            "Rhodesli",
                            cls="text-xl sm:text-lg font-display font-bold text-amber-50 tracking-wide ui99-title",
                        ),
                        href=f"{nav_prefix}/",
                    ),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-[#16120e]/95 backdrop-blur-md border-b border-amber-900/20 sticky top-0 z-50",
            ),
            _main_mod._admin_bar(user, community_slug=community_slug),
            # Content
            Section(
                Div(
                    H1(
                        "Can you identify this person?",
                        cls="text-3xl sm:text-4xl font-display tracking-tight font-bold text-amber-50 text-center mb-3 ui99-landing-title drop-shadow-sm",
                    ),
                    P(
                        "The AI found this face in a heritage photo but couldn't determine their name.",
                        cls="text-amber-500/70 text-sm sm:text-xs font-mono uppercase tracking-[0.1em] text-center mb-2",
                        data_testid="identify-ai-note",
                    ),
                    P(
                        f"This person appears in photos from {community_name}. If you recognize them, please let us know.",
                        cls="text-amber-100/70 text-base font-serif text-center mb-10 max-w-xl mx-auto leading-relaxed ui99-landing-body",
                    ),
                    face_section,
                    # Gap 2: Admin quick-nav on identify page
                    Div(
                        A(
                            "View Person Page",
                            href=f"{_main_mod.community_url_prefix(community_slug)}/person/{person_id}",
                            cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 underline",
                            data_testid="identify-admin-link",
                        ),
                        cls="text-center mb-6",
                    )
                    if is_admin
                    else None,
                    photos_section,
                    matches_section,
                    form_section,
                    admin_enrichment,
                    Div(share_btn, cls="flex justify-center mt-10 mb-6"),
                    explore_section,
                    cls="max-w-3xl mx-auto pt-12 pb-20 px-6",
                ),
            ),
            cls="min-h-screen bg-[#16120e] text-amber-50 ui99-surface ui99-identify-page",
        ),
        _main_mod._share_script(),
    )


@rt("/api/identify/{person_id}/respond")
def post(person_id: str, name: str = "", relationship: str = "", email: str = "", sess=None, request=None):
    """Save an identification response via the annotations system.

    Creates an annotation that appears in admin approvals. Also saves to
    identification_responses.json for backward compat / audit trail.
    Session 83a: Fixed silent failure — submissions now reach admin approvals.
    """
    if not name.strip():
        return Div(
            P("Please enter a name for this person.", cls="text-amber-400 text-sm"),
            cls="py-2",
        )

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    is_admin = user and user.is_admin if user else False
    submitted_by = (user.email if user else email.strip()) or "anonymous"

    # If admin, apply name AND confirm directly (no approval needed)
    if is_admin:
        try:
            registry = _main_mod.load_registry()
            previous_name = registry.rename_identity(person_id, name.strip(), user_source="admin_web")
            # Also confirm the person so they move out of New Matches
            identity = registry.get_identity(person_id)
            _notify = None
            if identity.get("state") != "CONFIRMED":
                try:
                    registry.confirm_identity(person_id, user_source="admin_web_identify")
                    _notify = {
                        "identity_id": person_id,
                        "identity_name": name.strip(),
                        "user_id": user.id if user else None,
                        "user_email": user.email if user else None,
                    }
                except ValueError:
                    pass  # Already confirmed or invalid state transition
            _main_mod.save_registry(registry, confirmed_identity_info=_notify, changed_ids={person_id})
            _main_mod.log_user_action(
                "RENAME_IDENTITY",
                identity_id=person_id,
                previous_name=previous_name or "",
                new_name=name.strip(),
                admin=user.email if user else "admin",
                source="admin_web_identify",
            )
            logging.info(f"[identify] Admin direct-named and confirmed {person_id} as '{name.strip()}'")
            return Div(
                Div(
                    P("Name applied and confirmed!", cls="text-xl sm:text-lg font-semibold text-emerald-400 mb-1"),
                    P(
                        f'This person has been named "{name.strip()}" and moved to People. ',
                        A(
                            "View in People \u2192",
                            href=f"{nav_prefix}/person/{person_id}",
                            cls="text-indigo-400 hover:text-indigo-300 underline",
                        ),
                        cls="text-slate-300 text-sm",
                    ),
                    cls="bg-emerald-900/20 border border-emerald-800/50 rounded-xl p-6 text-center",
                ),
            )
        except Exception as e:
            logging.error(f"[identify] Admin direct-name failed for {person_id}: {e}")
            return Div(
                P(f"Error applying name: {e}", cls="text-red-400 text-sm text-center py-4"),
            )

    # For non-admin users: create an annotation for admin review
    try:
        ann_id = str(uuid.uuid4())
        reason = relationship.strip() if relationship else ""
        annotation = {
            "annotation_id": ann_id,
            "type": "name_suggestion",
            "target_type": "identity",
            "target_id": person_id,
            "value": name.strip(),
            "confidence": "likely",
            "reason": reason,
            "submitted_by": submitted_by,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending" if user else "pending_unverified",
            "reviewed_by": None,
            "reviewed_at": None,
        }
        annotations = _main_mod._load_annotations()
        annotations["annotations"][ann_id] = annotation
        _main_mod._save_annotations(annotations)

        logging.info(
            f"[identify] Submission for {person_id}: name='{name.strip()}', by={submitted_by}, ann_id={ann_id}"
        )
        _main_mod.posthog_capture(
            "help_identify_submitted",
            distinct_id=submitted_by,
            properties={"person_id": person_id, "is_admin": is_admin},
        )
    except Exception as e:
        logging.error(f"[identify] Failed to save annotation for {person_id}: {e}")
        return Div(
            P(
                "Something went wrong saving your response. Please try again.",
                cls="text-red-400 text-sm text-center py-4",
            ),
        )

    # Also save to legacy identification_responses.json for audit trail
    try:
        responses = _main_mod._load_identification_responses()
        responses["responses"].append(
            {
                "person_id": person_id,
                "suggested_name": name.strip(),
                "relationship": relationship.strip(),
                "email": email.strip(),
                "timestamp": datetime.now().isoformat(),
                "status": "pending",
                "annotation_id": ann_id,
            }
        )
        _main_mod._save_identification_responses(responses)
    except Exception:
        pass  # Legacy file is a backup — annotation is the source of truth

    # Gap 5: Update URL so refresh preserves submission state
    from urllib.parse import quote_plus

    _encoded_name = quote_plus(name.strip())
    return Div(
        Div(
            P("Thank you!", cls="text-xl sm:text-lg font-semibold text-emerald-400 mb-1"),
            P(
                f'Your identification of this person as "{name.strip()}" has been submitted for review.',
                cls="text-slate-300 text-sm",
            ),
            P("An admin will review your suggestion shortly.", cls="text-slate-500 text-sm sm:text-xs mt-2"),
            cls="bg-emerald-900/20 border border-emerald-800/50 rounded-xl p-6 text-center",
        ),
        Script(
            f"history.replaceState(null, '', '{nav_prefix}/identify/{person_id}?submitted=true&name={_encoded_name}');"
        ),
    )


def _get_match_response_counts(person_a: str, person_b: str) -> dict:
    """Count community responses for a match pair (checks both orderings)."""
    responses = _main_mod._load_identification_responses()
    counts = {"yes": 0, "no": 0, "unsure": 0, "total": 0}
    for r in responses.get("responses", []):
        if r.get("type") != "match_confirmation":
            continue
        pa, pb = r.get("person_a"), r.get("person_b")
        if (pa == person_a and pb == person_b) or (pa == person_b and pb == person_a):
            ans = r.get("answer", "")
            if ans in counts:
                counts[ans] += 1
            counts["total"] += 1
    return counts


def _match_community_summary(person_a: str, person_b: str):
    """Render community response summary for match mode (admin view)."""
    counts = _main_mod._get_match_response_counts(person_a, person_b)
    if counts["total"] == 0:
        return None
    return Div(
        Span("Community: ", cls="text-sm sm:text-xs text-slate-500"),
        Span(f"{counts['yes']} Yes", cls="text-sm sm:text-xs text-emerald-400 font-medium"),
        Span(" · ", cls="text-sm sm:text-xs text-slate-600"),
        Span(f"{counts['no']} No", cls="text-sm sm:text-xs text-rose-400 font-medium"),
        Span(" · ", cls="text-sm sm:text-xs text-slate-600"),
        Span(f"{counts['unsure']} Unsure", cls="text-sm sm:text-xs text-slate-400 font-medium"),
        cls="text-center mt-3 py-2 px-3 bg-amber-900/20 border border-amber-800/30 rounded-lg",
    )


def _match_source_photo_card(face_id, photo_id, label, registry=None, crop_files=None, nav_prefix: str = ""):
    """Build a source photo thumbnail with face highlight for the match page.

    When registry and crop_files are provided, also builds face chips for
    other faces in the same photo (shown below the lightbox image).
    """
    if not photo_id:
        return None
    photo_data = _main_mod.get_photo_metadata(photo_id)
    if not photo_data:
        return None

    filename = photo_data.get("filename", "")
    photo_url = _main_mod.storage.get_photo_url(filename)
    width = photo_data.get("width", 0)
    height = photo_data.get("height", 0)

    # Find face bbox for highlight overlay
    bbox_overlay = None
    if width and height:
        for face in photo_data.get("faces", []):
            if face.get("face_id") == face_id:
                bbox = face.get("bbox")
                if bbox and len(bbox) == 4:
                    x1, y1, x2, y2 = [float(v) for v in bbox]
                    left_pct = (x1 / width) * 100
                    top_pct = (y1 / height) * 100
                    w_pct = ((x2 - x1) / width) * 100
                    h_pct = ((y2 - y1) / height) * 100
                    bbox_overlay = Div(
                        cls="absolute border-2 border-amber-400 rounded-sm",
                        style=f"left:{left_pct:.1f}%;top:{top_pct:.1f}%;width:{w_pct:.1f}%;height:{h_pct:.1f}%",
                    )
                break

    # Get collection and date
    collection = photo_data.get("collection", "")
    date_text, _, _ = _main_mod._get_date_badge(photo_id)

    meta_parts = []
    if collection:
        meta_parts.append(Span(collection, cls="text-slate-400 text-sm sm:text-xs"))
    if date_text:
        meta_parts.append(Span(date_text, cls="text-slate-400 text-sm sm:text-xs"))

    # Build face chips for other faces in this photo
    face_chips_data = []
    if registry and crop_files:
        for face in photo_data.get("faces", []):
            fid = face.get("face_id", "")
            if not fid or fid == face_id:
                continue
            ident = _main_mod.get_identity_for_face(registry, fid)
            if ident:
                iid = ident.get("identity_id", "")
                iname = ensure_utf8_display(ident.get("name", "Unknown"))
                istate = ident.get("state", "INBOX")
                chip_url = _main_mod.resolve_face_image_url(fid, crop_files)
                face_chips_data.append((iid, iname, istate, chip_url))

    # Encode face chips as data attribute for lightbox JS
    import json as _json_fc

    chips_json = _json_fc.dumps(face_chips_data) if face_chips_data else "[]"

    # Build face bbox data for lightbox overlays
    face_bboxes = []
    if width and height:
        for face in photo_data.get("faces", []):
            fid = face.get("face_id", "")
            bbox = face.get("bbox")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = [float(v) for v in bbox]
                ident = _main_mod.get_identity_for_face(registry, fid) if registry else None
                fname = ensure_utf8_display((ident or {}).get("name", "")) if ident else ""
                fstate = (ident or {}).get("state", "INBOX") if ident else "INBOX"
                fident_id = (ident or {}).get("identity_id", "") if ident else ""
                is_highlight = fid == face_id
                # Clean name for display — don't show "Unidentified Person 42"
                display_fname = fname if fname and not fname.startswith("Unidentified") else ""
                face_bboxes.append(
                    {
                        "left": round((x1 / width) * 100, 1),
                        "top": round((y1 / height) * 100, 1),
                        "width": round(((x2 - x1) / width) * 100, 1),
                        "height": round(((y2 - y1) / height) * 100, 1),
                        "name": display_fname,
                        "state": fstate,
                        "identity_id": fident_id,
                        "highlight": is_highlight,
                    }
                )
    bboxes_json = _json_fc.dumps(face_bboxes)

    return Div(
        P(label, cls="text-sm sm:text-xs text-slate-500 uppercase tracking-wider mb-2 font-medium"),
        Div(
            Img(
                src=photo_url,
                alt=f"Source photo for {label}",
                cls="w-full h-auto rounded-lg cursor-pointer transition-opacity hover:opacity-90",
            ),
            bbox_overlay,
            cls="relative inline-block w-full",
            data_action="open-lightbox",
            data_photo_url=photo_url,
            data_photo_label=label,
            data_photo_id=photo_id,
            data_face_chips=chips_json,
            data_face_bboxes=bboxes_json,
            data_collection=collection,
            data_date=date_text or "",
            style="cursor:pointer",
        )
        if photo_url
        else None,
        Div(*meta_parts, cls="flex gap-3 mt-1") if meta_parts else None,
        # Inline face chips preview below the thumbnail
        _match_face_chips_inline(face_chips_data, nav_prefix=nav_prefix) if face_chips_data else None,
        cls="mb-6",
    )


def _match_face_chips_inline(chips_data, nav_prefix: str = ""):
    """Render small face chip thumbnails below a source photo card."""
    if not chips_data:
        return None
    chip_els = []
    for iid, iname, istate, chip_url in chips_data[:8]:  # Cap at 8
        href = f"{nav_prefix}/person/{iid}" if istate == "CONFIRMED" else f"{nav_prefix}/identify/{iid}"
        short_name = iname if not iname.startswith("Unidentified") else "Unknown"
        chip_els.append(
            A(
                Img(src=chip_url, alt=short_name, cls="w-8 h-8 rounded-full object-cover border border-slate-600")
                if chip_url
                else Div(
                    "?",
                    cls="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-sm sm:text-xs text-slate-400",
                ),
                Span(short_name, cls="text-[10px] text-slate-400 block text-center truncate w-12 mt-0.5"),
                href=href,
                title=f"View {iname}" if not iname.startswith("Unidentified") else "Help identify this person",
                cls="flex flex-col items-center hover:opacity-80 transition-opacity",
            )
        )
    return Div(
        P("Also in this photo:", cls="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5"),
        Div(*chip_els, cls="flex flex-wrap gap-2"),
        cls="mt-3 pt-2 border-t border-slate-700/30",
    )


def _match_lightbox_script(nav_prefix: str = ""):
    """JS for the match page lightbox with face overlays, metadata, zoom."""
    _pfx = nav_prefix  # captured for JS injection
    return Script(
        """
    (function() {
        var _navPfx = '"""
        + _pfx.replace("'", "\\'")
        + """';
        var scale = 1;
        var lightbox = document.getElementById('match-lightbox');
        var lbImg = document.getElementById('match-lightbox-img');
        var lbFaces = document.getElementById('match-lightbox-faces');
        var lbOverlays = document.getElementById('match-lightbox-overlays');
        var lbMeta = document.getElementById('match-lightbox-meta');
        if (!lightbox) return;

        function openLightbox(src, chipsJson, bboxesJson, photoId, collection, dateText) {
            scale = 1;
            lbImg.src = src;
            lbImg.style.transform = 'scale(1)';

            // Build face bbox overlays on the lightbox image
            lbOverlays.innerHTML = '';
            try {
                var bboxes = JSON.parse(bboxesJson || '[]');
                bboxes.forEach(function(b) {
                    var div = document.createElement('div');
                    div.style.position = 'absolute';
                    div.style.left = b.left + '%';
                    div.style.top = b.top + '%';
                    div.style.width = b.width + '%';
                    div.style.height = b.height + '%';
                    div.style.pointerEvents = 'auto';
                    div.style.cursor = 'pointer';
                    var borderColor = b.highlight ? 'rgba(245,158,11,0.8)' : (b.state === 'CONFIRMED' ? 'rgba(16,185,129,0.6)' : 'rgba(148,163,184,0.4)');
                    div.style.border = '2px solid ' + borderColor;
                    div.style.borderRadius = '2px';
                    if (b.highlight) div.style.boxShadow = '0 0 8px rgba(245,158,11,0.4)';
                    if (b.name && !b.name.startsWith('Unidentified')) {
                        div.title = b.name;
                        var label = document.createElement('span');
                        label.textContent = b.name;
                        label.style.cssText = 'position:absolute;bottom:-18px;left:0;font-size:10px;color:#e2e8f0;white-space:nowrap;text-shadow:0 1px 3px rgba(0,0,0,0.8);';
                        div.appendChild(label);
                    }
                    if (b.identity_id) {
                        div.addEventListener('click', function(e) {
                            e.stopPropagation();
                            var href = b.state === 'CONFIRMED' ? _navPfx + '/person/' + b.identity_id : _navPfx + '/identify/' + b.identity_id;
                            window.location.href = href;
                        });
                    }
                    lbOverlays.appendChild(div);
                });
            } catch(e) {}

            // Build metadata bar
            lbMeta.innerHTML = '';
            var metaParts = [];
            if (collection) metaParts.push(collection);
            if (dateText) metaParts.push(dateText);
            if (metaParts.length > 0) {
                var metaP = document.createElement('p');
                metaP.textContent = metaParts.join(' · ');
                metaP.className = 'text-sm text-slate-300';
                lbMeta.appendChild(metaP);
            }
            if (photoId) {
                var link = document.createElement('a');
                link.href = _navPfx + '/photo/' + photoId;
                link.textContent = 'View Photo Page →';
                link.className = 'text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 inline-block mt-1 transition-colors';
                lbMeta.appendChild(link);
            }

            // Build face chips in lightbox
            lbFaces.innerHTML = '';
            try {
                var chips = JSON.parse(chipsJson || '[]');
                if (chips.length > 0) {
                    var heading = document.createElement('p');
                    heading.textContent = 'Also in this photo:';
                    heading.className = 'text-sm sm:text-xs text-slate-400 uppercase tracking-wider mb-2 text-center';
                    lbFaces.appendChild(heading);
                    var row = document.createElement('div');
                    row.className = 'flex flex-wrap justify-center gap-3';
                    chips.forEach(function(c) {
                        var iid = c[0], iname = c[1], istate = c[2], chipUrl = c[3];
                        var href = istate === 'CONFIRMED' ? _navPfx + '/person/' + iid : _navPfx + '/identify/' + iid;
                        var shortName = iname.startsWith('Unidentified') ? 'Unknown' : iname;
                        var a = document.createElement('a');
                        a.href = href;
                        a.title = iname.startsWith('Unidentified') ? 'Help identify' : 'View ' + iname;
                        a.className = 'flex flex-col items-center hover:opacity-80 transition-opacity';
                        if (chipUrl) {
                            var img = document.createElement('img');
                            img.src = chipUrl;
                            img.alt = shortName;
                            img.className = 'w-10 h-10 rounded-full object-cover border border-slate-500';
                            a.appendChild(img);
                        } else {
                            var placeholder = document.createElement('div');
                            placeholder.textContent = '?';
                            placeholder.className = 'w-10 h-10 rounded-full bg-slate-700 border border-slate-500 flex items-center justify-center text-sm sm:text-xs text-slate-400';
                            a.appendChild(placeholder);
                        }
                        var nameSpan = document.createElement('span');
                        nameSpan.textContent = shortName;
                        nameSpan.className = 'text-sm sm:text-xs text-slate-300 mt-1 text-center max-w-[60px] truncate';
                        a.appendChild(nameSpan);
                        row.appendChild(a);
                    });
                    lbFaces.appendChild(row);
                }
            } catch(e) {}
            lightbox.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
        function closeLightbox() {
            lightbox.classList.add('hidden');
            document.body.style.overflow = '';
            lbImg.src = '';
            lbOverlays.innerHTML = '';
            lbMeta.innerHTML = '';
        }

        // Event delegation for open/close
        document.addEventListener('click', function(e) {
            // Open lightbox
            var trigger = e.target.closest('[data-action="open-lightbox"]');
            if (trigger) {
                e.preventDefault();
                openLightbox(
                    trigger.dataset.photoUrl,
                    trigger.dataset.faceChips,
                    trigger.dataset.faceBboxes || '[]',
                    trigger.dataset.photoId || '',
                    trigger.dataset.collection || '',
                    trigger.dataset.date || ''
                );
                return;
            }
            // Close via X button
            if (e.target.closest('[data-action="close-lightbox"]')) {
                closeLightbox();
                return;
            }
            // Close via background click
            if (e.target.closest('[data-action="close-lightbox-bg"]') && e.target === lightbox) {
                closeLightbox();
                return;
            }
        });

        // Escape key closes lightbox
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !lightbox.classList.contains('hidden')) {
                closeLightbox();
            }
        });

        // Scroll-zoom on desktop
        lbImg.addEventListener('wheel', function(e) {
            e.preventDefault();
            scale = Math.max(0.5, Math.min(5, scale + (e.deltaY > 0 ? -0.15 : 0.15)));
            lbImg.style.transform = 'scale(' + scale + ')';
        }, {passive: false});

        // Pinch-to-zoom on mobile
        var lastDist = 0;
        lbImg.addEventListener('touchstart', function(e) {
            if (e.touches.length === 2) {
                var dx = e.touches[0].clientX - e.touches[1].clientX;
                var dy = e.touches[0].clientY - e.touches[1].clientY;
                lastDist = Math.sqrt(dx * dx + dy * dy);
            }
        }, {passive: true});
        lbImg.addEventListener('touchmove', function(e) {
            if (e.touches.length === 2) {
                e.preventDefault();
                var dx = e.touches[0].clientX - e.touches[1].clientX;
                var dy = e.touches[0].clientY - e.touches[1].clientY;
                var dist = Math.sqrt(dx * dx + dy * dy);
                if (lastDist > 0) {
                    var delta = (dist - lastDist) * 0.005;
                    scale = Math.max(0.5, Math.min(5, scale + delta));
                    lbImg.style.transform = 'scale(' + scale + ')';
                }
                lastDist = dist;
            }
        }, {passive: false});
        lbImg.addEventListener('touchend', function() { lastDist = 0; });
    })();
    """
    )


@rt("/identify/{person_a}/match/{person_b}")
def get(person_a: str, person_b: str, sess=None, request=None):
    """
    Shareable match confirmation page — 'Are these the same person?'

    Shows two faces side by side with source photos for comparison.
    No login required. This is the core crowdsourcing mechanism.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    ident_a = _main_mod._safe_get_identity(registry, person_a)
    ident_b = _main_mod._safe_get_identity(registry, person_b)

    if not ident_a or not ident_b:
        html_404 = to_xml(Title("People Not Found")) + to_xml(
            Main(
                Div(H2("One or both people not found", cls="text-xl text-white"), cls="text-center py-20"),
                cls="min-h-screen bg-slate-900",
            )
        )
        return HTMLResponse(html_404, status_code=404)

    _main_mod._build_caches()
    crop_files = _main_mod.get_crop_files()
    name_a = ensure_utf8_display(ident_a.get("name", "Unknown"))
    name_b = ensure_utf8_display(ident_b.get("name", "Unknown"))
    display_a = name_a if not name_a.startswith("Unidentified") else "Person A"
    display_b = name_b if not name_b.startswith("Unidentified") else "Person B"

    # Get face crops
    faces_a = ident_a.get("anchor_ids", []) + ident_a.get("candidate_ids", [])
    faces_b = ident_b.get("anchor_ids", []) + ident_b.get("candidate_ids", [])
    best_a = _main_mod.get_best_face_id(faces_a)
    best_b = _main_mod.get_best_face_id(faces_b)
    crop_a = _main_mod.resolve_face_image_url(best_a, crop_files) if best_a and crop_files else None
    crop_b = _main_mod.resolve_face_image_url(best_b, crop_files) if best_b and crop_files else None

    # Source photo info
    photo_id_a = _main_mod.get_photo_id_for_face(best_a) if best_a else None
    photo_id_b = _main_mod.get_photo_id_for_face(best_b) if best_b else None
    photo_data_a = _main_mod.get_photo_metadata(photo_id_a) if photo_id_a else None
    photo_data_b = _main_mod.get_photo_metadata(photo_id_b) if photo_id_b else None
    collection_a = (photo_data_a or {}).get("collection", "")
    collection_b = (photo_data_b or {}).get("collection", "")
    date_a, _, _ = _main_mod._get_date_badge(photo_id_a) if photo_id_a else (None, None, None)
    date_b, _, _ = _main_mod._get_date_badge(photo_id_b) if photo_id_b else (None, None, None)

    def _face_card(crop_url, display_name, collection, date_text, pid, state, all_faces=None, crop_files_ref=None):
        """Build a face card with optional carousel for multi-face identities."""
        meta_items = []
        if collection:
            meta_items.append(P(collection, cls="text-sm sm:text-xs text-slate-400 text-center"))
        if date_text:
            meta_items.append(P(date_text, cls="text-sm sm:text-xs text-slate-500 text-center"))
        # Link to person page (CONFIRMED) or identify page (all others)
        person_href = f"{nav_prefix}/person/{pid}" if state == "CONFIRMED" else f"{nav_prefix}/identify/{pid}"
        profile_label = f"View {display_name}'s Profile" if state == "CONFIRMED" else f"Help Identify {display_name}"

        # Build face data for carousel (if multiple faces)
        face_data_list = []
        if all_faces and crop_files_ref and len(all_faces) > 1:
            for fid_entry in all_faces:
                fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
                furl = _main_mod.resolve_face_image_url(fid, crop_files_ref)
                if furl:
                    fpid = _main_mod.get_photo_id_for_face(fid)
                    face_data_list.append({"crop_url": furl, "photo_id": fpid or ""})

        has_carousel = len(face_data_list) > 1

        face_img = (
            Img(
                src=crop_url,
                alt=display_name,
                id=f"face-img-{pid}",
                cls="w-40 h-40 sm:w-52 sm:h-52 rounded-2xl object-cover border-2 border-slate-700 mx-auto shadow-lg"
                " transition-transform duration-200 hover:scale-105 hover:shadow-[0_0_12px_rgba(255,191,0,0.5)]",
            )
            if crop_url
            else Div(
                Span("?", cls="text-5xl text-slate-500"),
                cls="w-40 h-40 sm:w-52 sm:h-52 rounded-2xl bg-slate-800 border-2 border-slate-700 flex items-center justify-center mx-auto",
            )
        )

        # Carousel navigation arrows
        carousel_el = None
        if has_carousel:
            import json as json_mod

            carousel_el = Div(
                Button(
                    NotStr("&#8249;"),
                    cls="w-8 h-8 bg-slate-700/80 hover:bg-slate-600 text-white rounded-full flex items-center justify-center text-xl sm:text-lg transition-colors",
                    data_action="face-carousel-prev",
                    data_target=pid,
                    type="button",
                    aria_label="Previous face",
                ),
                Span(f"1 of {len(face_data_list)}", id=f"face-counter-{pid}", cls="text-sm sm:text-xs text-slate-400"),
                Button(
                    NotStr("&#8250;"),
                    cls="w-8 h-8 bg-slate-700/80 hover:bg-slate-600 text-white rounded-full flex items-center justify-center text-xl sm:text-lg transition-colors",
                    data_action="face-carousel-next",
                    data_target=pid,
                    type="button",
                    aria_label="Next face",
                ),
                cls="flex items-center justify-center gap-3 mt-2",
                data_faces=json_mod.dumps(face_data_list),
                data_idx="0",
                id=f"face-carousel-{pid}",
            )

        return Div(
            A(face_img, href=person_href, title=f"View {display_name}"),
            carousel_el,
            A(
                display_name,
                href=person_href,
                cls="text-sm text-slate-200 mt-3 text-center font-semibold block hover:text-indigo-400 transition-colors",
            ),
            *meta_items,
            A(
                profile_label + " →",
                href=person_href,
                cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 text-center mt-2 block transition-colors",
            ),
            cls="flex flex-col items-center",
        )

    # Community response counts
    resp_counts = _main_mod._get_match_response_counts(person_a, person_b)
    response_summary = None
    if resp_counts["total"] > 0:
        parts = []
        if resp_counts["yes"]:
            parts.append(Span(f"{resp_counts['yes']} Yes", cls="text-emerald-400 font-medium"))
        if resp_counts["no"]:
            parts.append(Span(f"{resp_counts['no']} No", cls="text-rose-400 font-medium"))
        if resp_counts["unsure"]:
            parts.append(Span(f"{resp_counts['unsure']} Not Sure", cls="text-slate-400 font-medium"))
        response_summary = Div(
            P(
                f"{resp_counts['total']} {'person has' if resp_counts['total'] == 1 else 'people have'} weighed in",
                cls="text-sm text-slate-400 text-center mb-1",
            ),
            Div(
                *[Span(p, Span(" · ", cls="text-slate-600")) if i < len(parts) - 1 else p for i, p in enumerate(parts)],
                cls="flex items-center justify-center gap-1 text-sm",
            ),
            cls="mt-4 pt-3 border-t border-slate-700/50",
        )

    # Response form with name/note fields
    respond_url = f"/api/identify/{person_a}/match/{person_b}/respond"
    response_area = Div(
        H3("What do you think?", cls="text-xl sm:text-lg font-serif font-semibold text-white text-center mb-2"),
        P("Your knowledge helps preserve family history.", cls="text-sm text-slate-400 text-center mb-6"),
        # Vote buttons
        Div(
            Button(
                "Yes, Same Person",
                hx_post=respond_url,
                hx_include="#match-form-fields",
                hx_vals='{"answer": "yes"}',
                hx_target="#match-response-area",
                hx_swap="innerHTML",
                cls="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg transition-colors min-h-[44px]",
            ),
            Button(
                "No, Different People",
                hx_post=respond_url,
                hx_include="#match-form-fields",
                hx_vals='{"answer": "no"}',
                hx_target="#match-response-area",
                hx_swap="innerHTML",
                cls="px-6 py-3 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg transition-colors min-h-[44px]",
            ),
            Button(
                "Not Sure",
                hx_post=respond_url,
                hx_include="#match-form-fields",
                hx_vals='{"answer": "unsure"}',
                hx_target="#match-response-area",
                hx_swap="innerHTML",
                cls="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-lg transition-colors min-h-[44px]",
            ),
            cls="flex flex-wrap justify-center gap-3 mb-6",
        ),
        # Optional name/note fields
        Div(
            Div(
                Label("Your name (optional)", fr="responder_name", cls="text-sm sm:text-xs text-slate-500 block mb-1"),
                Input(
                    type="text",
                    name="responder_name",
                    id="responder_name",
                    placeholder="e.g. Cousin Sarah",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                ),
                cls="flex-1",
            ),
            Div(
                Label(
                    "How do you know? (optional)",
                    fr="responder_note",
                    cls="text-sm sm:text-xs text-slate-500 block mb-1",
                ),
                Input(
                    type="text",
                    name="responder_note",
                    id="responder_note",
                    placeholder="e.g. That's my uncle Marco",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                ),
                cls="flex-1",
            ),
            id="match-form-fields",
            cls="flex flex-col sm:flex-row gap-3",
        ),
        response_summary,
        id="match-response-area",
        cls="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50",
    )

    # Source photo cards
    source_photos = []
    src_photo_a = _match_source_photo_card(
        best_a, photo_id_a, f"Photo of {display_a}", registry=registry, crop_files=crop_files, nav_prefix=nav_prefix
    )
    src_photo_b = _match_source_photo_card(
        best_b, photo_id_b, f"Photo of {display_b}", registry=registry, crop_files=crop_files, nav_prefix=nav_prefix
    )
    if src_photo_a or src_photo_b:
        source_photos_content = []
        if src_photo_a:
            source_photos_content.append(Div(src_photo_a, cls="flex-1 min-w-0"))
        if src_photo_b:
            source_photos_content.append(Div(src_photo_b, cls="flex-1 min-w-0"))
        source_photos = [
            Div(
                H3("Source Photos", cls="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4"),
                Div(*source_photos_content, cls="grid grid-cols-1 sm:grid-cols-2 gap-6"),
                cls="mt-10 pt-6 border-t border-slate-700/30",
            )
        ]

    # Share button
    share_url = f"{_main_mod.SITE_URL}/identify/{person_a}/match/{person_b}"
    share_btn = Button(
        "Share This Match",
        cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
        data_action="share-photo",
        data_share_url=share_url,
        data_share_title="Are these the same person?",
        data_share_text="Help us confirm if these two faces from the Rhodesli Heritage Archive are the same person.",
    )

    # OG tags
    og_image = crop_a or ""
    if og_image and not og_image.startswith("http"):
        og_image = f"{_main_mod.SITE_URL}{og_image}"
    og_meta = (
        Meta(property="og:title", content="Are these the same person? — Rhodesli"),
        Meta(
            property="og:description",
            content="Help us confirm if these two faces are the same person in the Rhodes Jewish Heritage Archive.",
        ),
        Meta(property="og:image", content=og_image),
        Meta(property="og:url", content=share_url),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
    )

    nav_links = _main_mod._public_nav_links(user=user, community_slug=community_slug)
    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    # Admin summary of community responses
    admin_summary = None
    if is_admin and resp_counts["total"] > 0:
        admin_summary = Div(
            P(
                f"Community: {resp_counts['yes']} Yes, {resp_counts['no']} No, {resp_counts['unsure']} Unsure",
                cls="text-sm sm:text-xs text-amber-400 text-center",
            ),
            cls="bg-amber-900/20 border border-amber-800/30 rounded-lg px-3 py-2 mt-4",
        )

    # Build "Explore the Archive" section with contextual links
    explore_links = []
    # Link to the collection if we have one
    primary_collection = collection_a or collection_b
    if primary_collection:
        col_slug = _main_mod._collection_slug(primary_collection)
        explore_links.append(
            A(
                f"See all photos in {primary_collection}",
                href=f"{nav_prefix}/collection/{col_slug}",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
        )
    explore_links.extend(
        [
            A(
                "Browse identified people",
                href=f"{nav_prefix}/people",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
            A(
                "Help identify more faces",
                href=f"{nav_prefix}/",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
            A(
                "View the timeline",
                href=f"{nav_prefix}/timeline",
                cls="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700 min-h-[44px] flex items-center",
            ),
        ]
    )
    explore_section = Div(
        H3("Explore the Archive", cls="text-xl sm:text-lg font-serif font-semibold text-white text-center mb-4"),
        P(
            "There are hundreds more photos and faces waiting to be identified.",
            cls="text-sm text-slate-400 text-center mb-5",
        ),
        Div(*explore_links, cls="flex flex-wrap justify-center gap-3"),
        cls="mt-10 pt-6 border-t border-slate-700/30",
    )

    # Lightbox modal (hidden by default)
    lightbox = Div(
        Button(
            NotStr("&times;"),
            cls="absolute top-4 right-4 text-white text-3xl bg-transparent border-none cursor-pointer z-[1001] hover:text-slate-300 transition-colors leading-none",
            data_action="close-lightbox",
            aria_label="Close lightbox",
        ),
        Div(
            # Photo container with face overlays
            Div(
                Img(
                    id="match-lightbox-img",
                    src="",
                    alt="Full size photo",
                    cls="max-w-[90vw] max-h-[65vh] object-contain rounded-lg shadow-2xl",
                ),
                Div(id="match-lightbox-overlays", cls="absolute inset-0"),
                cls="relative inline-block",
                id="match-lightbox-photo-wrap",
            ),
            # Metadata bar
            Div(id="match-lightbox-meta", cls="mt-3 text-center"),
            # Face chips
            Div(id="match-lightbox-faces", cls="mt-3"),
            cls="flex flex-col items-center max-w-[90vw]",
        ),
        id="match-lightbox",
        cls="fixed inset-0 bg-black/90 z-[1000] flex items-center justify-center hidden overflow-y-auto py-8",
        data_action="close-lightbox-bg",
    )

    return (
        Title("Are these the same person? — Rhodesli"),
        *og_meta,
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl sm:text-lg font-serif font-bold text-white"), href="/"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    H1(
                        "Are these the same person?",
                        cls="text-2xl sm:text-3xl font-serif font-bold text-white text-center mb-8",
                    ),
                    # Side-by-side faces with carousel if multi-face
                    Div(
                        _face_card(
                            crop_a,
                            display_a,
                            collection_a,
                            date_a,
                            person_a,
                            ident_a.get("state", "INBOX"),
                            all_faces=faces_a,
                            crop_files_ref=crop_files,
                        ),
                        Div(
                            Span("vs", cls="text-slate-500 text-2xl font-bold"),
                            cls="flex items-center justify-center px-4 sm:px-8",
                        ),
                        _face_card(
                            crop_b,
                            display_b,
                            collection_b,
                            date_b,
                            person_b,
                            ident_b.get("state", "INBOX"),
                            all_faces=faces_b,
                            crop_files_ref=crop_files,
                        ),
                        cls="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6 mb-10",
                    ),
                    # Voting area
                    response_area,
                    admin_summary,
                    # Source photos
                    *source_photos,
                    # Explore the archive
                    explore_section,
                    # Share
                    Div(
                        share_btn,
                        cls="flex items-center justify-center mt-8 mb-4",
                    ),
                    P(
                        "Help us identify people in the Rhodesli archive — your family knowledge matters.",
                        cls="text-sm sm:text-xs text-slate-500 text-center mb-4",
                    ),
                    cls="max-w-3xl mx-auto pt-10 pb-16 px-6",
                ),
            ),
            lightbox,
            cls="min-h-screen bg-slate-900 text-white",
        ),
        _main_mod._share_script(),
        _match_lightbox_script(nav_prefix=nav_prefix),
        _face_carousel_script(),
    )


def _face_carousel_script():
    """JS for face carousel navigation on match pages and person pages."""
    return Script("""
    (function() {
        document.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-action="face-carousel-prev"], [data-action="face-carousel-next"]');
            if (!btn) return;
            e.preventDefault();
            var targetId = btn.dataset.target;
            var carousel = document.getElementById('face-carousel-' + targetId);
            if (!carousel) return;
            var faces;
            try { faces = JSON.parse(carousel.dataset.faces); } catch(err) { return; }
            if (!faces || faces.length < 2) return;
            var idx = parseInt(carousel.dataset.idx || '0', 10);
            if (btn.dataset.action === 'face-carousel-next') {
                idx = (idx + 1) % faces.length;
            } else {
                idx = (idx - 1 + faces.length) % faces.length;
            }
            carousel.dataset.idx = idx;
            // Update face image
            var img = document.getElementById('face-img-' + targetId);
            if (img) img.src = faces[idx].crop_url;
            // Update counter
            var counter = document.getElementById('face-counter-' + targetId);
            if (counter) counter.textContent = (idx + 1) + ' of ' + faces.length;
        });
    })();
    """)


# Rate limit storage for match responses (IP -> list of timestamps)
_match_rate_limit: dict = {}


@rt("/api/identify/{person_a}/match/{person_b}/respond")
def post(
    person_a: str,
    person_b: str,
    answer: str = "",
    responder_name: str = "",
    responder_note: str = "",
    sess=None,
    request=None,
):
    """Save a match confirmation response. No login required. Rate limited."""
    if answer not in ("yes", "no", "unsure"):
        return Div(P("Invalid response.", cls="text-amber-400 text-sm"))

    # Rate limiting: max 10 responses per IP per hour
    import hashlib as _rl_hashlib

    client_ip = ""
    if request:
        client_ip = getattr(request.client, "host", "") if request.client else ""
    ip_hash = _rl_hashlib.sha256(client_ip.encode()).hexdigest()[:12] if client_ip else "unknown"
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    _match_rate_limit[ip_hash] = [t for t in _match_rate_limit.get(ip_hash, []) if t > cutoff]
    if len(_match_rate_limit.get(ip_hash, [])) >= 10:
        return Div(
            P(
                "You've submitted many responses recently. Please try again later.",
                cls="text-amber-400 text-sm text-center py-4",
            )
        )
    _match_rate_limit.setdefault(ip_hash, []).append(now)

    responses = _main_mod._load_identification_responses()
    responses["responses"].append(
        {
            "type": "match_confirmation",
            "person_a": person_a,
            "person_b": person_b,
            "answer": answer,
            "responder_name": responder_name.strip()[:100] if responder_name else "",
            "responder_note": responder_note.strip()[:500] if responder_note else "",
            "timestamp": now.isoformat(),
            "ip_hash": ip_hash,
            "status": "pending",
        }
    )
    _main_mod._save_identification_responses(responses)

    messages = {
        "yes": "Thank you! You confirmed these are the same person. An admin will review.",
        "no": "Thank you! You indicated these are different people. An admin will review.",
        "unsure": "Thank you for looking! We'll ask others for confirmation.",
    }
    # Show updated response count
    counts = _main_mod._get_match_response_counts(person_a, person_b)
    count_text = f"{counts['total']} {'person has' if counts['total'] == 1 else 'people have'} weighed in so far."
    return Div(
        P(messages[answer], cls="text-emerald-400 text-sm text-center py-2"),
        P(count_text, cls="text-slate-400 text-sm sm:text-xs text-center mt-1"),
    )


def _sort_photos(photos: list, sort_by: str) -> list:
    """Sort photo dicts by the given sort criterion.

    Sort options:
      - upload_newest / upload_oldest: by upload_date ISO string
      - newest / oldest: by estimated year from date_labels
      - filename_az: alphabetical by filename
      - most_faces: descending face count
      - by_source: alphabetical by collection then filename
      - collection: alphabetical by collection/source then filename
      - recently_uploaded: legacy alias for upload_newest
    """
    if sort_by in ("upload_newest", "upload_oldest", "recently_uploaded"):
        newest_first = sort_by in ("upload_newest", "recently_uploaded")
        no_date = "9999-99-99T99:99:99+00:00"

        def _upload_key_newest(p):
            upload_date = p.get("upload_date") or ""
            created_at = p.get("created_at") or ""
            updated_at = p.get("updated_at") or ""
            primary_timestamp = upload_date or created_at or updated_at
            photo_index_order = p.get("photo_index_order")
            return (
                1 if primary_timestamp else 0,
                primary_timestamp,
                upload_date,
                created_at,
                updated_at,
                photo_index_order if photo_index_order is not None else -1,
                p.get("photo_id", ""),
                p.get("filename", ""),
            )

        def _upload_key_oldest(p):
            upload_date = p.get("upload_date") or ""
            created_at = p.get("created_at") or ""
            updated_at = p.get("updated_at") or ""
            primary_timestamp = upload_date or created_at or updated_at or no_date
            photo_index_order = p.get("photo_index_order")
            return (
                0 if (upload_date or created_at or updated_at) else 1,
                primary_timestamp,
                upload_date or no_date,
                created_at or no_date,
                updated_at or no_date,
                photo_index_order if photo_index_order is not None else 10**9,
                p.get("photo_id", ""),
                p.get("filename", ""),
            )

        photos.sort(key=_upload_key_newest if newest_first else _upload_key_oldest, reverse=newest_first)
    elif sort_by in ("oldest", "newest"):
        labels = _main_mod._load_date_labels()
        NO_DATE = 9999 if sort_by == "oldest" else 0

        def _year_key(p):
            label = labels.get(p["photo_id"], {})
            year = label.get("best_year_estimate") or label.get("estimated_decade") or 0
            return year if year else NO_DATE

        photos.sort(key=_year_key, reverse=(sort_by == "newest"))
    elif sort_by == "filename_az":
        photos.sort(key=lambda p: p.get("filename", "").lower())
    elif sort_by == "most_faces":
        photos.sort(key=lambda p: p["face_count"], reverse=True)
    elif sort_by == "by_source":
        photos.sort(key=lambda p: (p.get("collection") or "zzz", p["filename"]))
    elif sort_by == "collection":
        photos.sort(key=lambda p: (p.get("collection") or p.get("source") or "zzz", p["filename"]))
    return photos


def _build_photo_cards(photos: list, masonry: bool = False, nav_prefix: str = "", is_admin: bool = False) -> list:
    """Build photo card elements for a list of photo dicts.

    Args:
        photos: List of photo dicts with photo_id, filename, face_count, etc.
        masonry: If True, render cards at natural aspect ratio for masonry layout.
        is_admin: If True, show upload provenance metadata (uploader, import dates).
    """
    cards = []
    for photo in photos:
        provenance = _main_mod._get_upload_provenance_display(photo, is_admin=is_admin)
        badge_cls = (
            "bg-emerald-600/80"
            if photo["confirmed_count"] == photo["face_count"] and photo["face_count"] > 0
            else "bg-black/70"
        )
        date_text, date_conf, date_tooltip = _main_mod._get_date_badge(photo["photo_id"])
        date_badge = None
        if date_text:
            if date_conf == "high":
                date_cls = "bg-amber-800/80 text-amber-100"
            elif date_conf == "medium":
                date_cls = "bg-amber-800/50 border border-amber-600/50 text-amber-200/90"
            else:
                date_cls = "border border-dashed border-amber-600/40 text-amber-400/60"
            date_badge = Span(
                date_text,
                cls=f"absolute bottom-2 left-2 text-[11px] font-serif px-1.5 py-0.5 rounded backdrop-blur-sm {date_cls}",
                title=date_tooltip,
                data_testid="date-badge",
                data_confidence=date_conf,
            )
        match_label = None
        if photo.get("match_reason"):
            match_label = Div(
                Span(f"Matched: {photo['match_reason']}", cls="text-[10px] text-indigo-300/70 italic"),
                cls="px-2 pb-1",
                data_testid="match-reason",
            )

        # For masonry layout, use natural aspect ratio; otherwise force 4:3
        w = photo.get("width", 0)
        h = photo.get("height", 0)
        if masonry and w > 0 and h > 0:
            img_container_cls = "overflow-hidden relative"
            # Use aspect-ratio CSS for natural dimensions
            aspect_style = f"aspect-ratio: {w}/{h};"
        else:
            img_container_cls = "aspect-[4/3] overflow-hidden relative"
            aspect_style = ""

        # Masonry cards need break-inside: avoid
        card_cls = "bg-slate-800 rounded-lg border border-slate-700 overflow-hidden hover:border-slate-500 transition-colors group block"
        if masonry:
            card_cls += " mb-4"
            card_style = "break-inside: avoid;"
        else:
            card_style = ""

        cards.append(
            A(
                Div(
                    Img(
                        src=photo_url(photo["filename"]),
                        cls="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300",
                        loading="lazy",
                        alt=f"Archive photo {photo['filename']}",
                    ),
                    Div(
                        f"{photo['confirmed_count']}/{photo['face_count']}"
                        if photo["confirmed_count"] > 0
                        else f"{photo['face_count']} face{'s' if photo['face_count'] != 1 else ''}",
                        cls=f"absolute top-2 right-2 text-white text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 rounded-full backdrop-blur-sm {badge_cls}",
                    )
                    if photo["face_count"] > 0
                    else None,
                    date_badge,
                    cls=img_container_cls,
                    style=aspect_style if aspect_style else None,
                ),
                Div(
                    P(photo["collection"] or "", cls="text-sm sm:text-xs text-slate-500 leading-snug")
                    if photo["collection"]
                    else None,
                    P(provenance["headline"], cls="text-[11px] text-slate-400 leading-tight") if provenance else None,
                    P(provenance["subline"], cls="text-[10px] text-slate-500 leading-tight")
                    if provenance and provenance.get("subline")
                    else None,
                    cls="p-2 space-y-0.5",
                )
                if photo["collection"] or provenance
                else None,
                match_label,
                href=f"{nav_prefix}/photo/{photo['photo_id']}",
                cls=card_cls,
                style=card_style if card_style else None,
            )
        )
    return cards


@rt("/photos")
def get(
    filter_collection: str = "",
    sort_by: str = "upload_newest",
    decade: int = None,
    search_q: str = "",
    tag: str = "",
    sess=None,
    request=None,
):
    """
    Public photos browsing page — grid of all archive photos.

    No authentication required. Each photo links to /photo/{id}.
    Supports decade filtering, keyword search, and tag filtering via query params.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    # G10 (Session 168 self-audit): community-aware OG copy so a non-Rhodes /c/<slug>/photos
    # gallery doesn't leak "Jewish community of Rhodes" into its share preview.
    _photos_community = getattr(request.state, "community", None) if request else None
    _photos_community_prefixed = getattr(request.state, "community_prefixed", False) if request else False
    _photos_is_non_rhodes = bool(
        _photos_community_prefixed
        and _photos_community
        and community_slug != "rhodes"
        and not _photos_community.get("is_default")
    )
    _photos_community_name = (
        ((_photos_community.get("name") or "").strip() if _photos_is_non_rhodes else "Jewish community of Rhodes")
        or "Jewish community of Rhodes"
    )

    _main_mod._build_caches()
    registry = _main_mod.load_registry()

    # Get decade and tag counts for filter pills
    decade_counts = _main_mod._get_decade_counts()
    tag_counts = _main_mod._get_tag_counts()

    # Search-based filtering (uses search index for text, decade, tag)
    search_results = None
    search_photo_ids = None
    if search_q or decade or tag:
        search_results = _main_mod._search_photos(query=search_q, decade=decade, tag=tag)
        search_photo_ids = {r.get("cache_photo_id", r["photo_id"]): r.get("match_reason") for r in search_results}

    # Gather photos with metadata
    photos = []
    collections_set = set()
    for photo_id_val, photo_data in (_main_mod._photo_cache or {}).items():
        collection = photo_data.get("collection", "")
        if collection:
            collections_set.add(collection)
        # Apply collection filter
        if filter_collection and collection != filter_collection:
            continue
        # Apply search/decade/tag filter
        if search_photo_ids is not None and photo_id_val not in search_photo_ids:
            continue

        face_count = len(photo_data.get("faces", []))
        confirmed_count = 0
        for face in photo_data.get("faces", []):
            identity = _main_mod.get_identity_for_face(registry, face.get("face_id", ""))
            if identity and identity.get("state") == "CONFIRMED":
                confirmed_count += 1

        photos.append(
            {
                "photo_id": photo_id_val,
                "filename": photo_data.get("filename", "unknown"),
                "collection": collection,
                "face_count": face_count,
                "confirmed_count": confirmed_count,
                "match_reason": search_photo_ids.get(photo_id_val) if search_photo_ids else None,
                "width": photo_data.get("width", 0),
                "height": photo_data.get("height", 0),
                "uploaded_by": photo_data.get("uploaded_by", ""),
                "upload_date": photo_data.get("upload_date", ""),
                "created_at": photo_data.get("created_at", ""),
                "updated_at": photo_data.get("updated_at", ""),
                "photo_index_order": photo_data.get("photo_index_order"),
            }
        )

    collections = sorted(collections_set)

    # Sort
    photos = _main_mod._sort_photos(photos, sort_by)

    # Build photo cards (paginated — 24 per page for lazy loading)
    PHOTOS_PER_PAGE = 24
    _is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    photo_cards = _build_photo_cards(photos[:PHOTOS_PER_PAGE], masonry=True, nav_prefix=nav_prefix, is_admin=_is_admin)

    # Lazy loading sentinel: loads next page when scrolled into view
    total_pages = (len(photos) + PHOTOS_PER_PAGE - 1) // PHOTOS_PER_PAGE
    if total_pages > 1:
        from urllib.parse import urlencode as _ue

        _lazy_params = {
            "page": 2,
            "filter_collection": filter_collection,
            "sort_by": sort_by,
            "search_q": search_q,
            "tag": tag,
        }
        if decade:
            _lazy_params["decade"] = decade
        _lazy_params = {k: v for k, v in _lazy_params.items() if v}
        photo_cards.append(
            Div(
                Div(cls="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"),
                P("Loading more photos...", cls="text-slate-500 text-sm sm:text-xs mt-2"),
                id="photos-lazy-sentinel",
                cls="flex flex-col items-center py-8",
                style="break-inside: avoid; column-span: all;",
                hx_get=f"/api/photos/more?{_ue(_lazy_params)}",
                hx_trigger="revealed",
                hx_swap="outerHTML",
            )
        )

    # Build filter URL helper
    from urllib.parse import quote as _url_quote, urlencode as _url_encode

    def _filter_url(**overrides):
        """Build /photos URL preserving current filters with overrides."""
        params = {"filter_collection": filter_collection, "sort_by": sort_by, "search_q": search_q, "tag": tag}
        if decade:
            params["decade"] = str(decade)
        params.update({k: v for k, v in overrides.items() if v})
        # Remove empty/None params
        params = {k: v for k, v in params.items() if v}
        qs = _url_encode(params)
        return f"/photos?{qs}" if qs else "/photos"

    # Collection + sort dropdowns
    collection_options = [Option("All Collections", value="")]
    for c in collections:
        collection_options.append(Option(c, value=c, selected=(filter_collection == c)))

    sort_options = [
        Option("Upload Date (Newest)", value="upload_newest", selected=(sort_by == "upload_newest")),
        Option("Upload Date (Oldest)", value="upload_oldest", selected=(sort_by == "upload_oldest")),
        Option("Estimated Date (Newest)", value="newest", selected=(sort_by == "newest")),
        Option("Estimated Date (Oldest)", value="oldest", selected=(sort_by == "oldest")),
        Option("Filename (A-Z)", value="filename_az", selected=(sort_by == "filename_az")),
        Option("Most Faces", value="most_faces", selected=(sort_by == "most_faces")),
        Option("By Source", value="by_source", selected=(sort_by == "by_source")),
    ]

    # Decade pills
    decade_pills = [
        A(
            "All",
            href=_filter_url(decade=""),
            cls="px-3 py-1 text-sm sm:text-xs rounded-full transition-colors font-serif "
            + (
                "bg-amber-700 text-white"
                if not decade
                else "bg-slate-800 text-slate-400 hover:text-white border border-slate-700"
            ),
        )
    ]
    for dec, count in decade_counts.items():
        is_active = decade == dec
        decade_pills.append(
            A(
                f"{dec}s ({count})",
                href=_filter_url(decade=str(dec)),
                cls="px-3 py-1 text-sm sm:text-xs rounded-full transition-colors font-serif "
                + (
                    "bg-amber-700 text-white"
                    if is_active
                    else "bg-slate-800 text-slate-400 hover:text-white border border-slate-700"
                ),
                data_testid="decade-pill",
            )
        )

    # Tag pills (top 8)
    top_tags = list(tag_counts.items())[:8]
    tag_pills = []
    for tag_name, tag_count in top_tags:
        display_name = tag_name.replace("_", " ")
        is_active = tag == tag_name
        tag_pills.append(
            A(
                f"{display_name} ({tag_count})",
                href=_filter_url(tag=tag_name if not is_active else ""),
                cls="px-4 py-3 sm:px-2.5 sm:py-1 text-[11px] rounded-full transition-colors "
                + (
                    "bg-indigo-600 text-white"
                    if is_active
                    else "bg-slate-800/60 text-slate-400 hover:text-white border border-slate-700/50"
                ),
                data_testid="tag-pill",
            )
        )

    nav_links = _main_mod._public_nav_links(active="photos", user=user, community_slug=community_slug)

    # Active filter summary
    active_filters = []
    if decade:
        active_filters.append(f"{decade}s")
    if tag:
        active_filters.append(tag.replace("_", " "))
    if search_q:
        active_filters.append(f'"{search_q}"')
    subtitle = f"Showing {len(photos)} photo{'s' if len(photos) != 1 else ''}"
    if active_filters:
        subtitle += f" matching {' + '.join(active_filters)}"

    page_style = Style("""
        html, body { margin: 0; } body { background-color: #0f172a; }
        .masonry-grid { column-count: 1; column-gap: 1rem; }
        @media (min-width: 640px) { .masonry-grid { column-count: 2; } }
        @media (min-width: 1024px) { .masonry-grid { column-count: 3; } }
        @media (min-width: 1280px) { .masonry-grid { column-count: 4; } }
    """)

    return (
        Title("Photos — Rhodesli Heritage Archive"),
        *_main_mod.og_tags(
            "Photos — Rhodesli Heritage Archive",
            f"{len(photos)} historical photographs from the {_photos_community_name}.",
            canonical_url="/photos",
        ),
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    Div(
                        H1("Photos", cls="text-3xl font-serif font-bold text-white mb-2"),
                        _main_mod.share_button(
                            url="/photos",
                            style="link",
                            label="Share",
                            title="Photos — Rhodesli",
                            text="Browse historical photos from the Jewish community of Rhodes",
                        ),
                        cls="flex items-center justify-between",
                    ),
                    P(subtitle, cls="text-slate-400 text-sm"),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-4",
                ),
            ),
            Section(
                Div(
                    # Decade timeline pills
                    Div(*decade_pills, cls="flex flex-wrap gap-2 mb-3") if decade_pills else None,
                    # Search + tag row
                    Div(
                        # Search input
                        Div(
                            Input(
                                type="text",
                                name="search_q",
                                value=search_q,
                                placeholder="Search scenes, text, people...",
                                cls="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5 w-full sm:w-64 focus:ring-1 focus:ring-amber-500/50 focus:border-amber-500/50 placeholder-slate-500",
                                data_testid="photo-search",
                                onkeydown=f"if(event.key==='Enter')window.location.href='/photos?search_q='+encodeURIComponent(this.value)+'&decade={decade or ''}&tag={_url_quote(tag)}&filter_collection={_url_quote(filter_collection)}&sort_by={sort_by}'",
                            ),
                            cls="flex-shrink-0",
                        ),
                        # Tag pills
                        Div(
                            *tag_pills,
                            cls="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-1.5 w-full sm:w-auto text-center",
                        )
                        if tag_pills
                        else None,
                        cls="flex flex-wrap items-center gap-3 mb-3",
                    ),
                    # Collection/sort dropdowns
                    Div(
                        Select(
                            *collection_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection=' + encodeURIComponent(this.value) + '&sort_by={sort_by}&decade={decade or ''}&search_q={_url_quote(search_q)}&tag={_url_quote(tag)}'",
                        ),
                        Select(
                            *sort_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection={_url_quote(filter_collection)}&sort_by=' + this.value + '&decade={decade or ''}&search_q={_url_quote(search_q)}&tag={_url_quote(tag)}'",
                        ),
                        Span(
                            f"{len(photos)} result{'s' if len(photos) != 1 else ''}",
                            cls="text-sm sm:text-xs text-slate-500 ml-auto",
                        ),
                        cls="flex flex-wrap items-center gap-3 mb-6",
                    ),
                    # Photo grid — masonry layout via CSS columns
                    Div(*photo_cards, id="photo-grid", cls="masonry-grid")
                    if photo_cards
                    else Div(
                        P("No photos match your filters.", cls="text-slate-500 text-center py-12"),
                        A(
                            "Clear filters",
                            href="/photos",
                            cls="text-indigo-400 hover:text-indigo-300 text-sm block text-center mt-2",
                        ),
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-sm sm:text-xs text-slate-500 mb-1 font-serif"),
                    P(
                        "Preserving the memory of the Jewish community of Rhodes",
                        cls="text-[10px] text-slate-600 italic",
                    ),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/api/photos/more")
def photos_more(
    page: int = 2,
    filter_collection: str = "",
    sort_by: str = "upload_newest",
    decade: int = None,
    search_q: str = "",
    tag: str = "",
    sess=None,
):
    """HTMX endpoint for infinite scroll — returns next batch of photo cards."""
    from urllib.parse import urlencode as _ue

    PHOTOS_PER_PAGE = 24

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    _is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()

    _main_mod._build_caches()
    registry = _main_mod.load_registry()

    # Replicate same filtering/sorting as /photos
    search_photo_ids = None
    if search_q or decade or tag:
        search_results = _main_mod._search_photos(query=search_q, decade=decade, tag=tag)
        search_photo_ids = {r.get("cache_photo_id", r["photo_id"]): r.get("match_reason") for r in search_results}

    photos = []
    for photo_id_val, photo_data in (_main_mod._photo_cache or {}).items():
        collection = photo_data.get("collection", "")
        if filter_collection and collection != filter_collection:
            continue
        if search_photo_ids is not None and photo_id_val not in search_photo_ids:
            continue
        filename = photo_data.get("filename", "unknown")
        face_count = len(photo_data.get("faces", []))
        confirmed_count = 0
        for face in photo_data.get("faces", []):
            identity = _main_mod.get_identity_for_face(registry, face.get("face_id", ""))
            if identity and identity.get("state") == "CONFIRMED":
                confirmed_count += 1
        photos.append(
            {
                "photo_id": photo_id_val,
                "filename": filename,
                "collection": collection,
                "face_count": face_count,
                "confirmed_count": confirmed_count,
                "match_reason": search_photo_ids.get(photo_id_val) if search_photo_ids else None,
                "width": photo_data.get("width", 0),
                "height": photo_data.get("height", 0),
                "uploaded_by": photo_data.get("uploaded_by", ""),
                "upload_date": photo_data.get("upload_date", ""),
                "created_at": photo_data.get("created_at", ""),
                "updated_at": photo_data.get("updated_at", ""),
                "photo_index_order": photo_data.get("photo_index_order"),
            }
        )

    photos = _main_mod._sort_photos(photos, sort_by)

    # Paginate
    start = (page - 1) * PHOTOS_PER_PAGE
    end = start + PHOTOS_PER_PAGE
    page_photos = photos[start:end]

    if not page_photos:
        return ""  # No more photos

    cards = _build_photo_cards(page_photos, masonry=True, nav_prefix=nav_prefix, is_admin=_is_admin)

    # Add sentinel for next page if there are more
    total_pages = (len(photos) + PHOTOS_PER_PAGE - 1) // PHOTOS_PER_PAGE
    if page < total_pages:
        _lazy_params = {
            "page": page + 1,
            "filter_collection": filter_collection,
            "sort_by": sort_by,
            "search_q": search_q,
            "tag": tag,
        }
        if decade:
            _lazy_params["decade"] = decade
        _lazy_params = {k: v for k, v in _lazy_params.items() if v}
        cards.append(
            Div(
                Div(cls="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"),
                P("Loading more photos...", cls="text-slate-500 text-sm sm:text-xs mt-2"),
                id="photos-lazy-sentinel",
                cls="flex flex-col items-center py-8",
                style="break-inside: avoid; column-span: all;",
                hx_get=f"/api/photos/more?{_ue(_lazy_params)}",
                hx_trigger="revealed",
                hx_swap="outerHTML",
            )
        )

    return tuple(cards)


@rt("/people")
def get(sort_by: str = "name", sess=None, request=None):
    """
    Public people browsing page — grid of identified people.

    No authentication required. Each person links to /person/{id}.
    No admin actions visible.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"

    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Get confirmed identities with real names
    confirmed = [
        i
        for i in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
    ]

    # Sort
    if sort_by == "photos":
        photo_reg = _main_mod.load_photo_registry()

        def photo_count(identity):
            face_ids = [
                f if isinstance(f, str) else f.get("face_id", "")
                for f in identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            ]
            return len(photo_reg.get_photos_for_faces(face_ids))

        confirmed.sort(key=photo_count, reverse=True)
    elif sort_by == "newest":
        confirmed.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
    else:  # name
        confirmed.sort(key=lambda x: (x.get("name") or "").lower())

    # Build person cards
    person_cards = []
    for identity in confirmed:
        identity_id = identity["identity_id"]
        name = ensure_utf8_display(identity.get("name", ""))
        all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        best_face = _main_mod.get_best_face_id(all_faces)
        crop_url = _main_mod.resolve_face_image_url(best_face, crop_files) if best_face and crop_files else None
        face_count = len(all_faces)

        avatar = (
            Img(
                src=crop_url,
                alt=name,
                cls="w-24 h-24 rounded-full object-cover border-3 border-emerald-500/30",
                onerror="this.style.display='none'",
            )
            if crop_url
            else Div(
                Span(name[0].upper() if name else "?", cls="text-2xl font-serif text-slate-400"),
                cls="w-24 h-24 rounded-full bg-slate-800 border-3 border-slate-700 flex items-center justify-center",
            )
        )

        person_cards.append(
            A(
                avatar,
                P(name, cls="text-sm font-medium text-white mt-3 text-center"),
                P(f"{face_count} {'photo' if face_count == 1 else 'photos'}", cls="text-[10px] text-slate-500 mt-1"),
                href=f"{nav_prefix}/person/{identity_id}",
                cls="flex flex-col items-center p-4 bg-slate-800/50 rounded-xl border border-slate-700 hover:border-emerald-500/30 transition-colors group block",
            )
        )

    sort_options = [
        Option("A-Z", value="name", selected=(sort_by == "name")),
        Option("Most Photos", value="photos", selected=(sort_by == "photos")),
        Option("Newest", value="newest", selected=(sort_by == "newest")),
    ]

    nav_links = _main_mod._public_nav_links(active="people", user=user, community_slug=community_slug)

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    return (
        Title("People — Rhodesli Heritage Archive"),
        *_main_mod.og_tags(
            "People — Rhodesli Heritage Archive",
            f"{len(confirmed)} identified people in the Rhodes heritage archive.",
            canonical_url=f"{nav_prefix}/people",
        ),
        page_style,
        Main(
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/",
                        cls="hover:opacity-90",
                    ),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    Div(
                        H1("People", cls="text-3xl font-serif font-bold text-white mb-2"),
                        _main_mod.share_button(
                            url=f"{nav_prefix}/people",
                            style="link",
                            label="Share",
                            title="People — Rhodesli",
                            text="Browse identified people in the Rhodes heritage archive",
                        ),
                        cls="flex items-center justify-between",
                    ),
                    P(
                        f"{len(confirmed)} identified {'person' if len(confirmed) == 1 else 'people'} in the archive",
                        cls="text-slate-400 text-sm",
                    ),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-6",
                ),
            ),
            Section(
                Div(
                    Div(
                        Span("Sort:", cls="text-sm text-slate-400 mr-2"),
                        Select(
                            *sort_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5",
                            onchange=f"window.location.href='{nav_prefix}/people?sort_by=' + this.value",
                        ),
                        cls="flex items-center gap-2 mb-6",
                    ),
                    Div(
                        *person_cards,
                        cls="grid grid-cols-1 sm:grid-cols-1 sm:grid-cols-2 md:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4",
                    )
                    if person_cards
                    else Div(
                        P(
                            "No identified people yet. Help us identify faces in the archive!",
                            cls="text-slate-500 text-center py-12",
                        ),
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            # CTA
            Section(
                Div(
                    H3("Can you help identify someone?", cls="text-xl sm:text-lg font-serif text-white mb-2"),
                    P("Browse the photos and let us know if you recognize anyone.", cls="text-slate-400 text-sm mb-4"),
                    A(
                        "Browse Photos",
                        href=f"{nav_prefix}/photos",
                        cls="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
                    ),
                    cls="text-center",
                ),
                cls="py-12 border-t border-slate-800",
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-sm sm:text-xs text-slate-500 mb-1 font-serif"),
                    P(
                        "Preserving the memory of the Jewish community of Rhodes",
                        cls="text-[10px] text-slate-600 italic",
                    ),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/people/{identity_id}/similar")
def get(identity_id: str, sess=None, request=None):
    """Find Similar — full-page hero + grid layout (AD-186)."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    name = ensure_utf8_display(identity.get("name", ""))
    state = identity.get("state", "INBOX")
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    total_faces = len(all_face_ids)
    target_proposals = _main_mod._get_proposal_targets_for_identity(identity_id) if is_admin else []

    # Get best face for hero
    crop_files = _main_mod.get_crop_files()
    best_face = _main_mod.get_best_face_id(all_face_ids) if all_face_ids else (all_face_ids[0] if all_face_ids else "")
    face_id = best_face if isinstance(best_face, str) else best_face.get("face_id", "") if best_face else ""
    hero_url = _main_mod.resolve_face_image_url(face_id, crop_files) if face_id else ""

    # Find similar faces
    face_data = _main_mod.get_face_data()
    photo_registry = _main_mod.load_photo_registry()
    neighbors = []
    try:
        from core.neighbors import find_nearest_neighbors

        neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=20)
    except Exception as e:
        logging.warning(f"Find similar failed: {e}")

    # Enhance with crop URLs and state
    for n in neighbors:
        nid = n["identity_id"]
        try:
            n_ident = registry.get_identity(nid)
            n_faces = n_ident.get("anchor_ids", []) + n_ident.get("candidate_ids", [])
            n_best = _main_mod.get_best_face_id(n_faces) if n_faces else (n_faces[0] if n_faces else "")
            n_fid = n_best if isinstance(n_best, str) else n_best.get("face_id", "") if n_best else ""
            n["crop_url"] = _main_mod.resolve_face_image_url(n_fid, crop_files)
            n["name"] = ensure_utf8_display(n_ident.get("name", ""))
            n["state"] = n_ident.get("state", "INBOX")
            n["face_count"] = len(n_faces)
        except KeyError:
            n["crop_url"] = ""
            n["name"] = "Unknown"
            n["state"] = "INBOX"
            n["face_count"] = 0

    # Confidence tier for distance — color-coded labels
    from core.confidence import confidence_tier_from_distance

    # Build result grid cards
    result_cards = []
    for n in neighbors:
        if not n.get("crop_url"):
            continue
        nid = n["identity_id"]
        tier_label, tier_cls = confidence_tier_from_distance(n.get("distance", 99))
        admin_actions = []
        if is_admin:
            admin_actions.append(
                Button(
                    "Merge",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 bg-indigo-600 text-white rounded hover:bg-indigo-500 transition-colors",
                    hx_post=(
                        f"{nav_prefix}/api/identity/{identity_id}/merge/{nid}"
                        f"?source=similar_page&return_to={nav_prefix}/people/{identity_id}/similar"
                    ),
                    hx_target=f"#search-result-{nid}",
                    hx_swap="outerHTML",
                    hx_confirm=f"Merge {n.get('name', 'this identity')} into {name or 'this identity'}?",
                    type="button",
                )
            )
            admin_actions.append(
                Button(
                    "Not Same",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 border border-slate-500 text-slate-300 rounded hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/50 transition-colors",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/reject-match/{nid}",
                    hx_target=f"#search-result-{nid}",
                    hx_swap="outerHTML",
                    type="button",
                )
            )
        card = Div(
            A(
                Img(src=n["crop_url"], alt=n.get("name", ""), cls="w-full h-full object-cover", loading="lazy"),
                href=f"{nav_prefix}/person/{nid}",
                cls="block aspect-[3/4] overflow-hidden bg-slate-800",
            ),
            Div(
                Span(n.get("name", "Unknown"), cls="text-sm text-white font-medium truncate block"),
                Div(
                    Span(tier_label, cls=f"text-sm sm:text-xs px-2 py-0.5 rounded-full text-white {tier_cls}"),
                    Span(f"{n.get('distance', 0):.2f}", cls="text-sm sm:text-xs text-slate-500 ml-2")
                    if is_admin
                    else None,
                    cls="flex items-center gap-1 mt-1",
                ),
                Span(
                    f"{n.get('face_count', 0)} face{'s' if n.get('face_count', 0) != 1 else ''}",
                    cls="text-sm sm:text-xs text-slate-400 mt-0.5 block",
                )
                if n.get("face_count", 0) > 1
                else None,
                Div(*admin_actions, cls="flex flex-wrap gap-2 mt-3") if admin_actions else None,
                cls="p-2.5",
            ),
            cls="rounded-lg overflow-hidden bg-slate-800 border border-slate-700"
            " hover:border-slate-500 hover:shadow-lg hover:shadow-slate-900/50"
            " hover:-translate-y-1 transition-all duration-300",
            id=f"search-result-{nid}",
        )
        result_cards.append(card)

    nav_links = _main_mod._public_nav_links(active="people", user=user, community_slug=community_slug)

    # Share button for similar page hero
    similar_share_btn = (
        _main_mod.share_button(
            url=f"{nav_prefix}/person/{identity_id}",
            style="button",
            label="Share",
            title=f"{name} — Jews of Rhodes Heritage Archive",
            text=f"Do you recognize {name}? Help us identify people in our heritage photo archive.",
        )
        if name and not name.startswith("Unidentified") and not name.startswith("Identity ")
        else None
    )

    return (
        Title(f"Similar to {name} — Rhodesli"),
        _main_mod._share_script(),
        Style("""
            .similar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; }
            @media (max-width: 640px) { .similar-grid { grid-template-columns: repeat(2, 1fr); } }
        """),
        Main(
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/",
                        cls="hover:opacity-90",
                    ),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            _main_mod._admin_bar(user, community_slug=community_slug),
            # Hero section
            Section(
                Div(
                    Div(
                        A(
                            NotStr("&larr; "),
                            "Back to Profile",
                            href=f"{nav_prefix}/person/{identity_id}",
                            cls="text-sm text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1",
                        ),
                        Span(" | ", cls="text-slate-600 mx-2"),
                        A(
                            "All People",
                            href=f"{nav_prefix}/people",
                            cls="text-sm text-slate-400 hover:text-slate-300",
                        ),
                        cls="mb-4 flex items-center",
                    ),
                    Div(
                        # Large hero face
                        Div(
                            Img(src=hero_url, alt=name, cls="w-full h-full object-cover rounded-xl")
                            if hero_url
                            else Div("No photo", cls="w-full h-full flex items-center justify-center text-slate-500"),
                            cls="w-64 h-80 sm:w-80 sm:h-96 flex-shrink-0 overflow-hidden rounded-xl bg-slate-800",
                        ),
                        # Info beside hero
                        Div(
                            H1(name, cls="text-3xl font-serif font-bold text-white mb-2"),
                            P(f"{total_faces} photo{'s' if total_faces != 1 else ''}", cls="text-slate-400 mb-4"),
                            Div(
                                A(
                                    "View Profile",
                                    href=f"{nav_prefix}/person/{identity_id}",
                                    cls="inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors",
                                ),
                                A(
                                    f"Review Proposals ({len(target_proposals)})",
                                    href=f"{nav_prefix}/admin/upload-review#identity-group-{identity_id}",
                                    cls="inline-block px-4 py-2 bg-amber-600/90 hover:bg-amber-500 text-white text-sm rounded-lg transition-colors",
                                    data_testid="similar-review-proposals-link",
                                )
                                if target_proposals
                                else None,
                                A(
                                    "Edit in Admin",
                                    href=f"{nav_prefix}/?section={_main_mod._section_for_state(state)}&view=focus&current={identity_id}",
                                    cls="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors",
                                )
                                if is_admin
                                else None,
                                similar_share_btn,
                                cls="flex flex-wrap gap-3 items-center",
                            ),
                            cls="flex flex-col justify-center",
                        ),
                        cls="flex flex-col sm:flex-row gap-6 items-start",
                    ),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-8",
                ),
            ),
            # Results grid
            Section(
                Div(
                    H2(
                        f"{len(result_cards)} Similar Face{'s' if len(result_cards) != 1 else ''}",
                        cls="text-xl font-bold text-white mb-4",
                    ),
                    Div(*result_cards, cls="similar-grid")
                    if result_cards
                    else P("No similar faces found in the archive.", cls="text-slate-400"),
                    cls="max-w-6xl mx-auto px-6 pb-16",
                ),
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/api/find-similar/{identity_id}")
def get(identity_id: str, sess=None, request=None):
    """Inline Find Similar — returns HTML fragment for expansion panel (AD-194).

    Admin-only HTMX endpoint. Returns hero face + scrollable similar faces
    with Compare/Merge/Not Same actions. Designed to be swapped into an
    expansion-panel div below the identity card.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    name = ensure_utf8_display(identity.get("name", ""))
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_files = _main_mod.get_crop_files()

    # Best face for hero
    best_face = _main_mod.get_best_face_id(all_face_ids) if all_face_ids else (all_face_ids[0] if all_face_ids else "")
    face_id = best_face if isinstance(best_face, str) else best_face.get("face_id", "") if best_face else ""
    hero_url = _main_mod.resolve_face_image_url(face_id, crop_files) if face_id else ""

    # Find similar
    face_data = _main_mod.get_face_data()
    photo_registry = _main_mod.load_photo_registry()
    neighbors = []
    try:
        from core.neighbors import find_nearest_neighbors

        neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=12)
    except Exception as e:
        logging.warning(f"Find similar failed: {e}")

    # Enhance neighbors with crop URLs
    for n in neighbors:
        nid = n["identity_id"]
        try:
            n_ident = registry.get_identity(nid)
            n_faces = n_ident.get("anchor_ids", []) + n_ident.get("candidate_ids", [])
            n_best = _main_mod.get_best_face_id(n_faces) if n_faces else (n_faces[0] if n_faces else "")
            n_fid = n_best if isinstance(n_best, str) else n_best.get("face_id", "") if n_best else ""
            n["crop_url"] = _main_mod.resolve_face_image_url(n_fid, crop_files)
            n["name"] = ensure_utf8_display(n_ident.get("name", ""))
            n["state"] = n_ident.get("state", "INBOX")
        except KeyError:
            n["crop_url"] = ""
            n["name"] = "Unknown"
            n["state"] = "INBOX"

    # FB-008: Compute reciprocal rank for each neighbor
    if neighbors:
        try:
            from core.neighbors import find_nearest_neighbors as _fnn

            for idx, n in enumerate(neighbors):
                nid = n["identity_id"]
                try:
                    reverse_neighbors = _fnn(nid, registry, photo_registry, face_data, limit=12)
                    # Find source identity's rank in the reverse list
                    reciprocal_rank = None
                    reciprocal_best_name = ""
                    if reverse_neighbors:
                        reciprocal_best_name = reverse_neighbors[0].get("identity_id", "")
                        try:
                            rn_ident = registry.get_identity(reciprocal_best_name)
                            reciprocal_best_name = ensure_utf8_display(rn_ident.get("name", "Unknown"))
                        except KeyError:
                            reciprocal_best_name = "Unknown"
                        for ri, rn in enumerate(reverse_neighbors):
                            if rn["identity_id"] == identity_id:
                                reciprocal_rank = ri + 1  # 1-indexed
                                break
                    n["reciprocal_rank"] = reciprocal_rank
                    n["reciprocal_best_name"] = reciprocal_best_name
                    n["is_mutual_top"] = idx == 0 and reciprocal_rank == 1
                except Exception:
                    n["reciprocal_rank"] = None
                    n["reciprocal_best_name"] = ""
                    n["is_mutual_top"] = False
        except ImportError:
            pass

    # Confidence tier helper
    def _tier(dist):
        if dist < 0.80:
            return ("Very High", "bg-emerald-600 text-white")
        elif dist < 1.05:
            return ("High", "bg-blue-600 text-white")
        elif dist < 1.15:
            return ("Moderate", "bg-amber-500 text-white")
        elif dist < 1.30:
            return ("Low", "bg-slate-500 text-white")
        return ("Very Low", "bg-slate-600 text-slate-300")

    # Build similar face tiles
    css_id = _main_mod.make_css_id(identity_id)
    tiles = []
    for n in neighbors:
        if not n.get("crop_url"):
            continue
        nid = n["identity_id"]
        dist = n.get("distance", 99)
        tier_label, tier_cls = _tier(dist)

        # Action buttons
        tile_actions = []
        if is_admin:
            # Compare
            tile_actions.append(
                Button(
                    "Compare",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20 transition-colors",
                    hx_get=f"{nav_prefix}/api/identity/{identity_id}/compare/{nid}",
                    hx_target="#compare-modal-content",
                    hx_swap="innerHTML",
                    **{"_": "on click remove .hidden from #compare-modal"},
                    type="button",
                )
            )
            # Merge
            if n.get("can_merge", True):
                _n_name = n.get("name", "")
                _merge_confirm = (
                    f"Merge {_n_name} into {name}? All faces will be combined."
                    if name and not name.startswith("Unidentified")
                    else "Merge these identities? This can be undone."
                )
                tile_actions.append(
                    Button(
                        "Merge",
                        cls="text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors",
                        hx_post=f"{nav_prefix}/api/identity/{identity_id}/merge/{nid}",
                        hx_target=f"#expand-{css_id}",
                        hx_swap="innerHTML",
                        hx_confirm=_merge_confirm,
                        type="button",
                    )
                )
            # Not Same
            tile_actions.append(
                Button(
                    "Not Same",
                    cls="text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 border border-slate-500 text-slate-400 rounded hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/50 transition-colors",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/reject-match/{nid}",
                    hx_target=f"#similar-tile-{_main_mod.make_css_id(nid)}",
                    hx_swap="outerHTML",
                    type="button",
                )
            )

        # FB-008: Reciprocal rank indicator
        recip_el = None
        recip_rank = n.get("reciprocal_rank")
        recip_best = n.get("reciprocal_best_name", "")
        is_mutual = n.get("is_mutual_top", False)
        if is_mutual:
            recip_el = Span(
                "Mutual #1",
                cls="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-600 text-white",
                data_testid="reciprocal-rank",
            )
        elif recip_rank is not None:
            recip_el = Span(
                f"You're their #{recip_rank}",
                cls="text-[10px] text-slate-400",
                data_testid="reciprocal-rank",
            )
        elif recip_best:
            recip_el = Span(
                f"Not in top · #1 is {recip_best}",
                cls="text-[10px] text-amber-500",
                data_testid="reciprocal-rank",
            )

        tile = Div(
            A(
                Img(
                    src=n["crop_url"],
                    alt=n.get("name", ""),
                    cls="w-full aspect-[3/4] object-cover rounded-lg",
                    loading="lazy",
                ),
                href=f"{nav_prefix}/person/{nid}",
                cls="block overflow-hidden",
            ),
            Div(
                Span(n.get("name", "Unknown"), cls="text-sm text-white font-medium truncate block"),
                Div(
                    Span(tier_label, cls=f"text-[10px] px-1.5 py-0.5 rounded-full {tier_cls}"),
                    Span(f"{dist:.2f}", cls="text-[10px] text-slate-500 ml-1") if is_admin else None,
                    cls="flex items-center gap-1 mt-1",
                ),
                Div(recip_el, cls="mt-1") if recip_el else None,
                Div(*tile_actions, cls="flex flex-wrap gap-1 mt-2") if tile_actions else None,
                cls="mt-2",
            ),
            cls="similar-face-tile",
            id=f"similar-tile-{_main_mod.make_css_id(nid)}",
        )
        tiles.append(tile)

    # Close button
    close_btn = Button(
        NotStr("&times;"),
        cls="panel-close text-slate-400 hover:text-white text-xl font-bold bg-transparent border-0 p-1 leading-none",
        **{"_": f"on click set innerHTML of #expand-{css_id} to ''"},
        type="button",
        title="Close",
        aria_label="Close",
    )

    # Build the fragment
    hero_section = Div(
        Img(src=hero_url, alt=name, cls="w-20 h-20 rounded-lg object-cover flex-shrink-0") if hero_url else None,
        Div(
            Span(name or "Unidentified", cls="text-xl sm:text-lg font-semibold text-white block"),
            Span(f"{len(all_face_ids)} face{'s' if len(all_face_ids) != 1 else ''}", cls="text-sm text-slate-400"),
            A(
                "View Profile",
                href=f"{nav_prefix}/person/{identity_id}",
                cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 block mt-1",
            ),
            cls="min-w-0",
        ),
        Div(cls="flex-1"),
        close_btn,
        cls="flex items-start gap-4 mb-4",
    )

    results_section = Div(
        H4(f"{len(tiles)} Similar Face{'s' if len(tiles) != 1 else ''}", cls="text-sm font-medium text-slate-300 mb-3"),
        Div(*tiles, cls="similar-faces") if tiles else P("No similar faces found.", cls="text-sm text-slate-500"),
    )

    return Div(hero_section, results_section, data_testid="find-similar-panel")


@rt("/collections")
def get(sess=None, request=None):
    """Collection directory — list all collections with preview thumbnails."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    collections = _main_mod._get_collections_data()

    # Build collection cards
    cards = []
    for col_name in sorted(collections.keys(), key=lambda n: -len(collections[n]["photos"])):
        col = collections[col_name]
        photo_count = len(col["photos"])
        slug = col["slug"]

        # Preview thumbnails (first 4 photos)
        previews = []
        for photo in col["photos"][:4]:
            photo_path = photo.get("path", "")
            if photo_path:
                url = _main_mod.storage.get_photo_url(photo_path)
                previews.append(
                    Img(
                        src=url,
                        alt="",
                        cls="w-full h-24 object-cover rounded",
                        loading="lazy",
                        onerror="this.style.display='none'",
                    )
                )

        preview_grid = Div(*previews, cls="grid grid-cols-2 gap-1 mb-3") if previews else ""

        # Face counts
        face_line = f"{col['identified_count']} identified"
        if col["unidentified_count"] > 0:
            face_line += f", {col['unidentified_count']} unknown"

        cards.append(
            A(
                preview_grid,
                H3(col_name, cls="text-white font-semibold text-sm mb-1 line-clamp-2"),
                P(f"{photo_count} photo{'s' if photo_count != 1 else ''}", cls="text-sm sm:text-xs text-slate-400"),
                P(face_line, cls="text-sm sm:text-xs text-slate-500 mt-0.5"),
                href=f"{nav_prefix}/collection/{slug}",
                cls="block bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 hover:border-indigo-500/50 transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
                data_testid="collection-card",
            )
        )

    nav_links = _main_mod._public_nav_links(active="collections", user=user, community_slug=community_slug)

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    return (
        Title("Collections — Rhodesli"),
        *_main_mod.og_tags(
            "Collections — Rhodesli Heritage Archive",
            "Browse photo collections from the Rhodes-Capeluto family archive.",
            canonical_url=f"{nav_prefix}/collections",
        ),
        page_style,
        Div(
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/",
                        cls="hover:opacity-90",
                    ),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between",
                ),
                cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50",
            ),
            Div(
                Div(
                    H1("Collections", cls="text-2xl md:text-3xl font-bold text-white mb-2"),
                    _main_mod.share_button(
                        url=f"{nav_prefix}/collections",
                        style="link",
                        label="Share",
                        title="Collections — Rhodesli",
                        text="Browse photo collections from the Rhodes heritage archive",
                    ),
                    cls="flex items-center justify-between",
                ),
                P(
                    f"{len(collections)} collection{'s' if len(collections) != 1 else ''} in the archive",
                    cls="text-slate-400 mb-8",
                )
                if collections
                else None,
                Div(*cards, cls="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4")
                if collections
                else Div(
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 text-slate-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v13.5A1.5 1.5 0 003.75 21z"/></svg>'
                    ),
                    H3("No Collections Created", cls="text-xl font-serif text-slate-400 mb-2"),
                    P("Collections will appear here once photos are grouped.", cls="text-sm text-slate-500"),
                    cls="flex flex-col items-center justify-center py-20 px-6 border-2 border-slate-800 border-dashed rounded-2xl bg-slate-900/30 text-center",
                ),
                cls="max-w-6xl mx-auto px-6 pt-24 pb-16",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/collection/{slug}")
def get(slug: str, sess=None, request=None):
    """Collection detail page — shareable view of all photos in a collection."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    collections = _main_mod._get_collections_data()
    col_name = _main_mod._collection_from_slug(slug, collections)

    if not col_name or col_name not in collections:
        page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
        return (
            Title("Collection Not Found — Rhodesli"),
            page_style,
            Div(
                Div(
                    H1("Collection Not Found", cls="text-2xl font-bold text-white mb-4"),
                    P("This collection doesn't exist.", cls="text-slate-400"),
                    A(
                        "Browse all collections →",
                        href=f"{nav_prefix}/collections",
                        cls="text-indigo-400 hover:text-indigo-300 mt-4 inline-block",
                    ),
                    cls="max-w-4xl mx-auto px-6 pt-24",
                ),
                cls="min-h-screen bg-slate-900",
            ),
        )

    col = collections[col_name]
    photos = col["photos"]
    registry = _main_mod.load_registry()

    # Build photo grid
    photo_cards = []
    for photo in photos:
        photo_path = photo.get("path", "")
        photo_id = photo.get("photo_id", "")
        if not photo_path:
            continue
        url = _main_mod.storage.get_photo_url(photo_path)

        # Count faces
        face_ids = photo.get("face_ids", [])
        identified = 0
        unknown = 0
        for fid in face_ids:
            ident = _main_mod.get_identity_for_face(registry, fid)
            if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                identified += 1
            elif ident:
                unknown += 1

        face_badge = ""
        if identified + unknown > 0:
            badge_text = f"{identified} named"
            if unknown > 0:
                badge_text += f", {unknown} unknown"
            face_badge = Div(
                badge_text,
                cls="absolute bottom-1 left-1 text-[10px] px-1.5 py-0.5 rounded bg-black/70 text-slate-300",
            )

        photo_cards.append(
            A(
                Div(
                    Img(
                        src=url,
                        alt="",
                        cls="w-full h-40 md:h-48 object-cover",
                        loading="lazy",
                        onerror="this.style.display='none'",
                    ),
                    face_badge if face_badge else None,
                    cls="relative rounded-lg overflow-hidden",
                ),
                href=f"{nav_prefix}/photo/{photo_id}" if photo_id else "#",
                cls="block hover:opacity-90 transition-opacity",
                data_testid="collection-photo",
            )
        )

    # People in this collection
    people_in_collection = set()
    for photo in photos:
        for fid in photo.get("face_ids", []):
            ident = _main_mod.get_identity_for_face(registry, fid)
            if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                people_in_collection.add(ident.get("identity_id"))

    people_section = ""
    if people_in_collection:
        people_items = []
        for pid in sorted(
            people_in_collection, key=lambda x: _main_mod._safe_get_identity(registry, x).get("name", "").lower()
        ):
            p_ident = _main_mod._safe_get_identity(registry, pid)
            p_name = ensure_utf8_display(p_ident.get("name", "Unknown"))
            people_items.append(
                A(
                    p_name,
                    href=f"{nav_prefix}/person/{pid}",
                    cls="inline-block px-4 py-3 sm:px-2.5 sm:py-1 text-sm sm:text-xs rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
                )
            )
        people_section = Div(
            H3(
                f"People in this Collection ({len(people_in_collection)})",
                cls="text-sm font-semibold text-slate-300 mb-3",
            ),
            Div(*people_items, cls="flex flex-wrap gap-2"),
            cls="mt-8",
        )

    nav_links = _main_mod._public_nav_links(active="collections", user=user, community_slug=community_slug)

    share_url = f"{nav_prefix}/collection/{slug}"
    og_image_url = ""
    for photo in photos:
        photo_path = photo.get("path", "")
        if photo_path:
            og_image_url = _main_mod.storage.get_photo_url(photo_path)
            if og_image_url:
                break

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    return (
        Title(f"{col_name} — Rhodesli"),
        *_main_mod.og_tags(
            f"{col_name} — Rhodesli Heritage Archive",
            f"Browse {len(photos)} photos from the {col_name}.",
            image_url=og_image_url,
            canonical_url=share_url,
        ),
        page_style,
        Div(
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/",
                        cls="hover:opacity-90",
                    ),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between",
                ),
                cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50",
            ),
            Div(
                # Breadcrumb
                Div(
                    A(
                        "Collections",
                        href=f"{nav_prefix}/collections",
                        cls="text-indigo-400 hover:text-indigo-300 text-sm",
                    ),
                    Span(" / ", cls="text-slate-600 mx-2"),
                    Span(col_name, cls="text-slate-300 text-sm"),
                    cls="mb-6",
                ),
                # Header
                Div(
                    H1(col_name, cls="text-2xl md:text-3xl font-bold text-white mb-2"),
                    Div(
                        Span(f"{len(photos)} photo{'s' if len(photos) != 1 else ''}", cls="text-slate-400"),
                        Span(" · ", cls="text-slate-600 mx-2"),
                        Span(f"{col['identified_count']} people identified", cls="text-emerald-400"),
                        cls="text-sm mb-4",
                    ),
                    # Action buttons
                    Div(
                        Button(
                            NotStr(_main_mod._SHARE_ICON_SVG),
                            " Share Collection",
                            cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1",
                            type="button",
                            data_action="share-photo",
                            data_share_url=share_url,
                        ),
                        A(
                            "View on Timeline →",
                            href=f"{nav_prefix}/timeline?collection={quote(col_name)}",
                            cls="text-sm text-indigo-400 hover:text-indigo-300 ml-4",
                        ),
                        A(
                            "+ Add Photos",
                            href=f"{nav_prefix}/upload",
                            cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1 ml-3",
                        )
                        if (user and user.is_admin if _main_mod.is_auth_enabled() else False)
                        else None,
                        cls="flex items-center flex-wrap gap-2 mb-6",
                    ),
                    cls="mb-6",
                ),
                # Help identify banner
                Div(
                    P(
                        f"{col['unidentified_count']} face{'s' if col['unidentified_count'] != 1 else ''} waiting to be identified in this collection.",
                        cls="text-sm text-slate-300",
                    ),
                    A(
                        "Do you recognize anyone? →",
                        href=f"{nav_prefix}/help",
                        cls="text-sm text-indigo-400 hover:text-indigo-300 font-medium ml-4",
                    ),
                    cls="bg-blue-900/20 border border-blue-800/30 rounded-lg px-4 py-3 flex items-center justify-between mb-6",
                    data_testid="help-identify-banner",
                )
                if col["unidentified_count"] > 0
                else "",
                # Photo grid
                Div(
                    *photo_cards,
                    cls="grid grid-cols-1 sm:grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3",
                ),
                # People section
                people_section,
                cls="max-w-6xl mx-auto px-6 pt-24 pb-16",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


_photo_locations_cache = None


def _load_photo_locations() -> dict:
    """Load geocoded photo locations (photo_id -> location info).

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Returns dict keyed by photo_id with lat, lng, location_name, etc.
    Dual-keys inbox IDs to SHA256 IDs (same pattern as _load_date_labels).
    """
    global _photo_locations_cache
    if _photo_locations_cache is not None:
        return _photo_locations_cache

    if _main_mod.DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import load_photo_locations_from_supabase

            result = load_photo_locations_from_supabase()
            if result is not None:
                # Dual-key: Supabase stores inbox_* IDs, but _photo_cache uses SHA256 IDs.
                # Add SHA256 aliases so map lookups work (same fix as date_labels — Session 144b).
                try:
                    photo_registry = _main_mod.load_photo_registry()
                    aliases_added = 0
                    for pid in list(result.keys()):
                        if pid.startswith("inbox_"):
                            path = photo_registry.get_photo_path(pid)
                            if path:
                                sha256_id = _main_mod.generate_photo_id(Path(path).name)
                                if sha256_id not in result:
                                    result[sha256_id] = result[pid]
                                    aliases_added += 1
                    if aliases_added:
                        logger.info(f"Photo locations: added {aliases_added} SHA256 aliases for inbox IDs")
                except Exception as alias_err:
                    logger.warning(f"Photo locations dual-keying failed (non-fatal): {alias_err}")
                logger.info(f"Loaded {len(result)} photo locations from Postgres")
                _photo_locations_cache = result
                return _photo_locations_cache
            logger.warning(
                "Postgres photo locations: Supabase returned None, returning empty (no JSON fallback — AD-232)"
            )
        except Exception as e:
            logger.error(f"Postgres photo locations load failed, returning empty (no JSON fallback — AD-232): {e}")
        # Do NOT cache empty on failure — next request should retry (Codex P1 fix)
        return {}

    # JSON mode (DATA_SOURCE=json) — rollback escape hatch only
    _photo_locations_cache = {}
    locations_path = Path(_main_mod.DATA_DIR) / "photo_locations.json"
    if locations_path.exists():
        try:
            data = json.loads(locations_path.read_text())
            _photo_locations_cache = data.get("photos", {})

            # Dual-key: also index inbox_* IDs by their SHA256 cache ID
            try:
                from core.photo_registry import PhotoRegistry

                photo_registry = PhotoRegistry.load(_main_mod.data_path / "photo_index.json")
                mapped = 0
                for pid in list(_photo_locations_cache.keys()):
                    if pid.startswith("inbox_"):
                        path = photo_registry.get_photo_path(pid)
                        if path:
                            fname = Path(path).name
                            sha_id = _main_mod.hashlib.sha256(fname.encode("utf-8")).hexdigest()[:16]
                            if sha_id not in _photo_locations_cache:
                                _photo_locations_cache[sha_id] = _photo_locations_cache[pid]
                                mapped += 1
                logger.info(f"Photo locations: {len(_photo_locations_cache)} entries, {mapped} inbox->SHA256 mapped")
            except Exception as e:
                logger.warning(f"Photo locations dual-key mapping failed: {e}")
        except Exception:
            pass
    return _photo_locations_cache


@rt("/map")
def get(collection: str = "", person: str = "", people: str = "", decade: str = "", sess=None, request=None):
    """Interactive map view of photo locations across the Rhodes Jewish diaspora.

    Query params:
        person: Single person ID to filter by
        people: Comma-separated person IDs (from photo page navigation)
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    # If people param provided (from photo page), use the first as the person filter
    if people and not person:
        person_ids = [p.strip() for p in people.split(",") if p.strip()]
        if person_ids:
            person = person_ids[0]

    _main_mod._build_caches()
    locations = _main_mod._load_photo_locations()
    registry = _main_mod.load_registry()
    photo_reg = _main_mod.load_photo_registry()
    date_labels = _main_mod._load_date_labels()

    # Build markers with photo data
    markers = []
    location_groups = {}  # group photos by location key for clustering

    for photo_id, loc in locations.items():
        # Apply filters
        if collection:
            photo_data = (_main_mod._photo_cache or {}).get(photo_id, {})
            if not photo_data:
                # Try photo registry
                photo_data = photo_reg._photos.get(photo_id, {})
            photo_collection = photo_data.get("collection", "")
            if collection.lower() not in photo_collection.lower():
                continue

        if person:
            photo_data = (_main_mod._photo_cache or {}).get(photo_id, {})
            if not photo_data:
                photo_data = photo_reg._photos.get(photo_id, {})
            face_ids = photo_data.get("face_ids", [])
            person_found = False
            for fid in face_ids:
                ident = _main_mod.get_identity_for_face(registry, fid)
                if ident and ident.get("identity_id") == person:
                    person_found = True
                    break
            if not person_found:
                continue

        if decade:
            label = date_labels.get(photo_id, {})
            photo_decade = label.get("estimated_decade", 0)
            try:
                if photo_decade != int(decade):
                    continue
            except (ValueError, TypeError):
                continue

        loc_key = loc.get("location_key", "unknown")
        if loc_key not in location_groups:
            location_groups[loc_key] = {
                "lat": loc["lat"],
                "lng": loc["lng"],
                "name": loc["location_name"],
                "region": loc.get("region", ""),
                "photos": [],
            }

        # Get photo metadata
        photo_data = (_main_mod._photo_cache or {}).get(photo_id, {})
        if not photo_data:
            photo_data = photo_reg._photos.get(photo_id, {})
        photo_path = photo_data.get("path", photo_data.get("filename", ""))
        photo_url_val = _main_mod.storage.get_photo_url(photo_path) if photo_path else ""

        # Get date info
        label = date_labels.get(photo_id, {})
        est_decade = label.get("estimated_decade", 0)

        location_groups[loc_key]["photos"].append(
            {
                "photo_id": photo_id,
                "url": photo_url_val,
                "decade": est_decade,
                "collection": photo_data.get("collection", ""),
            }
        )

    # Convert to marker list for JSON
    for loc_key, group in location_groups.items():
        markers.append(
            {
                "lat": group["lat"],
                "lng": group["lng"],
                "name": group["name"],
                "region": group["region"],
                "count": len(group["photos"]),
                "photos": group["photos"][:8],  # Limit preview photos
                "total": len(group["photos"]),
            }
        )

    markers_json = json.dumps(markers)

    # Build filter options
    all_collections = set()
    all_decades = set()
    for pid, loc in locations.items():
        pd = (_main_mod._photo_cache or {}).get(pid, {})
        if not pd:
            pd = photo_reg._photos.get(pid, {})
        c = pd.get("collection", "")
        if c:
            all_collections.add(c)
        lbl = date_labels.get(pid, {})
        d = lbl.get("estimated_decade", 0)
        if d:
            all_decades.add(d)

    # People options
    all_people = []
    for ident in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED):
        if not ident.get("name", "").startswith("Unidentified"):
            all_people.append({"id": ident.get("identity_id", ""), "name": ensure_utf8_display(ident.get("name", ""))})
    all_people.sort(key=lambda x: x["name"].lower())

    collection_options = [Option("All collections", value="")] + [
        Option(c, value=c, selected=(c == collection)) for c in sorted(all_collections)
    ]
    decade_options = [Option("All decades", value="")] + [
        Option(f"{d}s", value=str(d), selected=(str(d) == decade)) for d in sorted(all_decades)
    ]
    person_options = [Option("All people", value="")] + [
        Option(p["name"], value=p["id"], selected=(p["id"] == person)) for p in all_people
    ]

    nav_links = _main_mod._public_nav_links(active="map", user=user, community_slug=community_slug)

    # Share URL with current filters
    share_params = []
    if collection:
        share_params.append(f"collection={quote(collection)}")
    if person:
        share_params.append(f"person={person}")
    if decade:
        share_params.append(f"decade={decade}")
    share_url = "/map" + ("?" + "&".join(share_params) if share_params else "")

    # Summary text
    total_photos = sum(m["total"] for m in markers)
    total_locations = len(markers)
    summary = f"{total_photos} photo{'s' if total_photos != 1 else ''} across {total_locations} location{'s' if total_locations != 1 else ''}"

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        #map-container { height: calc(100vh - 180px); min-height: 400px; border-radius: 12px; overflow: hidden; }
        .leaflet-popup-content { max-width: 280px; }
        .leaflet-popup-content-wrapper { background: #1e293b; color: #e2e8f0; border-radius: 8px; }
        .leaflet-popup-tip { background: #1e293b; }
        .leaflet-popup-close-button { color: #94a3b8 !important; }
        .photo-preview-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px; margin-top: 8px; }
        .photo-preview-grid img { width: 100%; height: 60px; object-fit: cover; border-radius: 4px; cursor: pointer; }
    """)

    leaflet_css = Link(rel="stylesheet", href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css")
    leaflet_js = Script(src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js")
    marker_cluster_css = Link(
        rel="stylesheet", href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
    )
    marker_cluster_default_css = Link(
        rel="stylesheet", href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
    )
    marker_cluster_js = Script(src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js")

    map_script = Script(
        f"""
    document.addEventListener('DOMContentLoaded', function() {{
        var markers = {markers_json};

        var map = L.map('map-container').setView([35.0, -20.0], 3);

        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }}).addTo(map);

        var cluster = L.markerClusterGroup({{
            maxClusterRadius: 50,
            iconCreateFunction: function(cluster) {{
                var count = 0;
                cluster.getAllChildMarkers().forEach(function(m) {{ count += m.options.photoCount || 1; }});
                var size = count > 50 ? 'large' : count > 20 ? 'medium' : 'small';
                return L.divIcon({{
                    html: '<div style="background:#6366f1;color:white;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:13px;border:2px solid #818cf8;">' + count + '</div>',
                    className: 'custom-cluster-icon',
                    iconSize: [40, 40]
                }});
            }}
        }});

        markers.forEach(function(m) {{
            var photosHtml = '';
            if (m.photos && m.photos.length > 0) {{
                photosHtml = '<div class="photo-preview-grid">';
                m.photos.forEach(function(p) {{
                    photosHtml += '<img src="' + p.url + '" alt="" onclick="window.location.href=\\'__NAV_PREFIX__/photo/' + p.photo_id + '\\'" onerror="this.style.display=\\'none\\'">';
                }});
                photosHtml += '</div>';
            }}
            var moreText = m.total > 8 ? '<div style="text-align:center;margin-top:6px;"><a href="__NAV_PREFIX__/photos?q=' + encodeURIComponent(m.name) + '" style="color:#818cf8;font-size:12px;">See all ' + m.total + ' photos &rarr;</a></div>' : '';

            var popupContent = '<div>' +
                '<strong style="font-size:14px;">' + m.name + '</strong>' +
                '<div style="color:#94a3b8;font-size:12px;margin-top:2px;">' + m.region + ' &middot; ' + m.count + ' photo' + (m.count !== 1 ? 's' : '') + '</div>' +
                photosHtml + moreText +
                '</div>';

            var icon = L.divIcon({{
                html: '<div style="background:#6366f1;color:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid #818cf8;box-shadow:0 2px 8px rgba(0,0,0,0.3);">' + m.count + '</div>',
                className: 'custom-marker-icon',
                iconSize: [32, 32],
                iconAnchor: [16, 16],
                popupAnchor: [0, -16]
            }});

            var marker = L.marker([m.lat, m.lng], {{ icon: icon, photoCount: m.count }});
            marker.bindPopup(popupContent, {{ maxWidth: 300 }});
            cluster.addLayer(marker);
        }});

        map.addLayer(cluster);

        /* Fit bounds if markers exist */
        if (markers.length > 0) {{
            var bounds = L.latLngBounds(markers.map(function(m) {{ return [m.lat, m.lng]; }}));
            map.fitBounds(bounds, {{ padding: [50, 50], maxZoom: 6 }});
        }}
    }});
    """.replace("__NAV_PREFIX__", nav_prefix or "")
    )

    return (
        Title("Map — Rhodesli"),
        Meta(property="og:title", content="Map — Rhodesli Heritage Archive"),
        Meta(
            property="og:description",
            content=f"Explore {total_photos} photos across {total_locations} locations in the Rhodes Jewish diaspora.",
        ),
        Meta(property="og:url", content=f"{_main_mod.SITE_URL}{share_url}"),
        leaflet_css,
        marker_cluster_css,
        marker_cluster_default_css,
        page_style,
        Div(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between",
                ),
                cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50",
            ),
            Div(
                # Header
                Div(
                    H1("Map", cls="text-2xl md:text-3xl font-bold text-white mb-1"),
                    P(summary, cls="text-slate-400 text-sm mb-4"),
                    cls="mb-2",
                ),
                # Filters
                Div(
                    Form(
                        Select(
                            *collection_options,
                            name="collection",
                            cls="bg-slate-800 text-slate-300 text-sm sm:text-xs rounded-lg px-4 py-3 sm:px-2 sm:py-1.5 border border-slate-700",
                            onchange="this.form.submit()",
                        ),
                        Select(
                            *person_options,
                            name="person",
                            cls="bg-slate-800 text-slate-300 text-sm sm:text-xs rounded-lg px-4 py-3 sm:px-2 sm:py-1.5 border border-slate-700",
                            onchange="this.form.submit()",
                        ),
                        Select(
                            *decade_options,
                            name="decade",
                            cls="bg-slate-800 text-slate-300 text-sm sm:text-xs rounded-lg px-4 py-3 sm:px-2 sm:py-1.5 border border-slate-700",
                            onchange="this.form.submit()",
                        ),
                        Button(
                            NotStr(_main_mod._SHARE_ICON_SVG),
                            " Share",
                            cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm sm:text-xs rounded-lg transition-colors inline-flex items-center gap-1",
                            type="button",
                            data_action="share-photo",
                            data_share_url=share_url,
                        ),
                        method="get",
                        action="/map",
                        cls="flex flex-wrap items-center gap-2",
                    ),
                    cls="mb-4",
                ),
                # Map container
                Div(id="map-container", data_testid="map-container"),
                # Legend
                Div(
                    Span("Locations sized by photo count", cls="text-sm sm:text-xs text-slate-500"),
                    Span(" · ", cls="text-slate-700 mx-2"),
                    Span("Click markers to see photos", cls="text-sm sm:text-xs text-slate-500"),
                    Span(" · ", cls="text-slate-700 mx-2"),
                    A(
                        "View Timeline →",
                        href=f"{nav_prefix}/timeline",
                        cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300",
                    ),
                    cls="mt-3 text-center",
                ),
                cls="max-w-6xl mx-auto px-6 pt-24 pb-8",
            ),
            cls="min-h-screen bg-slate-900",
        ),
        leaflet_js,
        marker_cluster_js,
        map_script,
    )


@rt("/timeline")
def get(
    person: str = "",
    people: str = "",
    start: int = None,
    end: int = None,
    context: str = "on",
    collection: str = "",
    sess=None,
    request=None,
):
    """
    Public timeline page — chronological story of the archive.

    Shows photos and historical context events on a vertical timeline,
    grouped by decade. Supports person/multi-person filter (with age overlay),
    year range filter, collection filter, and shareable URLs.

    Query params:
        person: single identity_id to filter by (backwards compat)
        people: comma-separated identity_ids for multi-person filter
        start: start year for range filter
        end: end year for range filter
        context: "on" (default) or "off" to toggle context events
        collection: collection name to filter by
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    photo_reg = _main_mod.load_photo_registry()
    crop_files = _main_mod.get_crop_files()

    # Load data sources
    search_docs = _main_mod._load_search_index()
    date_labels = _main_mod._load_date_labels()
    context_events = _main_mod._load_context_events() if context != "off" else []
    timeline_eligible_photo_ids = _timeline_eligible_photo_ids(
        search_docs,
        _main_mod._photo_cache or {},
        start=start,
        end=end,
        collection=collection,
    )

    # Build person lookup for filter
    confirmed = [
        i
        for i in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
    ]
    confirmed.sort(key=lambda x: (x.get("name") or "").lower())

    # Resolve person filter — support both single and multi-person
    person_ids = []
    if people:
        person_ids = [p.strip() for p in people.split(",") if p.strip()]
    elif person:
        person_ids = [person]

    person_identities = []
    person_photo_ids = None
    # Map photo_id -> set of person names appearing in it (for multi-person cards)
    photo_person_map = {}
    if person_ids:
        person_photo_ids = set()
        for pid in person_ids:
            try:
                ident = registry.get_identity(pid)
            except KeyError:
                continue
            if not ident:
                continue
            person_identities.append(ident)
            face_ids = [
                f if isinstance(f, str) else f.get("face_id", "")
                for f in ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            ]
            pname = ensure_utf8_display(ident.get("name", ""))
            for fid in face_ids:
                photo_id = _main_mod.get_photo_id_for_face(fid)
                if photo_id:
                    person_photo_ids.add(photo_id)
                    photo_person_map.setdefault(photo_id, set()).add(pname)

    # For backwards compat, keep person_identity for single-person features (age badge)
    person_identity = person_identities[0] if len(person_identities) == 1 else None

    # Build timeline entries from photos
    timeline_entries = []
    for doc in search_docs:
        photo_id = doc.get("cache_photo_id", doc.get("photo_id", ""))
        best_year = doc.get("best_year_estimate")
        decade = doc.get("estimated_decade")
        if not best_year and not decade:
            continue

        year = best_year or decade
        if not year:
            continue

        # Apply year range filter
        if start and year < start:
            continue
        if end and year > end:
            continue

        # Apply person filter
        if person_photo_ids is not None and photo_id not in person_photo_ids:
            continue

        # Get photo metadata
        photo_data = (_main_mod._photo_cache or {}).get(photo_id, {})
        filename = photo_data.get("filename", "")

        # Get collection and apply collection filter
        photo_collection = photo_data.get("collection", "")
        if collection and photo_collection != collection:
            continue

        # Get date label details
        label = date_labels.get(photo_id, {})
        prob_range = label.get("probable_range", [])
        confidence = label.get("confidence", "medium")

        # Count identified people in photo
        faces = photo_data.get("faces", [])
        people_names = []
        for face in faces:
            fid = face.get("face_id", "")
            ident = _main_mod.get_identity_for_face(registry, fid)
            if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                people_names.append(ident["name"])

        # For multi-person, note which filtered people appear in this photo
        highlighted_people = []
        if photo_person_map and photo_id in photo_person_map:
            highlighted_people = sorted(photo_person_map[photo_id])

        timeline_entries.append(
            {
                "type": "photo",
                "year": year,
                "decade": decade or (year // 10 * 10),
                "photo_id": photo_id,
                "filename": filename,
                "collection": photo_collection,
                "confidence": confidence,
                "prob_range": prob_range,
                "people": people_names,
                "highlighted_people": highlighted_people,
                "scene": label.get("scene_description", ""),
            }
        )

    # When person filter active, compute photo date range for era filtering
    person_era_start = None
    person_era_end = None
    if person_photo_ids is not None and timeline_entries:
        photo_years = [e["year"] for e in timeline_entries if e["type"] == "photo"]
        if photo_years:
            person_era_start = min(photo_years) - 30  # 30 years before earliest photo
            person_era_end = max(photo_years) + 10  # 10 years after latest photo

    # Add context events
    for event in context_events:
        year = event.get("year", 0)
        if start and year < start:
            continue
        if end and year > end:
            continue

        # Filter context events to person's era when person filter is active
        if person_era_start is not None:
            if year < person_era_start or year > person_era_end:
                continue

        timeline_entries.append(
            {
                "type": "context",
                "year": year,
                "decade": year // 10 * 10,
                "title": event.get("title", ""),
                "description": event.get("description", ""),
                "category": event.get("category", ""),
                "source": event.get("source", ""),
            }
        )

    # Add life events from Supabase
    try:
        from app.event_routes import list_events as _list_life_events, EVENT_TYPE_ICONS

        life_events = _list_life_events()
        for le in life_events:
            year = le.get("event_year")
            if not year:
                continue
            if start and year < start:
                continue
            if end and year > end:
                continue
            if person_era_start is not None:
                if year < person_era_start or year > person_era_end:
                    continue

            event_type = le.get("event_type", "other")
            icon = EVENT_TYPE_ICONS.get(event_type, EVENT_TYPE_ICONS.get("other", ""))
            le_title = le.get("title") or le.get("event_type", "Event").title()

            timeline_entries.append(
                {
                    "type": "life_event",
                    "year": year,
                    "decade": year // 10 * 10,
                    "title": f"{icon} {le_title}" if icon else le_title,
                    "description": le.get("description", ""),
                    "location": le.get("location", ""),
                    "event_type": event_type,
                    "event_id": le.get("id", ""),
                }
            )
    except Exception:
        logger.warning("Failed to load life events for timeline", exc_info=True)

    # Sort by year
    timeline_entries.sort(key=lambda e: e["year"])

    # Group by decade
    decades_order = []
    decades_map = {}
    for entry in timeline_entries:
        dec = entry["decade"]
        if dec not in decades_map:
            decades_map[dec] = []
            decades_order.append(dec)
        decades_map[dec].append(entry)

    # Compute age if person has confirmed birth_year (Gatekeeper: public sees confirmed only)
    person_birth_year = None
    birth_year_source = None
    birth_year_confidence = None
    if person_identity:
        iid = person_identity.get("identity_id", "")
        person_birth_year, birth_year_source, birth_year_confidence = _main_mod._get_birth_year(
            iid, person_identity, include_unreviewed=False
        )

    # Build person filter options (checkboxes for multi-select)
    selected_person_ids = set(person_ids)
    person_filter_items = _build_timeline_person_filter_items(
        confirmed,
        photo_reg,
        timeline_eligible_photo_ids,
        selected_person_ids,
    )

    # Also build backwards-compatible <select> options for single-person
    person_options = [Option("All people", value="")]
    for item in person_filter_items:
        person_options.append(
            Option(
                f"{item['name']} ({item['count']} photos)",
                value=item["id"],
                selected=item["selected"],
            )
        )

    # Build collection list for filter dropdown
    all_collections = sorted(
        set(
            ((_main_mod._photo_cache or {}).get(pid, {}).get("collection", "") or "")
            for pid in (_main_mod._photo_cache or {})
        )
    )
    all_collections = [c for c in all_collections if c]

    # Story header
    if len(person_identities) > 1:
        names = [ensure_utf8_display(pi.get("name", "")) for pi in person_identities]
        story_title = " & ".join(names)
        photo_count = len([e for e in timeline_entries if e["type"] == "photo"])
        story_subtitle = f"{photo_count} photos across {len(person_identities)} people"
    elif person_identity:
        person_name = ensure_utf8_display(person_identity.get("name", ""))
        story_title = f"{person_name}\u2019s Life in Photos"
        story_subtitle = ""
        if person_birth_year:
            if birth_year_source == "ml_inferred":
                story_subtitle = f"Born ~{person_birth_year} (estimated)"
            else:
                story_subtitle = f"Born {person_birth_year}"
    elif collection:
        story_title = collection
        photo_count = len([e for e in timeline_entries if e["type"] == "photo"])
        story_subtitle = f"{photo_count} photos in this collection"
    elif start and end:
        story_title = f"Rhodes, {start}\u2013{end}"
        story_subtitle = f"{len([e for e in timeline_entries if e['type'] == 'photo'])} photos in this period"
    else:
        story_title = "A Century of Rhodes"
        photo_count = len([e for e in timeline_entries if e["type"] == "photo"])
        event_count = len([e for e in timeline_entries if e["type"] == "context"])
        story_subtitle = f"{photo_count} photos \u00b7 {event_count} historical events"

    # Category colors for context events
    category_colors = {
        "holocaust": "border-red-700/60 bg-red-950/30",
        "persecution": "border-red-800/50 bg-red-950/20",
        "liberation": "border-emerald-700/50 bg-emerald-950/20",
        "immigration": "border-blue-700/50 bg-blue-950/20",
        "community": "border-amber-700/50 bg-amber-950/20",
        "political": "border-slate-600/50 bg-slate-800/30",
    }

    # Build timeline UI
    from urllib.parse import quote as _url_quote, urlencode as _url_encode

    def _timeline_url(**overrides):
        params = {}
        if len(person_ids) > 1:
            params["people"] = ",".join(person_ids)
        elif len(person_ids) == 1:
            params["person"] = person_ids[0]
        if start:
            params["start"] = str(start)
        if end:
            params["end"] = str(end)
        if context != "on":
            params["context"] = context
        if collection:
            params["collection"] = collection
        params.update({k: str(v) for k, v in overrides.items() if v})
        qs = _url_encode(params)
        return f"/timeline?{qs}" if qs else "/timeline"

    # Render decade sections
    decade_sections = []
    for dec in decades_order:
        entries = decades_map[dec]

        # Decade marker
        marker = Div(
            Div(
                Span(f"{dec}s", cls="text-xl sm:text-lg font-serif font-bold text-amber-400/80"),
                cls="bg-slate-900 px-3 py-1 relative z-10",
            ),
            cls="flex items-center justify-center my-6",
            data_testid="decade-marker",
        )

        # Entry cards
        cards = []
        for entry in entries:
            if entry["type"] == "photo":
                # Confidence bar
                prob = entry.get("prob_range", [])
                conf = entry.get("confidence", "medium")
                conf_bar = None
                if prob and len(prob) == 2:
                    # Bar width relative to range span
                    range_span = prob[1] - prob[0]
                    if conf == "high":
                        bar_cls = "bg-amber-500/60"
                    elif conf == "medium":
                        bar_cls = "bg-amber-500/35"
                    else:
                        bar_cls = "bg-amber-500/20"
                    conf_bar = Div(
                        Div(
                            cls=f"h-full rounded-full {bar_cls}",
                            style="width: 100%",
                        ),
                        Span(f"{prob[0]}\u2013{prob[1]}", cls="text-[9px] text-slate-500 ml-2 whitespace-nowrap"),
                        cls="flex items-center gap-1 mt-1.5",
                        data_testid="confidence-bar",
                        title=f"Estimated range: {prob[0]}\u2013{prob[1]} ({conf} confidence)",
                    )

                # Date badge
                badge_text = f"c. {entry['decade']}s"
                if conf == "high":
                    date_cls = "bg-amber-800/80 text-amber-100"
                elif conf == "medium":
                    date_cls = "bg-amber-800/50 border border-amber-600/50 text-amber-200/90"
                else:
                    date_cls = "border border-dashed border-amber-600/40 text-amber-400/60"

                # Age badge (when person filter active and birth year known)
                age_badge = None
                if person_birth_year and entry.get("year"):
                    age = entry["year"] - person_birth_year
                    if 0 <= age <= 120:
                        # Style by confidence: confirmed=solid, high=solid, medium=dashed, low=faded
                        if birth_year_source == "confirmed" or birth_year_confidence == "high":
                            age_cls = "bg-indigo-900/50 text-indigo-300 border border-indigo-700/30"
                            age_text = f"Age ~{age}"
                        elif birth_year_confidence == "medium":
                            age_cls = "bg-indigo-900/30 text-indigo-300/80 border border-dashed border-indigo-700/30"
                            age_text = f"Age ~{age}"
                        else:
                            age_cls = "bg-indigo-900/20 text-indigo-400/50 border border-dashed border-indigo-800/30"
                            age_text = f"~{age}?"
                        age_badge = Span(
                            age_text,
                            cls=f"text-[10px] px-1.5 py-0.5 rounded {age_cls}",
                            data_testid="age-badge",
                        )

                # People names (highlight filtered people in multi-person mode)
                people_line = None
                highlighted = entry.get("highlighted_people", [])
                if entry.get("people"):
                    if len(person_identities) > 1 and highlighted:
                        # Bold the filtered people, dim the others
                        parts = []
                        for name in entry["people"][:4]:
                            if name in highlighted:
                                parts.append(Span(name, cls="text-amber-300 font-medium"))
                            else:
                                parts.append(Span(name))
                            parts.append(", ")
                        if parts:
                            parts.pop()  # remove trailing comma
                        if len(entry["people"]) > 4:
                            parts.append(f" +{len(entry['people']) - 4} more")
                        people_line = P(*parts, cls="text-sm sm:text-xs text-slate-400 mt-1 truncate")
                    else:
                        names = ", ".join(entry["people"][:4])
                        if len(entry["people"]) > 4:
                            names += f" +{len(entry['people']) - 4} more"
                        people_line = P(names, cls="text-sm sm:text-xs text-slate-400 mt-1 truncate")

                card = A(
                    Div(
                        # Photo thumbnail
                        Div(
                            Img(
                                src=photo_url(entry["filename"]),
                                cls="w-full h-full object-cover",
                                loading="lazy",
                                alt=f"Archive photo {entry['filename']}",
                            ),
                            Span(
                                badge_text,
                                cls=f"absolute bottom-1.5 left-1.5 text-[10px] font-serif px-1.5 py-0.5 rounded backdrop-blur-sm {date_cls}",
                                data_testid="date-badge",
                                data_confidence=conf,
                            ),
                            cls="aspect-[4/3] overflow-hidden relative rounded-t-lg",
                        ),
                        # Card details
                        Div(
                            Div(
                                Span(f"c. {entry['year']}", cls="text-sm sm:text-xs font-serif text-amber-400/80"),
                                age_badge,
                                cls="flex items-center gap-2",
                            ),
                            people_line,
                            P(entry.get("collection", ""), cls="text-[10px] text-slate-600 mt-0.5")
                            if entry.get("collection")
                            else None,
                            conf_bar,
                            cls="p-3",
                        ),
                        cls="bg-slate-800/70 rounded-lg border border-slate-700/50 hover:border-amber-500/50 transition-all duration-300 hover:scale-[1.02] hover:shadow-lg w-full",
                    ),
                    href=f"{nav_prefix}/photo/{entry['photo_id']}",
                    cls="block",
                    data_testid="timeline-photo-card",
                )
                cards.append(Div(card, cls="ml-8 sm:ml-12 mb-4"))

            elif entry["type"] == "life_event":
                # Life event from Supabase
                le_type = entry.get("event_type", "other")
                le_color = "border-indigo-600/50 bg-indigo-950/20"

                card = Div(
                    Div(
                        Div(
                            Span(entry.get("title", ""), cls="text-sm font-medium text-indigo-200 leading-snug"),
                            Span(str(entry["year"]), cls="text-sm sm:text-xs font-serif text-indigo-400 ml-2"),
                            cls="flex items-center gap-1",
                        ),
                        P(entry["description"], cls="text-sm sm:text-xs text-slate-400 leading-relaxed mt-1.5")
                        if entry.get("description")
                        else None,
                        P(entry.get("location", ""), cls="text-[10px] text-slate-500 mt-1 italic")
                        if entry.get("location")
                        else None,
                        cls=f"p-4 rounded-lg border-l-4 {le_color}",
                    ),
                    cls="ml-8 sm:ml-12 mb-4",
                    data_testid="timeline-life-event",
                )
                cards.append(card)

            else:  # context event
                cat = entry.get("category", "")
                color_cls = category_colors.get(cat, "border-slate-600/50 bg-slate-800/30")

                # Category icon
                cat_icons = {
                    "holocaust": "\U0001f56f\ufe0f",
                    "persecution": "\u26a0\ufe0f",
                    "liberation": "\u2728",
                    "immigration": "\U0001f6a2",
                    "community": "\U0001f3db\ufe0f",
                    "political": "\U0001f3db\ufe0f",
                }
                icon = cat_icons.get(cat, "\U0001f4cd")

                card = Div(
                    Div(
                        Div(
                            Span(icon, cls="text-base"),
                            Div(
                                Span(
                                    str(entry["year"]), cls="text-sm sm:text-xs font-serif text-slate-300 font-medium"
                                ),
                                H3(
                                    entry["title"],
                                    cls="text-sm font-medium text-white leading-snug",
                                    data_testid="context-event-title",
                                ),
                                cls="flex-1",
                            ),
                            cls="flex items-start gap-2.5",
                        ),
                        P(entry["description"], cls="text-sm sm:text-xs text-slate-400 leading-relaxed mt-2"),
                        P(entry.get("source", ""), cls="text-[9px] text-slate-600 mt-2 italic")
                        if entry.get("source")
                        else None,
                        cls=f"p-4 rounded-lg border-l-4 {color_cls}",
                    ),
                    cls="ml-8 sm:ml-12 mb-4",
                    data_testid="timeline-context-event",
                )
                cards.append(card)

        decade_sections.append(Div(marker, *cards))

    # Navigation links (matches /photos and /people pattern)
    nav_links = _main_mod._public_nav_links(active="timeline", user=user, community_slug=community_slug)

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .timeline-line {
            position: absolute;
            left: 1rem;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(to bottom, transparent 0%, #D4A574 5%, #D4A574 95%, transparent 100%);
        }
        @media (min-width: 640px) {
            .timeline-line { left: 1.5rem; }
        }
    """)

    # Share button JS (clipboard copy)
    share_js = Script("""
        document.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-action="share-story"]');
            if (!btn) return;
            navigator.clipboard.writeText(window.location.href).then(function() {
                var toast = document.getElementById('timeline-toast');
                if (toast) {
                    toast.textContent = 'Link copied!';
                    toast.classList.remove('opacity-0');
                    toast.classList.add('opacity-100');
                    setTimeout(function() {
                        toast.classList.remove('opacity-100');
                        toast.classList.add('opacity-0');
                    }, 2000);
                }
            });
        });
    """)

    return (
        Title(f"{story_title} — Rhodesli Heritage Archive"),
        Meta(property="og:title", content=f"{story_title} — Rhodesli Heritage Archive"),
        Meta(property="og:description", content=story_subtitle),
        Meta(name="description", content=f"Timeline of the Jewish community of Rhodes. {story_subtitle}"),
        page_style,
        share_js,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="flex items-center gap-3 sm:gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            # Header
            Section(
                Div(
                    H1(story_title, cls="text-3xl font-serif font-bold text-white mb-2"),
                    P(story_subtitle, cls="text-slate-400 text-sm"),
                    cls="max-w-4xl mx-auto px-6 pt-10 pb-4",
                ),
            ),
            # Controls (sticky below nav)
            Section(
                Div(
                    # Person filter
                    Div(
                        Span("Person:", cls="text-sm text-slate-400 mr-2"),
                        Select(
                            *person_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5",
                            data_testid="person-filter",
                            onchange=f"window.location.href='{nav_prefix}/timeline?person=' + encodeURIComponent(this.value) + '&start={start or ''}&end={end or ''}&context={context}&collection=' + encodeURIComponent('{collection or ''}')",
                        ),
                        cls="flex items-center gap-2",
                    ),
                    # Collection filter
                    Div(
                        Span("Collection:", cls="text-sm text-slate-400 mr-2"),
                        Select(
                            Option("All collections", value=""),
                            *[Option(c, value=c, selected=(collection == c)) for c in all_collections],
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-5 py-4 sm:px-3 sm:py-1.5",
                            data_testid="collection-filter",
                            onchange=f"window.location.href='{nav_prefix}/timeline?collection=' + encodeURIComponent(this.value) + '&person={person or ''}&people={people or ''}&start={start or ''}&end={end or ''}&context={context}'",
                        ),
                        cls="flex items-center gap-2",
                    )
                    if all_collections
                    else None,
                    # Share button
                    Div(
                        Button(
                            "\U0001f517 Share This Story",
                            cls="px-5 py-4 sm:px-3 sm:py-1.5 text-sm bg-slate-800 text-slate-300 rounded-lg border border-slate-700 hover:border-amber-700/30 hover:text-white transition-colors",
                            data_action="share-story",
                            data_testid="share-story-btn",
                        ),
                        # Toast
                        Div(
                            "",
                            id="timeline-toast",
                            cls="opacity-0 transition-opacity duration-300 text-sm sm:text-xs text-emerald-400 ml-3",
                        ),
                        cls="flex items-center",
                    ),
                    cls="max-w-4xl mx-auto px-6 flex flex-wrap items-center justify-between gap-4 py-3",
                ),
                cls="sticky top-16 z-40 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800/50",
            ),
            # Timeline (lazy loading — show enough decades to include ~20 photos, load rest on scroll)
            Section(
                Div(
                    # The vertical line
                    Div(cls="timeline-line", data_testid="timeline-line"),
                    # Show decades until we have >=20 photo entries or exhaust them
                    *(_tl_initial := _timeline_initial_decades(decade_sections, decades_order, decades_map, limit=20)),
                    # Lazy sentinel for remaining decades
                    (
                        Div(
                            Div(
                                cls="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"
                            ),
                            P("Loading more decades...", cls="text-slate-500 text-sm sm:text-xs mt-2"),
                            id="timeline-lazy-sentinel",
                            cls="flex flex-col items-center py-8",
                            hx_get=f"{nav_prefix}/api/timeline/more?offset={len(_tl_initial)}&person={_url_quote(person or '')}&people={_url_quote(people or '')}&start={start or ''}&end={end or ''}&context={context}&collection={_url_quote(collection or '')}",
                            hx_trigger="revealed",
                            hx_swap="outerHTML",
                        )
                        if len(_tl_initial) < len(decade_sections)
                        else None
                    ),
                    # Empty state
                    Div(
                        Div(
                            Div(cls="w-2 h-2 rounded-full bg-slate-600 mt-1"),
                            Div(cls="w-px h-16 border-l-2 border-dashed border-slate-700 my-2"),
                            Div(cls="w-2 h-2 rounded-full bg-slate-600 mb-6"),
                            cls="flex flex-col items-center",
                        ),
                        P(
                            "No photos or events match your filters.",
                            cls="text-slate-500 text-center text-sm font-medium",
                        ),
                        A(
                            "Clear filters and view full timeline \u2192",
                            href=f"{nav_prefix}/timeline",
                            cls="text-indigo-400 hover:text-indigo-300 text-sm sm:text-xs block text-center mt-3 transition-colors active:scale-95",
                        ),
                        cls="flex flex-col items-center justify-center py-16",
                    )
                    if not decade_sections
                    else None,
                    cls="relative",
                    data_testid="timeline-container",
                    id="timeline",
                ),
                cls="max-w-4xl mx-auto px-6 pb-16",
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-sm sm:text-xs text-slate-500 mb-1 font-serif"),
                    P(
                        "Preserving the memory of the Jewish community of Rhodes",
                        cls="text-[10px] text-slate-600 italic",
                    ),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


def _timeline_initial_decades(decade_sections, decades_order, decades_map, limit=20):
    """Return enough decade sections to include at least `limit` photo entries."""
    result = []
    photo_count = 0
    for i, dec in enumerate(decades_order):
        result.append(decade_sections[i])
        photo_count += sum(1 for e in decades_map[dec] if e["type"] == "photo")
        if photo_count >= limit:
            break
    return result


@rt("/api/timeline/more")
def get(
    offset: int = 3,
    person: str = "",
    people: str = "",
    start: int = None,
    end: int = None,
    context: str = "on",
    collection: str = "",
    request=None,
):
    """HTMX endpoint for timeline lazy loading — returns remaining decade sections."""
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    search_docs = _main_mod._load_search_index()
    date_labels = _main_mod._load_date_labels()
    context_events = _main_mod._load_context_events() if context != "off" else []

    # Resolve person filter
    person_ids = []
    if people:
        person_ids = [p.strip() for p in people.split(",") if p.strip()]
    elif person:
        person_ids = [person]

    person_photo_ids = None
    photo_person_map = {}
    if person_ids:
        person_photo_ids = set()
        for pid in person_ids:
            try:
                ident = registry.get_identity(pid)
            except KeyError:
                continue
            if not ident:
                continue
            face_ids = [
                f if isinstance(f, str) else f.get("face_id", "")
                for f in ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            ]
            pname = ensure_utf8_display(ident.get("name", ""))
            for fid in face_ids:
                photo_id = _main_mod.get_photo_id_for_face(fid)
                if photo_id:
                    person_photo_ids.add(photo_id)
                    photo_person_map.setdefault(photo_id, set()).add(pname)

    person_identity = None
    if len(person_ids) == 1:
        try:
            person_identity = registry.get_identity(person_ids[0])
        except KeyError:
            pass

    # Build timeline entries (same logic as /timeline)
    timeline_entries = []
    for doc in search_docs:
        photo_id = doc.get("cache_photo_id", doc.get("photo_id", ""))
        best_year = doc.get("best_year_estimate")
        decade_val = doc.get("estimated_decade")
        if not best_year and not decade_val:
            continue
        year = best_year or decade_val
        if not year:
            continue
        if start and year < start:
            continue
        if end and year > end:
            continue
        if person_photo_ids is not None and photo_id not in person_photo_ids:
            continue
        photo_data = (_main_mod._photo_cache or {}).get(photo_id, {})
        filename = photo_data.get("filename", "")
        photo_collection = photo_data.get("collection", "")
        if collection and photo_collection != collection:
            continue
        label = date_labels.get(photo_id, {})
        faces = photo_data.get("faces", [])
        people_names = []
        for face in faces:
            fid = face.get("face_id", "")
            ident_for_face = _main_mod.get_identity_for_face(registry, fid)
            if (
                ident_for_face
                and ident_for_face.get("state") == "CONFIRMED"
                and not ident_for_face.get("name", "").startswith("Unidentified")
            ):
                people_names.append(ident_for_face["name"])
        highlighted_people = sorted(photo_person_map.get(photo_id, set()))
        timeline_entries.append(
            {
                "type": "photo",
                "year": year,
                "decade": decade_val or (year // 10 * 10),
                "photo_id": photo_id,
                "filename": filename,
                "collection": photo_collection,
                "confidence": label.get("confidence", "medium"),
                "prob_range": label.get("probable_range", []),
                "people": people_names,
                "highlighted_people": highlighted_people,
                "scene": label.get("scene_description", ""),
            }
        )

    # Add context events
    person_era_start = None
    person_era_end = None
    if person_photo_ids is not None and timeline_entries:
        photo_years = [e["year"] for e in timeline_entries if e["type"] == "photo"]
        if photo_years:
            person_era_start = min(photo_years) - 30
            person_era_end = max(photo_years) + 10

    for event in context_events:
        year = event.get("year", 0)
        if start and year < start:
            continue
        if end and year > end:
            continue
        if person_era_start is not None and (year < person_era_start or year > person_era_end):
            continue
        timeline_entries.append(
            {
                "type": "context",
                "year": year,
                "decade": year // 10 * 10,
                "title": event.get("title", ""),
                "description": event.get("description", ""),
                "category": event.get("category", ""),
                "source": event.get("source", ""),
            }
        )

    timeline_entries.sort(key=lambda e: e["year"])

    # Group by decade
    decades_order = []
    decades_map = {}
    for entry in timeline_entries:
        dec = entry["decade"]
        if dec not in decades_map:
            decades_map[dec] = []
            decades_order.append(dec)
        decades_map[dec].append(entry)

    # Age computation
    person_birth_year = None
    if person_identity:
        iid = person_identity.get("identity_id", "")
        person_birth_year, _, _ = _main_mod._get_birth_year(iid, person_identity, include_unreviewed=False)

    category_colors = {
        "holocaust": "border-red-700/60 bg-red-950/30",
        "persecution": "border-red-800/50 bg-red-950/20",
        "liberation": "border-emerald-700/50 bg-emerald-950/20",
        "immigration": "border-blue-700/50 bg-blue-950/20",
        "community": "border-amber-700/50 bg-amber-950/20",
        "political": "border-slate-600/50 bg-slate-800/30",
    }

    # Build decade sections (same rendering as /timeline)
    decade_sections = []
    for dec in decades_order:
        entries = decades_map[dec]
        marker = Div(
            Div(
                Span(f"{dec}s", cls="text-xl sm:text-lg font-serif font-bold text-amber-400/80"),
                cls="bg-slate-900 px-3 py-1 relative z-10",
            ),
            cls="flex items-center justify-center my-6",
            data_testid="decade-marker",
        )
        cards = []
        for entry in entries:
            if entry["type"] == "photo":
                conf = entry.get("confidence", "medium")
                age_badge = None
                if person_birth_year:
                    age = entry["year"] - person_birth_year
                    if 0 < age < 120:
                        age_badge = Span(f"Age ~{age}", cls="text-[10px] text-amber-300/60 ml-2")
                year_label = str(entry["year"])
                if conf == "high":
                    year_cls = "text-amber-200 font-semibold"
                elif conf == "medium":
                    year_cls = "text-amber-300/70"
                else:
                    year_cls = "text-amber-400/50 italic"
                cards.append(
                    Div(
                        Div(
                            Div(
                                cls="w-3 h-3 rounded-full bg-amber-700/80 border-2 border-amber-500/50 absolute -left-[6px] top-5"
                            ),
                            cls="relative",
                        ),
                        Div(
                            A(
                                Img(
                                    src=photo_url(entry["filename"]),
                                    cls="w-full h-40 sm:h-48 object-cover rounded-t-lg",
                                    loading="lazy",
                                    alt=f"Archive photo {entry['filename']}",
                                ),
                                href=f"{nav_prefix}/photo/{entry['photo_id']}",
                            ),
                            Div(
                                Div(Span(year_label, cls=year_cls), age_badge, cls="flex items-baseline"),
                                P(entry.get("collection", ""), cls="text-[10px] text-slate-500")
                                if entry.get("collection")
                                else None,
                                P(", ".join(entry.get("people", [])[:4]), cls="text-sm sm:text-xs text-slate-400 mt-1")
                                if entry.get("people")
                                else None,
                                cls="p-3",
                            ),
                            cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden hover:border-slate-600 transition-colors",
                        ),
                        cls="ml-8 sm:ml-12 mb-4",
                        data_testid="timeline-entry",
                    )
                )
            elif entry["type"] == "context":
                cat = entry.get("category", "")
                color_cls = category_colors.get(cat, "border-slate-600/50 bg-slate-800/30")
                cards.append(
                    Div(
                        Div(
                            Div(
                                cls="w-2.5 h-2.5 rounded-full bg-slate-600 border-2 border-slate-500/50 absolute -left-[5px] top-5"
                            ),
                            cls="relative",
                        ),
                        Div(
                            Div(
                                Span(str(entry["year"]), cls="text-sm font-serif text-slate-300"),
                                Span(f" \u00b7 {entry['title']}", cls="text-sm text-slate-400"),
                                cls="flex items-start gap-2.5",
                            ),
                            P(entry["description"], cls="text-sm sm:text-xs text-slate-400 leading-relaxed mt-2"),
                            P(entry.get("source", ""), cls="text-[9px] text-slate-600 mt-2 italic")
                            if entry.get("source")
                            else None,
                            cls=f"p-4 rounded-lg border-l-4 {color_cls}",
                        ),
                        cls="ml-8 sm:ml-12 mb-4",
                        data_testid="timeline-context-event",
                    )
                )
        decade_sections.append(Div(marker, *cards))

    # Return only sections from offset onward
    remaining = decade_sections[offset:]
    if not remaining:
        return ""

    return tuple(remaining)


# ---- Face Comparison Tool ----


def _upload_stage_item(stage_id: str, label: str, status: str = "pending") -> object:
    """Build a single stage indicator for progressive upload UI."""
    icons = {
        "pending": '<span class="text-slate-600 text-lg">○</span>',
        "active": '<svg class="animate-spin h-5 w-5 text-indigo-400 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
        "done": '<span class="text-green-400 text-lg">✓</span>',
        "error": '<span class="text-red-400 text-lg">✗</span>',
    }
    text_cls = {
        "pending": "text-slate-600",
        "active": "text-white font-medium",
        "done": "text-slate-300",
        "error": "text-red-400",
    }
    return Div(
        NotStr(icons.get(status, icons["pending"])),
        Span(label, cls=f"ml-3 {text_cls.get(status, text_cls['pending'])}"),
        Span("", cls="ml-auto text-sm sm:text-xs text-slate-500", id=f"stage-detail-{stage_id}"),
        cls="flex items-center",
        id=f"stage-{stage_id}",
        data_stage=stage_id,
    )


def _upload_progress_script() -> str:
    """JavaScript for SSE-based progressive upload with stage indicators."""
    return """
<script>
function validateUploadFile(form) {
    var input = form.querySelector('input[type="file"]');
    if (!input || !input.files || !input.files.length) {
        return 'Please select a photo to upload.';
    }
    var file = input.files[0];
    var validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (validTypes.indexOf(file.type) === -1) {
        return 'Please upload a JPEG, PNG, or WebP image.';
    }
    if (file.size > 10 * 1024 * 1024) {
        return 'File is too large (max 10 MB). Please choose a smaller photo.';
    }
    return null;
}

function startProgressUpload(form, flow) {
    // Client-side validation first
    var validationError = validateUploadFile(form);
    if (validationError) {
        var results = document.getElementById('compare-results') || document.getElementById('fc-results');
        if (results) results.innerHTML = '<p class="text-amber-400 text-center py-4">' + validationError + '</p>';
        return false;
    }

    var formData = new FormData(form);
    formData.append('flow', flow || 'compare');

    // Show progress, hide spinner
    var progress = document.getElementById('upload-progress');
    var spinner = document.getElementById('upload-spinner') || document.getElementById('fc-loading');
    var results = document.getElementById('compare-results') || document.getElementById('fc-results');
    if (progress) { progress.classList.remove('hidden'); progress.style.display = ''; }
    if (spinner) { spinner.classList.add('hidden'); spinner.style.display = 'none'; }

    // Reset all stage indicators to pending
    var stages = ['received', 'detecting', 'comparing', 'estimating', 'complete'];
    stages.forEach(function(s) {
        var el = document.getElementById('stage-' + s);
        if (!el) return;
        var icon = el.querySelector('span:first-child, svg');
        var label = el.querySelector('span.ml-3');
        if (icon) icon.outerHTML = '<span class="text-slate-600 text-lg">\\u25CB</span>';
        if (label) label.className = 'ml-3 text-slate-600';
    });

    // Disable submit button
    var btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }

    // Timeout: warn user after 45s
    var timeoutId = setTimeout(function() {
        var detail = document.getElementById('stage-detail-detecting') || document.getElementById('stage-detail-comparing');
        if (detail) detail.textContent = 'Taking longer than expected...';
    }, 45000);

    fetch('/api/upload/stream', {
        method: 'POST',
        body: formData
    }).then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';

        function readChunk() {
            reader.read().then(function(result) {
                if (result.done) { clearTimeout(timeoutId); return; }
                buffer += decoder.decode(result.value, {stream: true});

                var lines = buffer.split('\\n');
                buffer = lines.pop(); // keep incomplete line

                lines.forEach(function(line) {
                    if (line.startsWith('data: ')) {
                        try {
                            var data = JSON.parse(line.substring(6));
                            handleStageEvent(data, flow);
                        } catch(e) {}
                    }
                });
                readChunk();
            }).catch(function() {
                clearTimeout(timeoutId);
                handleStageEvent({stage: 'error', message: 'Connection lost. Please try again.'}, flow);
            });
        }
        readChunk();
    }).catch(function(err) {
        clearTimeout(timeoutId);
        if (progress) { progress.classList.add('hidden'); progress.style.display = 'none'; }
        if (results) results.innerHTML = '<p class="text-red-400 text-center py-4">Connection error. Please try again.</p>';
        if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    });

    return false; // prevent default form submission
}

function handleStageEvent(data, flow) {
    var stageOrder = ['received', 'detecting', 'comparing', 'estimating', 'complete'];
    var stageIdx = stageOrder.indexOf(data.stage);

    // Mark completed stages
    stageOrder.forEach(function(s, i) {
        var el = document.getElementById('stage-' + s);
        if (!el) return;
        var icon = el.querySelector('span:first-child, svg');
        var label = el.querySelector('span.ml-3');

        if (data.stage === 'error') {
            // Show error on current active stage
            return;
        }

        if (i < stageIdx) {
            // Completed
            if (icon) icon.outerHTML = '<span class="text-green-400 text-lg">✓</span>';
            if (label) label.className = 'ml-3 text-slate-300';
        } else if (i === stageIdx) {
            // Active / just completed
            if (data.stage === s) {
                if (icon) icon.outerHTML = '<span class="text-green-400 text-lg">✓</span>';
                if (label) { label.className = 'ml-3 text-white font-medium'; label.textContent = data.message || label.textContent; }
            }
        }
    });

    // Update detail text
    var detail = document.getElementById('stage-detail-' + data.stage);
    if (detail && data.stage === 'detected') detail.textContent = data.detect_time ? data.detect_time + 's' : '';
    if (detail && data.stage === 'compared') detail.textContent = data.compare_time ? data.compare_time + 's' : '';

    // Handle completion — redirect to results
    if (data.stage === 'complete' && data.redirect) {
        setTimeout(function() { window.location.href = data.redirect; }, 500);
    }

    // Handle error
    if (data.stage === 'error') {
        var progress = document.getElementById('upload-progress');
        if (progress) { progress.classList.add('hidden'); progress.style.display = 'none'; }
        var results = document.getElementById('compare-results') || document.getElementById('fc-results');
        if (results) results.innerHTML = '<p class="text-amber-400 text-center py-4">' + (data.message || 'An error occurred.') + '</p>';
        var btn = document.querySelector('button[type="submit"]');
        if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    }
}
</script>
"""


def _queue_compare_upload_for_review(upload_id: str, meta: dict) -> None:
    """Ensure compare uploads are visible in admin pending queue.

    Compare uploads are user contributions by default, so they should appear in
    pending review without requiring a second manual submit action.
    """
    pending = _main_mod._load_pending_uploads()
    job_id = f"compare_{upload_id}"
    uploads = pending.setdefault("uploads", {})
    if job_id in uploads:
        return

    uploads[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "submitted_at": datetime.now().isoformat(),
        "submitted_by": "compare_auto",
        "source": "compare_upload",
        "collection": "",
        "file_count": 1,
        "files": [meta.get("original_filename", f"{upload_id}.jpg")],
        "compare_upload_id": upload_id,
        "image_key": meta.get("image_key", f"uploads/compare/{upload_id}.jpg"),
        "faces_detected": meta.get("faces_detected", 0),
        "top_match": meta.get("top_match"),
    }
    _main_mod._save_pending_uploads(pending)

    # Dual-write to Supabase
    from app.supabase_data import sync_pending_upload

    sync_pending_upload(job_id, uploads[job_id])


def _save_compare_upload(content: bytes, filename: str, faces: list, results: list, status: str = "uploaded") -> str:
    """Persist a compare upload to R2 (preferred) or local filesystem.

    Returns the upload UUID.
    """
    import uuid as _uuid
    import mimetypes
    from core.storage import can_write_r2, upload_bytes_to_r2

    upload_id = _uuid.uuid4().hex[:12]
    suffix = _Path(filename).suffix or ".jpg"
    image_key = f"uploads/compare/{upload_id}{suffix}"

    # Save metadata
    meta = {
        "upload_id": upload_id,
        "uploaded_at": datetime.now().isoformat(),
        "original_filename": filename,
        "image_key": image_key,
        "faces_detected": len(faces) if faces else 0,
        "status": status,
        "top_match": {
            "identity_name": results[0].get("identity_name", "Unknown") if results else None,
            "confidence_pct": results[0].get("confidence_pct", 0) if results else 0,
            "tier": results[0].get("tier", "WEAK") if results else None,
        },
    }
    meta_key = f"uploads/compare/{upload_id}_meta.json"

    if can_write_r2():
        # Save to R2 for persistence across deploys
        content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        upload_bytes_to_r2(image_key, content, content_type=content_type)
        upload_bytes_to_r2(meta_key, json.dumps(meta, indent=2).encode(), content_type="application/json")
    else:
        # Fall back to local filesystem (will not survive Railway restarts)
        upload_dir = _Path("uploads/compare")
        upload_dir.mkdir(parents=True, exist_ok=True)
        (_Path("uploads/compare") / f"{upload_id}{suffix}").write_bytes(content)
        (_Path("uploads/compare") / f"{upload_id}_meta.json").write_text(json.dumps(meta, indent=2))

    try:
        _queue_compare_upload_for_review(upload_id, meta)
    except Exception as e:
        logging.warning(f"[compare] Could not queue upload {upload_id} for admin review: {e}")

    return upload_id


@rt("/api/upload/stream")
async def post(request):
    """SSE streaming endpoint for upload processing with progressive feedback.

    Returns text/event-stream with stage events as processing completes.
    Works for both /compare and /facecompare upload flows.
    """
    # Rate limiting
    client_ip = request.client.host if request and request.client else "unknown"
    if not check_rate_limit(client_ip):
        return Response("Rate limit exceeded", status_code=429)

    import time as _time
    import json as _json
    import tempfile

    form = await request.form()
    photo = form.get("photo")
    flow = form.get("flow", "compare")  # "compare" or "facecompare"

    async def event_generator():
        t0 = _time.time()

        def sse_event(data):
            return f"data: {_json.dumps(data)}\n\n"

        # --- Validation ---
        if not photo:
            yield sse_event({"stage": "error", "message": "No photo uploaded."})
            return

        content = await photo.read()
        original_filename = photo.filename or "upload.jpg"
        suffix = _Path(original_filename).suffix.lower() or ".jpg"

        if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            yield sse_event({"stage": "error", "message": "Please upload a JPEG, PNG, or WebP image."})
            return

        if len(content) > 10 * 1024 * 1024:
            yield sse_event({"stage": "error", "message": "File is too large (max 10 MB)."})
            return

        yield sse_event({"stage": "received", "message": "Photo received", "filename": original_filename})

        # --- Check ML availability ---
        has_insightface = False
        try:
            import cv2
            from insightface.app import FaceAnalysis  # noqa: F401
            from core.ingest_inbox import extract_faces_hybrid

            has_insightface = True
        except ImportError:
            pass

        if not has_insightface:
            yield sse_event({"stage": "error", "message": "Face detection is being set up. Check back soon."})
            return

        # --- Face Detection ---
        yield sse_event({"stage": "detecting", "message": "Detecting faces..."})

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = _Path(tmp.name)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as ml_tmp:
            ml_tmp.write(content)
            ml_path = _Path(ml_tmp.name)

        try:
            # Resize for ML
            img = cv2.imread(str(ml_path))
            if img is not None:
                h, w = img.shape[:2]
                _ML_MAX_DIM = 640
                if max(h, w) > _ML_MAX_DIM:
                    scale = _ML_MAX_DIM / max(h, w)
                    new_w, new_h = int(w * scale), int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(str(ml_path), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

            t1 = _time.time()
            faces, _, _ = extract_faces_hybrid(ml_path)
            detect_time = _time.time() - t1

            if not faces:
                yield sse_event(
                    {"stage": "error", "message": "No faces detected. Try a clearer photo with visible faces."}
                )
                return

            yield sse_event(
                {
                    "stage": "detected",
                    "message": f"Found {len(faces)} face{'s' if len(faces) != 1 else ''}",
                    "face_count": len(faces),
                    "detect_time": round(detect_time, 2),
                }
            )

            # --- Embedding Comparison ---
            yield sse_event({"stage": "comparing", "message": "Searching archive..."})

            t1 = _time.time()
            query_embedding = faces[0]["mu"]
            face_data = _main_mod.get_face_data()
            registry = _main_mod.load_registry()
            crop_files = _main_mod.get_crop_files()

            from core.neighbors import find_similar_faces

            results = find_similar_faces(
                query_embedding,
                face_data,
                registry=registry,
                limit=20,
            )
            compare_time = _time.time() - t1

            match_count = sum(1 for r in results if r.get("tier") in ("STRONG", "MODERATE"))
            yield sse_event(
                {
                    "stage": "compared",
                    "message": f"{match_count} potential match{'es' if match_count != 1 else ''} found",
                    "match_count": match_count,
                    "total_results": len(results),
                    "archive_size": len(face_data),
                    "compare_time": round(compare_time, 2),
                }
            )

            # --- Date Estimation (if available) ---
            date_estimate = None
            try:
                from rhodesli_ml.date_inference.service import DateEstimationService

                date_svc = DateEstimationService()
                if date_svc.is_available():
                    yield sse_event({"stage": "estimating", "message": "Estimating photo date..."})
                    date_result = date_svc.predict(str(tmp_path))
                    if date_result:
                        date_estimate = date_result.get("predicted_decade")
                        yield sse_event(
                            {
                                "stage": "estimated",
                                "message": f"Estimated circa {date_estimate}s"
                                if date_estimate
                                else "Date estimation inconclusive",
                                "decade": date_estimate,
                            }
                        )
            except Exception:
                pass  # Date estimation is optional

            # --- Save & Complete ---
            yield sse_event({"stage": "saving", "message": "Saving results..."})

            upload_id = _main_mod._save_compare_upload(content, original_filename, faces, results)

            # Save comparison result to comparison_results.json so the result page can find it
            # Session 83a fix: SSE was saving upload metadata but NOT the result entry
            try:
                result_data = {
                    "result_id": upload_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "query_type": "compare_upload" if flow == "compare" else "facecompare_upload",
                    "query_name": original_filename,
                    "matches": results,
                    "date_estimate": date_estimate,
                    "face_count": len(faces),
                    "responses": [],
                }
                _main_mod._save_comparison_result(result_data)
                logging.info(f"[compare] Saved result {upload_id} with {len(results)} matches")
            except Exception as e:
                logging.error(f"[compare] Failed to save comparison result {upload_id}: {e}")

            # Save face embeddings for face selection
            import pickle
            from core.storage import can_write_r2, upload_bytes_to_r2

            face_save_data = [
                {
                    "mu": f["mu"].tolist(),
                    "bbox": f.get("bbox", [0, 0, 0, 0]) if not hasattr(f.get("bbox"), "tolist") else f["bbox"].tolist(),
                }
                for f in faces
            ]
            faces_pkl = pickle.dumps(face_save_data)
            if can_write_r2():
                upload_bytes_to_r2(f"uploads/compare/{upload_id}_faces.pkl", faces_pkl)
            else:
                upload_dir = _Path("uploads/compare")
                upload_dir.mkdir(parents=True, exist_ok=True)
                (upload_dir / f"{upload_id}_faces.pkl").write_bytes(faces_pkl)

            total_time = _time.time() - t0

            yield sse_event(
                {
                    "stage": "complete",
                    "message": "Analysis complete",
                    "upload_id": upload_id,
                    "face_count": len(faces),
                    "match_count": match_count,
                    "total_results": len(results),
                    "date_estimate": date_estimate,
                    "total_time": round(total_time, 2),
                    "redirect": f"/compare/result/{upload_id}"
                    if flow == "compare"
                    else f"/facecompare/result/{upload_id}",
                }
            )

        except Exception as e:
            yield sse_event({"stage": "error", "message": f"Processing error: {str(e)}"})
        finally:
            tmp_path.unlink(missing_ok=True)
            ml_path.unlink(missing_ok=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- Shareable Comparison Results ----


_comparison_results_cache = None


def _load_comparison_results() -> dict:
    """Load comparison results from data file."""
    global _comparison_results_cache
    if _comparison_results_cache is not None:
        return _comparison_results_cache
    path = _main_mod.data_path / "comparison_results.json"
    default = {"schema_version": 1, "results": {}}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                _comparison_results_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _comparison_results_cache = default
    else:
        _comparison_results_cache = default
    return _comparison_results_cache


def _save_comparison_result(result_data: dict) -> str:
    """Save a comparison result and return its ID.

    Gracefully handles disk-full errors — the comparison result is still
    returned (cached in memory) even if disk write fails.
    """
    global _comparison_results_cache
    data = _main_mod._load_comparison_results()
    result_id = result_data["result_id"]
    data["results"][result_id] = result_data
    _comparison_results_cache = data  # Always update in-memory cache
    try:
        path = _main_mod.data_path / "comparison_results.json"
        import portalocker

        with portalocker.Lock(str(path) + ".lock", timeout=5):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logging.warning(f"Could not save comparison result to disk: {e}")

    # Dual-write to Supabase
    from app.supabase_data import sync_comparison_result

    sync_comparison_result(result_id, result_data)

    return result_id


def _generate_result_id() -> str:
    """Generate a 12-character result ID."""
    return uuid.uuid4().hex[:12]


# ---- Connection Finder (Six Degrees) ----


def _load_social_graph():
    """Load and cache the unified social graph."""
    from rhodesli_ml.graph.social_graph import build_social_graph

    rel_graph = _main_mod._load_relationship_graph()
    cooccur_path = _main_mod.data_path / "co_occurrence_graph.json"
    cooccur = {"edges": []}
    if cooccur_path.exists():
        try:
            cooccur = json.loads(cooccur_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass
    return build_social_graph(rel_graph, cooccur)


def _connection_path_html(path_steps, registry, nav_prefix: str = ""):
    """Render a connection path as styled HTML steps."""
    if path_steps is None:
        return Div(
            P("No known connection found.", cls="text-slate-400 text-center py-8"),
            cls="mt-4",
        )
    if len(path_steps) == 0:
        return Div(
            P("Same person!", cls="text-emerald-400 text-center py-4"),
            cls="mt-4",
        )

    steps = []
    for i, step in enumerate(path_steps):
        from_id = step["from"]
        to_id = step["to"]
        edge = step["edge"]
        from_ident = _main_mod._safe_get_identity(registry, from_id)
        to_ident = _main_mod._safe_get_identity(registry, to_id)
        from_name = ensure_utf8_display(from_ident.get("name", "Unknown"))
        to_name = ensure_utf8_display(to_ident.get("name", "Unknown"))

        # Edge styling by category
        if edge.get("category") == "family":
            edge_color = "text-amber-400 bg-amber-900/30 border-amber-700/50"
            edge_icon = '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>'
        else:
            edge_color = "text-blue-400 bg-blue-900/30 border-blue-700/50"
            edge_icon = '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/></svg>'

        label = edge.get("label", edge.get("type", "connected"))

        if i == 0:
            steps.append(
                Div(
                    A(
                        from_name,
                        href=f"{nav_prefix}/person/{from_id}",
                        cls="text-white font-semibold hover:text-indigo-300 transition-colors",
                    ),
                    cls="px-4 py-2 bg-slate-800 rounded-lg border border-slate-700",
                )
            )

        # Arrow + relationship label
        steps.append(
            Div(
                Div(
                    NotStr(edge_icon),
                    Span(label, cls="text-sm sm:text-xs"),
                    cls=f"inline-flex items-center px-3 py-1 rounded-full border text-sm sm:text-xs {edge_color}",
                ),
                Div("", cls="w-px h-3 bg-slate-700 mx-auto"),
                cls="flex flex-col items-center my-1",
            )
        )

        # Target person
        steps.append(
            Div(
                A(
                    to_name,
                    href=f"{nav_prefix}/person/{to_id}",
                    cls="text-white font-semibold hover:text-indigo-300 transition-colors",
                ),
                cls="px-4 py-2 bg-slate-800 rounded-lg border border-slate-700",
            )
        )

    return Div(*steps, cls="flex flex-col items-center mt-6", data_testid="connection-path")


# =============================================================================
# TWO-PHOTO FACE COMPARISON — /compare/pair
# =============================================================================


# =============================================================================
# UNIFIED COMPARISON ENGINE (PRD-026, Session 85c)
# =============================================================================


# --- Gemini date estimation helper ---
# Simplified version of rhodesli_ml/scripts/generate_date_labels.py::call_gemini()
# for real-time single-photo estimation via the web upload.


@rt("/tree")
def get(person: str = "", show_theory: str = "true", photo_id: str = "", people: str = "", sess=None, request=None):
    """Family Tree — lazy-loading tree with search, zoom, expand/collapse (AD-185).

    Query params:
        person: Single person ID to center tree on
        photo_id: Source photo ID (for using face crops from that photo)
        people: Comma-separated person IDs (from photo page navigation)
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"

    # If people param provided (from photo page), pick the first as the focused person
    # but pass all of them to the JS for smart subtree computation
    people_list = [p.strip() for p in people.split(",") if p.strip()] if people else []
    if people_list and not person:
        person = people_list[0]

    # Person name for title/OG
    person_name = ""
    if person:
        registry = _main_mod.load_registry()
        try:
            p_ident = registry.get_identity(person)
            if p_ident:
                person_name = ensure_utf8_display(p_ident.get("name", ""))
        except KeyError:
            pass

    community_prefix = _main_mod.community_url_prefix(community_slug)
    title_text = f"{person_name}'s Family Tree" if person_name else "Family Tree"
    share_url = f"{community_prefix}/tree?person={person}" if person else f"{community_prefix}/tree"
    nav_links = _main_mod._public_nav_links(active="tree", user=user, community_slug=community_slug)

    page_style = Style("""
        html, body { margin: 0; } body { background-color: #080d1a; }
        #tree-container { width: 100%; height: calc(100vh - 260px); min-height: 400px; position: relative; }
        #tree-container svg { border-radius: 0.75rem; }
        .tree-search-results { position: absolute; top: 100%; left: 0; right: 0; max-height: 300px;
            overflow-y: auto; background: #151d2e; border: 1px solid rgba(148,163,184,0.12); border-radius: 0.5rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 100; backdrop-filter: blur(12px); }
        .tree-search-results .result-item { padding: 10px 14px; cursor: pointer; border-bottom: 1px solid rgba(148,163,184,0.08); transition: background 0.15s; }
        .tree-search-results .result-item:hover { background: rgba(99,102,241,0.12); }
        .tree-search-results .result-item .name { font-weight: 500; color: #f1f5f9; }
        .tree-search-results .result-item .badge { font-size: 11px; color: #8b9ab5; }
        .tree-zoom-controls { position: absolute; top: 12px; right: 12px; display: flex; flex-direction: column;
            gap: 4px; z-index: 50; }
        .tree-zoom-controls button { width: 36px; height: 36px; background: rgba(21,29,46,0.9); border: 1px solid rgba(148,163,184,0.12);
            border-radius: 8px; cursor: pointer; font-size: 18px; display: flex; align-items: center;
            justify-content: center; color: #8b9ab5; transition: all 0.2s; backdrop-filter: blur(8px); }
        .tree-zoom-controls button:hover { background: rgba(30,41,59,0.95); border-color: rgba(99,102,241,0.3); color: #f1f5f9; }
        .tree-node-popup { position: fixed; background: rgba(21,29,46,0.95); border: 1px solid rgba(148,163,184,0.12); border-radius: 12px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.6); padding: 4px 4px 8px; z-index: 200; min-width: 180px; backdrop-filter: blur(16px); }
        .tree-node-popup a, .tree-node-popup button { display: block; width: 100%; text-align: left;
            padding: 8px 12px; border: none; background: none; cursor: pointer; border-radius: 6px;
            font-size: 13px; color: #f1f5f9; text-decoration: none; transition: background 0.15s; font-family: 'Inter', system-ui, sans-serif; }
        .tree-node-popup a:hover, .tree-node-popup button:hover { background: rgba(99,102,241,0.15); }
        /* Timeline slider */
        #timeline-bar { width: 100%; background: rgba(15,20,32,0.85); border: 1px solid rgba(148,163,184,0.08);
            border-radius: 12px; padding: 12px 20px 8px; backdrop-filter: blur(8px); margin-top: 8px; }
        #timeline-bar.hidden { display: none; }
        #timeline-slider { -webkit-appearance: none; appearance: none; width: 100%; height: 6px; border-radius: 3px;
            background: linear-gradient(90deg, rgba(99,102,241,0.3), rgba(212,165,116,0.4)); outline: none; cursor: pointer; }
        #timeline-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 22px; height: 22px;
            border-radius: 50%; background: #d4a574; border: 3px solid #080d1a; cursor: grab; box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            transition: transform 0.15s ease; }
        #timeline-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }
        #timeline-slider::-webkit-slider-thumb:active { cursor: grabbing; transform: scale(1.1); }
        #timeline-year { font-family: 'Georgia', serif; font-size: 20px; color: #d4a574; font-weight: bold; }
        .timeline-ticks { display: flex; justify-content: space-between; padding: 0 2px; margin-top: 2px; }
        .timeline-ticks span { font-size: 10px; color: rgba(148,163,184,0.5); font-family: 'Inter', system-ui, sans-serif; }
    """)

    return (
        Title(f"{title_text} — Rhodesli"),
        Meta(property="og:title", content=f"{title_text} — Rhodesli"),
        Meta(
            property="og:description",
            content="Explore the Rhodes-Capeluto family tree — generations of a Sephardic Jewish family from Rhodes.",
        ),
        Meta(property="og:url", content=f"{_main_mod.SITE_URL}{share_url}"),
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Div(
                # Header
                Div(
                    H1(title_text, cls="text-2xl md:text-3xl font-serif font-bold text-white mb-2"),
                    P("Explore family relationships across generations.", cls="text-slate-400 mb-4"),
                    cls="mb-4",
                ),
                # Controls row: search + options
                Div(
                    # Search bar
                    Div(
                        Label("Search", cls="text-sm sm:text-xs text-slate-400 mb-1 block"),
                        Div(
                            Input(
                                type="text",
                                id="tree-search-input",
                                placeholder="Type a name to find someone...",
                                cls="w-full px-3 py-2 bg-slate-700 text-slate-200 rounded-lg border border-slate-600 focus:border-indigo-500 outline-none text-sm placeholder-slate-400",
                                autocomplete="off",
                            ),
                            Div(id="tree-search-results", cls="tree-search-results hidden"),
                            cls="relative",
                        ),
                        cls="flex-1 min-w-[200px]",
                    ),
                    # Show speculative toggle
                    Div(
                        Label(
                            Input(
                                type="checkbox",
                                id="tree-show-theory",
                                value="true",
                                checked=(show_theory != "false"),
                                cls="mr-2 rounded",
                            ),
                            "Show speculative",
                            cls="text-sm text-slate-400 flex items-center",
                        ),
                        cls="flex items-end pb-2",
                    ),
                    # Share button
                    Button(
                        NotStr(_main_mod._SHARE_ICON_SVG),
                        " Share",
                        cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1",
                        type="button",
                        data_action="share-photo",
                        data_share_url=share_url,
                    ),
                    cls="flex flex-wrap items-end gap-4 bg-slate-800/50 rounded-xl p-4 border border-slate-700 mb-4",
                ),
                # Tree visualization with zoom controls
                Div(
                    P("Loading family tree...", id="tree-loading", cls="text-center text-slate-500 py-8"),
                    Div(id="tree-container", cls="rounded-xl border border-slate-800/50"),
                    # Zoom controls
                    Div(
                        Button("+", type="button", data_action="tree-zoom-in", title="Zoom in"),
                        Button("\u2013", type="button", data_action="tree-zoom-out", title="Zoom out"),
                        Button("\u2302", type="button", data_action="tree-fit", title="Fit to screen"),
                        cls="tree-zoom-controls",
                    ),
                    cls="relative",
                ),
                # Photo timeline slider
                Div(
                    Div(
                        Span("", id="timeline-year"),
                        Span(
                            " — drag to see faces change through time",
                            id="timeline-hint",
                            cls="text-sm sm:text-xs text-slate-500 ml-2",
                        ),
                        cls="flex items-baseline mb-2",
                    ),
                    Input(type="range", id="timeline-slider", min="1870", max="2020", value="1945", step="1"),
                    Div(id="timeline-ticks", cls="timeline-ticks"),
                    id="timeline-bar",
                    cls="hidden",
                ),
                cls="max-w-6xl mx-auto px-6 pt-10 pb-16",
            ),
            # Popup container for node actions
            Div(id="tree-node-popup", cls="tree-node-popup hidden"),
            # family-chart library
            Script(src="https://d3js.org/d3.v7.min.js"),
            Script(src="/static/js/family-tree.js?v=83a"),
            Script(f"""
                document.addEventListener('DOMContentLoaded', function() {{
                    window.initRhodesliTree('{person}', '{show_theory}', {json.dumps(people_list)}, '{community_prefix}');
                }});
            """),
        ),
    )


# --- Tree API Endpoints (AD-185: Lazy loading tree) ---


def _build_tree_adjacency(show_theory=True):
    """Build adjacency maps from relationship graph for tree API.

    Unifies GEDCOM xrefs with linked identity UUIDs so the graph
    is one connected component instead of two disconnected clusters.
    """
    rel_graph = _main_mod._load_relationship_graph()
    manual_rels = [r for r in rel_graph.get("relationships", []) if r.get("source") != "gedcom"]
    current_gedcom_rels = _main_mod._load_current_gedcom_relationship_edges()
    combined_rels = manual_rels + current_gedcom_rels if current_gedcom_rels else rel_graph.get("relationships", [])
    rels = [r for r in combined_rels if not r.get("removed") and (show_theory or r.get("confidence") != "theory")]

    # Build GEDCOM xref -> identity UUID mapping to unify the graph
    gedcom_links = _main_mod._load_gedcom_face_links()
    xref_to_uuid = {}
    for identity_id, link_data in gedcom_links.items():
        gid = link_data.get("gedcom_id")
        if gid:
            xref_to_uuid[gid] = identity_id

    # Also build from gedcom_matches.json for comprehensive xref resolution
    # (Supabase gedcom_face_links may not have all confirmed matches)
    try:
        gm = _main_mod._load_gedcom_matches()
        for m in gm.get("matches", []):
            xref = m.get("gedcom_xref")
            uid = m.get("identity_id")
            if xref and uid and xref not in xref_to_uuid:
                xref_to_uuid[xref] = uid
    except Exception:
        pass

    def resolve(pid):
        return xref_to_uuid.get(pid, pid)

    ptc, ctp, pts = {}, {}, {}  # parent_to_children, child_to_parents, person_to_spouses
    for r in rels:
        a = resolve(r["person_a"])
        b = resolve(r["person_b"])
        if a == b:
            continue  # skip self-loops from merging
        if r["type"] == "parent_child":
            ptc.setdefault(a, set()).add(b)
            ctp.setdefault(b, set()).add(a)
        elif r["type"] == "spouse":
            pts.setdefault(a, set()).add(b)
            pts.setdefault(b, set()).add(a)
    return ptc, ctp, pts


def _build_tree_link_maps():
    """Build GEDCOM xref <-> identity maps for targeted tree resolution."""
    gedcom_links = _main_mod._load_gedcom_face_links()
    xref_to_uuid = {}
    uuid_to_gedcom = {}
    for identity_id, link_data in gedcom_links.items():
        gid = link_data.get("gedcom_id")
        if gid:
            xref_to_uuid[gid] = identity_id
            uuid_to_gedcom.setdefault(identity_id, set()).add(gid)

    try:
        gm = _main_mod._load_gedcom_matches()
        for match in gm.get("matches", []):
            xref = match.get("gedcom_xref")
            uid = match.get("identity_id")
            if xref and uid:
                xref_to_uuid.setdefault(xref, uid)
                uuid_to_gedcom.setdefault(uid, set()).add(xref)
    except Exception:
        pass

    return xref_to_uuid, uuid_to_gedcom


def _merge_tree_relationships(rels, ptc, ctp, pts, resolve, show_theory=True):
    """Merge normalized relationship edges into adjacency maps."""
    for rel in rels:
        if rel.get("removed") or (not show_theory and rel.get("confidence") == "theory"):
            continue
        a = resolve(rel["person_a"])
        b = resolve(rel["person_b"])
        if a == b:
            continue
        if rel["type"] == "parent_child":
            ptc.setdefault(a, set()).add(b)
            ctp.setdefault(b, set()).add(a)
        elif rel["type"] == "spouse":
            pts.setdefault(a, set()).add(b)
            pts.setdefault(b, set()).add(a)


def _tree_query_ids_for_person(pid, uuid_to_gedcom):
    """Return the raw GEDCOM IDs needed to expand a unified tree person."""
    if pid in uuid_to_gedcom:
        return set(uuid_to_gedcom[pid])
    if isinstance(pid, str) and pid.startswith("@"):
        return {pid}
    return set()


def _build_targeted_tree_adjacency(seed_ids, depth=1, show_theory=True):
    """Build a local tree slice without loading the full GEDCOM mirror."""
    xref_to_uuid, uuid_to_gedcom = _build_tree_link_maps()

    def resolve(pid):
        return xref_to_uuid.get(pid, pid)

    ptc, ctp, pts = {}, {}, {}
    rel_graph = _main_mod._load_relationship_graph()
    manual_rels = [r for r in rel_graph.get("relationships", []) if r.get("source") != "gedcom"]
    _merge_tree_relationships(manual_rels, ptc, ctp, pts, resolve, show_theory=show_theory)

    included = {pid for pid in seed_ids if pid}
    frontier = set(included)
    queried_raw_ids = set()

    for _ in range(max(depth, 0)):
        next_frontier = set()
        for pid in frontier:
            next_frontier.update(ctp.get(pid, set()))
            next_frontier.update(ptc.get(pid, set()))
            next_frontier.update(pts.get(pid, set()))

        frontier_raw_ids = set()
        for pid in frontier:
            frontier_raw_ids.update(_tree_query_ids_for_person(pid, uuid_to_gedcom))
        frontier_raw_ids -= queried_raw_ids

        if frontier_raw_ids:
            targeted_rels = _main_mod._load_gedcom_relationship_edges_for_ids(frontier_raw_ids)
            _merge_tree_relationships(targeted_rels, ptc, ctp, pts, resolve, show_theory=show_theory)
            queried_raw_ids.update(frontier_raw_ids)
            for pid in frontier:
                next_frontier.update(ctp.get(pid, set()))
                next_frontier.update(ptc.get(pid, set()))
                next_frontier.update(pts.get(pid, set()))

        next_frontier -= included
        if not next_frontier:
            frontier = set()
            break
        included.update(next_frontier)
        frontier = next_frontier

    # Probe one hop beyond the included set so expand controls know if more exists.
    probe_raw_ids = set()
    for pid in included:
        probe_raw_ids.update(_tree_query_ids_for_person(pid, uuid_to_gedcom))
    probe_raw_ids -= queried_raw_ids
    if probe_raw_ids:
        targeted_rels = _main_mod._load_gedcom_relationship_edges_for_ids(probe_raw_ids)
        _merge_tree_relationships(targeted_rels, ptc, ctp, pts, resolve, show_theory=show_theory)

    return ptc, ctp, pts, included, xref_to_uuid


def _build_tree_person_lookup():
    """Build lookup of all people (identities + GEDCOM) for tree rendering."""
    from rhodesli_ml.graph.relationship_graph import parse_gedcom_year

    registry = _main_mod.load_registry()
    lookup = {}
    for ident in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED):
        if not ident.get("merged_into"):
            lookup[ident["identity_id"]] = ident
    gedcom_inds = _main_mod._load_gedcom_individuals()
    gedcom_links = _main_mod._load_gedcom_face_links()
    g2i = {v["gedcom_id"]: k for k, v in gedcom_links.items()}
    # Also include gedcom_matches.json links for comprehensive coverage
    try:
        gm = _main_mod._load_gedcom_matches()
        for m in gm.get("matches", []):
            xref = m.get("gedcom_xref")
            uid = m.get("identity_id")
            if xref and uid and xref not in g2i:
                g2i[xref] = uid
    except Exception:
        pass
    for g in gedcom_inds:
        gid = g.get("gedcom_id")
        if not gid or gid in g2i:
            continue
        lookup[gid] = {
            "name": g.get("name") or "Unknown",
            "metadata": {
                "gender": g.get("gender", "U"),
                "birth_year": parse_gedcom_year(g.get("birth_date")) or "",
                "death_year": parse_gedcom_year(g.get("death_date")) or "",
            },
        }
    return lookup


def _build_tree_person_lookup_for_ids(person_ids, xref_to_uuid=None):
    """Build lookup only for the tree people being rendered."""
    from rhodesli_ml.graph.relationship_graph import parse_gedcom_year

    registry = _main_mod.load_registry()
    lookup = {}
    unresolved_gedcom_ids = []
    xref_to_uuid = xref_to_uuid or {}

    for pid in person_ids:
        try:
            ident = registry.get_identity(pid)
        except KeyError:
            ident = None
        if ident and not ident.get("merged_into"):
            lookup[pid] = ident
        elif isinstance(pid, str) and pid.startswith("@") and pid not in xref_to_uuid:
            unresolved_gedcom_ids.append(pid)

    if unresolved_gedcom_ids:
        for g in _main_mod._load_gedcom_individuals_by_ids(unresolved_gedcom_ids):
            gid = g.get("gedcom_id")
            if not gid:
                continue
            lookup[gid] = {
                "name": g.get("name") or "Unknown",
                "metadata": {
                    "gender": g.get("gender", "U"),
                    "birth_year": parse_gedcom_year(g.get("birth_date")) or "",
                    "death_year": parse_gedcom_year(g.get("death_date")) or "",
                },
            }

    return lookup


def _compute_shared_photos(person_ids, registry):
    """Compute shared photo counts between pairs of people.

    Returns a dict: {person_id: {other_person_id: count}} for each pair
    of people in person_ids that share at least one photo.
    """
    _main_mod._build_caches()
    # Build identity_id -> set of photo_ids
    id_to_photos = {}
    for pid in person_ids:
        photos = set()
        try:
            ident = registry.get_identity(pid)
            if ident:
                fids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
                for fid in fids:
                    photo_id = _main_mod._face_to_photo_cache.get(fid) if _main_mod._face_to_photo_cache else None
                    if photo_id:
                        photos.add(photo_id)
        except (KeyError, TypeError):
            pass
        if photos:
            id_to_photos[pid] = photos

    # Compute pairwise overlap
    result = {}
    pids_with_photos = list(id_to_photos.keys())
    for i, pid_a in enumerate(pids_with_photos):
        for pid_b in pids_with_photos[i + 1 :]:
            shared = len(id_to_photos[pid_a] & id_to_photos[pid_b])
            if shared > 0:
                result.setdefault(pid_a, {})[pid_b] = shared
                result.setdefault(pid_b, {})[pid_a] = shared
    return result


def _make_tree_node(
    pid, lookup, ptc, ctp, pts, included, crop_files, registry, shared_photos_map=None, nav_prefix: str = ""
):
    """Create a single family-chart node with expansion indicators."""
    from rhodesli_ml.graph.relationship_graph import parse_gedcom_year, format_lifespan

    ident = lookup.get(pid, {})
    name = ident.get("name", "Unknown")
    meta = ident.get("metadata", {})
    gender = meta.get("gender", "U")
    parts = name.rsplit(" ", 1) if name != "Unknown" else ["Unknown", ""]
    first = ident.get("first_name") or (parts[0] if parts else "Unknown")
    last = ident.get("last_name") or (parts[1] if len(parts) >= 2 else "")
    br = meta.get("birth_date") or meta.get("birth_year") or meta.get("birth_year_estimate") or ""
    dr = meta.get("death_date") or meta.get("death_year") or ""
    lifespan = format_lifespan(str(br) if br else None, str(dr) if dr else None)
    avatar = ""
    all_faces = []
    try:
        ri = registry.get_identity(pid)
        if ri:
            fids = ri.get("anchor_ids", []) + ri.get("candidate_ids", [])
            for fid in fids:
                url = _main_mod.resolve_face_image_url(fid, crop_files)
                if url:
                    all_faces.append({"url": url, "face_id": fid})
            # Use highest-quality face as avatar (not just first)
            if fids:
                best = _main_mod.get_best_face_id(fids)
                if best:
                    best_url = _main_mod.resolve_face_image_url(best, crop_files)
                    if best_url:
                        avatar = best_url
            if not avatar and all_faces:
                avatar = all_faces[0]["url"]
    except (KeyError, IndexError):
        pass
    # Rels — only to included persons
    rels = {}
    parents = list(ctp.get(pid, set()))
    father, mother = None, None
    for p in parents:
        if p not in included:
            continue
        pg = lookup.get(p, {}).get("metadata", {}).get("gender", "U")
        if pg == "M" and not father:
            father = p
        elif pg == "F" and not mother:
            mother = p
        elif not father:
            father = p
        elif not mother:
            mother = p
    if father:
        rels["father"] = father
    if mother:
        rels["mother"] = mother
    spouses = [s for s in pts.get(pid, set()) if s in included]
    if spouses:
        rels["spouses"] = spouses
    children = [c for c in ptc.get(pid, set()) if c in included]
    if children:
        rels["children"] = children
    # Expansion flags
    all_parents = ctp.get(pid, set())
    all_children = ptc.get(pid, set())
    all_siblings = set()
    for p in all_parents:
        for c in ptc.get(p, set()):
            if c != pid:
                all_siblings.add(c)
    # Shared photos with related people
    sp = shared_photos_map.get(pid, {}) if shared_photos_map else {}
    return {
        "id": pid,
        "data": {
            "first name": first,
            "last name": last,
            "gender": gender,
            "birthday": parse_gedcom_year(str(br)) if br else "",
            "lifespan": lifespan,
            "avatar": avatar,
            "identity_url": f"{nav_prefix}/person/{pid}" if not pid.startswith("@") else "",
            "face_count": len(all_faces),
            "all_faces": all_faces,
            "has_more_parents": bool(all_parents - included),
            "has_more_children": bool(all_children - included),
            "has_more_siblings": bool(all_siblings - included),
            "shared_photos": sp,
        },
        "rels": rels,
    }


def _bfs_immediate_family(person_id, ptc, ctp, pts):
    """Return the immediate family of a person: parents, spouses, children, siblings."""
    family = {person_id}
    # Parents
    parents = ctp.get(person_id, set())
    family.update(parents)
    # Children
    family.update(ptc.get(person_id, set()))
    # Spouses
    family.update(pts.get(person_id, set()))
    # Siblings (share at least one parent)
    for p in parents:
        family.update(ptc.get(p, set()))
    return family


def _is_nuclear_family(person_ids, ptc, ctp, pts):
    """Check if a set of people form a nuclear family (parents + their children).

    Returns True if all people in person_ids are either:
    - A parent-child pair, or
    - All children of the same parent(s), or
    - Parents + children of those parents
    """
    if len(person_ids) < 2:
        return False

    pids = set(person_ids)

    # Find all parents and children within the group
    parents_in_group = set()
    children_in_group = set()
    for pid in pids:
        pid_children = ptc.get(pid, set())
        pid_parents = ctp.get(pid, set())
        if pid_children & pids:
            parents_in_group.add(pid)
        if pid_parents & pids:
            children_in_group.add(pid)

    # Nuclear family: at least one parent-child relationship within the group
    if not parents_in_group and not children_in_group:
        return False

    # Every person is either a parent or a child of someone in the group
    accounted = parents_in_group | children_in_group
    # Spouses of parents are also accounted for
    for p in list(parents_in_group):
        spouses = pts.get(p, set()) & pids
        accounted.update(spouses)

    return accounted == pids


def _bfs_shortest_path(person_a, person_b, ptc, ctp, pts, max_depth=10):
    """BFS shortest path between two people using family relationships.

    Returns list of person IDs in the path (including endpoints), or None.
    """
    if person_a == person_b:
        return [person_a]

    visited = {person_a}
    queue = [(person_a, [person_a])]

    while queue:
        current, path = queue.pop(0)
        if len(path) > max_depth:
            continue

        # All neighbors: parents, children, spouses
        neighbors = set()
        neighbors.update(ctp.get(current, set()))
        neighbors.update(ptc.get(current, set()))
        neighbors.update(pts.get(current, set()))

        for neighbor in neighbors:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            new_path = path + [neighbor]
            if neighbor == person_b:
                return new_path
            queue.append((neighbor, new_path))

    return None


def compute_subtree_for_photo(person_ids, ptc, ctp, pts):
    """Given person IDs from a photo, compute the best subtree to show.

    Returns a set of person IDs to include in the tree view.
    """
    if not person_ids:
        return set()

    pids = [p for p in person_ids if p]
    if not pids:
        return set()

    if len(pids) == 1:
        return _main_mod._bfs_immediate_family(pids[0], ptc, ctp, pts)

    # Nuclear family: parents + children only, show the nuclear unit
    if _main_mod._is_nuclear_family(pids, ptc, ctp, pts):
        subtree = set(pids)
        # Add spouses of people in the group (to complete the family picture)
        for pid in list(pids):
            subtree.update(pts.get(pid, set()))
        # Add parents of children in the group (to show full parentage)
        for pid in list(pids):
            subtree.update(ctp.get(pid, set()))
        # Add children of parents in the group (to show full sibship)
        for pid in list(subtree):
            if ptc.get(pid, set()) & set(pids):
                subtree.update(ptc.get(pid, set()))
        return subtree

    # Find connecting paths via BFS
    path_union = set()
    for i, p1 in enumerate(pids):
        for p2 in pids[i + 1 :]:
            path = _main_mod._bfs_shortest_path(p1, p2, ptc, ctp, pts)
            if path:
                path_union.update(path)

    if path_union:
        # Also add spouses for people along the path
        for pid in list(path_union):
            path_union.update(pts.get(pid, set()))
        # Ensure ALL original photo people are included, even if disconnected
        # (they're in the same photo, so they should appear in the tree)
        for pid in pids:
            if pid not in path_union:
                path_union.add(pid)
                # Also add their immediate family for context
                path_union.update(pts.get(pid, set()))
                for parent in ctp.get(pid, set()):
                    path_union.add(parent)
                for child in ptc.get(pid, set()):
                    path_union.add(child)
        return path_union

    # Fallback: side-by-side immediate families
    combined = set()
    for pid in pids:
        combined.update(_main_mod._bfs_immediate_family(pid, ptc, ctp, pts))
    return combined


@rt("/api/tree/data")
def get(person_id: str = "", depth: int = 1, show_theory: str = "true", people: str = "", request=None):
    """Return tree data for a focal person + N levels of connections.

    When `people` is provided (comma-separated IDs from photo navigation),
    uses smart subtree computation to show the best family context for the
    group of people in the photo.
    """
    people_list = [p.strip() for p in people.split(",") if p.strip()] if people else []
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    # Smart subtree for multiple people (from photo navigation)
    if people_list and len(people_list) > 1:
        ptc, ctp, pts = _build_tree_adjacency(show_theory == "true")
        lookup = _build_tree_person_lookup()
        # Use smart subtree computation
        included = _main_mod.compute_subtree_for_photo(people_list, ptc, ctp, pts)
        focal = person_id or people_list[0]

        if included:
            shared_photos_map = _main_mod._compute_shared_photos(included, registry)
            nodes = [
                _make_tree_node(
                    pid, lookup, ptc, ctp, pts, included, crop_files, registry, shared_photos_map, nav_prefix=nav_prefix
                )
                for pid in included
            ]
            return JSONResponse(
                {
                    "focal_person": focal,
                    "nodes": nodes,
                    "photo_people": people_list,
                }
            )

    if people_list and len(people_list) == 1 and not person_id:
        person_id = people_list[0]

    _, uuid_to_gedcom = _build_tree_link_maps()
    if person_id and _tree_query_ids_for_person(person_id, uuid_to_gedcom):
        ptc, ctp, pts, included, xref_to_uuid = _build_targeted_tree_adjacency(
            [person_id], depth=depth, show_theory=(show_theory == "true")
        )
        lookup = _build_tree_person_lookup_for_ids(included, xref_to_uuid)
        shared_photos_map = _main_mod._compute_shared_photos(included, registry)
        nodes = [
            _make_tree_node(
                pid, lookup, ptc, ctp, pts, included, crop_files, registry, shared_photos_map, nav_prefix=nav_prefix
            )
            for pid in included
        ]
        return JSONResponse({"focal_person": person_id, "nodes": nodes})

    ptc, ctp, pts = _build_tree_adjacency(show_theory == "true")
    lookup = _build_tree_person_lookup()

    # Default to most-connected person
    if not person_id:
        counts = {}
        for pid in set(list(ptc.keys()) + list(ctp.keys()) + list(pts.keys())):
            counts[pid] = len(ptc.get(pid, set())) + len(ctp.get(pid, set())) + len(pts.get(pid, set()))
        # Prefer UUID-based (archive identities) over GEDCOM xrefs
        uuid_counts = {k: v for k, v in counts.items() if not k.startswith("@")}
        person_id = (
            max(uuid_counts, key=uuid_counts.get) if uuid_counts else (max(counts, key=counts.get) if counts else "")
        )

    if not person_id:
        return JSONResponse({"focal_person": "", "nodes": []})

    # BFS with depth limit
    included = set()
    queue = [(person_id, 0)]
    while queue:
        pid, d = queue.pop(0)
        if pid in included or d > depth:
            continue
        included.add(pid)
        if d < depth:
            for p in ctp.get(pid, set()):
                queue.append((p, d + 1))
            for c in ptc.get(pid, set()):
                queue.append((c, d + 1))
            for s in pts.get(pid, set()):
                queue.append((s, d + 1))

    # Build shared_photos map: for each pair of included people,
    # count how many photos they both appear in
    shared_photos_map = _main_mod._compute_shared_photos(included, registry)

    nodes = [
        _make_tree_node(
            pid, lookup, ptc, ctp, pts, included, crop_files, registry, shared_photos_map, nav_prefix=nav_prefix
        )
        for pid in included
    ]
    return JSONResponse({"focal_person": person_id, "nodes": nodes})


@rt("/api/tree/expand")
def get(person_id: str, direction: str = "parents", show_theory: str = "true", request=None):
    """Return additional tree nodes for expansion in a given direction."""
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    _, uuid_to_gedcom = _build_tree_link_maps()
    if _tree_query_ids_for_person(person_id, uuid_to_gedcom):
        ptc, ctp, pts, _, xref_to_uuid = _build_targeted_tree_adjacency(
            [person_id], depth=1, show_theory=(show_theory == "true")
        )
        lookup_builder = lambda ids: _build_tree_person_lookup_for_ids(ids, xref_to_uuid)
    else:
        ptc, ctp, pts = _build_tree_adjacency(show_theory == "true")
        lookup_builder = _build_tree_person_lookup

    new_ids = set()
    if direction == "parents":
        new_ids = ctp.get(person_id, set())
    elif direction == "children":
        new_ids = ptc.get(person_id, set())
    elif direction == "siblings":
        for p in ctp.get(person_id, set()):
            for c in ptc.get(p, set()):
                if c != person_id:
                    new_ids.add(c)

    # Include spouses of new people
    extra = set()
    for nid in new_ids:
        extra.update(pts.get(nid, set()))
    new_ids.update(extra)

    # Include the requesting person so rels connect, and return
    # the requesting person's updated node so the client can merge
    # its rels (e.g., new children appear in parent's rels.children)
    all_ids = new_ids | {person_id}
    lookup = lookup_builder(all_ids) if lookup_builder is not _build_tree_person_lookup else lookup_builder()

    shared_photos_map = _main_mod._compute_shared_photos(all_ids, registry)

    nodes = [
        _make_tree_node(
            pid, lookup, ptc, ctp, pts, all_ids, crop_files, registry, shared_photos_map, nav_prefix=nav_prefix
        )
        for pid in all_ids
    ]
    return JSONResponse({"source_person": person_id, "direction": direction, "nodes": nodes})


@rt("/api/tree/search")
def get(q: str = ""):
    """Search all people (identities + GEDCOM) by name for tree type-ahead."""
    if not q or len(q) < 2:
        return JSONResponse({"results": []})
    lookup = _build_tree_person_lookup()
    q_lower = q.lower()
    results = []
    for pid, info in lookup.items():
        name = info.get("name", "Unknown")
        if q_lower in name.lower():
            results.append(
                {
                    "id": pid,
                    "name": name,
                    "has_photo": not pid.startswith("@"),
                }
            )
    results.sort(key=lambda x: (not x["has_photo"], x["name"].lower()))
    return JSONResponse({"results": results[:20]})


@rt("/connect")
def get(person_a: str = "", person_b: str = "", sess=None, request=None):
    """Six Degrees Connection Finder — find how two people are connected."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()

    # Build person selector options (confirmed identities with real names)
    confirmed = [
        i
        for i in registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
    ]
    confirmed.sort(key=lambda x: (x.get("name") or "").lower())

    # Person selector options
    person_options = [Option("Select a person...", value="", disabled=True, selected=not person_a)]
    for ident in confirmed:
        name = ensure_utf8_display(ident.get("name", ""))
        iid = ident.get("identity_id", "")
        person_options.append(Option(name, value=iid, selected=(iid == person_a)))

    person_b_options = [Option("Select a person...", value="", disabled=True, selected=not person_b)]
    for ident in confirmed:
        name = ensure_utf8_display(ident.get("name", ""))
        iid = ident.get("identity_id", "")
        person_b_options.append(Option(name, value=iid, selected=(iid == person_b)))

    # Build connection results if both people selected
    results_html = ""
    if person_a and person_b:
        from rhodesli_ml.graph.social_graph import find_all_paths, export_for_d3

        social = _load_social_graph()
        paths = find_all_paths(social, person_a, person_b)

        name_a = ensure_utf8_display(_main_mod._safe_get_identity(registry, person_a).get("name", "Unknown"))
        name_b = ensure_utf8_display(_main_mod._safe_get_identity(registry, person_b).get("name", "Unknown"))

        # Compute degrees of separation
        any_path = paths.get("any")
        if any_path is not None:
            degrees = len(any_path)
            degrees_text = f"{degrees} degree{'s' if degrees != 1 else ''} of separation"
        else:
            degrees_text = "No known connection"

        path_sections = []

        # Main path (any edges)
        path_sections.append(
            Div(
                H3(f"{name_a} & {name_b}", cls="text-xl sm:text-lg font-bold text-white mb-1"),
                P(degrees_text, cls="text-sm text-indigo-400 mb-4"),
                _connection_path_html(paths["any"], registry, nav_prefix=nav_prefix),
                cls="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50",
                data_testid="connection-result",
            )
        )

        # Family-only path
        if paths.get("family") is not None and paths["family"] != paths["any"]:
            path_sections.append(
                Div(
                    H4("Family path", cls="text-sm font-semibold text-amber-400 mb-2"),
                    P(
                        f"{len(paths['family'])} step{'s' if len(paths['family']) != 1 else ''} through family",
                        cls="text-sm sm:text-xs text-slate-500 mb-2",
                    ),
                    _connection_path_html(paths["family"], registry, nav_prefix=nav_prefix),
                    cls="bg-slate-800/30 rounded-lg p-4 border border-amber-900/30",
                )
            )

        # Photo-only path
        if paths.get("photo") is not None and paths["photo"] != paths["any"]:
            path_sections.append(
                Div(
                    H4("Photo path", cls="text-sm font-semibold text-blue-400 mb-2"),
                    P(
                        f"{len(paths['photo'])} step{'s' if len(paths['photo']) != 1 else ''} through photos",
                        cls="text-sm sm:text-xs text-slate-500 mb-2",
                    ),
                    _connection_path_html(paths["photo"], registry, nav_prefix=nav_prefix),
                    cls="bg-slate-800/30 rounded-lg p-4 border border-blue-900/30",
                )
            )

        # Add "View in Family Tree" link if family path exists
        if paths.get("family") is not None:
            path_sections.append(
                Div(
                    A(
                        "View in Family Tree →",
                        href=f"{nav_prefix}/tree?person={person_a}",
                        cls="text-sm text-indigo-400 hover:text-indigo-300",
                        data_testid="tree-link",
                    ),
                    cls="text-center mt-2",
                )
            )

        results_html = Div(*path_sections, cls="space-y-6 mt-8", id="connection-results")

    # Build D3 graph data for visualization
    from rhodesli_ml.graph.social_graph import export_for_d3

    social = _load_social_graph()

    # Count photos per person
    _main_mod._build_caches()
    photo_reg = _main_mod.load_photo_registry()
    photo_counts = {}
    for ident in confirmed:
        iid = ident.get("identity_id", "")
        faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        photos = set()
        for fid in faces:
            pid = photo_reg.get_photo_for_face(fid)
            if pid:
                photos.add(pid)
        photo_counts[iid] = len(photos)

    identities_dict = {i["identity_id"]: i for i in confirmed}
    d3_data = export_for_d3(social, identities_dict, photo_counts)
    d3_json = json.dumps(d3_data)

    # Navigation
    nav_links = _main_mod._public_nav_links(active="connect", user=user, community_slug=community_slug)

    share_url = f"/connect?person_a={person_a}&person_b={person_b}" if person_a and person_b else "/connect"

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        #graph-container { width: 100%; height: 500px; border-radius: 0.75rem; overflow: hidden; }
        @media (min-width: 768px) { #graph-container { height: 600px; } }
        .node-label { font-size: 11px; fill: #e2e8f0; pointer-events: none; text-anchor: middle; }
        .link-family { stroke: #d97706; stroke-opacity: 0.6; }
        .link-photo { stroke: #3b82f6; stroke-opacity: 0.4; }
        .node-circle { cursor: pointer; transition: r 0.2s ease; }
        .node-circle:hover { filter: brightness(1.3); }
        .graph-legend { display: flex; gap: 1rem; align-items: center; }
        .legend-item { display: flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; color: #94a3b8; }
        .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
    """)

    return (
        Title("Connect People — Rhodesli"),
        Meta(property="og:title", content="Connect People — Rhodesli"),
        Meta(
            property="og:description",
            content="Find how two people in the Rhodes-Capeluto family are connected through family and photos.",
        ),
        Meta(property="og:url", content=f"{_main_mod.SITE_URL}{share_url}"),
        page_style,
        Div(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between",
                ),
                cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50",
            ),
            Div(
                # Header
                Div(
                    H1("Connect People", cls="text-2xl md:text-3xl font-bold text-white mb-2"),
                    P(
                        "Discover how two people are connected through family ties and shared photographs.",
                        cls="text-slate-400 mb-6",
                    ),
                    cls="mb-6",
                ),
                # Person selectors
                Form(
                    Div(
                        Div(
                            Label("Person A", cls="text-sm sm:text-xs text-slate-400 mb-1 block"),
                            Select(
                                *person_options,
                                name="person_a",
                                cls="w-full px-3 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none",
                            ),
                            cls="flex-1",
                        ),
                        Div(
                            NotStr('<span class="text-2xl text-slate-600">&#x2194;</span>'),
                            cls="flex items-end pb-2",
                        ),
                        Div(
                            Label("Person B", cls="text-sm sm:text-xs text-slate-400 mb-1 block"),
                            Select(
                                *person_b_options,
                                name="person_b",
                                cls="w-full px-3 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none",
                            ),
                            cls="flex-1",
                        ),
                        Button(
                            "Find Connection",
                            cls="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors self-end",
                            type="submit",
                        ),
                        cls="flex flex-col sm:flex-row gap-4 items-end",
                    ),
                    method="get",
                    action="/connect",
                    cls="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50",
                    data_testid="connection-form",
                ),
                # Share button
                Div(
                    Button(
                        NotStr(_main_mod._SHARE_ICON_SVG),
                        " Share",
                        cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1",
                        type="button",
                        data_action="share-photo",
                        data_share_url=share_url,
                    ),
                    cls="flex justify-end mt-4",
                )
                if person_a and person_b
                else "",
                # Connection results
                results_html if results_html else "",
                # Graph visualization
                Div(
                    Div(
                        H3("Community Network", cls="text-xl sm:text-lg font-semibold text-white"),
                        Div(
                            Div(Div(cls="legend-dot", style="background:#d97706"), Span("Family"), cls="legend-item"),
                            Div(Div(cls="legend-dot", style="background:#3b82f6"), Span("Photo"), cls="legend-item"),
                            cls="graph-legend",
                        ),
                        cls="flex items-center justify-between mb-4",
                    ),
                    Div(id="graph-container", cls="bg-slate-800/50 rounded-xl border border-slate-700/50"),
                    cls="mt-8",
                    data_testid="network-graph",
                ),
                cls="max-w-4xl mx-auto px-6 pt-24 pb-16",
            ),
            # D3.js script
            Script(src="https://d3js.org/d3.v7.min.js"),
            Script(f"""
(function() {{
    var data = {d3_json};
    var container = document.getElementById('graph-container');
    if (!container || !data.nodes.length) return;
    var width = container.clientWidth;
    var height = container.clientHeight || 500;

    var svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);

    // Zoom behavior
    var g = svg.append('g');
    svg.call(d3.zoom().scaleExtent([0.3, 4]).on('zoom', function(event) {{
        g.attr('transform', event.transform);
    }}));

    // Force simulation
    var simulation = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(data.links).id(function(d) {{ return d.id; }}).distance(function(d) {{
            return d.category === 'family' ? 80 : 120;
        }}))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Links
    var link = g.append('g')
        .selectAll('line')
        .data(data.links)
        .join('line')
        .attr('class', function(d) {{ return 'link-' + d.category; }})
        .attr('stroke-width', function(d) {{
            if (d.type === 'photographed_with') return Math.min(d.photo_count || 1, 5);
            return 2;
        }});

    // Nodes
    var node = g.append('g')
        .selectAll('g')
        .data(data.nodes)
        .join('g')
        .call(d3.drag()
            .on('start', function(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
            }})
            .on('drag', function(event, d) {{
                d.fx = event.x; d.fy = event.y;
            }})
            .on('end', function(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null; d.fy = null;
            }})
        );

    node.append('circle')
        .attr('r', function(d) {{ return Math.max(8, Math.min(20, 5 + (d.photo_count || 0))); }})
        .attr('fill', function(d) {{
            // Highlight selected people
            if (d.id === '{person_a}') return '#818cf8';
            if (d.id === '{person_b}') return '#818cf8';
            return '#64748b';
        }})
        .attr('stroke', function(d) {{
            if (d.id === '{person_a}' || d.id === '{person_b}') return '#c7d2fe';
            return '#475569';
        }})
        .attr('stroke-width', function(d) {{
            if (d.id === '{person_a}' || d.id === '{person_b}') return 3;
            return 1.5;
        }})
        .attr('class', 'node-circle')
        .on('click', function(event, d) {{
            // Navigate to person on click
            window.location.href = '{nav_prefix}/person/' + d.id;
        }});

    node.append('text')
        .text(function(d) {{ return d.name; }})
        .attr('dy', function(d) {{ return Math.max(8, Math.min(20, 5 + (d.photo_count || 0))) + 14; }})
        .attr('class', 'node-label');

    /* Highlight path if both selected */
    var pathNodes = new Set();
    var pathLinks = new Set();
    var selectedA = '{person_a}';
    var selectedB = '{person_b}';

    simulation.on('tick', function() {{
        link
            .attr('x1', function(d) {{ return d.source.x; }})
            .attr('y1', function(d) {{ return d.source.y; }})
            .attr('x2', function(d) {{ return d.target.x; }})
            .attr('y2', function(d) {{ return d.target.y; }});
        node.attr('transform', function(d) {{ return 'translate(' + d.x + ',' + d.y + ')'; }});
    }});

    // Tooltip
    node.append('title')
        .text(function(d) {{ return d.name + ' (' + (d.photo_count || 0) + ' photos)'; }});
}})();
"""),
            cls="min-h-screen bg-slate-900",
        ),
    )


def public_photo_page(
    photo_id: str,
    selected_face_id: str = None,
    identity_id: str = None,
    sort_by: str = "date_asc",
    seq_mode: bool = False,
    from_queue: bool = False,
    user=None,
    is_admin: bool = False,
    community_slug: str = "rhodes",
) -> tuple:
    """
    Build the public shareable photo page.

    This is the beautiful, museum-like page that gets shared on social media.
    Shows the photo with face overlays, person cards, and a call to action.
    No authentication required.
    """
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        # Gentle 404 page with correct HTTP status
        style_404 = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
        page_html = (
            to_xml(
                Title("Photo Not Found - Rhodesli"),
            )
            + to_xml(style_404)
            + to_xml(
                Main(
                    Nav(
                        Div(
                            A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                            cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                        ),
                        cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800",
                    ),
                    Div(
                        Div(
                            Span("404", cls="text-6xl font-bold text-slate-700 block mb-4"),
                            H1("Photo not found", cls="text-2xl font-serif font-bold text-white mb-3"),
                            P("This photo hasn't been added to the archive yet.", cls="text-slate-400 mb-8"),
                            A(
                                "Explore the Archive",
                                href=f"{nav_prefix}/?section=photos",
                                cls="inline-block px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors",
                            ),
                            cls="text-center",
                        ),
                        cls="flex items-center justify-center min-h-[60vh]",
                    ),
                    cls="min-h-screen bg-slate-900",
                ),
            )
        )
        return HTMLResponse(page_html, status_code=404)

    if seq_mode and is_admin:
        return photo_view_content(
            photo_id,
            selected_face_id=selected_face_id,
            is_partial=False,
            identity_id=identity_id,
            sort_by=sort_by,
            is_admin=is_admin,
            seq_mode=True,
            from_queue=from_queue,
            community_slug=community_slug,
        )

    filename = photo["filename"]
    width, height = _main_mod.get_photo_dimensions(filename)
    has_dimensions = width > 0 and height > 0
    registry = _main_mod.load_registry()
    from urllib.parse import quote as _url_quote

    if sort_by not in {"date_asc", "date_desc", "uploaded_desc", "uploaded_asc"}:
        sort_by = "date_asc"

    # --- Photo carousel: person-context first, else within same collection ---
    collection_name = photo.get("collection", "")
    prev_photo_id = None
    next_photo_id = None
    nav_position = 0
    nav_total = 0
    context_person_name = ""
    date_labels = _main_mod._load_date_labels()

    def _parse_year(value):
        try:
            return int(str(value)[:4])
        except (TypeError, ValueError):
            return None

    def _parse_uploaded_timestamp(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    def _build_sort_meta(photo_id_value, photo_meta):
        photo_meta = photo_meta or {}
        year = _parse_year((date_labels.get(photo_id_value) or {}).get("best_year_estimate"))
        if year is None:
            year = _parse_year(photo_meta.get("date_taken"))
        uploaded_ts = _parse_uploaded_timestamp(photo_meta.get("created_at") or photo_meta.get("updated_at"))
        return {
            "year": year,
            "has_year": year is not None,
            "uploaded_ts": uploaded_ts,
            "has_uploaded_ts": uploaded_ts is not None,
        }

    def _gallery_sort_key(sort_meta, stable):
        year = sort_meta["year"] if sort_meta["has_year"] else 0
        uploaded_ts = sort_meta["uploaded_ts"] if sort_meta["has_uploaded_ts"] else 0.0
        if sort_by == "date_desc":
            return (0 if sort_meta["has_year"] else 1, -year, -uploaded_ts, stable)
        if sort_by == "uploaded_desc":
            return (
                0 if sort_meta["has_uploaded_ts"] else 1,
                -uploaded_ts,
                year if sort_meta["has_year"] else 9999,
                stable,
            )
        if sort_by == "uploaded_asc":
            return (
                0 if sort_meta["has_uploaded_ts"] else 1,
                uploaded_ts,
                year if sort_meta["has_year"] else 9999,
                stable,
            )
        return (0 if sort_meta["has_year"] else 1, year if sort_meta["has_year"] else 9999, uploaded_ts, stable)

    # Normalize the incoming photo_id to canonical space so membership checks
    # below match regardless of which entry link the viewer arrived from
    # (faces gallery → canonical ID, photos gallery → inbox_* ID). Session 165.
    canonical_pid = _main_mod.canonical_photo_id(photo_id)

    if identity_id:
        # Unified with photo_view_content via _ordered_identity_photo_ids — both
        # paths now build the person photo set in the SAME canonical ID space so
        # person-scoped navigation no longer leaks into the whole collection
        # (FB-004, Session 165, Lesson 25 / Lesson 63).
        identity_photo_ids, person_nav_name = _ordered_identity_photo_ids(registry, identity_id, sort_by)
        if person_nav_name:
            context_person_name = person_nav_name
        if canonical_pid in identity_photo_ids:
            idx = identity_photo_ids.index(canonical_pid)
            nav_position = idx + 1
            nav_total = len(identity_photo_ids)
            if idx > 0:
                prev_photo_id = identity_photo_ids[idx - 1]
            if idx < len(identity_photo_ids) - 1:
                next_photo_id = identity_photo_ids[idx + 1]

    # Collection fallback ONLY when there is NO person context. With an
    # identity_id present (even a raw/stale deep link to an off-person photo),
    # navigation must stay person-scoped — never leak into the whole collection
    # (FB-004 / Codex P1, Session 165). Off-person → no arrows (nav_total stays 0).
    if nav_total == 0 and not identity_id and collection_name and _main_mod._photo_cache:
        collection_photos = sorted(
            [pid for pid, pdata in _main_mod._photo_cache.items() if pdata.get("collection", "") == collection_name],
            key=lambda pid: _main_mod._photo_cache[pid].get("filename", ""),
        )
        nav_total = len(collection_photos)
        if canonical_pid in collection_photos:
            idx = collection_photos.index(canonical_pid)
            nav_position = idx + 1
            if idx > 0:
                prev_photo_id = collection_photos[idx - 1]
            if idx < len(collection_photos) - 1:
                next_photo_id = collection_photos[idx + 1]

    # Check for back image (front/back flip feature)
    back_image = photo.get("back_image", "")
    back_transcription = photo.get("back_transcription", "")
    has_back = bool(back_image)

    # Non-destructive transforms (CSS-based, never modifies original)
    front_transform = photo.get("transform", "")
    back_transform_str = photo.get("back_transform", "")
    front_css_transform = _main_mod.parse_transform_to_css(front_transform)
    front_css_filter = _main_mod.parse_transform_to_filter(front_transform)
    back_css_transform = _main_mod.parse_transform_to_css(back_transform_str)
    back_css_filter = _main_mod.parse_transform_to_filter(back_transform_str)

    # Collect face info for overlays and person cards
    def _bbox_iou(a, b) -> float:
        """Return IoU for two [x1, y1, x2, y2] boxes; 0 for invalid boxes."""
        if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) < 4 or len(b) < 4:
            return 0.0
        ax1, ay1, ax2, ay2 = a[:4]
        bx1, by1, bx2, by2 = b[:4]
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter_area
        return (inter_area / union) if union > 0 else 0.0

    face_info_list = []
    identified_names = []
    unidentified_count = 0
    missing_face_artifacts = sum(1 for face in photo.get("faces", []) if face.get("missing_artifacts"))
    missing_face_label = "record" if missing_face_artifacts == 1 else "records"
    missing_face_verb = "is" if missing_face_artifacts == 1 else "are"
    crop_files = _main_mod.get_crop_files()

    for face_data in photo.get("faces", []):
        face_id = face_data["face_id"]
        bbox = face_data.get("bbox", [])
        identity = _main_mod.get_identity_for_face(registry, face_id)
        raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
        display_name = ensure_utf8_display(raw_name)
        face_identity_id = identity["identity_id"] if identity else None
        state = identity.get("state", "INBOX") if identity else None
        is_identified = state == "CONFIRMED" and not display_name.startswith("Unidentified")

        # Get crop URL for person card
        crop_url = _main_mod.resolve_face_image_url(face_id, crop_files) if crop_files else None

        if is_identified:
            identified_names.append(display_name)
        else:
            unidentified_count += 1

        face_info_list.append(
            {
                "source_index": len(face_info_list),
                "face_id": face_id,
                "bbox": bbox,
                "display_name": display_name,
                "raw_name": raw_name,
                "identity_id": face_identity_id,
                "state": state,
                "is_identified": is_identified,
                "is_context_identity": bool(identity_id and face_identity_id == identity_id),
                "crop_url": crop_url,
                "bbox_conflict": False,
                "conflict_names": set(),
            }
        )

    for i, face_info in enumerate(face_info_list):
        for other_face in face_info_list[i + 1 :]:
            if _bbox_iou(face_info["bbox"], other_face["bbox"]) < 0.85:
                continue
            face_info["bbox_conflict"] = True
            other_face["bbox_conflict"] = True
            face_info["conflict_names"].add(other_face["raw_name"])
            other_face["conflict_names"].add(face_info["raw_name"])

    has_bbox_conflicts = any(fi["bbox_conflict"] for fi in face_info_list)
    context_face_info = next((fi for fi in face_info_list if fi["is_context_identity"]), None)
    context_identity_present = context_face_info is not None
    context_identity_conflict = bool(
        context_face_info
        and (context_face_info["bbox_conflict"] or context_face_info["state"] in {"REJECTED", "CONTESTED"})
    )
    context_identity_missing = bool(identity_id and context_person_name and not context_face_info)

    # Public-appropriate context banner copy (Session 165, Phase 3). The
    # "needs review / review before trusting this link" framing is ADMIN
    # language. Anonymous/non-admin viewers get gentle, non-alarming wording and
    # neutral (amber) styling; admins keep the review framing + rose alarm.
    # With the Phase 1 nav fix, public viewers won't reach an off-person photo
    # via the arrows, but a raw deep link still can — so handle it gracefully.
    _is_review_state = context_identity_conflict or context_identity_missing
    banner_alarm = _is_review_state and is_admin
    banner_badge_label = "Needs review" if banner_alarm else "Viewing"
    if context_identity_present and not context_identity_conflict:
        banner_headline = f"Viewing {context_person_name} in this photo."
        banner_subline = "The highlighted face card below matches the person context you came from."
    elif context_identity_conflict:
        if is_admin:
            banner_headline = f"{context_person_name} is tagged on this photo, but the current assignment needs review."
            banner_subline = (
                "The highlighted face overlaps another assignment on this photo. "
                "Treat it as disputed until it is reviewed."
            )
        else:
            banner_headline = f"{context_person_name} may appear in this photo."
            banner_subline = "We're still confirming who's who in this photo."
    else:  # context_identity_missing
        if is_admin:
            banner_headline = f"{context_person_name} is not currently tagged on this photo."
            banner_subline = (
                "You reached this photo from that person's gallery, but no current face assignment "
                "matches them here. Review before trusting this link."
            )
        else:
            banner_headline = f"We haven't tagged {context_person_name} in this photo yet."
            banner_subline = (
                f"You came from {context_person_name}'s photos. Browse the photo below — and if you "
                "recognize someone, help us identify them."
            )

    # First unidentified face from this photo — for contextual "Help Identify" CTA
    first_unidentified_id = next(
        (fi["identity_id"] for fi in face_info_list if not fi["is_identified"] and fi["identity_id"]), None
    )
    dense_faces_layout = len(face_info_list) >= 7

    # --- Build face overlays (simplified for public view — no admin actions) ---
    face_overlays = []
    if has_dimensions:
        for fi in face_info_list:
            bbox = fi["bbox"]
            if not bbox or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = bbox
            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            # Name label positioning: below box if face is near top (avoids clipping),
            # above box if face is lower (more natural reading position)
            name_above = top_pct > 15  # Face is below top 15% — put name above
            name_pos_cls = "-top-6" if name_above else "-bottom-6"

            if fi["bbox_conflict"] and not fi["is_identified"]:
                # Only show "Needs review" for unidentified/unconfirmed faces with bbox conflicts
                overlay_cls = (
                    "face-overlay-box absolute border-2 border-rose-400/80 bg-rose-500/10 "
                    "hover:bg-rose-500/20 transition-all cursor-pointer group"
                )
                name_el = Span(
                    "Needs review",
                    cls=f"face-overlay-label absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/85 text-rose-200 text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[min(220%,calc(100vw-2rem))] truncate",
                )
            elif fi["is_context_identity"]:
                overlay_cls = (
                    "face-overlay-box absolute border-2 border-amber-300 bg-amber-400/10 "
                    "ring-2 ring-amber-200/50 hover:bg-amber-400/15 transition-all cursor-pointer group"
                )
                name_el = Span(
                    fi["display_name"],
                    cls=f"face-overlay-label absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/85 text-amber-200 text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[min(200%,calc(100vw-2rem))] truncate",
                )
            elif fi["is_identified"]:
                overlay_cls = "face-overlay-box absolute border-2 border-emerald-400/70 bg-emerald-400/5 hover:bg-emerald-400/15 transition-all cursor-pointer group"
                name_el = Span(
                    fi["display_name"],
                    cls=f"face-overlay-label absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-emerald-300 text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[min(200%,calc(100vw-2rem))] truncate",
                )
            elif fi["state"] == "SKIPPED":
                overlay_cls = "face-overlay-box absolute border-2 border-dashed border-slate-500/40 bg-slate-500/5 hover:bg-slate-500/10 transition-all cursor-pointer group"
                name_el = Span(
                    "Dismissed",
                    cls=f"face-overlay-label absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-slate-400 text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity",
                )
            else:
                overlay_cls = "face-overlay-box absolute border-2 border-dashed border-amber-400/50 bg-amber-400/5 hover:bg-amber-400/15 transition-all cursor-pointer group"
                name_el = Span(
                    "Unidentified",
                    cls=f"face-overlay-label absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-amber-300/70 text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity",
                )

            # Click navigates to person page (identified) or identify page (unidentified)
            # Admin: unidentified face clicks open Speed Loop at that face
            if fi["bbox_conflict"] and not fi["is_identified"]:
                click_href = None
            elif fi["is_identified"] and fi["identity_id"]:
                click_href = f"{nav_prefix}/person/{fi['identity_id']}"
            elif fi["identity_id"] and is_admin:
                _face_param = f"&face={fi['face_id']}" if fi.get("face_id") else ""
                click_href = f"{nav_prefix}/photo/{photo_id}?seq=1{_face_param}"
            elif fi["identity_id"]:
                click_href = f"{nav_prefix}/identify/{fi['identity_id']}"
            else:
                click_href = None

            _pub_overlay_base = (
                f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;"
            )
            # Face labels: confirmed/identified faces visible for ALL users, others admin-only
            _show_overlay = is_admin or fi["is_identified"] or fi["bbox_conflict"]
            _pub_overlay_style = _pub_overlay_base + (" display: block;" if _show_overlay else " display: none;")
            _id_attr = "true" if fi["is_identified"] else "false"
            _title = (
                "Conflicting face assignments: " + ", ".join(sorted(fi["conflict_names"] | {fi["raw_name"]}))
                if fi["bbox_conflict"]
                else fi["display_name"]
            )
            overlay_inner = (
                A(
                    name_el,
                    href=click_href,
                    cls=overlay_cls,
                    style=_pub_overlay_style,
                    title=_title,
                    id=f"overlay-{fi['identity_id']}" if fi["identity_id"] else None,
                    data_identified=_id_attr,
                )
                if click_href
                else Div(
                    name_el,
                    cls=overlay_cls,
                    style=_pub_overlay_base + ("" if _show_overlay else " display: none;"),
                    title=_title,
                    data_identified=_id_attr,
                )
            )
            overlay = overlay_inner
            face_overlays.append(overlay)

    # --- Build person cards strip / dense grid ---
    def _face_card_border_cls(fi: dict) -> str:
        """Return border CSS classes based on identity state (FB-008)."""
        state = fi.get("state", "")
        if state == "CONFIRMED":
            return "border-2 border-emerald-400"
        elif state == "PROPOSED":
            return "border-2 border-amber-400"
        elif state == "INBOX":
            return "border-2 border-dashed border-slate-400"
        else:
            return "border-2 border-slate-600"

    def _face_card_thumb(fi: dict):
        border_cls = _face_card_border_cls(fi)
        if fi["crop_url"]:
            return Img(
                src=fi["crop_url"],
                alt=fi["display_name"],
                cls=f"w-20 h-20 rounded-full object-cover {border_cls}",
                onerror="this.style.display='none'",
                data_testid="photo-face-thumb",
            )

        if has_dimensions and fi["bbox"] and len(fi["bbox"]) >= 4:
            x1, y1, x2, y2 = fi["bbox"][:4]
            face_w = max(1.0, x2 - x1)
            face_h = max(1.0, y2 - y1)
            crop_span = max(face_w, face_h) * 1.8
            thumb_size = 80.0
            scale = min(2.5, thumb_size / crop_span)
            scaled_w = width * scale
            scaled_h = height * scale
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            offset_x = (thumb_size / 2.0) - (center_x * scale)
            offset_y = (thumb_size / 2.0) - (center_y * scale)
            return Div(
                Img(
                    src=photo_url(filename),
                    alt=fi["display_name"],
                    cls="absolute max-w-none select-none pointer-events-none",
                    style=(
                        f"width:{scaled_w:.2f}px;height:{scaled_h:.2f}px;"
                        f"transform:translate({offset_x:.2f}px,{offset_y:.2f}px);"
                    ),
                    loading="lazy",
                ),
                cls=f"relative w-20 h-20 rounded-full overflow-hidden {border_cls} bg-slate-900",
                data_testid="photo-face-fallback-thumb",
            )

        return Div(
            Span("?", cls="text-2xl text-slate-500"),
            cls="w-20 h-20 rounded-full bg-slate-800 border-2 border-slate-600 flex items-center justify-center",
        )

    display_face_info_list = sorted(
        face_info_list,
        key=lambda fi: (0 if fi["is_context_identity"] else 1, fi["source_index"]),
    )

    person_cards = []
    for fi in display_face_info_list:
        # Card border matches face state (FB-008)
        _state = fi.get("state", "")
        if _state == "CONFIRMED":
            card_border = "border-emerald-500/30"
        elif _state == "PROPOSED":
            card_border = "border-amber-500/30"
        elif _state == "INBOX":
            card_border = "border-dashed border-slate-500/30"
        else:
            card_border = "border-slate-600/50"
        if fi["bbox_conflict"] and not fi["is_identified"]:
            badge = Span("Conflict", cls="text-[10px] text-rose-300 bg-rose-500/10 px-1.5 py-0.5 rounded-full")
        elif fi["is_context_identity"]:
            badge = Span(
                "Current person",
                cls="text-[10px] text-amber-200 bg-amber-500/15 px-1.5 py-0.5 rounded-full border border-amber-400/30",
            )
        elif fi["is_identified"]:
            badge = Span("Identified", cls="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-full")
        elif fi["state"] == "SKIPPED":
            badge = Span("Dismissed", cls="text-[10px] text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded-full")
        elif fi["state"] == "PROPOSED":
            badge = Span("Proposed", cls="text-[10px] text-sky-300 bg-sky-500/10 px-1.5 py-0.5 rounded-full")
        elif fi["state"] in {"REJECTED", "CONTESTED"}:
            badge = Span("Contested", cls="text-[10px] text-rose-300 bg-rose-500/10 px-1.5 py-0.5 rounded-full")
        else:
            badge = Span("Unidentified", cls="text-[10px] text-amber-400/70 bg-amber-500/10 px-1.5 py-0.5 rounded-full")

        crop_el = _face_card_thumb(fi)

        # Card links to person page (identified) or identify page (unidentified)
        if fi["is_identified"] and fi["identity_id"]:
            card_href = f"{nav_prefix}/person/{fi['identity_id']}"
            card_title = f"View {fi['display_name']}'s page"
        elif fi["identity_id"]:
            card_href = f"{nav_prefix}/identify/{fi['identity_id']}"
            card_title = "Do you recognize this person?"
        else:
            card_href = None
            card_title = None

        # Name element: plain text when card is already a link (avoid nested <a> tags
        # which cause browsers to render doubled/overlapping text — Session 143 fix)
        name_el = fi["display_name"]
        see_all_link = None
        if fi["is_identified"] and fi["identity_id"]:
            if not card_href:
                # Only make name a link if the card itself isn't linked
                name_el = A(
                    fi["display_name"],
                    href=f"{nav_prefix}/person/{fi['identity_id']}",
                    cls="text-white hover:text-emerald-300 transition-colors",
                )
            if card_href:
                # Card is already a link — use plain text to avoid nested <a> tags
                see_all_link = Span(
                    "See all photos \u2192",
                    cls="text-[10px] text-indigo-400 mt-1",
                )
            else:
                see_all_link = A(
                    "See all photos \u2192",
                    href=f"{nav_prefix}/person/{fi['identity_id']}",
                    cls="text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 transition-colors",
                )

        # Quick-identify button for admin on unidentified faces
        quick_id_btn = None
        quick_id_area = None
        if is_admin and not fi["is_identified"] and fi["face_id"]:
            # Sanitize face_id for use in CSS selectors / DOM IDs
            # Legacy face IDs contain colons and spaces (e.g. "Image 968_compress:face0")
            # which break CSS selectors like #qid-Image 968_compress:face0
            safe_fid = re.sub(r"[^a-zA-Z0-9_-]", "_", fi["face_id"])
            from urllib.parse import quote as _url_quote

            encoded_fid = _url_quote(fi["face_id"], safe="")
            quick_id_btn = Button(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>'
                ),
                type="button",
                cls="absolute top-1 right-1 p-1 bg-indigo-600/80 hover:bg-indigo-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity z-10",
                hx_get=f"/api/admin/quick-identify-form/{encoded_fid}",
                hx_target=f"#qid-{safe_fid}",
                hx_swap="innerHTML",
                title="Quick identify",
                data_testid="quick-identify-btn",
                aria_label="Quick identify this face",
            )
            quick_id_area = Div(id=f"qid-{safe_fid}", cls="w-full")

        card_inner = Div(
            Div(
                crop_el,
                quick_id_btn,
                cls="relative group" if quick_id_btn else "",
            )
            if quick_id_btn
            else crop_el,
            Div(
                P(name_el, cls="text-sm font-medium text-white mt-2 text-center font-display")
                if isinstance(name_el, str)
                else Div(name_el, cls="text-sm font-medium mt-2 text-center font-display"),
                badge,
                P(
                    "Overlaps another face assignment on this photo.",
                    cls="text-[10px] text-rose-300/80 mt-1 text-center leading-snug",
                )
                if fi["bbox_conflict"] and not fi["is_identified"]
                else None,
                see_all_link,
                cls="flex flex-col items-center",
            ),
            quick_id_area,
            id=f"person-{fi['identity_id']}" if fi["identity_id"] else None,
            data_testid="photo-current-person-card" if fi["is_context_identity"] else None,
            cls=(
                f"photo-face-card photo-card-frame flex flex-col items-center rounded-xl border {card_border} "
                "p-3 hover:bg-amber-900/10 transition-colors min-w-0 w-full"
                + (" ring-2 ring-amber-400/50 bg-amber-950/10" if fi["is_context_identity"] else "")
            ),
        )

        if card_href and not quick_id_btn:
            person_cards.append(
                A(
                    card_inner,
                    href=card_href,
                    cls="no-underline cursor-pointer block h-full w-full",
                    title=card_title,
                )
            )
        else:
            # For admin cards with quick-identify, don't wrap in link (form inside link = invalid HTML)
            person_cards.append(card_inner)

    # --- Collect identified person IDs for tree/map navigation ---
    identified_person_ids = [fi["identity_id"] for fi in face_info_list if fi["is_identified"] and fi["identity_id"]]

    # --- Photo metadata line (with clickable collection link) ---
    meta_elements = []
    if photo.get("collection"):
        collection_name = photo["collection"]
        collection_slug = _main_mod._collection_slug(collection_name)
        meta_elements.append(
            A(
                collection_name,
                href=f"{nav_prefix}/collection/{collection_slug}",
                cls="text-indigo-400 hover:text-indigo-300 transition-colors",
            )
        )
    if photo.get("source") and photo.get("source") != photo.get("collection"):
        if meta_elements:
            meta_elements.append(Span(" · ", cls="text-slate-600"))
        meta_elements.append(Span(photo["source"]))
    meta_line = Span(*meta_elements) if meta_elements else None

    # --- Uploader attribution (admin-only) ---
    uploader_line = _main_mod._build_upload_provenance_line(photo, is_admin=is_admin)

    # --- Open Graph meta tag data ---
    total_faces = len(face_info_list)
    identified_count = len(identified_names)

    # Build OG title and description
    page_title = photo.get("collection") or "Historical Photo"
    og_title = f"{page_title} — Rhodesli Heritage Archive"

    if identified_count > 0:
        names_preview = ", ".join(identified_names[:3])
        if len(identified_names) > 3:
            names_preview += f", and {len(identified_names) - 3} more"
        if unidentified_count > 0:
            og_description = f"{identified_count} {'person' if identified_count == 1 else 'people'} identified: {names_preview}. Help identify the remaining {unidentified_count}."
        else:
            og_description = (
                f"All {identified_count} {'person' if identified_count == 1 else 'people'} identified: {names_preview}."
            )
    elif total_faces > 0:
        og_description = f"{total_faces} {'face' if total_faces == 1 else 'faces'} detected. Can you help identify anyone in this historical photo?"
    else:
        og_description = "A photograph from the Jewish heritage of Rhodes. Explore the archive."

    # Photo URL for og:image (must be publicly accessible)
    og_image_url = photo_url(filename)
    if not og_image_url.startswith("http"):
        og_image_url = f"{_main_mod.SITE_URL}{og_image_url}"
    og_page_url = f"{_main_mod.SITE_URL}{nav_prefix}/photo/{photo_id}"

    og_meta_tags = (
        Meta(property="og:title", content=og_title),
        Meta(property="og:description", content=og_description),
        Meta(property="og:image", content=og_image_url),
        Meta(property="og:url", content=og_page_url),
        Meta(property="og:type", content="article"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content=og_title),
        Meta(name="twitter:description", content=og_description),
        Meta(name="twitter:image", content=og_image_url),
        Meta(name="description", content=og_description),
    )
    if has_dimensions:
        og_meta_tags = og_meta_tags + (
            Meta(property="og:image:width", content=str(width)),
            Meta(property="og:image:height", content=str(height)),
        )

    # Navigation — use _public_page_nav for mobile hamburger support (UX-103)
    nav_links = _main_mod._public_nav_links(active="photos", user=user, community_slug=community_slug)

    # Build compact metadata overlay for the photo hero (UX-103)
    # Shows date estimate, face count, and collection on the photo itself
    date_text_overlay, date_conf_overlay, _ = _main_mod._get_date_badge(photo_id)
    overlay_meta_parts = []
    if date_text_overlay:
        overlay_meta_parts.append(
            Span(date_text_overlay, cls="text-amber-200 font-serif", data_testid="photo-overlay-date")
        )
    if total_faces > 0:
        face_summary = f"{identified_count}/{total_faces} identified"
        overlay_meta_parts.append(Span(face_summary, cls="text-slate-200", data_testid="photo-overlay-faces"))
    if collection_name:
        overlay_meta_parts.append(Span(collection_name, cls="text-slate-300", data_testid="photo-overlay-collection"))
    # Build interleaved list with dot separators
    _interleaved_meta = []
    for i, part in enumerate(overlay_meta_parts):
        _interleaved_meta.append(part)
        if i < len(overlay_meta_parts) - 1:
            _interleaved_meta.append(Span(" \u00b7 ", cls="text-slate-500"))
    photo_metadata_overlay = (
        Div(
            *_interleaved_meta,
            cls="photo-info-overlay absolute top-3 left-3 bg-black/70 rounded-lg px-2 py-1 sm:px-3 sm:py-1.5 text-[10px] sm:text-xs backdrop-blur-sm z-[5] opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity pointer-events-none",
            data_testid="photo-metadata-overlay",
        )
        if overlay_meta_parts
        else None
    )

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .photo-hero-container {
            position: relative;
            display: inline-block;
            max-width: 100%;
            /* Padding for face overlay name labels that extend beyond photo edges */
            padding-top: 1.5rem;
            overflow: visible;
        }
        .photo-hero-container img.photo-hero {
            max-width: 100%;
            height: auto;
            display: block;
            border-radius: 0.5rem;
        }
        .photo-hero-container .face-overlay-public {
            box-sizing: border-box;
        }
        .photo-hero-container .face-overlay-public:hover {
            z-index: 10;
        }
        /* Photo info overlays: semi-transparent by default, fade when hovering photo */
        .photo-info-overlay {
            opacity: 0.75;
        }
        .group:hover .photo-info-overlay {
            opacity: 0.35;
        }
        .photo-info-overlay:hover {
            opacity: 0.9 !important;
        }
        .person-strip, .person-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            padding: 0.5rem 0;
        }
        @media (min-width: 640px) {
            .person-strip, .person-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }
        @media (min-width: 1024px) {
            .person-strip, .person-grid {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }
        }
        /* Mobile: single-column person grid at narrow viewports */
        @media (max-width: 400px) {
            .person-strip, .person-grid {
                grid-template-columns: 1fr;
            }
        }
        /* Mobile: constrain face overlay labels to viewport */
        @media (max-width: 639px) {
            .face-overlay-label {
                max-width: calc(100vw - 2rem) !important;
            }
            .photo-hero-container {
                overflow: hidden;
                padding-top: 0.5rem;
            }
            /* Touch targets: 44px minimum on mobile */
            .photo-page-container a,
            .photo-page-container button {
                min-height: 44px;
            }
            /* Stack action bar vertically on narrow screens */
            .photo-action-bar {
                flex-direction: column;
                align-items: stretch;
            }
            .photo-action-bar > * {
                justify-content: center;
                text-align: center;
            }
        }
        /* CSS 3D Flip Animation — Premium "turning over a real photo" feel */
        .photo-flip-container {
            perspective: 1200px;
            perspective-origin: center center;
        }
        .photo-flip-inner {
            position: relative;
            transition: transform 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                        box-shadow 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            transform-style: preserve-3d;
            /* Resting shadow — subtle, like a photo lying on a surface */
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            border-radius: 2px;
        }
        .photo-flip-inner.is-flipped {
            transform: rotateY(180deg) scale(1.02);
            /* Lifted shadow — photo appears to hover while flipping */
            box-shadow: 0 15px 40px rgba(0,0,0,0.35);
        }
        .photo-flip-front {
            backface-visibility: hidden;
            position: relative;
        }
        .photo-flip-back {
            backface-visibility: hidden;
            transform: rotateY(180deg);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            /* Back of a real photo — warm, slightly textured */
            background-color: #f5f0e8;
            background-image:
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(0,0,0,0.008) 2px,
                    rgba(0,0,0,0.008) 3px
                );
            /* Edge shadow suggesting photo thickness */
            box-shadow: inset 0 0 30px rgba(0,0,0,0.06);
            border-radius: 2px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
        }
        .photo-flip-back img {
            border-radius: 2px;
        }
        .photo-flip-inner:not(.is-flipped) .photo-flip-back {
            pointer-events: none;
        }
        .photo-flip-inner.is-flipped .photo-flip-front {
            pointer-events: none;
        }
        /* Face overlay minimum click target + hover enhancement */
        .face-overlay-box {
            min-width: 44px;
            min-height: 44px;
        }
        .face-overlay-box:hover {
            transform: scale(1.2);
            z-index: 50;
            transition: transform 0.15s ease;
        }
        /* Face overlays fade out during flip */
        .photo-flip-inner .face-overlay-box {
            transition: opacity 0.3s ease, transform 0.15s ease;
        }
        .photo-flip-inner.is-flipped .face-overlay-box {
            opacity: 0;
            pointer-events: none;
        }
        /* Identify Mode — highlights unidentified faces */
        @keyframes identify-pulse {
            0%, 100% { box-shadow: 0 0 8px 2px rgba(251, 191, 36, 0.4); }
            50% { box-shadow: 0 0 16px 4px rgba(251, 191, 36, 0.7); }
        }
        .identify-mode .photo-hero-container::after {
            content: '';
            position: absolute;
            inset: 0;
            background: rgba(0, 0, 0, 0.55);
            border-radius: 0.5rem;
            z-index: 1;
            pointer-events: none;
        }
        .identify-mode .face-overlay-box {
            display: block !important;
            z-index: 2;
        }
        .identify-mode .face-overlay-box[data-identified="true"] {
            border-color: rgba(52, 211, 153, 0.6);
            border-style: solid;
            opacity: 0.7;
        }
        .identify-mode .face-overlay-box[data-identified="false"] {
            border-color: rgba(251, 191, 36, 0.9);
            border-style: solid;
            border-width: 3px;
            animation: identify-pulse 2s ease-in-out infinite;
            z-index: 3;
        }
        .identify-mode .face-overlay-box[data-identified="false"]::after {
            content: '?';
            position: absolute;
            top: -10px;
            right: -10px;
            width: 20px;
            height: 20px;
            background: #f59e0b;
            color: #000;
            font-size: 12px;
            font-weight: bold;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 4;
        }
    """)

    # Keyboard navigation script for carousel
    keyboard_nav_script = None
    touch_nav_script = None
    if prev_photo_id or next_photo_id:
        # Build the query with urlencode (never raw f-string interpolation) and
        # serialize the URLs into the inline JS via json.dumps so untrusted
        # identity_id/sort_by can never break out of the JS string literal
        # (reflected-XSS hardening — Codex P1, Session 165).
        identity_qs = "?" + urlencode({"identity_id": identity_id, "sort_by": sort_by}) if identity_id else ""
        prev_url = f"{nav_prefix}/photo/{quote(str(prev_photo_id))}{identity_qs}" if prev_photo_id else ""
        next_url = f"{nav_prefix}/photo/{quote(str(next_photo_id))}{identity_qs}" if next_photo_id else ""
        prev_url_js = json.dumps(prev_url)
        next_url_js = json.dumps(next_url)
        keyboard_nav_script = Script(f"""
            document.addEventListener('keydown', function(e) {{
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                var prevUrl = {prev_url_js}, nextUrl = {next_url_js};
                if (e.key === 'ArrowLeft' && prevUrl) window.location.href = prevUrl;
                if (e.key === 'ArrowRight' && nextUrl) window.location.href = nextUrl;
            }});
        """)
        touch_nav_script = Script(f"""
            (function() {{
                var hero = document.querySelector('.photo-hero-container');
                if (!hero) return;
                var sx = 0;
                var sy = 0;
                hero.addEventListener('touchstart', function(e) {{
                    if (!e.touches || e.touches.length !== 1) return;
                    sx = e.touches[0].clientX;
                    sy = e.touches[0].clientY;
                }}, {{ passive: true }});
                hero.addEventListener('touchend', function(e) {{
                    if (!e.changedTouches || e.changedTouches.length !== 1) return;
                    var dx = e.changedTouches[0].clientX - sx;
                    var dy = e.changedTouches[0].clientY - sy;
                    if (Math.abs(dx) < 50 || Math.abs(dx) <= Math.abs(dy)) return;
                    var prevUrl = {prev_url_js}, nextUrl = {next_url_js};
                    if (dx > 0 && prevUrl) window.location.href = prevUrl;
                    if (dx < 0 && nextUrl) window.location.href = nextUrl;
                }}, {{ passive: true }});
            }})();
        """)

    return (
        Title(f"{page_title} — Rhodesli Heritage Archive"),
        *og_meta_tags,
        page_style,
        Main(
            # Top navigation bar — uses _public_page_nav for mobile hamburger (UX-103)
            _main_mod._public_page_nav(
                nav_links,
                active="photos",
                user=user,
                community_slug=community_slug,
                include_admin_bar=False,
            ),
            _main_mod._admin_bar(user, community_slug=community_slug),
            # Breadcrumb bar — back navigation (UX-103: eliminates dead-end)
            Div(
                Div(
                    A(
                        NotStr(
                            '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>'
                        ),
                        f"Back to {context_person_name}" if identity_id and context_person_name else "Back to Photos",
                        href=(
                            f"{nav_prefix}/person/{identity_id}?view=photos&sort_by={sort_by}"
                            if identity_id and context_person_name
                            else f"{nav_prefix}/photos"
                        ),
                        cls="text-slate-400 hover:text-white text-sm transition-colors",
                        data_testid="back-to-photos",
                    ),
                    Span(" / ", cls="text-slate-600 mx-2") if collection_name else None,
                    A(
                        collection_name,
                        href=f"{nav_prefix}/collection/{_main_mod._collection_slug(collection_name)}",
                        cls="text-slate-400 hover:text-indigo-300 text-sm transition-colors",
                    )
                    if collection_name
                    else None,
                    cls="max-w-[900px] mx-auto flex items-center",
                ),
                cls="px-4 sm:px-6 pt-4 pb-1",
                data_testid="photo-breadcrumb",
            ),
            Div(
                Div(
                    Span(
                        banner_badge_label,
                        cls=(
                            "text-[11px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full"
                            + (
                                " text-rose-200 bg-rose-500/15 border border-rose-500/30"
                                if banner_alarm
                                else " text-amber-200 bg-amber-500/15 border border-amber-500/30"
                            )
                        ),
                    ),
                    Div(
                        P(
                            banner_headline,
                            cls=(
                                "text-sm leading-relaxed font-medium "
                                + ("text-rose-100" if banner_alarm else "text-amber-100")
                            ),
                        ),
                        P(
                            banner_subline,
                            cls=(
                                "text-sm sm:text-xs leading-relaxed "
                                + ("text-rose-100/80" if banner_alarm else "text-amber-100/80")
                            ),
                        ),
                        cls="flex-1 min-w-0",
                    ),
                    A(
                        "Jump to current face",
                        href=f"#person-{identity_id}",
                        cls=(
                            "text-sm sm:text-xs rounded-lg px-3 py-2 inline-flex items-center justify-center transition-colors "
                            + (
                                "bg-rose-500/15 text-rose-100 hover:bg-rose-500/25 border border-rose-500/25"
                                if banner_alarm
                                else "bg-amber-500/15 text-amber-100 hover:bg-amber-500/25 border border-amber-500/25"
                            )
                        ),
                        data_testid="photo-context-jump-link",
                    )
                    if context_identity_present and identity_id
                    else None,
                    cls=(
                        "max-w-[900px] mx-auto flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl px-4 py-3 "
                        + (
                            "bg-rose-950/40 border border-rose-500/20"
                            if banner_alarm
                            else "bg-amber-950/30 border border-amber-500/20"
                        )
                    ),
                    data_testid="photo-context-banner",
                ),
                cls="px-4 sm:px-6 pt-2",
            )
            if identity_id and context_person_name
            else None,
            # Hero photo section
            Section(
                Div(
                    # Photo with overlays (with optional flip animation)
                    Div(
                        Div(
                            # Front side
                            Div(
                                Img(
                                    src=photo_url(filename),
                                    alt=f"Historical photograph from {photo.get('collection', 'the Rhodes diaspora')}",
                                    cls="photo-hero max-w-full h-auto rounded-lg",
                                    style=f"transform: {front_css_transform}; filter: {front_css_filter};"
                                    if (front_css_transform or front_css_filter)
                                    else None,
                                ),
                                *face_overlays,
                                # Metadata overlay — date, face count, collection (UX-103)
                                photo_metadata_overlay,
                                # Overlay legend
                                Div(
                                    Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-emerald-400 mr-1"),
                                    Span("Identified", cls="text-slate-300 mr-3"),
                                    Span(
                                        cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-dashed border-amber-400 mr-1"
                                    ),
                                    Span("Unidentified", cls="text-slate-300"),
                                    cls="photo-info-overlay absolute top-3 right-3 bg-black/70 rounded-lg px-2 py-1 sm:px-3 sm:py-1.5 flex items-center gap-1 text-[10px] sm:text-xs backdrop-blur-sm face-overlay-legend-public pointer-events-none hidden sm:flex sm:opacity-0 sm:group-hover:opacity-100 transition-opacity",
                                    id="face-overlay-legend-public",
                                    style=""
                                    if (is_admin or any(fi["is_identified"] for fi in face_info_list))
                                    else "display: none;",
                                )
                                if face_overlays
                                else None,
                                # Front label badge (only when back exists)
                                Div(
                                    "Front",
                                    cls="absolute top-3 left-3 bg-black/60 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm z-10",
                                    id="photo-side-label",
                                )
                                if has_back
                                else None,
                                cls="photo-flip-front relative group" if has_back else "relative group",
                            ),
                            # Back side (only rendered if back image exists)
                            Div(
                                Img(
                                    src=photo_url(back_image),
                                    alt="Back of photograph",
                                    cls="max-w-full h-auto rounded-lg",
                                    style=f"transform: {back_css_transform}; filter: {back_css_filter};"
                                    if (back_css_transform or back_css_filter)
                                    else None,
                                ),
                                # Back label badge
                                Div(
                                    "Back",
                                    cls="absolute top-3 left-3 bg-amber-600/80 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm z-10",
                                ),
                                P(
                                    "Back of photograph",
                                    cls="text-amber-700/60 text-sm sm:text-xs text-center mt-2 italic font-serif",
                                ),
                                P(
                                    back_transcription,
                                    cls="text-amber-900/80 text-sm mt-3 bg-amber-50/50 rounded-lg p-3 border border-amber-200/30 italic font-serif leading-relaxed",
                                )
                                if back_transcription
                                else None,
                                cls="photo-flip-back",
                            )
                            if has_back
                            else None,
                            id="photo-flip-inner",
                            cls="photo-flip-inner" if has_back else "",
                        ),
                        cls="photo-flip-container photo-hero-container relative mx-auto"
                        if has_back
                        else "photo-hero-container relative mx-auto",
                    ),
                    # Photo carousel navigation
                    Div(
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>'
                            ),
                            href=(
                                f"{nav_prefix}/photo/{prev_photo_id}?identity_id={identity_id}&sort_by={sort_by}"
                                if identity_id
                                else f"{nav_prefix}/photo/{prev_photo_id}"
                            ),
                            cls="p-2 bg-black/60 hover:bg-black/80 text-white rounded-full backdrop-blur-sm transition-colors",
                            title="Previous photo",
                        )
                        if prev_photo_id
                        else Span(cls="w-9"),
                        Span(
                            f"Photo {nav_position} of {nav_total}",
                            cls="text-sm sm:text-xs text-slate-400",
                        )
                        if nav_total > 1
                        else None,
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>'
                            ),
                            href=(
                                f"{nav_prefix}/photo/{next_photo_id}?identity_id={identity_id}&sort_by={sort_by}"
                                if identity_id
                                else f"{nav_prefix}/photo/{next_photo_id}"
                            ),
                            cls="p-2 bg-black/60 hover:bg-black/80 text-white rounded-full backdrop-blur-sm transition-colors",
                            title="Next photo",
                        )
                        if next_photo_id
                        else Span(cls="w-9"),
                        cls="flex items-center justify-center gap-4 mt-3",
                    )
                    if nav_total > 1
                    else None,
                    # Action bar: Share, Download, Flip (if back image)
                    Div(
                        Button(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
                            ),
                            "Share This Photo",
                            cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors",
                            type="button",
                            data_action="share-photo",
                            id="share-photo-btn",
                            data_share_title=og_title,
                            data_share_text=og_description,
                            data_share_url=og_page_url,
                        ),
                        Button(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
                            ),
                            Span(
                                "Show Faces" if not is_admin else "Hide Faces",
                                id="face-overlay-toggle-text",
                            ),
                            cls="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded-lg transition-colors inline-flex items-center",
                            type="button",
                            data_action="toggle-face-overlays-public",
                            id="face-overlay-toggle-public",
                            data_overlays_hidden="false" if is_admin else "true",
                        )
                        if face_overlays
                        else None,
                        # Admin: Identify Mode links to Speed Loop; non-admin: toggle behavior
                        (
                            A(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
                                ),
                                Span("Identify Mode"),
                                cls="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
                                href=f"{nav_prefix}/photo/{photo_id}?seq=1",
                                id="identify-mode-toggle",
                                data_testid="identify-mode-toggle",
                            )
                            if is_admin
                            else Button(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
                                ),
                                Span("Identify Mode", id="identify-mode-text"),
                                cls="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg transition-colors",
                                type="button",
                                data_action="toggle-identify-mode",
                                id="identify-mode-toggle",
                                data_testid="identify-mode-toggle",
                            )
                        )
                        if face_overlays and (unidentified_count > 0 or is_admin)
                        else None,
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>'
                            ),
                            f"Back to {context_person_name}"
                            if identity_id and context_person_name
                            else "Back to Workstation",
                            href=(
                                f"{nav_prefix}/person/{identity_id}?view=photos&sort_by={sort_by}"
                                if identity_id and context_person_name
                                else f"{nav_prefix}/?section=photos"
                            ),
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                            data_testid="back-to-workstation",
                        )
                        if is_admin
                        else None,
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>'
                            ),
                            "Download",
                            href=f"{nav_prefix}/photo/{photo_id}/download",
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                            download=True,
                        ),
                        # Flip button (only when back image exists)
                        Button(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'
                            ),
                            Span("Turn Over", id="flip-btn-text"),
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors",
                            type="button",
                            data_action="flip-photo",
                            id="flip-photo-btn",
                        )
                        if has_back
                        else None,
                        # Family Tree button (only when identified people exist)
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>'
                            ),
                            "Family Tree",
                            href=f"{nav_prefix}/tree?photo_id={photo_id}&people={','.join(identified_person_ids)}",
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                            data_testid="photo-tree-btn",
                        )
                        if identified_person_ids
                        else None,
                        # Map button (only when identified people exist)
                        A(
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>'
                            ),
                            "See on Map",
                            href=f"{nav_prefix}/map?people={','.join(identified_person_ids)}",
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                            data_testid="photo-map-btn",
                        )
                        if identified_person_ids
                        else None,
                        # Admin: Name These Faces button (2+ unidentified faces required)
                        A(
                            f"Start Speed Loop ({unidentified_count} unidentified)",
                            href=(
                                f"{nav_prefix}/photo/{photo_id}?seq=1"
                                + (f"&identity_id={identity_id}&sort_by={sort_by}" if identity_id else "")
                            ),
                            cls="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
                            data_testid="name-these-faces-public",
                        )
                        if is_admin and unidentified_count >= 2
                        else None,
                        cls="photo-action-bar flex flex-wrap items-center justify-center gap-3 mt-4",
                    ),
                    Span(
                        "This photograph has writing on the back"
                        if back_transcription
                        else "Turn over to see the back of this photograph",
                        cls="text-slate-500 text-sm sm:text-xs text-center block mt-2",
                    )
                    if has_back
                    else None,
                    # (Name These Faces now targets #photo-modal-content directly)
                    # Admin: Upload back image (only shown to admin when no back image)
                    Div(
                        Div(
                            P("Admin: Add a back image", cls="text-slate-400 text-sm sm:text-xs font-medium mb-2"),
                            Form(
                                Input(
                                    type="file",
                                    name="file",
                                    accept=".jpg,.jpeg,.png,.webp",
                                    cls="text-sm sm:text-xs text-slate-300 file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-sm file:bg-slate-600 file:text-white hover:file:bg-slate-500",
                                ),
                                Div(
                                    Input(
                                        type="text",
                                        name="back_transcription",
                                        placeholder="Transcribe writing on back (optional)...",
                                        cls="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 min-h-[44px]",
                                    ),
                                    Button(
                                        "Upload",
                                        type="submit",
                                        cls="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg min-h-[44px]",
                                    ),
                                    cls="flex gap-2 mt-2",
                                ),
                                hx_post=f"/api/photo/{photo_id}/back-image",
                                hx_target="#back-upload-result",
                                hx_swap="innerHTML",
                                hx_encoding="multipart/form-data",
                            ),
                            Div(id="back-upload-result", cls="mt-2"),
                        ),
                        cls="mt-4 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
                    )
                    if is_admin and not has_back
                    else None,
                    # Admin: Update transcription (when back exists but no transcription)
                    Div(
                        Form(
                            Input(
                                type="text",
                                name="back_transcription",
                                placeholder="Transcribe writing on back...",
                                value=back_transcription or "",
                                cls="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 min-h-[44px]",
                            ),
                            Button(
                                "Save",
                                type="submit",
                                cls="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg min-h-[44px]",
                            ),
                            hx_post=f"/api/photo/{photo_id}/back-transcription",
                            hx_target="#transcription-result",
                            hx_swap="innerHTML",
                            cls="flex flex-col sm:flex-row gap-3 sm:gap-2 w-full sm:w-auto",
                        ),
                        Div(id="transcription-result", cls="mt-1"),
                        cls="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
                    )
                    if is_admin and has_back
                    else None,
                    # Admin: Image orientation toolbar
                    Div(
                        _main_mod.image_transform_toolbar(photo_id, target="front"),
                        _main_mod.image_transform_toolbar(photo_id, target="back") if has_back else None,
                        Div(id="transform-result", cls="mt-1"),
                        P(f"Current: {front_transform}", cls="text-sm sm:text-xs text-slate-500 mt-1")
                        if front_transform
                        else None,
                        cls="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
                    )
                    if is_admin
                    else None,
                    # Photo metadata (with inline admin editing)
                    Div(
                        # Filename always visible for admin (user feedback: "can't find filename")
                        P(
                            Span("File: ", cls="text-slate-500"),
                            Span(Path(filename).name, cls="text-slate-300 font-mono text-sm sm:text-xs"),
                            cls="text-sm sm:text-xs mb-1",
                        )
                        if is_admin
                        else None,
                        P(uploader_line, cls="mt-1") if uploader_line else None,
                        P(meta_line, cls="text-slate-400 text-sm") if meta_line else None,
                        P(
                            f"{total_faces} {'person' if total_faces == 1 else 'people'} detected · "
                            f"{identified_count} identified",
                            cls="text-slate-500 text-sm sm:text-xs mt-1",
                        ),
                        P(
                            f"{missing_face_artifacts} archived face {missing_face_label} "
                            f"{missing_face_verb} preserved below without overlay coordinates.",
                            cls="text-amber-300/80 text-sm sm:text-xs mt-1",
                        )
                        if missing_face_artifacts
                        else None,
                        P(
                            A(
                                photo.get("source_url", ""),
                                href=photo.get("source_url", ""),
                                target="_blank",
                                rel="noopener",
                                cls="text-indigo-400/70 hover:text-indigo-300 text-sm sm:text-xs underline",
                            ),
                            cls="mt-1",
                        )
                        if photo.get("source_url")
                        else None,
                        # Admin inline edit for collection/source
                        Div(
                            Form(
                                Label("Collection:", cls="text-sm sm:text-xs text-slate-500 mr-1"),
                                Input(
                                    type="text",
                                    name="collection",
                                    value=photo.get("collection", ""),
                                    placeholder="Select or type a collection",
                                    cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-sm sm:text-xs text-white w-48 placeholder-slate-500",
                                    list="photo-collections",
                                ),
                                Button(
                                    "Save",
                                    type="submit",
                                    cls="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm sm:text-xs rounded ml-1",
                                ),
                                Div(id=f"collection-status-{photo_id}", cls="inline ml-1"),
                                hx_post=f"/api/photo/{photo_id}/collection",
                                hx_target=f"#collection-status-{photo_id}",
                                hx_swap="innerHTML",
                                cls="flex items-center gap-1 mb-1",
                            ),
                            Form(
                                Label("Source:", cls="text-sm sm:text-xs text-slate-500 mr-1"),
                                Input(
                                    type="text",
                                    name="source",
                                    value=photo.get("source", ""),
                                    cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-sm sm:text-xs text-white w-48",
                                ),
                                Button(
                                    "Save",
                                    type="submit",
                                    cls="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm sm:text-xs rounded ml-1",
                                ),
                                Div(id=f"source-status-{photo_id}", cls="inline ml-1"),
                                hx_post=f"/api/photo/{photo_id}/source",
                                hx_target=f"#source-status-{photo_id}",
                                hx_swap="innerHTML",
                                cls="flex items-center gap-1 mb-1",
                            ),
                            Form(
                                Label("Source URL:", cls="text-sm sm:text-xs text-slate-500 mr-1"),
                                Input(
                                    type="text",
                                    name="source_url",
                                    value=photo.get("source_url", ""),
                                    cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-sm sm:text-xs text-white w-56",
                                ),
                                Button(
                                    "Save",
                                    type="submit",
                                    cls="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm sm:text-xs rounded ml-1",
                                ),
                                Div(id=f"source-url-status-{photo_id}", cls="inline ml-1"),
                                hx_post=f"/api/photo/{photo_id}/source-url",
                                hx_target=f"#source-url-status-{photo_id}",
                                hx_swap="innerHTML",
                                cls="flex items-center gap-1",
                            ),
                            _main_mod._photo_collection_datalist(),
                            cls="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
                            data_testid="photo-inline-edit",
                        )
                        if is_admin
                        else None,
                        cls="mt-4 text-center",
                    ),
                    cls="max-w-[900px] mx-auto",
                    id="photo-modal-content",
                ),
                cls="px-4 sm:px-6 pt-8 pb-6",
            ),
            # People in this photo
            Section(
                Div(
                    Div(
                        H2(
                            f"{'People' if total_faces != 1 else 'Person'} in this photo",
                            cls="text-xl sm:text-lg font-serif font-semibold text-white",
                        ),
                        Span(
                            "Potential tag conflicts detected",
                            cls="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/20 px-2 py-1 rounded-full",
                            data_testid="photo-face-conflict-banner",
                        )
                        if has_bbox_conflicts
                        else None,
                        A(
                            "Compare faces",
                            href=f"{nav_prefix}/compare?photo_id={photo_id}",
                            cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 transition-colors",
                            data_testid="compare-photo-link",
                        ),
                        cls="flex items-center justify-between gap-3 flex-wrap mb-4",
                    ),
                    Div(
                        *person_cards,
                        cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 py-2",
                        data_testid="photo-people-grid",
                    )
                    if person_cards
                    else P("No faces detected in this photo.", cls="text-slate-500 text-sm"),
                    cls="max-w-[900px] mx-auto",
                ),
                cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
            )
            if face_info_list
            else None,
            # Prominent date estimate badge (PRD-022: Photo Detective UX)
            _main_mod._build_photo_date_badge(photo_id),
            # AI Analysis panel (from date labels + search index)
            _main_mod._build_ai_analysis_section(photo_id, is_admin),
            # Face alignment descriptions (PRD-015 coordinate bridging)
            _main_mod._build_face_alignment_section(photo_id, is_admin),
            # Life events linked to this photo (PRD-011)
            _main_mod.event_routes.photo_events_section(photo_id, is_admin, nav_prefix=nav_prefix)
            if is_admin
            else None,
            # Call to action — link to first unidentified face from this photo
            # More prominent when ALL faces are unidentified (UX-105)
            Section(
                Div(
                    Div(
                        Span(
                            f"{unidentified_count} {'person' if unidentified_count == 1 else 'people'} awaiting identification",
                            cls="text-sm sm:text-xs font-semibold uppercase tracking-wider text-amber-400 mb-2 block",
                        ),
                        cls="",
                    )
                    if identified_count == 0 and total_faces > 0
                    else None,
                    H2(
                        "Nobody in this photo has been identified yet — can you help?"
                        if identified_count == 0 and total_faces > 0
                        else "Do you recognize someone?",
                        cls="text-xl font-serif font-bold text-white mb-3",
                    ),
                    P(
                        "Help us identify the people in this photograph. Your family knowledge could be the key to preserving our shared history.",
                        cls="text-slate-400 leading-relaxed mb-6 max-w-lg mx-auto",
                    ),
                    Div(
                        A(
                            "Do you recognize anyone?",
                            href=(
                                f"{nav_prefix}/identify/{first_unidentified_id}"
                                if first_unidentified_id
                                else f"{nav_prefix}/help"
                            ),
                            cls=(
                                "inline-block px-8 py-4 bg-amber-600 text-white font-semibold text-xl sm:text-lg rounded-lg hover:bg-amber-500 transition-colors"
                                if identified_count == 0 and total_faces > 0
                                else "inline-block px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors"
                            ),
                            data_testid="help-identify-cta",
                        ),
                        A(
                            "Compare Faces",
                            href=f"{nav_prefix}/compare?photo_id={photo_id}",
                            cls="inline-block px-6 py-3 border border-indigo-600 text-indigo-300 font-medium rounded-lg hover:border-indigo-400 hover:text-white transition-colors",
                            data_testid="compare-photo-link",
                        ),
                        A(
                            "Browse All Photos",
                            href=f"{nav_prefix}/photos",
                            cls="inline-block px-6 py-3 border border-slate-600 text-slate-300 font-medium rounded-lg hover:border-slate-400 hover:text-white transition-colors",
                        ),
                        cls="flex flex-wrap justify-center gap-4",
                    ),
                    cls="text-center max-w-2xl mx-auto",
                ),
                cls=(
                    "px-4 sm:px-6 py-12 border-t border-amber-800/30 bg-amber-950/10"
                    if identified_count == 0 and total_faces > 0
                    else "px-4 sm:px-6 py-12 border-t border-slate-800/50"
                ),
                data_testid="help-identify-section",
            )
            if unidentified_count > 0
            else None,
            # Footer
            Footer(
                Div(
                    P(
                        Span("Rhodesli", cls="font-bold text-white"),
                        " — Preserving the visual heritage of the Jews of Rhodes",
                        cls="text-slate-500 text-sm",
                    ),
                    Div(
                        A("Home", href=f"{nav_prefix}/", cls="text-sm sm:text-xs text-slate-500 hover:text-slate-300"),
                        Span("·", cls="text-slate-700"),
                        A(
                            "Photos",
                            href=f"{nav_prefix}/photos",
                            cls="text-sm sm:text-xs text-slate-500 hover:text-slate-300",
                        ),
                        Span("·", cls="text-slate-700"),
                        A(
                            "People",
                            href=f"{nav_prefix}/people",
                            cls="text-sm sm:text-xs text-slate-500 hover:text-slate-300",
                        ),
                        cls="flex items-center gap-2",
                    ),
                    cls="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            # Action button event handlers (standalone page — uses reusable _share_script + flip JS)
            _main_mod._share_script(),
            Script("""
                document.addEventListener('click', function(e) {
                    var flipBtn = e.target.closest('[data-action="flip-photo"]');
                    if (flipBtn) {
                        var inner = document.getElementById('photo-flip-inner');
                        if (!inner) return;
                        inner.classList.toggle('is-flipped');
                        var textEl = document.getElementById('flip-btn-text');
                        if (textEl) {
                            textEl.textContent = inner.classList.contains('is-flipped') ? 'View Front' : 'Turn Over';
                        }
                        return;
                    }
                    var toggleBtn = e.target.closest('[data-action="toggle-face-overlays-public"]');
                    if (toggleBtn) {
                        var overlays = document.querySelectorAll('.face-overlay-box');
                        var legend = document.getElementById('face-overlay-legend-public');
                        var isHidden = toggleBtn.getAttribute('data-overlays-hidden') === 'true';
                        overlays.forEach(function(el) {
                            el.style.display = isHidden ? 'block' : 'none';
                        });
                        if (legend) legend.style.display = isHidden ? '' : 'none';
                        toggleBtn.setAttribute('data-overlays-hidden', isHidden ? 'false' : 'true');
                        var toggleText = document.getElementById('face-overlay-toggle-text');
                        if (toggleText) toggleText.textContent = isHidden ? 'Hide Faces' : 'Show Faces';
                        return;
                    }
                    var idModeBtn = e.target.closest('[data-action="toggle-identify-mode"]');
                    if (idModeBtn) {
                        var container = document.querySelector('.photo-page-container');
                        if (!container) return;
                        var isActive = container.classList.toggle('identify-mode');
                        var textEl = document.getElementById('identify-mode-text');
                        if (textEl) textEl.textContent = isActive ? 'Exit Identify Mode' : 'Identify Mode';
                        idModeBtn.style.background = isActive ? '#b45309' : '';
                        return;
                    }
                });
            """),
            cls="min-h-screen bg-slate-900 photo-page-container",
        ),
        keyboard_nav_script,
        touch_nav_script,
    )


@rt("/photo/{photo_id}")
def get(
    photo_id: str,
    face: str = None,
    identity_id: str = None,
    sort_by: str = "date_asc",
    seq: bool = False,
    from_queue: bool = False,
    sess=None,
    request=None,
):
    """
    Public shareable photo page with face overlays and person cards.

    This is the page people share on Facebook, WhatsApp, email, etc.
    No authentication required — anyone can view.

    Query params:
    - face: Optional face_id to highlight
    - identity_id: Optional person context for prev/next photo navigation
    - sort_by: Optional person-gallery sort mode for prev/next navigation
    - seq: If True for admins, enter the standalone speed-loop flow
    - from_queue: If True, show "Back to Review Queue" link in Speed Loop
    """
    _main_mod.touch_user_activity()  # SWR bot guard (egress reduction)
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    return _main_mod.public_photo_page(
        photo_id,
        selected_face_id=face,
        identity_id=identity_id,
        sort_by=sort_by,
        seq_mode=seq and user_is_admin,
        from_queue=from_queue and user_is_admin,
        user=user,
        is_admin=user_is_admin,
        community_slug=community_slug,
    )


@rt("/photo/{photo_id}/partial")
def get(
    photo_id: str,
    face: str = None,
    prev_id: str = None,
    next_id: str = None,
    nav_idx: int = -1,
    nav_total: int = 0,
    identity_id: str = None,
    sort_by: str = "date_asc",
    from_compare: bool = False,
    seq: bool = False,
    sess=None,
    request=None,
):
    """
    Render photo view partial for HTMX modal injection.

    Optional navigation context:
    - prev_id/next_id: Adjacent photo IDs for prev/next buttons
    - nav_idx/nav_total: Current position for "X of Y" display
    - identity_id: Identity context for computing prev/next from identity's photos
    - from_compare: If True, show "Back to Compare" button (opened via compare modal)
    - seq: If True, activate "Name These Faces" sequential mode
    """
    user_is_admin = (
        (_main_mod.get_current_user(sess or {}).is_admin if _main_mod.get_current_user(sess or {}) else False)
        if _main_mod.is_auth_enabled()
        else True
    )
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    return _main_mod.photo_view_content(
        photo_id,
        selected_face_id=face,
        is_partial=True,
        prev_id=prev_id,
        next_id=next_id,
        nav_idx=nav_idx,
        nav_total=nav_total,
        identity_id=identity_id,
        sort_by=sort_by,
        is_admin=user_is_admin,
        from_compare=from_compare,
        seq_mode=seq and user_is_admin,
        community_slug=community_slug,
    )


@rt("/photo/{photo_id}/download")
def get(photo_id: str):
    """
    Download the original full-resolution photo.

    Public endpoint — no auth required.
    Returns the photo file with Content-Disposition: attachment header.
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return Response("Photo not found", status_code=404)

    filename = photo["filename"]
    basename = Path(filename).name

    # In R2 mode, redirect to the R2 URL (can't serve local file)
    if _main_mod.storage.is_r2_mode():
        download_url = photo_url(filename)
        return Response(status_code=302, headers={"Location": download_url})

    # Local mode: serve from filesystem
    photo_path = _main_mod.photos_path / basename
    if not photo_path.exists():
        return Response("Photo file not found", status_code=404)

    return FileResponse(
        str(photo_path),
        filename=basename,
        headers={"Content-Disposition": f'attachment; filename="{basename}"'},
    )


@rt("/api/onboarding/discover")
def get(surnames: str = "", request=None):
    """Return HTML fragment showing confirmed identities matching selected surnames.

    Public endpoint — no auth required. Used by the onboarding modal.
    """
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    if not surnames.strip():
        return Div(P("No surnames selected.", cls="text-sm text-slate-400"))

    surname_list = [s.strip() for s in surnames.split(",") if s.strip()]

    # Load surname variants for matching
    from core.registry import _load_surname_variants

    variant_lookup = _load_surname_variants()

    # Expand each surname to its variant group
    target_names = set()
    for surname in surname_list:
        target_names.add(surname.lower())
        variants = variant_lookup.get(surname.lower(), [])
        target_names.update(variants)

    # Find confirmed identities whose last name matches
    registry = _main_mod.load_registry()
    confirmed = registry.list_identities(state=_main_mod.IdentityState.CONFIRMED)
    crop_files = _main_mod.get_crop_files()

    matches = []
    for identity in confirmed:
        name = (identity.get("name") or "").strip()
        if not name or name.startswith("Unidentified"):
            continue
        # Check last name or any word in name
        name_words = [w.lower() for w in name.split()]
        if any(w in target_names for w in name_words):
            face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            crop_url = _main_mod.resolve_face_image_url(face_ids[0], crop_files) if face_ids else None
            if crop_url:
                matches.append(
                    {
                        "name": name,
                        "crop_url": crop_url,
                        "identity_id": identity["identity_id"],
                        "photo_count": len(face_ids),
                    }
                )

    if not matches:
        return Div(
            H3("No matches yet", cls="text-xl sm:text-lg font-bold text-white mb-2"),
            P(
                "We don't have confirmed identities with those surnames yet, "
                "but you can still help identify unknown faces!",
                cls="text-sm text-slate-400 mb-4",
            ),
            Button(
                "Continue",
                type="button",
                data_action="onboarding-continue",
                cls="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-500 w-full",
            ),
        )

    # Show up to 6 matching people
    people_cards = []
    for m in matches[:6]:
        people_cards.append(
            A(
                Div(
                    Img(
                        src=m["crop_url"],
                        alt=m["name"],
                        cls="w-16 h-16 rounded-full object-cover border-2 border-amber-400/50",
                    ),
                    Div(
                        Span(m["name"], cls="text-sm font-medium text-white"),
                        Span(
                            f"{m['photo_count']} photo{'s' if m['photo_count'] != 1 else ''}",
                            cls="text-sm sm:text-xs text-slate-400",
                        ),
                        cls="flex flex-col",
                    ),
                    cls="flex items-center gap-3",
                ),
                href=f"{nav_prefix}/?section=confirmed&current={m['identity_id']}",
                cls="block p-2 rounded-lg hover:bg-slate-700/50 transition-colors",
                data_action="onboarding-close",
            )
        )

    return Div(
        H3(
            f"We found {len(matches)} {'person' if len(matches) == 1 else 'people'} with those family names!",
            cls="text-xl sm:text-lg font-bold text-white mb-3",
        ),
        Div(*people_cards, cls="space-y-1 mb-4 max-h-64 overflow-y-auto"),
        P(f"{len(matches)} identified so far — can you help find more?", cls="text-sm sm:text-xs text-slate-500 mb-3")
        if len(matches) > 6
        else None,
        Button(
            "Continue",
            type="button",
            data_action="onboarding-continue",
            cls="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-500 w-full",
        ),
    )
