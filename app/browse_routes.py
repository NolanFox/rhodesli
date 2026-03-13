"""
Browse routes extracted from app/main.py.

All /photos, /people, /collections, /collection/* routes plus browse-exclusive helpers.
Shared helpers (caches, registries, UI components) remain in app.main.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import *

from core.registry import IdentityState
from core.ui_safety import ensure_utf8_display
from core import storage

# Import route decorator only (bound once, never reassigned)
from app.main import rt
from app.utils import make_css_id, photo_url

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS — Browse-exclusive
# =============================================================================


def _build_photo_cards(photos: list, masonry: bool = False, nav_prefix: str = "") -> list:
    """Build photo card elements for a list of photo dicts.

    Args:
        photos: List of photo dicts with photo_id, filename, face_count, etc.
        masonry: If True, render cards at natural aspect ratio for masonry layout.
    """
    cards = []
    for photo in photos:
        provenance = _main_mod._get_upload_provenance_display(photo)
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

        # Flip icon badge for photos with back images
        has_back = bool(photo.get("back_image"))
        flip_badge = (
            Div(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"/></svg>'
                ),
                cls="absolute bottom-2 right-2 w-6 h-6 rounded-full bg-amber-600/80 "
                "text-white flex items-center justify-center backdrop-blur-sm",
                title="Has back image",
            )
            if has_back
            else None
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
                    ),
                    Div(
                        f"{photo['confirmed_count']}/{photo['face_count']}"
                        if photo["confirmed_count"] > 0
                        else f"{photo['face_count']} face{'s' if photo['face_count'] != 1 else ''}",
                        cls=f"absolute top-2 right-2 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm {badge_cls}",
                    )
                    if photo["face_count"] > 0
                    else None,
                    date_badge,
                    flip_badge,
                    cls=img_container_cls,
                    style=aspect_style if aspect_style else None,
                ),
                Div(
                    P(photo["collection"] or "", cls="text-xs text-slate-500 leading-snug")
                    if photo["collection"]
                    else None,
                    P(provenance["headline"], cls="text-[11px] text-slate-400 leading-tight")
                    if provenance
                    else None,
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


def _collection_slug(name: str) -> str:
    """Convert collection name to URL slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _collection_from_slug(slug: str, collections: dict) -> str:
    """Find collection name from slug."""
    for name in collections:
        if _collection_slug(name) == slug:
            return name
    return ""


def _get_collections_data():
    """Build collection metadata from photo_index."""
    photo_reg = _main_mod.load_photo_registry()
    registry = _main_mod.load_registry()
    photos = photo_reg.list_photos() if hasattr(photo_reg, "list_photos") else []

    # Fall back to raw photo_index if list_photos not available
    if not photos:
        pi_path = _main_mod.data_path / "photo_index.json"
        if pi_path.exists():
            pi = json.loads(pi_path.read_text(encoding="utf-8"))
            photos = list(pi.get("photos", {}).values())
            for p in photos:
                if "photo_id" not in p:
                    # Try to generate from path
                    path = p.get("path", "")
                    if path:
                        p["photo_id"] = hashlib.sha256(Path(path).name.encode()).hexdigest()[:16]

    collections = {}
    for photo in photos:
        col_name = photo.get("collection", "") or photo.get("source", "")
        if not col_name:
            continue
        if col_name not in collections:
            collections[col_name] = {
                "name": col_name,
                "slug": _collection_slug(col_name),
                "photos": [],
                "identified_count": 0,
                "unidentified_count": 0,
            }
        collections[col_name]["photos"].append(photo)

    # Count identified vs unidentified faces per collection
    for col_name, col_data in collections.items():
        identified = set()
        unidentified = 0
        for photo in col_data["photos"]:
            for fid in photo.get("face_ids", []):
                ident = _main_mod.get_identity_for_face(registry, fid)
                if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                    identified.add(ident.get("identity_id"))
                elif ident:
                    unidentified += 1
        col_data["identified_count"] = len(identified)
        col_data["unidentified_count"] = unidentified

    return collections


# =============================================================================
# ROUTES — Photos Browsing
# =============================================================================


@rt("/photos")
def get(
    filter_collection: str = "",
    sort_by: str = "newest",
    decade: int = None,
    search_q: str = "",
    tag: str = "",
    media_filter: str = "all",
    sess=None,
    request=None,
):
    """
    Public photos browsing page — grid of all archive photos.

    No authentication required. Each photo links to /photo/{id}.
    Supports decade filtering, keyword search, and tag filtering via query params.
    Community-aware: filters photos by community context from middleware.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None

    # Community context from middleware (PRD-035)
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    community_photo_ids = _main_mod._get_community_photo_ids(community)
    nav_prefix = _main_mod.community_url_prefix(community_slug)

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

    # Build reverse alias map: SHA256 cache ID -> inbox_* photo_index ID
    # Needed because community_photo_ids uses inbox_* IDs from Supabase,
    # but _photo_cache keys are SHA256 IDs from embeddings.npy.
    _reverse_aliases = {}
    if community_photo_ids is not None and _main_mod._photo_id_aliases:
        for inbox_id, cache_id in _main_mod._photo_id_aliases.items():
            _reverse_aliases[cache_id] = inbox_id

    for photo_id_val, photo_data in (_main_mod._photo_cache or {}).items():
        # Apply community filter (PRD-035)
        if community_photo_ids is not None:
            # Check both the cache ID and its alias (inbox_* ID)
            alias_id = _reverse_aliases.get(photo_id_val)
            if photo_id_val not in community_photo_ids and (alias_id is None or alias_id not in community_photo_ids):
                continue
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
                "back_image": photo_data.get("back_image", ""),
                "media_role": photo_data.get("media_role", "front"),
            }
        )

    collections = sorted(collections_set)

    # Apply media filter
    if media_filter == "front_only":
        photos = [p for p in photos if p["media_role"] != "back"]
    elif media_filter == "has_back":
        photos = [p for p in photos if p.get("back_image")]

    # Sort
    photos = _main_mod._sort_photos(photos, sort_by)

    # Build photo cards (paginated — 24 per page for lazy loading)
    PHOTOS_PER_PAGE = 24
    photo_cards = _build_photo_cards(photos[:PHOTOS_PER_PAGE], masonry=True, nav_prefix=nav_prefix)

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
            "media_filter": media_filter,
        }
        if decade:
            _lazy_params["decade"] = decade
        _lazy_params = {k: v for k, v in _lazy_params.items() if v and v != "all"}
        photo_cards.append(
            Div(
                Div(cls="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"),
                P("Loading more photos...", cls="text-slate-500 text-xs mt-2"),
                id="photos-lazy-sentinel",
                cls="flex flex-col items-center py-8",
                style="break-inside: avoid; column-span: all;",
                hx_get=f"{nav_prefix}/api/photos/more?{_ue(_lazy_params)}",
                hx_trigger="revealed",
                hx_swap="outerHTML",
            )
        )

    # Build filter URL helper
    from urllib.parse import quote as _url_quote, urlencode as _url_encode

    def _filter_url(**overrides):
        """Build /photos URL preserving current filters with overrides."""
        params = {
            "filter_collection": filter_collection,
            "sort_by": sort_by,
            "search_q": search_q,
            "tag": tag,
            "media_filter": media_filter,
        }
        if decade:
            params["decade"] = str(decade)
        params.update({k: v for k, v in overrides.items() if v})
        # Remove empty/None params
        params = {k: v for k, v in params.items() if v}
        qs = _url_encode(params)
        photos_path = f"{nav_prefix}/photos" if nav_prefix else "/photos"
        return f"{photos_path}?{qs}" if qs else photos_path

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

    media_options = [
        Option("All Photos", value="all", selected=(media_filter == "all")),
        Option("Front Only", value="front_only", selected=(media_filter == "front_only")),
        Option("Has Back Image", value="has_back", selected=(media_filter == "has_back")),
    ]

    # Decade pills
    decade_pills = [
        A(
            "All",
            href=_filter_url(decade=""),
            cls="px-3 py-1 text-xs rounded-full transition-colors font-serif "
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
                cls="px-3 py-1 text-xs rounded-full transition-colors font-serif "
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
                cls="px-2.5 py-1 text-[11px] rounded-full transition-colors "
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
            f"{len(photos)} historical photographs from the Jewish community of Rhodes.",
            canonical_url=f"{nav_prefix}/photos" if nav_prefix else "/photos",
        ),
        page_style,
        Main(
            Nav(
                Div(
                    A(
                        Span("Rhodesli", cls="text-xl font-bold text-white"),
                        href=f"{nav_prefix}/" if nav_prefix else "/",
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
                        H1("Photos", cls="text-3xl font-serif font-bold text-white mb-2"),
                        _main_mod.share_button(
                            url=f"{nav_prefix}/photos" if nav_prefix else "/photos",
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
                                cls="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-1.5 w-full sm:w-64 focus:ring-1 focus:ring-amber-500/50 focus:border-amber-500/50 placeholder-slate-500",
                                data_testid="photo-search",
                                onkeydown=f"if(event.key==='Enter')window.location.href='/photos?search_q='+encodeURIComponent(this.value)+'&decade={decade or ''}&tag={_url_quote(tag)}&filter_collection={_url_quote(filter_collection)}&sort_by={sort_by}'",
                            ),
                            cls="flex-shrink-0",
                        ),
                        # Tag pills
                        Div(*tag_pills, cls="flex flex-wrap gap-1.5") if tag_pills else None,
                        cls="flex flex-wrap items-center gap-3 mb-3",
                    ),
                    # Collection/sort/media dropdowns
                    Div(
                        Select(
                            *collection_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection=' + encodeURIComponent(this.value) + '&sort_by={sort_by}&decade={decade or ''}&search_q={_url_quote(search_q)}&tag={_url_quote(tag)}&media_filter={_url_quote(media_filter)}'",
                        ),
                        Select(
                            *sort_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection={_url_quote(filter_collection)}&sort_by=' + this.value + '&decade={decade or ''}&search_q={_url_quote(search_q)}&tag={_url_quote(tag)}&media_filter={_url_quote(media_filter)}'",
                        ),
                        Div(
                            Span("Media:", cls="text-sm text-slate-400 mr-1"),
                            Select(
                                *media_options,
                                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                                onchange=f"window.location.href='/photos?filter_collection={_url_quote(filter_collection)}&sort_by={sort_by}&decade={decade or ''}&search_q={_url_quote(search_q)}&tag={_url_quote(tag)}&media_filter=' + this.value",
                            ),
                            cls="flex items-center",
                        ),
                        Span(
                            f"{len(photos)} result{'s' if len(photos) != 1 else ''}",
                            cls="text-xs text-slate-500 ml-auto",
                        ),
                        cls="flex flex-wrap items-center gap-3 mb-6",
                    ),
                    # Photo grid — masonry layout via CSS columns
                    Div(*photo_cards, id="photo-grid", cls="masonry-grid")
                    if photo_cards
                    # Empty state for non-Rhodes community
                    else (
                        Div(
                            Div(
                                H3("No photos yet", cls="text-xl font-serif text-amber-200 mb-2"),
                                P(
                                    "Upload your first photos to start building this archive.",
                                    cls="text-slate-400 mb-4",
                                ),
                                A(
                                    "Upload Photos",
                                    href=f"{_main_mod.community_url_prefix(community_slug)}/upload",
                                    cls="inline-block px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors",
                                ),
                                cls="text-center py-16",
                            ),
                            cls="bg-slate-800/50 rounded-xl border border-slate-700/50 p-8 mt-8",
                        )
                        if community_slug != "rhodes"
                        else Div(
                            P("No photos match your filters.", cls="text-slate-500 text-center py-12"),
                            A(
                                "Clear filters",
                                href=f"{_main_mod.community_url_prefix(community_slug)}/photos",
                                cls="text-indigo-400 hover:text-indigo-300 text-sm block text-center mt-2",
                            ),
                        )
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
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
    media_filter: str = "all",
    request=None,
):
    """HTMX endpoint for infinite scroll — returns next batch of photo cards."""
    from urllib.parse import urlencode as _ue

    PHOTOS_PER_PAGE = 24

    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    community_photo_ids = _main_mod._get_community_photo_ids(community)
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    _main_mod._build_caches()
    registry = _main_mod.load_registry()

    # Replicate same filtering/sorting as /photos
    search_photo_ids = None
    if search_q or decade or tag:
        search_results = _main_mod._search_photos(query=search_q, decade=decade, tag=tag)
        search_photo_ids = {r.get("cache_photo_id", r["photo_id"]): r.get("match_reason") for r in search_results}

    photos = []
    _reverse_aliases = {}
    if community_photo_ids is not None and _main_mod._photo_id_aliases:
        for inbox_id, cache_id in _main_mod._photo_id_aliases.items():
            _reverse_aliases[cache_id] = inbox_id
    for photo_id_val, photo_data in (_main_mod._photo_cache or {}).items():
        if community_photo_ids is not None:
            alias_id = _reverse_aliases.get(photo_id_val)
            if photo_id_val not in community_photo_ids and (alias_id is None or alias_id not in community_photo_ids):
                continue
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
                "back_image": photo_data.get("back_image", ""),
                "media_role": photo_data.get("media_role", "front"),
            }
        )

    # Apply media filter
    if media_filter == "front_only":
        photos = [p for p in photos if p["media_role"] != "back"]
    elif media_filter == "has_back":
        photos = [p for p in photos if p.get("back_image")]

    photos = _main_mod._sort_photos(photos, sort_by)

    # Paginate
    start = (page - 1) * PHOTOS_PER_PAGE
    end = start + PHOTOS_PER_PAGE
    page_photos = photos[start:end]

    if not page_photos:
        return ""  # No more photos

    cards = _build_photo_cards(page_photos, masonry=True, nav_prefix=nav_prefix)

    # Add sentinel for next page if there are more
    total_pages = (len(photos) + PHOTOS_PER_PAGE - 1) // PHOTOS_PER_PAGE
    if page < total_pages:
        _lazy_params = {
            "page": page + 1,
            "filter_collection": filter_collection,
            "sort_by": sort_by,
            "search_q": search_q,
            "tag": tag,
            "media_filter": media_filter,
        }
        if decade:
            _lazy_params["decade"] = decade
        _lazy_params = {k: v for k, v in _lazy_params.items() if v and v != "all"}
        cards.append(
            Div(
                Div(cls="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"),
                P("Loading more photos...", cls="text-slate-500 text-xs mt-2"),
                id="photos-lazy-sentinel",
                cls="flex flex-col items-center py-8",
                style="break-inside: avoid; column-span: all;",
                hx_get=f"{nav_prefix}/api/photos/more?{_ue(_lazy_params)}",
                hx_trigger="revealed",
                hx_swap="outerHTML",
            )
        )

    return tuple(cards)


# =============================================================================
# ROUTES — People Browsing
# =============================================================================


@rt("/people")
def get(sort_by: str = "name", sess=None, request=None):
    """
    Public people browsing page — grid of identified people.

    No authentication required. Each person links to /person/{id}.
    No admin actions visible.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Get confirmed identities with real names
    confirmed = [
        i
        for i in registry.list_identities(state=IdentityState.CONFIRMED)
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
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href=f"{nav_prefix}/", cls="hover:opacity-90"),
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
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange=f"window.location.href='{nav_prefix}/people?sort_by=' + this.value",
                        ),
                        cls="flex items-center gap-2 mb-6",
                    ),
                    Div(
                        *person_cards,
                        cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4",
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
                    H3("Can you help identify someone?", cls="text-lg font-serif text-white mb-2"),
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
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
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
    current_community = getattr(request.state, "community", None) if request else None
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

    mergeable_count = sum(1 for n in neighbors if n.get("can_merge"))
    blocked_count = sum(1 for n in neighbors if not n.get("can_merge"))
    dismissed_count = sum(1 for n in neighbors if n.get("state") in {"SKIPPED", "REJECTED", "CONTESTED"})

    # Build result grid cards
    result_cards = []
    for n in neighbors:
        if not n.get("crop_url"):
            continue
        nid = n["identity_id"]
        tier_label, tier_cls = confidence_tier_from_distance(n.get("distance", 99))
        neighbor_section = _main_mod._section_for_state(n.get("state", "INBOX"))
        state_label = {
            "CONFIRMED": "Identified",
            "SKIPPED": "Dismissed",
            "REJECTED": "Rejected",
            "CONTESTED": "Contested",
            "PROPOSED": "Proposed",
        }.get(n.get("state"), "In Queue")
        state_cls = {
            "CONFIRMED": "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
            "SKIPPED": "bg-amber-500/10 text-amber-300 border border-amber-500/20",
            "REJECTED": "bg-rose-500/10 text-rose-300 border border-rose-500/20",
            "CONTESTED": "bg-rose-500/10 text-rose-300 border border-rose-500/20",
            "PROPOSED": "bg-sky-500/10 text-sky-300 border border-sky-500/20",
        }.get(n.get("state"), "bg-slate-700 text-slate-300 border border-slate-600")
        blocked_reason = n.get("merge_blocked_reason_display") or n.get("merge_blocked_reason")
        admin_actions = []
        if is_admin:
            admin_actions.append(
                Button(
                    "Merge",
                    cls="text-xs px-2 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-500 transition-colors",
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
                    cls="text-xs px-2 py-1 border border-slate-500 text-slate-300 rounded hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/50 transition-colors",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/reject-match/{nid}",
                    hx_target=f"#search-result-{nid}",
                    hx_swap="outerHTML",
                    type="button",
                )
            )
            admin_actions.append(
                A(
                    "Review in Queue",
                    href=f"{nav_prefix}/?section={neighbor_section}&view=browse#identity-{nid}",
                    cls="text-xs px-2 py-1 border border-slate-600 text-slate-300 rounded hover:border-slate-500 hover:text-white transition-colors",
                    data_testid="similar-review-queue-link",
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
                    Span(state_label, cls=f"text-[10px] px-2 py-0.5 rounded-full {state_cls}", data_testid="similar-result-state"),
                    _main_mod._cross_community_badge(nid, current_community),
                    cls="flex items-center gap-1 flex-wrap mt-1",
                ),
                Div(
                    Span(tier_label, cls=f"text-xs px-2 py-0.5 rounded-full text-white {tier_cls}"),
                    Span(f"{n.get('distance', 0):.2f}", cls="text-xs text-slate-500 ml-2") if is_admin else None,
                    cls="flex items-center gap-1 mt-1",
                ),
                P(
                    "This match is blocked because the faces already appear in the same photo."
                    if blocked_reason == "co_occurrence"
                    else f"Merge blocked: {blocked_reason}"
                    if blocked_reason
                    else "",
                    cls="text-[11px] text-amber-300/80 mt-2 leading-snug",
                )
                if blocked_reason and is_admin
                else None,
                P(
                    "Previously dismissed or contested matches stay visible here so they can be reviewed deliberately.",
                    cls="text-[11px] text-slate-400 mt-2 leading-snug",
                )
                if n.get("state") in {"SKIPPED", "REJECTED", "CONTESTED"}
                else None,
                Span(
                    f"{n.get('face_count', 0)} face{'s' if n.get('face_count', 0) != 1 else ''}",
                    cls="text-xs text-slate-400 mt-0.5 block",
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
                                Span(
                                    f"{mergeable_count} mergeable",
                                    cls="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
                                ),
                                Span(
                                    f"{blocked_count} blocked",
                                    cls="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20",
                                ),
                                Span(
                                    f"{dismissed_count} dismissed/contested",
                                    cls="text-xs px-2.5 py-1 rounded-full bg-slate-700 text-slate-300 border border-slate-600",
                                ),
                                cls="flex flex-wrap gap-2 mb-4",
                                data_testid="similar-admin-summary",
                            )
                            if is_admin and neighbors
                            else None,
                            P(
                                "Use this page to review candidates, then jump straight back into the queue when you need more surrounding context."
                                if is_admin
                                else "",
                                cls="text-xs text-slate-500 mb-4 max-w-xl",
                            )
                            if is_admin
                            else None,
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
                                    href=f"{nav_prefix}/?section={_main_mod._section_for_state(state)}&view=browse#identity-{identity_id}",
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
    css_id = make_css_id(identity_id)
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
                    cls="text-xs px-2 py-1 border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20 transition-colors",
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
                        cls="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors",
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
                    cls="text-xs px-2 py-1 border border-slate-500 text-slate-400 rounded hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/50 transition-colors",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/reject-match/{nid}",
                    hx_target=f"#similar-tile-{make_css_id(nid)}",
                    hx_swap="outerHTML",
                    type="button",
                )
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
                Div(*tile_actions, cls="flex flex-wrap gap-1 mt-2") if tile_actions else None,
                cls="mt-2",
            ),
            cls="similar-face-tile",
            id=f"similar-tile-{make_css_id(nid)}",
        )
        tiles.append(tile)

    # Close button
    close_btn = Button(
        NotStr("&times;"),
        cls="panel-close text-slate-400 hover:text-white text-xl font-bold bg-transparent border-0 p-1 leading-none",
        **{"_": f"on click set innerHTML of #expand-{css_id} to ''"},
        type="button",
        title="Close",
    )

    # Build the fragment
    hero_section = Div(
        Img(src=hero_url, alt=name, cls="w-20 h-20 rounded-lg object-cover flex-shrink-0") if hero_url else None,
        Div(
            Span(name or "Unidentified", cls="text-lg font-semibold text-white block"),
            Span(f"{len(all_face_ids)} face{'s' if len(all_face_ids) != 1 else ''}", cls="text-sm text-slate-400"),
            A(
                "View Profile",
                href=f"{nav_prefix}/person/{identity_id}",
                cls="text-xs text-indigo-400 hover:text-indigo-300 block mt-1",
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


@rt("/api/identity/{identity_id}/reject-match/{neighbor_id}", methods=["POST"])
def post(identity_id: str, neighbor_id: str, sess=None):
    """Record a negative match between two identities and remove the tile."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    if not is_admin:
        return Response("Forbidden", status_code=403)

    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    # Record bidirectional negative pair
    try:
        registry.reject_identity_pair(identity_id, neighbor_id, user_source="admin_inline")
        _main_mod.save_registry(registry)
    except KeyError:
        pass  # Neighbor may have been merged/deleted

    # Return empty div to remove the tile
    return ""


# =============================================================================
# ROUTES — Collections
# =============================================================================


@rt("/collections")
def get(sess=None, request=None):
    """Collection directory — list all collections with preview thumbnails."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    collections = _get_collections_data()

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
                url = storage.get_photo_url(photo_path)
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
                P(f"{photo_count} photo{'s' if photo_count != 1 else ''}", cls="text-xs text-slate-400"),
                P(face_line, cls="text-xs text-slate-500 mt-0.5"),
                href=f"{nav_prefix}/collection/{slug}",
                cls="block bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
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
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href=f"{nav_prefix}/", cls="hover:opacity-90"),
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
                ),
                Div(*cards, cls="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"),
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

    collections = _get_collections_data()
    col_name = _collection_from_slug(slug, collections)

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
                        "Browse all collections \u2192",
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
        url = storage.get_photo_url(photo_path)

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
            people_in_collection,
            key=lambda x: _main_mod._safe_get_identity(registry, x).get("name", "").lower(),
        ):
            p_ident = _main_mod._safe_get_identity(registry, pid)
            p_name = ensure_utf8_display(p_ident.get("name", "Unknown"))
            people_items.append(
                A(
                    p_name,
                    href=f"{nav_prefix}/person/{pid}",
                    cls="inline-block px-2.5 py-1 text-xs rounded-full bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
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
            og_image_url = storage.get_photo_url(photo_path)
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
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href=f"{nav_prefix}/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between",
                ),
                cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50",
            ),
            Div(
                # Breadcrumb
                Div(
                    A("Collections", href=f"{nav_prefix}/collections", cls="text-indigo-400 hover:text-indigo-300 text-sm"),
                    Span(" / ", cls="text-slate-600 mx-2"),
                    Span(col_name, cls="text-slate-300 text-sm"),
                    cls="mb-6",
                ),
                # Header
                Div(
                    H1(col_name, cls="text-2xl md:text-3xl font-bold text-white mb-2"),
                    Div(
                        Span(f"{len(photos)} photo{'s' if len(photos) != 1 else ''}", cls="text-slate-400"),
                        Span(" \u00b7 ", cls="text-slate-600 mx-2"),
                        Span(f"{col['identified_count']} people identified", cls="text-emerald-400"),
                        cls="text-sm mb-4",
                    ),
                    # Action buttons
                    Div(
                        Button(
                            NotStr(_main_mod._SHARE_ICON_SVG),
                            " Share Collection",
                            cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1",
                            type="button",
                            data_action="share-photo",
                            data_share_url=share_url,
                        ),
                        A(
                            "View on Timeline \u2192",
                            href=f"{nav_prefix}/timeline?collection={quote(col_name)}",
                            cls="text-sm text-indigo-400 hover:text-indigo-300 ml-4",
                        ),
                        A(
                            "+ Add Photos",
                            href=f"{nav_prefix}/upload",
                            cls="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded-lg transition-colors inline-flex items-center gap-1 ml-3",
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
                        "Help Identify \u2192",
                        href=f"{nav_prefix}/help",
                        cls="text-sm text-indigo-400 hover:text-indigo-300 font-medium ml-4",
                    ),
                    cls="bg-blue-900/20 border border-blue-800/30 rounded-lg px-4 py-3 flex items-center justify-between mb-6",
                    data_testid="help-identify-banner",
                )
                if col["unidentified_count"] > 0
                else "",
                # Photo grid
                Div(*photo_cards, cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3"),
                # People section
                people_section,
                cls="max-w-6xl mx-auto px-6 pt-24 pb-16",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )
