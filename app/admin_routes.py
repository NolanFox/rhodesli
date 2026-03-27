"""
Admin routes extracted from app/main.py.

All /admin/*, /api/admin/*, /api/ml-review/* routes and admin-exclusive helpers.
"""

import io
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fasthtml.common import *
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.auth import get_current_user, _check_origin
from core import storage
from core.registry import IdentityState
from core.ui_safety import ensure_utf8_display
from core.config import (
    MATCH_THRESHOLD_HIGH,
    MATCH_THRESHOLD_MEDIUM,
    MATCH_THRESHOLD_MODERATE,
    MATCH_THRESHOLD_VERY_HIGH,
    PROCESSING_ENABLED,
)

# Import route decorators (bound once, never reassigned)
from app.main import rt, app

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)

# Module-level state for GEDCOM upload preview
_gedcom_upload_preview = None


def _run_ml_client_async(coro_fn):
    """Run an async ML client method in a sync context.

    asyncio.run() destroys the event loop after completion, which invalidates
    any httpx.AsyncClient bound to it. We create a fresh client each time
    to avoid "Event loop is closed" errors on subsequent calls.
    """
    import asyncio
    from core.ml_client import MLServiceClient
    import os

    client = MLServiceClient(
        base_url=os.getenv("ML_SERVICE_URL", ""),
        token=os.getenv("ML_SERVICE_TOKEN", "dev-token"),
    )
    try:
        return asyncio.run(coro_fn(client))
    finally:
        # Client is bound to the now-closed event loop, discard it
        pass


@rt("/api/admin/ml-health")
def get(sess=None):
    """Admin-only ML service health check. Returns ML service status."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    from core.ml_client import MLServiceClient
    import os

    base_url = os.getenv("ML_SERVICE_URL", "")
    if not base_url:
        return Response(
            json.dumps({"status": "not_configured", "ml_service_url": ""}),
            media_type="application/json",
        )
    try:
        result = _run_ml_client_async(lambda c: c.health())
        return Response(
            json.dumps({"status": "connected", "ml_service": result}),
            media_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"status": "unreachable", "error": str(e)}),
            media_type="application/json",
        )


@rt("/api/admin/ml-warm")
def post(sess=None):
    """Admin-only: pre-load ML model so first detection doesn't timeout."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    import os

    base_url = os.getenv("ML_SERVICE_URL", "")
    if not base_url:
        return Response(
            json.dumps({"status": "not_configured"}),
            media_type="application/json",
        )
    try:
        result = _run_ml_client_async(lambda c: c.warm())
        return Response(
            json.dumps({"status": "success", "ml_service": result}),
            media_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"status": "error", "error": str(e)}),
            media_type="application/json",
        )


@rt("/api/admin/ml-compare")
async def post(request, sess=None):
    """Admin-only: detect faces and return embeddings for a photo. No DB writes.

    Proxies to ML service detect-and-embed endpoint. Used by
    scripts/compare_ml_embeddings.py for AD-229 cosine similarity verification.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    base_url = os.getenv("ML_SERVICE_URL", "")
    if not base_url:
        return Response(
            json.dumps({"error": "ML_SERVICE_URL not configured"}),
            media_type="application/json",
            status_code=503,
        )

    # Read uploaded file
    form = await request.form()
    upload = form.get("file")
    if not upload:
        return Response(
            json.dumps({"error": "No file uploaded. Send as multipart with field 'file'."}),
            media_type="application/json",
            status_code=400,
        )

    import tempfile

    # Save to temp file and forward to ML service
    file_bytes = await upload.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        result = _run_ml_client_async(lambda c: c.detect_and_embed(tmp_path))
        return Response(
            json.dumps(result),
            media_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=502,
        )
    finally:
        import pathlib

        pathlib.Path(tmp_path).unlink(missing_ok=True)


@rt("/api/admin/run-migrations")
def post(sess=None, request=None):
    """Admin-only: run pending SQL migrations (indexes, schema changes)."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from app.supabase_data import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return Response(
            json.dumps({"status": "error", "error": "Supabase not configured"}),
            media_type="application/json",
            status_code=503,
        )

    migrations = [
        "CREATE INDEX IF NOT EXISTS idx_photo_communities_community_id ON photo_communities (community_id)",
        "CREATE INDEX IF NOT EXISTS idx_identity_communities_community_id ON identity_communities (community_id)",
    ]

    results = []
    for sql in migrations:
        try:
            sb.rpc("exec_sql", {"query": sql}).execute()
            results.append({"sql": sql, "status": "ok"})
        except Exception as e:
            results.append({"sql": sql, "status": "error", "error": str(e)})

    return Response(
        json.dumps({"status": "complete", "migrations": results}),
        media_type="application/json",
    )


@rt("/api/admin/disk-usage")
def get(request, sess=None):
    """Admin-only disk usage diagnostic. Shows volume contents and sizes.
    Accepts either session auth (admin) or Bearer sync token."""
    sync_check = _check_sync_token(request)
    if sync_check is not None:
        guard = _main_mod._check_admin(sess)
        if guard:
            return guard

    import shutil as _shutil_diag

    storage_dir = os.environ.get("STORAGE_DIR", "")
    result = {"storage_dir": storage_dir or "(not set)"}

    # Root filesystem
    try:
        rt, ru, rf = _shutil_diag.disk_usage("/")
        result["root"] = {
            "total_mb": round(rt / (1024 * 1024)),
            "free_mb": round(rf / (1024 * 1024)),
            "used_pct": round((ru / rt) * 100, 1),
        }
    except Exception as e:
        result["root"] = {"error": str(e)}

    # Volume filesystem
    if storage_dir and Path(storage_dir).exists():
        try:
            vt, vu, vf = _shutil_diag.disk_usage(storage_dir)
            result["volume"] = {
                "mount": storage_dir,
                "total_mb": round(vt / (1024 * 1024)),
                "free_mb": round(vf / (1024 * 1024)),
                "used_pct": round((vu / vt) * 100, 1),
            }
        except Exception as e:
            result["volume"] = {"error": str(e)}

        # List top-level contents with sizes
        items = []
        base = Path(storage_dir)
        for item in sorted(base.iterdir()):
            try:
                if item.is_file():
                    size = item.stat().st_size
                    items.append({"name": item.name, "type": "file", "size_mb": round(size / (1024 * 1024), 2)})
                elif item.is_dir():
                    total_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    file_count = sum(1 for f in item.rglob("*") if f.is_file())
                    items.append(
                        {
                            "name": item.name,
                            "type": "dir",
                            "size_mb": round(total_size / (1024 * 1024), 2),
                            "file_count": file_count,
                        }
                    )
            except Exception as e:
                items.append({"name": item.name, "error": str(e)})
        result["contents"] = items

        # Also check data/ subdirectory
        data_dir = base / "data"
        if data_dir.exists():
            data_items = []
            for item in sorted(data_dir.iterdir()):
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        data_items.append(
                            {"name": item.name, "type": "file", "size_mb": round(size / (1024 * 1024), 2)}
                        )
                    elif item.is_dir():
                        total_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        file_count = sum(1 for f in item.rglob("*") if f.is_file())
                        data_items.append(
                            {
                                "name": item.name,
                                "type": "dir",
                                "size_mb": round(total_size / (1024 * 1024), 2),
                                "file_count": file_count,
                            }
                        )
                except Exception as e:
                    data_items.append({"name": item.name, "error": str(e)})
            result["data_contents"] = data_items

    return result


# =============================================================================
# LANDING PAGE
# =============================================================================


# =============================================================================
# ROUTES - PHASE 2: TEACH MODE
# =============================================================================


@rt("/api/admin/quick-identify-form/{face_id}")
def get(face_id: str, sess=None):
    """Return inline identify form for a face (admin only).

    Used on photo pages — clicking the pencil icon opens this form
    inline next to the face card. Submits to /api/face/create-identity.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Sanitize face_id for CSS-safe DOM IDs (colons/spaces break selectors)
    safe_fid = re.sub(r"[^a-zA-Z0-9_-]", "_", face_id)

    # Get confirmed identity names for autocomplete suggestions
    registry = _main_mod.load_registry()
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    name_suggestions = sorted(
        set(
            ensure_utf8_display(i.get("name", ""))
            for i in confirmed
            if i.get("name") and not i["name"].startswith("Unidentified")
        )
    )

    # Datalist for autocomplete
    datalist = (
        Datalist(
            *[Option(value=n) for n in name_suggestions[:50]],
            id=f"names-{safe_fid}",
        )
        if name_suggestions
        else None
    )

    return Div(
        Form(
            Div(
                Input(
                    type="text",
                    name="name",
                    placeholder="Enter name...",
                    list=f"names-{safe_fid}" if datalist else None,
                    cls="bg-slate-700 text-white text-sm rounded-lg px-3 py-2 w-full border border-slate-600 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none",
                    autofocus=True,
                    data_testid="quick-identify-input",
                ),
                datalist if datalist else None,
                cls="flex-1",
            ),
            Div(
                Button(
                    "Save",
                    type="submit",
                    cls="px-3 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors",
                ),
                Button(
                    "Cancel",
                    type="button",
                    cls="px-3 py-2 text-slate-400 hover:text-white text-sm transition-colors",
                    onclick=f"document.getElementById('qid-{safe_fid}').innerHTML='';",
                ),
                cls="flex gap-2 mt-2",
            ),
            Input(type="hidden", name="face_id", value=face_id),
            hx_post="/api/face/create-identity",
            hx_target="closest .photo-face-card",
            hx_swap="outerHTML",
            data_testid="quick-identify-form",
        ),
        id=f"qid-{safe_fid}",
        cls="mt-2",
    )


@rt("/api/ml-review/birth-year/{identity_id}/accept")
def post(identity_id: str, birth_year: str = "", source_detail: str = "", sess=None):
    """Accept (or edit & accept) an ML birth year estimate. Admin-only.

    Writes the accepted birth year to canonical identity metadata.
    Records in ground truth file for ML feedback loop.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        by = int(birth_year)
    except (ValueError, TypeError):
        return Div(
            Span("Invalid birth year", cls="text-red-400 text-xs"),
            id=f"ml-suggestion-{identity_id}",
        )

    registry = _main_mod.load_registry()
    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Div(
            Span("Identity not found", cls="text-red-400 text-xs"),
            id=f"ml-suggestion-{identity_id}",
        )

    # Get original ML estimate for ground truth
    estimates = _main_mod._load_birth_year_estimates()
    est = estimates.get(identity_id, {})
    original_ml = est.get("birth_year_estimate")

    # Determine source provenance
    if original_ml and by != original_ml:
        source = "admin_correction"
    else:
        source = "ml_accepted"

    # Write to canonical identity metadata
    registry.set_metadata(identity_id, {"birth_year": by}, user_source="admin_ml_review")
    _main_mod.save_registry(registry, changed_ids={identity_id})

    # Record review decision
    decisions = dict(_main_mod._load_ml_review_decisions())
    decisions[identity_id] = {
        "action": "accepted",
        "birth_year": by,
        "original_ml_estimate": original_ml,
        "source": source,
        "source_detail": source_detail.strip() if source_detail else "",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": "admin",
    }
    _main_mod._save_ml_review_decisions(decisions)

    # Write ground truth for ML feedback loop
    _main_mod._save_ground_truth_birth_year(
        identity_id=identity_id,
        identity=registry.get_identity(identity_id),
        birth_year=by,
        source=source,
        source_detail=source_detail.strip() if source_detail else "",
        original_ml_estimate=original_ml,
    )

    # Session 105b: Sync birth year estimate to Supabase (was DATA-015 dead code)
    try:
        from app.supabase_data import sync_birth_year_estimate

        sync_birth_year_estimate(
            identity_id,
            {
                "birth_year_estimate": by,
                "birth_year_confidence": "confirmed",
                "source": source,
            },
        )
    except Exception as e:
        logging.error(f"Supabase birth year estimate sync failed for {identity_id}: {e}")

    name = ensure_utf8_display(identity.get("name", ""))
    correction_note = f" (ML: {original_ml})" if original_ml and by != original_ml else ""

    # Count remaining pending for OOB counter update (UX-101)
    remaining = _main_mod._count_pending_birth_year_reviews()
    oob_counter = P(
        f"{remaining} pending review", cls="text-slate-400 text-sm mb-6", id="pending-count", hx_swap_oob="true"
    )

    return Div(
        Div(
            Span("\u2705 ", cls="mr-1"),
            Span(f"Born {by}{correction_note}", cls="text-emerald-400 text-sm font-medium"),
            cls="mb-1",
        ),
        Span(f"Confirmed for {name}", cls="text-xs text-slate-500"),
        oob_counter,
        id=f"review-row-{identity_id}",
        cls="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 mt-3 mb-3 text-center max-w-sm mx-auto",
        data_testid="ml-suggestion-accepted",
        # Auto-dismiss after 4s (UX-100)
        _="on load wait 4s then transition my opacity to 0 over 0.5s then remove me",
    )


@rt("/api/ml-review/birth-year/{identity_id}/reject")
def post(identity_id: str, reason: str = "", sess=None):
    """Reject an ML birth year estimate. Admin-only."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    estimates = _main_mod._load_birth_year_estimates()
    est = estimates.get(identity_id, {})
    original_ml = est.get("birth_year_estimate")

    decisions = dict(_main_mod._load_ml_review_decisions())
    decisions[identity_id] = {
        "action": "rejected",
        "original_ml_estimate": original_ml,
        "reason": reason.strip() if reason else "",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": "admin",
    }
    _main_mod._save_ml_review_decisions(decisions)

    # Invalidate cache
    _main_mod._ml_review_decisions_cache = None

    # Count remaining pending for OOB counter update (UX-101)
    remaining = _main_mod._count_pending_birth_year_reviews()
    oob_counter = P(
        f"{remaining} pending review", cls="text-slate-400 text-sm mb-6", id="pending-count", hx_swap_oob="true"
    )

    return Div(
        Span("\u274c Estimate rejected", cls="text-slate-500 text-xs"),
        oob_counter,
        id=f"review-row-{identity_id}",
        cls="text-center py-2",
        data_testid="ml-suggestion-rejected",
        # Auto-dismiss after 4s (UX-100)
        _="on load wait 4s then transition my opacity to 0 over 0.5s then remove me",
    )


@rt("/admin/pending")
def get(request, sess=None):
    """
    Admin page to review pending uploads from non-admin users.
    Requires admin when auth is enabled.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})
    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical _main_mod.sidebar counts (community-scoped)
    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry, community=community)

    # Load pending uploads (both contributor "pending" and admin "staged")
    # Session 121 (UX-207): Filter by community if in community context
    pending = _main_mod._load_pending_uploads()
    community_id = community.get("id") if community else None
    pending_items = [u for u in pending["uploads"].values() if u["status"] in ("pending", "staged")]
    if community_id:
        # Show uploads for this community + uploads with no community (pre-community data)
        pending_items = [u for u in pending_items if not u.get("community") or u.get("community") == community_id]
    # Sort by submitted_at descending (newest first)
    pending_items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)

    # Also show recently reviewed items
    reviewed_items = [u for u in pending["uploads"].values() if u["status"] in ("approved", "rejected")]
    if community_id:
        reviewed_items = [u for u in reviewed_items if not u.get("community") or u.get("community") == community_id]
    reviewed_items.sort(key=lambda x: x.get("reviewed_at", x.get("submitted_at", "")), reverse=True)
    reviewed_items = reviewed_items[:10]  # Show last 10

    # Separate contributor-pending items (eligible for batch approve) from staged
    contributor_pending_ids = [item["job_id"] for item in pending_items if item.get("status") == "pending"]

    # Build pending cards
    if pending_items:
        from urllib.parse import quote

        pending_cards = []
        for item in pending_items:
            job_id = item["job_id"]
            file_count = item.get("file_count", len(item.get("files", [])))
            file_msg = "1 file" if file_count == 1 else f"{file_count} files"
            is_staged = item.get("status") == "staged"
            collection_label = item.get("collection", "")
            source_label = item.get("source", "Unknown")
            detail_parts = [file_msg]
            if collection_label:
                detail_parts.append(f"Collection: {collection_label}")
            if source_label and source_label != "Unknown":
                detail_parts.append(f"Source: {source_label}")
            detail_line = " · ".join(detail_parts)

            # Checkbox for batch selection (contributor uploads only)
            batch_checkbox = (
                Input(
                    type="checkbox",
                    name="job_ids",
                    value=job_id,
                    form="batch-approve-form",
                    cls="batch-select-checkbox mt-0.5 accent-green-500",
                    data_testid=f"batch-checkbox-{job_id}",
                )
                if not is_staged
                else None
            )

            # Staged items (admin uploads) show status badge, no approve/reject
            # Pending items (contributor uploads) show approve/reject buttons
            if is_staged:
                actions = Div(
                    Span(
                        "Staged", cls="px-2 py-1 bg-indigo-600/30 text-indigo-300 text-xs font-bold rounded uppercase"
                    ),
                    Button(
                        "Mark Processed",
                        hx_post=f"/admin/pending/{job_id}/mark-processed",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors",
                    ),
                    cls="flex gap-2 items-start",
                )
            else:
                actions = Div(
                    Button(
                        "Approve",
                        hx_post=f"/admin/pending/{job_id}/approve",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        hx_indicator=f"#approve-spinner-{job_id}",
                        cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors",
                    ),
                    Span(
                        "…",
                        id=f"approve-spinner-{job_id}",
                        cls="htmx-indicator text-green-400 text-xs",
                    ),
                    Form(
                        Select(
                            Option("Reason…", value="", selected=True),
                            Option("Duplicate", value="Duplicate"),
                            Option("Not relevant", value="Not relevant"),
                            Option("Poor quality", value="Poor quality"),
                            Option("Wrong archive", value="Wrong archive"),
                            name="rejection_reason",
                            cls="text-xs bg-slate-800 border border-slate-600 rounded px-1 py-1 text-slate-300",
                        ),
                        Button(
                            "Reject",
                            type="submit",
                            cls="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-500 transition-colors",
                        ),
                        hx_post=f"/admin/pending/{job_id}/reject",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="flex gap-1 items-center",
                    ),
                    cls="flex gap-2 items-center",
                )

            # Photo preview thumbnails (served via admin-authenticated endpoint)
            preview_thumbs = []
            upload_files = item.get("files", [])

            is_compare = item.get("compare_mode", False)
            for fname in upload_files[:6]:
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    # Try staging preview first; fall back to R2 public URL if staging is gone
                    staging_path = _main_mod.data_path / "staging" / job_id / fname
                    if staging_path.exists():
                        thumb_url = f"/admin/staging-preview/{quote(job_id)}/{quote(fname)}"
                    elif os.environ.get("R2_PUBLIC_URL"):
                        r2_base = os.environ["R2_PUBLIC_URL"]
                        if is_compare:
                            # Compare uploads stored at uploads/pending/{job_id}/{filename} on R2
                            thumb_url = f"{r2_base}/uploads/pending/{quote(job_id)}/{quote(fname)}"
                        else:
                            thumb_url = f"{r2_base}/raw_photos/{quote(fname)}"
                    else:
                        thumb_url = f"/admin/staging-preview/{quote(job_id)}/{quote(fname)}"
                    # Graceful fallback: show filename label if image fails to load
                    preview_thumbs.append(
                        Div(
                            A(
                                Img(
                                    src=thumb_url,
                                    alt=fname,
                                    loading="lazy",
                                    cls="w-16 h-16 object-cover rounded border border-slate-600 cursor-pointer hover:border-indigo-400 transition-colors",
                                    title=fname,
                                    onerror="this.style.display='none'; this.parentElement.nextElementSibling.style.display='flex'",
                                ),
                                href=thumb_url,
                                target="_blank",
                                rel="noopener",
                                data_testid=f"pending-thumb-{job_id}",
                            ),
                            Div(
                                fname[:12],
                                cls="w-16 h-16 bg-slate-700 border border-slate-600 rounded text-[8px] text-slate-400 items-center justify-center text-center p-1 hidden",
                            ),
                            cls="flex-shrink-0",
                        )
                    )
            remaining = len(upload_files) - 6
            if remaining > 0:
                preview_thumbs.append(
                    Div(
                        f"+{remaining}",
                        cls="w-16 h-16 flex items-center justify-center rounded border border-slate-600 text-slate-400 text-sm bg-slate-800",
                    )
                )
            preview_row = Div(*preview_thumbs, cls="flex gap-2 mt-3 flex-wrap") if preview_thumbs else None

            # Session 121 (UX-207): Community badge on approval cards
            item_community = item.get("community", "")
            community_badge = (
                Span(
                    item_community if isinstance(item_community, str) and len(item_community) > 20 else item_community,
                    cls="px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-900/50 text-indigo-300 border border-indigo-700/50",
                )
                if item_community
                else None
            )

            card_row = Div(
                batch_checkbox if batch_checkbox else Div(cls="w-4"),
                Div(
                    Div(
                        P(item.get("uploader_email", "Unknown"), cls="text-slate-200 font-medium text-sm"),
                        community_badge,
                        cls="flex items-center gap-2",
                    )
                    if community_badge
                    else P(item.get("uploader_email", "Unknown"), cls="text-slate-200 font-medium text-sm"),
                    P(detail_line, cls="text-slate-400 text-xs"),
                    P(
                        f"Submitted: {item.get('submitted_at', 'Unknown')[:19].replace('T', ' ')}",
                        cls="text-slate-500 text-xs mt-0.5",
                    ),
                    P(f"Job ID: {job_id}", cls="text-slate-600 text-xs font-mono"),
                    cls="flex-1",
                ),
                actions,
                cls="flex items-start gap-3 justify-between",
            )

            pending_cards.append(
                Div(
                    card_row,
                    preview_row,
                    id=f"pending-card-{job_id}",
                    cls="p-4 bg-slate-800 border border-slate-700 rounded-lg",
                )
            )

        # Batch approve toolbar (only shown when there are contributor-pending items)
        batch_toolbar = ""
        if contributor_pending_ids:
            batch_toolbar = Div(
                Form(
                    Div(
                        Label(
                            Input(
                                type="checkbox",
                                id="select-all-pending",
                                cls="accent-green-500",
                                data_testid="select-all-pending",
                            ),
                            " Select All",
                            cls="text-slate-300 text-xs flex items-center gap-1.5 cursor-pointer",
                        ),
                        Button(
                            "Approve Selected",
                            type="submit",
                            cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors disabled:opacity-50",
                            data_testid="batch-approve-btn",
                        ),
                        cls="flex items-center gap-4",
                    ),
                    id="batch-approve-form",
                    hx_post="/admin/pending/batch-approve",
                    hx_target="#batch-approve-result",
                    hx_swap="outerHTML",
                    cls="flex items-center gap-4",
                ),
                Div(id="batch-approve-result"),
                Script("""
                    (function() {
                        var selectAll = document.getElementById('select-all-pending');
                        if (!selectAll) return;
                        selectAll.addEventListener('change', function() {
                            var boxes = document.querySelectorAll('.batch-select-checkbox');
                            boxes.forEach(function(b) { b.checked = selectAll.checked; });
                        });
                    })();
                """),
                cls="mb-3 p-3 bg-slate-800/60 border border-slate-700/50 rounded-lg",
            )

        pending_section = Div(batch_toolbar, *pending_cards, cls="space-y-3")
    else:
        pending_section = Div(
            P("No pending uploads.", cls="text-slate-500 text-sm"),
            cls="p-4 bg-slate-800/50 border border-slate-700/50 rounded-lg",
        )

    # Build reviewed history cards
    if reviewed_items:
        reviewed_cards = []
        for item in reviewed_items:
            status_color = "green" if item["status"] == "approved" else "red"
            status_label = "Approved" if item["status"] == "approved" else "Rejected"
            file_count = item.get("file_count", len(item.get("files", [])))
            file_msg = "1 file" if file_count == 1 else f"{file_count} files"

            # Format timestamps
            ts_parts = []
            submitted_at = item.get("submitted_at", "")
            reviewed_at = item.get("reviewed_at", "")
            try:
                from datetime import datetime as _dt

                if submitted_at:
                    dt = _dt.fromisoformat(submitted_at.replace("Z", "+00:00"))
                    ts_parts.append(
                        Span(f"Submitted: {dt.strftime('%b %-d at %-I:%M %p')}", cls="text-slate-500 text-[10px]")
                    )
                if reviewed_at:
                    dt = _dt.fromisoformat(reviewed_at.replace("Z", "+00:00"))
                    ts_parts.append(
                        Span(f"{status_label}: {dt.strftime('%b %-d at %-I:%M %p')}", cls="text-slate-500 text-[10px]")
                    )
            except (ValueError, TypeError):
                pass

            # Build photo links for approved uploads
            photo_links = []
            if item["status"] == "approved":
                job_id = item.get("job_id", "")
                files = item.get("files", [])
                for idx, file_info in enumerate(files):
                    fname = file_info.get("filename", "") if isinstance(file_info, dict) else str(file_info)
                    if fname:
                        # Try to find the photo by inbox ID pattern
                        candidate_id = f"inbox_{job_id}_{idx}_{Path(fname).stem}"
                        photo_links.append(
                            A(
                                "View photo",
                                href=f"{nav_prefix}/photo/{candidate_id}",
                                cls="text-indigo-400 hover:text-indigo-300 text-[10px] underline",
                                data_testid="reviewed-photo-link",
                            )
                        )

            card_elements = [
                Div(
                    Span(status_label, cls=f"text-{status_color}-400 text-xs font-bold uppercase"),
                    Span(" | ", cls="text-slate-600"),
                    Span(item.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
                    Span(f" | {file_msg}", cls="text-slate-500 text-xs"),
                    cls="flex items-center gap-1",
                ),
            ]
            if ts_parts:
                card_elements.append(Div(*ts_parts, cls="flex gap-3 mt-1"))
            if photo_links:
                card_elements.append(Div(*photo_links, cls="flex gap-2 mt-1"))

            reviewed_cards.append(
                Div(
                    *card_elements,
                    cls="px-3 py-2 bg-slate-800/30 border border-slate-700/30 rounded",
                    data_testid="reviewed-card",
                )
            )
        reviewed_section = Div(
            H3("Recently Reviewed", cls="text-lg font-semibold text-slate-300 mb-3 mt-6"),
            *reviewed_cards,
            cls="space-y-2",
        )
    else:
        reviewed_section = None

    # Sidebar styles (same as upload page)
    page_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #_main_mod.sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #_main_mod.sidebar.open { transform: translateX(0); }
            #_main_mod.sidebar .sidebar-label { display: inline !important; }
            #_main_mod.sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #_main_mod.sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    _main_mod.mobile_header = Div(
        Button(
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
        Span("Pending Uploads", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30",
    )
    sidebar_overlay = Div(
        onclick="closeSidebar()", cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )
    sidebar_script = Script("""
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
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
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
        })();
    """)

    return (
        Title(f"Pending Uploads - {community_name}"),
        style,
        page_style,
        Div(
            _main_mod.toast_container(),
            _main_mod.mobile_header,
            sidebar_overlay,
            _main_mod.sidebar(counts, current_section="pending_uploads", user=user),
            Main(
                Div(
                    # Header
                    Div(
                        H2("Pending Uploads", cls="text-2xl font-bold text-white"),
                        P(
                            f"{len(pending_items)} upload{'s' if len(pending_items) != 1 else ''} awaiting review",
                            cls="text-sm text-slate-400 mt-1",
                        ),
                        cls="mb-6",
                    ),
                    pending_section,
                    reviewed_section if reviewed_section else "",
                    cls="max-w-3xl mx-auto px-4 sm:px-8 py-6",
                ),
                cls="main-content min-h-screen overflow-x-hidden",
            ),
            sidebar_script,
            cls="h-full",
        ),
    )


# =============================================================================
# DISCOVERIES — High-confidence matches to confirmed identities
# =============================================================================


@rt("/admin/proposals")
def get(request, sess=None):
    """
    Admin page to review proposed identity matches.
    Requires admin when auth is enabled.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})
    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical _main_mod.sidebar counts (community-scoped)
    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry, community=community)

    # Sidebar styles (reuse)
    page_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #_main_mod.sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #_main_mod.sidebar.open { transform: translateX(0); }
            #_main_mod.sidebar .sidebar-label { display: inline !important; }
            #_main_mod.sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #_main_mod.sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    _main_mod.mobile_header = Div(
        Button(
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
        Span("Proposals", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30",
    )
    sidebar_overlay = Div(
        onclick="closeSidebar()", cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )
    sidebar_script = Script("""
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
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
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
        })();
    """)

    return (
        Title(f"Proposals - {community_name}"),
        style,
        page_style,
        Div(
            _main_mod.toast_container(),
            _main_mod.mobile_header,
            sidebar_overlay,
            _main_mod.sidebar(counts, current_section="proposals", user=user),
            Main(
                Div(
                    Div(
                        H2("Proposed Matches", cls="text-2xl font-bold text-white"),
                        P(
                            f"{counts['proposals']} pending proposal{'s' if counts['proposals'] != 1 else ''}",
                            cls="text-sm text-slate-400 mt-1",
                        ),
                        cls="mb-6",
                    ),
                    # Load proposals list via HTMX on page load
                    Div(
                        id="proposed-matches-list",
                        hx_get=f"/api/proposed-matches?community_slug={community.get('slug', '')}"
                        if community
                        else "/api/proposed-matches",
                        hx_trigger="load",
                        hx_swap="innerHTML",
                    ),
                    cls="max-w-3xl mx-auto px-4 sm:px-8 py-6",
                ),
                cls="main-content min-h-screen overflow-x-hidden",
            ),
            sidebar_script,
            cls="h-full",
        ),
    )


def _auto_confirm_job_identities(data_path: Path, job_id: str, user_source: str) -> int:
    """Auto-confirm INBOX identities that have a real name, created for this job.

    INBOX identities without a real name (still "Unidentified Person NNN") cannot be
    confirmed — they stay in INBOX for admin review.  Only identities that have been
    assigned a human-readable name during ingest (e.g. matched to a named cluster) are
    eligible for auto-confirm.

    Returns the number of identities confirmed.
    """
    try:
        from core.registry import IdentityRegistry, IdentityState

        identity_path = data_path / "identities.json"
        registry = IdentityRegistry.load(identity_path)
        confirmed_count = 0
        # list_identities_by_job uses provenance.job_id to find all identities for this job
        for identity in registry.list_identities_by_job(job_id):
            if identity.get("state") != IdentityState.INBOX.value:
                continue
            # Only auto-confirm if the identity has a real (non-placeholder) name
            if not IdentityRegistry._is_real_name(identity.get("name")):
                continue
            try:
                registry.confirm_identity(identity["identity_id"], user_source=user_source)
                confirmed_count += 1
            except Exception as e:
                logger.warning(f"Could not auto-confirm identity {identity['identity_id']}: {e}")
        if confirmed_count:
            registry.save(identity_path)
            logger.info(f"Auto-confirmed {confirmed_count} named identities for job {job_id}")
        return confirmed_count
    except Exception as e:
        logger.warning(f"Auto-confirm failed for job {job_id}: {e}")
        return 0


@rt("/admin/pending/{job_id}/approve")
def post(job_id: str, sess=None, request=None):
    """Approve a pending upload. Requires admin."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    pending = _main_mod._load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg",
            id=f"pending-card-{job_id}",
        )

    upload = pending["uploads"][job_id]
    # Allow approving both "pending" (contributor) and "staged" (admin) uploads.
    # Already-approved/rejected/processed uploads cannot be re-approved.
    if upload["status"] in ("approved", "rejected", "processed"):
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
            id=f"pending-card-{job_id}",
        )

    # Update status to approved
    upload["status"] = "approved"
    upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["reviewed_by"] = user.email if user else "unknown"
    _main_mod._save_pending_uploads(pending)
    _main_mod.log_user_action(
        "APPROVE_UPLOAD",
        job_id=job_id,
        uploader=upload.get("uploaded_by", "unknown"),
        file_count=len(upload.get("files", [])),
        admin=user.email if user else "unknown",
    )

    will_process = False
    # If PROCESSING_ENABLED, move files from staging to uploads and spawn processing
    if PROCESSING_ENABLED:
        import shutil

        staging_dir = _main_mod.data_path / "staging" / job_id
        uploads_dir = _main_mod.data_path / "uploads" / job_id
        if staging_dir.exists():
            will_process = True
            uploads_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging_dir, uploads_dir, dirs_exist_ok=True)
        elif upload.get("compare_mode"):
            # Compare uploads store photos in R2 at uploads/pending/{job_id}/{filename}.
            # Try to recover the photo from R2 for processing.
            try:
                from core.storage import can_write_r2

                if can_write_r2():
                    import boto3

                    s3 = boto3.client(
                        "s3",
                        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                    )
                    bucket = os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")
                    # R2 path matches what compare_routes.py uploads (line 1635)
                    upload_files = upload.get("files", [])
                    r2_filename = upload_files[0] if upload_files else f"{job_id}.jpg"
                    r2_key = f"uploads/pending/{job_id}/{r2_filename}"
                    uploads_dir.mkdir(parents=True, exist_ok=True)
                    local_path = uploads_dir / r2_filename
                    s3.download_file(bucket, r2_key, str(local_path))
                    will_process = True
                    logger.info(f"Downloaded compare photo from R2 for job {job_id}")
            except Exception as r2_err:
                logger.warning(f"Could not recover compare photo from R2 for {job_id}: {r2_err}")

        # Run processing in background thread for ANY approved upload with files
        if will_process:
            import threading

            source = upload.get("source", "")
            upload_collection = upload.get("collection", "")
            uploader_email = upload.get("uploader_email", "")
            submitted_at = upload.get("submitted_at", "")
            source_url = upload.get("source_url", "")
            admin_email = user.email if user else "admin"

            def _bg_approve_ingest():
                import logging as _bg_logging

                log_path = uploads_dir / f"{job_id}.log"
                try:
                    file_handler = _bg_logging.FileHandler(str(log_path))
                    file_handler.setLevel(_bg_logging.INFO)
                    _bg_logging.getLogger("core.ingest_inbox").addHandler(file_handler)

                    from core.ingest_inbox import process_directory

                    ingest_result = process_directory(
                        directory=uploads_dir,
                        job_id=job_id,
                        data_dir=_main_mod.data_path,
                        source=source,
                        collection=upload_collection,
                        prefer_hybrid=True,
                        uploaded_by=uploader_email,
                        upload_date=submitted_at,
                    )

                    # Session 121 (UX-212): Set source_url on photos from this upload
                    if source_url and ingest_result.get("photo_ids"):
                        from core.photo_registry import PhotoRegistry

                        photo_reg = PhotoRegistry.load(_main_mod.data_path / "photo_index.json")
                        for pid in ingest_result["photo_ids"]:
                            photo_reg.set_source_url(pid, source_url)
                        photo_reg.save(_main_mod.data_path / "photo_index.json")

                    # Auto-confirm all INBOX identities created for this job so
                    # detected faces appear in the main photo browse immediately.
                    _auto_confirm_job_identities(
                        _main_mod.data_path, job_id, user_source=f"admin_approve:{admin_email}"
                    )

                    # Upload new raw photos + crops to R2 (if R2 is configured)
                    try:
                        _main_mod._upload_new_files_to_r2(_main_mod.data_path, job_id)
                    except Exception as r2_err:
                        _bg_logging.getLogger("core.ingest_inbox").warning(
                            f"R2 upload failed for job {job_id}: {r2_err}"
                        )

                    # Invalidate caches so new photo appears immediately in browse/landing
                    _main_mod._invalidate_all_caches()
                except Exception:
                    import traceback

                    try:
                        with open(log_path, "a") as _lf:
                            traceback.print_exc(file=_lf)
                    except Exception:
                        pass

            threading.Thread(target=_bg_approve_ingest, daemon=True, name=f"approve-{job_id}").start()

    file_count = upload.get("file_count", len(upload.get("files", [])))
    processing_note = (
        P(
            "Processing in background — photos will appear in browse shortly.",
            cls="text-green-300/70 text-[10px] mt-1",
        )
        if will_process
        else None
    )
    return Div(
        Div(
            Span("Approved", cls="text-green-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1",
        ),
        processing_note if processing_note else "",
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg",
        id=f"pending-card-{job_id}",
    )


@rt("/admin/pending/{job_id}/reject")
def post(job_id: str, rejection_reason: str = "", sess=None):
    """Reject a pending upload. Requires admin.

    Accepts an optional ``rejection_reason`` form field with a short label
    (e.g. "Duplicate", "Not relevant", "Poor quality", "Wrong archive").
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    pending = _main_mod._load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg",
            id=f"pending-card-{job_id}",
        )

    upload = pending["uploads"][job_id]
    # Allow rejecting both "pending" and "staged" uploads.
    if upload["status"] in ("approved", "rejected", "processed"):
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
            id=f"pending-card-{job_id}",
        )

    # Update status to rejected with full audit metadata
    upload["status"] = "rejected"
    upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["reviewed_by"] = user.email if user else "unknown"
    if rejection_reason:
        upload["rejection_reason"] = rejection_reason.strip()
    _main_mod._save_pending_uploads(pending)
    _main_mod.log_user_action(
        "REJECT_UPLOAD",
        job_id=job_id,
        uploader=upload.get("uploaded_by", "unknown"),
        admin=user.email if user else "unknown",
        reason=upload.get("rejection_reason", ""),
    )

    # Clean up orphaned identities created during processing of this upload
    orphaned_identity_ids = _cleanup_orphaned_identities_for_upload(upload)
    if orphaned_identity_ids:
        logger.info(
            f"Rejection cleanup: marked {len(orphaned_identity_ids)} orphaned identities as REJECTED for job {job_id}"
        )

    # Sync rejection metadata to Supabase BEFORE deleting staging files
    try:
        from app.supabase_data import sync_pending_upload

        sync_pending_upload(job_id, upload)
    except Exception as e:
        logger.warning(f"Supabase sync failed for rejected upload {job_id}: {e}")

    # Clean up staging files (metadata preserved in JSON + Supabase)
    import shutil

    staging_dir = _main_mod.data_path / "staging" / job_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    file_count = upload.get("file_count", len(upload.get("files", [])))
    reason_label = upload.get("rejection_reason", "")
    return Div(
        Div(
            Span("Rejected", cls="text-red-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            *(
                [
                    Span(" | ", cls="text-slate-600"),
                    Span(reason_label, cls="text-red-400/70 text-xs italic"),
                ]
                if reason_label
                else []
            ),
            cls="flex items-center gap-1 flex-wrap",
        ),
        cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg",
        id=f"pending-card-{job_id}",
    )


def _cleanup_orphaned_identities_for_upload(upload: dict) -> list[str]:
    """Mark as REJECTED any identities whose only faces came from this upload.

    An identity is considered orphaned if every face_id in its anchor_ids and
    candidate_ids belongs exclusively to photos that were part of this upload
    batch.  Identities with at least one face from another source are left
    untouched.  CONFIRMED identities are never touched (Gatekeeper invariant).

    Returns the list of identity_ids that were marked REJECTED.
    """
    # Collect the filenames / face-id prefixes tied to this upload
    upload_files: list[str] = upload.get("files", [])
    if not upload_files:
        return []

    try:
        registry = _main_mod.load_registry()
        photo_registry = _main_mod.load_photo_registry()
    except Exception as exc:
        logger.warning(f"Could not load registries for orphan cleanup: {exc}")
        return []

    # Build the set of face_ids from photos associated with this upload.
    # We match by filename: the photo_registry stores paths, and upload.files
    # contains bare filenames (e.g. "photo.jpg").
    upload_basenames = {Path(f).name for f in upload_files}
    upload_face_ids: set[str] = set()
    for photo_id in list(photo_registry._photos):
        photo_path = photo_registry.get_photo_path(photo_id)
        if photo_path and Path(photo_path).name in upload_basenames:
            upload_face_ids.update(photo_registry.get_faces_in_photo(photo_id))

    if not upload_face_ids:
        return []

    orphaned_ids: list[str] = []
    changed = False
    for iid, identity in list(registry._identities.items()):
        if not identity:
            continue
        state = identity.get("state", "")
        # Never touch confirmed identities
        if state == IdentityState.CONFIRMED.value:
            continue
        all_faces = set(identity.get("anchor_ids", [])) | set(identity.get("candidate_ids", []))
        if not all_faces:
            continue
        # Orphaned: every face belongs to this upload batch
        if all_faces.issubset(upload_face_ids):
            identity["state"] = IdentityState.REJECTED.value
            identity["rejection_source"] = "upload_rejected"
            registry._identities[iid] = identity
            orphaned_ids.append(iid)
            changed = True

    if changed:
        try:
            _main_mod.save_registry(registry, changed_ids=set(orphaned_ids))
        except Exception as exc:
            logger.warning(f"Failed to save registry after orphan cleanup: {exc}")
            return []

    return orphaned_ids


@rt("/admin/pending/{job_id}/mark-processed")
def post(job_id: str, sess=None):
    """Mark a staged upload as processed. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    pending = _main_mod._load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg",
        )

    upload = pending["uploads"][job_id]
    if upload["status"] != "staged":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
        )

    upload["status"] = "processed"
    upload["processed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["processed_by"] = user.email if user else "unknown"
    _main_mod._save_pending_uploads(pending)

    file_count = upload.get("file_count", len(upload.get("files", [])))
    return Div(
        Div(
            Span("Processed", cls="text-green-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1",
        ),
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg",
    )


@rt("/admin/pending/batch-approve")
async def post(request, sess=None):
    """Approve multiple pending uploads at once. Requires admin.

    Accepts form data with one or more ``job_ids`` fields.  Returns an
    HTMX-compatible response that replaces the pending-list container.
    """
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    form = await request.form()
    # ``getlist`` returns all values for a repeated form field.
    job_ids = form.getlist("job_ids")

    if not job_ids:
        return Div(
            P("No uploads selected.", cls="text-yellow-400 text-sm"),
            cls="p-3 bg-yellow-900/20 border border-yellow-500/30 rounded-lg mb-3",
        )

    pending = _main_mod._load_pending_uploads()
    user = get_current_user(sess or {})
    approved_ids = []
    skipped_ids = []

    for job_id in job_ids:
        if job_id not in pending["uploads"]:
            skipped_ids.append(job_id)
            continue
        upload = pending["uploads"][job_id]
        if upload["status"] in ("approved", "rejected", "processed"):
            skipped_ids.append(job_id)
            continue
        upload["status"] = "approved"
        upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        upload["reviewed_by"] = user.email if user else "unknown"
        approved_ids.append(job_id)

    if approved_ids:
        _main_mod._save_pending_uploads(pending)
        _main_mod.log_user_action(
            "BATCH_APPROVE_UPLOADS",
            job_ids=approved_ids,
            count=len(approved_ids),
            admin=user.email if user else "unknown",
        )

        # Spawn background processing for each approved upload
        if PROCESSING_ENABLED:
            import shutil
            import threading

            admin_email = user.email if user else "admin"
            for job_id in approved_ids:
                upload = pending["uploads"][job_id]
                staging_dir = _main_mod.data_path / "staging" / job_id
                uploads_dir = _main_mod.data_path / "uploads" / job_id
                has_files = False
                if staging_dir.exists():
                    uploads_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(staging_dir, uploads_dir, dirs_exist_ok=True)
                    has_files = True
                elif upload.get("compare_mode"):
                    # Compare uploads: recover from R2
                    try:
                        from core.storage import can_write_r2

                        if can_write_r2():
                            import boto3

                            s3 = boto3.client(
                                "s3",
                                endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                                aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                                aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                            )
                            bucket = os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")
                            upload_files = upload.get("files", [])
                            r2_filename = upload_files[0] if upload_files else f"{job_id}.jpg"
                            r2_key = f"uploads/pending/{job_id}/{r2_filename}"
                            uploads_dir.mkdir(parents=True, exist_ok=True)
                            local_path = uploads_dir / r2_filename
                            s3.download_file(bucket, r2_key, str(local_path))
                            has_files = True
                    except Exception as r2_err:
                        logger.warning(f"Batch approve: could not recover {job_id} from R2: {r2_err}")
                if not has_files:
                    continue

                source = upload.get("source", "")
                upload_collection = upload.get("collection", "")
                uploader_email = upload.get("uploader_email", "")
                submitted_at = upload.get("submitted_at", "")

                def _make_bg(jid, udir, src, coll, email, ts):
                    def _bg():
                        import logging as _bg_logging

                        log_path = udir / f"{jid}.log"
                        try:
                            file_handler = _bg_logging.FileHandler(str(log_path))
                            file_handler.setLevel(_bg_logging.INFO)
                            _bg_logging.getLogger("core.ingest_inbox").addHandler(file_handler)

                            from core.ingest_inbox import process_directory

                            process_directory(
                                directory=udir,
                                job_id=jid,
                                data_dir=_main_mod.data_path,
                                source=src,
                                collection=coll,
                                prefer_hybrid=True,
                                uploaded_by=email,
                                upload_date=ts,
                            )

                            _auto_confirm_job_identities(
                                _main_mod.data_path, jid, user_source=f"admin_approve:{admin_email}"
                            )

                            try:
                                _main_mod._upload_new_files_to_r2(_main_mod.data_path, jid)
                            except Exception as r2_err:
                                _bg_logging.getLogger("core.ingest_inbox").warning(
                                    f"R2 upload failed for job {jid}: {r2_err}"
                                )

                            _main_mod._invalidate_all_caches()
                        except Exception:
                            import traceback

                            try:
                                with open(log_path, "a") as _lf:
                                    traceback.print_exc(file=_lf)
                            except Exception:
                                pass

                    return _bg

                threading.Thread(
                    target=_make_bg(job_id, uploads_dir, source, upload_collection, uploader_email, submitted_at),
                    daemon=True,
                    name=f"approve-{job_id}",
                ).start()

    # Build summary response — redirect to /admin/pending to refresh the full list
    _batch_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    _batch_prefix = _main_mod.community_url_prefix(_batch_slug)
    msg_parts = [f"Approved {len(approved_ids)} upload{'s' if len(approved_ids) != 1 else ''}"]
    if skipped_ids:
        msg_parts.append(f"{len(skipped_ids)} skipped (already reviewed)")
    summary = " | ".join(msg_parts)

    return Div(
        P(summary, cls="text-green-400 text-sm font-medium"),
        P(
            A(
                "Refresh page",
                href=f"{_batch_prefix}/admin/pending",
                cls="text-indigo-400 hover:text-indigo-300 underline text-xs",
            ),
            cls="mt-1",
        ),
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg mb-3",
        id="batch-approve-result",
    )


@app.get("/admin/staging-preview/{job_id}/{filename:path}")
async def admin_staging_preview(job_id: str, filename: str, sess=None):
    """Serve staged upload photos for admin preview. Session-authenticated."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return Response("Unauthorized", status_code=401)

    # Security: block path traversal
    if ".." in job_id or ".." in filename or job_id.startswith("/") or filename.startswith("/"):
        return Response("Invalid path", status_code=400)

    staging_dir = _main_mod.data_path / "staging"
    target = (staging_dir / job_id / filename).resolve()

    # Ensure resolved path is still inside staging dir
    if not str(target).startswith(str(staging_dir.resolve())):
        return Response("Invalid path", status_code=400)

    if not target.exists() or not target.is_file():
        return Response("File not found", status_code=404)

    # Determine content type from extension
    ext = target.suffix.lower()
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(str(target), media_type=content_type)


# Move staging preview route before FastHTML's catch-all static route


@rt("/admin/export/identities")
def get(sess=None):
    """Download identities.json. Admin-only."""
    block = _main_mod._check_admin(sess)
    if block:
        return block
    fpath = _main_mod.data_path / "identities.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    return FileResponse(
        str(fpath),
        media_type="application/json",
        filename="identities.json",
    )


@rt("/admin/export/photo-index")
def get(sess=None):
    """Download photo_index.json. Admin-only."""
    block = _main_mod._check_admin(sess)
    if block:
        return block
    fpath = _main_mod.data_path / "photo_index.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    return FileResponse(
        str(fpath),
        media_type="application/json",
        filename="photo_index.json",
    )


@rt("/admin/export/all")
def get(sess=None):
    """Download a ZIP of all data files. Admin-only."""
    block = _main_mod._check_admin(sess)
    if block:
        return block
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("identities.json", "photo_index.json"):
            fpath = _main_mod.data_path / name
            if fpath.exists():
                zf.write(str(fpath), arcname=name)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=rhodesli-data-export.zip"},
    )


# =============================================================================
# ML EVALUATION DASHBOARD (admin-only)
# =============================================================================


@rt("/admin/ml-dashboard")
def get(request, sess=None):
    """ML evaluation dashboard. Shows golden set stats, thresholds, identity counts."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"

    registry = _main_mod.load_registry()

    # Identity stats by state
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped = registry.list_identities(state=IdentityState.SKIPPED)
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)

    total_identities = len(confirmed) + len(skipped) + len(inbox) + len(proposed) + len(rejected)
    total_faces = sum(
        len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", [])) for i in confirmed + skipped + inbox + proposed
    )

    # Golden set stats
    gs_stats = _load_golden_set_stats()
    eval_stats = _load_evaluation_stats()

    # Recent actions from event log
    recent_actions = _load_recent_actions(limit=10)

    # Build stat cards
    stat_cards = Div(
        _stat_card("Confirmed", str(len(confirmed)), "emerald"),
        _stat_card("Skipped", str(len(skipped)), "amber"),
        _stat_card("New Matches", str(len(inbox) + len(proposed)), "blue"),
        _stat_card("Rejected", str(len(rejected)), "red"),
        _stat_card("Total Faces", str(total_faces), "slate"),
        _stat_card("Identities", str(total_identities), "indigo"),
        cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8",
    )

    # Golden set section
    if gs_stats:
        gs_section = Div(
            H3("Golden Set", cls="text-lg font-semibold text-white mb-3"),
            Div(
                _stat_card("Mappings", str(gs_stats.get("total_mappings", 0)), "purple"),
                _stat_card("Identities", str(gs_stats.get("unique_identities", 0)), "purple"),
                _stat_card("Photos", str(gs_stats.get("unique_photos", 0)), "purple"),
                cls="grid grid-cols-3 gap-4",
            ),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )
    else:
        gs_section = Div(
            H3("Golden Set", cls="text-lg font-semibold text-white mb-3"),
            P("No golden set data available. Run: python scripts/build_golden_set.py", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )

    # Golden set diversity section (ML-011)
    diversity_path = _main_mod.data_path / "golden_set_diversity.json"
    if diversity_path.exists():
        try:
            import json as _json

            with open(diversity_path) as f:
                diversity = _json.load(f)
            diversity_section = Div(
                H3("Golden Set Diversity (ML-011)", cls="text-lg font-semibold text-white mb-3"),
                Div(
                    _stat_card("Multi-face", str(diversity.get("multi_face_identities", 0)), "blue"),
                    _stat_card("Single-face", str(diversity.get("single_face_identities", 0)), "amber"),
                    _stat_card("Same Pairs", str(diversity.get("same_person_pairs", 0)), "green"),
                    _stat_card("Collections", str(diversity.get("collections", 0)), "purple"),
                    cls="grid grid-cols-4 gap-4",
                ),
                P(
                    f"Same-person pairs: {diversity.get('same_person_pairs', 0)} | "
                    f"Different-person pairs: {diversity.get('different_person_pairs', 0)}",
                    cls="text-xs text-slate-400 mt-2",
                ),
                cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
            )
        except Exception:
            diversity_section = Span()
    else:
        diversity_section = Div(
            H3("Golden Set Diversity", cls="text-lg font-semibold text-white mb-3"),
            P("Run: python scripts/analyze_golden_set.py", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )

    # Threshold section
    threshold_section = Div(
        H3("Calibrated Thresholds (AD-013)", cls="text-lg font-semibold text-white mb-3"),
        Div(
            _threshold_row("VERY HIGH", MATCH_THRESHOLD_VERY_HIGH, "100%", "~13%", "emerald"),
            _threshold_row("HIGH", MATCH_THRESHOLD_HIGH, "100%", "~63%", "green"),
            _threshold_row("MODERATE", MATCH_THRESHOLD_MODERATE, "~94%", "~81%", "amber"),
            _threshold_row("MEDIUM", MATCH_THRESHOLD_MEDIUM, "~87%", "~87%", "orange"),
            cls="space-y-2",
        ),
        cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
    )

    # Evaluation results
    if eval_stats:
        eval_section = Div(
            H3("Last Evaluation", cls="text-lg font-semibold text-white mb-3"),
            P(f"Zero-FP ceiling: {eval_stats.get('zero_fp_ceiling', 'N/A')}", cls="text-sm text-slate-300"),
            P(f"Optimal F1 threshold: {eval_stats.get('optimal_f1_threshold', 'N/A')}", cls="text-sm text-slate-300"),
            P(eval_stats.get("statistical_note", ""), cls="text-xs text-slate-400 mt-2"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )
    else:
        eval_section = Div(
            H3("Evaluation", cls="text-lg font-semibold text-white mb-3"),
            P("No evaluation data. Run: python scripts/evaluate_golden_set.py", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )

    # Recent actions
    if recent_actions:
        action_rows = [
            Div(
                Span(a.get("action", "?"), cls="text-xs font-mono bg-slate-700 px-2 py-0.5 rounded text-slate-300"),
                Span(a.get("timestamp", "")[:19], cls="text-xs text-slate-500 ml-2"),
                Span(a.get("detail", ""), cls="text-xs text-slate-400 ml-2"),
                cls="flex items-center gap-1",
            )
            for a in recent_actions
        ]
        actions_section = Div(
            H3("Recent Actions", cls="text-lg font-semibold text-white mb-3"),
            Div(*action_rows, cls="space-y-1"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )
    else:
        actions_section = Div(
            H3("Recent Actions", cls="text-lg font-semibold text-white mb-3"),
            P("No recent actions logged.", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6",
        )

    return Title(f"ML Dashboard — {community_name}"), Div(
        _admin_nav_bar("ml-dashboard", request=request),
        Div(H1("ML Evaluation Dashboard", cls="text-2xl font-bold text-white"), cls="mb-6"),
        stat_cards,
        gs_section,
        diversity_section,
        threshold_section,
        eval_section,
        actions_section,
        cls="max-w-5xl mx-auto p-6",
    )


def _stat_card(label: str, value: str, color: str) -> Div:
    """Small stat card for the ML dashboard."""
    color_map = {
        "emerald": "border-emerald-500 text-emerald-400",
        "amber": "border-amber-500 text-amber-400",
        "blue": "border-indigo-500 text-indigo-400",
        "red": "border-red-500 text-red-400",
        "slate": "border-slate-500 text-slate-300",
        "indigo": "border-indigo-500 text-indigo-400",
        "purple": "border-purple-500 text-purple-400",
        "green": "border-green-500 text-green-400",
        "orange": "border-orange-500 text-orange-400",
    }
    cls = color_map.get(color, "border-slate-500 text-slate-300")
    return Div(
        Div(value, cls=f"text-2xl font-bold {cls.split()[-1]}"),
        Div(label, cls="text-xs text-slate-400 mt-1"),
        cls=f"bg-slate-800 rounded-lg p-4 border-l-4 {cls.split()[0]}",
    )


def _threshold_row(label: str, value: float, precision: str, recall: str, color: str) -> Div:
    """Single threshold row in the dashboard."""
    return Div(
        Span(label, cls=f"text-sm font-medium text-{color}-400 w-24"),
        Span(f"< {value}", cls="text-sm font-mono text-white w-16"),
        Span(f"Precision: {precision}", cls="text-xs text-slate-400 w-28"),
        Span(f"Recall: {recall}", cls="text-xs text-slate-400"),
        cls="flex items-center gap-4",
    )


def _load_golden_set_stats() -> dict:
    """Load golden set stats from data file."""
    gs_path = _main_mod.data_path / "golden_set.json"
    if not gs_path.exists():
        return {}
    try:
        import json as _json

        with open(gs_path) as f:
            gs = _json.load(f)
        return gs.get("stats", {})
    except Exception:
        return {}


def _load_evaluation_stats() -> dict:
    """Load the most recent evaluation results."""
    # Find the most recent evaluation file
    eval_files = sorted(_main_mod.data_path.glob("golden_set_evaluation_*.json"), reverse=True)
    if not eval_files:
        return {}
    try:
        import json as _json

        with open(eval_files[0]) as f:
            return _json.load(f)
    except Exception:
        return {}


def _load_recent_actions(limit: int = 10) -> list:
    """Load recent user actions from the event log."""
    log_path = _main_mod.data_path / "event_log.jsonl"
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text().strip().split("\n")
        recent = lines[-limit:] if len(lines) > limit else lines
        recent.reverse()  # Most recent first
        import json as _json

        actions = []
        for line in recent:
            if not line.strip():
                continue
            try:
                event = _json.load(io.StringIO(line))
                actions.append(
                    {
                        "action": event.get("event_type", event.get("action", "?")),
                        "timestamp": event.get("timestamp", ""),
                        "detail": event.get("identity_id", event.get("target_id", ""))[:12],
                    }
                )
            except Exception:
                continue
        return actions
    except Exception:
        return []


# =============================================================================
# ANNOTATION SYSTEM (contributor submissions + admin review)
# =============================================================================

# Annotation data stored in data/annotations.json


def _admin_nav_bar(active: str = "", request=None) -> Div:
    """Consistent navigation bar for admin sub-pages.

    Shows links to all admin areas + back to dashboard.
    `active` should be one of: approvals, proposals, gedcom, uploads, audit, ml-dashboard
    """
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    links = [
        ("Uploads", "/admin/pending", "uploads"),
        ("Approvals", "/admin/approvals", "approvals"),
        ("Proposals", "/admin/proposals", "proposals"),
        ("Birth Years", "/admin/review/birth-years", "birth-year-review"),
        ("GEDCOM", "/admin/gedcom", "gedcom"),
        ("Audit Log", "/admin/audit", "audit"),
        ("ML Dashboard", "/admin/ml-dashboard", "ml-dashboard"),
        ("Event Groups", "/admin/event-groups", "event-groups"),
    ]
    nav_items = []
    for label, href, key in links:
        is_active = key == active
        cls = "px-3 py-1.5 text-sm rounded-lg transition-colors " + (
            "bg-indigo-600 text-white" if is_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"
        )
        nav_items.append(A(label, href=f"{nav_prefix}{href}", cls=cls))
    nav_items.append(
        A(
            "Dashboard",
            href=f"{nav_prefix}/?section=to_review",
            cls="px-3 py-1.5 text-sm text-indigo-400 hover:text-indigo-300 ml-auto",
        ),
    )
    return Div(
        *nav_items,
        cls="flex items-center gap-2 mb-6 pb-4 border-b border-slate-700/50 overflow-x-auto whitespace-nowrap scrollbar-hide shrink-0",
        data_testid="admin-nav-bar",
    )


@rt("/admin/approvals")
def get(request, sess=None):
    """Admin page for reviewing pending annotations."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"

    annotations = _main_mod._load_annotations()
    pending = [a for a in annotations["annotations"].values() if a.get("status") in ("pending", "pending_unverified")]
    skipped = [a for a in annotations["annotations"].values() if a.get("status") == "skipped"]
    # Sort: authenticated ("pending") before guest ("pending_unverified"), newest first within each group
    pending.sort(key=lambda a: a.get("submitted_at", ""), reverse=True)
    pending.sort(key=lambda a: 0 if a.get("status") == "pending" else 1)
    # Append skipped at the end so they appear below pending
    pending = pending + sorted(skipped, key=lambda a: a.get("submitted_at", ""), reverse=True)

    rows = []
    crop_files = _main_mod.get_crop_files()
    registry = _main_mod.load_registry()
    for a in pending:
        ann_id = a["annotation_id"]
        is_guest = a.get("submitted_by") == "anonymous"
        guest_badge = (
            Span("Guest", cls="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full ml-2")
            if is_guest
            else None
        )

        # Merge suggestions get special rendering with face thumbnails
        if a["type"] == "merge_suggestion":
            try:
                merge_data = json.loads(a["value"])
                t_id = merge_data.get("target_id", a["target_id"])
                s_id = merge_data.get("source_id", "")
                t_identity = registry.get_identity(t_id)
                s_identity = registry.get_identity(s_id)
                t_name = ensure_utf8_display(t_identity.get("name", "")) or f"Identity {t_id[:8]}"
                s_name = ensure_utf8_display(s_identity.get("name", "")) or f"Identity {s_id[:8]}"
                # Get face thumbnails
                t_faces = t_identity.get("anchor_ids", []) + t_identity.get("candidate_ids", [])
                s_faces = s_identity.get("anchor_ids", []) + s_identity.get("candidate_ids", [])
                t_thumb = None
                s_thumb = None
                for fid in t_faces:
                    url = _main_mod.resolve_face_image_url(fid, crop_files)
                    if url:
                        t_thumb = Img(src=url, alt=t_name, cls="w-16 h-16 object-cover rounded border border-slate-600")
                        break
                for fid in s_faces:
                    url = _main_mod.resolve_face_image_url(fid, crop_files)
                    if url:
                        s_thumb = Img(src=url, alt=s_name, cls="w-16 h-16 object-cover rounded border border-slate-600")
                        break
                if not t_thumb:
                    t_thumb = Div(cls="w-16 h-16 bg-slate-600 rounded")
                if not s_thumb:
                    s_thumb = Div(cls="w-16 h-16 bg-slate-600 rounded")

                rows.append(
                    Div(
                        Div(
                            Span("Merge Suggestion", cls="text-sm font-bold text-purple-400"),
                            Span(f"by {a['submitted_by']}", cls="text-xs text-slate-400 ml-2"),
                            Span(
                                _format_submitted_at(a.get("submitted_at", "")),
                                cls="text-xs text-slate-500 ml-2",
                            )
                            if a.get("submitted_at")
                            else None,
                            guest_badge,
                            cls="flex items-center mb-3",
                        ),
                        # Side-by-side face comparison
                        Div(
                            Div(
                                t_thumb,
                                P(t_name, cls="text-xs text-slate-300 mt-1 text-center truncate w-16"),
                                cls="flex flex-col items-center",
                            ),
                            Span("→", cls="text-slate-500 text-xl font-bold mx-4 self-center"),
                            Div(
                                s_thumb,
                                P(s_name, cls="text-xs text-slate-300 mt-1 text-center truncate w-16"),
                                cls="flex flex-col items-center",
                            ),
                            cls="flex items-start justify-center mb-3",
                        ),
                        P(f"Confidence: {a['confidence']}", cls="text-xs text-slate-500"),
                        P(f"Reason: {a.get('reason', 'none')}", cls="text-xs text-slate-500")
                        if a.get("reason")
                        else None,
                        Div(
                            Button(
                                "Execute Merge",
                                hx_post=f"/admin/approvals/{ann_id}/approve",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
                                cls="px-3 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-500",
                            ),
                            Button(
                                "Compare",
                                hx_get=f"/api/identity/{t_id}/compare/{s_id}",
                                hx_target="#compare-modal-content",
                                hx_swap="innerHTML",
                                cls="px-3 py-1 text-sm border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
                                **{"_": "on click remove .hidden from #compare-modal"},
                                type="button",
                            ),
                            Button(
                                "Skip",
                                hx_post=f"/admin/approvals/{ann_id}/reject",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
                                cls="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-500",
                            ),
                            cls="flex gap-2 mt-3",
                        ),
                        cls="bg-slate-800 rounded-lg p-4 border border-purple-500/30",
                        id=f"annotation-{ann_id}",
                    )
                )
                continue
            except (json.JSONDecodeError, KeyError):
                pass  # Fall through to generic rendering

        # Build face thumbnail for identity-targeted annotations
        face_thumb = None
        photo_thumb = None
        target_name = f"{a['target_type']} {a['target_id'][:12]}..."
        if a["target_type"] == "identity":
            try:
                identity = registry.get_identity(a["target_id"])
            except KeyError:
                identity = None
            if identity:
                target_name = ensure_utf8_display(identity.get("name", "")) or f"Identity {a['target_id'][:8]}"
                faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
                for fid in faces:
                    url = _main_mod.resolve_face_image_url(fid, crop_files)
                    if url:
                        face_thumb = Img(
                            src=url, alt=target_name, cls="w-16 h-16 object-cover rounded border border-slate-600"
                        )
                        # Get photo thumbnail for context
                        photo_id = _main_mod.get_photo_id_for_face(fid)
                        if photo_id:
                            photo = _main_mod._photo_cache.get(photo_id, {}) if _main_mod._photo_cache else {}
                            if photo.get("path"):
                                photo_thumb = Img(
                                    src=storage.get_photo_url(photo["path"]),
                                    alt="Photo context",
                                    cls="w-12 h-12 object-cover rounded border border-slate-700 opacity-80",
                                )
                        break

        rows.append(
            Div(
                Div(
                    # Thumbnails on the left
                    Div(
                        face_thumb
                        or Div(
                            cls="w-16 h-16 bg-slate-700 rounded flex items-center justify-center text-slate-500 text-2xl"
                        ),
                        photo_thumb,
                        cls="flex gap-2 items-start flex-shrink-0",
                    )
                    if a["target_type"] == "identity"
                    else None,
                    # Details on the right
                    Div(
                        Div(
                            Span(a["type"].replace("_", " ").title(), cls="text-sm font-bold text-white"),
                            guest_badge,
                            cls="flex items-center",
                        ),
                        P(target_name, cls="text-xs text-slate-400") if a["target_type"] == "identity" else None,
                        P(f'"{a["value"]}"', cls="text-sm text-slate-300 mt-1"),
                        P(
                            f"By: {a['submitted_by']}"
                            + (
                                f", confirmed by {len(a.get('confirmations', []))} other{'s' if len(a.get('confirmations', [])) != 1 else ''}"
                                if a.get("confirmations")
                                else ""
                            )
                            + (
                                f" · {_format_submitted_at(a.get('submitted_at', ''))}" if a.get("submitted_at") else ""
                            ),
                            cls="text-xs text-slate-500",
                        ),
                        P(f"Reason: {a.get('reason', 'none')}", cls="text-xs text-slate-500")
                        if a.get("reason")
                        else None,
                        # Auto-confirm checkbox (Session 107b Fix 2)
                        Div(
                            Input(
                                type="checkbox",
                                name=f"auto_confirm_{ann_id}",
                                id=f"auto-confirm-{ann_id}",
                                checked=True,
                                cls="mr-2 accent-emerald-500",
                            ),
                            Label(
                                "Also confirm this person",
                                **{"for": f"auto-confirm-{ann_id}"},
                                cls="text-xs text-slate-400 cursor-pointer",
                            ),
                            cls="flex items-center mt-2",
                        )
                        if a["type"] == "name_suggestion"
                        else None,
                        Div(
                            Button(
                                "Approve",
                                hx_post=f"/admin/approvals/{ann_id}/approve",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
                                hx_include=f"#auto-confirm-{ann_id}",
                                cls="px-3 py-1 text-sm bg-emerald-600 text-white rounded hover:bg-emerald-500",
                            ),
                            Button(
                                "Skip",
                                hx_post=f"/admin/approvals/{ann_id}/skip",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
                                cls="px-3 py-1 text-sm bg-amber-600 text-white rounded hover:bg-amber-500",
                            ),
                            Button(
                                "Reject",
                                hx_post=f"/admin/approvals/{ann_id}/reject",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
                                cls="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-500",
                            ),
                            cls="flex gap-2 mt-3",
                        ),
                        cls="flex-1",
                    ),
                    cls="flex gap-4",
                ),
                cls="bg-slate-800 rounded-lg p-4 border border-slate-700",
                id=f"annotation-{ann_id}",
                data_annotation_id=ann_id,
            )
        )

    if not rows:
        rows = [Div(P("No pending annotations to review.", cls="text-slate-400"), cls="text-center py-12")]

    # Bulk approve controls
    bulk_controls = (
        Div(
            Button(
                "Approve All Pending",
                hx_post="/admin/approvals/batch-approve",
                hx_target="#annotations-list",
                hx_swap="innerHTML",
                hx_confirm=f"Approve all {len([a for a in pending if a.get('status') in ('pending', 'pending_unverified')])} pending annotations?",
                cls="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors",
            ),
            cls="mb-4",
        )
        if pending
        else None
    )

    # FB-072: Recently approved annotations history
    approved = [
        a for a in annotations["annotations"].values() if a.get("status") == "approved" and a.get("reviewed_at")
    ]
    approved.sort(key=lambda a: a.get("reviewed_at", ""), reverse=True)
    approved = approved[:20]  # Show last 20

    history_rows = []
    for ann in approved:
        ann_type = ann.get("type", "unknown")
        value = ann.get("value", "")
        reviewed_at = ann.get("reviewed_at", "")[:16].replace("T", " ")
        reviewed_by = ann.get("reviewed_by", "admin")
        identity_id = ann.get("identity_id", "")
        submitted_by = ann.get("user_email", ann.get("submitted_by", "anonymous"))

        # Build display
        if ann_type == "name_suggestion":
            desc = f'Named "{value}"'
        elif ann_type == "merge_suggestion":
            desc = "Merge suggestion"
        else:
            desc = f"{ann_type}: {value[:40]}"

        nav_prefix = _main_mod.community_url_prefix(community.get("slug", "") if community else "")
        history_rows.append(
            Div(
                Div(
                    Span(desc, cls="text-sm text-white font-medium"),
                    Span(f" by {submitted_by}", cls="text-xs text-slate-500 ml-2"),
                    cls="flex-1",
                ),
                Div(
                    Span(reviewed_at, cls="text-xs text-slate-500"),
                    A(
                        "View",
                        href=f"{nav_prefix}/person/{identity_id}" if identity_id else "#",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 ml-3",
                    )
                    if identity_id
                    else "",
                    cls="flex items-center gap-1",
                ),
                cls="flex items-center justify-between p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
            )
        )

    history_section = (
        Div(
            H2("Recently Approved", cls="text-lg font-bold text-white mt-8 mb-4"),
            Div(f"{len(approved)} recent approvals", cls="text-sm text-slate-400 mb-3"),
            Div(*history_rows, cls="space-y-2"),
            cls="border-t border-slate-700 pt-4 mt-8",
        )
        if history_rows
        else ""
    )

    return Title(f"Annotation Approvals — {community_name}"), Div(
        _admin_nav_bar("approvals", request=request),
        Div(H1("Pending Approvals", cls="text-2xl font-bold text-white"), cls="mb-6"),
        Div(f"{len(pending)} pending annotations", cls="text-sm text-slate-400 mb-4"),
        bulk_controls if bulk_controls else "",
        Div(*rows, cls="space-y-3", id="annotations-list"),
        history_section,
        cls="max-w-3xl mx-auto p-6",
    )


@rt("/admin/approvals/batch-approve")
def post(sess=None):
    """Bulk approve all pending annotations."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from datetime import datetime, timezone

    user = get_current_user(sess)
    annotations = _main_mod._load_annotations()
    approved_count = 0
    results = []

    for ann_id, ann in list(annotations["annotations"].items()):
        if ann.get("status") not in ("pending", "pending_unverified"):
            continue

        ann["status"] = "approved"
        ann["reviewed_by"] = user.email if user else "admin"
        ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()

        # Apply the annotation to the target
        try:
            if ann["type"] == "name_suggestion":
                registry = _main_mod.load_registry()
                identity = registry.get_identity(ann["target_id"])
                if identity and identity.get("state") != "CONFIRMED":
                    registry.rename_identity(ann["target_id"], ann["value"])
                    registry.save(_main_mod.data_path / "identities.json")
                    _main_mod._invalidate_all_caches()
        except Exception as e:
            logger.warning(f"Failed to apply annotation {ann_id}: {e}")

        # Notify the contributor (BROKEN-2 fix)
        if ann.get("submitted_by") and ann["submitted_by"] not in ("anonymous", "admin"):
            try:
                from app.notification_routes import create_annotation_approved_notification

                create_annotation_approved_notification(
                    identity_id=ann.get("target_id", ""),
                    identity_name=ann.get("value", "Unknown"),
                    annotator_name=ann["submitted_by"].split("@")[0],
                    user_email=ann["submitted_by"],
                )
            except Exception:
                pass  # Don't block batch on notification failure

        approved_count += 1
        results.append(
            Div(
                Span("Approved", cls="text-sm font-bold text-emerald-400"),
                Span(f" — {ann.get('value', '')} for {ann.get('target_id', '')[:8]}", cls="text-sm text-slate-400"),
                cls="bg-emerald-900/20 rounded-lg p-3 border border-emerald-700",
                id=f"annotation-{ann_id}",
            )
        )

    _main_mod._save_annotations(annotations)
    _main_mod.log_user_action("BATCH_APPROVE_ANNOTATIONS", count=approved_count, admin=user.email if user else "admin")

    return Div(
        Div(f"Approved {approved_count} annotations", cls="text-emerald-400 font-bold mb-3"),
        *results,
        cls="space-y-2",
    )


@rt("/admin/approvals/{ann_id}/approve")
async def post(ann_id: str, request=None, sess=None, **kwargs):
    """Approve an annotation. Updates target record. Optional auto-confirm."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)

    # Parse form data to check for auto-confirm checkbox (FB-071)
    _form_data = {}
    if request is not None:
        try:
            _form_data = dict(await request.form())
        except Exception:
            pass
    annotations = _main_mod._load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(
            to_xml(_main_mod.toast("Annotation not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    if ann.get("status") == "approved":
        return Div(
            Div(
                Span("Already approved", cls="text-sm font-bold text-emerald-400"),
                Span(
                    f" — {ann['value']} (suggested by {ann['submitted_by']})",
                    cls="text-sm text-slate-400",
                ),
                cls="flex-1",
            ),
            Button(
                "Undo",
                hx_post=f"/admin/approvals/{ann_id}/undo",
                hx_target=f"#annotation-{ann_id}",
                hx_swap="outerHTML",
                cls="px-3 py-1 text-xs bg-slate-600 text-white rounded hover:bg-slate-500 ml-2 flex-shrink-0",
            ),
            cls="bg-emerald-900/20 rounded-lg p-4 border border-emerald-700 flex items-center",
            id=f"annotation-{ann_id}",
        )

    from datetime import datetime, timezone

    ann["status"] = "approved"
    ann["reviewed_by"] = user.email if user else "admin"
    ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _main_mod.log_user_action(
        "APPROVE_ANNOTATION",
        annotation_id=ann_id,
        type=ann.get("type", "unknown"),
        target_id=ann.get("target_id", ""),
        submitted_by=ann.get("submitted_by", ""),
        admin=user.email if user else "admin",
    )

    # Apply the annotation to the target
    if ann["type"] == "name_suggestion" and ann["target_type"] == "identity":
        registry = _main_mod.load_registry()
        identity = registry._identities.get(ann["target_id"])
        if identity:
            registry.rename_identity(
                ann["target_id"],
                ann["value"],
                user_source="approved_name_suggestion",
                annotation_id=ann_id,
            )
            # Auto-confirm if checkbox was checked (FB-071 / Session 107b Fix 2)
            auto_confirm_key = f"auto_confirm_{ann_id}"
            auto_confirm = _form_data.get(auto_confirm_key, "") or kwargs.get(auto_confirm_key, "")
            if auto_confirm == "on" and identity.get("state") != "CONFIRMED":
                registry.confirm_identity(ann["target_id"], user_source="auto_confirm_on_approve")
                _main_mod.log_user_action(
                    "AUTO_CONFIRM_ON_APPROVE",
                    identity_id=ann["target_id"],
                    annotation_id=ann_id,
                    admin=user.email if user else "admin",
                )
            _main_mod.save_registry(registry, changed_ids={ann["target_id"]})
    elif ann["type"] == "merge_suggestion":
        # Execute the merge
        try:
            merge_data = json.loads(ann["value"])
            t_id = merge_data.get("target_id", ann["target_id"])
            s_id = merge_data.get("source_id", "")
            registry = _main_mod.load_registry()
            photo_registry = _main_mod.load_photo_registry()
            result = registry.merge_identities(
                source_id=s_id,
                target_id=t_id,
                user_source="approved_suggestion",
                photo_registry=photo_registry,
            )
            if result["success"]:
                _main_mod.save_registry(registry, changed_ids={s_id, t_id})
                actual_target = result.get("actual_target_id") or t_id
                _main_mod._merge_annotations(s_id, actual_target)
                _main_mod.log_user_action(
                    "APPROVE_MERGE_SUGGESTION",
                    target=t_id,
                    source=s_id,
                    suggested_by=ann["submitted_by"],
                    admin=user.email if user else "admin",
                )
            else:
                _main_mod._save_annotations(annotations)
                return Div(
                    Span("MERGE FAILED", cls="text-sm font-bold text-red-400"),
                    Span(f" — {result['reason']}", cls="text-sm text-slate-400"),
                    cls="bg-red-900/20 rounded-lg p-4 border border-red-700",
                    id=f"annotation-{ann_id}",
                )
        except (json.JSONDecodeError, KeyError) as e:
            _main_mod._save_annotations(annotations)
            return Div(
                Span("ERROR", cls="text-sm font-bold text-red-400"),
                Span(f" — Invalid merge data: {e}", cls="text-sm text-slate-400"),
                cls="bg-red-900/20 rounded-lg p-4 border border-red-700",
                id=f"annotation-{ann_id}",
            )

    _main_mod._save_annotations(annotations)

    merge_label = ""
    if ann["type"] == "merge_suggestion":
        try:
            merge_data = json.loads(ann["value"])
            merge_label = f"Merged {merge_data.get('source_id', '')[:8]} into {merge_data.get('target_id', '')[:8]}"
        except (json.JSONDecodeError, KeyError):
            merge_label = "Merge executed"

    _log_audit("approved", ann_id, user.email if user else "admin", merge_label or ann["value"])

    # Notify the contributor that their suggestion was approved (BROKEN-2 fix)
    if ann.get("submitted_by") and ann["submitted_by"] not in ("anonymous", "admin"):
        try:
            from app.notification_routes import create_annotation_approved_notification

            identity_name = ann.get("value", "Unknown")
            create_annotation_approved_notification(
                identity_id=ann.get("target_id", ""),
                identity_name=identity_name,
                annotator_name=ann["submitted_by"].split("@")[0],
                user_email=ann["submitted_by"],
            )
        except Exception as e:
            logger.warning(f"Failed to send approval notification for {ann_id}: {e}")

    status_label = "Approved" if ann["type"] != "merge_suggestion" else "Merged"
    return Div(
        Div(
            Span(status_label, cls="text-sm font-bold text-emerald-400"),
            Span(
                f" — {merge_label or ann['value']} (suggested by {ann['submitted_by']})", cls="text-sm text-slate-400"
            ),
            cls="flex-1",
        ),
        Button(
            "Undo",
            hx_post=f"/admin/approvals/{ann_id}/undo",
            hx_target=f"#annotation-{ann_id}",
            hx_swap="outerHTML",
            cls="px-3 py-1 text-xs bg-slate-600 text-white rounded hover:bg-slate-500 ml-2 flex-shrink-0",
        ),
        cls="bg-emerald-900/20 rounded-lg p-4 border border-emerald-700 flex items-center",
        id=f"annotation-{ann_id}",
    )


def _load_activity_feed(limit: int = 50) -> list:
    """Load activity from user_actions.log and annotations."""
    activities = []

    # Load from user action log
    action_log = Path(__file__).resolve().parent.parent / "logs" / "user_actions.log"
    if action_log.exists():
        try:
            lines = action_log.read_text().strip().split("\n")
            for line in lines[-limit:]:
                parts = line.split(" | ", 2)
                if len(parts) >= 2:
                    timestamp = parts[0].strip()
                    action_type = parts[1].strip()
                    detail = parts[2].strip() if len(parts) > 2 else ""

                    # Skip internal actions
                    if action_type in ("SKIP",):
                        continue

                    desc_map = {
                        "MERGE": "Two identities were merged",
                        "CONFIRM": "An identity was confirmed",
                        "RENAME": "An identity was renamed",
                        "REJECT_IDENTITY": "A match was rejected",
                        "DETACH": "A face was detached",
                    }
                    description = desc_map.get(action_type, f"Action: {action_type}")
                    if "target_identity_id=" in detail:
                        # Extract a readable fragment
                        for kv in detail.split():
                            if kv.startswith("target_identity_id="):
                                description += f" ({kv.split('=')[1][:8]}...)"
                                break

                    activities.append(
                        {
                            "type": action_type,
                            "description": description,
                            "timestamp": timestamp,
                        }
                    )
        except Exception:
            pass

    # Load from approved annotations
    try:
        annotations = _main_mod._load_annotations()
        for ann in annotations.get("annotations", {}).values():
            if ann.get("status") == "approved":
                activities.append(
                    {
                        "type": "annotation_approved",
                        "description": f'Name suggestion approved: "{ann["value"]}"',
                        "timestamp": ann.get("reviewed_at", ann.get("submitted_at", "")),
                    }
                )
    except Exception:
        pass

    # Sort by timestamp, newest first
    activities.sort(key=lambda a: a.get("timestamp") or "", reverse=True)
    return activities[:limit]


@rt("/admin/approvals/{ann_id}/reject")
def post(ann_id: str, sess=None):
    """Reject an annotation. No data change."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    annotations = _main_mod._load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(
            to_xml(_main_mod.toast("Annotation not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    from datetime import datetime, timezone

    ann["status"] = "rejected"
    ann["reviewed_by"] = user.email if user else "admin"
    ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _main_mod._save_annotations(annotations)
    _main_mod.log_user_action(
        "REJECT_ANNOTATION",
        annotation_id=ann_id,
        type=ann.get("type", "unknown"),
        target_id=ann.get("target_id", ""),
        admin=user.email if user else "admin",
    )

    _log_audit("rejected", ann_id, user.email if user else "admin", ann["value"])

    return Div(
        Div(
            Span("REJECTED", cls="text-sm font-bold text-red-400"),
            Span(f' — "{ann["value"]}" by {ann["submitted_by"]}', cls="text-sm text-slate-400"),
            cls="flex-1",
        ),
        Button(
            "Undo",
            hx_post=f"/admin/approvals/{ann_id}/undo",
            hx_target=f"#annotation-{ann_id}",
            hx_swap="outerHTML",
            cls="px-3 py-1 text-xs bg-slate-600 text-white rounded hover:bg-slate-500 ml-2 flex-shrink-0",
        ),
        cls="bg-red-900/20 rounded-lg p-4 border border-red-700 flex items-center",
        id=f"annotation-{ann_id}",
    )


@rt("/admin/approvals/{ann_id}/skip")
def post(ann_id: str, sess=None):
    """Skip an annotation for later review."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    annotations = _main_mod._load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(
            to_xml(_main_mod.toast("Annotation not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    from datetime import datetime, timezone

    ann["status"] = "skipped"
    ann["reviewed_by"] = user.email if user else "admin"
    ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _main_mod._save_annotations(annotations)

    _log_audit("skipped", ann_id, user.email if user else "admin", ann["value"])

    return Div(
        Div(
            Span("SKIPPED", cls="text-sm font-bold text-amber-400"),
            Span(f' — "{ann["value"]}" by {ann["submitted_by"]}', cls="text-sm text-slate-400"),
            cls="flex-1",
        ),
        Button(
            "Undo",
            hx_post=f"/admin/approvals/{ann_id}/undo",
            hx_target=f"#annotation-{ann_id}",
            hx_swap="outerHTML",
            cls="px-3 py-1 text-xs bg-slate-600 text-white rounded hover:bg-slate-500 ml-2 flex-shrink-0",
        ),
        cls="bg-amber-900/20 rounded-lg p-4 border border-amber-700 flex items-center",
        id=f"annotation-{ann_id}",
    )


@rt("/admin/approvals/{ann_id}/undo")
def post(ann_id: str, sess=None):
    """Undo a previous approve/reject/skip — reverts annotation to pending."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    annotations = _main_mod._load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(
            to_xml(_main_mod.toast("Annotation not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    old_status = ann["status"]
    ann["status"] = "pending" if ann.get("submitted_by") != "anonymous" else "pending_unverified"
    ann["reviewed_by"] = None
    ann["reviewed_at"] = None
    _main_mod._save_annotations(annotations)

    _log_audit("undone", ann_id, user.email if user else "admin", f"Reverted from {old_status} to {ann['status']}")

    # Return the annotation back to its original pending card form
    # Redirect browser to refresh the approvals page
    return Response("", status_code=200, headers={"HX-Redirect": "/admin/approvals"})


def _format_submitted_at(submitted_at: str) -> str:
    """Format a submission timestamp as relative time string."""
    if not submitted_at:
        return ""
    try:
        from datetime import datetime, timezone

        ts_str = submitted_at.replace("Z", "+00:00")
        if "+" not in ts_str and "-" not in ts_str[10:]:
            ts_str += "+00:00"
        dt = datetime.fromisoformat(ts_str)
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return submitted_at[:16]


def _log_audit(action: str, annotation_id: str, admin: str, details: str = ""):
    """Append an entry to the audit log."""
    from datetime import datetime, timezone

    audit_path = _main_mod.data_path / "audit_log.json"

    audit = {"entries": []}
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            audit = {"entries": []}

    audit["entries"].append(
        {
            "action": action,
            "annotation_id": annotation_id,
            "admin": admin,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
    )

    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    # Dual-write to Supabase
    from app.supabase_data import sync_audit_log_entry

    sync_audit_log_entry(action, annotation_id, actor=admin, entry_data=audit["entries"][-1])


# =============================================================================
# ADMIN: ML BIRTH YEAR BULK REVIEW (Gatekeeper Pattern — AD-097)
# =============================================================================


@rt("/admin/review/birth-years")
def get(request, sess=None):
    """Admin bulk review page for ML birth year estimates."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    pending = _main_mod._get_pending_ml_birth_year_suggestions()
    crop_files = _main_mod.get_crop_files()
    registry = _main_mod.load_registry()

    rows = []
    for item in pending:
        iid = item["identity_id"]
        name = item["name"]
        est = item["birth_year_estimate"]
        conf = (item["birth_year_confidence"] or "low").capitalize()
        est_range = item.get("birth_year_range", [])
        range_str = f"{est_range[0]}\u2013{est_range[1]}" if len(est_range) == 2 else ""
        n_photos = item.get("n_with_age_data", 0)

        conf_cls = {
            "High": "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
            "Medium": "text-amber-400 bg-amber-500/10 border-amber-500/20",
            "Low": "text-slate-400 bg-slate-500/10 border-slate-500/20",
        }.get(conf, "text-slate-400 bg-slate-500/10 border-slate-500/20")

        # Get face crop
        try:
            identity = registry.get_identity(iid)
            all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            best_fid = _main_mod.get_best_face_id(all_faces)
            crop_url = _main_mod.resolve_face_image_url(best_fid, crop_files) if best_fid and crop_files else None
        except KeyError:
            crop_url = None

        # Evidence preview (top 3)
        evidence = item.get("evidence", [])[:3]
        evidence_items = []
        for ev in evidence:
            py = ev.get("photo_year", "?")
            age = ev.get("estimated_age", "?")
            evidence_items.append(Span(f"{py}: age ~{age}", cls="text-xs text-slate-500 block"))

        rows.append(
            Div(
                Div(
                    # Face crop
                    Img(
                        src=crop_url,
                        alt=name,
                        cls="w-14 h-14 rounded-lg object-cover border border-slate-700",
                        onerror="this.style.display='none'",
                    )
                    if crop_url
                    else Div(
                        Span("?", cls="text-xl text-slate-500"),
                        cls="w-14 h-14 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center",
                    ),
                    # Info
                    Div(
                        A(
                            name,
                            href=f"{nav_prefix}/person/{iid}",
                            cls="text-white text-sm font-medium hover:text-indigo-400",
                        ),
                        Div(
                            Span(f"Born c. {est}", cls="text-slate-300 text-sm"),
                            Span(f" ({range_str})" if range_str else "", cls="text-slate-500 text-xs"),
                            cls="mt-0.5",
                        ),
                        Div(
                            Span(conf, cls=f"text-xs px-2 py-0.5 rounded-full border {conf_cls} mr-2"),
                            Span(
                                f"{n_photos} photo{'s' if n_photos != 1 else ''} with age data",
                                cls="text-xs text-slate-500",
                            ),
                        ),
                        cls="ml-3 flex-1 min-w-0",
                    ),
                    cls="flex items-center",
                ),
                # Evidence preview (collapsible)
                Details(
                    Summary("Evidence", cls="text-xs text-indigo-400 cursor-pointer hover:text-indigo-300 mt-2"),
                    Div(*evidence_items, cls="mt-1 ml-2")
                    if evidence_items
                    else Span("No evidence", cls="text-xs text-slate-600"),
                    cls="mt-1",
                )
                if evidence
                else None,
                # Actions — single form so Accept always uses current input value (UX-092)
                Div(
                    Form(
                        Button(
                            "Accept",
                            type="submit",
                            cls="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded",
                        ),
                        Input(
                            type="number",
                            name="birth_year",
                            value=str(est),
                            cls="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white w-20",
                        ),
                        Input(type="hidden", name="source_detail", value="admin_bulk_review"),
                        Button(
                            "Save Edit",
                            type="submit",
                            cls="px-2 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded",
                        ),
                        hx_post=f"/api/ml-review/birth-year/{iid}/accept",
                        hx_target=f"#review-row-{iid}",
                        hx_swap="outerHTML",
                        cls="inline-flex items-center gap-2",
                    ),
                    Button(
                        "Reject",
                        type="button",
                        hx_post=f"/api/ml-review/birth-year/{iid}/reject",
                        hx_target=f"#review-row-{iid}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1 bg-red-600/80 hover:bg-red-500 text-white text-xs rounded",
                    ),
                    cls="flex items-center gap-2 mt-3",
                ),
                id=f"review-row-{iid}",
                cls="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 mb-3",
                data_testid="review-row",
            )
        )

    # Accept all high-confidence button
    high_count = sum(1 for p in pending if p["birth_year_confidence"] == "high")
    accept_all_btn = None
    if high_count > 0:
        accept_all_btn = Div(
            Button(
                f"Accept All High-Confidence ({high_count})",
                hx_post="/api/ml-review/birth-year/accept-all-high",
                hx_target="#review-list",
                hx_swap="innerHTML",
                hx_confirm=f"Accept {high_count} high-confidence birth year estimates?",
                cls="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg",
            ),
            cls="mb-4",
        )

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
    return (
        Title(f"ML Birth Year Review - {community_name} Admin"),
        page_style,
        Main(
            _admin_nav_bar("birth-year-review", request=request),
            Div(
                H1("ML Birth Year Estimates", cls="text-2xl font-serif font-bold text-white mb-2"),
                P(f"{len(pending)} pending review", cls="text-slate-400 text-sm mb-6", id="pending-count"),
                accept_all_btn,
                Div(*rows, id="review-list")
                if rows
                else P("All estimates have been reviewed.", cls="text-slate-500 text-center py-8"),
                cls="max-w-3xl mx-auto px-6 py-8",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/api/ml-review/birth-year/accept-all-high")
def post(sess=None):
    """Accept all high-confidence ML birth year estimates at once."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    pending = _main_mod._get_pending_ml_birth_year_suggestions()
    high_confidence = [p for p in pending if p["birth_year_confidence"] == "high"]

    registry = _main_mod.load_registry()
    decisions = dict(_main_mod._load_ml_review_decisions())
    accepted_count = 0

    for item in high_confidence:
        iid = item["identity_id"]
        by = item["birth_year_estimate"]

        try:
            identity = registry.get_identity(iid)
        except KeyError:
            continue

        # Write to canonical identity metadata
        registry.set_metadata(iid, {"birth_year": by}, user_source="admin_ml_bulk_review")

        # Record review decision
        decisions[iid] = {
            "action": "accepted",
            "birth_year": by,
            "original_ml_estimate": by,
            "source": "ml_accepted",
            "source_detail": "bulk_high_confidence_review",
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "decided_by": "admin",
        }

        # Write ground truth
        _main_mod._save_ground_truth_birth_year(
            identity_id=iid,
            identity=registry.get_identity(iid),
            birth_year=by,
            source="ml_accepted",
            source_detail="bulk_high_confidence_review",
            original_ml_estimate=by,
        )
        accepted_count += 1

    _main_mod.save_registry(registry, changed_ids={item["identity_id"] for item in high_confidence})
    _main_mod._save_ml_review_decisions(decisions)

    return Div(
        Div(
            Span(f"\u2705 Accepted {accepted_count} high-confidence estimates", cls="text-emerald-400 text-sm"),
            cls="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-4 text-center mb-4",
        ),
        A("Refresh page", href="/admin/review/birth-years", cls="text-indigo-400 hover:text-indigo-300 text-sm"),
        data_testid="bulk-accept-result",
    )


@rt("/admin/audit")
def get(request, sess=None):
    """Admin audit log — shows all annotation review actions."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"

    audit_path = _main_mod.data_path / "audit_log.json"
    entries = []
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            entries = audit.get("entries", [])
        except (json.JSONDecodeError, ValueError):
            pass

    # Most recent first
    entries = list(reversed(entries))

    rows = []
    for entry in entries[:100]:
        action_colors = {
            "approved": "text-emerald-400",
            "rejected": "text-red-400",
            "skipped": "text-amber-400",
            "undone": "text-slate-400",
        }
        color = action_colors.get(entry.get("action", ""), "text-slate-400")
        rows.append(
            Div(
                Span(entry.get("action", "unknown").upper(), cls=f"text-sm font-bold {color} w-24"),
                Span(entry.get("details", "")[:80], cls="text-sm text-slate-300 flex-1 truncate"),
                Span(entry.get("admin", ""), cls="text-xs text-slate-500 w-40 text-right"),
                Span(entry.get("timestamp", "")[:19].replace("T", " "), cls="text-xs text-slate-600 w-36 text-right"),
                cls="flex items-center gap-2 py-2 border-b border-slate-800",
            )
        )

    if not rows:
        rows = [P("No audit entries yet.", cls="text-slate-400 text-center py-12")]

    return Title(f"Audit Log — {community_name}"), Div(
        _admin_nav_bar("audit", request=request),
        Div(H1("Audit Log", cls="text-2xl font-bold text-white"), cls="mb-6"),
        P(f"{len(entries)} audit entries", cls="text-sm text-slate-400 mb-4"),
        Div(*rows, cls="space-y-0"),
        cls="max-w-4xl mx-auto p-6",
    )


# --- GEDCOM Import (Session 35) ---


@rt("/admin/gedcom")
def get(request, sess=None):
    """GEDCOM admin page — version management, upload, match review (AD-164)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"

    matches_data = _main_mod._load_gedcom_matches()
    matches = matches_data.get("matches", [])
    source_file = matches_data.get("source_file", "")

    pending = [m for m in matches if m.get("status") == "pending"]
    confirmed = [m for m in matches if m.get("status") == "confirmed"]
    rejected = [m for m in matches if m.get("status") == "rejected"]

    # Relationship graph stats
    rel_graph = _main_mod._load_relationship_graph()
    rel_count = len(rel_graph.get("relationships", []))

    # Co-occurrence graph stats
    cooccur_path = _main_mod.data_path / "co_occurrence_graph.json"
    cooccur_count = 0
    if cooccur_path.exists():
        try:
            cooccur = json.loads(cooccur_path.read_text(encoding="utf-8"))
            cooccur_count = len(cooccur.get("edges", []))
        except (json.JSONDecodeError, ValueError):
            pass

    # --- GEDCOM Version Info from Supabase (AD-164) ---
    versions = _main_mod._load_gedcom_versions()
    enrichment_pending_count = _main_mod._load_gedcom_enrichment_queue_count()
    current_version = versions[0] if versions else None

    # Version info panel
    if current_version:
        summary = current_version.get("summary", {}) or {}
        imported_at = (
            current_version.get("imported_at", "")[:19].replace("T", " ")
            if current_version.get("imported_at")
            else "Unknown"
        )
        version_info = Div(
            H2("Current GEDCOM Version", cls="text-lg font-semibold text-white mb-3"),
            Div(
                Div(
                    P(str(current_version.get("version_number", "?")), cls="text-3xl font-bold text-indigo-400"),
                    P("Version", cls="text-sm text-slate-400"),
                    cls="text-center",
                ),
                Div(
                    P(f"{current_version.get('individual_count', 0):,}", cls="text-3xl font-bold text-white"),
                    P("Individuals", cls="text-sm text-slate-400"),
                    cls="text-center",
                ),
                Div(
                    P(f"{current_version.get('family_count', 0):,}", cls="text-3xl font-bold text-white"),
                    P("Families", cls="text-sm text-slate-400"),
                    cls="text-center",
                ),
                Div(
                    P(
                        str(enrichment_pending_count),
                        cls=f"text-3xl font-bold {'text-amber-400' if enrichment_pending_count > 0 else 'text-emerald-400'}",
                    ),
                    P("Re-Enrichment Queue", cls="text-sm text-slate-400"),
                    cls="text-center",
                ),
                cls="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4",
            ),
            P(f"Imported: {imported_at}", cls="text-sm text-slate-500"),
            P(f"File: {current_version.get('source_file', '?')}", cls="text-sm text-slate-500"),
            P(f"Notes: {current_version.get('notes', 'None')}", cls="text-sm text-slate-500")
            if current_version.get("notes")
            else None,
            cls="bg-slate-800 rounded-lg p-5 border border-slate-700 mb-6",
            data_testid="gedcom-version-info",
        )
    else:
        version_info = Div(
            H2("GEDCOM Version", cls="text-lg font-semibold text-white mb-3"),
            P("No versions imported yet. Upload a GEDCOM file to get started.", cls="text-slate-400"),
            cls="bg-slate-800 rounded-lg p-5 border border-slate-700 mb-6",
            data_testid="gedcom-version-info",
        )

    # Stats section (match-related)
    stats_cards = Div(
        Div(
            P(str(len(matches)), cls="text-3xl font-bold text-white"),
            P("Total Matches", cls="text-sm text-slate-400"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center",
        ),
        Div(
            P(str(len(pending)), cls="text-3xl font-bold text-amber-400"),
            P("Pending Review", cls="text-sm text-slate-400"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center",
        ),
        Div(
            P(str(len(confirmed)), cls="text-3xl font-bold text-emerald-400"),
            P("Confirmed", cls="text-sm text-slate-400"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center",
        ),
        Div(
            P(str(rel_count), cls="text-3xl font-bold text-indigo-400"),
            P("Relationships", cls="text-sm text-slate-400"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center",
        ),
        Div(
            P(str(cooccur_count), cls="text-3xl font-bold text-purple-400"),
            P("Co-occurrences", cls="text-sm text-slate-400"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700 text-center",
        ),
        cls="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6",
    )

    # Versioned upload section (AD-164)
    upload_section = Div(
        H2("Upload GEDCOM File", cls="text-lg font-semibold text-white mb-3"),
        P(
            "Upload a .ged file exported from Ancestry, MyHeritage, FamilySearch, or other genealogy software. "
            "The file will be parsed and compared against the current database before any changes are applied.",
            cls="text-sm text-slate-400 mb-4",
        ),
        Form(
            Input(
                type="file",
                name="gedcom_file",
                accept=".ged,.gedcom",
                cls="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-500 file:text-white hover:file:bg-indigo-400",
            ),
            Input(
                type="text",
                name="notes",
                placeholder="Notes (e.g., 'Added Marcus branch')",
                cls="block w-full mt-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-400",
            ),
            Button(
                "Upload & Preview Changes",
                type="submit",
                cls="mt-3 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium",
            ),
            hx_post="/admin/gedcom/upload",
            hx_target="#gedcom-results",
            hx_encoding="multipart/form-data",
            hx_indicator="#upload-spinner",
            cls="space-y-2",
        ),
        Span("Parsing and comparing...", id="upload-spinner", cls="htmx-indicator text-sm text-slate-400 ml-2"),
        Div(id="gedcom-results", cls="mt-4"),
        cls="bg-slate-800 rounded-lg p-5 border border-slate-700 mb-6",
    )

    # Version history table (AD-164)
    version_history_section = None
    if versions:
        version_rows = []
        for v in versions:
            v_summary = v.get("summary", {}) or {}
            v_date = v.get("imported_at", "")[:10] if v.get("imported_at") else "?"
            added = v_summary.get("added", 0)
            modified = v_summary.get("modified", 0)
            removed = v_summary.get("removed", 0)
            unchanged = v_summary.get("unchanged", 0)

            change_badges = []
            if added:
                change_badges.append(
                    Span(f"+{added}", cls="text-xs px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400")
                )
            if modified:
                change_badges.append(
                    Span(f"~{modified}", cls="text-xs px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400")
                )
            if removed:
                change_badges.append(
                    Span(f"-{removed}", cls="text-xs px-1.5 py-0.5 rounded bg-red-900/40 text-red-400")
                )
            if unchanged:
                change_badges.append(
                    Span(f"={unchanged}", cls="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-400")
                )

            version_rows.append(
                Div(
                    Div(
                        Span(f"v{v.get('version_number', '?')}", cls="text-white font-bold text-sm mr-3"),
                        Span(v.get("source_file", "?"), cls="text-slate-300 text-sm"),
                        cls="flex items-center",
                    ),
                    Div(*change_badges, cls="flex items-center gap-1.5 mt-1"),
                    Div(
                        Span(v_date, cls="text-xs text-slate-500"),
                        Span(
                            f" — {v.get('individual_count', 0):,} individuals, {v.get('family_count', 0):,} families",
                            cls="text-xs text-slate-500",
                        ),
                        Span(f" — {v.get('notes', '')}", cls="text-xs text-slate-400 italic")
                        if v.get("notes")
                        else None,
                        cls="mt-1",
                    ),
                    cls="py-3 border-b border-slate-700/50 last:border-0",
                )
            )

        version_history_section = Div(
            H2("Version History", cls="text-lg font-semibold text-white mb-3"),
            *version_rows,
            cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 mb-6",
            data_testid="gedcom-version-history",
        )

    # Pending matches section
    match_rows = []
    for m in sorted(pending, key=lambda x: x.get("match_score", 0), reverse=True):
        score_pct = int(m.get("match_score", 0) * 100)
        score_color = (
            "text-emerald-400" if score_pct >= 90 else "text-amber-400" if score_pct >= 80 else "text-slate-400"
        )

        ged_birth = f"b. {m.get('gedcom_birth_year', '?')}" if m.get("gedcom_birth_year") else ""
        ged_death = f"d. {m.get('gedcom_death_year', '?')}" if m.get("gedcom_death_year") else ""
        ged_place = m.get("gedcom_birth_place", "")

        match_rows.append(
            Div(
                # Left: GEDCOM person
                Div(
                    P(m.get("gedcom_name", "?"), cls="text-white font-medium"),
                    P(f"{ged_birth} {ged_death}".strip(), cls="text-sm text-slate-400")
                    if ged_birth or ged_death
                    else None,
                    P(ged_place, cls="text-xs text-slate-500") if ged_place else None,
                    cls="flex-1",
                ),
                # Arrow
                Span("→", cls="text-slate-500 text-xl px-3 self-center"),
                # Right: Archive identity
                Div(
                    P(m.get("identity_name", "?"), cls="text-white font-medium"),
                    P(m.get("match_reason", ""), cls="text-xs text-slate-500 mt-1"),
                    cls="flex-1",
                ),
                # Score + actions
                Div(
                    Span(f"{score_pct}%", cls=f"text-lg font-bold {score_color} mr-4"),
                    Button(
                        "Confirm",
                        cls="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg mr-1",
                        hx_post=f"/admin/gedcom/confirm/{m.get('gedcom_xref', '')}",
                        hx_target="closest div.gedcom-match-row",
                        hx_swap="outerHTML",
                    ),
                    Button(
                        "Reject",
                        cls="px-3 py-1 bg-red-600/50 hover:bg-red-600 text-white text-sm rounded-lg mr-1",
                        hx_post=f"/admin/gedcom/reject/{m.get('gedcom_xref', '')}",
                        hx_target="closest div.gedcom-match-row",
                        hx_swap="outerHTML",
                    ),
                    Button(
                        "Skip",
                        cls="px-3 py-1 bg-slate-600 hover:bg-slate-500 text-white text-sm rounded-lg",
                        hx_post=f"/admin/gedcom/skip/{m.get('gedcom_xref', '')}",
                        hx_target="closest div.gedcom-match-row",
                        hx_swap="outerHTML",
                    ),
                    cls="flex items-center flex-shrink-0",
                ),
                cls="gedcom-match-row flex items-start gap-2 bg-slate-800 rounded-lg p-4 border border-slate-700",
            )
        )

    matches_section = Div(
        Div(
            H2("Pending Matches", cls="text-lg font-semibold text-white"),
            Span(f"{len(pending)} pending", cls="text-sm text-amber-400 ml-2"),
            cls="flex items-center gap-2 mb-4",
        ),
        Div(*match_rows, cls="space-y-3")
        if match_rows
        else P("No pending matches. Upload a GEDCOM file to start.", cls="text-slate-400 text-center py-8"),
        cls="mb-6",
        id="gedcom-matches-list",
    )

    # Confirmed matches summary
    confirmed_section = None
    if confirmed:
        confirmed_rows = []
        for m in confirmed:
            confirmed_rows.append(
                Div(
                    Span(m.get("gedcom_name", "?"), cls="text-emerald-400 font-medium"),
                    Span("→", cls="text-slate-500 mx-2"),
                    Span(m.get("identity_name", "?"), cls="text-white"),
                    cls="text-sm py-1",
                )
            )
        confirmed_section = Div(
            H2(f"Confirmed ({len(confirmed)})", cls="text-lg font-semibold text-emerald-400 mb-3"),
            *confirmed_rows,
            cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 mb-6",
        )

    # Legacy import history section (from relationship graph)
    import_history_section = None
    imports = rel_graph.get("gedcom_imports", [])
    if imports:
        import_rows = []
        for imp in imports:
            import_rows.append(
                Div(
                    Span(imp.get("filename", "?"), cls="text-white font-medium text-sm"),
                    Span(
                        f" — {imp.get('individuals_count', 0)} individuals, {imp.get('families_count', 0)} families",
                        cls="text-slate-400 text-sm",
                    ),
                    Span(
                        f" — {imp.get('matches_confirmed', 0)} matched, {imp.get('relationships_added', 0)} relationships",
                        cls="text-emerald-400 text-sm",
                    ),
                    P(imp.get("imported_at", "")[:10] if imp.get("imported_at") else "", cls="text-xs text-slate-500"),
                    cls="py-2 border-b border-slate-700/50 last:border-0",
                )
            )
        import_history_section = Div(
            H2("Import History", cls="text-lg font-semibold text-white mb-3"),
            *import_rows,
            cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 mb-6",
            data_testid="import-history",
        )

    # Enrichment status for confirmed matches
    enrichment_section = None
    if confirmed:
        registry = _main_mod.load_registry()
        enrichment_rows = []
        for m in confirmed:
            identity_id = m.get("identity_id", "")
            badges = []
            try:
                ident = registry.get_identity(identity_id)
                if ident:
                    meta = ident.get("metadata", {})
                    if meta.get("birth_date_full"):
                        badges.append(
                            Span("birth", cls="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400")
                        )
                    if meta.get("death_date_full"):
                        badges.append(
                            Span("death", cls="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400")
                        )
                    if meta.get("gender"):
                        badges.append(
                            Span("gender", cls="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400")
                        )
                    if meta.get("birth_place"):
                        badges.append(
                            Span("place", cls="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400")
                        )
                    if not badges:
                        badges.append(
                            Span("no metadata", cls="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500")
                        )
            except (KeyError, TypeError):
                badges.append(Span("error", cls="text-[10px] px-1.5 py-0.5 rounded bg-red-900/40 text-red-400"))

            enrichment_rows.append(
                Div(
                    Span(m.get("identity_name", "?"), cls="text-white text-sm mr-2"),
                    *badges,
                    cls="flex items-center gap-1.5 py-1",
                    data_testid="enrichment-status",
                )
            )

        enrichment_section = Div(
            H2("Enrichment Status", cls="text-lg font-semibold text-white mb-3"),
            P("Metadata fields applied from GEDCOM data:", cls="text-xs text-slate-500 mb-2"),
            *enrichment_rows,
            cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 mb-6",
        )

    # Test data warning
    test_data_warning = None
    if source_file and "test" in source_file.lower():
        test_data_warning = Div(
            P("This is test data — upload your real GEDCOM file to replace it.", cls="text-sm text-amber-200"),
            cls="bg-amber-900/30 border border-amber-700/50 rounded-lg px-4 py-3 mb-6",
            data_testid="test-data-warning",
        )

    return Title(f"GEDCOM Import — {community_name}"), Div(
        _admin_nav_bar("gedcom", request=request),
        Div(
            H1("GEDCOM Management", cls="text-2xl font-bold text-white"),
            P(
                f"Source: {source_file}"
                if source_file
                else "Upload a GEDCOM file to enrich identity records with genealogical data.",
                cls="text-sm text-slate-400",
            ),
            cls="mb-6",
        ),
        test_data_warning,
        version_info,
        stats_cards,
        version_history_section,
        upload_section,
        import_history_section,
        matches_section,
        confirmed_section,
        enrichment_section,
        cls="max-w-4xl mx-auto p-6",
    )


@rt("/admin/gedcom/upload")
async def post(gedcom_file: UploadFile = None, notes: str = "", sess=None):
    """Handle GEDCOM file upload — parse, diff, and show preview before apply (AD-164)."""
    global _gedcom_upload_preview
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not gedcom_file or not gedcom_file.filename:
        return Div(P("No file selected.", cls="text-red-400"), cls="mt-4")

    # Save uploaded file temporarily
    import tempfile
    import hashlib as _hashlib

    content = await gedcom_file.read()
    with tempfile.NamedTemporaryFile(suffix=".ged", delete=False, mode="wb") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from rhodesli_ml.importers.gedcom_parser import parse_gedcom

        # Parse GEDCOM
        parsed = parse_gedcom(tmp_path)

        # Compute file hash for dedup
        file_hash = _hashlib.sha256(content).hexdigest()

        # Try versioned diff against Supabase (AD-163/164)
        diff_result = None
        try:
            from app.supabase_data import get_supabase_client
            from scripts.import_gedcom_version import import_versioned, check_duplicate_hash

            sb = get_supabase_client()
            if sb:
                # Check for duplicate
                existing = check_duplicate_hash(sb, file_hash)
                if existing:
                    return Div(
                        P(
                            f"This exact file was already imported as version {existing['version_number']}.",
                            cls="text-amber-400 font-medium",
                        ),
                        P(
                            "Upload a different GEDCOM file or modify this one first.",
                            cls="text-sm text-slate-400 mt-1",
                        ),
                        cls="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4 mt-4",
                    )

                # Dry-run to get diff
                diff_result = import_versioned(
                    sb,
                    parsed,
                    gedcom_file.filename,
                    file_hash,
                    notes=notes.strip() if notes else None,
                    dry_run=True,
                )
        except Exception as e:
            logging.warning(f"Versioned diff failed (falling back to legacy): {e}")

        # Store preview data for apply step
        _gedcom_upload_preview = {
            "tmp_path": tmp_path,
            "filename": gedcom_file.filename,
            "file_hash": file_hash,
            "notes": notes.strip() if notes else None,
            "individual_count": parsed.individual_count,
            "family_count": parsed.family_count,
            "diff": diff_result,
        }

        # Build diff preview UI
        if diff_result and not diff_result.get("skipped"):
            added = diff_result.get("added", 0)
            modified = diff_result.get("modified", 0)
            removed = diff_result.get("removed", 0)
            unchanged = diff_result.get("unchanged", 0)
            entity_summaries = diff_result.get("entity_summaries", {}) or {}
            sample_changes = diff_result.get("sample_changes", []) or []
            missing_tables = diff_result.get("missing_tables", []) or []
            schema_ready = diff_result.get("schema_ready", True)
            redirect_summary = diff_result.get("redirects", {}) or {}
            redirect_sample = redirect_summary.get("sample", []) or []

            diff_badges = []
            if added:
                diff_badges.append(
                    Span(f"+{added} added", cls="px-2 py-1 rounded bg-emerald-900/40 text-emerald-400 text-sm")
                )
            if modified:
                diff_badges.append(
                    Span(f"~{modified} modified", cls="px-2 py-1 rounded bg-amber-900/40 text-amber-400 text-sm")
                )
            if removed:
                diff_badges.append(
                    Span(f"-{removed} removed", cls="px-2 py-1 rounded bg-red-900/40 text-red-400 text-sm")
                )
            if unchanged:
                diff_badges.append(
                    Span(f"={unchanged} unchanged", cls="px-2 py-1 rounded bg-slate-700 text-slate-400 text-sm")
                )
            if redirect_summary.get("detected"):
                diff_badges.append(
                    Span(
                        f"{redirect_summary['detected']} redirects",
                        cls="px-2 py-1 rounded bg-sky-900/40 text-sky-300 text-sm",
                    )
                )

            parsed_counts = Div(
                Div(
                    P(f"{parsed.individual_count:,}", cls="text-xl font-semibold text-white"),
                    P("Individuals", cls="text-xs text-slate-400"),
                ),
                Div(
                    P(f"{parsed.family_count:,}", cls="text-xl font-semibold text-white"),
                    P("Families", cls="text-xs text-slate-400"),
                ),
                Div(
                    P(f"{parsed.source_count:,}", cls="text-xl font-semibold text-white"),
                    P("Sources", cls="text-xs text-slate-400"),
                ),
                Div(
                    P(f"{parsed.media_count:,}", cls="text-xl font-semibold text-white"),
                    P("Media", cls="text-xs text-slate-400"),
                ),
                Div(
                    P(f"{len(parsed.records):,}", cls="text-xl font-semibold text-white"),
                    P("Raw Records", cls="text-xs text-slate-400"),
                ),
                cls="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4",
            )

            entity_cards = []
            for label, key in (
                ("Individuals", "individuals"),
                ("Events", "events"),
                ("Families", "families"),
                ("Relationships", "relationships"),
                ("Sources", "sources"),
                ("Media", "media_objects"),
                ("Records", "records"),
            ):
                summary = entity_summaries.get(key, {})
                entity_cards.append(
                    Div(
                        P(label, cls="text-sm text-slate-300"),
                        P(
                            f"+{summary.get('added', 0)}  ~{summary.get('modified', 0)}  -{summary.get('removed', 0)}",
                            cls="text-xs text-slate-400 mt-1",
                        ),
                        cls="rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2",
                    )
                )

            sample_items = []
            for item in sample_changes[:5]:
                change_preview = []
                for change in item.get("changes", [])[:3]:
                    old_value = change.get("old_value")
                    new_value = change.get("new_value")
                    old_text = (
                        json.dumps(old_value)[:40] if isinstance(old_value, (dict, list)) else str(old_value)[:40]
                    )
                    new_text = (
                        json.dumps(new_value)[:40] if isinstance(new_value, (dict, list)) else str(new_value)[:40]
                    )
                    change_preview.append(f"{change.get('path')}: {old_text} → {new_text}")
                sample_items.append(
                    Div(
                        P(f"{item.get('entity_type')} · {item.get('entity_id')}", cls="text-sm text-white font-medium"),
                        P(" | ".join(change_preview), cls="text-xs text-slate-400 mt-1"),
                        cls="rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2",
                    )
                )

            redirect_items = []
            for item in redirect_sample[:5]:
                redirect_items.append(
                    Div(
                        P(
                            f"{item.get('entity_type')} · {item.get('old_key')} -> {item.get('new_key')}",
                            cls="text-sm text-white font-medium",
                        ),
                        P(
                            f"{item.get('redirect_type')} · score {item.get('match_score')} · {', '.join(item.get('reasons') or [])}",
                            cls="text-xs text-slate-400 mt-1",
                        ),
                        cls="rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2",
                    )
                )

            action_row = None
            if schema_ready:
                action_row = Div(
                    Button(
                        "Apply Changes",
                        cls="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium mr-2",
                        hx_post="/admin/gedcom/apply",
                        hx_target="#gedcom-results",
                        hx_indicator="#apply-spinner",
                    ),
                    Button(
                        "Cancel",
                        cls="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm font-medium",
                        hx_post="/admin/gedcom/cancel",
                        hx_target="#gedcom-results",
                    ),
                    Span("Applying...", id="apply-spinner", cls="htmx-indicator text-sm text-slate-400 ml-2"),
                    cls="flex items-center",
                )
            else:
                action_row = Div(
                    P(
                        "Rich GEDCOM schema migration is required before apply. Dry-run diff is safe; live import is blocked.",
                        cls="text-amber-300 text-sm",
                    ),
                    P(", ".join(missing_tables), cls="text-xs text-slate-500 mt-1") if missing_tables else None,
                    Button(
                        "Cancel",
                        cls="mt-3 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm font-medium",
                        hx_post="/admin/gedcom/cancel",
                        hx_target="#gedcom-results",
                    ),
                )

            return Div(
                parsed_counts,
                H3("Change Summary", cls="text-white font-semibold mt-3 mb-2"),
                Div(*diff_badges, cls="flex flex-wrap gap-2 mb-4"),
                Div(*entity_cards, cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4"),
                H3("Sample Changes", cls="text-white font-semibold mt-3 mb-2") if sample_items else None,
                Div(*sample_items, cls="space-y-2 mb-4") if sample_items else None,
                H3("Detected Redirects", cls="text-white font-semibold mt-3 mb-2") if redirect_items else None,
                Div(*redirect_items, cls="space-y-2 mb-4") if redirect_items else None,
                action_row,
                cls="bg-indigo-900/20 border border-indigo-700/50 rounded-lg p-4 mt-4",
                data_testid="gedcom-diff-preview",
            )
        else:
            # Fallback: no Supabase or diff failed — show basic parse results + apply
            return Div(
                P(
                    f"Parsed {parsed.individual_count:,} individuals, {parsed.family_count:,} families",
                    cls="text-emerald-400 font-medium",
                ),
                P(
                    "Version diff not available (Supabase not configured). You can still apply the import.",
                    cls="text-sm text-slate-400 mt-1",
                )
                if not diff_result
                else None,
                Div(
                    Button(
                        "Apply Import",
                        cls="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium mr-2",
                        hx_post="/admin/gedcom/apply",
                        hx_target="#gedcom-results",
                    ),
                    Button(
                        "Cancel",
                        cls="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm font-medium",
                        hx_post="/admin/gedcom/cancel",
                        hx_target="#gedcom-results",
                    ),
                    cls="flex items-center mt-3",
                ),
                cls="bg-indigo-900/20 border border-indigo-700/50 rounded-lg p-4 mt-4",
                data_testid="gedcom-diff-preview",
            )
    except Exception as e:
        logging.exception("GEDCOM parse error")
        # Clean up temp file on error
        import os as _os

        try:
            _os.unlink(tmp_path)
        except OSError:
            pass
        return Div(P(f"Error parsing GEDCOM: {e}", cls="text-red-400"), cls="mt-4")


@rt("/admin/gedcom/apply")
def post(sess=None):
    """Apply a previewed GEDCOM import (AD-164). Gatekeeper pattern: requires explicit confirmation."""
    global _gedcom_upload_preview
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    preview = _gedcom_upload_preview
    if not preview:
        return Div(P("No pending upload to apply. Please upload a file first.", cls="text-amber-400"), cls="mt-4")

    diff_result = preview.get("diff") or {}
    if not diff_result.get("schema_ready", True):
        missing_tables = diff_result.get("missing_tables", []) or []
        return Div(
            P("Cannot apply GEDCOM import until the rich-schema migration is in place.", cls="text-amber-300"),
            P(", ".join(missing_tables), cls="text-xs text-slate-500 mt-1") if missing_tables else None,
            cls="mt-4",
        )

    tmp_path = preview.get("tmp_path")
    filename = preview.get("filename", "unknown.ged")
    file_hash = preview.get("file_hash", "")
    notes = preview.get("notes")

    try:
        from rhodesli_ml.importers.gedcom_parser import parse_gedcom

        # Re-parse the file (still on disk)
        parsed = parse_gedcom(tmp_path)

        # Try versioned import to Supabase
        version_result = None
        try:
            from app.supabase_data import get_supabase_client
            from scripts.import_gedcom_version import import_versioned

            sb = get_supabase_client()
            if sb:
                version_result = import_versioned(
                    sb,
                    parsed,
                    filename,
                    file_hash,
                    notes=notes,
                    dry_run=False,
                )
        except Exception as e:
            logging.warning(f"Versioned import failed: {e}")

        # Also run legacy matching pipeline
        try:
            from rhodesli_ml.importers.identity_matcher import match_gedcom_to_identities
            from rhodesli_ml.importers.gedcom_matches import save_gedcom_matches

            registry = _main_mod.load_registry()
            identities = {iid: registry.get_identity(iid) for iid in registry.list_identities()}
            estimates = _main_mod._load_birth_year_estimates()

            match_result = match_gedcom_to_identities(
                parsed,
                identities,
                surname_variants_path=str(_main_mod.data_path / "surname_variants.json"),
                birth_year_estimates=estimates,
            )
            save_gedcom_matches(
                match_result.proposals,
                filepath=str(_main_mod.data_path / "gedcom_matches.json"),
                source_file=filename,
            )
            _main_mod.invalidate_gedcom_matches_cache()

            # Sync to Supabase
            try:
                from rhodesli_ml.importers.gedcom_matches import load_gedcom_matches
                from app.supabase_data import sync_gedcom_matches

                gm_data = load_gedcom_matches(str(_main_mod.data_path / "gedcom_matches.json"))
                sync_gedcom_matches(gm_data.get("matches", []))
            except Exception as e:
                logging.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")

            match_info = P(
                f"Found {match_result.match_count} potential matches with archive identities", cls="text-white mt-1"
            )
        except Exception as e:
            logging.warning(f"Legacy matching pipeline failed: {e}")
            match_info = P(f"Match generation skipped: {e}", cls="text-sm text-amber-400 mt-1")

        # Build success UI
        version_badge = None
        if version_result and not version_result.get("skipped"):
            vn = version_result.get("version_number", "?")
            version_badge = P(f"Created version {vn} in database.", cls="text-indigo-400 mt-1")

        _gedcom_upload_preview = None  # Clear preview

        return Div(
            P(
                f"Successfully imported {parsed.individual_count:,} individuals, {parsed.family_count:,} families",
                cls="text-emerald-400 font-medium",
            ),
            version_badge,
            match_info,
            A(
                "Refresh page to see updated data",
                href="/admin/gedcom",
                cls="inline-block mt-3 text-indigo-400 hover:text-indigo-300 underline text-sm",
            ),
            cls="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-4 mt-4",
            data_testid="gedcom-apply-success",
        )
    except Exception as e:
        logging.exception("GEDCOM apply error")
        return Div(P(f"Error applying GEDCOM import: {e}", cls="text-red-400"), cls="mt-4")
    finally:
        # Clean up temp file
        import os as _os

        try:
            if tmp_path:
                _os.unlink(tmp_path)
        except OSError:
            pass


@rt("/admin/gedcom/cancel")
def post(sess=None):
    """Cancel a previewed GEDCOM import (AD-164)."""
    global _gedcom_upload_preview
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    preview = _gedcom_upload_preview
    _gedcom_upload_preview = None

    # Clean up temp file
    if preview and preview.get("tmp_path"):
        import os as _os

        try:
            _os.unlink(preview["tmp_path"])
        except OSError:
            pass

    return Div(
        P("Upload cancelled.", cls="text-slate-400"),
        cls="mt-4",
        data_testid="gedcom-cancel-result",
    )


@rt("/admin/gedcom/confirm/{xref}")
def post(xref: str, sess=None):
    """Confirm a GEDCOM-to-identity match and apply enrichment."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from rhodesli_ml.importers.gedcom_matches import update_match_status

    # Update status
    matches_data = update_match_status(
        filepath=str(_main_mod.data_path / "gedcom_matches.json"),
        gedcom_xref=xref,
        status="confirmed",
    )

    # Find the confirmed match
    match = None
    for m in matches_data.get("matches", []):
        if m.get("gedcom_xref") == xref:
            match = m
            break

    if not match:
        return Div(P("Match not found.", cls="text-red-400"))

    # Apply enrichment to identity
    registry = _main_mod.load_registry()
    identity_id = match.get("identity_id", "")
    updates = {}

    if match.get("gedcom_birth_year"):
        updates["birth_year"] = match["gedcom_birth_year"]
    if match.get("gedcom_death_year"):
        updates["death_year"] = match["gedcom_death_year"]
    if match.get("gedcom_birth_place"):
        updates["birth_place"] = match["gedcom_birth_place"]

    if updates:
        registry.set_metadata(identity_id, updates, user_source="gedcom")
        _main_mod.save_registry(registry, changed_ids={identity_id})

    # Invalidate caches
    _main_mod.invalidate_gedcom_matches_cache()
    _main_mod._birth_year_cache = None

    # Sync GEDCOM matches to Supabase (AD-135)
    try:
        from app.supabase_data import sync_gedcom_matches

        sync_gedcom_matches(matches_data.get("matches", []))
    except Exception as e:
        logging.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")

    return Div(
        Span(match.get("gedcom_name", "?"), cls="text-emerald-400 font-medium"),
        Span("→", cls="text-slate-500 mx-2"),
        Span(match.get("identity_name", "?"), cls="text-white font-medium"),
        Span("Confirmed", cls="ml-3 px-2 py-0.5 bg-emerald-600/30 text-emerald-400 text-xs rounded"),
        cls="flex items-center py-3 px-4 bg-emerald-900/10 rounded-lg border border-emerald-700/30",
    )


@rt("/admin/gedcom/reject/{xref}")
def post(xref: str, sess=None):
    """Reject a GEDCOM-to-identity match."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from rhodesli_ml.importers.gedcom_matches import update_match_status

    matches_data = update_match_status(
        filepath=str(_main_mod.data_path / "gedcom_matches.json"),
        gedcom_xref=xref,
        status="rejected",
    )

    match = None
    for m in matches_data.get("matches", []):
        if m.get("gedcom_xref") == xref:
            match = m
            break
    _main_mod.invalidate_gedcom_matches_cache()

    # Sync GEDCOM matches to Supabase (AD-135)
    try:
        from app.supabase_data import sync_gedcom_matches

        sync_gedcom_matches(matches_data.get("matches", []))
    except Exception as e:
        logging.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")

    return Div(
        Span(match.get("gedcom_name", "?") if match else "?", cls="text-red-400/50 line-through"),
        Span("→", cls="text-slate-600 mx-2"),
        Span(match.get("identity_name", "?") if match else "?", cls="text-slate-500 line-through"),
        Span("Rejected", cls="ml-3 px-2 py-0.5 bg-red-600/20 text-red-400 text-xs rounded"),
        cls="flex items-center py-3 px-4 bg-red-900/5 rounded-lg border border-red-700/20 opacity-60",
    )


@rt("/admin/gedcom/skip/{xref}")
def post(xref: str, sess=None):
    """Skip a GEDCOM match for later review."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from rhodesli_ml.importers.gedcom_matches import update_match_status

    matches_data = update_match_status(
        filepath=str(_main_mod.data_path / "gedcom_matches.json"),
        gedcom_xref=xref,
        status="skipped",
    )
    _main_mod.invalidate_gedcom_matches_cache()

    # Sync GEDCOM matches to Supabase (AD-135)
    try:
        from app.supabase_data import sync_gedcom_matches

        sync_gedcom_matches(matches_data.get("matches", []))
    except Exception as e:
        logging.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")

    return Div(Span("Skipped — will reappear on refresh", cls="text-slate-500 text-sm italic"), cls="py-3 px-4")


# --- GEDCOM Search & Linking API (Session 65b, AD-160) ---


def _compute_correction_priority(label: dict) -> float:
    """Compute priority score for a photo date label.

    Higher score = more urgent to review.
    Score formula from PRD 005:
      (1 - confidence_numeric) * range_width_normalized * (1 + temporal_conflict_flag)
    """
    confidence = label.get("confidence", "medium")
    conf_numeric = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(confidence, 0.5)

    prob_range = label.get("probable_range", [])
    if len(prob_range) == 2:
        range_width = abs(prob_range[1] - prob_range[0])
    else:
        range_width = 20  # Default wide range if unknown
    range_normalized = range_width / 50.0

    # temporal_conflict_flag would come from audit data — for now, default to 0
    temporal_flag = 0

    return (1.0 - conf_numeric) * range_normalized * (1.0 + temporal_flag)


def _get_priority_reason(label: dict) -> str:
    """Generate human-readable reason for review priority."""
    reasons = []
    confidence = label.get("confidence", "medium")
    if confidence == "low":
        reasons.append("Low confidence")
    prob_range = label.get("probable_range", [])
    if len(prob_range) == 2:
        width = abs(prob_range[1] - prob_range[0])
        if width >= 15:
            reasons.append(f"Wide date range ({prob_range[0]}\u2013{prob_range[1]})")
    return " \u00b7 ".join(reasons) if reasons else "Routine review"


@rt("/admin/review-queue")
def get(request, sess=None):
    """Admin review queue — photos sorted by correction priority score."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    labels = _main_mod._load_date_labels()
    _main_mod._build_caches()

    # Score all photos, exclude already-verified ones and duplicates
    scored = []
    seen_labels = set()  # Track by label id() to skip dual-keyed duplicates
    for photo_id, label in labels.items():
        if id(label) in seen_labels:
            continue
        seen_labels.add(id(label))
        if label.get("source") == "human":
            continue  # Already verified
        # Prefer SHA256 cache ID for display (matches _main_mod._photo_cache and /photo/{id} URLs)
        cache_id = photo_id
        if photo_id.startswith("inbox_"):
            # Check if there's a SHA256 alias that maps to a _main_mod._photo_cache entry
            for k, v in labels.items():
                if v is label and not k.startswith("inbox_"):
                    cache_id = k
                    break
        photo_id = cache_id
        score = _compute_correction_priority(label)
        scored.append((photo_id, label, score))

    # Sort by priority (highest first)
    scored.sort(key=lambda x: -x[2])

    # Build review items
    items = []
    for photo_id, label, score in scored[:50]:  # Show top 50
        decade = label.get("estimated_decade", "")
        best_year = label.get("best_year_estimate", "")
        confidence = label.get("confidence", "medium")
        reason = _get_priority_reason(label)

        # Get photo filename for thumbnail
        photo_data = (_main_mod._photo_cache or {}).get(photo_id)
        if not photo_data:
            # Try looking up by cache_photo_id
            for pid, pdata in (_main_mod._photo_cache or {}).items():
                if pid == photo_id:
                    photo_data = pdata
                    break
        filename = photo_data.get("filename", "") if photo_data else ""

        conf_cls = {
            "high": "text-emerald-400",
            "medium": "text-amber-400",
            "low": "text-red-400",
        }.get(confidence, "text-slate-400")

        items.append(
            Div(
                A(
                    Img(
                        src=_main_mod.photo_url(filename) if filename else "",
                        cls="w-20 h-20 object-cover rounded",
                        loading="lazy",
                        alt="Archive photo",
                    ),
                    href=f"{nav_prefix}/photo/{photo_id}",
                    cls="shrink-0",
                )
                if filename
                else Div(cls="w-20 h-20 bg-slate-800 rounded"),
                Div(
                    Div(
                        Span(f"c. {best_year}" if best_year else f"{decade}s", cls="font-serif text-amber-200"),
                        Span(f" ({confidence})", cls=f"text-xs {conf_cls} ml-1"),
                        cls="mb-1",
                    ),
                    P(reason, cls="text-xs text-slate-400 mb-2"),
                    Div(
                        A(
                            "Confirm AI",
                            href=f"/api/photo/{photo_id}/confirm-date",
                            cls="text-xs px-2 py-1 bg-emerald-600/30 text-emerald-400 rounded hover:bg-emerald-600/50 transition-colors",
                            hx_post=f"/api/photo/{photo_id}/confirm-date",
                            hx_target=f"#review-{photo_id[:8]}",
                            hx_swap="outerHTML",
                        ),
                        A(
                            "View & Correct",
                            href=f"{nav_prefix}/photo/{photo_id}",
                            cls="text-xs px-2 py-1 bg-indigo-600/30 text-indigo-400 rounded hover:bg-indigo-600/50 transition-colors",
                        ),
                        cls="flex gap-2",
                    ),
                    cls="flex-1",
                ),
                Div(
                    Span(f"{score:.3f}", cls="text-[10px] text-slate-600 font-mono"),
                    cls="shrink-0",
                ),
                cls="flex items-start gap-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50",
                id=f"review-{photo_id[:8]}",
                data_testid="review-item",
                data_priority=f"{score:.4f}",
            )
        )

    if not items:
        items = [P("All photos have been reviewed!", cls="text-slate-400 text-center py-12")]

    return Title(f"Review Queue \u2014 {community_name}"), Div(
        Div(
            H1("Date Review Queue", cls="text-2xl font-bold text-white"),
            P(f"{len(scored)} photos need review", cls="text-sm text-slate-400"),
            cls="mb-6",
        ),
        Div(*items, cls="space-y-2"),
        cls="max-w-3xl mx-auto p-6",
    )


# =============================================================================
# COMMUNITY SWITCHER API
# =============================================================================


@rt("/api/communities/switcher")
def get(sess=None):
    """Returns HTML fragment with community list for workspace switcher dropdown."""
    user = _main_mod.get_current_user(sess or {})
    if not user or not user.is_admin:
        return ""
    from app.supabase_data import load_communities

    communities = load_communities() or []
    items = []
    for c in communities:
        slug = c.get("slug", "")
        name = c.get("name", slug)
        prefix = _main_mod.community_url_prefix(slug)
        items.append(
            A(
                name,
                href=f"{prefix}/",
                cls="block px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 rounded",
            )
        )
    items.append(Hr(cls="border-slate-700 my-1"))
    items.append(
        A(
            "Manage Communities",
            href="/admin/communities",
            cls="block px-3 py-2 text-xs text-slate-500 hover:text-slate-300",
        )
    )
    return Div(
        *items,
        cls="py-1 bg-slate-800 border border-slate-700 rounded-lg shadow-lg",
        data_testid="community-switcher-list",
    )


# =============================================================================
# COMMUNITY ADMIN CRUD (PRD-035)
# =============================================================================


@rt("/admin/communities")
def get(sess=None):
    """List all communities for admin management."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    from app.supabase_data import load_communities

    communities = load_communities() or []

    rows = []
    for c in communities:
        rows.append(
            Tr(
                Td(c.get("name", ""), cls="px-4 py-3 text-white"),
                Td(
                    A(
                        f"/c/{c.get('slug', '')}",
                        href=f"/c/{c.get('slug', '')}/",
                        cls="text-indigo-400 hover:text-indigo-300",
                    ),
                    cls="px-4 py-3",
                ),
                Td(
                    Span("Default", cls="text-xs bg-emerald-600/30 text-emerald-300 px-2 py-0.5 rounded")
                    if c.get("is_default")
                    else "",
                    cls="px-4 py-3",
                ),
                Td(
                    A(
                        "Edit",
                        href=f"/admin/communities/{c.get('slug', '')}/edit",
                        cls="text-indigo-400 hover:text-indigo-300 text-sm",
                    ),
                    cls="px-4 py-3",
                ),
                cls="border-b border-slate-700/50",
                data_testid="community-row",
            )
        )

    if not rows:
        rows = [
            Tr(
                Td(
                    "No communities found. Create one to get started.",
                    colspan="4",
                    cls="px-4 py-8 text-slate-400 text-center",
                ),
            )
        ]

    return Title("Communities — Admin"), Div(
        _admin_nav_bar(active="communities"),
        Div(
            Div(
                H1("Communities", cls="text-2xl font-bold text-white"),
                A(
                    "+ New Community",
                    href="/admin/communities/new",
                    cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors",
                ),
                cls="flex items-center justify-between mb-6",
            ),
            Table(
                Thead(
                    Tr(
                        Th("Name", cls="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase"),
                        Th("URL", cls="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase"),
                        Th("Status", cls="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase"),
                        Th("Actions", cls="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase"),
                    ),
                ),
                Tbody(*rows),
                cls="w-full",
                data_testid="communities-table",
            ),
            cls="max-w-4xl mx-auto p-6",
        ),
        cls="min-h-screen bg-slate-900",
    )


@rt("/admin/communities/new")
def get(sess=None):
    """Form to create a new community."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    return Title("New Community — Admin"), Div(
        _admin_nav_bar(active="communities"),
        Div(
            H1("Create Community", cls="text-2xl font-bold text-white mb-6"),
            _community_form(action="/admin/communities", submit_label="Create Community"),
            cls="max-w-2xl mx-auto p-6",
        ),
        cls="min-h-screen bg-slate-900",
    )


@rt("/admin/communities")
def post(
    name: str = "",
    slug: str = "",
    landing_title: str = "",
    landing_subtitle: str = "",
    sess=None,
):
    """Create a new community."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    if not name or not slug:
        return Div(P("Name and slug are required.", cls="text-red-400"), cls="p-4")

    # Validate slug format
    import re as _re_community

    if not _re_community.match(r"^[a-z0-9][a-z0-9_-]*$", slug):
        return Div(P("Slug must be lowercase alphanumeric with hyphens/underscores.", cls="text-red-400"), cls="p-4")

    from app.supabase_data import create_community

    data = {"name": name, "slug": slug}
    if landing_title:
        data["landing_title"] = landing_title
    if landing_subtitle:
        data["landing_subtitle"] = landing_subtitle

    result = create_community(data)
    if result:
        return RedirectResponse(url="/admin/communities", status_code=303)
    else:
        return Div(P("Failed to create community. Check Supabase connection.", cls="text-red-400"), cls="p-4")


@rt("/admin/communities/{slug}/edit")
def get(slug: str, sess=None):
    """Edit form for a community."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    from app.supabase_data import get_community_by_slug

    community = get_community_by_slug(slug)
    if not community:
        return HTMLResponse("<h1>Community not found</h1>", status_code=404)

    return Title(f"Edit {community.get('name', slug)} — Admin"), Div(
        _admin_nav_bar(active="communities"),
        Div(
            H1(f"Edit: {community.get('name', slug)}", cls="text-2xl font-bold text-white mb-6"),
            _community_form(
                action=f"/admin/communities/{slug}",
                submit_label="Save Changes",
                community=community,
            ),
            cls="max-w-2xl mx-auto p-6",
        ),
        cls="min-h-screen bg-slate-900",
    )


@rt("/admin/communities/{slug}")
def post(
    slug: str,
    name: str = "",
    landing_title: str = "",
    landing_subtitle: str = "",
    sess=None,
):
    """Update a community."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    from app.supabase_data import get_community_by_slug, update_community

    community = get_community_by_slug(slug)
    if not community:
        return HTMLResponse("<h1>Community not found</h1>", status_code=404)

    data = {}
    if name:
        data["name"] = name
    if landing_title:
        data["landing_title"] = landing_title
    if landing_subtitle:
        data["landing_subtitle"] = landing_subtitle

    if data:
        update_community(community["id"], data)

    return RedirectResponse(url="/admin/communities", status_code=303)


def _community_form(action: str, submit_label: str = "Save", community: dict = None) -> Form:
    """Render a community create/edit form."""
    c = community or {}
    return Form(
        Div(
            Label("Name *", cls="block text-sm font-medium text-slate-300 mb-1"),
            Input(
                type="text",
                name="name",
                value=c.get("name", ""),
                placeholder="e.g., Fox Family Archive",
                required=True,
                cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400",
            ),
            cls="mb-4",
        ),
        Div(
            Label("Slug *", cls="block text-sm font-medium text-slate-300 mb-1"),
            Input(
                type="text",
                name="slug",
                value=c.get("slug", ""),
                placeholder="e.g., fox-family",
                required=not bool(community),  # Required for create, readonly for edit
                readonly=bool(community),
                cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400"
                + (" opacity-50" if community else ""),
            ),
            P("URL-safe identifier (lowercase, hyphens, no spaces)", cls="text-xs text-slate-500 mt-1"),
            cls="mb-4",
        ),
        Div(
            Label("Landing Title", cls="block text-sm font-medium text-slate-300 mb-1"),
            Input(
                type="text",
                name="landing_title",
                value=c.get("landing_title", ""),
                placeholder="e.g., Fox Family Heritage Archive",
                cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400",
            ),
            cls="mb-4",
        ),
        Div(
            Label("Landing Subtitle", cls="block text-sm font-medium text-slate-300 mb-1"),
            Input(
                type="text",
                name="landing_subtitle",
                value=c.get("landing_subtitle", ""),
                placeholder="e.g., Preserving four generations of family photos",
                cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400",
            ),
            cls="mb-4",
        ),
        Div(
            Button(
                submit_label,
                type="submit",
                cls="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors",
            ),
            A("Cancel", href="/admin/communities", cls="ml-4 text-slate-400 hover:text-slate-300"),
            cls="mt-6",
        ),
        action=action,
        method="post",
        data_testid="community-form",
    )
