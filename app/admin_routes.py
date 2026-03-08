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
from starlette.responses import FileResponse, Response

from app.auth import get_current_user
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

# Module-level state for GEDCOM upload preview
_gedcom_upload_preview = None


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
    _main_mod.save_registry(registry)

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
def get(sess=None):
    """
    Admin page to review pending uploads from non-admin users.
    Requires admin when auth is enabled.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical _main_mod.sidebar counts
    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry)

    # Load pending uploads (both contributor "pending" and admin "staged")
    pending = _main_mod._load_pending_uploads()
    pending_items = [u for u in pending["uploads"].values() if u["status"] in ("pending", "staged")]
    # Sort by submitted_at descending (newest first)
    pending_items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)

    # Also show recently reviewed items
    reviewed_items = [u for u in pending["uploads"].values() if u["status"] in ("approved", "rejected")]
    reviewed_items.sort(key=lambda x: x.get("reviewed_at", x.get("submitted_at", "")), reverse=True)
    reviewed_items = reviewed_items[:10]  # Show last 10

    # Build pending cards
    if pending_items:
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

            # Staged items (admin uploads) show status badge, no approve/reject
            # Pending items (contributor uploads) show approve/reject buttons
            if is_staged:
                actions = Div(
                    Span("Staged", cls="px-2 py-1 bg-blue-600/30 text-blue-300 text-xs font-bold rounded uppercase"),
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
                        cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors",
                    ),
                    Button(
                        "Reject",
                        hx_post=f"/admin/pending/{job_id}/reject",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-500 transition-colors",
                    ),
                    cls="flex gap-2 items-start",
                )

            # Photo preview thumbnails (served via admin-authenticated endpoint)
            preview_thumbs = []
            upload_files = item.get("files", [])
            from urllib.parse import quote

            for fname in upload_files[:6]:
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    thumb_url = f"/admin/staging-preview/{quote(job_id)}/{quote(fname)}"
                    # Graceful fallback: show filename label if image fails to load
                    preview_thumbs.append(
                        Div(
                            Img(
                                src=thumb_url,
                                alt=fname,
                                loading="lazy",
                                cls="w-16 h-16 object-cover rounded border border-slate-600",
                                title=fname,
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'",
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

            pending_cards.append(
                Div(
                    Div(
                        Div(
                            P(item.get("uploader_email", "Unknown"), cls="text-slate-200 font-medium text-sm"),
                            P(detail_line, cls="text-slate-400 text-xs"),
                            P(
                                f"Submitted: {item.get('submitted_at', 'Unknown')[:19].replace('T', ' ')}",
                                cls="text-slate-500 text-xs mt-0.5",
                            ),
                            P(f"Job ID: {job_id}", cls="text-slate-600 text-xs font-mono"),
                            cls="flex-1",
                        ),
                        actions,
                        cls="flex items-start justify-between gap-4",
                    ),
                    preview_row,
                    id=f"pending-card-{job_id}",
                    cls="p-4 bg-slate-800 border border-slate-700 rounded-lg",
                )
            )
        pending_section = Div(*pending_cards, cls="space-y-3")
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
                                href=f"/photo/{candidate_id}",
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
        Title("Pending Uploads - Rhodesli"),
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
def get(sess=None):
    """
    Admin page to review proposed identity matches.
    Requires admin when auth is enabled.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical _main_mod.sidebar counts
    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry)

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
        Title("Proposals - Rhodesli"),
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
                        hx_get="/api/proposed-matches",
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


@rt("/admin/pending/{job_id}/approve")
def post(job_id: str, sess=None):
    """Approve a pending upload. Requires admin."""
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
    if upload["status"] != "pending":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
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

    # If PROCESSING_ENABLED, move files from staging to uploads and spawn processing
    if PROCESSING_ENABLED:
        import shutil

        staging_dir = _main_mod.data_path / "staging" / job_id
        uploads_dir = _main_mod.data_path / "uploads" / job_id
        if staging_dir.exists():
            uploads_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging_dir, uploads_dir, dirs_exist_ok=True)

            # Run processing in background thread (AD-161: avoids OOM from subprocess)
            import threading

            source = upload.get("source", "")
            upload_collection = upload.get("collection", "")
            uploader_email = upload.get("uploader_email", "")
            submitted_at = upload.get("submitted_at", "")

            def _bg_approve_ingest():
                import logging as _bg_logging

                log_path = uploads_dir / f"{job_id}.log"
                try:
                    file_handler = _bg_logging.FileHandler(str(log_path))
                    file_handler.setLevel(_bg_logging.INFO)
                    _bg_logging.getLogger("core.ingest_inbox").addHandler(file_handler)

                    from core.ingest_inbox import process_directory

                    process_directory(
                        directory=uploads_dir,
                        job_id=job_id,
                        data_dir=_main_mod.data_path,
                        source=source,
                        collection=upload_collection,
                        prefer_hybrid=True,
                        uploaded_by=uploader_email,
                        upload_date=submitted_at,
                    )

                    # Upload new raw photos + crops to R2 (if R2 is configured)
                    try:
                        _main_mod._upload_new_files_to_r2(_main_mod.data_path, job_id)
                    except Exception as r2_err:
                        _bg_logging.getLogger("core.ingest_inbox").warning(
                            f"R2 upload failed for job {job_id}: {r2_err}"
                        )

                    # Invalidate caches so new photo appears immediately
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
    return Div(
        Div(
            Span("Approved", cls="text-green-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1",
        ),
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg",
    )


@rt("/admin/pending/{job_id}/reject")
def post(job_id: str, sess=None):
    """Reject a pending upload. Requires admin."""
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
    if upload["status"] != "pending":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg",
        )

    # Update status to rejected
    upload["status"] = "rejected"
    upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["reviewed_by"] = user.email if user else "unknown"
    _main_mod._save_pending_uploads(pending)
    _main_mod.log_user_action(
        "REJECT_UPLOAD",
        job_id=job_id,
        uploader=upload.get("uploaded_by", "unknown"),
        admin=user.email if user else "unknown",
    )

    # Optionally clean up staging files
    import shutil

    staging_dir = _main_mod.data_path / "staging" / job_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    file_count = upload.get("file_count", len(upload.get("files", [])))
    return Div(
        Div(
            Span("Rejected", cls="text-red-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1",
        ),
        cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg",
    )


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
def get(sess=None):
    """ML evaluation dashboard. Shows golden set stats, thresholds, identity counts."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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

    return Title("ML Dashboard — Rhodesli"), Div(
        _admin_nav_bar("ml-dashboard"),
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
        "blue": "border-blue-500 text-blue-400",
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


def _admin_nav_bar(active: str = "") -> Div:
    """Consistent navigation bar for admin sub-pages.

    Shows links to all admin areas + back to dashboard.
    `active` should be one of: approvals, proposals, gedcom, uploads, audit, ml-dashboard
    """
    links = [
        ("Uploads", "/admin/pending", "uploads"),
        ("Approvals", "/admin/approvals", "approvals"),
        ("Proposals", "/admin/proposals", "proposals"),
        ("Birth Years", "/admin/review/birth-years", "birth-year-review"),
        ("GEDCOM", "/admin/gedcom", "gedcom"),
        ("Audit Log", "/admin/audit", "audit"),
        ("ML Dashboard", "/admin/ml-dashboard", "ml-dashboard"),
    ]
    nav_items = []
    for label, href, key in links:
        is_active = key == active
        cls = "px-3 py-1.5 text-sm rounded-lg transition-colors " + (
            "bg-indigo-600 text-white" if is_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"
        )
        nav_items.append(A(label, href=href, cls=cls))
    nav_items.append(
        A(
            "Dashboard",
            href="/?section=to_review",
            cls="px-3 py-1.5 text-sm text-indigo-400 hover:text-indigo-300 ml-auto",
        ),
    )
    return Div(
        *nav_items,
        cls="flex items-center gap-2 mb-6 pb-4 border-b border-slate-700/50 overflow-x-auto whitespace-nowrap scrollbar-hide shrink-0",
        data_testid="admin-nav-bar",
    )


@rt("/admin/approvals")
def get(sess=None):
    """Admin page for reviewing pending annotations."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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
                                cls="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-500",
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
                    if face_thumb
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
                            ),
                            cls="text-xs text-slate-500",
                        ),
                        P(f"Reason: {a.get('reason', 'none')}", cls="text-xs text-slate-500")
                        if a.get("reason")
                        else None,
                        Div(
                            Button(
                                "Approve",
                                hx_post=f"/admin/approvals/{ann_id}/approve",
                                hx_target=f"#annotation-{ann_id}",
                                hx_swap="outerHTML",
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

    return Title("Annotation Approvals — Rhodesli"), Div(
        _admin_nav_bar("approvals"),
        Div(H1("Pending Approvals", cls="text-2xl font-bold text-white"), cls="mb-6"),
        Div(f"{len(pending)} pending annotations", cls="text-sm text-slate-400 mb-4"),
        Div(*rows, cls="space-y-3"),
        cls="max-w-3xl mx-auto p-6",
    )


@rt("/admin/approvals/{ann_id}/approve")
def post(ann_id: str, sess=None):
    """Approve an annotation. Updates target record."""
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
            identity["name"] = ann["value"]
            identity["updated_at"] = datetime.now(timezone.utc).isoformat()
            _main_mod.save_registry(registry)
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
                _main_mod.save_registry(registry)
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

    status_label = "APPROVED" if ann["type"] != "merge_suggestion" else "MERGED"
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
def get(sess=None):
    """Admin bulk review page for ML birth year estimates."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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
                        A(name, href=f"/person/{iid}", cls="text-white text-sm font-medium hover:text-indigo-400"),
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
        Title("ML Birth Year Review - Rhodesli Admin"),
        page_style,
        Main(
            _admin_nav_bar("birth-year-review"),
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

    _main_mod.save_registry(registry)
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
def get(sess=None):
    """Admin audit log — shows all annotation review actions."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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

    return Title("Audit Log — Rhodesli"), Div(
        _admin_nav_bar("audit"),
        Div(H1("Audit Log", cls="text-2xl font-bold text-white"), cls="mb-6"),
        P(f"{len(entries)} audit entries", cls="text-sm text-slate-400 mb-4"),
        Div(*rows, cls="space-y-0"),
        cls="max-w-4xl mx-auto p-6",
    )


# --- GEDCOM Import (Session 35) ---


@rt("/admin/gedcom")
def get(sess=None):
    """GEDCOM admin page — version management, upload, match review (AD-164)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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

    return Title("GEDCOM Import — Rhodesli"), Div(
        _admin_nav_bar("gedcom"),
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

            return Div(
                P(
                    f"Parsed {parsed.individual_count:,} individuals, {parsed.family_count:,} families",
                    cls="text-emerald-400 font-medium",
                ),
                H3("Change Summary", cls="text-white font-semibold mt-3 mb-2"),
                Div(*diff_badges, cls="flex flex-wrap gap-2 mb-4"),
                Div(
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
                ),
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
            _main_mod._gedcom_matches_cache = None

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
        _main_mod.save_registry(registry)

    # Invalidate caches
    _main_mod._gedcom_matches_cache = None
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
    _main_mod._gedcom_matches_cache = None

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
    _main_mod._gedcom_matches_cache = None

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
def get(sess=None):
    """Admin review queue — photos sorted by correction priority score."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

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
                        src=photo_url(filename) if filename else "",
                        cls="w-20 h-20 object-cover rounded",
                        loading="lazy",
                    ),
                    href=f"/photo/{photo_id}",
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
                            href=f"/photo/{photo_id}",
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

    return Title("Review Queue \u2014 Rhodesli"), Div(
        Div(
            H1("Date Review Queue", cls="text-2xl font-bold text-white"),
            P(f"{len(scored)} photos need review", cls="text-sm text-slate-400"),
            cls="mb-6",
        ),
        Div(*items, cls="space-y-2"),
        cls="max-w-3xl mx-auto p-6",
    )
