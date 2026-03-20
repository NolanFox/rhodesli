"""
Person routes extracted from app/main.py.

All /person/* and /api/person/* routes plus person-exclusive helpers.
Shared helpers (caches, registries, UI builders) remain in app.main.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta

from fasthtml.common import *
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.auth import get_current_user
from core.ui_safety import ensure_utf8_display

# Import route decorator only (bound once, never reassigned)
from app.main import rt
from app.utils import photo_url, _section_for_state

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)


def _detect_person_community(person_id: str) -> str | None:
    """Detect which community a person belongs to by checking identity_communities.

    Returns the community slug if the person belongs to a non-default community,
    or None if rhodes/unknown. Used for auto-redirect on /person/{id} without prefix.
    """
    try:
        from app.supabase_data import load_communities

        communities = load_communities() or []
        for comm in communities:
            slug = comm.get("slug", "")
            if slug == "rhodes":
                continue  # Skip default — no redirect needed
            comm_ids = _main_mod._get_community_identity_ids(comm)
            if comm_ids and person_id in comm_ids:
                return slug
    except Exception:
        pass
    return None


# =============================================================================
# HELPERS — Person-exclusive (not used outside person routes)
# =============================================================================

# --- Person Comments ---
# _load_person_comments, _save_person_comments, and _person_comments_cache
# remain in app.main so that test patches on app.main work correctly.


def _bbox_iou(box_a, box_b) -> float:
    """Compute IoU for two [x1, y1, x2, y2] boxes."""
    if not box_a or not box_b or len(box_a) < 4 or len(box_b) < 4:
        return 0.0
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(ax2 - ax1, 0) * max(ay2 - ay1, 0)
    area_b = max(bx2 - bx1, 0) * max(by2 - by1, 0)
    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def _name_provenance_line(person_id: str, is_admin: bool):
    """Show provenance of this person's name — who suggested it, when approved.

    Only shown for admins. Returns None if no provenance is available.
    """
    if not is_admin:
        return None

    try:
        annotations = _main_mod._load_annotations()
        for ann in annotations.get("annotations", {}).values():
            if (
                ann.get("target_id") == person_id
                and ann.get("type") == "name_suggestion"
                and ann.get("status") == "approved"
            ):
                parts = []
                if ann.get("submitted_by"):
                    parts.append(f"Suggested by {ann['submitted_by']}")
                if ann.get("submitted_at"):
                    parts.append(f"on {ann['submitted_at'][:10]}")
                if ann.get("reviewed_by"):
                    parts.append(f"approved by {ann['reviewed_by']}")
                if ann.get("reviewed_at"):
                    parts.append(f"on {ann['reviewed_at'][:10]}")
                if parts:
                    return P(
                        " · ".join(parts),
                        cls="text-xs text-slate-500 mt-1",
                        data_testid="name-provenance",
                    )
    except Exception:
        pass
    return None


def _photo_context_conflict(photo_meta: dict | None, registry, person_id: str) -> bool:
    """Return True when this person's presence in the photo is disputed."""
    if not photo_meta or not person_id:
        return False

    face_infos = []
    for face in photo_meta.get("faces", []):
        bbox = face.get("bbox") or []
        if len(bbox) < 4:
            continue
        identity = _main_mod.get_identity_for_face(registry, face.get("face_id", ""))
        if not identity:
            continue
        face_infos.append(
            {
                "bbox": bbox,
                "identity_id": identity.get("identity_id"),
                "state": identity.get("state", "INBOX"),
            }
        )

    context_faces = [fi for fi in face_infos if fi.get("identity_id") == person_id]
    if not context_faces:
        return False
    if any(fi.get("state") in {"REJECTED", "CONTESTED"} for fi in context_faces):
        return True

    for context_face in context_faces:
        for other in face_infos:
            if other is context_face or other.get("identity_id") == person_id:
                continue
            if _bbox_iou(context_face["bbox"], other["bbox"]) >= 0.8:
                return True
    return False


def _life_events_section(person_id: str, nav_prefix: str = ""):
    """Build the life events section for person pages (PRD-011). Lazy import to avoid circular."""
    from app.event_routes import person_events_section

    return person_events_section(person_id, nav_prefix=nav_prefix)


def _person_comments_section(person_id: str, is_admin: bool = False):
    """Build the comments section for person pages."""
    comments_data = _main_mod._load_person_comments()
    person_comments = comments_data.get("comments", {}).get(person_id, [])
    visible_comments = [c for c in person_comments if c.get("status", "visible") == "visible"]

    comment_items = []
    for c in visible_comments:
        author = c.get("author", "Anonymous")
        text = c.get("text", "")
        ts = c.get("timestamp", "")
        date_str = ts[:10] if ts else ""

        hide_btn = None
        if is_admin:
            hide_btn = Button(
                "Hide",
                hx_post=f"/api/person/{person_id}/comment/{c.get('id', '')}/hide",
                hx_target=f"#comment-{c.get('id', '')}",
                hx_swap="outerHTML",
                cls="text-xs text-rose-400 hover:text-rose-300 ml-2",
            )

        comment_items.append(
            Div(
                Div(
                    Span(author, cls="text-sm font-medium text-slate-300"),
                    Span(f" · {date_str}", cls="text-xs text-slate-600") if date_str else None,
                    hide_btn,
                    cls="flex items-center mb-1",
                ),
                P(text, cls="text-sm text-slate-400 leading-relaxed"),
                cls="py-3 border-b border-slate-800/50 last:border-0",
                id=f"comment-{c.get('id', '')}",
            )
        )

    # Comment form (no login required)
    form = Form(
        Input(type="hidden", name="person_id", value=person_id),
        Div(
            Input(
                type="text",
                name="author",
                placeholder="Your name (optional)",
                cls="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
            ),
            cls="mb-3",
        ),
        Div(
            Textarea(
                name="text",
                placeholder="Share a memory, correction, or anything you know about this person...",
                rows=3,
                cls="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none resize-none",
            ),
            cls="mb-3",
        ),
        Button(
            "Post Comment",
            type="submit",
            cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
        ),
        hx_post=f"/api/person/{person_id}/comment",
        hx_target="#person-comments-list",
        hx_swap="innerHTML",
    )

    return Div(
        H3(f"Comments ({len(visible_comments)})", cls="text-3xl font-serif tracking-tight text-white mb-6"),
        Div(*comment_items, id="person-comments-list")
        if comment_items
        else Div(
            P("No comments yet. Be the first to share a memory!", cls="text-sm text-slate-500 italic"),
            id="person-comments-list",
        ),
        Div(form, cls="mt-6"),
        cls="mt-10 pt-8 border-t border-slate-800",
        data_testid="comments-section",
    )


def public_person_page(
    person_id: str,
    view: str = "faces",
    sort_by: str = "date_asc",
    user=None,
    is_admin: bool = False,
    community_slug: str = "rhodes",
) -> tuple:
    """
    Build the public shareable person page.

    Shows all photos of a specific identified person — the page you share
    when you want to say "Look at all these photos of Aunt Selma!"
    No authentication required.
    """
    registry = _main_mod.load_registry()
    nav_prefix = _main_mod.community_url_prefix(community_slug)
    try:
        identity = registry.get_identity(person_id)
    except KeyError:
        identity = None

    # UX-038: Redirect merged identities to canonical person
    if identity and identity.get("merged_into"):
        canonical_id = identity["merged_into"]
        return RedirectResponse(f"{nav_prefix}/person/{canonical_id}", status_code=301)

    if not identity:
        style_404 = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
        page_html = (
            to_xml(
                Title("Person Not Found - Rhodesli"),
            )
            + to_xml(style_404)
            + to_xml(
                Main(
                    Nav(
                        Div(
                            A(
                                Span("Rhodesli", cls="text-xl font-bold text-white"),
                                href=f"{nav_prefix}/",
                                cls="hover:opacity-90",
                            ),
                            cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                        ),
                        cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800",
                    ),
                    Div(
                        Div(
                            Span("404", cls="text-6xl font-bold text-slate-700 block mb-4"),
                            H1("Person not found", cls="text-2xl font-serif font-bold text-white mb-3"),
                            P("This person hasn't been identified in our archive yet.", cls="text-slate-400 mb-8"),
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

    raw_name = ensure_utf8_display(identity.get("name"))
    display_name = raw_name or f"Person {person_id[:8]}"
    state = identity.get("state", "INBOX")
    is_state_confirmed = state == "CONFIRMED"
    is_confirmed = is_state_confirmed and not display_name.startswith("Unidentified")
    target_proposals = _main_mod._get_proposal_targets_for_identity(person_id) if is_admin else []
    similar_container_id = f"person-similar-{person_id}"

    def _person_photo_href(photo_id: str) -> str:
        if not photo_id:
            return "#"
        return f"{nav_prefix}/photo/{photo_id}?identity_id={person_id}&sort_by={sort_by}"

    # Get all face IDs for this person
    anchor_ids = identity.get("anchor_ids", [])
    candidate_ids = identity.get("candidate_ids", [])
    all_face_ids = anchor_ids + candidate_ids
    face_id_strings = [f if isinstance(f, str) else f.get("face_id", "") for f in all_face_ids]

    # Get photos where this person appears
    photo_reg = _main_mod.load_photo_registry()
    photo_ids = photo_reg.get_photos_for_faces(face_id_strings)
    crop_files = _main_mod.get_crop_files()

    # Get best face crop for avatar
    best_face_id = _main_mod.get_best_face_id(all_face_ids)
    avatar_url = _main_mod.resolve_face_image_url(best_face_id, crop_files) if best_face_id and crop_files else None

    if sort_by not in {"date_asc", "date_desc", "uploaded_desc", "uploaded_asc"}:
        sort_by = "date_asc"

    date_labels = _main_mod._load_date_labels()

    def _is_unresolved_face(face_id: str) -> bool:
        ident = _main_mod.get_identity_for_face(registry, face_id)
        ident_state = ident.get("state", "INBOX") if ident else None
        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))

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

    def _build_sort_meta(photo_id: str, pm: dict | None):
        pm = pm or {}
        year = _parse_year((date_labels.get(photo_id) or {}).get("best_year_estimate"))
        if year is None:
            year = _parse_year(pm.get("date_taken"))
        uploaded_ts = _parse_uploaded_timestamp(pm.get("created_at") or pm.get("updated_at"))
        return {
            "year": year,
            "has_year": year is not None,
            "uploaded_ts": uploaded_ts,
            "has_uploaded_ts": uploaded_ts is not None,
        }

    def _gallery_sort_key(sort_meta: dict, stable: str):
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

    # Get collections this person appears in
    collections = set()
    for pid in photo_ids:
        pm = _main_mod.get_photo_metadata(pid)
        if pm and pm.get("collection"):
            collections.add(pm["collection"])

    # --- Build face gallery items ---
    face_entries = []
    for face_id_entry in all_face_ids:
        fid = face_id_entry if isinstance(face_id_entry, str) else face_id_entry.get("face_id", "")
        crop_url = _main_mod.resolve_face_image_url(fid, crop_files) if crop_files else None
        if not crop_url:
            continue
        # Find the photo for this face
        face_photo_id = _main_mod.get_photo_id_for_face(fid)
        face_photo = _main_mod.get_photo_metadata(face_photo_id) if face_photo_id else None
        context_conflict = _photo_context_conflict(face_photo, registry, person_id)
        source_label = ""
        if face_photo:
            source_label = face_photo.get("collection", "") or face_photo.get("source", "") or ""

        face_entries.append(
            {
                "sort_key": _gallery_sort_key(
                    _build_sort_meta(face_photo_id, face_photo), f"{face_photo_id or 'zz'}:{fid}"
                ),
                "item": A(
                    Div(
                        Img(
                            src=crop_url,
                            alt=f"{display_name}",
                            cls="w-full aspect-square object-cover",
                            onerror="this.style.display='none'",
                        ),
                        Span(
                            "Needs review",
                            cls="absolute top-2 left-2 bg-rose-500/85 text-white text-[10px] font-medium px-2 py-0.5 rounded-full shadow-sm",
                            data_testid="person-gallery-conflict",
                        )
                        if context_conflict
                        else None,
                        Div(
                            P(source_label, cls="text-[10px] text-white/90 text-center truncate w-full leading-snug")
                            if source_label
                            else None,
                            cls="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-900/90 to-transparent pt-6 pb-2 px-2 opacity-0 group-hover:opacity-100 transition-opacity flex justify-center items-end z-20",
                        )
                        if source_label
                        else None,
                        cls="relative w-full aspect-square rounded-lg overflow-hidden cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:z-30 hover:ring-2 hover:ring-indigo-400/50 shadow-sm bg-slate-800",
                    ),
                    href=_person_photo_href(face_photo_id),
                    onclick="event.preventDefault(); window.openLightbox(this.href, this.querySelector('img').src);",
                    cls="flex flex-col group block outline-none",
                    title=f"View photo of {display_name}",
                    data_testid="person-gallery-item-conflicted" if context_conflict else None,
                ),
            }
        )

    face_entries.sort(key=lambda entry: entry["sort_key"])
    face_gallery_items = [entry["item"] for entry in face_entries]

    # --- Build photo gallery items ---
    photo_entries = []
    for pid in photo_ids:
        pm = _main_mod.get_photo_metadata(pid)
        if not pm:
            continue
        filename = pm["filename"]
        collection_label = pm.get("collection", "") or ""
        context_conflict = _photo_context_conflict(pm, registry, person_id)
        photo_entries.append(
            {
                "sort_key": _gallery_sort_key(_build_sort_meta(pid, pm), pid),
                "item": A(
                    Div(
                        Img(
                            src=photo_url(filename),
                            alt=f"Photo featuring {display_name}",
                            cls="w-full h-auto rounded-lg shadow-sm",
                            loading="lazy",
                        ),
                        Span(
                            "Needs review",
                            cls="absolute top-2 left-2 bg-rose-500/85 text-white text-[10px] font-medium px-2 py-0.5 rounded-full shadow-sm",
                            data_testid="person-gallery-conflict",
                        )
                        if context_conflict
                        else None,
                        cls="relative overflow-hidden rounded-lg",
                    ),
                    P(
                        "Conflicting face assignment",
                        cls="text-[10px] text-rose-300 mt-2 text-center leading-snug",
                    )
                    if context_conflict
                    else None,
                    P(collection_label, cls="text-sm italic text-slate-400 mt-2 text-center leading-snug")
                    if collection_label
                    else None,
                    href=_person_photo_href(pid),
                    onclick="event.preventDefault(); window.openLightbox(this.href, this.querySelector('img').src);",
                    cls="flex flex-col group mb-6 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:z-30 cursor-pointer outline-none",
                    title=f"View photo of {display_name}",
                    data_testid="person-gallery-item-conflicted" if context_conflict else None,
                ),
            }
        )

    photo_entries.sort(key=lambda entry: entry["sort_key"])
    photo_gallery_items = [entry["item"] for entry in photo_entries]

    # --- Build "Appears with" section ---
    appears_with = []
    for pid in photo_ids:
        pm = _main_mod.get_photo_metadata(pid)
        if not pm:
            continue
        for face_data in pm.get("faces", []):
            other_fid = face_data.get("face_id", "")
            if other_fid in face_id_strings:
                continue  # skip self
            other_identity = _main_mod.get_identity_for_face(registry, other_fid)
            if not other_identity:
                continue
            other_id = other_identity["identity_id"]
            other_state = other_identity.get("state", "")
            other_name = ensure_utf8_display(other_identity.get("name", ""))
            if other_state != "CONFIRMED" or other_name.startswith("Unidentified"):
                continue
            if other_id == person_id:
                continue
            # Avoid duplicates
            if any(a["id"] == other_id for a in appears_with):
                continue
            other_best_face = _main_mod.get_best_face_id(
                other_identity.get("anchor_ids", []) + other_identity.get("candidate_ids", [])
            )
            other_crop = (
                _main_mod.resolve_face_image_url(other_best_face, crop_files)
                if other_best_face and crop_files
                else None
            )
            appears_with.append(
                {
                    "id": other_id,
                    "name": other_name,
                    "crop_url": other_crop,
                }
            )

    appears_with_section = None
    if appears_with:
        companion_cards = []
        shown = appears_with[:8]
        for companion in shown:
            crop_el = (
                Img(
                    src=companion["crop_url"],
                    alt=companion["name"],
                    cls="w-16 h-16 sm:w-20 sm:h-20 rounded-lg object-cover cursor-pointer group-hover:ring-2 transition-all duration-300 group-hover:scale-[1.05] group-hover:shadow-lg group-hover:ring-2 group-hover:ring-indigo-400/50 shadow-sm bg-slate-800",
                    onerror="this.style.display='none'",
                )
                if companion["crop_url"]
                else Div(
                    cls="w-16 h-16 sm:w-20 sm:h-20 rounded-lg bg-slate-800/50 border border-slate-700 border-dashed flex items-center justify-center opacity-70 cursor-pointer group-hover:ring-2 group-hover:ring-amber-400 transition-all",
                )
            )
            companion_cards.append(
                A(
                    crop_el,
                    Span(
                        companion["name"],
                        cls="text-[10px] sm:text-xs text-slate-400 mt-1.5 text-center truncate w-full",
                        title=companion["name"],
                    ),
                    href=f"{nav_prefix}/person/{companion['id']}",
                    cls="flex flex-col items-center gap-1 group w-16 sm:w-20",
                    title=f"View {companion['name']}",
                )
            )
        if len(appears_with) > 8:
            companion_cards.append(
                Span(f"+{len(appears_with) - 8} more", cls="text-xs text-slate-500 self-center ml-2")
            )
        appears_with_section = Div(
            H3("Often appears with", cls="text-3xl font-serif tracking-tight text-white mb-6"),
            Div(*companion_cards, cls="flex flex-wrap gap-4 sm:gap-6 items-start"),
            cls="mt-10 pt-8 border-t border-slate-800",
        )

    # --- Family relationships (from GEDCOM import) ---
    family_section = None
    try:
        rel_graph = _main_mod._load_relationship_graph()
        if rel_graph.get("relationships"):
            from rhodesli_ml.graph.relationship_graph import get_relationships_for_person

            rels = get_relationships_for_person(rel_graph, person_id)

            family_items = []
            rel_labels = {
                "parents": "Parents",
                "children": "Children",
                "spouses": "Spouse",
                "siblings": "Siblings",
            }
            for rel_type, label in rel_labels.items():
                rel_ids = rels.get(rel_type, [])
                if not rel_ids:
                    continue
                names = []
                for rid in rel_ids:
                    try:
                        r_ident = registry.get_identity(rid)
                        r_name = ensure_utf8_display(r_ident.get("name", "Unknown"))
                        names.append(
                            A(
                                r_name,
                                href=f"{nav_prefix}/person/{rid}",
                                cls="text-indigo-400 hover:text-indigo-300 underline",
                            )
                        )
                    except KeyError:
                        continue
                if names:
                    separator = []
                    for i, n in enumerate(names):
                        if i > 0:
                            separator.append(Span(", ", cls="text-slate-500"))
                        separator.append(n)
                    family_items.append(
                        Div(
                            Span(f"{label}: ", cls="text-slate-400 text-sm font-medium w-20 inline-block"),
                            *separator,
                            cls="text-sm py-1",
                        )
                    )

            if family_items:
                family_items.append(
                    A(
                        "View in Family Tree →",
                        href=f"{nav_prefix}/tree?person={person_id}",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 mt-3 inline-block",
                        data_testid="family-tree-link",
                    ),
                )
                family_section = Div(
                    H3("Family", cls="text-3xl font-serif tracking-tight text-white mb-6"),
                    *family_items,
                    cls="mt-10 pt-8 border-t border-slate-800",
                )
    except Exception:
        pass  # Graceful degradation if graph not available

    # --- Closest connections (from social graph) ---
    connections_section = None
    try:
        from rhodesli_ml.graph.social_graph import build_social_graph, get_closest_connections

        social = build_social_graph(
            _main_mod._load_relationship_graph(),
            json.loads((_main_mod.data_path / "co_occurrence_graph.json").read_text(encoding="utf-8"))
            if (_main_mod.data_path / "co_occurrence_graph.json").exists()
            else {"edges": []},
        )
        closest = get_closest_connections(social, person_id, n=5)
        if closest:
            conn_items = []
            for conn in closest:
                try:
                    c_ident = registry.get_identity(conn["person_id"])
                    c_name = ensure_utf8_display(c_ident.get("name", "Unknown"))
                except (KeyError, TypeError):
                    continue
                edge_type = conn.get("edge_type", "indirect")
                if edge_type == "spouse_of":
                    badge = Span("Spouse", cls="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 ml-2")
                elif edge_type in ("parent_child", "child_of"):
                    badge = Span("Family", cls="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 ml-2")
                elif edge_type == "sibling_of":
                    badge = Span("Sibling", cls="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 ml-2")
                elif edge_type == "photographed_with":
                    photo_ct = conn.get("photo_count", 0)
                    photo_label = f"{photo_ct} shared photo{'s' if photo_ct != 1 else ''}" if photo_ct else "Photos"
                    badge = Span(
                        photo_label, cls="text-[10px] px-1.5 py-0.5 rounded bg-indigo-900/40 text-indigo-400 ml-2"
                    )
                else:
                    steps = conn.get("path_length", 0)
                    badge = Span(
                        f"{steps} step{'s' if steps != 1 else ''}",
                        cls="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 ml-2",
                    )
                conn_items.append(
                    Div(
                        A(
                            c_name,
                            href=f"{nav_prefix}/person/{conn['person_id']}",
                            cls="text-indigo-400 hover:text-indigo-300 text-sm",
                        ),
                        badge,
                        cls="flex items-center py-1",
                    )
                )
            if conn_items:
                conn_items.append(
                    Div(
                        A(
                            "Find connections →",
                            href=f"{nav_prefix}/connect?person_a={person_id}",
                            cls="text-xs text-indigo-400 hover:text-indigo-300 mr-4",
                        ),
                        A(
                            "View in Tree →",
                            href=f"{nav_prefix}/tree?person={person_id}",
                            cls="text-xs text-indigo-400 hover:text-indigo-300",
                        ),
                        cls="mt-2 flex gap-4",
                    )
                )
                connections_section = Div(
                    H3("Connections", cls="text-3xl font-serif tracking-tight text-white mb-6"),
                    *conn_items,
                    cls="mt-10 pt-8 border-t border-slate-800",
                    data_testid="connections-section",
                )
    except Exception:
        pass  # Graceful degradation

    # --- Approved annotations (bio, story, etc.) ---
    annotations_section = None
    try:
        annotations_data = _main_mod._load_annotations()
        approved_anns = [
            ann
            for ann in annotations_data.get("annotations", {}).values()
            if ann.get("target_type") == "identity"
            and ann.get("target_id") == person_id
            and ann.get("status") == "approved"
        ]
        if approved_anns:
            type_labels = {
                "bio": "Bio",
                "relationship": "Relationship",
                "story": "Story",
                "name_suggestion": "Name",
                "caption": "Caption",
            }
            # Deduplicate by value
            seen_values = set()
            unique_anns = []
            for ann in sorted(approved_anns, key=lambda a: a.get("submitted_at", "")):
                if ann["value"] not in seen_values:
                    seen_values.add(ann["value"])
                    unique_anns.append(ann)
            ann_items = []
            for ann in unique_anns:
                label = type_labels.get(ann["type"], ann["type"].title())
                ann_items.append(
                    Div(
                        Span(f"{label}", cls="text-xs text-slate-500 font-medium block mb-0.5"),
                        P(f"\u201c{ann['value']}\u201d", cls="text-slate-300 text-sm italic"),
                        cls="py-2",
                    )
                )
            annotations_section = Div(
                H3("Community Notes", cls="text-3xl font-serif tracking-tight text-white mb-6"),
                *ann_items,
                cls="mt-10 pt-8 border-t border-slate-800",
            )
    except Exception:
        pass

    # --- Open Graph meta tags ---
    og_title = f"{display_name} — Rhodesli Heritage Archive"
    photo_count = len(photo_ids)
    collection_count = len(collections)
    if photo_count > 0:
        og_description = f"Appears in {photo_count} {'photo' if photo_count == 1 else 'photos'} across {collection_count} {'collection' if collection_count == 1 else 'collections'}. Help identify more photos of {display_name}."
    else:
        og_description = (
            f"{display_name} in the Rhodesli Heritage Archive. Explore photographs from the Jewish community of Rhodes."
        )

    og_image_url = avatar_url or ""
    if og_image_url and not og_image_url.startswith("http"):
        og_image_url = f"{_main_mod.SITE_URL}{og_image_url}"
    og_page_url = f"{_main_mod.SITE_URL}{nav_prefix}/person/{person_id}"

    og_meta_tags = (
        Meta(property="og:title", content=og_title),
        Meta(property="og:description", content=og_description),
        Meta(property="og:image", content=og_image_url),
        Meta(property="og:url", content=og_page_url),
        Meta(property="og:type", content="profile"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary"),
        Meta(name="twitter:title", content=og_title),
        Meta(name="twitter:description", content=og_description),
        Meta(name="twitter:image", content=og_image_url),
        Meta(name="description", content=og_description),
    )

    # --- Navigation ---
    nav_links = _main_mod._public_nav_links(active="people", user=user, community_slug=community_slug)
    workstation_prefix = _main_mod.community_url_prefix(community_slug)
    has_tree_link = (
        bool(_main_mod._load_gedcom_face_links().get(person_id) or identity.get("gedcom_xref")) if is_admin else False
    )

    # --- View toggle (HTMX partial swap for fast switching) ---
    faces_active = view != "photos"
    toggle = Div(
        Button(
            "Faces",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors "
            + ("bg-indigo-600 text-white" if faces_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"),
            hx_get=f"{workstation_prefix}/api/person/{person_id}/gallery?view=faces&sort_by={sort_by}",
            hx_target="#person-gallery-container",
            hx_swap="innerHTML",
            type="button",
        ),
        Button(
            "Photos",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors "
            + (
                "bg-indigo-600 text-white"
                if not faces_active
                else "text-slate-400 hover:text-white hover:bg-slate-700/50"
            ),
            hx_get=f"{workstation_prefix}/api/person/{person_id}/gallery?view=photos&sort_by={sort_by}",
            hx_target="#person-gallery-container",
            hx_swap="innerHTML",
            type="button",
        ),
        cls="flex gap-1 bg-slate-800/50 p-1 rounded-xl",
    )

    sort_select = Select(
        Option("Earliest First \u2191", value="date_asc", selected=(sort_by == "date_asc")),
        Option("Earliest Last \u2193", value="date_desc", selected=(sort_by == "date_desc")),
        Option("Newest Uploads \u2191", value="uploaded_desc", selected=(sort_by == "uploaded_desc")),
        Option("Oldest Uploads \u2193", value="uploaded_asc", selected=(sort_by == "uploaded_asc")),
        cls="bg-slate-800/80 hover:bg-slate-700 border border-slate-600 text-white font-medium text-sm rounded-lg px-4 py-2 cursor-pointer focus:ring-2 focus:ring-indigo-400/50 transition-colors shadow-sm active:scale-95",
        hx_get=f"{workstation_prefix}/api/person/{person_id}/gallery?view={'faces' if faces_active else 'photos'}",
        hx_target="#person-gallery-container",
        hx_swap="innerHTML",
        hx_trigger="change",
        hx_include="this",
        name="sort_by",
        aria_label="Sort gallery",
    )

    # --- Gallery content ---
    gallery_items = face_gallery_items if faces_active else photo_gallery_items
    gallery_count = len(gallery_items)
    gallery_grid_cls = (
        "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 sm:gap-4"
        if faces_active
        else "columns-2 sm:columns-3 lg:columns-4 gap-4 sm:gap-6 space-y-4 sm:space-y-6"
    )

    if gallery_items:
        gallery_content = Div(*gallery_items, cls=gallery_grid_cls)
    else:
        gallery_content = Div(
            P("No photos available yet.", cls="text-slate-500 text-center py-8"),
        )

    # --- Status badge ---
    if is_state_confirmed:
        badge = Span(
            "Confirmed",
            cls="text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 transition-all duration-300 hover:ring-2 hover:ring-indigo-400/50",
            title="This person has been confirmed by an admin",
        )
    else:
        badge = Span(
            "Under Review",
            cls="text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20 cursor-help transition-all duration-300 hover:ring-2 hover:ring-indigo-400/50",
            title="This identity is awaiting admin review",
        )

    # --- Birth year (Gatekeeper: public sees confirmed only, admin sees ML estimates) ---
    # Public: only confirmed metadata birth years
    person_birth_year, by_source, by_confidence = _main_mod._get_birth_year(
        person_id, identity, include_unreviewed=False
    )
    birth_year_line = None
    if person_birth_year:
        birth_year_line = f"Born {person_birth_year}"

    # Admin: also check for pending ML suggestion
    ml_suggestion_card = None
    if is_admin and not person_birth_year:
        _admin_by, _admin_src, _admin_conf = _main_mod._get_birth_year(person_id, identity, include_unreviewed=True)
        if _admin_by and _admin_src == "ml_inferred":
            estimates = _main_mod._load_birth_year_estimates()
            est = estimates.get(person_id, {})
            est_range = est.get("birth_year_range", [])
            range_str = f"{est_range[0]}\u2013{est_range[1]}" if len(est_range) == 2 else ""
            n_photos = est.get("n_with_age_data", 0)
            conf_label = (_admin_conf or "low").capitalize()
            conf_cls = {
                "High": "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
                "Medium": "text-amber-400 bg-amber-500/10 border-amber-500/20",
                "Low": "text-slate-400 bg-slate-500/10 border-slate-500/20",
            }.get(conf_label, "text-slate-400 bg-slate-500/10 border-slate-500/20")
            ml_suggestion_card = Div(
                Div(
                    Span("\u2728 ", cls="mr-1"),
                    Span("ML Estimate", cls="text-xs font-semibold text-indigo-300"),
                    cls="mb-2",
                ),
                Div(
                    Span(f"Born c. {_admin_by}", cls="text-white text-sm font-medium"),
                    Span(f" ({range_str})" if range_str else "", cls="text-slate-400 text-xs"),
                    cls="mb-1",
                ),
                Div(
                    Span(conf_label, cls=f"text-xs px-2 py-0.5 rounded-full border {conf_cls} mr-2"),
                    Span(f"Based on {n_photos} photo{'s' if n_photos != 1 else ''}", cls="text-xs text-slate-500"),
                    cls="mb-3",
                ),
                Div(
                    Button(
                        "Accept",
                        type="button",
                        hx_post=f"/api/ml-review/birth-year/{person_id}/accept",
                        hx_target=f"#ml-suggestion-{person_id}",
                        hx_swap="outerHTML",
                        hx_vals=json.dumps({"birth_year": _admin_by}),
                        cls="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded",
                    ),
                    Button(
                        "Edit & Accept",
                        type="button",
                        onclick=f"document.getElementById('ml-edit-{person_id}').classList.toggle('hidden')",
                        cls="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded",
                    ),
                    Button(
                        "Reject",
                        type="button",
                        hx_post=f"/api/ml-review/birth-year/{person_id}/reject",
                        hx_target=f"#ml-suggestion-{person_id}",
                        hx_swap="outerHTML",
                        hx_confirm="Reject this ML birth year estimate?",
                        cls="px-3 py-1 bg-red-600/80 hover:bg-red-500 text-white text-xs rounded",
                    ),
                    cls="flex gap-2 flex-wrap",
                ),
                # Inline edit form (hidden by default)
                Div(
                    Form(
                        Div(
                            Label("Birth year:", cls="text-xs text-slate-400"),
                            Input(
                                type="number",
                                name="birth_year",
                                value=str(_admin_by),
                                cls="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white w-24",
                            ),
                            cls="flex items-center gap-2",
                        ),
                        Div(
                            Label("Source:", cls="text-xs text-slate-400"),
                            Input(
                                type="text",
                                name="source_detail",
                                placeholder="e.g. Italian census 1903",
                                cls="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white w-48",
                            ),
                            cls="flex items-center gap-2 mt-2",
                        ),
                        Button(
                            "Save",
                            type="submit",
                            cls="mt-2 px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded",
                            onclick="event.stopPropagation()",
                        ),
                        hx_post=f"/api/ml-review/birth-year/{person_id}/accept",
                        hx_target=f"#ml-suggestion-{person_id}",
                        hx_swap="outerHTML",
                    ),
                    id=f"ml-edit-{person_id}",
                    cls="hidden mt-3 pt-3 border-t border-slate-700/50",
                ),
                id=f"ml-suggestion-{person_id}",
                cls="bg-indigo-500/5 border border-indigo-500/20 rounded-lg p-4 mt-3 mb-3 text-left max-w-sm mx-auto",
                data_testid="ml-suggestion-card",
            )

    # --- Stats line ---
    stats_parts = []
    if birth_year_line:
        stats_parts.append(birth_year_line)
    if photo_count > 0:
        stats_parts.append(f"Appears in {photo_count} {'photo' if photo_count == 1 else 'photos'}")
    if collection_count > 0:
        stats_parts.append(f"{collection_count} {'collection' if collection_count == 1 else 'collections'}")
    stats_line = " · ".join(stats_parts) if stats_parts else None

    # --- Life details section (show even when empty, with contribution prompts) ---
    life_detail_items = []
    death_year = identity.get("death_year")
    birth_place = identity.get("birth_place")
    death_place = identity.get("death_place")
    maiden_name = identity.get("maiden_name")

    def _life_detail_row(label, value, prompt_text):
        if value:
            return Div(
                Span(f"{label}: ", cls="text-slate-500 text-sm w-20 inline-block"),
                Span(str(value), cls="text-slate-300 text-sm"),
                cls="py-0.5",
            )
        else:
            return Div(
                Span(f"{label}: ", cls="text-slate-500 text-sm w-20 inline-block"),
                Span("Unknown", cls="text-slate-600 text-sm italic"),
                A(
                    f" — {prompt_text}",
                    href=f"{nav_prefix}/identify/{person_id}" if not is_confirmed else "#",
                    cls="text-indigo-400/60 hover:text-indigo-300 text-xs ml-1",
                    data_action="share-photo" if is_confirmed else None,
                    data_share_url=f"{_main_mod.SITE_URL}{nav_prefix}/person/{person_id}" if is_confirmed else None,
                    data_share_title=f"Help us learn more about {display_name}" if is_confirmed else None,
                )
                if not is_admin
                else None,
                cls="py-0.5",
            )

    # Only show life details section if person is identified or under active review
    if is_confirmed or identity.get("state") in ("PROPOSED", "INBOX"):
        if not person_birth_year:
            life_detail_items.append(_life_detail_row("Born", None, "Can you help?"))
        if not death_year:
            life_detail_items.append(_life_detail_row("Died", None, "Can you help?"))
        if birth_place or not is_confirmed:
            life_detail_items.append(_life_detail_row("From", birth_place, "Can you help?"))
        elif not birth_place:
            life_detail_items.append(_life_detail_row("From", None, "Can you help?"))
        if death_place:
            life_detail_items.append(_life_detail_row("Resting", death_place, ""))
        if maiden_name:
            life_detail_items.append(
                Div(
                    Span("Maiden: ", cls="text-slate-500 text-sm w-20 inline-block"),
                    Span(maiden_name, cls="text-slate-300 text-sm"),
                    cls="py-0.5",
                )
            )

    # Only show section if there are empty fields to prompt about (or filled fields to display)
    life_details_section = None
    if life_detail_items:
        life_details_section = Div(
            *life_detail_items,
            cls="text-center mb-4",
            data_testid="life-details",
        )

    # --- Page style ---
    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
    """)

    # --- Lightbox JS and Dialog ---
    lightbox_js = Script("""
        window.openLightbox = function(href, src) {
            const d = document.getElementById('lightbox-dialog');
            d.querySelector('img').src = src;
            d.querySelector('a').href = href;
            d.classList.remove('hidden');
            d.showModal();
        };
        window.closeLightbox = function() {
            const d = document.getElementById('lightbox-dialog');
            d.classList.add('hidden');
            d.close();
            d.querySelector('img').src = '';
        };
    """)
    lightbox_dialog = Dialog(
        Div(
            Button(
                "✕",
                onclick="window.closeLightbox()",
                cls="absolute top-4 right-4 text-white hover:text-amber-400 bg-black/50 hover:bg-black/80 rounded-full w-10 h-10 flex items-center justify-center transition-colors text-xl font-bold z-50 focus:outline-none",
                type="button"
            ),
            Img(src="", alt="Enlarged photo view", cls="max-w-full max-h-[85vh] object-contain mx-auto rounded-lg shadow-2xl"),
            Div(
                A("View Photo Details \u2192", href="#", cls="inline-block mt-4 px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors active:scale-95"),
                cls="text-center"
            ),
            cls="relative p-2 md:p-6"
        ),
        id="lightbox-dialog",
        cls="hidden backdrop:bg-slate-950/90 backdrop:backdrop-blur-sm bg-transparent border-0 fixed inset-0 m-auto max-w-5xl w-full p-4 outline-none",
        onclick="if(event.target === this) window.closeLightbox()"
    )

    # --- Share button ---
    share_btn = Button(
        NotStr(
            '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
        ),
        "Share",
        cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center active:scale-95",
        type="button",
        data_action="share-photo",
        data_share_url=og_page_url,
        data_share_title=f"{display_name} — Jews of Rhodes Heritage Archive",
        data_share_text=f"Do you recognize {display_name}? Help us identify people in our heritage photo archive.",
    )

    return (
        Title(f"{display_name} — Rhodesli Heritage Archive"),
        *og_meta_tags,
        page_style,
        lightbox_js,
        lightbox_dialog,
        Main(
            # Top navigation bar
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/",
                        cls="hover:opacity-90",
                    ),
                    Div(
                        *nav_links,
                        A(
                            "Explore More Photos",
                            href=f"{nav_prefix}/photos",
                            cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-4",
                        ),
                        cls="hidden sm:flex items-center gap-6",
                    ),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            _main_mod._admin_bar(user, community_slug=community_slug),
            # Hero section
            Section(
                Div(
                    # Avatar
                    Div(
                        Img(
                            src=avatar_url,
                            alt=display_name,
                            cls="w-32 h-32 rounded-2xl object-cover border-4 border-emerald-500/30 shadow-lg shadow-emerald-500/10",
                            onerror="this.style.display='none'",
                        )
                        if avatar_url
                        else Div(
                            Span(
                                display_name[0].upper() if display_name else "?",
                                cls="text-4xl font-serif text-slate-400",
                            ),
                            cls="w-32 h-32 rounded-2xl bg-slate-800 border-4 border-slate-700 flex items-center justify-center",
                        ),
                        cls="flex justify-center mb-6",
                    ),
                    # Name + badge
                    Div(
                        H1(display_name, cls="text-3xl sm:text-4xl font-serif font-bold text-white mb-3 tracking-tight"),
                        badge,
                        _name_provenance_line(person_id, is_admin),
                        cls="text-center mb-3",
                    ),
                    # Contextual explanation for unidentified persons (Gap 1, Session 83a-cont)
                    Div(
                        P(
                            "This person hasn't been identified yet — the AI detected a face but doesn't know who they are. Can you help?",
                            cls="text-amber-300/80 text-sm",
                        ),
                        A(
                            "Help identify this person",
                            href=f"{nav_prefix}/identify/{person_id}",
                            cls="inline-block mt-2 text-indigo-400 hover:text-indigo-300 text-sm font-medium",
                        ),
                        cls="text-center mb-4 bg-amber-500/5 border border-amber-500/20 rounded-lg px-4 py-3 max-w-lg mx-auto",
                        data_testid="unidentified-explanation",
                    )
                    if not is_confirmed
                    else None,
                    # Stats line
                    P(stats_line, cls="text-slate-400 text-sm text-center mb-4 tabular-nums") if stats_line else None,
                    # Life details (birth/death/place with prompts for unknowns)
                    life_details_section,
                    # Admin: ML birth year suggestion card (Gatekeeper pattern)
                    ml_suggestion_card,
                    # Admin: inline metadata editing
                    Div(
                        Form(
                            Div(
                                Div(
                                    Label("Birth year:", cls="text-xs text-slate-500"),
                                    Input(
                                        type="number",
                                        name="birth_year",
                                        value=str(person_birth_year) if person_birth_year else "",
                                        placeholder="e.g. 1905",
                                        cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-white w-24",
                                    ),
                                    cls="flex items-center gap-1",
                                ),
                                Div(
                                    Label("Death year:", cls="text-xs text-slate-500"),
                                    Input(
                                        type="number",
                                        name="death_year",
                                        value=str(identity.get("death_year", "")) if identity.get("death_year") else "",
                                        placeholder="e.g. 1985",
                                        cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-white w-24",
                                    ),
                                    cls="flex items-center gap-1",
                                ),
                                cls="flex flex-wrap gap-3 mb-1",
                            ),
                            Div(
                                Div(
                                    Label("Birth place:", cls="text-xs text-slate-500"),
                                    Input(
                                        type="text",
                                        name="birth_place",
                                        value=identity.get("birth_place", ""),
                                        placeholder="e.g. Rhodes, Greece",
                                        list="places-list",
                                        cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-white w-40",
                                    ),
                                    cls="flex items-center gap-1",
                                ),
                                Div(
                                    Label("Death place:", cls="text-xs text-slate-500"),
                                    Input(
                                        type="text",
                                        name="death_place",
                                        value=identity.get("death_place", ""),
                                        placeholder="e.g. New York, NY",
                                        list="places-list",
                                        cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-white w-40",
                                    ),
                                    cls="flex items-center gap-1",
                                ),
                                cls="flex flex-wrap gap-3 mb-1",
                            ),
                            Div(
                                Label("Maiden name:", cls="text-xs text-slate-500"),
                                Input(
                                    type="text",
                                    name="maiden_name",
                                    value=identity.get("maiden_name", ""),
                                    cls="bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-xs text-white w-40",
                                ),
                                cls="flex items-center gap-1 mb-2",
                            ),
                            Button(
                                "Save Metadata",
                                type="submit",
                                cls="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded",
                                onclick="event.stopPropagation()",
                            ),
                            Div(id=f"metadata-status-{person_id}", cls="inline ml-2"),
                            hx_post=f"/api/identity/{person_id}/metadata",
                            hx_target=f"#metadata-status-{person_id}",
                            hx_swap="innerHTML",
                        ),
                        _main_mod._place_datalist(),
                        cls="mt-3 mb-4 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50 text-left",
                        data_testid="person-metadata-edit",
                    )
                    if is_admin and is_state_confirmed
                    else None,
                    # Action buttons
                    Div(
                        share_btn,
                        cls="flex justify-center gap-3 mb-4",
                    ),
                    # UX-039: Admin controls — inline rename, state actions, merge search
                    Div(
                        # State badge + nav links
                        Div(
                            Span(
                                state,
                                cls="text-xs px-2 py-0.5 rounded-full font-medium cursor-help "
                                + (
                                    "bg-emerald-500/20 text-emerald-400"
                                    if state == "CONFIRMED"
                                    else "bg-amber-500/20 text-amber-400"
                                    if state in ("INBOX", "PROPOSED")
                                    else "bg-slate-500/20 text-slate-400"
                                ),
                                title=f"This identity is {state.lower()}",
                            ),
                            A(
                                "Edit in Admin",
                                href=f"{workstation_prefix}/?section={_section_for_state(state)}&view=browse#identity-{person_id}",
                                cls="text-xs text-indigo-400 hover:text-white",
                                data_testid="edit-in-admin-link",
                            ),
                            Button(
                                "Find Similar",
                                hx_get=f"{nav_prefix}/api/identity/{person_id}/neighbors?container_id={similar_container_id}",
                                hx_target=f"#{similar_container_id}",
                                hx_swap="innerHTML",
                                hx_disabled_elt="this",
                                cls="text-xs px-2.5 py-2 rounded-full bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25 hover:text-white transition-colors disabled:opacity-50",
                                type="button",
                                **{"_": "on click put 'Searching...' into me"},
                            )
                            if is_admin
                            else A(
                                "Find Similar",
                                href=f"{nav_prefix}/people/{person_id}/similar",
                                cls="text-xs px-2.5 py-2 rounded-full bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25 hover:text-white transition-colors",
                            ),
                            A(
                                "Tree Linked" if has_tree_link else "Needs Tree Link",
                                href="#gedcom",
                                cls=(
                                    "text-xs px-2.5 py-2 rounded-full bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 hover:text-white transition-colors"
                                    if has_tree_link
                                    else "text-xs px-2.5 py-2 rounded-full bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 hover:text-white transition-colors"
                                ),
                                data_testid="jump-to-gedcom-link",
                            )
                            if is_confirmed
                            else None,
                            A(
                                f"Review Proposals ({len(target_proposals)})",
                                href=f"{nav_prefix}/admin/upload-review#identity-group-{person_id}",
                                cls="text-xs px-2.5 py-2 rounded-full bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 hover:text-white transition-colors",
                                data_testid="review-proposals-link",
                            )
                            if target_proposals
                            else None,
                            cls="flex items-center justify-center gap-3 mb-3",
                        ),
                        # Inline rename
                        Form(
                            Input(
                                name="name",
                                value=display_name,
                                placeholder="Enter name...",
                                cls="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-white w-48 focus:ring-2 focus:ring-indigo-400 focus:outline-none",
                            ),
                            Button(
                                "Rename",
                                type="submit",
                                cls="px-2 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded disabled:opacity-50 active:scale-95 transition-transform",
                                **{"_": "on click put 'Saving...' into me"},
                            ),
                            Span(id=f"rename-status-{person_id}", cls="text-xs text-emerald-400 ml-1"),
                            hx_post=f"/api/identity/{person_id}/rename",
                            hx_target=f"#rename-status-{person_id}",
                            hx_swap="innerHTML",
                            cls="flex items-center justify-center gap-2 mb-3",
                            data_testid="inline-rename-form",
                        ),
                        # State actions (confirm/skip/reject) — only for unresolved states
                        # FB-017: Use from_person_page=true so handler returns status, not full card
                        # FB-016/FB-024: Loading indicators via hx_disabled_elt
                        Div(
                            # FB-009: Disable confirm for unidentified persons
                            (
                                Button(
                                    "\u2713 Confirm",
                                    cls="px-3 py-1.5 text-xs font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50",
                                    hx_post=f"/{'inbox/' + person_id + '/confirm' if state == 'INBOX' else 'confirm/' + person_id}?from_person_page=true",
                                    hx_target="#person-admin-actions",
                                    hx_swap="outerHTML",
                                    hx_disabled_elt="this",
                                    type="button",
                                    **{"_": "on click put 'Confirming...' into me"},
                                )
                                if raw_name and not raw_name.startswith("Unidentified Person ")
                                else Button(
                                    "\u2713 Confirm",
                                    cls="px-3 py-1.5 text-xs font-bold bg-gray-400 cursor-not-allowed text-white rounded opacity-50",
                                    title="Name this person first",
                                    type="button",
                                    disabled=True,
                                )
                            )
                            if state in ("INBOX", "PROPOSED", "SKIPPED")
                            else None,
                            Button(
                                "\u23f8 Skip",
                                cls="px-3 py-1.5 text-xs font-bold bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-50",
                                hx_post=f"/identity/{person_id}/skip?from_person_page=true",
                                hx_target="#person-admin-actions",
                                hx_swap="outerHTML",
                                hx_disabled_elt="this",
                                type="button",
                                **{"_": "on click put 'Skipping...' into me"},
                            )
                            if state in ("INBOX", "PROPOSED")
                            else None,
                            Button(
                                "\u2717 Reject",
                                cls="px-3 py-1.5 text-xs font-bold border border-red-500 text-red-500 rounded hover:bg-red-500/20 disabled:opacity-50",
                                hx_post=f"/{'inbox/' + person_id + '/reject' if state == 'INBOX' else 'reject/' + person_id}?from_person_page=true",
                                hx_target="#person-admin-actions",
                                hx_swap="outerHTML",
                                hx_disabled_elt="this",
                                type="button",
                                **{"_": "on click put 'Rejecting...' into me"},
                            )
                            if state in ("INBOX", "PROPOSED", "SKIPPED")
                            else None,
                            id="person-admin-actions",
                            cls="flex items-center justify-center gap-2 mb-3",
                            data_testid="person-state-actions",
                        )
                        if state in ("INBOX", "PROPOSED", "SKIPPED")
                        else None,
                        # Merge search
                        Div(
                            Input(
                                name="q",
                                placeholder="Search to merge...",
                                autocomplete="off",
                                hx_get=f"/api/identity/{person_id}/search-merge",
                                hx_trigger="keyup changed delay:300ms",
                                hx_target=f"#merge-search-results-{person_id}",
                                cls="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-white w-48 focus:ring-2 focus:ring-indigo-400 focus:outline-none",
                            ),
                            Div(id=f"merge-search-results-{person_id}"),
                            cls="flex flex-col items-center gap-1 mb-3",
                            data_testid="merge-search",
                        ),
                        cls="bg-slate-800/50 rounded-lg p-4 border border-indigo-500/20 mb-4",
                        data_testid="admin-controls",
                    )
                    if is_admin
                    else None,
                    Div(id=similar_container_id, cls="mb-6", data_testid="person-similar-container")
                    if is_admin
                    else None,
                    # Cross-feature action bar
                    Div(
                        A(
                            "Timeline",
                            href=f"{nav_prefix}/timeline?person={person_id}",
                            cls="px-3 py-2 text-sm rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
                        ),
                        A(
                            "Map",
                            href=f"{nav_prefix}/map?person={person_id}",
                            cls="px-3 py-2 text-sm rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
                            data_testid="person-map-link",
                        ),
                        A(
                            "Family Tree",
                            href=f"{nav_prefix}/tree?person={person_id}",
                            cls="px-3 py-2 text-sm rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
                        ),
                        A(
                            "Connections",
                            href=f"{nav_prefix}/connect?person_a={person_id}",
                            cls="px-3 py-2 text-sm rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
                        ),
                        A(
                            "Compare with a photo",
                            href=f"{nav_prefix}/compare?person_id={person_id}",
                            cls="px-3 py-2 text-sm rounded-full bg-amber-500/10 text-amber-300 hover:text-white border border-amber-500/30 hover:border-amber-500/50 transition-colors",
                            data_testid="compare-cta",
                        ),
                        cls="flex flex-wrap justify-center gap-2 mb-8",
                        data_testid="person-action-bar",
                    ),
                    cls="max-w-3xl mx-auto pt-12 pb-8 px-6",
                ),
                cls="border-b border-slate-800",
            ),
            # Gallery section
            Section(
                Div(
                    # Toggle + sort + gallery (HTMX partial swap target)
                    Div(
                        # Section header with toggle
                        Div(
                            H2(
                                f"{'Faces' if faces_active else 'Photos'} of {display_name}",
                                cls="text-xl font-serif font-semibold text-white",
                                id="gallery-heading",
                            ),
                            Div(
                                toggle,
                                Div(
                                    Span("Sort:", cls="text-xs text-slate-500 mr-2"),
                                    sort_select,
                                    cls="flex items-center ml-3",
                                ),
                                Span(
                                    f"{gallery_count} {'face' if gallery_count == 1 else 'faces'}"
                                    if faces_active
                                    else f"{gallery_count} {'photo' if gallery_count == 1 else 'photos'}",
                                    cls="text-xs text-slate-500 ml-3 self-center",
                                ),
                                cls="flex flex-wrap items-center",
                            ),
                            cls="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6",
                        ),
                        gallery_content,
                        id="person-gallery-container",
                    ),
                    # Family relationships (from GEDCOM)
                    family_section if family_section else None,
                    # GEDCOM link management (admin only, AD-160)
                    _main_mod._person_gedcom_link_section(person_id, display_name, is_admin)
                    if is_admin and is_state_confirmed
                    else None,
                    # Closest connections (social graph)
                    connections_section if connections_section else None,
                    # Appears with section
                    appears_with_section if appears_with_section else None,
                    # Approved community annotations
                    annotations_section if annotations_section else None,
                    # Life events (PRD-011)
                    _life_events_section(person_id, nav_prefix=nav_prefix),
                    # Comments section
                    _person_comments_section(person_id, is_admin),
                    cls="max-w-5xl mx-auto px-6 py-10",
                ),
            ),
            # CTA section
            Section(
                Div(
                    H3(f"Do you have more photos of {display_name}?", cls="text-lg font-serif text-white mb-2"),
                    P(
                        "Upload your family photos to help us build a more complete picture.",
                        cls="text-slate-400 text-sm mb-4",
                    ),
                    Div(
                        A(
                            "Upload Photos",
                            href=f"{workstation_prefix}/?section=upload",
                            cls="inline-block px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg transition-colors",
                        ),
                        A(
                            "Help Identify",
                            href=f"{nav_prefix}/identify/{person_id}",
                            cls="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
                        )
                        if not is_confirmed
                        else None,
                        cls="flex flex-wrap justify-center gap-3",
                    ),
                    cls="text-center",
                ),
                cls="py-12 border-t border-slate-800",
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P(
                        "Preserving the memory of the Jewish community of Rhodes",
                        cls="text-[10px] text-slate-600 italic",
                    ),
                    Div(
                        A("Photos", href=f"{nav_prefix}/photos", cls="text-xs text-slate-500 hover:text-slate-300"),
                        Span("·", cls="text-slate-700"),
                        A("People", href=f"{nav_prefix}/people", cls="text-xs text-slate-500 hover:text-slate-300"),
                        cls="flex items-center gap-2 mt-2",
                    ),
                    cls="max-w-5xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            # Share JS (standalone page uses reusable _share_script)
            _main_mod._share_script(),
            Script("""
                document.addEventListener('click', function(e) {
                    var toggleBtn = e.target.closest('[data-action="toggle-date-correction"]');
                    if (toggleBtn) {
                        var photoId = toggleBtn.getAttribute('data-photo-id') || toggleBtn.closest('[data-photo-id]')?.getAttribute('data-photo-id');
                        if (!photoId) {
                            var form = document.querySelector('[id^="date-correction-form-"]');
                            if (form) form.classList.toggle('hidden');
                            return;
                        }
                        var formId = 'date-correction-form-' + photoId.substring(0, 8);
                        var form = document.getElementById(formId);
                        if (form) form.classList.toggle('hidden');
                        return;
                    }
                });
            """),
            _main_mod.compare_modal(),
            _main_mod.toast_container(),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/person/{person_id}")
def get(person_id: str, view: str = "faces", sort_by: str = "date_asc", sess=None, request=None):
    """
    Public shareable person page showing all photos of a specific person.

    No authentication required — anyone can view.

    Query params:
    - view: "faces" (default) or "photos" — gallery view mode
    - sort_by: date_asc (default), date_desc, uploaded_desc, uploaded_asc
    """
    user = get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"

    # FB-063: If no explicit community prefix was used, auto-detect the person's
    # primary community and redirect so all links on the page get the right prefix.
    community_explicit = getattr(request.state, "community_explicit", False) if request else False
    if not community_explicit and user_is_admin:
        detected_slug = _detect_person_community(person_id)
        if detected_slug and detected_slug != "rhodes":
            from starlette.responses import RedirectResponse

            qs = request.url.query
            redirect_url = f"/c/{detected_slug}/person/{person_id}"
            if qs:
                redirect_url += f"?{qs}"
            return RedirectResponse(redirect_url, status_code=302)

    return public_person_page(
        person_id, view=view, sort_by=sort_by, user=user, is_admin=user_is_admin, community_slug=community_slug
    )


# --- Person Gallery HTMX Partial (Phase 5: fast toggle) ---


@rt("/api/person/{person_id}/gallery")
def get(person_id: str, view: str = "faces", sort_by: str = "date_asc", sess=None, request=None):
    """Return gallery toggle + grid as HTMX partial for fast Faces/Photos switching."""
    user = get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    try:
        identity = registry.get_identity(person_id)
    except KeyError:
        return Response("Not found", status_code=404)

    display_name = ensure_utf8_display(identity.get("name", ""))
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_files = _main_mod.get_crop_files()

    face_id_strings = set()
    for f in all_face_ids:
        face_id_strings.add(f if isinstance(f, str) else f.get("face_id", ""))

    # Build photo IDs from face-to-photo mapping
    photo_ids = []
    seen_photos = set()
    for fid in face_id_strings:
        pid = _main_mod.get_photo_id_for_face(fid)
        if pid and pid not in seen_photos:
            photo_ids.append(pid)
            seen_photos.add(pid)

    date_labels = _main_mod._load_date_labels()

    def _is_unresolved_face(face_id: str) -> bool:
        ident = _main_mod.get_identity_for_face(registry, face_id)
        ident_state = ident.get("state", "INBOX") if ident else None
        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))

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

    def _build_sort_meta(photo_id, pm):
        pm = pm or {}
        year = _parse_year((date_labels.get(photo_id) or {}).get("best_year_estimate"))
        if year is None:
            year = _parse_year(pm.get("date_taken"))
        uploaded_ts = _parse_uploaded_timestamp(pm.get("created_at") or pm.get("updated_at"))
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

    def _person_photo_href(photo_id: str) -> str:
        if not photo_id:
            return "#"
        return f"{nav_prefix}/photo/{photo_id}?identity_id={person_id}&sort_by={sort_by}"

    ordered_photo_entries = []
    for pid in photo_ids:
        pm = _main_mod.get_photo_metadata(pid)
        if not pm:
            continue
        ordered_photo_entries.append(
            {
                "photo_id": pid,
                "photo_meta": pm,
                "sort_key": _gallery_sort_key(_build_sort_meta(pid, pm), pid),
                "context_conflict": _photo_context_conflict(pm, registry, person_id),
            }
        )
    ordered_photo_entries.sort(key=lambda e: e["sort_key"])

    speed_loop_photo_id = None
    speed_loop_photo_count = 0
    if is_admin:
        for entry in ordered_photo_entries:
            unresolved_here = any(
                _is_unresolved_face(face.get("face_id", "")) for face in entry["photo_meta"].get("faces", [])
            )
            if unresolved_here:
                speed_loop_photo_count += 1
                if not speed_loop_photo_id:
                    speed_loop_photo_id = entry["photo_id"]

    faces_active = view != "photos"

    if faces_active:
        face_entries = []
        for face_id_entry in all_face_ids:
            fid = face_id_entry if isinstance(face_id_entry, str) else face_id_entry.get("face_id", "")
            crop_url = _main_mod.resolve_face_image_url(fid, crop_files) if crop_files else None
            if not crop_url:
                continue
            face_photo_id = _main_mod.get_photo_id_for_face(fid)
            face_photo = _main_mod.get_photo_metadata(face_photo_id) if face_photo_id else None
            context_conflict = _photo_context_conflict(face_photo, registry, person_id)
            source_label = ""
            if face_photo:
                source_label = face_photo.get("collection", "") or face_photo.get("source", "") or ""
            face_entries.append(
                {
                    "sort_key": _gallery_sort_key(
                        _build_sort_meta(face_photo_id, face_photo), f"{face_photo_id or 'zz'}:{fid}"
                    ),
                    "item": A(
                        Div(
                            Img(
                                src=crop_url,
                                alt=display_name,
                                cls="w-full aspect-square object-cover",
                                loading="lazy",
                                onerror="this.style.display='none'",
                            ),
                            Span(
                                "Needs review",
                                cls="absolute top-2 left-2 bg-rose-500/85 text-white text-[10px] font-medium px-2 py-0.5 rounded-full shadow-sm",
                                data_testid="person-gallery-conflict",
                            )
                            if context_conflict
                            else None,
                            Div(
                                P(
                                    source_label,
                                    cls="text-[10px] text-white/90 text-center truncate w-full leading-snug",
                                )
                                if source_label
                                else None,
                                cls="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-900/90 to-transparent pt-6 pb-2 px-2 opacity-0 group-hover:opacity-100 transition-opacity flex justify-center items-end",
                            )
                            if source_label
                            else None,
                            cls="relative w-full aspect-square rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-amber-400 transition-all shadow-sm bg-slate-800",
                        ),
                        href=_person_photo_href(face_photo_id),
                        cls="flex flex-col group block",
                        title=f"View photo of {display_name}",
                        data_testid="person-gallery-item-conflicted" if context_conflict else None,
                    ),
                }
            )
        face_entries.sort(key=lambda e: e["sort_key"])
        gallery_items = [e["item"] for e in face_entries]
        grid_cls = "grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2"
    else:
        photo_entries = []
        for entry in ordered_photo_entries:
            pid = entry["photo_id"]
            pm = entry["photo_meta"]
            filename = pm["filename"]
            collection_label = pm.get("collection", "") or ""
            context_conflict = entry["context_conflict"]
            photo_entries.append(
                {
                    "sort_key": entry["sort_key"],
                    "item": A(
                        Div(
                            Img(
                                src=photo_url(filename),
                                alt=f"Photo of {display_name}",
                                cls="w-full h-48 sm:h-56 object-cover rounded-lg",
                                loading="lazy",
                            ),
                            Span(
                                "Needs review",
                                cls="absolute top-2 left-2 bg-rose-500/85 text-white text-[10px] font-medium px-2 py-0.5 rounded-full shadow-sm",
                                data_testid="person-gallery-conflict",
                            )
                            if context_conflict
                            else None,
                            cls="relative overflow-hidden rounded-lg",
                        ),
                        P(
                            "Conflicting face assignment",
                            cls="text-[10px] text-rose-300 mt-1 text-center leading-snug",
                        )
                        if context_conflict
                        else None,
                        P(collection_label, cls="text-[10px] text-slate-500 mt-1 text-center leading-snug")
                        if collection_label
                        else None,
                        href=_person_photo_href(pid),
                        cls="flex flex-col group",
                        data_testid="person-gallery-item-conflicted" if context_conflict else None,
                    ),
                }
            )
        photo_entries.sort(key=lambda e: e["sort_key"])
        gallery_items = [e["item"] for e in photo_entries]
        grid_cls = "grid grid-cols-2 sm:grid-cols-3 gap-4"

    gallery_count = len(gallery_items)

    # Toggle buttons (HTMX swap)
    toggle = Div(
        Button(
            "Faces",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors "
            + ("bg-indigo-600 text-white" if faces_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"),
            hx_get=f"{nav_prefix}/api/person/{person_id}/gallery?view=faces&sort_by={sort_by}",
            hx_target="#person-gallery-container",
            hx_swap="innerHTML",
            type="button",
        ),
        Button(
            "Photos",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors "
            + (
                "bg-indigo-600 text-white"
                if not faces_active
                else "text-slate-400 hover:text-white hover:bg-slate-700/50"
            ),
            hx_get=f"{nav_prefix}/api/person/{person_id}/gallery?view=photos&sort_by={sort_by}",
            hx_target="#person-gallery-container",
            hx_swap="innerHTML",
            type="button",
        ),
        cls="flex gap-1 bg-slate-800/50 p-1 rounded-xl",
    )

    sort_select = Select(
        Option("Earliest First", value="date_asc", selected=(sort_by == "date_asc")),
        Option("Earliest Last", value="date_desc", selected=(sort_by == "date_desc")),
        Option("Newest Uploads", value="uploaded_desc", selected=(sort_by == "uploaded_desc")),
        Option("Oldest Uploads", value="uploaded_asc", selected=(sort_by == "uploaded_asc")),
        cls="bg-slate-800/60 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500",
        hx_get=f"{nav_prefix}/api/person/{person_id}/gallery?view={'faces' if faces_active else 'photos'}",
        hx_target="#person-gallery-container",
        hx_swap="innerHTML",
        hx_trigger="change",
        hx_include="this",
        name="sort_by",
        aria_label="Sort gallery",
    )

    gallery_content = (
        Div(*gallery_items, cls=grid_cls)
        if gallery_items
        else Div(P("No photos available yet.", cls="text-slate-500 text-center py-8"))
    )

    count_label = (
        f"{gallery_count} {'face' if gallery_count == 1 else 'faces'}"
        if faces_active
        else f"{gallery_count} {'photo' if gallery_count == 1 else 'photos'}"
    )
    speed_loop_cta = (
        A(
            f"Start Speed Loop ({speed_loop_photo_count} photo{'s' if speed_loop_photo_count != 1 else ''} to review)",
            href=f"{nav_prefix}/photo/{speed_loop_photo_id}?identity_id={person_id}&sort_by={sort_by}&seq=1",
            cls="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg bg-amber-600 hover:bg-amber-500 text-white transition-colors",
            data_testid="person-speed-loop",
        )
        if speed_loop_photo_id
        else None
    )

    return Div(
        Div(
            H2(
                f"{'Faces' if faces_active else 'Photos'} of {display_name}",
                cls="text-xl font-serif font-semibold text-white",
                id="gallery-heading",
            ),
            Div(
                toggle,
                speed_loop_cta,
                Div(Span("Sort:", cls="text-xs text-slate-500 mr-2"), sort_select, cls="flex items-center ml-3"),
                Span(count_label, cls="text-xs text-slate-500 ml-3 self-center"),
                cls="flex flex-wrap items-center gap-3",
            ),
            cls="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6",
        ),
        gallery_content,
    )


# --- Person Comments API ---

# Rate limit storage for person comments (IP -> list of timestamps)
_comment_rate_limit: dict = {}


@rt("/api/person/{person_id}/comment")
def post(person_id: str, author: str = "", text: str = "", sess=None, request=None):
    """Submit a comment on a person page. No login required. Rate limited."""
    if not text.strip():
        return Div(P("Please enter a comment.", cls="text-amber-400 text-sm py-2"))

    # Rate limiting: max 5 comments per IP per hour
    import hashlib as _rl_hashlib

    client_ip = ""
    if request:
        client_ip = getattr(request.client, "host", "") if request.client else ""
    ip_hash = _rl_hashlib.sha256(client_ip.encode()).hexdigest()[:12] if client_ip else "unknown"
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    _comment_rate_limit[ip_hash] = [t for t in _comment_rate_limit.get(ip_hash, []) if t > cutoff]
    if len(_comment_rate_limit.get(ip_hash, [])) >= 5:
        return Div(P("Please wait before submitting another comment.", cls="text-amber-400 text-sm text-center py-4"))
    _comment_rate_limit.setdefault(ip_hash, []).append(now)

    comments_data = _main_mod._load_person_comments()
    if person_id not in comments_data.get("comments", {}):
        comments_data.setdefault("comments", {})[person_id] = []

    comment = {
        "id": str(uuid.uuid4())[:8],
        "author": author.strip() or "Anonymous",
        "text": text.strip(),
        "timestamp": datetime.now().isoformat(),
        "status": "visible",
    }
    comments_data["comments"][person_id].append(comment)
    _main_mod._save_person_comments(comments_data)

    # Session 105b: Sync comment to Supabase (was DATA-015 dead code)
    try:
        from app.supabase_data import sync_person_comment

        sync_person_comment(person_id, text.strip(), author=author.strip() or "Anonymous")
    except Exception as e:
        logging.error(f"Supabase person comment sync failed for {person_id}: {e}")

    # Re-render comments list
    visible = [c for c in comments_data["comments"][person_id] if c.get("status") == "visible"]
    items = []
    for c in visible:
        date_str = c.get("timestamp", "")[:10]
        items.append(
            Div(
                Div(
                    Span(c["author"], cls="text-sm font-medium text-slate-300"),
                    Span(f" · {date_str}", cls="text-xs text-slate-600") if date_str else None,
                    cls="flex items-center mb-1",
                ),
                P(c["text"], cls="text-sm text-slate-400 leading-relaxed"),
                cls="py-3 border-b border-slate-800/50 last:border-0",
                id=f"comment-{c['id']}",
            )
        )
    return Div(*items)


@rt("/api/person/{person_id}/comment/{comment_id}/hide")
def post(person_id: str, comment_id: str, sess=None):
    """Hide a comment (admin only)."""
    err = _main_mod._check_admin(sess)
    if err:
        return err

    comments_data = _main_mod._load_person_comments()
    person_comments = comments_data.get("comments", {}).get(person_id, [])
    for c in person_comments:
        if c.get("id") == comment_id:
            c["status"] = "hidden"
            break
    _main_mod._save_person_comments(comments_data)
    return Div(P("Comment hidden.", cls="text-xs text-slate-500 italic py-2"))
