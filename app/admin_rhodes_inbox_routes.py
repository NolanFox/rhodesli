"""Admin routes for the rhodes-wiki inbox approval workflow (Session 161).

Adds 4 routes to rhodesli (local-dev-only — gated by `is_rhodes_wiki_available`
which returns False on production Railway):

    GET  /admin/rhodes-inbox                   — list view
    GET  /admin/rhodes-inbox/<slug>            — detail view (caption + 14 comments + kinship triples)
    POST /admin/rhodes-inbox/<slug>/approve    — atomic-CAS approve → redirect /upload?prefill=<slug>
    POST /admin/rhodes-inbox/<slug>/reject     — atomic-CAS reject with reason

All POSTs follow the rhodesli admin pattern: `_check_origin` (CSRF, Codex P1-1),
then `_check_admin`, then `_validate_slug` (Codex P0-2), then the action.

Production safety: every handler short-circuits to 404 when
`is_rhodes_wiki_available()` is False. On Railway this is always the case
because RAILWAY_ENVIRONMENT is set (Codex P1-2).

Registered from `app/main.py` via `register_admin_rhodes_inbox_routes(app)`.
"""

from __future__ import annotations

import logging
from typing import Any

from fasthtml.common import (
    Div, A, Span, H1, H2, H3, P, Table, Tr, Td, Th, Thead, Tbody,
    Form, Input, Textarea, Button, Script, Pre, Code, Ul, Li,
)
from starlette.responses import RedirectResponse, Response

from app.rhodes_inbox import (
    AlreadyApprovedError,
    AlreadyRejectedError,
    _validate_slug,
    count_pending_rhodes_inbox,
    is_rhodes_wiki_available,
    kinship_triples_for,
    list_approved_entries,
    list_pending_entries,
    list_rejected_entries,
    load_entry,
    mark_approved,
    mark_rejected,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tailwind class shortcuts (consistent with rhodesli admin design tokens)
# ---------------------------------------------------------------------------

_PAGE_WRAP = "max-w-6xl mx-auto px-4 py-6 sm:px-6 lg:px-8"
_HEADER_CLS = "text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2"
_SUB_CLS = "text-sm text-slate-600 dark:text-slate-400 mb-6"
_CARD_CLS = "bg-white dark:bg-slate-800 shadow rounded-2xl p-6 mb-6"
_BTN_PRIMARY = "inline-flex items-center px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
_BTN_DANGER = "inline-flex items-center px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
_BTN_NEUTRAL = "inline-flex items-center px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600"


def _status_badge(status: str) -> Span:
    colors = {
        "pending": "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
        "approved": "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
        "rejected": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    }
    cls = "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium " + colors.get(status, "bg-slate-100 text-slate-700")
    return Span(status, cls=cls)


def _render_list_view(state: str = "pending") -> Any:
    """Render the inbox list at a given state."""
    state_listers = {
        "pending": list_pending_entries,
        "approved": list_approved_entries,
        "rejected": list_rejected_entries,
    }
    entries = state_listers.get(state, list_pending_entries)()

    pending_count = len(list_pending_entries())
    approved_count = len(list_approved_entries())
    rejected_count = len(list_rejected_entries())

    # Tabs
    def tab(label, target_state, count, current):
        is_active = (target_state == state)
        active_cls = "border-indigo-500 text-indigo-700 dark:text-indigo-300" if is_active else "border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900"
        return A(
            f"{label} ",
            Span(f"({count})", cls="text-xs"),
            href=f"/admin/rhodes-inbox?state={target_state}",
            cls=f"inline-flex items-center px-3 py-2 border-b-2 text-sm font-medium {active_cls}",
        )

    tabs = Div(
        tab("Pending", "pending", pending_count, state),
        tab("Approved", "approved", approved_count, state),
        tab("Rejected", "rejected", rejected_count, state),
        cls="flex gap-2 border-b border-slate-200 dark:border-slate-700 mb-4",
    )

    if not entries:
        body = Div(
            P(
                f"No {state} entries. ",
                "Capture posts via the rhodes-wiki Chrome MCP workflow, then refresh."
                if state == "pending"
                else "Approved entries will appear here once admin clicks Approve."
                if state == "approved"
                else "Rejected entries are kept for audit (per AD-S161-6).",
                cls="text-slate-600 dark:text-slate-400",
            ),
            cls="py-12 text-center",
        )
    else:
        rows = []
        for e in entries:
            rows.append(
                Tr(
                    Td(
                        A(e.slug, href=f"/admin/rhodes-inbox/{e.slug}", cls="text-indigo-600 hover:underline font-mono text-sm"),
                        cls="px-4 py-3",
                    ),
                    Td(e.fb_author_name or "—", cls="px-4 py-3 text-sm"),
                    Td(str(e.comments_count), cls="px-4 py-3 text-sm text-right"),
                    Td((e.captured_at or "")[:10], cls="px-4 py-3 text-sm text-slate-500"),
                    Td(_status_badge(e.status), cls="px-4 py-3"),
                    Td(
                        A("Review →", href=f"/admin/rhodes-inbox/{e.slug}", cls=_BTN_NEUTRAL),
                        cls="px-4 py-3 text-right",
                    ),
                    cls="border-t border-slate-200 dark:border-slate-700",
                )
            )
        body = Div(
            Table(
                Thead(
                    Tr(
                        Th("Slug", cls="px-4 py-2 text-left text-xs font-semibold text-slate-600 uppercase"),
                        Th("Author", cls="px-4 py-2 text-left text-xs font-semibold text-slate-600 uppercase"),
                        Th("Comments", cls="px-4 py-2 text-right text-xs font-semibold text-slate-600 uppercase"),
                        Th("Captured", cls="px-4 py-2 text-left text-xs font-semibold text-slate-600 uppercase"),
                        Th("Status", cls="px-4 py-2 text-left text-xs font-semibold text-slate-600 uppercase"),
                        Th("", cls="px-4 py-2"),
                    ),
                ),
                Tbody(*rows),
                cls="w-full",
            ),
            cls=_CARD_CLS + " p-0 overflow-x-auto",
        )

    return Div(
        H1("Rhodes Inbox", cls=_HEADER_CLS),
        P(
            "Inbox entries from rhodes-wiki awaiting rhodesli admin review. ",
            "Approve → photo enters rhodesli upload pipeline with prefill. ",
            "Local-dev only; production returns 404.",
            cls=_SUB_CLS,
        ),
        tabs,
        body,
        cls=_PAGE_WRAP,
    )


def _render_detail_view(slug: str, entry: dict) -> Any:
    """Render the detail view for one inbox entry."""
    caption_text = (entry.get("caption") or {}).get("text", "") or "(no caption)"
    fb_post_url = entry.get("fb_post_url") or ""
    fb_post_id = entry.get("fb_post_id") or ""
    captured_at = entry.get("captured_at") or ""
    comments = entry.get("comments") or []
    images = entry.get("images") or []
    reactions = entry.get("reactions_count")
    author = (entry.get("post_author") or {}).get("name") or "(unknown)"

    # Kinship triples (cached or computed)
    try:
        triples = kinship_triples_for(slug, state="pending")
    except Exception:  # noqa: BLE001
        triples = []

    # Header
    header = Div(
        Div(
            A("← Rhodes Inbox", href="/admin/rhodes-inbox", cls="text-sm text-slate-500 hover:text-slate-700"),
            cls="mb-2",
        ),
        H1(f"Entry: {slug}", cls="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100 mb-1"),
        P(
            f"Author: {author} · ",
            f"Captured: {captured_at[:10] if captured_at else '—'} · ",
            f"Comments: {len(comments)} · ",
            f"Reactions: {reactions or 0}",
            cls=_SUB_CLS,
        ),
        cls="mb-4",
    )

    # FB post link + image links + copy buttons
    image_block_children = []
    for img in images:
        original_url = img.get("original_url") or ""
        fb_photo_id = img.get("fb_photo_id") or ""
        alt = img.get("alt_text") or img.get("alt") or ""
        image_block_children.append(
            Div(
                P(f"Image: {alt}", cls="text-sm font-medium mb-2"),
                P(f"FB photo ID: ", Code(fb_photo_id, cls="font-mono text-xs"), cls="text-sm mb-2"),
                Div(
                    A("Open FB photo", href=original_url, target="_blank", cls=_BTN_NEUTRAL),
                    Button("Copy FB URL", type="button",
                           onclick=f"navigator.clipboard.writeText({original_url!r}); this.textContent='Copied!'; setTimeout(()=>this.textContent='Copy FB URL', 1500);",
                           cls=_BTN_NEUTRAL),
                    cls="flex gap-2",
                ),
                cls="bg-slate-50 dark:bg-slate-900 rounded p-3 mb-2",
            )
        )

    source_block = Div(
        H2("Source", cls="text-lg font-semibold mb-3"),
        P(
            "FB post: ",
            A(fb_post_url, href=fb_post_url, target="_blank", cls="text-indigo-600 hover:underline break-all"),
            cls="text-sm mb-3",
        ),
        *image_block_children,
        cls=_CARD_CLS,
    )

    # Caption
    caption_block = Div(
        H2("Caption", cls="text-lg font-semibold mb-3"),
        Pre(caption_text, cls="whitespace-pre-wrap text-sm bg-slate-50 dark:bg-slate-900 rounded p-4"),
        cls=_CARD_CLS,
    )

    # Comments
    comment_items = []
    for c in comments:
        c_author = (c.get("author") or {}).get("name") if isinstance(c.get("author"), dict) else c.get("author_name", "?")
        c_text = c.get("text") or ""
        c_depth = int(c.get("depth") or 0)
        indent_cls = "ml-8 border-l-2 border-slate-300 dark:border-slate-600 pl-4" if c_depth > 0 else ""
        comment_items.append(
            Div(
                P(c_author or "(anonymous)", cls="text-sm font-semibold text-slate-900 dark:text-slate-100"),
                P(c_text, cls="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap"),
                cls=f"py-2 {indent_cls}",
            )
        )

    comments_block = Div(
        H2(f"Comments ({len(comments)})", cls="text-lg font-semibold mb-3"),
        Div(*comment_items, cls="space-y-1"),
        cls=_CARD_CLS,
    )

    # Kinship triples
    if triples:
        triple_rows = []
        for t in triples:
            triple_rows.append(
                Li(
                    Span(t.get("subject", ""), cls="font-medium"),
                    Span(" → ", cls="text-slate-400 mx-1"),
                    Span(t.get("relation", ""), cls="text-indigo-600 font-mono text-xs"),
                    Span(" → ", cls="text-slate-400 mx-1"),
                    Span(t.get("object", ""), cls="font-medium"),
                    Span(f" ({t.get('confidence', '?')})", cls="text-slate-500 text-xs ml-2"),
                    cls="text-sm py-1",
                )
            )
        kinship_block = Div(
            H2(f"Auto-extracted Kinship Triples ({len(triples)})", cls="text-lg font-semibold mb-2"),
            P(
                "Computed by app.extract_kinship.extract_kinship_from_post. ",
                "Manual review required — some triples may be over-strong or imprecise (Session 160 P2-E known issue).",
                cls="text-xs text-slate-500 mb-3",
            ),
            Ul(*triple_rows, cls="space-y-0.5"),
            cls=_CARD_CLS,
        )
    else:
        kinship_block = Div()

    # Approve / Reject forms
    actions_block = Div(
        H2("Actions", cls="text-lg font-semibold mb-3"),
        Form(
            # CSRF protection: server-side `_check_origin(request)` in the
            # admin_rhodes_inbox_approve handler validates the Origin header
            # against the canonical site host. No hidden token field needed.
            Textarea(name="notes", placeholder="Optional notes (caption corrections, identity hints, etc.)",
                     rows="2", cls="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm mb-2"),
            Button("Approve → Open Upload Form", type="submit", cls=_BTN_PRIMARY),
            method="post",
            action=f"/admin/rhodes-inbox/{slug}/approve",
            cls="mb-4",
        ),
        Form(
            Textarea(name="reason", placeholder="Rejection reason (required, will be persisted)",
                     rows="2", required="required",
                     cls="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm mb-2"),
            Button("Reject", type="submit", cls=_BTN_DANGER),
            method="post",
            action=f"/admin/rhodes-inbox/{slug}/reject",
        ),
        cls=_CARD_CLS,
    )

    return Div(
        header,
        source_block,
        caption_block,
        comments_block,
        kinship_block,
        actions_block,
        cls=_PAGE_WRAP,
    )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_admin_rhodes_inbox_routes(app) -> None:
    """Register the 4 admin routes on the FastHTML app.

    Imports `_check_admin` and `_check_origin` lazily to avoid a circular
    import (app.main imports this module back via this function at startup).
    """

    @app.get("/admin/rhodes-inbox")
    def admin_rhodes_inbox_list(sess, state: str = "pending"):
        if not is_rhodes_wiki_available():
            return Response("", status_code=404)
        from app.main import _check_admin  # noqa: PLC0415
        guard = _check_admin(sess)
        if guard is not None:
            return guard
        if state not in ("pending", "approved", "rejected"):
            state = "pending"
        return _render_list_view(state=state)

    @app.get("/admin/rhodes-inbox/{slug}")
    def admin_rhodes_inbox_detail(slug: str, sess):
        if not is_rhodes_wiki_available():
            return Response("", status_code=404)
        from app.main import _check_admin  # noqa: PLC0415
        guard = _check_admin(sess)
        if guard is not None:
            return guard
        try:
            _validate_slug(slug)
        except ValueError:
            return Response("invalid slug", status_code=400)
        try:
            entry = load_entry(slug, state="pending")
        except FileNotFoundError:
            # Try approved/rejected
            try:
                entry = load_entry(slug, state="approved")
            except FileNotFoundError:
                try:
                    entry = load_entry(slug, state="rejected")
                except FileNotFoundError:
                    return Response("not found", status_code=404)
        return _render_detail_view(slug, entry)

    @app.post("/admin/rhodes-inbox/{slug}/approve")
    def admin_rhodes_inbox_approve(slug: str, sess, request, notes: str = ""):
        if not is_rhodes_wiki_available():
            return Response("", status_code=404)
        from app.main import _check_admin  # noqa: PLC0415
        from app.auth import _check_origin, User  # noqa: PLC0415
        # CSRF check FIRST (Codex P1-1)
        origin_err = _check_origin(request)
        if origin_err is not None:
            return origin_err
        guard = _check_admin(sess)
        if guard is not None:
            return guard
        try:
            _validate_slug(slug)
        except ValueError:
            return Response("invalid slug", status_code=400)
        user = User.from_session(sess) if sess else None
        approved_by = user.email if user else "admin"
        try:
            mark_approved(slug, approved_by=approved_by)
        except AlreadyApprovedError:
            # Race-loser or retry: treat as success-equivalent
            return RedirectResponse(
                f"/admin/rhodes-inbox/{slug}?msg=already_approved",
                status_code=303,
            )
        except FileNotFoundError:
            return Response("not found", status_code=404)
        # Redirect to upload form with prefill
        return RedirectResponse(f"/upload?prefill={slug}", status_code=303)

    @app.post("/admin/rhodes-inbox/{slug}/reject")
    def admin_rhodes_inbox_reject(slug: str, sess, request, reason: str = ""):
        if not is_rhodes_wiki_available():
            return Response("", status_code=404)
        from app.main import _check_admin  # noqa: PLC0415
        from app.auth import _check_origin, User  # noqa: PLC0415
        origin_err = _check_origin(request)
        if origin_err is not None:
            return origin_err
        guard = _check_admin(sess)
        if guard is not None:
            return guard
        try:
            _validate_slug(slug)
        except ValueError:
            return Response("invalid slug", status_code=400)
        user = User.from_session(sess) if sess else None
        rejected_by = user.email if user else "admin"
        try:
            mark_rejected(slug, rejected_by=rejected_by, reason=(reason or "")[:4096])
        except AlreadyRejectedError:
            return RedirectResponse(f"/admin/rhodes-inbox?msg=already_rejected", status_code=303)
        except FileNotFoundError:
            return Response("not found", status_code=404)
        return RedirectResponse("/admin/rhodes-inbox", status_code=303)
