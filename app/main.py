"""
Rhodesli Forensic Workstation.

A triage-focused interface for identity verification with epistemic humility.
The UI reflects backend state - it never calculates probabilities.

Error Semantics:
- 409 = Variance Explosion (faces too dissimilar)
- 423 = Lock Contention (another process is writing)
- 404 = Identity or face not found
"""

import hashlib
import json
import logging
import os
import sys

# Ensure project root is on sys.path for cross-module imports (compare_routes, estimate_routes, upload_routes).
# When running `python app/main.py`, sys.path[0] = app/ not project root.
from pathlib import Path as _PathEarly

_project_root = str(_PathEarly(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# When running as __main__ (python app/main.py), register this module as 'app.main'
# so that `from app.main import rt` in route modules gets the SAME module instance
# (not a duplicate). Without this, compare_routes would get a different rt/app object.
if "app.main" not in sys.modules:
    sys.modules["app.main"] = sys.modules[__name__]
    # Also ensure 'app' package is importable
    if "app" not in sys.modules:
        import types

        _app_pkg = types.ModuleType("app")
        _app_pkg.__path__ = [str(_PathEarly(__file__).resolve().parent)]
        sys.modules["app"] = _app_pkg
if (
    not os.environ.get("RAILWAY_ENVIRONMENT")
    and "pytest" not in sys.modules
    and not os.environ.get("RHODESLI_SKIP_DOTENV")
):
    from dotenv import load_dotenv

    load_dotenv()
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
from fasthtml.common import *
from PIL import Image
from starlette.responses import FileResponse, HTMLResponse

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.registry import IdentityRegistry, IdentityState
from core.config import (
    HOST,
    PORT,
    DEBUG,
    PROCESSING_ENABLED,
    DATA_DIR,
    PHOTOS_DIR,
)
from core.config import SYNC_API_TOKEN  # noqa: F401 — used by sync_routes via _main_mod
from core.config import MATCH_THRESHOLD_HIGH, MATCH_THRESHOLD_LOW  # noqa: F401 — used by identity_routes via _main_mod
from core.ui_safety import ensure_utf8_display
from core import storage
from app.auth import (
    is_auth_enabled,
    SESSION_SECRET,
    get_current_user,
    User,
    ADMIN_EMAILS,
    get_oauth_url,
)

# --- INSTRUMENTATION IMPORT ---
from core.event_recorder import get_event_recorder

# --- EXTRACTED UTILITIES ---
from app.utils import (
    _pl,  # noqa: F401 — re-exported for tests
    _section_for_state,
    make_css_id,
    generate_photo_id,
    generate_face_id,
    sanitize_stem,
    parse_quality_from_filename,
    photo_url,
    APP_VERSION,
)

# --- Observability init (all gated on env vars) ---
# Sentry error tracking — no-op when SENTRY_DSN is not set
_sentry_enabled = bool(os.environ.get("SENTRY_DSN"))
if _sentry_enabled:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=0.1,
        send_default_pii=False,  # Heritage app — faces are PII
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )

# PostHog server-side analytics — no-op when POSTHOG_API_KEY is not set
_posthog_server = None
_posthog_api_key = os.environ.get("POSTHOG_API_KEY", "")
if _posthog_api_key:
    import posthog as _posthog_mod

    _posthog_mod.api_key = _posthog_api_key
    _posthog_mod.host = "https://us.i.posthog.com"
    _posthog_server = _posthog_mod

# Structured logging — configures alongside stdlib logging
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

static_path = Path(__file__).resolve().parent / "static"
# Data and photos paths come from config, which handles STORAGE_DIR for Railway
data_path = Path(DATA_DIR) if Path(DATA_DIR).is_absolute() else project_root / DATA_DIR
photos_path = Path(PHOTOS_DIR) if Path(PHOTOS_DIR).is_absolute() else project_root / PHOTOS_DIR

# Canonical site URL for Open Graph tags and sharing
SITE_URL = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")

# Data source feature flag: "json" (default) or "postgres" (PRD-027 Phase B/C)
DATA_SOURCE = os.environ.get("DATA_SOURCE", "json")

# APP_VERSION imported from app.utils

# No blanket auth — all GET routes are public.
# Specific POST routes use @require_admin or @require_login decorators.


def _posthog_script():
    """Return PostHog analytics snippet if POSTHOG_API_KEY is set, else empty tuple."""
    key = os.environ.get("POSTHOG_API_KEY", "")
    if not key:
        return ()
    return (
        Script(f"""
            !function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}},o="init capture register register_once unregister opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing identify alias people.set people.set_once set_config reset get_distinct_id getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys onFeatureFlags onSessionId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);
            posthog.init('{key}', {{api_host: 'https://us.i.posthog.com', person_profiles: 'identified_only', respect_dnt: true}});
        """),
    )


def posthog_capture(event: str, distinct_id: str = "server", properties: dict | None = None):
    """Capture a server-side PostHog event. No-op when PostHog is not configured."""
    if _posthog_server is None:
        return
    try:
        _posthog_server.capture(distinct_id, event, properties or {})
    except Exception as e:
        logging.warning(f"PostHog capture failed: {e}")


app, rt = fast_app(
    pico=False,
    secret_key=SESSION_SECRET,
    hdrs=(
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Link(
            rel="icon",
            type="image/svg+xml",
            href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%234f46e5'/%3E%3Ctext x='16' y='23' font-size='20' font-family='serif' font-weight='bold' fill='white' text-anchor='middle'%3ER%3C/text%3E%3C/svg%3E",
        ),
        # Preconnect to CDN domains for faster resource loading
        Link(rel="preconnect", href="https://cdn.tailwindcss.com"),
        Link(rel="preconnect", href="https://unpkg.com"),
        # Google Fonts: Playfair Display (serif) for editorial archival headings (DD-001)
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin="anonymous"),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        ),
        Script(src="https://cdn.tailwindcss.com"),
        # Tailwind config: extend font-serif to use Playfair Display (DD-001)
        Script("""
            tailwind.config = {
                theme: {
                    extend: {
                        fontFamily: {
                            serif: ['"Playfair Display"', 'Georgia', '"Times New Roman"', 'serif'],
                            display: ['"Playfair Display"', 'Georgia', '"Times New Roman"', 'serif'],
                        }
                    }
                }
            }
        """),
        # Hyperscript required for _="on click..." modal interactions
        Script(src="https://unpkg.com/hyperscript.org@0.9.12"),
        # Global: handle auth error hash fragments and recovery redirects
        Script("""
            document.addEventListener('DOMContentLoaded', function() {
                var hash = window.location.hash.substring(1);
                if (!hash) return;
                var params = new URLSearchParams(hash);
                var error = params.get('error');
                var errorCode = params.get('error_code');
                var errorDesc = params.get('error_description');

                // If user lands on wrong page with a valid recovery token, redirect
                var type = params.get('type');
                if (type === 'recovery' && params.get('access_token')) {
                    window.location.href = '/reset-password' + window.location.hash;
                    return;
                }

                if (error) {
                    var messages = {
                        'otp_expired': 'This link has expired. Please request a new one.',
                        'access_denied': 'There was a problem with your login link. Please try again.'
                    };
                    var msg = messages[errorCode] || (errorDesc ? errorDesc.replace(/\\+/g, ' ') : 'An error occurred.');

                    var container = document.getElementById('toast-container');
                    if (container) {
                        var toast = document.createElement('div');
                        toast.className = 'px-4 py-3 rounded shadow-lg flex items-center bg-red-600 text-white';
                        toast.innerHTML = '<span class="mr-2">&#10007;</span><span>' + msg + '</span>';
                        container.appendChild(toast);
                        setTimeout(function() { toast.remove(); }, 8000);
                    }

                    history.replaceState(null, '', window.location.pathname + window.location.search);
                }
            });
        """),
        # Global: intercept HTMX 401 responses to show login modal instead of swapping content
        Script("""
            document.addEventListener('htmx:beforeSwap', function(evt) {
                if (evt.detail.xhr.status === 401) {
                    evt.detail.shouldSwap = false;
                    var modal = document.getElementById('login-modal');
                    if (modal) {
                        // Update the modal message based on the triggering element
                        var trigger = evt.detail.elt;
                        var msgEl = document.getElementById('login-modal-message');
                        if (msgEl && trigger) {
                            var action = trigger.getAttribute('data-auth-action') ||
                                         trigger.innerText.trim() || 'do that';
                            msgEl.textContent = 'You need to sign in to ' + action.toLowerCase() + '.';
                        }
                        modal.classList.remove('hidden');
                    }
                }
            });
        """),
        # Global: styled confirmation dialog replacing native confirm()
        # Only intercept requests that have hx-confirm (evt.detail.question is set).
        # Without this guard, ALL htmx requests trigger an empty confirm modal.
        Script("""
            document.addEventListener('htmx:confirm', function(evt) {
                if (!evt.detail.question) return;
                evt.preventDefault();
                var modal = document.getElementById('confirm-modal');
                if (!modal) { evt.detail.issueRequest(true); return; }
                document.getElementById('confirm-modal-message').textContent = evt.detail.question;
                modal.classList.remove('hidden');
                document.getElementById('confirm-modal-yes').onclick = function() {
                    modal.classList.add('hidden');
                    evt.detail.issueRequest(true);
                };
                document.getElementById('confirm-modal-no').onclick = function() {
                    modal.classList.add('hidden');
                };
            });
        """),
        # Leaflet map auto-init: finds [data-testid="location-map"] elements and
        # loads Leaflet + initializes maps. Uses data-lat/data-lng/data-label attributes.
        Script("""
            document.addEventListener('DOMContentLoaded', function() {
                var maps = document.querySelectorAll('[data-testid="location-map"]');
                if (!maps.length) return;
                // Load Leaflet JS dynamically
                var script = document.createElement('script');
                script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
                script.onload = function() {
                    maps.forEach(function(el) {
                        if (el._leaflet_id) return;
                        var lat = parseFloat(el.dataset.lat);
                        var lng = parseFloat(el.dataset.lng);
                        var label = el.dataset.label || '';
                        var draggable = el.dataset.draggable === 'true';
                        if (isNaN(lat) || isNaN(lng)) return;
                        var map = L.map(el.id).setView([lat, lng], 10);
                        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                            attribution: '&copy; OSM &copy; CARTO',
                            subdomains: 'abcd',
                            maxZoom: 19
                        }).addTo(map);
                        L.marker([lat, lng], draggable ? {draggable: true} : {}).addTo(map)
                            .bindPopup('<strong>' + label + '</strong>');
                        setTimeout(function() { map.invalidateSize(); }, 100);
                    });
                };
                document.head.appendChild(script);
            });
        """),
        # Mobile sidebar toggle
        Script("""
            function toggleSidebar() {
                var sidebar = document.getElementById('sidebar');
                var overlay = document.getElementById('sidebar-overlay');
                if (sidebar && overlay) {
                    sidebar.classList.toggle('-translate-x-full');
                    overlay.classList.toggle('hidden');
                }
            }
            function closeSidebar() {
                var sidebar = document.getElementById('sidebar');
                var overlay = document.getElementById('sidebar-overlay');
                if (sidebar && overlay) {
                    sidebar.classList.add('-translate-x-full');
                    overlay.classList.add('hidden');
                }
            }
        """),
        # Mobile nav: inject hamburger menu on public pages that have hidden nav links
        # Triggers below md breakpoint (768px) — slides from right with scrim + ESC key
        Script("""
            document.addEventListener('DOMContentLoaded', function() {
                // Skip if sidebar already exists (admin/command center pages)
                if (document.getElementById('sidebar')) return;

                // Find the nav with hidden links (supports both sm:flex and md:flex)
                var navs = document.querySelectorAll('nav');
                var targetNav = null;
                var hiddenDiv = null;
                for (var i = 0; i < navs.length; i++) {
                    var divs = navs[i].querySelectorAll('div');
                    for (var j = 0; j < divs.length; j++) {
                        var cn = divs[j].className || '';
                        if (cn.indexOf('hidden') !== -1 &&
                            (cn.indexOf('sm:flex') !== -1 || cn.indexOf('md:flex') !== -1)) {
                            hiddenDiv = divs[j]; targetNav = navs[i]; break;
                        }
                    }
                    if (targetNav) break;
                }
                if (!targetNav || !hiddenDiv) return;

                // Upgrade sm:flex to md:flex so hamburger shows below 768px
                hiddenDiv.className = hiddenDiv.className.replace('sm:flex', 'md:flex');

                // Collect links from the hidden nav
                var links = hiddenDiv.querySelectorAll('a');
                if (links.length === 0) return;

                // Helper to close mobile nav
                function closeMobileNav() {
                    var o = document.getElementById('mobile-nav-overlay');
                    if (o) {
                        o.querySelector('.mobile-nav-panel').style.transform = 'translateX(100%)';
                        setTimeout(function() {
                            o.classList.add('hidden');
                            o.style.display = 'none';
                        }, 200);
                    }
                }
                function openMobileNav() {
                    var o = document.getElementById('mobile-nav-overlay');
                    if (o) {
                        o.style.display = 'block';
                        o.classList.remove('hidden');
                        requestAnimationFrame(function() {
                            o.querySelector('.mobile-nav-panel').style.transform = 'translateX(0)';
                        });
                    }
                }

                // Create mobile overlay (slides from right)
                var overlay = document.createElement('div');
                overlay.id = 'mobile-nav-overlay';
                overlay.className = 'hidden fixed inset-0 z-[60]';
                overlay.style.display = 'none';
                overlay.innerHTML =
                    '<div onclick="closeMobileNav()" class="absolute inset-0 bg-black/50 transition-opacity"></div>' +
                    '<div class="mobile-nav-panel absolute top-0 right-0 w-72 h-full bg-slate-800 shadow-xl overflow-y-auto transition-transform duration-200" style="transform:translateX(100%)">' +
                    '<div class="flex items-center justify-between px-4 py-4 border-b border-slate-700">' +
                    '<span class="text-lg font-bold text-white">Rhodesli</span>' +
                    '<button onclick="closeMobileNav()" class="text-slate-400 hover:text-white p-1" type="button" aria-label="Close menu">' +
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>' +
                    '</button></div><div class="py-2 px-2" id="mobile-nav-links"></div></div>';
                document.body.appendChild(overlay);

                // Expose close/open globally for inline handlers
                window.closeMobileNav = closeMobileNav;
                window.openMobileNav = openMobileNav;

                // Populate links
                var linkContainer = document.getElementById('mobile-nav-links');
                for (var k = 0; k < links.length; k++) {
                    var text = links[k].textContent.trim();
                    if (!text || text === '|') continue;
                    var a = document.createElement('a');
                    a.href = links[k].href;
                    a.textContent = text;
                    a.className = 'block px-4 py-3 text-slate-200 hover:bg-slate-700/50 hover:text-white text-base font-medium rounded-lg transition-colors';
                    a.onclick = function() { closeMobileNav(); };
                    linkContainer.appendChild(a);
                }

                // Find or create hamburger button container
                var innerDiv = targetNav.querySelector('div');
                if (innerDiv) {
                    // Remove any existing hamburger to avoid duplicates
                    var existing = innerDiv.querySelector('[aria-label="Open navigation menu"]');
                    if (!existing) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'md:hidden text-white p-1 -ml-1 mr-2 flex-shrink-0';
                        btn.setAttribute('aria-label', 'Open navigation menu');
                        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>';
                        btn.onclick = function() { openMobileNav(); };
                        innerDiv.insertBefore(btn, innerDiv.firstChild);
                    }
                }

                // ESC key: hook into existing global keydown (no extra listener)
                var _origOnKeydown = window.onkeydown;
                window.onkeydown = function(e) {
                    if (e.key === 'Escape') closeMobileNav();
                    if (_origOnKeydown) _origOnKeydown(e);
                };
            });
        """),
        *_posthog_script(),
    ),
    static_path=str(static_path),
)


# --- COMMUNITY ROUTING MIDDLEWARE ---
# Extracts community from /c/{slug}/... URL prefix, rewrites path for downstream routes.
# Default community is "rhodes" when no /c/ prefix is present.
from starlette.middleware.base import BaseHTTPMiddleware

_community_slug_pattern = re.compile(r"^/c/([a-z0-9_-]+)(/.*)?$")

# Paths that should NOT be intercepted by community middleware
_COMMUNITY_SKIP_PREFIXES = ("/static/", "/api/", "/_")


class CommunityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        request.state.community_prefixed = False

        # Skip static/API routes entirely
        for prefix in _COMMUNITY_SKIP_PREFIXES:
            if path.startswith(prefix):
                request.state.community_slug = "rhodes"
                request.state.community = None  # lazy-loaded if needed
                return await call_next(request)

        # Check for /c/{slug}/ prefix
        match = _community_slug_pattern.match(path)
        if match:
            slug = match.group(1)
            remaining_path = match.group(2) or "/"
            request.state.community_slug = slug
            request.state.community_prefixed = True
            # Rewrite the path to remove the /c/{slug} prefix
            request.scope["path"] = remaining_path
        else:
            request.state.community_slug = "rhodes"  # default

        # Fetch community data (cached)
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug(request.state.community_slug)
        request.state.community = community

        # If slug was explicit but community not found, return 404
        if match and community is None:
            from starlette.responses import HTMLResponse

            return HTMLResponse(
                content=f"<h1>Community not found: {request.state.community_slug}</h1>",
                status_code=404,
            )

        response = await call_next(request)
        return response


app.add_middleware(CommunityMiddleware)


# --- COMMUNITY DATA SCOPING UTILITIES ---


def community_url_prefix(slug: str | None) -> str:
    """Return URL prefix for community-scoped links.

    Returns "" for Rhodes/default (bare URLs), "/c/{slug}" for others.
    """
    if not slug or slug == "rhodes":
        return ""
    return f"/c/{slug}"


def _cross_community_badge(identity_id: str, current_community: dict | None) -> "FT | None":
    """Return a badge if identity belongs to a DIFFERENT community than current.

    COMMUNITY-014: Shows "[Community Name]" badge when viewing cross-community content.
    Returns None if same community or no community context.
    """
    if current_community is None:
        return None

    current_slug = current_community.get("slug", "rhodes")
    current_id = current_community.get("id")
    if not current_id:
        return None

    # Check cached identity sets for all communities
    from app.supabase_data import load_communities

    communities = load_communities()
    if not communities:
        return None

    # First check if identity belongs to current community — if so, no badge needed
    current_ids = _get_community_identity_ids(current_community)
    if current_ids and identity_id in current_ids:
        return None  # Identity is in current community, no cross-community badge

    for comm in communities:
        comm_slug = comm.get("slug", "")
        comm_id = comm.get("id")
        if not comm_id or comm_slug == current_slug:
            continue  # skip current community

        # Check if identity belongs to this other community
        other_ids = _get_community_identity_ids(comm)
        if other_ids and identity_id in other_ids:
            comm_name = comm.get("name", comm_slug.replace("-", " ").title())
            return Span(
                comm_name,
                cls="text-xs px-1.5 py-0.5 rounded bg-blue-600/30 text-blue-300 border border-blue-500/30",
                title=f"This person appears in the {comm_name} archive",
            )

    return None


def _identity_home_community_slug(identity_id: str, current_community: dict | None) -> str | None:
    """Return the slug of the community an identity belongs to, if different from current.

    Returns None if the identity belongs to the current community or no cross-community
    membership is found. Used for building correct navigation links to cross-community identities.
    """
    if current_community is None:
        return None

    current_slug = current_community.get("slug", "rhodes")
    current_id = current_community.get("id")
    if not current_id:
        return None

    from app.supabase_data import load_communities

    communities = load_communities()
    if not communities:
        return None

    for comm in communities:
        comm_slug = comm.get("slug", "")
        comm_id = comm.get("id")
        if not comm_id or comm_slug == current_slug:
            continue

        other_ids = _get_community_identity_ids(comm)
        if other_ids and identity_id in other_ids:
            return comm_slug

    return None


# Cached community photo/identity ID sets (120s TTL)
_community_photo_ids_cache: dict = {}  # community_id -> set[str]
_community_identity_ids_cache: dict = {}  # community_id -> set[str]
_community_ids_cache_ts: float = 0.0
_COMMUNITY_IDS_CACHE_TTL: float = 120.0


def _get_community_photo_ids(community: dict | None) -> set[str] | None:
    """Return photo IDs for a community, or None when scoping cannot be computed.

    Results cached for 120s. Returning None means "fall back to no filtering"
    because there is no reliable community-photo scope available.
    ALL communities including Rhodes get photo-derived scoping to prevent
    cross-community leakage when the community mapping is available.
    """
    if community is None:
        return None

    global _community_photo_ids_cache, _community_ids_cache_ts
    community_id = community.get("id")
    if not community_id:
        return None  # Can't scope without a community ID — fall back to no filtering

    now = time.time()
    if now - _community_ids_cache_ts < _COMMUNITY_IDS_CACHE_TTL and community_id in _community_photo_ids_cache:
        return _community_photo_ids_cache[community_id]

    from app.supabase_data import load_photos_for_community, get_supabase_client

    # If Supabase is unavailable (local dev, tests), skip scoping to avoid empty results
    if not get_supabase_client():
        _community_photo_ids_cache[community_id] = None
        _community_ids_cache_ts = now
        return None

    photo_ids = load_photos_for_community(community_id)
    if photo_ids is None:
        _community_photo_ids_cache[community_id] = None
        _community_ids_cache_ts = now
        return None

    result = set(photo_ids)

    # Resolve aliases: community photos use inbox_* IDs in Supabase,
    # but _photo_cache uses SHA256(filename)[:16] IDs. Include both formats
    # so all callers (photos section, identity derivation) match correctly.
    _build_caches()
    if _photo_id_aliases:
        aliases_to_add = set()
        for pid in result:
            alias = _photo_id_aliases.get(pid)
            if alias:
                aliases_to_add.add(alias)
        # Also reverse: SHA256 IDs that alias FROM community IDs
        for alias_from, alias_to in _photo_id_aliases.items():
            if alias_from in result:
                aliases_to_add.add(alias_to)
        result.update(aliases_to_add)

    _community_photo_ids_cache[community_id] = result
    _community_ids_cache_ts = now
    return result


def _get_community_identity_ids(community: dict | None) -> set[str] | None:
    """Return identity IDs for a community, or None when scoping cannot be computed.

    Uses photo-derived identity set (AD-216): finds all identities that have faces
    in photos belonging to this community. This is the source of truth — if a person
    has faces in a community's photos, they belong to that community.

    Results cached for 120s. Returning None means "fall back to no filtering"
    because a reliable photo-derived scope is unavailable. ALL communities
    including Rhodes get photo-derived scoping to prevent cross-community
    leakage when the mapping is available.
    """
    if community is None:
        return None

    global _community_identity_ids_cache, _community_ids_cache_ts
    community_id = community.get("id")
    if not community_id:
        return None  # Can't scope without a community ID — fall back to no filtering

    now = time.time()
    if now - _community_ids_cache_ts < _COMMUNITY_IDS_CACHE_TTL and community_id in _community_identity_ids_cache:
        return _community_identity_ids_cache[community_id]

    # Photo-derived identity set: get all identities with faces in community photos
    community_photo_ids = _get_community_photo_ids(community)
    if community_photo_ids is None:
        return None

    if not community_photo_ids:
        _community_identity_ids_cache[community_id] = set()
        _community_ids_cache_ts = now
        return set()

    _build_caches()
    registry = load_registry()

    # Resolve community photo IDs to SHA256 cache IDs (the format used by _face_to_photo_cache).
    # community_photo_ids from Supabase use inbox_* format, but _face_to_photo_cache uses SHA256.
    # _photo_id_aliases maps inbox_id → SHA256_cache_id.
    resolved_photo_ids = set(community_photo_ids)  # Start with original IDs
    if _photo_id_aliases:
        for cpid in community_photo_ids:
            alias = _photo_id_aliases.get(cpid)
            if alias:
                resolved_photo_ids.add(alias)
        # Also add reverse: SHA256 IDs that alias TO community IDs
        for alias_from, alias_to in _photo_id_aliases.items():
            if alias_from in community_photo_ids:
                resolved_photo_ids.add(alias_to)

    # Collect all face IDs from community photos
    community_face_ids = set()
    if _face_to_photo_cache:
        for face_id, photo_id in _face_to_photo_cache.items():
            if photo_id in resolved_photo_ids:
                community_face_ids.add(face_id)

    # Find identities that own these faces
    result = set()
    for face_id in community_face_ids:
        identity = get_identity_for_face(registry, face_id)
        if identity:
            iid = identity.get("identity_id")
            if iid:
                result.add(iid)

    _community_identity_ids_cache[community_id] = result
    _community_ids_cache_ts = now
    return result


# --- INSTRUMENTATION LIFECYCLE HOOKS ---
@app.on_event("startup")
async def startup_event():
    """Initialize required directories, sync from Supabase, clean temp files, and log start."""
    # Deployment safety: ensure all required directories exist
    required_dirs = [
        data_path / "staging",
        data_path / "inbox",
        data_path / "cleanup_backups",
        static_path / "crops",
        Path(__file__).resolve().parent.parent / "logs",
    ]
    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

    # AD-162: Clean up temp files from previous runs to prevent disk exhaustion.
    _startup_disk_cleanup(data_path)

    # AD-135: Sync user data from Supabase on startup.
    # This ensures deploys can never lose user-entered data —
    # even if the Docker bundle has stale JSON, Supabase has the truth.
    try:
        from app.supabase_data import sync_from_supabase_on_startup

        sync_from_supabase_on_startup(data_path)
    except Exception as e:
        logging.warning(f"Supabase startup sync failed (using existing JSON): {e}")

    # Prewarm UI caches in a background thread so server starts accepting
    # requests immediately. Caches are built lazily on first access if the
    # background thread hasn't finished yet.
    import threading

    def _prewarm_caches():
        try:
            t0 = time.perf_counter()
            _build_caches()
            _load_date_labels()
            get_crop_files()
            logging.info(f"UI caches prewarmed in {time.perf_counter() - t0:.2f}s")
        except Exception as e:
            logging.warning(f"UI cache prewarm failed (lazy loading on first request): {e}")

    threading.Thread(target=_prewarm_caches, daemon=True, name="cache-prewarm").start()

    # Session 105b: Startup parity check — compare JSON and Supabase counts
    # Runs in background thread to avoid blocking startup
    def _startup_parity_check():
        try:
            from app.page_routes import _check_data_parity

            registry = load_registry()
            photo_index_path = data_path / "photo_index.json"
            photo_count = 0
            if photo_index_path.exists():
                import json as _json_parity

                with open(photo_index_path) as f:
                    photo_count = len(_json_parity.load(f).get("photos", {}))

            total_identities = len(registry.list_identities(include_merged=True))
            result = _check_data_parity(photo_count, total_identities)

            if result.get("error"):
                logging.warning(f"Startup parity check skipped: {result['error']}")
                return

            if result.get("synced"):
                logging.info("Startup parity check: JSON and Supabase in sync")
                return

            photo_diff = result.get("photo_diff", 0)
            id_diff = result.get("identity_diff", 0)
            pg_ids = result.get("identities_pg", 0)

            if photo_diff > 0:
                logging.warning(
                    f"Startup parity: photo mismatch — JSON={result['photos_json']} PG={result['photos_pg']}"
                )
            if total_identities > (pg_ids or 0):
                logging.warning(f"Startup parity: identities in JSON > PG — JSON={total_identities} PG={pg_ids}")
            elif (pg_ids or 0) > total_identities and id_diff > 100:
                logging.error(
                    f"Startup parity: {id_diff} stale Supabase identity rows detected — "
                    f"run /api/admin/reconcile?action=prune to clean up"
                )
        except Exception as e:
            logging.warning(f"Startup parity check failed: {e}")

    threading.Thread(target=_startup_parity_check, daemon=True, name="parity-check").start()

    get_event_recorder().record(
        "RUN_START", {"action": "server_start", "timestamp_utc": datetime.utcnow().isoformat()}, actor="system"
    )


def _startup_disk_cleanup(base_path: Path):
    """Clean stale temp files and prune old backups at startup (AD-162).

    Removes:
    - Staging directories older than 1 hour (incomplete uploads)
    - Stale .status.json and .log files in inbox/ older than 24 hours
    - Old .bak files (keep most recent 3 per type)
    - .tmp files left from atomic writes

    Logs disk usage for monitoring.
    """
    import time

    now = time.time()

    # Log disk usage — check BOTH root FS and volume mount
    try:
        import shutil as _shutil_disk

        total, used, free = _shutil_disk.disk_usage("/")
        free_mb = free / (1024 * 1024)
        used_pct = (used / total) * 100
        logging.info(f"Root FS: {used_pct:.1f}% used, {free_mb:.0f}MB free")

        storage_dir = os.environ.get("STORAGE_DIR", "")
        if storage_dir and Path(storage_dir).exists():
            vt, vu, vf = _shutil_disk.disk_usage(storage_dir)
            vol_free_mb = vf / (1024 * 1024)
            vol_used_pct = (vu / vt) * 100
            vol_total_mb = vt / (1024 * 1024)
            logging.info(
                f"Volume ({storage_dir}): {vol_used_pct:.1f}% used, {vol_free_mb:.0f}MB free of {vol_total_mb:.0f}MB total"
            )
            if vol_free_mb < 50:
                logging.warning(f"LOW VOLUME SPACE: only {vol_free_mb:.0f}MB free on {storage_dir}!")
    except Exception:
        pass

    cleaned = 0

    # Clean stale staging directories (older than 1 hour)
    # BUT preserve staging dirs for uploads still in "pending" or "staged" status
    staging_dir = base_path / "staging"
    if staging_dir.exists():
        # Build set of job_ids that still need their staging files
        pending_job_ids = set()
        try:
            pending = _load_pending_uploads()
            for jid, upload in pending.get("uploads", {}).items():
                if upload.get("status") in ("pending", "staged"):
                    pending_job_ids.add(jid)
        except Exception:
            pass

        for item in list(staging_dir.iterdir()):
            try:
                # Skip directories that still have pending uploads
                if item.is_dir() and item.name in pending_job_ids:
                    continue
                age = now - item.stat().st_mtime
                if age > 3600:  # 1 hour
                    if item.is_dir():
                        import shutil

                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    cleaned += 1
            except OSError:
                pass

    # Clean stale inbox status/log files (older than 24 hours)
    inbox_dir = base_path / "inbox"
    if inbox_dir.exists():
        for item in list(inbox_dir.iterdir()):
            try:
                if item.suffix in (".json", ".log") and (now - item.stat().st_mtime) > 86400:
                    item.unlink(missing_ok=True)
                    cleaned += 1
            except OSError:
                pass

    # Clean .tmp files from atomic writes
    for item in list(base_path.iterdir()):
        try:
            if item.suffix == ".tmp" and item.is_file():
                item.unlink(missing_ok=True)
                cleaned += 1
        except OSError:
            pass

    # Prune old .bak files (keep 1 per type to save space)
    from app.sync_routes import _prune_bak_files

    _prune_bak_files(base_path, max_keep=1)

    # Prune data/backups/ — the BIGGEST space consumer on the volume.
    # These are full snapshot backups. Keep only the 2 most recent.
    for dir_name in ("backups", "auto_backups", "cleanup_backups"):
        bk_dir = base_path / dir_name
        if bk_dir.exists():
            try:
                items = sorted(bk_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                keep = 2 if dir_name == "backups" else 3
                for old in items[keep:]:
                    try:
                        if old.is_dir():
                            import shutil

                            shutil.rmtree(old, ignore_errors=True)
                        else:
                            old.unlink(missing_ok=True)
                        cleaned += 1
                    except OSError:
                        pass
            except OSError:
                pass

    # Clean stale upload job directories (older than 24 hours)
    uploads_dir = base_path / "uploads"
    if uploads_dir.exists():
        for item in list(uploads_dir.iterdir()):
            try:
                if item.is_dir() and (now - item.stat().st_mtime) > 86400:
                    import shutil

                    shutil.rmtree(item, ignore_errors=True)
                    cleaned += 1
            except OSError:
                pass

    # Prune comparison_results.json lock files
    for item in list(base_path.iterdir()):
        try:
            if item.suffix == ".lock" and item.is_file() and (now - item.stat().st_mtime) > 3600:
                item.unlink(missing_ok=True)
                cleaned += 1
        except OSError:
            pass

    if cleaned > 0:
        logging.info(f"Startup cleanup: removed {cleaned} stale temp files")


@app.on_event("shutdown")
async def shutdown_event():
    """Log the end of a session/run."""
    get_event_recorder().record(
        "RUN_END", {"action": "server_shutdown", "timestamp_utc": datetime.utcnow().isoformat()}, actor="system"
    )


# ---------------------------------------


@app.get("/photos/{filename:path}")
async def serve_photo(filename: str):
    """
    Serve photos from raw_photos/.

    All photos (original and uploaded) live in a single directory.
    """
    photo_path = photos_path / filename
    if photo_path.exists() and photo_path.is_file():
        return FileResponse(photo_path)

    return Response(content=f"Photo not found: {filename}", status_code=404, media_type="text/plain")


from starlette.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Note: Sentry ASGI integration is auto-detected by sentry_sdk.init() above.
# No explicit middleware wrapping needed — it hooks into Starlette/ASGI automatically.


def _reorder_routes_atomic():
    """Reorder routes so path-matching routes take precedence over catch-all.

    Uses atomic list slice assignment instead of pop/insert to avoid
    race conditions when xdist workers import this module concurrently.
    Routes with {filename:path} or {filepath:path} patterns must precede
    FastHTML's catch-all /{fname:path}.{ext:static} route.
    """
    priority_paths = {
        "/photos/{filename:path}",
        "/admin/staging-preview/{job_id}/{filename:path}",
        "/api/sync/staged/download/{filepath:path}",
    }
    priority_names = {"static"}

    priority_routes = []
    other_routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        name = getattr(route, "name", None)
        if path in priority_paths or name in priority_names:
            priority_routes.append(route)
        else:
            other_routes.append(route)
    app.routes[:] = priority_routes + other_routes


_reorder_routes_atomic()


# ---------------------------------------------------------------------------
# Global 404 handler — styled page for any unrecognized route
# ---------------------------------------------------------------------------


@app.exception_handler(404)
async def custom_404_handler(request, exc):
    page_html = (
        to_xml(
            Title("Page Not Found - Rhodesli"),
        )
        + to_xml(
            Script(src="https://cdn.tailwindcss.com"),
        )
        + to_xml(Style("html, body { margin: 0; } body { background-color: #0f172a; }"))
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
                        H1("Page not found", cls="text-2xl font-serif font-bold text-white mb-3"),
                        P("The page you're looking for doesn't exist.", cls="text-slate-400 mb-8"),
                        A(
                            "Explore the Archive",
                            href="/",
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


# Registry path - single source of truth
REGISTRY_PATH = data_path / "identities.json"

# Registry TTL cache — avoids reloading 2500+ identities from Supabase on every request
_registry_cache = None
_registry_cache_ts: float = 0.0
_registry_cache_key: tuple[str, str] | None = None
_REGISTRY_CACHE_TTL: float = 120.0


def load_registry():
    """Load the identity registry (backend authority).

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Uses a 120-second TTL cache to avoid repeated Supabase queries.

    Returns an empty registry if the source is missing or corrupted,
    so the server never crashes on bad data.
    """
    global _registry_cache, _registry_cache_ts, _registry_cache_key
    import time as _time

    now = _time.time()
    cache_key = (DATA_SOURCE, str(REGISTRY_PATH))
    if (
        _registry_cache is not None
        and _registry_cache_key == cache_key
        and (now - _registry_cache_ts) < _REGISTRY_CACHE_TTL
    ):
        logging.debug("registry_cache_hit ttl_remaining=%.1fs", _REGISTRY_CACHE_TTL - (now - _registry_cache_ts))
        return _registry_cache

    logging.debug("registry_cache_miss source=%s", DATA_SOURCE)
    if DATA_SOURCE == "postgres":
        try:
            registry = IdentityRegistry.load_from_postgres()
            if registry is not None:
                _registry_cache = registry
                _registry_cache_ts = now
                _registry_cache_key = cache_key
                logging.debug("registry_cache_populated source=postgres count=%d", len(registry._identities))
                return registry
            logging.warning("Postgres load returned None, falling back to JSON")
        except Exception as e:
            logging.warning(f"Postgres identity load failed, falling back to JSON: {e}")

    if REGISTRY_PATH.exists():
        try:
            registry = IdentityRegistry.load(REGISTRY_PATH)
            _registry_cache = registry
            _registry_cache_ts = now
            _registry_cache_key = cache_key
            return registry
        except (ValueError, OSError) as e:
            logging.error(f"Failed to load identity registry from {REGISTRY_PATH}: {e}")
            return IdentityRegistry()
    return IdentityRegistry()


def save_registry(registry, confirmed_identity_info=None):
    """Save registry with atomic write + sync to Supabase (AD-135).

    When DATA_SOURCE=postgres, writes to Supabase only (no JSON).
    When DATA_SOURCE=json (default), writes JSON + shadow-writes to Supabase.

    Args:
        registry: The IdentityRegistry to save
        confirmed_identity_info: Optional dict with keys:
            - identity_id: str
            - identity_name: str
            - user_id: str (Supabase auth user ID of the admin)
            - user_email: str (email for Resend notification delivery)
    """
    global _registry_cache, _registry_cache_key, _registry_cache_ts
    # Repopulate cache with the registry we just saved (avoid redundant reload)
    _registry_cache = registry
    _registry_cache_ts = time.time()
    # Keep cache_key — it will match on next load

    # Clear face-identity lookup cache so get_identity_for_face() rebuilds it
    # from the updated _identities dict. Without this, merges/tags appear to
    # succeed but the stale cache causes the old mapping to be returned on
    # the next render, silently reverting the tag (BUG-001 / FB-141).
    registry_dict = getattr(registry, "__dict__", None)
    if registry_dict is not None:
        registry_dict.pop("_face_identity_lookup_cache", None)

    # Invalidate neighbors cache — stale after any identity change
    try:
        from app.identity_routes import invalidate_neighbors_cache

        invalidate_neighbors_cache()
    except ImportError:
        pass

    # Always write JSON as backup (Session 105b: write-through)
    registry.save(REGISTRY_PATH)

    identities_copy = dict(registry._identities)

    if DATA_SOURCE == "postgres":
        # Synchronous Supabase write — failures are visible (Session 105b)
        try:
            from app.supabase_data import shadow_write_identities_batch, sync_identity_overrides

            sync_identity_overrides(identities_copy)
            items = [dict(v, identity_id=k) for k, v in identities_copy.items()]
            shadow_write_identities_batch(items, strict=True)
        except Exception as e:
            logging.error(f"Postgres save_registry failed: {e}")
            # JSON backup already written above
        return

    # JSON mode: shadow-write to Supabase in background
    def _background_supabase_sync(identities_dict):
        try:
            from app.supabase_data import sync_identity_overrides

            sync_identity_overrides(identities_dict)
        except Exception as e:
            logging.warning(f"Supabase identity sync failed (degraded mode): {e}")
        try:
            from app.supabase_data import shadow_write_identities_batch

            items = [dict(v, identity_id=k) for k, v in identities_dict.items()]
            shadow_write_identities_batch(items)
        except Exception as e:
            logging.warning(f"Supabase identity shadow sync failed: {e}")

    import threading

    threading.Thread(
        target=_background_supabase_sync,
        args=(identities_copy,),
        daemon=True,
    ).start()

    # Fire notification if an identity was just confirmed
    if confirmed_identity_info:

        def _fire_notification(info):
            try:
                from app.notification_routes import create_identity_confirmed_notification

                # Look up photo_ids for this identity
                photo_ids = []
                try:
                    identity = registry.get_identity(info["identity_id"])
                    face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
                    photo_reg = load_photo_registry()
                    for fid in face_ids:
                        pid = photo_reg.face_to_photo.get(fid)
                        if pid and pid not in photo_ids:
                            photo_ids.append(pid)
                except Exception:
                    pass
                create_identity_confirmed_notification(
                    identity_id=info["identity_id"],
                    identity_name=info["identity_name"],
                    photo_ids=photo_ids,
                    user_id=info.get("user_id"),
                    user_email=info.get("user_email"),
                )
            except Exception:
                pass  # Notifications are best-effort

        threading.Thread(target=_fire_notification, args=(confirmed_identity_info,), daemon=True).start()


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

# _pl imported from app.utils


def _format_display_date(date_str: str, include_time: bool = False) -> str | None:
    """Format an ISO timestamp for UI display."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if include_time:
            base = dt.strftime("%b %-d, %Y at %-I:%M %p")
            tz_name = dt.tzname()
            return f"{base} {tz_name}" if tz_name else base
        return dt.strftime("%b %-d, %Y")
    except (TypeError, ValueError):
        return None


def _get_upload_provenance_display(photo: dict) -> dict | None:
    """Return shared upload/archive provenance strings for photo UIs."""
    upload_date_label = _format_display_date(photo.get("upload_date", ""), include_time=True)
    uploaded_by = (photo.get("uploaded_by") or "").strip()

    if uploaded_by:
        headline = f"Uploaded {upload_date_label}" if upload_date_label else f"Uploaded by {uploaded_by}"
        subline = f"by {uploaded_by}" if upload_date_label else None
        full_text = f"Uploaded by {uploaded_by}"
        if upload_date_label:
            full_text += f" on {upload_date_label}"
        return {
            "headline": headline,
            "subline": subline,
            "full_text": full_text,
        }

    if upload_date_label:
        return {
            "headline": f"Archive entry {upload_date_label}",
            "subline": "Uploader not recorded for this import",
            "full_text": f"Archive entry recorded on {upload_date_label} · uploader not recorded for this import",
        }

    return None


def _build_upload_provenance_line(photo: dict):
    """Build the archive-entry/source line shown on photo pages."""
    provenance = _get_upload_provenance_display(photo)
    if provenance:
        return Span(provenance["full_text"], cls="text-xs text-slate-500")

    # Source is already shown in the Collection/Source/URL section of photo context modal.
    # Don't duplicate it here (BUG-5, Session 96e-cont6).
    return None


# =============================================================================
# USER ACTION LOGGING (LEGACY - REPLACED BY EVENT RECORDER)
# =============================================================================
# We keep this for backward compatibility if needed, but EventRecorder is primary now.

logs_path = Path(__file__).resolve().parent.parent / "logs"


def _check_admin(sess) -> Response | None:
    """Return a 401/403/redirect Response if user is not admin, else None.
    When auth is disabled, always allows access.
    Returns 401 (not 303) so HTMX beforeSwap handler can show login modal."""
    if not is_auth_enabled():
        return None  # Auth disabled — everyone has access
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    if not user.is_admin:
        return Response(
            to_xml(toast("You don't have permission to do this.", "error")),
            status_code=403,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )
    return None


def _check_login(sess) -> Response | None:
    """Return a 401/redirect Response if user is not logged in, else None.
    When auth is disabled, always allows access.
    Returns 401 (not 303) so HTMX beforeSwap handler can show login modal."""
    if not is_auth_enabled():
        return None  # Auth disabled — everyone has access
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    return None


def _get_user_role(sess) -> str:
    """Get the user's role string for UI rendering. Returns 'admin' when auth disabled."""
    if not is_auth_enabled():
        return "admin"
    user = get_current_user(sess or {})
    if not user:
        return "viewer"
    return user.role


def _check_contributor(sess) -> Response | None:
    """ROLE-002: Return 401/403 if user is not at least a contributor, else None.
    Allows admin and contributor roles. Rejects viewers and anonymous users.
    When auth is disabled, always allows access."""
    if not is_auth_enabled():
        return None
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    if user.role in ("admin", "contributor"):
        return None
    return Response(
        to_xml(toast("Contributor access required.", "error")),
        status_code=403,
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
    )


def _auth_disabled_warning():
    """Return a warning banner when auth is disabled, or None when enabled."""
    if is_auth_enabled():
        return None
    return Div(
        P(
            "Authentication is disabled. All admin features are publicly accessible.",
            cls="text-amber-400 text-xs text-center",
        ),
        cls="bg-amber-900/30 border border-amber-700/30 rounded px-3 py-1.5 mb-3",
        data_testid="auth-disabled-warning",
    )


def log_user_action(action: str, **kwargs) -> None:
    """
    Log a user action to the append-only user_actions.log.

    Format: ISO_TIMESTAMP | ACTION | key=value key=value ...

    Args:
        action: Action name (e.g., "DETACH", "MERGE", "RENAME")
        kwargs: Key-value pairs to log
    """
    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / "user_actions.log"

    timestamp = datetime.now(timezone.utc).isoformat()
    kvs = " ".join(f"{k}={v}" for k, v in kwargs.items())
    line = f"{timestamp} | {action} | {kvs}\n"

    with open(log_file, "a") as f:
        f.write(line)

    try:
        from app.supabase_data import sync_audit_log_entry

        target_id = (
            kwargs.get("annotation_id")
            or kwargs.get("identity_id")
            or kwargs.get("target_identity_id")
            or kwargs.get("target_id")
            or kwargs.get("photo_id")
            or kwargs.get("job_id")
            or action.lower()
        )
        if kwargs.get("annotation_id"):
            target_type = "annotation_action"
        elif kwargs.get("identity_id") or kwargs.get("target_identity_id"):
            target_type = "identity_action"
        elif kwargs.get("photo_id"):
            target_type = "photo_action"
        elif kwargs.get("job_id"):
            target_type = "upload_action"
        else:
            target_type = "user_action"
        actor = (
            kwargs.get("admin") or kwargs.get("user") or kwargs.get("actor") or kwargs.get("uploaded_by") or "system"
        )
        sync_audit_log_entry(
            action=action,
            target_id=str(target_id),
            actor=str(actor),
            entry_data={"timestamp": timestamp, **kwargs},
            target_type=target_type,
        )
    except Exception as e:
        # Structured Supabase audit is best-effort and must never block local writes.
        logging.warning(f"Supabase audit log sync failed: {e}")


# =============================================================================
# PENDING UPLOADS REGISTRY
# =============================================================================


def _load_pending_uploads() -> dict:
    """Load pending uploads registry."""
    path = data_path / "pending_uploads.json"
    if not path.exists():
        return {"uploads": {}}
    with open(path) as f:
        return json.load(f)


def _save_pending_uploads(data: dict) -> None:
    """Save pending uploads registry (atomic write)."""
    path = data_path / "pending_uploads.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.rename(path)


def _count_pending_uploads() -> int:
    """Count pending uploads awaiting review or processing."""
    data = _load_pending_uploads()
    return sum(1 for u in data["uploads"].values() if u["status"] in ("pending", "staged"))


# =============================================================================
# CLUSTERING PROPOSALS (from data/proposals.json)
# =============================================================================

_proposals_cache = None
_proposal_target_counts_cache = None


def _load_proposals() -> dict:
    """Load clustering proposals generated by cluster_new_faces.py."""
    global _proposals_cache, _proposal_target_counts_cache
    if _proposals_cache is not None:
        return _proposals_cache
    path = data_path / "proposals.json"
    if not path.exists():
        _proposals_cache = {"proposals": [], "generated_at": ""}
        _proposal_target_counts_cache = {}
        return _proposals_cache
    with open(path) as f:
        _proposals_cache = json.load(f)
    _proposal_target_counts_cache = None
    return _proposals_cache


def _get_proposals_for_identity(identity_id: str) -> list[dict]:
    """Get all clustering proposals where this identity is the source."""
    data = _load_proposals()
    return [p for p in data.get("proposals", []) if p.get("source_identity_id") == identity_id]


def _get_proposal_targets_for_identity(identity_id: str) -> list[dict]:
    """Get all clustering proposals where this identity is the target."""
    data = _load_proposals()
    return [p for p in data.get("proposals", []) if p.get("target_identity_id") == identity_id]


def _get_proposal_target_count(identity_id: str) -> int:
    """Get the number of clustering proposals targeting an identity."""
    global _proposal_target_counts_cache
    if _proposal_target_counts_cache is None:
        counts = {}
        for proposal in _load_proposals().get("proposals", []):
            target_id = proposal.get("target_identity_id")
            if not target_id:
                continue
            counts[target_id] = counts.get(target_id, 0) + 1
        _proposal_target_counts_cache = counts
    return _proposal_target_counts_cache.get(identity_id, 0)


def _get_identities_with_proposals() -> set[str]:
    """Get set of source identity IDs that have clustering proposals."""
    data = _load_proposals()
    return {p["source_identity_id"] for p in data.get("proposals", [])}


def _get_best_proposal_for_identity(identity_id: str) -> dict | None:
    """Get the highest-confidence proposal for an identity."""
    proposals = _get_proposals_for_identity(identity_id)
    if not proposals:
        return None
    return min(proposals, key=lambda p: p.get("distance", float("inf")))


# =============================================================================
# DISCOVERY LAYER CACHES (date labels + search index)
# =============================================================================

_date_labels_cache = None
_search_index_cache = None
_birth_year_cache = None
_ml_review_decisions_cache = None


def _load_date_labels() -> dict:
    """Load date labels from ML pipeline output, keyed by photo_id for O(1) lookup.

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Labels are indexed by BOTH their original photo_index ID (e.g. inbox_*)
    AND the SHA256 cache ID used by _photo_cache. This dual-keying handles
    the ID mismatch between photo_index.json and the embeddings-based cache.
    """
    global _date_labels_cache
    if _date_labels_cache is not None:
        return _date_labels_cache

    if DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import load_date_labels_from_supabase

            result = load_date_labels_from_supabase()
            if result is not None:
                logging.info(f"Loaded {len(result)} date labels from Postgres")
                _date_labels_cache = result
                return _date_labels_cache
            logging.warning("Postgres date labels load returned None, falling back to JSON")
        except Exception as e:
            logging.warning(f"Postgres date labels load failed, falling back to JSON: {e}")

    _date_labels_cache = {}
    ml_data_path = data_path / "date_labels.json"
    if not ml_data_path.exists():
        return _date_labels_cache

    # Build filename → photo_index_id mapping for cross-referencing
    filename_to_index_id = {}
    try:
        photo_registry = load_photo_registry()
        for pid in photo_registry._photos:
            path = photo_registry.get_photo_path(pid)
            if path:
                filename_to_index_id[Path(path).name] = pid
    except Exception:
        pass

    try:
        with open(ml_data_path) as f:
            data = json.load(f)
        for label in data.get("labels", []):
            pid = label.get("photo_id", "")
            if pid:
                _date_labels_cache[pid] = label
                # Also key by SHA256 cache ID if the original is an inbox_* ID
                if pid.startswith("inbox_"):
                    # Extract filename from photo_index path, compute SHA256 ID
                    path = None
                    try:
                        path = photo_registry.get_photo_path(pid)
                    except Exception:
                        pass
                    if path:
                        fname = Path(path).name
                        sha_id = hashlib.sha256(fname.encode("utf-8")).hexdigest()[:16]
                        _date_labels_cache[sha_id] = label
    except Exception as e:
        logging.warning(f"Failed to load date labels: {e}")

    return _date_labels_cache


def _load_search_index() -> list:
    """Load photo search index for in-memory keyword search.

    For inbox photos, adds a SHA256-based alias photo_id so that
    _photo_cache lookups match search results.
    """
    global _search_index_cache
    if _search_index_cache is not None:
        return _search_index_cache

    _search_index_cache = []
    search_path = data_path / "photo_search_index.json"
    if not search_path.exists():
        return _search_index_cache

    # Build inbox_id → SHA256 ID mapping for cross-referencing
    index_to_sha = {}
    try:
        photo_registry = load_photo_registry()
        for pid in photo_registry._photos:
            if pid.startswith("inbox_"):
                path = photo_registry.get_photo_path(pid)
                if path:
                    fname = Path(path).name
                    sha_id = hashlib.sha256(fname.encode("utf-8")).hexdigest()[:16]
                    index_to_sha[pid] = sha_id
    except Exception:
        pass

    try:
        with open(search_path) as f:
            data = json.load(f)
        docs = data.get("documents", [])
        # Add SHA256 alias for inbox photos so _photo_cache keys match
        for doc in docs:
            pid = doc.get("photo_id", "")
            if pid in index_to_sha:
                doc["cache_photo_id"] = index_to_sha[pid]
            else:
                doc["cache_photo_id"] = pid
        _search_index_cache = docs
    except Exception as e:
        logging.warning(f"Failed to load search index: {e}")

    return _search_index_cache


def _load_birth_year_estimates() -> dict:
    """Load ML-inferred birth year estimates, keyed by identity_id.

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Returns dict mapping identity_id -> {birth_year_estimate, birth_year_confidence, ...}.
    Human-confirmed metadata.birth_year always takes priority over these estimates.
    """
    global _birth_year_cache
    if _birth_year_cache is not None:
        return _birth_year_cache

    if DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import load_birth_year_estimates_from_supabase

            result = load_birth_year_estimates_from_supabase()
            if result is not None:
                logging.info(f"Loaded {len(result)} birth year estimates from Postgres")
                _birth_year_cache = result
                return _birth_year_cache
            logging.warning("Postgres birth year estimates load returned None, falling back to JSON")
        except Exception as e:
            logging.warning(f"Postgres birth year estimates load failed, falling back to JSON: {e}")

    _birth_year_cache = {}
    # Check both possible locations (ML output dir and data dir)
    for candidate in [
        Path("rhodesli_ml/data/birth_year_estimates.json"),
        data_path / "birth_year_estimates.json",
    ]:
        if candidate.exists():
            try:
                with open(candidate) as f:
                    data = json.load(f)
                for est in data.get("estimates", []):
                    iid = est.get("identity_id", "")
                    if iid:
                        _birth_year_cache[iid] = est
            except Exception as e:
                logging.warning(f"Failed to load birth year estimates: {e}")
            break

    return _birth_year_cache


def _get_birth_year(identity_id: str, identity: dict = None, include_unreviewed: bool = True) -> tuple:
    """Get birth year for an identity, checking metadata first then ML estimates.

    Args:
        identity_id: The identity UUID
        identity: Optional identity dict (avoids re-lookup)
        include_unreviewed: If False, only return confirmed metadata birth years.
            Public-facing code should pass False (Gatekeeper pattern: AD-097).
            Admin code can pass True to see pending ML estimates.

    Returns:
        (birth_year: int or None, source: str, confidence: str or None)
        source is "confirmed" (metadata) or "ml_inferred"
    """
    # Priority 1: Human-confirmed metadata (check both top-level and nested)
    if identity:
        # Some contexts flatten metadata to top level, some nest it
        for by in [
            identity.get("birth_year"),
            (identity.get("metadata") or {}).get("birth_year"),
        ]:
            if by:
                try:
                    return int(by), "confirmed", None
                except (ValueError, TypeError):
                    pass

    # Priority 2: ML-inferred estimate (only if caller allows unreviewed data)
    if include_unreviewed:
        # Skip rejected estimates
        decisions = _load_ml_review_decisions()
        decision = decisions.get(identity_id)
        if decision and decision.get("action") == "rejected":
            return None, None, None

        estimates = _load_birth_year_estimates()
        est = estimates.get(identity_id)
        if est:
            return est["birth_year_estimate"], "ml_inferred", est.get("birth_year_confidence")

    return None, None, None


def _load_ml_review_decisions() -> dict:
    """Load ML birth year review decisions (accept/reject).

    Returns dict mapping identity_id -> decision record.
    """
    global _ml_review_decisions_cache
    if _ml_review_decisions_cache is not None:
        return _ml_review_decisions_cache

    decisions_path = data_path / "ml_review_decisions.json"
    _ml_review_decisions_cache = {}
    if decisions_path.exists():
        try:
            with open(decisions_path) as f:
                data = json.load(f)
            _ml_review_decisions_cache = data.get("decisions", {})
        except Exception as e:
            logging.warning(f"Failed to load ML review decisions: {e}")

    return _ml_review_decisions_cache


def _save_ml_review_decisions(decisions: dict):
    """Save ML review decisions with atomic write."""
    global _ml_review_decisions_cache
    decisions_path = data_path / "ml_review_decisions.json"
    payload = {
        "schema_version": 1,
        "decisions": decisions,
    }
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, str(decisions_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    _ml_review_decisions_cache = decisions


def _save_ground_truth_birth_year(
    identity_id: str,
    identity: dict,
    birth_year: int,
    source: str,
    source_detail: str = "",
    original_ml_estimate: int = None,
    confirmed_by: str = "admin",
):
    """Write confirmed birth year to ground truth file for ML feedback loop.

    Each confirmed identity x photo appearance = one labeled training sample.
    This is the bridge between the app and the ML pipeline (AD-099).
    """
    gt_path = data_path / "ground_truth_birth_years.json"

    # Load existing
    gt_data = {"schema_version": 1, "entries": {}}
    if gt_path.exists():
        try:
            with open(gt_path) as f:
                gt_data = json.load(f)
        except Exception:
            pass

    # Build face appearances from photo data
    photo_reg = load_photo_registry()
    face_ids = [
        f if isinstance(f, str) else f.get("face_id", "")
        for f in identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    ]
    photo_ids = photo_reg.get_photos_for_faces(face_ids)

    face_appearances = []
    labels = _load_date_labels()
    for pid in photo_ids:
        pm = get_photo_metadata(pid)
        if not pm:
            continue
        label = labels.get(pid, {})
        photo_year = label.get("best_year_estimate") or pm.get("date_taken", "")[:4]
        if photo_year:
            try:
                py = int(str(photo_year)[:4])
                face_appearances.append(
                    {
                        "photo_id": pid,
                        "photo_filename": pm.get("filename", ""),
                        "photo_year": py,
                        "true_age": py - birth_year,
                    }
                )
            except (ValueError, TypeError):
                pass

    gt_data["entries"][identity_id] = {
        "name": ensure_utf8_display(identity.get("name", "")),
        "birth_year": birth_year,
        "source": source,
        "source_detail": source_detail,
        "original_ml_estimate": original_ml_estimate,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_by": confirmed_by,
        "face_appearances": face_appearances,
    }

    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(gt_data, f, indent=2)
        os.replace(tmp_path, str(gt_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _get_pending_ml_birth_year_suggestions() -> list:
    """Get all ML birth year estimates that haven't been reviewed yet.

    Returns list of dicts with identity_id, name, estimate info.
    Excludes identities that already have confirmed birth years or review decisions.
    """
    estimates = _load_birth_year_estimates()
    decisions = _load_ml_review_decisions()
    registry = load_registry()

    pending = []
    for iid, est in estimates.items():
        # Skip if already reviewed
        if iid in decisions:
            continue
        # Skip if identity already has confirmed birth year
        try:
            identity = registry.get_identity(iid)
        except KeyError:
            continue
        if identity.get("merged_into"):
            continue
        for by in [identity.get("birth_year"), (identity.get("metadata") or {}).get("birth_year")]:
            if by:
                break
        else:
            by = None
        if by:
            continue
        pending.append(
            {
                "identity_id": iid,
                "name": ensure_utf8_display(identity.get("name", "")),
                "state": identity.get("state", ""),
                "birth_year_estimate": est["birth_year_estimate"],
                "birth_year_confidence": est.get("birth_year_confidence", "low"),
                "birth_year_range": est.get("birth_year_range", []),
                "birth_year_std": est.get("birth_year_std"),
                "n_appearances": est.get("n_appearances", 0),
                "n_with_age_data": est.get("n_with_age_data", 0),
                "evidence": est.get("evidence", []),
            }
        )

    # Sort by confidence (high first), then by evidence count
    conf_order = {"high": 0, "medium": 1, "low": 2}
    pending.sort(key=lambda x: (conf_order.get(x["birth_year_confidence"], 3), -x["n_with_age_data"]))
    return pending


def _count_pending_birth_year_reviews() -> int:
    """Count pending ML birth year reviews (for OOB counter updates)."""
    estimates = _load_birth_year_estimates()
    decisions = _load_ml_review_decisions()
    registry = load_registry()
    count = 0
    for iid, est in estimates.items():
        if iid in decisions:
            continue
        try:
            identity = registry.get_identity(iid)
        except KeyError:
            continue
        if identity.get("merged_into"):
            continue
        for by in [identity.get("birth_year"), (identity.get("metadata") or {}).get("birth_year")]:
            if by:
                break
        else:
            by = None
        if by:
            continue
        count += 1
    return count


def _get_decade_counts() -> dict:
    """Compute photo counts per decade from the search index."""
    docs = _load_search_index()
    labels = _load_date_labels()
    counts = {}
    for doc in docs:
        decade = None
        for photo_id in (doc.get("cache_photo_id"), doc.get("photo_id")):
            if photo_id:
                decade = labels.get(photo_id, {}).get("estimated_decade")
                if decade:
                    break
        if not decade:
            decade = doc.get("estimated_decade")
        if decade:
            counts[decade] = counts.get(decade, 0) + 1
    return dict(sorted(counts.items()))


def _get_tag_counts() -> dict:
    """Compute photo counts per controlled tag from the search index."""
    docs = _load_search_index()
    counts = {}
    for doc in docs:
        for tag in doc.get("controlled_tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


_context_events_cache = None


def _load_context_events() -> list:
    """Load Rhodes historical context events from JSON file.

    Returns list of event dicts with year, title, description, category, source.
    Cached after first load.
    """
    global _context_events_cache
    if _context_events_cache is not None:
        return _context_events_cache

    context_path = data_path / "rhodes_context_events.json"
    try:
        if context_path.exists():
            with open(context_path) as f:
                data = json.load(f)
            _context_events_cache = data.get("events", [])
        else:
            _context_events_cache = []
    except Exception as e:
        logging.warning(f"Failed to load context events: {e}")
        _context_events_cache = []

    return _context_events_cache


_place_options_cache = None


def _get_place_options() -> list:
    """Load place names from location_dictionary.json for autocomplete.

    Returns list of (value, label) tuples. Includes historical name aliases.
    Cached after first load.
    """
    global _place_options_cache
    if _place_options_cache is not None:
        return _place_options_cache

    loc_path = data_path / "location_dictionary.json"
    options = []
    # Historical name mappings (alias → modern name)
    historical_aliases = {
        "Salonika": "Thessaloniki, Greece",
        "Salonica": "Thessaloniki, Greece",
        "Smyrna": "İzmir, Turkey",
        "Constantinople": "Istanbul, Turkey",
        "La Judería": "Rhodes, Greece",
        "Rodos": "Rhodes, Greece",
        "Rodas": "Rhodes, Greece",
        "Salisbury": "Harare, Zimbabwe",
        "Usumbura": "Bujumbura, Burundi",
        "Elisabethville": "Lubumbashi, Congo",
    }
    try:
        if loc_path.exists():
            with open(loc_path) as f:
                data = json.load(f)
            for loc in data.get("locations", {}).values():
                name = loc.get("name", "")
                if name:
                    options.append((name, name))
    except Exception:
        pass

    # Add historical aliases as separate options pointing to modern names
    for alias, modern in historical_aliases.items():
        options.append((modern, f"{modern} ({alias})"))

    # Deduplicate by value
    seen = set()
    deduped = []
    for val, label in options:
        if val not in seen:
            seen.add(val)
            deduped.append((val, label))
        elif label != val:  # Add alias labels even if value exists
            deduped.append((val, label))

    _place_options_cache = sorted(deduped, key=lambda x: x[0])
    return _place_options_cache


def _place_datalist() -> tuple:
    """Return a Datalist element with place options for autocomplete."""
    options = _get_place_options()
    return Datalist(
        *[Option(value=val, label=label) for val, label in options],
        id="places-list",
    )


def _photo_collection_datalist():
    """Return a Datalist with known collection names for inline photo editing."""
    collections = set()
    if _photo_cache:
        for pdata in _photo_cache.values():
            c = pdata.get("collection", "")
            if c:
                collections.add(c)
    return Datalist(
        *[Option(value=c) for c in sorted(collections)],
        id="photo-collections",
    )


def _search_photos(query: str = "", decade: int = None, tag: str = None) -> list:
    """Search photos using in-memory index. Returns matching documents with match reason."""
    docs = _load_search_index()
    labels = _load_date_labels()
    results = []
    query_lower = query.lower().strip() if query else ""

    for doc in docs:
        effective_decade = None
        for photo_id in (doc.get("cache_photo_id"), doc.get("photo_id")):
            if photo_id:
                effective_decade = labels.get(photo_id, {}).get("estimated_decade")
                if effective_decade:
                    break
        if not effective_decade:
            effective_decade = doc.get("estimated_decade")

        # Apply decade filter
        if decade and effective_decade != decade:
            continue

        # Apply tag filter
        if tag and tag not in doc.get("controlled_tags", []):
            continue

        # Apply text search
        match_reason = None
        if query_lower:
            searchable = doc.get("searchable_text", "").lower()
            if query_lower in searchable:
                # Determine match reason
                tags_lower = " ".join(doc.get("controlled_tags", [])).lower()
                if query_lower in tags_lower:
                    match_reason = "tags"
                else:
                    match_reason = "scene"
            else:
                # Check filename match from photo cache (FB-007)
                filename_matched = False
                for pid in (doc.get("cache_photo_id"), doc.get("photo_id")):
                    if pid and _photo_cache and pid in _photo_cache:
                        fname = _photo_cache[pid].get("filename", "")
                        if fname and query_lower in fname.lower():
                            match_reason = "filename"
                            filename_matched = True
                            break
                if not filename_matched:
                    continue
        elif not decade and not tag:
            pass  # No filters, include all

        results.append({**doc, "estimated_decade": effective_decade, "match_reason": match_reason})

    return results


def _get_date_badge(photo_id: str) -> tuple:
    """Get date badge text, confidence, and tooltip for a photo.

    Returns (badge_text, confidence, tooltip) or (None, None, None) if no label.
    """
    labels = _load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return None, None, None

    decade = label.get("estimated_decade")
    if not decade:
        return None, None, None

    badge_text = f"c. {decade}s"
    confidence = label.get("confidence", "medium")
    best_year = label.get("best_year_estimate", "")
    prob_range = label.get("probable_range", [])
    range_str = f"{prob_range[0]}\u2013{prob_range[1]}" if len(prob_range) == 2 else ""
    tooltip = f"Best estimate: {best_year} (range: {range_str})" if best_year and range_str else f"Estimated: {decade}s"

    return badge_text, confidence, tooltip


def _build_photo_date_badge(photo_id: str):
    """Build prominent date estimate badge for photo detail page.

    Returns a Section with the estimate badge, or None if no estimate.
    PRD-022: Show 'c. 1935 ± 5 years' prominently on photo pages.
    """
    date_text, confidence, tooltip = _get_date_badge(photo_id)
    if not date_text:
        return None

    # Load full label for range info
    labels = _load_date_labels()
    label = labels.get(photo_id, {})
    prob_range = label.get("probable_range", [])
    best_year = label.get("best_year_estimate")
    range_str = ""
    if best_year and len(prob_range) == 2:
        margin = max(abs(prob_range[1] - best_year), abs(best_year - prob_range[0]))
        range_str = f" \u00b1 {margin} years"

    conf_cls = {
        "high": "border-emerald-500/40 bg-emerald-950/20",
        "medium": "border-amber-500/40 bg-amber-950/20",
        "low": "border-slate-500/40 bg-slate-800/40",
    }.get(confidence, "border-slate-500/40 bg-slate-800/40")

    refinement_badge = _progressive_refinement_badge(label)

    return Section(
        Div(
            Div(
                Span(date_text + range_str, cls="text-xl font-serif text-amber-200", data_testid="photo-date-badge"),
                Span(f"{confidence} confidence", cls="text-[11px] text-slate-400 ml-3"),
                refinement_badge,
                cls="flex items-center gap-2 flex-wrap",
            ),
            cls=f"max-w-[900px] mx-auto border-l-2 {conf_cls} rounded-lg px-4 py-3",
        ),
        cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
        data_testid="photo-date-badge-section",
    )


def _build_ai_analysis_section(photo_id: str, is_admin: bool = False):
    """Build the AI Analysis metadata panel for a photo detail page.

    Shows date estimate, scene description, tags, visible text, evidence, subject ages.
    Each subsection has provenance styling (AI = indigo, human = emerald).
    Returns None if no AI data available for this photo.
    """

    def _build_reanalyze_controls(label: dict | None = None, button_label: str = "Re-analyze Photo"):
        if not is_admin:
            return None

        last_analyzed_el = None
        if label:
            analysis_ts = label.get("reanalyzed_at") or label.get("analyzed_at") or label.get("timestamp")
            analysis_label = _format_display_date(analysis_ts, include_time=True)
            if analysis_label:
                last_analyzed_el = Span(
                    f"Last analyzed: {analysis_label}",
                    cls="text-[10px] text-slate-500 mr-2",
                    data_testid="last-analyzed",
                )

        safe_id = photo_id.replace(".", "_")
        return Div(
            last_analyzed_el,
            Button(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'
                ),
                button_label,
                hx_post=f"/api/photo/{photo_id}/reanalyze",
                hx_target=f"#reanalyze-result-{safe_id}",
                hx_swap="innerHTML",
                hx_indicator=f"#reanalyze-spinner-{safe_id}",
                cls="flex items-center text-[11px] text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 hover:border-indigo-400/50 rounded px-2 py-1 transition-colors cursor-pointer",
                data_testid="reanalyze-button",
                title="Date, location, and scene analysis",
            ),
            Span(
                cls="htmx-indicator animate-spin inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full ml-2",
                id=f"reanalyze-spinner-{safe_id}",
            ),
            cls="flex items-center",
        )

    labels = _load_date_labels()
    label = labels.get(photo_id)
    if not label:
        if is_admin:
            return Section(
                Div(
                    Div(
                        Div(
                            Span("\u2728", cls="text-lg mr-2"),
                            H2("AI Analysis", cls="text-lg font-serif font-semibold text-white inline"),
                            cls="flex items-center",
                        ),
                        _build_reanalyze_controls(button_label="Run AI Analysis"),
                        cls="flex items-center justify-between mb-1",
                    ),
                    P("No Gemini analysis has been run on this photo yet.", cls="text-[11px] text-indigo-400/70 mb-2"),
                    P(
                        "Run the first analysis to generate date, location, scene, and evidence fields.",
                        cls="text-sm text-slate-400 mb-4",
                        data_testid="ai-analysis-empty",
                    ),
                    Div(id=f"reanalyze-result-{photo_id.replace('.', '_')}", cls="mb-3"),
                    cls="max-w-[900px] mx-auto",
                    data_testid="ai-analysis",
                ),
                cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
            )
        return None

    # Build search index entry for tags/scene (check both photo_id and cache_photo_id)
    docs = _load_search_index()
    search_doc = next((d for d in docs if d.get("photo_id") == photo_id or d.get("cache_photo_id") == photo_id), None)

    # Track which specific fields have been human-corrected
    _date_is_human = label.get("source") == "human"

    def _field(title, content, field_key="ai", expanded=False):
        """Render a collapsible subsection with provenance styling.

        field_key: 'ai' (default), 'human' (force verified), or 'date' (uses date-specific source).
        """
        is_human = field_key == "human" or (field_key == "date" and _date_is_human)
        border_cls = "border-emerald-500/40 bg-emerald-950/20" if is_human else "border-indigo-500/40 bg-indigo-950/20"
        icon = "\u2713" if is_human else "\u2728"
        provenance_text = "Verified" if is_human else "AI Estimated"
        provenance_cls = "text-emerald-400" if is_human else "text-indigo-400"

        return Details(
            Summary(
                Div(
                    Span(icon, cls="mr-1.5"),
                    Span(title, cls="text-sm font-medium text-white"),
                    Span(f" \u2014 {provenance_text}", cls=f"text-[10px] {provenance_cls} ml-2"),
                    cls="flex items-center",
                ),
                cls="cursor-pointer list-none select-none py-2 px-3 hover:bg-slate-800/50 rounded-lg transition-colors",
            ),
            Div(content, cls="px-3 pb-3 text-sm text-slate-300 leading-relaxed"),
            cls=f"border-l-2 {border_cls} rounded-lg mb-2",
            open=expanded,
            data_provenance="human" if is_human else "ai",
            data_testid="verified-field" if is_human else None,
        )

    sections = []

    # Date estimate
    decade = label.get("estimated_decade")
    best_year = label.get("best_year_estimate")
    confidence = label.get("confidence", "medium")
    prob_range = label.get("probable_range", [])
    if decade:
        range_str = f"{prob_range[0]}\u2013{prob_range[1]}" if len(prob_range) == 2 else ""
        conf_badge_cls = {
            "high": "bg-emerald-500/20 text-emerald-400",
            "medium": "bg-amber-500/20 text-amber-400",
            "low": "bg-red-500/20 text-red-400",
        }.get(confidence, "bg-slate-500/20 text-slate-400")
        # Correction pencil button (visible to all, triggers form or login prompt)
        pencil_btn = Button(
            "\u270f\ufe0f",
            cls="text-xs text-slate-500 hover:text-white transition-colors ml-2 px-1",
            data_testid="correct-date",
            data_action="toggle-date-correction",
            data_photo_id=photo_id,
            title="Correct this date",
            type="button",
        )
        # Inline correction form (hidden by default, shown on pencil click)
        correction_form = Div(
            Form(
                Div(
                    Label("Actual year:", fr="correction-year-input", cls="text-[11px] text-slate-400 mr-2"),
                    Input(
                        type="number",
                        name="correction_year",
                        id="correction-year-input",
                        min="1850",
                        max="2030",
                        placeholder=str(best_year or decade),
                        cls="w-20 bg-slate-800 border border-slate-600 rounded px-2 py-1 text-sm text-white",
                        data_testid="correction-year",
                    ),
                    Button(
                        "Submit",
                        cls="ml-2 px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors",
                        data_testid="correction-submit",
                        type="submit",
                    ),
                    Button(
                        "Cancel",
                        cls="ml-1 px-2 py-1 text-xs text-slate-400 hover:text-white transition-colors",
                        type="button",
                        data_action="toggle-date-correction",
                    ),
                    cls="flex items-center mt-2",
                ),
                method="post",
                action=f"/api/photo/{photo_id}/correct-date",
                hx_post=f"/api/photo/{photo_id}/correct-date",
                hx_target=f"#date-section-{photo_id[:8]}",
                hx_swap="outerHTML",
            ),
            id=f"date-correction-form-{photo_id[:8]}",
            cls="hidden",
        )
        # Decade probability distribution bars (from Gemini decade_probabilities)
        decade_probs = label.get("decade_probabilities", {})
        prob_bars_el = None
        if decade_probs and isinstance(decade_probs, dict):
            bars = []
            for dec_str in sorted(decade_probs.keys()):
                try:
                    dec_val = int(dec_str)
                    prob_val = float(decade_probs[dec_str])
                except (ValueError, TypeError):
                    continue
                pct = prob_val * 100
                bar_width = max(1, pct)
                is_predicted = dec_val == decade
                bar_color = "bg-amber-400" if is_predicted else "bg-slate-600"
                text_cls = "text-amber-400 font-semibold" if is_predicted else "text-slate-500"
                bars.append(
                    Div(
                        Span(f"{dec_val}s", cls=f"text-[10px] {text_cls} w-10 text-right mr-2 shrink-0"),
                        Div(
                            Div(cls=f"{bar_color} h-full rounded-r", style=f"width:{bar_width}%"),
                            cls="flex-1 bg-slate-800 rounded h-2.5",
                        ),
                        Span(f"{pct:.0f}%", cls=f"text-[10px] {text_cls} w-8 ml-2 shrink-0"),
                        cls="flex items-center",
                    )
                )
            if bars:
                prob_bars_el = Div(
                    *bars,
                    cls="flex flex-col gap-0.5 mt-3",
                    data_testid="decade-probability-bars",
                )

        date_content = Div(
            Div(
                P(
                    f"circa {best_year}" if best_year else f"{decade}s",
                    cls="text-lg font-serif text-amber-200 mb-1 inline",
                ),
                pencil_btn,
                cls="flex items-center",
            ),
            Div(
                Span(f"Confidence: {confidence}", cls=f"text-[11px] px-2 py-0.5 rounded-full {conf_badge_cls}"),
                Span(f"Range: {range_str}", cls="text-[11px] text-slate-500 ml-2") if range_str else None,
                _progressive_refinement_badge(label),
                cls="flex items-center gap-2 flex-wrap",
            ),
            prob_bars_el,
            correction_form,
            id=f"date-section-{photo_id[:8]}",
        )
        sections.append(_field("Date Estimate", date_content, field_key="date", expanded=True))

    # Location estimate (from Gemini + geocoded data)
    location_estimate = label.get("location_estimate", "")
    locations = _load_photo_locations()
    location_data = locations.get(photo_id, {})
    location_name = location_data.get("location_name", "")
    location_region = location_data.get("region", "")
    location_confidence = location_data.get("confidence", "")
    has_location = bool(location_estimate or location_name)

    if has_location:
        location_parts = []
        # Location label
        if location_name:
            loc_label = location_name
            if location_region:
                loc_label += f", {location_region}"
            location_parts.append(P(loc_label, cls="text-lg font-serif text-amber-200 mb-1"))
        # Confidence badge
        if location_confidence:
            loc_conf_cls = {
                "high": "bg-emerald-500/20 text-emerald-400",
                "medium": "bg-amber-500/20 text-amber-400",
                "low": "bg-red-500/20 text-red-400",
            }.get(location_confidence, "bg-slate-500/20 text-slate-400")
            location_parts.append(
                Span(f"Confidence: {location_confidence}", cls=f"text-[11px] px-2 py-0.5 rounded-full {loc_conf_cls}")
            )
        # Evidence text (Gemini's reasoning)
        if location_estimate:
            location_parts.append(
                P(location_estimate, cls="text-slate-400 text-xs mt-2 italic", data_testid="location-evidence")
            )
        # Admin: Correct Location button (simple text input)
        if is_admin:
            location_parts.append(
                Div(
                    Form(
                        Div(
                            Label(
                                "Correct location:",
                                fr="correction-location-input",
                                cls="text-[11px] text-slate-400 mr-2",
                            ),
                            Input(
                                type="text",
                                name="correction_location",
                                id="correction-location-input",
                                placeholder=location_name or "City, Country",
                                cls="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-sm text-white w-48",
                                data_testid="correction-location",
                            ),
                            Button(
                                "Submit",
                                cls="ml-2 px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors",
                                type="button",
                                disabled=True,
                                title="Location correction coming soon",
                            ),
                            cls="flex items-center mt-2",
                        ),
                    ),
                    cls="mt-2",
                    data_testid="location-correction-form",
                )
            )

        # Embedded Leaflet map if geocoded data exists
        if location_data.get("lat") and location_data.get("lng"):
            map_id = f"location-map-{photo_id[:8]}"
            draggable = "true" if is_admin else "false"
            # Data attributes drive init; Leaflet loaded via onload callback
            location_parts.append(
                Div(
                    Div(
                        id=map_id,
                        style="height: 300px; border-radius: 8px; margin-top: 12px;",
                        data_testid="location-map",
                        data_lat=str(location_data["lat"]),
                        data_lng=str(location_data["lng"]),
                        data_label=location_name,
                        data_draggable=draggable,
                    ),
                    Link(rel="stylesheet", href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
                )
            )

        location_content = Div(
            *location_parts,
            id=f"location-section-{photo_id[:8]}",
            data_testid="location-estimate",
        )
        sections.append(_field("Location Estimate", location_content, expanded=True))

    # Scene description
    scene = label.get("scene_description", "")
    if not scene and search_doc:
        # Fall back to searchable text (first sentence)
        st = search_doc.get("searchable_text", "")
        scene = st.split(".")[0] + "." if "." in st else st[:200]
    if scene:
        sections.append(_field("Scene", P(scene), expanded=True))

    # Visible text (OCR)
    visible_text = label.get("visible_text", "")
    if visible_text:
        sections.append(_field("Visible Text", P(visible_text, cls="italic font-mono text-xs text-slate-400")))

    # Tags
    tags = label.get("controlled_tags") or (search_doc.get("controlled_tags") if search_doc else None)
    if tags:
        tag_pills = [
            A(
                t.replace("_", " "),
                href=f"/photos?tag={quote(t)}",
                cls="px-2 py-0.5 text-[11px] bg-slate-700/60 text-slate-300 rounded-full hover:bg-indigo-600/40 hover:text-white transition-colors",
                data_testid="ai-tag",
            )
            for t in tags
        ]
        sections.append(_field("Tags", Div(*tag_pills, cls="flex flex-wrap gap-1.5")))

    # Dating evidence — Photo Detective card layout
    detective_section = _detective_evidence_section(label)
    if detective_section:
        sections.append(_field("Photo Detective Evidence", detective_section, expanded=True))
    else:
        # Fallback: simple list for labels without structured evidence
        evidence = label.get("evidence", {})
        if evidence:
            evidence_items = []
            for category, cues in evidence.items():
                if not isinstance(cues, list):
                    continue
                for cue in cues[:3]:  # Max 3 per category
                    cue_text = cue.get("cue", "") if isinstance(cue, dict) else str(cue)
                    strength = cue.get("strength", "") if isinstance(cue, dict) else ""
                    if cue_text:
                        strength_cls = {
                            "strong": "text-emerald-400",
                            "moderate": "text-amber-400",
                            "weak": "text-slate-500",
                        }.get(strength, "text-slate-500")
                        evidence_items.append(
                            Li(
                                Span(cue_text, cls="text-slate-400"),
                                Span(f" ({strength})", cls=f"text-[10px] {strength_cls}") if strength else None,
                                cls="text-xs mb-1",
                            )
                        )
            if evidence_items:
                sections.append(_field("Dating Evidence", Ul(*evidence_items, cls="list-disc list-inside space-y-0.5")))

    # Subject ages
    ages = label.get("subject_ages")
    if ages:
        if isinstance(ages, list):
            ages_text = ", ".join(str(a) for a in ages)
        elif isinstance(ages, str):
            ages_text = ages
        else:
            ages_text = str(ages)
        if ages_text:
            sections.append(_field("Subject Ages", P(ages_text)))

    if not sections:
        return None

    reanalyze_btn = _build_reanalyze_controls(label)

    return Section(
        Div(
            Div(
                Div(
                    Span("\u2728", cls="text-lg mr-2"),
                    H2("AI Analysis", cls="text-lg font-serif font-semibold text-white inline"),
                    cls="flex items-center",
                ),
                reanalyze_btn,
                cls="flex items-center justify-between mb-1",
            ),
            P("Estimated by AI \u2014 help us verify", cls="text-[11px] text-indigo-400/70 mb-4"),
            Div(id=f"reanalyze-result-{photo_id.replace('.', '_')}", cls="mb-3"),
            Div(
                *sections,
                id=f"ai-analysis-sections-{photo_id}",
                hx_get=f"/api/photo/{photo_id}/ai-sections",
                hx_trigger="refreshAnalysis from:body",
                hx_swap="innerHTML",
            ),
            cls="max-w-[900px] mx-auto",
            data_testid="ai-analysis",
        ),
        cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
    )


def _build_ai_sections_list(photo_id: str, label: dict, is_admin: bool = False):
    """Build just the collapsible sections for AI Analysis (no wrapper).

    This is the inner content of the ai-analysis-sections-{photo_id} div,
    used both for initial render and for OOB refresh after re-analyze.
    """
    docs = _load_search_index()
    search_doc = next((d for d in docs if d.get("photo_id") == photo_id or d.get("cache_photo_id") == photo_id), None)
    _date_is_human = label.get("source") == "human"

    def _field(title, content, field_key="ai", expanded=False):
        is_human = field_key == "human" or (field_key == "date" and _date_is_human)
        border_cls = "border-emerald-500/40 bg-emerald-950/20" if is_human else "border-indigo-500/40 bg-indigo-950/20"
        icon = "\u2713" if is_human else "\u2728"
        provenance_text = "Verified" if is_human else "AI Estimated"
        provenance_cls = "text-emerald-400" if is_human else "text-indigo-400"
        return Details(
            Summary(
                Div(
                    Span(icon, cls="mr-1.5"),
                    Span(title, cls="text-sm font-medium text-white"),
                    Span(f" \u2014 {provenance_text}", cls=f"text-[10px] {provenance_cls} ml-2"),
                    cls="flex items-center",
                ),
                cls="cursor-pointer list-none select-none py-2 px-3 hover:bg-slate-800/50 rounded-lg transition-colors",
            ),
            Div(content, cls="px-3 pb-3 text-sm text-slate-300 leading-relaxed"),
            cls=f"border-l-2 {border_cls} rounded-lg mb-2",
            open=expanded,
            data_provenance="human" if is_human else "ai",
            data_testid="verified-field" if is_human else None,
        )

    sections = []

    # Date estimate
    decade = label.get("estimated_decade")
    best_year = label.get("best_year_estimate")
    confidence = label.get("confidence", "medium")
    if decade:
        conf_badge_cls = {
            "high": "bg-emerald-500/20 text-emerald-400",
            "medium": "bg-amber-500/20 text-amber-400",
            "low": "bg-red-500/20 text-red-400",
        }.get(confidence, "bg-slate-500/20 text-slate-400")
        date_text = f"circa {best_year}" if best_year else f"{decade}s"
        date_content = Div(
            P(date_text, cls="text-lg font-serif text-amber-200 mb-1"),
            Span(confidence.capitalize(), cls=f"text-[10px] px-2 py-0.5 rounded-full {conf_badge_cls}"),
        )
        sections.append(_field("Date Estimate", date_content, field_key="date", expanded=True))

    # Location
    locations = _load_photo_locations()
    location_data = locations.get(photo_id, {})
    location_name = location_data.get("location_name", "")
    if location_name:
        location_parts = [P(location_name, cls="text-white font-medium")]
        location_estimate = location_data.get("location_estimate", "")
        if location_estimate:
            location_parts.append(P(location_estimate, cls="text-slate-400 text-xs mt-2 italic"))
        location_content = Div(*location_parts, data_testid="location-estimate")
        sections.append(_field("Location Estimate", location_content, expanded=True))

    # Scene description
    scene = label.get("scene_description", "")
    if not scene and search_doc:
        st = search_doc.get("searchable_text", "")
        scene = st.split(".")[0] + "." if "." in st else st[:200]
    if scene:
        sections.append(_field("Scene", P(scene), expanded=True))

    # Photo Detective Evidence
    detective_section = _detective_evidence_section(label)
    if detective_section:
        sections.append(_field("Photo Detective Evidence", detective_section, expanded=True))

    if not sections:
        return Div()
    return Div(*sections)


def _build_face_alignment_section(photo_id: str, is_admin: bool = False):
    """Build the face alignment description panel for a photo page.

    Shows per-face Gemini descriptions (from PRD-015 coordinate bridging).
    Returns None if no alignment data exists for this photo.
    Admin users see a "Detect Faces" trigger button if not yet aligned.
    """
    from app.face_alignment import get_cached_alignment, load_alignments

    # Check for existing alignment data (Supabase-first, AD-152)
    alignment = get_cached_alignment(photo_id)
    if alignment is None:
        alignments = load_alignments(data_path)
        alignment = alignments.get(photo_id)

    # Admin trigger button if no alignment exists
    if alignment is None:
        if not is_admin:
            return None
        return Div(
            H3("Face Analysis", cls="text-lg font-serif font-bold text-white mb-2"),
            P("No face descriptions available yet.", cls="text-slate-400 text-sm mb-2"),
            Div(
                Button(
                    "Detect Faces",
                    cls="text-sm px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white "
                    "rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                    hx_post=f"/api/face-alignment/{photo_id}",
                    hx_target=f"#face-alignment-{photo_id[:8]}",
                    hx_swap="innerHTML",
                    hx_indicator=f"#face-alignment-spinner-{photo_id[:8]}",
                    hx_disabled_elt="this",
                    type="button",
                ),
                Span(
                    Span(
                        cls="inline-block w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mr-2"
                    ),
                    "Analyzing faces...",
                    cls="htmx-indicator ml-3 text-sm text-indigo-300",
                    id=f"face-alignment-spinner-{photo_id[:8]}",
                ),
                cls="flex items-center",
            ),
            id=f"face-alignment-{photo_id[:8]}",
            cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
            data_testid="face-alignment-trigger",
        )

    # Render alignment results
    # Handle both AlignmentResult objects and raw dicts
    if isinstance(alignment, dict):
        aligned_faces = alignment.get("aligned_faces", [])
        faces_detected = alignment.get("faces_detected", 0)
        faces_described = alignment.get("faces_described", 0)
        gemini_only = alignment.get("gemini_only_faces", [])
        scene_context = alignment.get("scene_context", "")
        model_used = alignment.get("model_used", "")
        analyzed_at = alignment.get("analyzed_at", "")
    else:
        aligned_faces = [
            f
            if isinstance(f, dict)
            else {
                "face_id": f.face_id,
                "estimated_age": f.estimated_age,
                "gender": f.gender,
                "gemini_description": f.gemini_description,
                "clothing": f.clothing,
                "position_in_photo": f.position_in_photo,
                "identifying_features": f.identifying_features,
                "identity_name": f.identity_name,
                "is_subject": f.is_subject,
            }
            for f in alignment.aligned_faces
        ]
        faces_detected = alignment.faces_detected
        faces_described = alignment.faces_described
        gemini_only = alignment.gemini_only_faces
        scene_context = alignment.scene_context
        model_used = alignment.model_used
        analyzed_at = getattr(alignment, "analyzed_at", "")

    # Format model + timestamp line
    model_line = f"Gemini coordinate bridging ({model_used})" if model_used else "Gemini coordinate bridging"
    if analyzed_at:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(analyzed_at)
            model_line += f" on {dt.strftime('%b %-d, %Y')}"
        except (ValueError, TypeError):
            pass

    # Look up identities for face labels
    registry = load_registry()

    face_cards = []
    for i, face in enumerate(aligned_faces):
        is_subject = face.get("is_subject", True)
        if not is_subject:
            continue  # Skip non-subject faces in the display

        name = face.get("identity_name") or "Unidentified"
        age = face.get("estimated_age")
        gender = face.get("gender", "")
        clothing = face.get("clothing", "")
        description = face.get("gemini_description", "")
        position = face.get("position_in_photo", "")
        features = face.get("identifying_features", "")

        # Look up actual identity from registry for this face
        face_id = face.get("face_id", "")
        matched_identity = get_identity_for_face(registry, face_id) if face_id else None
        identity_id = matched_identity.get("identity_id") if matched_identity else None
        registry_name = ensure_utf8_display(matched_identity.get("name", "")) if matched_identity else ""
        is_confirmed = matched_identity and matched_identity.get("state") == "CONFIRMED"
        has_real_name = is_confirmed and registry_name and not registry_name.startswith("Unidentified")

        # Use registry name if available and confirmed, otherwise use Gemini name
        display_name = registry_name if has_real_name else name

        card_content = []
        # Header: face index + identity name (clickable link if identified)
        if has_real_name and identity_id:
            header_el = Div(
                A(
                    display_name,
                    href=f"/person/{identity_id}",
                    cls="text-emerald-400 hover:text-emerald-300 font-medium text-sm underline transition-colors",
                    data_testid="face-identity-link",
                ),
                cls="mb-1",
            )
        else:
            header_text = f"Face {i}"
            if display_name != "Unidentified":
                header_text += f": {display_name}"
            header_el = P(header_text, cls="text-white font-medium text-sm mb-1")
        card_content.append(header_el)

        # Demographics line
        demo_parts = []
        if age:
            demo_parts.append(f"Age: ~{age}")
        if gender:
            demo_parts.append(gender.capitalize())
        if demo_parts:
            card_content.append(P(" | ".join(demo_parts), cls="text-indigo-300 text-xs mb-1"))

        # Description
        if description:
            card_content.append(P(description, cls="text-slate-300 text-xs mb-1"))

        # Clothing
        if clothing:
            card_content.append(P(f"Attire: {clothing}", cls="text-slate-400 text-xs mb-1"))

        # Position + Features
        if position:
            card_content.append(P(f"Position: {position}", cls="text-slate-500 text-xs"))
        if features:
            card_content.append(P(f"Features: {features}", cls="text-slate-500 text-xs italic"))

        face_cards.append(
            Div(
                *card_content,
                cls="border border-indigo-500/30 bg-indigo-950/20 rounded-lg p-3",
            )
        )

    # Mismatch warning
    mismatch_warning = None
    if faces_detected != faces_described:
        mismatch_warning = Div(
            P(
                f"InsightFace detected {faces_detected} faces, Gemini described {faces_described}.",
                cls="text-amber-300 text-xs",
            ),
            P(
                f"{len(gemini_only)} additional face(s) seen by Gemini only." if gemini_only else "",
                cls="text-amber-400/70 text-xs",
            )
            if gemini_only
            else None,
            cls="bg-amber-900/20 border border-amber-500/30 rounded px-3 py-2 mb-3",
            data_testid="face-alignment-mismatch",
        )

    # Scene context
    scene_el = None
    if scene_context:
        scene_el = P(f"Scene: {scene_context}", cls="text-slate-400 text-xs italic mb-3")

    return Div(
        H3("Face Analysis", cls="text-lg font-serif font-bold text-white mb-2"),
        P(model_line, cls="text-indigo-400/70 text-[11px] mb-3"),
        mismatch_warning,
        scene_el,
        Div(*face_cards, cls="grid gap-2 sm:grid-cols-2")
        if face_cards
        else P("No subject faces described.", cls="text-slate-500 text-sm"),
        # Re-run button for admin
        Button(
            "Re-run Analysis",
            cls="mt-3 text-xs px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
            hx_post=f"/api/face-alignment/{photo_id}",
            hx_target=f"#face-alignment-{photo_id[:8]}",
            hx_swap="innerHTML",
            type="button",
        )
        if is_admin
        else None,
        id=f"face-alignment-{photo_id[:8]}",
        cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
        data_testid="face-alignment-results",
    )


def _render_date_badge_overlay(photo_id: str) -> Span:
    """Render a date badge overlay for a photo card. Returns None if no label."""
    date_text, date_conf, date_tooltip = _get_date_badge(photo_id)
    if not date_text:
        return None

    if date_conf == "high":
        cls = "bg-amber-800/80 text-amber-100"
    elif date_conf == "medium":
        cls = "bg-amber-800/50 border border-amber-600/50 text-amber-200/90"
    else:
        cls = "border border-dashed border-amber-600/40 text-amber-400/60"

    return Span(
        date_text,
        cls=f"absolute bottom-2 right-2 text-[11px] font-serif px-1.5 py-0.5 rounded backdrop-blur-sm {cls}",
        title=date_tooltip,
        data_testid="date-badge",
        data_confidence=date_conf,
    )


def _compute_triage_counts(to_review: list) -> dict:
    """Categorize inbox identities by actionability for the triage bar.

    Returns:
        {
            "ready_to_confirm": int,  # Has Very High or High proposal to confirmed
            "rediscovered": int,      # Promoted from SKIPPED (has promoted_from field)
            "unmatched": int,         # No proposals, no promotion
        }
    """
    ids_with_proposals = _get_identities_with_proposals()
    ready = 0
    rediscovered = 0
    unmatched = 0

    for identity in to_review:
        iid = identity.get("identity_id", "")
        has_promotion = identity.get("promoted_from") is not None

        if iid in ids_with_proposals:
            best = _get_best_proposal_for_identity(iid)
            if best and best.get("confidence") in ("VERY HIGH", "HIGH"):
                ready += 1
                continue

        if has_promotion:
            rediscovered += 1
        elif iid in ids_with_proposals:
            # Has proposals but not high-confidence
            ready += 1
        else:
            unmatched += 1

    return {
        "ready_to_confirm": ready,
        "rediscovered": rediscovered,
        "unmatched": unmatched,
    }


def _triage_category(identity: dict) -> str:
    """Determine triage category for a single identity.

    Returns: "ready", "rediscovered", or "unmatched"
    """
    iid = identity.get("identity_id", "")
    ids_with_proposals = _get_identities_with_proposals()

    if iid in ids_with_proposals:
        return "ready"

    if identity.get("promoted_from") is not None:
        return "rediscovered"

    return "unmatched"


def _build_triage_bar(to_review: list, view_mode: str, active_filter: str = "", nav_prefix: str = "") -> Div:
    """Build the triage summary bar for the inbox."""
    counts = _compute_triage_counts(to_review)

    items = []
    categories = [
        (
            "ready",
            "Ready to Confirm",
            counts["ready_to_confirm"],
            "bg-emerald-900/40 border-emerald-600/40 text-emerald-300 hover:bg-emerald-900/60",
            "ring-2 ring-emerald-400 bg-emerald-800/60 font-bold",
            "ML found a strong match — review and confirm",
        ),
        (
            "rediscovered",
            "Rediscovered",
            counts["rediscovered"],
            "bg-amber-900/40 border-amber-600/40 text-amber-300 hover:bg-amber-900/60",
            "ring-2 ring-amber-400 bg-amber-800/60 font-bold",
            "Previously skipped faces with new match evidence",
        ),
        (
            "unmatched",
            "Unmatched",
            counts["unmatched"],
            "bg-slate-700/40 border-slate-600/40 text-slate-300 hover:bg-slate-700/60",
            "ring-2 ring-slate-400 bg-slate-600/60 font-bold",
            "Faces not yet linked to a known person — help identify them",
        ),
    ]

    for filter_val, label, count, color_cls, active_cls, tooltip in categories:
        if count == 0:
            continue
        is_active = filter_val == active_filter
        pill_cls = f"flex flex-col items-center px-4 py-2 rounded-lg border transition-colors {color_cls}"
        if is_active:
            pill_cls += f" {active_cls}"
        items.append(
            A(
                Span(str(count), cls="text-lg font-bold"),
                Span(label, cls="text-xs" + ("" if is_active else " opacity-80")),
                href=f"{nav_prefix}/?section=to_review&view={view_mode}&filter={filter_val}",
                cls=pill_cls,
                title=tooltip,
            )
        )

    if not items:
        return None

    return Div(
        *items,
        cls="flex gap-3 mb-6 flex-wrap pb-4 border-b border-slate-700/50",
    )


def _promotion_badge(identity: dict):
    """Badge for promoted (rediscovered) identities in browse view."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    if reason == "confirmed_match":
        return Span(
            "Suggested ID",
            cls="text-xs px-2 py-0.5 rounded border bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
            title="Previously skipped — now matches a confirmed identity",
        )
    else:
        return Span(
            "Rediscovered",
            cls="text-xs px-2 py-0.5 rounded border bg-amber-600/30 text-amber-300 border-amber-500/30",
            title="Previously skipped — new match evidence found",
        )


def _promotion_banner(identity: dict):
    """Banner for promoted faces shown above expanded cards in Focus mode."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    context = identity.get("promotion_context", "")

    if reason == "confirmed_match":
        title = "Identity Suggested"
        desc = context or "This previously skipped face now matches a confirmed identity with high confidence."
        icon_cls = "text-emerald-400"
        border_cls = "border-emerald-600/40 bg-emerald-900/20"
    elif reason == "new_face_match":
        title = "New Context Available"
        desc = context or "A newly uploaded photo matches this previously skipped face."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"
    else:  # group_discovery
        title = "Rediscovered"
        desc = context or "This face now groups with another face from a different batch."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"

    return Div(
        Div(
            Span("*", cls=f"text-lg font-bold {icon_cls}"),
            Div(
                Strong(title, cls="text-white text-sm"),
                P(desc, cls="text-slate-400 text-xs mt-0.5"),
                cls="ml-2",
            ),
            cls="flex items-start",
        ),
        cls=f"rounded-lg border p-3 mb-3 {border_cls}",
    )


# _section_for_state imported from app.utils


def _safe_get_identity(registry, identity_id: str) -> dict:
    """Get identity by ID, returning empty dict instead of raising KeyError."""
    try:
        return registry.get_identity(identity_id)
    except (KeyError, TypeError):
        return {}


def _compute_sidebar_counts(registry, community=None) -> dict:
    """Compute sidebar navigation counts from a loaded registry.

    This is the SINGLE canonical source for sidebar counts.
    All pages with a sidebar MUST call this instead of computing counts inline.

    Args:
        registry: Loaded IdentityRegistry
        community: Community dict (None = Rhodes/default, shows all data)
    """
    _build_caches()

    # Get community filter sets (None = all data, set = filtered)
    community_photo_ids = _get_community_photo_ids(community)
    community_identity_ids = _get_community_identity_ids(community)

    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped_list = registry.list_identities(state=IdentityState.SKIPPED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    # Filter by community identity IDs when scoped
    if community_identity_ids is not None:
        inbox = [i for i in inbox if i.get("identity_id") in community_identity_ids]
        proposed = [i for i in proposed if i.get("identity_id") in community_identity_ids]
        confirmed_list = [i for i in confirmed_list if i.get("identity_id") in community_identity_ids]
        skipped_list = [i for i in skipped_list if i.get("identity_id") in community_identity_ids]
        rejected = [i for i in rejected if i.get("identity_id") in community_identity_ids]
        contested = [i for i in contested if i.get("identity_id") in community_identity_ids]

    to_review = inbox + proposed
    dismissed = rejected + contested

    # Photo count: filtered by community when scoped
    # Use intersection with _photo_cache to avoid counting aliases twice (COMMUNITY-007)
    if community_photo_ids is not None:
        if _photo_cache:
            photo_count = len(community_photo_ids & set(_photo_cache.keys()))
        else:
            photo_count = len(community_photo_ids)
    else:
        photo_count = len(_photo_cache) if _photo_cache else 0

    # ML features: compute for all communities (AD-216 removes Rhodes-only restriction)
    # Proposals count: merge registry proposed_matches + proposals.json (clustering output)
    proposal_count = 0
    if hasattr(registry, "list_proposed_matches"):
        registry_proposals = registry.list_proposed_matches()
        if community_identity_ids is not None:
            registry_proposals = [p for p in registry_proposals if p.get("source_id") in community_identity_ids]
        proposal_count = len(registry_proposals)
    # Also count proposals.json entries (clustering pipeline output) — COMMUNITY-010
    try:
        _storage = os.getenv("STORAGE_DIR")
        _data_dir = os.path.join(_storage, "data") if _storage else os.getenv("DATA_DIR", "data")
        proposals_path = Path(_data_dir) / "proposals.json"
        if proposals_path.exists():
            import json as _json

            with open(proposals_path) as _f:
                proposals_data = _json.load(_f)
            file_proposals = proposals_data.get("proposals", [])
            if community_identity_ids is not None:
                file_proposals = [
                    p
                    for p in file_proposals
                    if p.get("source_identity_id") in community_identity_ids
                    or p.get("target_identity_id") in community_identity_ids
                ]
            # Avoid double-counting: only add file proposals not already in registry
            proposal_count = max(proposal_count, len(file_proposals))
    except Exception:
        pass

    # Count pending user annotations (for admin approvals badge)
    pending_annotations = 0
    try:
        annotations_data = _load_annotations()
        for ann in annotations_data.get("annotations", []):
            if ann.get("status") in ("pending", "pending_unverified"):
                pending_annotations += 1
    except Exception:
        pass

    # Count discoveries (high-confidence matches to confirmed identities)
    discovery_count = _count_discoveries(registry, community_identity_ids=community_identity_ids)

    return {
        "to_review": len(to_review),
        "confirmed": len(confirmed_list),
        "skipped": len(skipped_list),
        "rejected": len(dismissed),
        "photos": photo_count,
        "pending_uploads": _count_pending_uploads(),
        "proposals": proposal_count,
        "pending_annotations": pending_annotations,
        "discoveries": discovery_count,
    }


async def _notify_admin_upload(uploader_email: str, job_id: str, file_count: int, source: str) -> None:
    """Send email notification to admins about a new pending upload.

    Uses Resend API if RESEND_API_KEY is set. Fire-and-forget — does not
    block the upload response on email delivery.
    """
    import os

    resend_api_key = os.getenv("RESEND_API_KEY", "")
    if not resend_api_key:
        logging.info(f"[upload] No RESEND_API_KEY set, skipping email notification for job {job_id}")
        return

    if not ADMIN_EMAILS:
        logging.info(f"[upload] No ADMIN_EMAILS configured, skipping email notification for job {job_id}")
        return

    import httpx

    site_url = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")
    from_email = os.getenv("NOTIFICATION_FROM_EMAIL", "noreply@nolanandrewfox.com")
    subject = f"New photo upload pending review ({file_count} file{'s' if file_count != 1 else ''})"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px;">
        <h2 style="color: #1e293b;">New Upload Pending Review</h2>
        <p><strong>Uploader:</strong> {uploader_email}</p>
        <p><strong>Files:</strong> {file_count}</p>
        <p><strong>Source:</strong> {source or "Not specified"}</p>
        <p><strong>Job ID:</strong> <code>{job_id}</code></p>
        <p style="margin-top: 20px;">
            <a href="{site_url}/admin/pending"
               style="display: inline-block; background-color: #2563eb; color: #ffffff !important;
                      padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold;">
                Review Uploads
            </a>
        </p>
    </div>
    """

    try:
        async with httpx.AsyncClient() as client:
            for admin_email in ADMIN_EMAILS:
                await client.post(
                    "https://api.resend.com/emails",
                    json={
                        "from": f"Rhodesli <{from_email}>",
                        "to": [admin_email],
                        "subject": subject,
                        "html": html_body,
                    },
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
        logging.info(f"[upload] Email notification sent for job {job_id}")
    except Exception as e:
        logging.warning(f"[upload] Failed to send email notification for job {job_id}: {e}")


# =============================================================================
# FACE DATA & PHOTO REGISTRY LOADERS
# =============================================================================

_face_data_cache = None
_photo_registry_cache = None


def load_face_embeddings() -> dict[str, dict]:
    """
    Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Returns:
        Dict mapping face_id to {"mu": np.ndarray, "sigma_sq": np.ndarray}

    # TODO: Embeddings remain on disk (embeddings.npy) even when DATA_SOURCE=postgres.
    # NumPy arrays are not efficiently stored in Postgres. Future options:
    # - pgvector extension for embedding storage + similarity search
    # - Keep .npy on disk as performance-optimized cache
    # - R2 backup of embeddings.npy (PRD-027 Phase A)
    """
    from core.embeddings_io import load_face_data

    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        return {}
    return load_face_data(embeddings_path)


def get_face_data() -> dict[str, dict]:
    """Get face data with caching."""
    global _face_data_cache
    if _face_data_cache is None:
        _face_data_cache = load_face_embeddings()
    return _face_data_cache


def load_photo_registry():
    """Load the photo registry for merge validation.

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Returns an empty registry if the source is missing or corrupted,
    so the server never crashes on bad data.
    """
    global _photo_registry_cache
    if _photo_registry_cache is None:
        from core.photo_registry import PhotoRegistry

        if DATA_SOURCE == "postgres":
            try:
                loaded = PhotoRegistry.load_from_postgres()
                if loaded is not None:
                    _photo_registry_cache = loaded
                    return _photo_registry_cache
                logging.warning("Postgres photo load returned None, falling back to JSON")
            except Exception as e:
                logging.warning(f"Postgres photo load failed, falling back to JSON: {e}")

        photo_index_path = data_path / "photo_index.json"
        if photo_index_path.exists():
            try:
                _photo_registry_cache = PhotoRegistry.load(photo_index_path)
            except (ValueError, OSError) as e:
                logging.error(f"Failed to load photo registry from {photo_index_path}: {e}")
                _photo_registry_cache = PhotoRegistry()
        else:
            _photo_registry_cache = PhotoRegistry()
    return _photo_registry_cache


def save_photo_registry(registry):
    """Save photo registry to disk and sync to Supabase.

    Session 105b: Write-through architecture.
    - Always write JSON as backup (both DATA_SOURCE modes)
    - When DATA_SOURCE=postgres: synchronous Supabase write (not background thread)
    - photo_faces table is written alongside photos table
    """
    global _photo_registry_cache
    _photo_registry_cache = registry

    # Always write JSON as backup
    photo_index_path = data_path / "photo_index.json"
    registry.save(photo_index_path)

    # Build items for Supabase write
    items = [dict(v, photo_id=k) for k, v in registry._photos.items()]
    face_items = [{"photo_id": k, "face_ids": list(v.get("face_ids", []))} for k, v in registry._photos.items()]

    if DATA_SOURCE == "postgres":
        # Synchronous write — failures are visible (Session 105b)
        try:
            from app.supabase_data import shadow_write_photos_batch, shadow_write_photo_faces_batch

            shadow_write_photos_batch(items, strict=True)
            shadow_write_photo_faces_batch(face_items, strict=True)
        except Exception as e:
            logging.error(f"Postgres save_photo_registry failed: {e}")
            # JSON backup already written above
        return

    # JSON mode: shadow-write to Supabase in background
    def _shadow_sync_photos(photo_items, pf_items):
        try:
            from app.supabase_data import shadow_write_photos_batch, shadow_write_photo_faces_batch

            shadow_write_photos_batch(photo_items)
            shadow_write_photo_faces_batch(pf_items)
        except Exception as e:
            logging.warning(f"Supabase photo shadow sync failed: {e}")

    import threading

    threading.Thread(
        target=_shadow_sync_photos,
        args=(items, face_items),
        daemon=True,
    ).start()


# =============================================================================
# PHOTO CONTEXT HELPERS
# =============================================================================

# generate_photo_id, generate_face_id, make_css_id imported from app.utils


def load_embeddings_for_photos():
    """
    Load embeddings and build photo metadata cache.

    Returns:
        dict mapping photo_id -> {
            "filename": str,
            "faces": list of {face_id, bbox, face_index}
        }
    """
    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        return {}

    embeddings = np.load(embeddings_path, allow_pickle=True)

    # Group faces by photo_id
    photos = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]

        # Track face index per filename
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        photo_id = generate_photo_id(filename)
        # Use stored face_id if present (inbox format), otherwise generate legacy format
        face_id = entry.get("face_id") or generate_face_id(filename, face_index)

        # Parse bbox - it might be a string or list
        bbox = entry["bbox"]
        if isinstance(bbox, str):
            bbox = json.loads(bbox)
        elif hasattr(bbox, "tolist"):
            bbox = bbox.tolist()

        if photo_id not in photos:
            photos[photo_id] = {
                "filename": filename,
                "faces": [],
            }

        photos[photo_id]["faces"].append(
            {
                "face_id": face_id,
                "bbox": bbox,  # [x1, y1, x2, y2]
                "face_index": face_index,
                "det_score": float(entry.get("det_score", 0)),
                "quality": float(entry.get("quality", 0)),
            }
        )

    return photos


def has_displayable_face_bbox(face: dict) -> bool:
    """Return True when a face record has a usable [x1, y1, x2, y2] bbox."""
    bbox = face.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    return all(value is not None for value in bbox)


_photo_dimensions_cache = None


def _load_photo_dimensions_cache() -> dict:
    """Load photo dimensions from photo_index.json into a cache."""
    global _photo_dimensions_cache
    if _photo_dimensions_cache is not None:
        return _photo_dimensions_cache

    _photo_dimensions_cache = {}
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        try:
            import json

            with open(photo_index_path) as f:
                data = json.load(f)
            for photo_id, photo_data in data.get("photos", {}).items():
                width = photo_data.get("width", 0)
                height = photo_data.get("height", 0)
                if width > 0 and height > 0:
                    # Index by path and by filename for flexible lookup
                    path = photo_data.get("path", "")
                    if path:
                        _photo_dimensions_cache[path] = (width, height)
                        _photo_dimensions_cache[Path(path).name] = (width, height)
        except Exception as e:
            logging.warning(f"Failed to load photo dimensions cache: {e}")

    return _photo_dimensions_cache


def get_photo_dimensions(filename: str) -> tuple:
    """
    Get image dimensions for a photo.

    Args:
        filename: Photo filename (looked up in raw_photos/).

    Returns:
        (width, height) tuple or (0, 0) if file not found
    """
    basename = Path(filename).name

    # In R2 mode, photos aren't stored locally, so use cached dimensions
    # from photo_index.json instead of reading from filesystem
    if storage.is_r2_mode():
        cache = _load_photo_dimensions_cache()
        if basename in cache:
            return cache[basename]
        return (0, 0)

    # Local mode: read from filesystem
    filepath = photos_path / basename
    if not filepath.exists():
        # Fall back to cached dimensions from photo_index.json
        cache = _load_photo_dimensions_cache()
        if basename in cache:
            return cache[basename]
        return (0, 0)

    try:
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def get_identity_for_face(registry, face_id: str) -> dict:
    """
    Find the identity containing a face.

    Returns:
        Identity dict or None if not found
    """
    registry_dict = getattr(registry, "__dict__", None)
    face_lookup = registry_dict.get("_face_identity_lookup_cache") if registry_dict is not None else None
    if face_lookup is None:
        face_lookup = {}
        for identity in registry.list_identities():
            all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            for entry in all_face_ids:
                fid = entry if isinstance(entry, str) else entry.get("face_id")
                if fid:
                    face_lookup[fid] = identity
        if registry_dict is not None:
            registry_dict["_face_identity_lookup_cache"] = face_lookup

    return face_lookup.get(face_id)


def find_shared_photo_filename(
    target_id: str,
    neighbor_id: str,
    registry,
    photo_registry,
) -> str:
    """
    Find the filename of a shared photo between two identities.

    Used to show users why a merge is blocked (co-occurrence).

    Returns:
        Filename of shared photo, or empty string if none found.
    """
    # Get all face IDs for both identities
    faces_a = registry.get_all_face_ids(target_id)
    faces_b = registry.get_all_face_ids(neighbor_id)

    # Get photo_ids for each identity's faces
    photos_a = photo_registry.get_photos_for_faces(faces_a)
    photos_b = photo_registry.get_photos_for_faces(faces_b)

    # Find intersection
    shared_photos = photos_a & photos_b

    if shared_photos:
        # Get filename for first shared photo
        first_photo_id = next(iter(shared_photos))
        photo_path = photo_registry.get_photo_path(first_photo_id)
        if photo_path:
            return Path(photo_path).name

    return ""


def _compute_co_occurrence(
    identity_a_id: str,
    identity_b_id: str,
    registry,
    photo_registry,
) -> int:
    """
    Count how many photos two identities appear in together.

    Strong evidence they are different people (or family members in the same photo).
    Uses anchor + candidate face IDs for both identities.

    Returns:
        Number of shared photos (0 if none).
    """
    faces_a = registry.get_anchor_face_ids(identity_a_id) + registry.get_candidate_face_ids(identity_a_id)
    faces_b = registry.get_anchor_face_ids(identity_b_id) + registry.get_candidate_face_ids(identity_b_id)

    photos_a = photo_registry.get_photos_for_faces(faces_a)
    photos_b = photo_registry.get_photos_for_faces(faces_b)

    return len(photos_a & photos_b)


def get_first_anchor_face_id(identity_id: str, registry) -> str | None:
    """
    Get the best-quality anchor face ID for an identity.

    Used for showing thumbnails in neighbor cards.
    Falls back to the first anchor if quality data is unavailable.

    Returns:
        Best anchor face ID, or None if identity has no anchors.
    """
    try:
        anchor_ids = registry.get_anchor_face_ids(identity_id)
        if not anchor_ids:
            return None
        return get_best_face_id(anchor_ids)
    except KeyError:
        return None


import threading as _threading

# Photo metadata cache (rebuilt on each request for simplicity)
_cache_lock = _threading.Lock()  # Guards _build_caches() for background prewarm
_photo_cache = None
_face_to_photo_cache = None
_photo_id_aliases = None  # Maps photo_index.json IDs → SHA256 cache IDs


def _invalidate_all_caches():
    """Reset ALL in-memory caches so data is reloaded from disk.

    IMPORTANT: Every cached object that reads from data files MUST be
    cleared here. Missing a cache causes stale data after sync pushes.
    Session 104b: _photo_registry_cache and community caches were missed,
    causing Robert Mattatia photos to show without metadata.
    """
    global _photo_cache, _face_to_photo_cache, _photo_id_aliases
    global _date_labels_cache, _photo_locations_cache
    global _registry_cache, _photo_registry_cache
    global _community_photo_ids_cache, _community_identity_ids_cache, _community_ids_cache_ts
    global _face_data_cache
    _photo_cache = None
    _face_to_photo_cache = None
    _photo_id_aliases = None
    _date_labels_cache = None
    _photo_locations_cache = None
    _registry_cache = None
    _photo_registry_cache = None
    _face_data_cache = None
    _community_photo_ids_cache = {}
    _community_identity_ids_cache = {}
    _community_ids_cache_ts = 0.0


def _upload_new_files_to_r2(data_dir: Path, job_id: str):
    """Upload raw photos and crops from a processed job to R2."""
    import os

    r2_url = os.getenv("R2_PUBLIC_URL", "")
    r2_access = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_account = os.getenv("R2_ACCOUNT_ID", "")
    r2_bucket = os.getenv("R2_BUCKET_NAME", "rhodesli-photos")

    if not (r2_access and r2_secret and r2_account):
        logging.info(f"R2 not configured, skipping upload for job {job_id}")
        return

    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{r2_account}.r2.cloudflarestorage.com",
        aws_access_key_id=r2_access,
        aws_secret_access_key=r2_secret,
    )

    uploaded_raw_keys = set()

    # Upload raw photos from the job directory if it still exists.
    upload_dirs = [
        data_dir / "uploads" / job_id,
        data_dir.parent / "uploads" / job_id,
        data_dir / "staging" / job_id,
        data_dir.parent / "staging" / job_id,
    ]
    for uploads_dir in upload_dirs:
        if not uploads_dir.exists():
            continue
        for f in uploads_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp"):
                r2_key = f"raw_photos/{f.name}"
                try:
                    s3.upload_file(str(f), r2_bucket, r2_key, ExtraArgs={"ContentType": "image/jpeg"})
                    logging.info(f"Uploaded {r2_key} to R2")
                    uploaded_raw_keys.add(r2_key)
                except Exception as e:
                    logging.warning(f"Failed to upload {r2_key}: {e}")

    # Upload raw photos from the canonical photo_index path as a fallback.
    import json

    photo_index_path = data_dir / "photo_index.json"
    photo_index = {}
    if photo_index_path.exists():
        with open(photo_index_path) as pf:
            photo_index = json.load(pf)

    for pid, pdata in photo_index.get("photos", {}).items():
        if job_id not in pid:
            continue
        raw_rel_path = pdata.get("path", "")
        raw_filename = Path(raw_rel_path).name
        r2_key = f"raw_photos/{raw_filename}"
        if not raw_filename or r2_key in uploaded_raw_keys:
            continue
        raw_candidates = [
            data_dir.parent / raw_rel_path,
            data_dir.parent / "raw_photos" / raw_filename,
            data_dir / raw_rel_path,
            data_dir / "raw_photos" / raw_filename,
        ]
        raw_path = next((candidate for candidate in raw_candidates if candidate.exists()), None)
        if not raw_path:
            continue
        try:
            s3.upload_file(str(raw_path), r2_bucket, r2_key, ExtraArgs={"ContentType": "image/jpeg"})
            logging.info(f"Uploaded {r2_key} to R2")
            uploaded_raw_keys.add(r2_key)
        except Exception as e:
            logging.warning(f"Failed to upload {r2_key}: {e}")

    # Upload crops (new crops from this job)
    crops_dir = data_dir / "crops" if (data_dir / "crops").exists() else data_dir.parent / "app" / "static" / "crops"
    if crops_dir.exists():
        for pid, pdata in photo_index.get("photos", {}).items():
            if job_id in pid:
                for face_id in pdata.get("face_ids", []):
                    crop_path = crops_dir / f"{face_id}.jpg"
                    if crop_path.exists():
                        r2_key = f"crops/{face_id}.jpg"
                        try:
                            s3.upload_file(str(crop_path), r2_bucket, r2_key, ExtraArgs={"ContentType": "image/jpeg"})
                            logging.info(f"Uploaded {r2_key} to R2")
                        except Exception as e:
                            logging.warning(f"Failed to upload crop {r2_key}: {e}")


def _build_caches():
    """Build photo and face-to-photo caches.

    Loads raw detections from embeddings.npy, then filters each photo's
    face list to only include faces registered in photo_index.json.
    This removes noise detections (e.g., a newspaper photo might have
    63 raw detections but only 21 real registered faces).

    Thread-safe: uses _cache_lock to prevent concurrent builds during
    background prewarm and request handling.
    """
    global _photo_cache, _face_to_photo_cache, _photo_id_aliases
    if _photo_cache is not None:
        return  # Fast path: already built
    with _cache_lock:
        if _photo_cache is not None:
            return  # Double-check after acquiring lock
        _photo_cache = load_embeddings_for_photos()

        # Merge source data and filter faces using photo_index.json
        try:
            photo_index_raw = {}
            photo_index_path = data_path / "photo_index.json"
            if photo_index_path.exists():
                with open(photo_index_path) as f:
                    photo_index_raw = json.load(f)
            photo_registry = load_photo_registry()

            # Build filename-based fallback maps for photos with mismatched IDs
            # (e.g., inbox_* IDs in photo_index.json vs SHA256 IDs in _photo_cache)
            filename_to_source = {}
            filename_to_collection = {}
            filename_to_source_url = {}
            filename_to_face_ids = {}
            filename_to_face_ids_ordered = {}
            filename_to_metadata = {}
            filename_to_photo_index_id = {}
            filename_to_photo_index_order = {}

            def _filename_entry_score(path: str, metadata: dict, face_ids) -> tuple:
                """Rank duplicate basename entries so the richest archive metadata wins."""
                return (
                    1 if metadata.get("upload_date") else 0,
                    1 if metadata.get("uploaded_by") else 0,
                    1 if metadata.get("job_id") else 0,
                    1 if str(path).startswith("raw_photos/") else 0,
                    metadata.get("created_at", ""),
                    metadata.get("updated_at", ""),
                    len(face_ids or []),
                )

            best_raw_entries = {}
            for photo_index_order, (pid, photo_data) in enumerate(photo_index_raw.get("photos", {}).items()):
                path = photo_data.get("path", "")
                if not path:
                    continue
                fname = Path(path).name
                candidate = {
                    "pid": pid,
                    "path": path,
                    "photo_index_order": photo_index_order,
                    "ordered_face_ids": [fid for fid in photo_data.get("face_ids", []) if isinstance(fid, str) and fid],
                    "metadata": {k: v for k, v in photo_data.items() if v},
                }
                existing = best_raw_entries.get(fname)
                if existing is None or _filename_entry_score(
                    candidate["path"], candidate["metadata"], candidate["ordered_face_ids"]
                ) > _filename_entry_score(existing["path"], existing["metadata"], existing["ordered_face_ids"]):
                    best_raw_entries[fname] = candidate

            for fname, candidate in best_raw_entries.items():
                filename_to_face_ids_ordered[fname] = candidate["ordered_face_ids"]
                filename_to_photo_index_id[fname] = candidate["pid"]
                filename_to_photo_index_order[fname] = candidate["photo_index_order"]

            best_registry_entries = {}
            for pid in photo_registry._photos:
                path = photo_registry.get_photo_path(pid)
                source = photo_registry.get_source(pid)
                collection = photo_registry.get_collection(pid)
                source_url = photo_registry.get_source_url(pid)
                face_ids = photo_registry.get_faces_in_photo(pid)
                metadata = photo_registry.get_metadata(pid)
                if path:
                    fname = Path(path).name
                    candidate = {
                        "path": path,
                        "source": source,
                        "collection": collection,
                        "source_url": source_url,
                        "face_ids": face_ids,
                        "metadata": metadata,
                    }
                    existing = best_registry_entries.get(fname)
                    if existing is None or _filename_entry_score(
                        candidate["path"], candidate["metadata"], candidate["face_ids"]
                    ) > _filename_entry_score(existing["path"], existing["metadata"], existing["face_ids"]):
                        best_registry_entries[fname] = candidate

            for fname, candidate in best_registry_entries.items():
                if candidate["source"]:
                    filename_to_source[fname] = candidate["source"]
                if candidate["collection"]:
                    filename_to_collection[fname] = candidate["collection"]
                if candidate["source_url"]:
                    filename_to_source_url[fname] = candidate["source_url"]
                filename_to_face_ids[fname] = candidate["face_ids"]
                filename_to_face_ids_ordered.setdefault(fname, sorted(candidate["face_ids"]))
                if candidate["metadata"]:
                    filename_to_metadata[fname] = candidate["metadata"]

            for photo_id in _photo_cache:
                filename = _photo_cache[photo_id].get("filename", "")
                fname = Path(filename).name

                # Filter faces to only registered ones from photo_index
                registered_ids = filename_to_face_ids_ordered.get(fname)
                if registered_ids is None:
                    registered_ids = sorted(filename_to_face_ids.get(fname, []))
                if registered_ids:
                    existing_faces = {
                        face["face_id"]: face
                        for face in _photo_cache[photo_id]["faces"]
                        if face["face_id"] in registered_ids
                    }
                    merged_faces = []
                    missing_artifacts = 0
                    for face_id in registered_ids:
                        face = existing_faces.get(face_id)
                        if face:
                            merged_faces.append(face)
                            continue
                        missing_artifacts += 1
                        merged_faces.append(
                            {
                                "face_id": face_id,
                                "bbox": [],
                                "face_index": None,
                                "det_score": 0.0,
                                "quality": 0.0,
                                "missing_artifacts": True,
                            }
                        )
                    _photo_cache[photo_id]["faces"] = merged_faces
                    if missing_artifacts:
                        _photo_cache[photo_id]["missing_face_artifacts"] = missing_artifacts

                # Set source (provenance)
                source = photo_registry.get_source(photo_id)
                if not source:
                    source = filename_to_source.get(fname, "")
                _photo_cache[photo_id]["source"] = source

                # Set collection (classification)
                collection = photo_registry.get_collection(photo_id)
                if not collection:
                    collection = filename_to_collection.get(fname, "")
                _photo_cache[photo_id]["collection"] = collection

                # Set source_url (citation)
                source_url = photo_registry.get_source_url(photo_id)
                if not source_url:
                    source_url = filename_to_source_url.get(fname, "")
                _photo_cache[photo_id]["source_url"] = source_url

                # Merge photo metadata (BE-012)
                # Try direct lookup first, then filename fallback for mismatched IDs
                metadata = photo_registry.get_metadata(photo_id)
                fallback_meta = filename_to_metadata.get(fname, {})
                # Merge fallback first (lower priority), then direct (higher priority)
                merged = {}
                merged.update(fallback_meta)
                merged.update(metadata)
                if merged:
                    _photo_cache[photo_id].update(merged)
                if fname in filename_to_photo_index_order:
                    _photo_cache[photo_id]["photo_index_order"] = filename_to_photo_index_order[fname]

            # Preserve photo_index-only photos even when embeddings are absent.
            for fname, photo_index_id in filename_to_photo_index_id.items():
                cache_id = generate_photo_id(fname)
                if cache_id in _photo_cache:
                    continue
                registered_ids = filename_to_face_ids_ordered.get(fname)
                if registered_ids is None:
                    registered_ids = sorted(filename_to_face_ids.get(fname, []))
                placeholder_faces = [
                    {
                        "face_id": face_id,
                        "bbox": [],
                        "face_index": None,
                        "det_score": 0.0,
                        "quality": 0.0,
                        "missing_artifacts": True,
                    }
                    for face_id in registered_ids
                ]
                photo_data = {
                    "filename": fname,
                    "faces": placeholder_faces,
                    "source": filename_to_source.get(fname, ""),
                    "collection": filename_to_collection.get(fname, ""),
                    "source_url": filename_to_source_url.get(fname, ""),
                }
                metadata = filename_to_metadata.get(fname, {})
                if metadata:
                    photo_data.update(metadata)
                if fname in filename_to_photo_index_order:
                    photo_data["photo_index_order"] = filename_to_photo_index_order[fname]
                if placeholder_faces:
                    photo_data["missing_face_artifacts"] = len(placeholder_faces)
                _photo_cache[cache_id] = photo_data
        except FileNotFoundError:
            # No photo_index.json yet, set empty sources
            for photo_id in _photo_cache:
                _photo_cache[photo_id]["source"] = ""

        # Build reverse mapping AFTER filtering: face_id -> photo_id
        _face_to_photo_cache = {}
        for photo_id, photo_data in _photo_cache.items():
            for face in photo_data["faces"]:
                _face_to_photo_cache[face["face_id"]] = photo_id

        # Also include face_to_photo from photo_index.json for faces not in embeddings.
        # Some faces exist in photo_index but not in embeddings.npy (e.g., inbox faces
        # from community uploads). Without this, community scoping misses them.
        try:
            for fid, pid in photo_registry._face_to_photo.items():
                if fid not in _face_to_photo_cache:
                    _face_to_photo_cache[fid] = pid
        except Exception:
            pass

        # Build alias map: photo_index.json IDs → SHA256 cache IDs
        # Community/inbox photos have IDs like "inbox_community-batch-..."
        # in photo_index.json, but _photo_cache uses SHA256(filename)[:16].
        _photo_id_aliases = {}
        try:
            from core.photo_registry import PhotoRegistry

            photo_registry = PhotoRegistry.load(data_path / "photo_index.json")
            filename_to_cache_id = {}
            for cache_id, pdata in _photo_cache.items():
                fname = Path(pdata.get("filename", "")).name
                if fname:
                    filename_to_cache_id[fname] = cache_id
            for pid in photo_registry._photos:
                if pid not in _photo_cache:
                    path = photo_registry.get_photo_path(pid)
                    if path:
                        fname = Path(path).name
                        cache_id = filename_to_cache_id.get(fname)
                        if cache_id:
                            _photo_id_aliases[pid] = cache_id
        except (FileNotFoundError, Exception):
            pass


def get_photo_metadata(photo_id: str) -> dict:
    """Get photo metadata including face bboxes."""
    _build_caches()
    result = _photo_cache.get(photo_id)
    if result is None and _photo_id_aliases:
        # Try resolving photo_index.json ID → SHA256 cache ID
        resolved = _photo_id_aliases.get(photo_id)
        if resolved:
            result = _photo_cache.get(resolved)
    return result


def resolve_photo_registry_photo_id(photo_id: str, photo_registry=None) -> str:
    """Resolve viewer/cache IDs back to the editable PhotoRegistry ID.

    Some live pages are addressed by SHA/cache IDs while the durable photo
    registry still stores the canonical photo_index / inbox-style ID. Editing
    routes must resolve through the same filename/alias bridge that read paths
    use, or saves appear to silently fail.
    """
    if not photo_id:
        return photo_id

    photo_registry = photo_registry or load_photo_registry()
    try:
        if photo_registry.get_photo_path(photo_id):
            return photo_id
    except Exception:
        pass

    _build_caches()

    if _photo_id_aliases:
        for registry_photo_id, cache_photo_id in _photo_id_aliases.items():
            if cache_photo_id == photo_id:
                try:
                    if photo_registry.get_photo_path(registry_photo_id):
                        return registry_photo_id
                except Exception:
                    pass

    photo_meta = get_photo_metadata(photo_id) or {}
    filename = Path(photo_meta.get("filename", "")).name
    if not filename:
        return photo_id

    for registry_photo_id, entry in getattr(photo_registry, "_photos", {}).items():
        path = entry.get("path") or ""
        if path and Path(path).name == filename:
            return registry_photo_id
    return photo_id


def get_photo_id_for_face(face_id: str) -> str:
    """Get the photo_id containing a face."""
    _build_caches()
    if _face_to_photo_cache is None:
        return None
    return _face_to_photo_cache.get(face_id)


def get_face_quality(face_id: str) -> float:
    """Look up face quality score from embeddings cache.

    Returns the quality score stored in embeddings.npy for this face,
    or None if not found. This is needed because inbox-style crop
    filenames don't encode quality in the filename.
    """
    photo_id = get_photo_id_for_face(face_id)
    if not photo_id:
        return None
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None
    for face in photo.get("faces", []):
        if face.get("face_id") == face_id:
            q = face.get("quality", 0)
            return q if q > 0 else None
    return None


def _get_face_cache_entry(face_id: str) -> dict | None:
    """Look up full face data (bbox, det_score, quality) from embeddings cache."""
    _build_caches()
    photo_id = get_photo_id_for_face(face_id)
    if not photo_id:
        return None
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None
    for face in photo.get("faces", []):
        if face.get("face_id") == face_id:
            return face
    return None


def compute_face_quality_score(face_id: str) -> float:
    """Compute composite quality score (0-100) for a face.

    Components:
    - Detection confidence (0-30 pts): InsightFace SCRFD det_score
    - Face crop size (0-35 pts): pixel area from bounding box
    - Embedding norm (0-35 pts): proxy for image quality (MagFace principle)

    Returns 0 if face data is not found.
    """
    face = _get_face_cache_entry(face_id)
    if not face:
        return 0.0

    score = 0.0

    # 1. Detection confidence — 0-30 pts
    det_score = face.get("det_score", 0.5)
    score += det_score * 30

    # 2. Face crop size from bbox — 0-35 pts
    # Good faces are 150+ pixels on a side (~22500 area)
    bbox = face.get("bbox", [0, 0, 0, 0])
    if len(bbox) == 4:
        face_width = abs(bbox[2] - bbox[0])
        face_height = abs(bbox[3] - bbox[1])
        face_area = face_width * face_height
        # Scale: 0=tiny, 1=good (22500px²=150×150)
        area_factor = min(face_area / 22500.0, 1.0)
        score += area_factor * 35

    # 3. Embedding norm — 0-35 pts
    # Raw quality is the embedding L2 norm (~15-30 range typically)
    raw_quality = face.get("quality", 0)
    if raw_quality > 0:
        # Normalize: 15 = low, 30 = high quality
        norm_factor = max(min((raw_quality - 15) / 15.0, 1.0), 0.0)
        score += norm_factor * 35

    return round(score, 1)


def get_best_face_id(face_ids: list) -> str | None:
    """Pick the highest-quality face from a list of face IDs.

    Returns the face_id with the highest composite quality score,
    or the first one if scores can't be computed.
    """
    if not face_ids:
        return None

    # Normalize: face_ids can be strings or dicts
    ids = []
    for f in face_ids:
        if isinstance(f, str):
            ids.append(f)
        elif isinstance(f, dict):
            ids.append(f.get("face_id", ""))
        else:
            ids.append(str(f))

    if len(ids) == 1:
        return ids[0]

    best_id = ids[0]
    best_score = -1
    for fid in ids:
        s = compute_face_quality_score(fid)
        if s > best_score:
            best_score = s
            best_id = fid
    return best_id


def _highlight_match(name: str, query: str):
    """Return FastHTML elements with the matched portion highlighted.

    Case-insensitive substring match. When the exact query doesn't match,
    tries surname variant terms (e.g., query "Capelluto" highlights "Capeluto"
    in "Leon Capeluto").
    """
    if not query:
        return name
    idx = name.lower().find(query.lower())
    if idx == -1:
        # Try variant terms — if query word maps to a variant group,
        # highlight whichever variant appears in the name
        from core.registry import _load_surname_variants

        variant_lookup = _load_surname_variants()
        for word in query.lower().split():
            if word in variant_lookup:
                for variant in variant_lookup[word]:
                    vidx = name.lower().find(variant)
                    if vidx != -1:
                        before = name[:vidx]
                        match = name[vidx : vidx + len(variant)]
                        after = name[vidx + len(variant) :]
                        return (
                            Span(before) if before else None,
                            Span(match, cls="text-amber-300 font-semibold"),
                            Span(after) if after else None,
                        )
        return name
    before = name[:idx]
    match = name[idx : idx + len(query)]
    after = name[idx + len(query) :]
    return (
        Span(before) if before else None,
        Span(match, cls="text-amber-300 font-semibold"),
        Span(after) if after else None,
    )


# parse_quality_from_filename, photo_url imported from app.utils


_crop_files_cache = None


def get_crop_files():
    """
    Get set of available crop filenames.

    In local mode: reads from static/crops directory.
    In R2 mode: builds the expected crop filenames from embeddings data,
    since we can't list R2 bucket contents.

    Crop filename format: {sanitized_stem}_{quality:.2f}_{face_index}.jpg
    """
    global _crop_files_cache
    if _crop_files_cache is not None:
        return _crop_files_cache

    # Try local mode first
    crops_dir = static_path / "crops"
    if crops_dir.exists():
        crop_files = {f.name for f in crops_dir.glob("*.jpg")}
        if crop_files:
            _crop_files_cache = crop_files
            return _crop_files_cache

    # R2 mode or no local crops: build from embeddings
    # The embeddings have: filename, quality, and we compute face_index
    # by tracking order of faces within each unique filename
    crop_files = set()

    embeddings_path = Path(DATA_DIR) / "embeddings.npy"
    if embeddings_path.exists():
        try:
            embeddings = np.load(embeddings_path, allow_pickle=True)
            filename_face_counts = {}

            for entry in embeddings:
                if not isinstance(entry, dict):
                    continue

                filename = entry.get("filename", "")
                quality = entry.get("quality")

                if not filename or quality is None:
                    continue

                # Get face index (order within this filename)
                face_index = filename_face_counts.get(filename, 0)
                filename_face_counts[filename] = face_index + 1

                # Build crop filename
                stem = Path(filename).stem
                sanitized = stem.lower()
                sanitized = re.sub(r"[^a-z0-9]+", "_", sanitized)
                sanitized = sanitized.strip("_")

                crop_filename = f"{sanitized}_{quality:.2f}_{face_index}.jpg"
                crop_files.add(crop_filename)

        except Exception as e:
            logging.warning(f"Failed to build crop files from embeddings: {e}")

    _crop_files_cache = crop_files
    return _crop_files_cache


# sanitize_stem imported from app.utils


def _existing_suggestions_for_identity(identity_id: str, face_id_encoded: str) -> list:
    """Return FT elements showing existing pending suggestions for an identity.

    If there are pending name_suggestion annotations for this identity,
    returns "I Agree" buttons so community members can confirm them.
    """
    if not identity_id:
        return []
    try:
        annotations = _load_annotations()
    except Exception:
        return []

    pending = [
        a
        for a in annotations.get("annotations", {}).values()
        if a.get("target_id") == identity_id
        and a.get("type") == "name_suggestion"
        and a.get("status") in ("pending", "pending_unverified")
    ]
    if not pending:
        return []

    from urllib.parse import unquote
    import json as _json

    items = []
    for ann in pending:
        confirmations = len(ann.get("confirmations", []))
        people_count = 1 + confirmations  # original + confirmations
        items.append(
            Div(
                Div(
                    Span(ann["value"], cls="text-sm font-medium text-amber-300"),
                    Span(
                        f"suggested by {people_count} {'person' if people_count == 1 else 'people'}",
                        cls="text-xs text-slate-500",
                    ),
                    cls="flex flex-col",
                ),
                Button(
                    "I Agree",
                    hx_post="/api/annotations/submit",
                    hx_vals=_json.dumps(
                        {
                            "target_type": "identity",
                            "target_id": identity_id,
                            "annotation_type": "name_suggestion",
                            "value": ann["value"],
                            "confidence": "likely",
                            "reason": f"face_tag:{unquote(face_id_encoded)}:agree",
                        }
                    ),
                    hx_target="closest div",
                    hx_swap="outerHTML",
                    cls="px-2 py-0.5 text-xs bg-emerald-700 text-white rounded hover:bg-emerald-600 flex-shrink-0",
                    type="button",
                ),
                cls="flex items-center justify-between gap-2 px-2 py-1.5 bg-amber-900/20 border border-amber-700/30 rounded mb-1",
            )
        )
    return items


def resolve_face_image_url(face_id: str, crop_files: set) -> str:
    """
    Resolve a canonical face ID to its crop image URL.

    Supports two face_id formats:
    1. Legacy: {filename_stem}:face{index} -> {sanitized_stem}_{quality}_{index}.jpg
    2. Inbox: inbox_{hash} -> inbox_{hash}.jpg (direct mapping)

    In local mode: returns /static/crops/{filename}
    In R2 mode: returns Cloudflare R2 public URL

    Args:
        face_id: Canonical face identifier
        crop_files: Set of available crop filenames

    Returns:
        URL path to the crop image, or None if no matching crop file is found.
    """
    # Inbox format: face_ids starting with "inbox_" have crops named exactly {face_id}.jpg
    # In R2 mode, inbox crops aren't in embeddings.npy (and thus not in crop_files),
    # so we return the URL directly without checking crop_files.
    if face_id.startswith("inbox_"):
        inbox_crop = f"{face_id}.jpg"
        # In local mode, verify it exists; in R2 mode, assume it exists
        if storage.is_r2_mode() or inbox_crop in crop_files:
            return storage.get_crop_url_by_filename(inbox_crop)

    # Fall back to legacy format parsing
    # Legacy face_ids use format: {filename_stem}:face{index}
    if ":face" not in face_id:
        return None

    stem, face_suffix = face_id.rsplit(":face", 1)
    try:
        face_index = int(face_suffix)
    except ValueError:
        return None

    # Sanitize the stem to match crop file naming
    sanitized = sanitize_stem(stem)

    # Find matching crop file: {sanitized}_{quality}_{index}.jpg
    # Quality is a float like 22.17, index matches face_index
    pattern = re.compile(rf"^{re.escape(sanitized)}_[\d.]+_{face_index}\.jpg$")

    for crop in crop_files:
        if pattern.match(crop):
            return storage.get_crop_url_by_filename(crop)

    return None


# =============================================================================
# UI COMPONENTS
# =============================================================================


def toast_container() -> Div:
    """
    Toast notification container.
    UX Intent: Non-blocking feedback for actions.
    """
    return Div(id="toast-container", cls="fixed top-4 right-4 z-[10001] flex flex-col gap-2")


def toast(message: str, variant: str = "info") -> Div:
    """
    Single toast notification.
    Variants: success, error, warning, info
    """
    # UI BOUNDARY: sanitize message for safe rendering
    safe_message = ensure_utf8_display(message)

    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(safe_message),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Auto-dismiss after 4 seconds
        **{"_": "on load wait 4s then remove me"},
    )


def toast_with_undo(
    message: str,
    source_id: str,
    target_id: str,
    variant: str = "info",
) -> Div:
    """
    Toast notification with inline Undo button (D5).

    Used for "Not Same Person" rejection - allows immediate reversal.
    Auto-dismisses after 8 seconds (longer than standard toast to allow undo).
    """
    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(message, cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{source_id}/unreject/{target_id}",
            hx_swap="outerHTML",
            hx_target="closest div",  # Replace the toast itself
            type="button",
        ),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Longer dismiss time to allow undo
        **{"_": "on load wait 8s then remove me"},
    )


def _admin_dashboard_banner(counts: dict, current_section: str) -> Div:
    """Admin-only dashboard summary banner at the top of the workstation.

    Shows inbox count, skipped count, and quick links.
    Focus/Browse toggle lives in each section's header instead.
    Only rendered when user is admin.
    """
    to_review = counts.get("to_review", 0)
    skipped = counts.get("skipped", 0)
    confirmed = counts.get("confirmed", 0)
    proposals = counts.get("proposals", 0)
    photo_count = counts.get("photo_count", 0)

    stat_items = [
        ("To Review", to_review, "/?section=to_review&view=focus", "text-amber-500"),
        ("People", confirmed, "/?section=confirmed", "text-emerald-500"),
        ("Help Identify", skipped, "/?section=skipped", "text-amber-300"),
    ]
    if proposals > 0:
        stat_items.append(("Proposals", proposals, "/admin/proposals", "text-blue-400"))

    stats_row = [
        A(
            Span(str(count), cls=f"font-display font-semibold text-lg {color}"),
            Span(f" {label}", cls="text-slate-400 text-xs font-medium uppercase tracking-wider ml-1"),
            href=link,
            cls="hover:bg-slate-800 px-3 py-1.5 rounded-md transition-colors flex items-baseline line-height-none border border-transparent hover:border-slate-700",
        )
        for label, count, link, color in stat_items
    ]

    return Div(
        Div(
            Div(*stats_row, cls="flex items-center gap-2"),
            cls="max-w-7xl mx-auto px-6 flex items-center justify-between",
        ),
        id="admin-dashboard-banner",
        cls="py-2 bg-slate-900 border-b border-amber-900/40 sticky top-0 z-40 shadow-sm ui99-workstation-banner",
    )


def mobile_header() -> Div:
    """
    Mobile top bar with hamburger menu button.
    Hidden on desktop (lg+), shown on smaller screens.
    """
    return Div(
        Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>'
            ),
            cls="text-white p-2 -ml-2",
            onclick="toggleSidebar()",
            type="button",
            aria_label="Open menu",
        ),
        Span("Rhodesli", cls="text-lg font-display font-bold text-white"),
        cls="mobile-header fixed top-0 left-0 right-0 h-14 bg-slate-800 border-b border-slate-700 "
        "flex items-center gap-3 px-4 z-20",
        id="mobile-header",
    )


def _public_nav_links(active: str = "", user=None, community_slug: str | None = None) -> list:
    """Build standard navigation links for public pages."""
    _inactive = "text-amber-900/60 hover:text-amber-900 font-serif tracking-wide text-sm transition-colors duration-300"
    _active = "text-amber-950 font-serif tracking-wide text-sm border-b border-amber-900 pb-0.5"

    p = community_url_prefix(community_slug)

    links = [
        # Core Archive
        A("Photos", href=f"{p}/photos", cls=_active if active == "photos" else _inactive),
        A("Collections", href=f"{p}/collections", cls=_active if active == "collections" else _inactive),
        A("People", href=f"{p}/people", cls=_active if active == "people" else _inactive),
        A("Timeline", href=f"{p}/timeline", cls=_active if active == "timeline" else _inactive),
        A("Map", href=f"{p}/map", cls=_active if active == "map" else _inactive),
        # Visual separator for Tools
        Span("|", cls="text-slate-700 hidden lg:inline"),
        # Tools
        A("Tree", href=f"{p}/tree", cls=_active if active == "tree" else _inactive),
        A("Connect", href=f"{p}/connect", cls=_active if active == "connect" else _inactive),
        A("Compare", href="/tools/compare", cls=_active if active == "compare" else _inactive),
        A("Estimate", href="/tools/estimate", cls=_active if active == "estimate" else _inactive),
    ]

    # Help Identify CTA — links to dedicated /help page
    links.append(
        A(
            "Help Identify",
            href=f"{p}/help",
            cls=(
                "text-amber-400 font-medium text-sm border-b-2 border-amber-500 pb-1 ml-2"
                if active == "help"
                else "text-amber-400 hover:text-amber-300 font-medium text-sm transition-colors border border-amber-500/30 px-2 py-0.5 rounded ml-2"
            ),
        )
    )

    if is_auth_enabled() and not user:
        links.append(
            A(
                "Sign In",
                href="/login",
                cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-2",
            )
        )

    # Bell icon for logged-in users (PRD-028 Notifications)
    if user:
        bell_svg = NotStr(
            '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" '
            'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" '
            'd="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 '
            "6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 "
            "11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 "
            '11-6 0v-1m6 0H9"/></svg>'
        )
        links.append(
            A(
                Div(
                    bell_svg,
                    Span(id="notification-badge"),
                    cls="relative",
                    hx_get="/api/notifications/count",
                    hx_trigger="load, every 30s",
                    hx_target="#notification-badge",
                    hx_swap="outerHTML",
                ),
                href=f"{p}/notifications",
                cls="text-slate-300 hover:text-white transition-colors ml-2",
                title="Notifications",
            )
        )

    return links


def _public_page_nav(
    nav_links: list,
    *,
    active: str = "",
    user=None,
    community_slug: str | None = None,
    max_w: str = "max-w-5xl",
    font_cls: str = "text-lg font-display font-bold text-white",
    sticky: bool = True,
    fixed: bool = False,
    extra_links: list = None,
    include_admin_bar: bool = True,
) -> object:
    """Build a public page nav bar with mobile hamburger menu.

    All public pages should use this instead of inlining Nav() with hidden sm:flex.
    Includes a hamburger button visible below sm breakpoint.
    """
    hamburger_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>'
    close_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>'

    # Mobile menu overlay (hidden by default, shown via JS)
    mobile_menu_links = []
    for link in nav_links:
        # Clone link with mobile-friendly styling
        href = link.attrs.get("href", "#") if hasattr(link, "attrs") else "#"
        text = link.children[0] if hasattr(link, "children") and link.children else str(link)
        if hasattr(text, "children"):
            text = str(text.children[0]) if text.children else str(text)
        mobile_menu_links.append(
            A(
                str(text),
                href=href,
                cls="block px-4 py-3 text-slate-200 hover:bg-slate-700/50 hover:text-white text-base font-medium rounded-lg transition-colors",
                onclick="document.getElementById('mobile-nav-overlay').classList.add('hidden');",
            )
        )

    mobile_overlay = Div(
        # Backdrop
        Div(
            onclick="closeMobileNav ? closeMobileNav() : document.getElementById('mobile-nav-overlay').classList.add('hidden');",
            cls="absolute inset-0 bg-black/50 transition-opacity",
        ),
        # Menu panel (slides from right)
        Div(
            Div(
                Span("Rhodesli", cls="text-lg font-display font-bold text-white"),
                Button(
                    NotStr(close_svg),
                    cls="text-slate-400 hover:text-white p-1",
                    onclick="closeMobileNav ? closeMobileNav() : document.getElementById('mobile-nav-overlay').classList.add('hidden');",
                    type="button",
                    aria_label="Close menu",
                ),
                cls="flex items-center justify-between px-4 py-4 border-b border-slate-700",
            ),
            Div(*mobile_menu_links, cls="py-2 px-2"),
            cls="mobile-nav-panel absolute top-0 right-0 w-72 h-full bg-slate-800 shadow-xl overflow-y-auto transition-transform duration-200",
            style="transform: translateX(100%);",
        ),
        id="mobile-nav-overlay",
        cls="hidden fixed inset-0 z-[60]",
        style="display: none;",
    )

    # Hamburger button (visible below md/768px, hidden at md+)
    hamburger_btn = Button(
        NotStr(hamburger_svg),
        cls="md:hidden text-white p-1 -ml-1",
        onclick="openMobileNav ? openMobileNav() : document.getElementById('mobile-nav-overlay').classList.remove('hidden');",
        type="button",
        aria_label="Open navigation menu",
    )

    right_items = list(extra_links) if extra_links else []

    pos_cls = "sticky top-0" if sticky else ("fixed top-0 left-0 right-0" if fixed else "")

    home_href = (
        f"{community_url_prefix(community_slug)}/" if community_slug and community_url_prefix(community_slug) else "/"
    )

    nav = Nav(
        Div(
            Div(
                hamburger_btn,
                A(Span("Rhodesli", cls=font_cls), href=home_href),
                cls="flex items-center gap-2",
            ),
            Div(*nav_links, *right_items, cls="hidden md:flex items-center gap-6"),
            cls=f"{max_w} mx-auto px-6 flex items-center justify-between h-16",
        ),
        mobile_overlay,
        cls=f"bg-slate-900/80 backdrop-blur-md border-b border-slate-800 {pos_cls} z-50",
    )

    if include_admin_bar and user and getattr(user, "is_admin", False):
        return Div(nav, _admin_bar(user, community_slug=community_slug), id="nav-with-admin")
    return nav


def _admin_bar(user=None, community_slug: str = "rhodes", community: dict | None = None) -> object:
    """Admin mode indicator bar — only visible for admin users.

    Shows pending count, quick links to admin sections.
    Returns empty string for non-admin users.
    Community-aware: scopes counts and links to active community.
    """
    if not user or not getattr(user, "is_admin", False):
        return NotStr("")

    prefix = community_url_prefix(community_slug or "rhodes")

    # Count pending items (scoped to community)
    pending_count = 0
    proposal_count = 0
    try:
        registry = load_registry()
        community_identity_ids = _get_community_identity_ids(community)
        for ident in registry.list_identities():
            if community_identity_ids is not None and ident.get("identity_id") not in community_identity_ids:
                continue
            state = ident.get("state", "")
            if state == "INBOX":
                pending_count += 1
            elif state == "PROPOSED":
                proposal_count += 1
    except Exception:
        pass

    return Div(
        Div(
            Span(
                "Admin Mode",
                cls="text-amber-400/80 text-[10px] sm:text-xs font-medium tracking-wide uppercase shrink-0",
            ),
            Div(
                A(
                    f"Pending ({pending_count})",
                    href=f"{prefix}/?section=to_review",
                    cls="text-slate-400 hover:text-white text-xs whitespace-nowrap transition-colors",
                ),
                Span("|", cls="text-slate-700 mx-1 sm:mx-2"),
                A(
                    f"Proposals ({proposal_count})",
                    href=f"{prefix}/?section=to_review",
                    cls="text-slate-400 hover:text-white text-xs whitespace-nowrap transition-colors",
                ),
                Span("|", cls="text-slate-700 mx-1 sm:mx-2"),
                A(
                    "Upload",
                    href=f"{prefix}/upload",
                    cls="text-slate-400 hover:text-white text-xs whitespace-nowrap transition-colors",
                ),
                cls="flex items-center overflow-x-auto scrollbar-hide w-full sm:w-auto",
            ),
            cls="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1 sm:gap-0",
        ),
        cls="bg-slate-950 border-b border-amber-400/20 py-1.5 sm:py-1",
        id="admin-bar",
        data_testid="admin-bar",
    )


def sidebar(
    counts: dict,
    current_section: str = "to_review",
    user: "User | None" = None,
    community_slug: str = "rhodes",
    community: dict | None = None,
) -> Aside:
    """
    Collapsible sidebar navigation for the Command Center.

    Supports expanded (full labels + counts) and collapsed (icons only) states.
    Default: collapsed on mobile (< 768px), expanded on desktop.
    Collapse state persisted in localStorage.

    Args:
        counts: Dict with keys: to_review, confirmed, skipped, rejected
        current_section: Currently active section
        user: Current user (None if anonymous)
        community_slug: Community slug for URL prefixing (default: 'rhodes')
        community: Optional community dict for display customization
    """
    # Determine community context
    is_rhodes = community_slug == "rhodes" or community_slug is None or community is None
    prefix = community_url_prefix(community_slug or "rhodes")
    header_name = community.get("name", "Rhodesli") if community else "Rhodesli"
    header_subtitle = community.get("landing_subtitle", "Heritage Archive") if community else "Heritage Archive"
    if not header_subtitle:
        header_subtitle = "Heritage Archive"

    def nav_item(href: str, icon: str, label: str, count: int, section_key: str, color: str):
        """Single navigation item with badge. Adapts to collapsed state."""
        is_active = current_section == section_key

        if is_active:
            container_cls = "bg-amber-900/40 text-amber-100 shadow-inner border border-amber-700/50 ui99-nav-active"
            badge_cls = "bg-amber-500 text-amber-950 shadow-sm"
        else:
            container_cls = (
                "text-slate-400 hover:bg-[#1a1714] hover:text-slate-200 border border-transparent ui99-nav-inactive"
            )
            badge_cls = f"bg-{color}-500/20 text-{color}-400"

        return A(
            # Icon always visible
            Span(icon, cls="sidebar-icon text-base flex-shrink-0 w-5 text-center"),
            # Label shown when expanded
            Span(label, cls="sidebar-label ml-2 whitespace-nowrap"),
            # Badge shown when expanded
            Span(str(count), cls=f"sidebar-label ml-auto px-2 py-0.5 text-xs font-bold rounded-full {badge_cls}"),
            href=href,
            title=f"{label} ({count})",
            onclick="closeSidebar()",
            cls=f"sidebar-nav-item flex items-center px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] {container_cls}",
        )

    # Workspace switcher (admin-only, between header and search)
    workspace_switcher = None
    if user and user.is_admin:
        workspace_switcher = Div(
            Div(
                Span(header_name, cls="sidebar-label text-xs text-slate-400 truncate"),
                A(
                    "Switch",
                    hx_get="/api/communities/switcher",
                    hx_target="#community-switcher-dropdown",
                    hx_swap="innerHTML",
                    cls="sidebar-label text-xs text-indigo-400 hover:text-indigo-300 cursor-pointer ml-auto flex-shrink-0",
                ),
                cls="flex items-center gap-2 px-3 py-1.5",
            ),
            Div(id="community-switcher-dropdown", cls="relative"),
            cls="border-b border-slate-700/50",
            data_testid="workspace-switcher",
        )
    elif not is_rhodes and community:
        # Non-admin: just show community name
        workspace_switcher = Div(
            Span(header_name, cls="sidebar-label text-xs text-slate-400 truncate px-3 py-1.5"),
            cls="border-b border-slate-700/50",
        )

    # Notifications bell (shared by admin and contributor)
    notifications_item = (
        A(
            Span("🔔", cls="sidebar-icon text-base flex-shrink-0 w-5 text-center"),
            Span("Notifications", cls="sidebar-label ml-2 whitespace-nowrap"),
            Span(
                id="notification-badge-sidebar",
                cls="sidebar-label ml-auto",
            ),
            href=f"{prefix}/notifications",
            title="Notifications",
            onclick="closeSidebar()",
            hx_get="/api/notifications/count?target=sidebar",
            hx_trigger="load, every 30s",
            hx_target="#notification-badge-sidebar",
            hx_swap="innerHTML",
            cls=f"sidebar-nav-item flex items-center px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] {'bg-slate-700 text-white' if current_section == 'notifications' else 'text-slate-300 hover:bg-slate-700/50'}",
        )
        if user
        else None
    )

    # Build review section — admins see full ML review, contributors see simplified view
    if user and user.is_admin:
        review_section = Div(
            P(
                "Review",
                cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1",
            ),
            nav_item(f"{prefix}/?section=to_review", "📥", "New Matches", counts["to_review"], "to_review", "amber"),
            nav_item(
                f"{prefix}/discoveries", "\u2728", "Discoveries", counts.get("discoveries", 0), "discoveries", "amber"
            ),
            nav_item(f"{prefix}/?section=skipped", "❓", "Help Identify", counts["skipped"], "skipped", "amber"),
            notifications_item,
            cls="mb-3",
        )
    elif user:
        # Contributor sidebar — focused on what THEY can do
        review_section = Div(
            P(
                "Contribute",
                cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1",
            ),
            nav_item(f"{prefix}/?section=skipped", "❓", "Help Identify", counts["skipped"], "skipped", "amber"),
            A(
                Span("📝", cls="sidebar-icon text-base flex-shrink-0 w-5 text-center"),
                Span("My Contributions", cls="sidebar-label ml-2 whitespace-nowrap"),
                href="/my-contributions",
                title="View your submissions",
                onclick="closeSidebar()",
                cls=f"sidebar-nav-item flex items-center px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] {'bg-slate-700 text-white' if current_section == 'my-contributions' else 'text-slate-300 hover:bg-slate-700/50'}",
            ),
            notifications_item,
            cls="mb-3",
        )
    else:
        # Anonymous — no review section
        review_section = None

    # Build browse section items — advanced items only for Rhodes
    browse_items = [
        nav_item(f"{prefix}/?section=photos", "📷", "Photos", counts.get("photos", 0), "photos", "slate"),
    ]
    if is_rhodes:
        browse_items.extend(
            [
                A(
                    Span("📂", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("Collections", cls="sidebar-label ml-2"),
                    href=f"{prefix}/collections",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
                ),
                A(
                    Span("🗺️", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("Map", cls="sidebar-label ml-2"),
                    href=f"{prefix}/map",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
                ),
                A(
                    Span("\U0001f4c5", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("Timeline", cls="sidebar-label ml-2"),
                    href=f"{prefix}/timeline",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
                ),
                A(
                    Span("\U0001f333", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("Tree", cls="sidebar-label ml-2"),
                    href=f"{prefix}/tree",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
                ),
                A(
                    Span("🔗", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("Connect", cls="sidebar-label ml-2"),
                    href=f"{prefix}/connect",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
                ),
            ]
        )
    # Global tools (always shown, no community prefix)
    browse_items.extend(
        [
            A(
                Span("🔍", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                Span("Compare", cls="sidebar-label ml-2"),
                href="/tools/compare",
                cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
            ),
            A(
                Span("📅", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                Span("Estimate", cls="sidebar-label ml-2"),
                href="/tools/estimate",
                cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
            ),
            A(
                Span("📖", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                Span("About", cls="sidebar-label ml-2"),
                href="/about",
                cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
            ),
        ]
    )

    # Admin section (all communities, admin-only)
    admin_section = (
        Div(
            P("Admin", cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1"),
            nav_item(
                f"{prefix}/admin/pending", "📋", "Uploads", counts.get("pending_uploads", 0), "pending_uploads", "amber"
            ),
            nav_item(
                f"{prefix}/admin/approvals",
                "✅",
                "Approvals",
                counts.get("pending_annotations", 0),
                "approvals",
                "emerald",
            ),
            nav_item(f"{prefix}/admin/proposals", "🔗", "Proposals", counts.get("proposals", 0), "proposals", "indigo"),
            A(
                Span("🔬", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                Span("Upload Review", cls="sidebar-label ml-2"),
                href=f"{prefix}/admin/upload-review",
                cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
            ),
            A(
                Span("🌳", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                Span("GEDCOM", cls="sidebar-label ml-2"),
                href=f"{prefix}/admin/gedcom",
                cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors",
            ),
            cls="mb-3",
        )
        if (user and user.is_admin)
        else None
    )

    header_name_cls = "sidebar-label text-xl font-bold text-amber-50 leading-tight font-display tracking-wide uppercase ui99-sidebar-title"
    header_subtitle_cls = "sidebar-label text-[10px] text-amber-500/60 mt-1 tracking-[0.2em] font-medium uppercase"
    sidebar_cls = "flex flex-col h-full bg-[#110e0c] border-r border-[#2a241e] text-slate-300 w-60 ui99-sidebar transition-all duration-300 z-50 fixed lg:static"
    header_border_cls = "border-b border-[#2a241e]"

    return Aside(
        # Header with collapse toggle
        Div(
            A(
                H1(header_name, cls=header_name_cls),
                P(header_subtitle, cls=header_subtitle_cls),
                href=f"{prefix}/",
                cls="flex-1 min-w-0 no-underline hover:opacity-80 transition-opacity",
            ),
            Button(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M15 19l-7-7 7-7"),
                    cls="sidebar-chevron w-4 h-4 transition-transform duration-200",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                onclick="toggleSidebarCollapse()",
                cls="sidebar-collapse-btn hidden lg:flex items-center justify-center p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 transition-colors",
                title="Toggle sidebar",
            ),
            cls=f"flex items-center px-3 py-3 {header_border_cls}",
        ),
        # Workspace switcher (admin or non-Rhodes communities)
        workspace_switcher,
        # Search input
        Div(
            Div(
                Svg(
                    Path(
                        stroke_linecap="round",
                        stroke_linejoin="round",
                        stroke_width="2",
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
                    ),
                    cls="w-4 h-4 text-slate-400 flex-shrink-0",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Input(
                    type="text",
                    name="q",
                    placeholder="Search names...",
                    autocomplete="off",
                    cls="sidebar-label bg-transparent border-none outline-none text-sm text-slate-200 placeholder-slate-500 w-full ml-2",
                    id="sidebar-search-input",
                    hx_get=f"{prefix}/api/search",
                    hx_trigger="keyup changed delay:300ms",
                    hx_target="#sidebar-search-results",
                    hx_swap="innerHTML",
                ),
                cls="flex items-center bg-slate-700/50 rounded-lg px-3 py-2",
            ),
            Div(id="sidebar-search-results", cls="sidebar-search-results"),
            cls="sidebar-search px-3 pt-3 pb-1 relative",
        ),
        # Upload Button (any logged-in user can upload; non-admin uploads go to moderation queue)
        Div(
            A(
                Svg(
                    Path(
                        stroke_linecap="round",
                        stroke_linejoin="round",
                        stroke_width="2",
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",
                    ),
                    cls="w-4 h-4 flex-shrink-0",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span("Upload", cls="sidebar-label ml-2"),
                href=f"{prefix}/upload",
                title="Upload photos",
                cls="flex items-center justify-center gap-0 w-full px-3 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors",
            )
            if user
            else None,
            cls="px-3 py-2",
        ),
        # Navigation
        Nav(
            # Review Section (Rhodes-only)
            review_section,
            # Library Section
            Div(
                P(
                    "Library",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1",
                ),
                nav_item(f"{prefix}/?section=confirmed", "✓", "People", counts["confirmed"], "confirmed", "green"),
                nav_item(f"{prefix}/?section=rejected", "🗑️", "Dismissed", counts["rejected"], "rejected", "gray")
                if is_rhodes
                else None,
                cls="mb-3",
            ),
            # Browse Section (photo-centric)
            Div(
                P(
                    "Browse",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1",
                ),
                *browse_items,
                cls="mb-3",
            ),
            # Admin Section (admin-only, Rhodes-only)
            admin_section,
            cls="flex-1 px-2 py-2 space-y-0 overflow-y-auto",
        ),
        # Footer with user info and stats
        Div(
            Div(
                Div(
                    Span(user.email, cls="sidebar-label text-xs text-slate-400 truncate"),
                    Span(" (admin)" if user.is_admin else "", cls="sidebar-label text-xs text-indigo-400"),
                    cls="flex items-center gap-1 min-w-0",
                ),
                A(
                    "Sign out",
                    href="/logout",
                    cls="sidebar-label text-xs text-slate-500 hover:text-slate-300 underline flex-shrink-0",
                ),
                cls="flex items-center justify-between mb-1 gap-2",
            )
            if user
            else Div(
                A("Sign in", href="/login", cls="sidebar-label text-xs text-slate-400 hover:text-slate-300 underline"),
                cls="mb-1",
            ),
            Div(
                f"{counts['confirmed']} of {counts['to_review'] + counts['confirmed'] + counts['skipped']} identified",
                cls="sidebar-label text-xs text-slate-500 font-data",
            ),
            Div(APP_VERSION, cls="sidebar-label text-xs text-slate-600 mt-0.5"),
            cls="px-3 py-2 border-t border-slate-700/50",
        ),
        # Close button for mobile
        Div(
            Button(
                Span("\u00d7", cls="text-2xl"),
                onclick="closeSidebar()",
                cls="text-slate-400 hover:text-white p-2 min-h-[44px] min-w-[44px] flex items-center justify-center",
            ),
            cls="absolute top-3 right-3 lg:hidden",
        ),
        id="sidebar",
        cls="sidebar-container fixed left-0 top-0 h-screen flex flex-col z-40 -translate-x-full lg:translate-x-0 transition-all duration-200 bg-slate-900 border-r border-amber-900/30 font-serif ui99-workstation-sidebar ui99-surface",
    )


def section_header(
    title: str,
    subtitle: str,
    view_mode: str = None,
    section: str = None,
    nav_prefix: str = "",
) -> Div:
    """
    Section header with optional Focus/Browse toggle.
    """
    header_content = [
        Div(
            H2(title, cls="text-3xl font-bold text-slate-100 font-display tracking-tight ui99-title"),
            P(subtitle, cls="text-sm text-slate-400 font-serif italic mt-1"),
        )
    ]
    _tab_active = "bg-amber-900/40 text-amber-100 shadow-inner shadow-black/50 font-medium border border-amber-700/50"
    _tab_inactive = "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-transparent"
    _tab_match_active = "bg-amber-600 text-white shadow-md shadow-amber-900/50 font-semibold border border-amber-500"

    if section == "to_review" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href=f"{nav_prefix}/?section=to_review&view=focus",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'focus' else _tab_inactive}",
            ),
            A(
                "View All",
                href=f"{nav_prefix}/?section=to_review&view=browse",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'browse' else _tab_inactive}",
            ),
            A(
                "Match",
                href=f"{nav_prefix}/?section=to_review&view=match",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_match_active if view_mode == 'match' else _tab_inactive}",
            ),
            cls="flex items-center gap-2",
        )
        header_content.append(toggle)
    elif section == "skipped" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href=f"{nav_prefix}/?section=skipped&view=focus",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'focus' else _tab_inactive}",
            ),
            A(
                "View All",
                href=f"{nav_prefix}/?section=skipped&view=browse",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'browse' else _tab_inactive}",
            ),
            cls="flex items-center gap-2",
        )
        header_content.append(toggle)

    return Div(*header_content, cls="section-header flex items-center justify-between mb-8")


def _proposal_banner(identity_id: str):
    """Show a proposal banner if ML found a match for this identity."""
    best = _get_best_proposal_for_identity(identity_id)
    if not best:
        return None
    confidence = best.get("confidence", "")
    target_name = best.get("target_identity_name", "Unknown")
    distance = best.get("distance", 0)
    from core.confidence import compute_confidence_pct

    confidence_pct = compute_confidence_pct(distance)

    color_cls = {
        "VERY HIGH": "bg-emerald-900/30 border-emerald-500/50 text-emerald-300",
        "HIGH": "bg-blue-900/30 border-blue-500/50 text-blue-300",
        "MODERATE": "bg-amber-900/30 border-amber-500/50 text-amber-300",
    }.get(confidence, "bg-slate-700/30 border-slate-500/50 text-slate-300")

    all_proposals = _get_proposals_for_identity(identity_id)
    count_text = f" (+{len(all_proposals) - 1} additional)" if len(all_proposals) > 1 else ""

    # User-friendly confidence labels (UX fix: avoid mixing system vocabulary with prose)
    confidence_label = _CONFIDENCE_LABEL.get(confidence, "Possible match")

    return Div(
        Span(confidence_label, cls="text-xs font-bold uppercase"),
        Span(" — ", cls="text-xs opacity-50"),
        Span(f"Likely {target_name}", cls="text-sm font-medium"),
        Span(f" ({confidence_pct}%)", cls="text-xs opacity-70"),
        Span(count_text, cls="text-xs opacity-50") if count_text else None,
        cls=f"mt-2 px-3 py-2 rounded-lg border text-sm {color_cls}",
    )


def _proposal_badge_inline(identity_id: str):
    """Inline badge showing ML match target name + confidence on browse cards.

    COMMUNITY-012: Shows "Matches [Name] (XX%)" directly, not just count.
    """
    proposals = _get_proposals_for_identity(identity_id)
    if not proposals:
        return None
    best = min(proposals, key=lambda p: p.get("distance", 999))
    confidence = best.get("confidence", "")
    target_name = best.get("target_identity_name", "?")
    # Compute confidence percentage
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(best.get("distance", 999))
    pct = conf.get("confidence_pct", 0)

    color_cls = {
        "VERY HIGH": "bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
        "HIGH": "bg-blue-600/30 text-blue-300 border-blue-500/30",
        "MODERATE": "bg-amber-600/30 text-amber-300 border-amber-500/30",
    }.get(confidence, "bg-slate-600/30 text-slate-300 border-slate-500/30")

    # Show full target name + percentage for actionable info
    short_name = target_name if len(target_name) <= 20 else target_name[:18] + "..."
    label = f"Matches {short_name} ({pct}%)" if pct else f"Matches {short_name}"

    return Span(
        label,
        cls=f"text-xs px-2 py-0.5 rounded border {color_cls}",
        title=f"ML match: {target_name} — {confidence} confidence, distance {best.get('distance', 0):.3f}",
    )


def identity_card_expanded(
    identity: dict, crop_files: set, is_admin: bool = True, triage_filter: str = "", nav_prefix: str = ""
) -> Div:
    """
    Expanded identity card for Focus Mode review.
    Shows larger thumbnail and prominent actions (admin only).

    Args:
        triage_filter: Active triage filter to preserve in action URLs
    """
    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or "Unidentified Person"
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get best-quality face for main thumbnail
    main_crop_url = None
    main_photo_id = None
    best_face_id = get_best_face_id(all_face_ids)
    if best_face_id:
        main_crop_url = resolve_face_image_url(best_face_id, crop_files)
        main_photo_id = get_photo_id_for_face(best_face_id)

    # Build face grid for additional faces (skip best since it's shown as main thumbnail)
    face_previews = []
    for face_entry in all_face_ids[:6]:  # Show up to 6, skip the best one
        if isinstance(face_entry, str):
            face_id = face_entry
        else:
            face_id = face_entry.get("face_id", "")
        if face_id == best_face_id:
            continue  # Already shown as main thumbnail
        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            # Get photo_id for this face to make it clickable
            face_photo_id = get_photo_id_for_face(face_id)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(
                            src=crop_url,
                            cls="w-16 h-16 rounded object-cover border border-slate-600 hover:border-indigo-400 hover:scale-110 transition-all",
                            alt=f"Face {face_id[:8]}",
                        ),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded transition-all",
                        hx_get=f"{nav_prefix}/photo/{face_photo_id}/partial?face={face_id}&identity_id={identity_id}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                        type="button",
                        title="Click to view photo",
                    )
                )
            else:
                face_previews.append(
                    Img(
                        src=crop_url,
                        cls="w-16 h-16 rounded object-cover border border-slate-600",
                        alt=f"Face {face_id[:8]}",
                    )
                )

    # Action buttons - only for admins
    if is_admin:
        base_confirm_url = (
            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
        )
        base_reject_url = (
            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
        )
        _filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        confirm_url = f"{base_confirm_url}?from_focus=true{_filter_suffix}"
        reject_url = f"{base_reject_url}?from_focus=true{_filter_suffix}"
        skip_url = f"{nav_prefix}/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"

        actions = Div(
            Button(
                "✓ Confirm",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                hx_post=confirm_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-confirm",
            ),
            Button(
                "⏸ Skip",
                cls="px-4 py-2 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600 transition-colors min-h-[44px]",
                hx_post=skip_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-skip",
            ),
            Button(
                "✗ Reject",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors min-h-[44px]",
                hx_post=reject_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-reject",
            ),
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors ml-auto min-h-[44px]",
                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                id="focus-btn-similar",
                **{
                    "hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"
                },
            ),
            Span(
                "Keyboard: C S R F",
                cls="text-xs text-slate-600 hidden sm:inline ml-2",
                title="C=Confirm, S=Skip, R=Reject, F=Find Similar",
            ),
            cls="flex flex-wrap items-center gap-3 mt-6",
        )
    else:
        actions = Div(
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors",
                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                **{
                    "hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"
                },
            ),
            Button(
                "I Know This Person",
                cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors",
                **{"_": f"on click toggle .hidden on #suggest-name-{identity_id}"},
                type="button",
            ),
            cls="flex items-center gap-3 mt-6",
        )

    return Div(
        Div(
            # Left: Main Face (clickable to open photo)
            Div(
                Button(
                    Div(
                        Img(src=main_crop_url or "", alt=name, cls="w-full h-full object-cover")
                        if main_crop_url
                        else Span("?", cls="text-6xl text-slate-500"),
                        cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                    ),
                    cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                    hx_get=f"{nav_prefix}/photo/{main_photo_id}/partial?face={best_face_id}&identity_id={identity_id}"
                    if main_photo_id
                    else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                    title="Click to view photo",
                )
                if main_photo_id
                else Div(
                    Img(src=main_crop_url, alt=name, cls="w-full h-full object-cover")
                    if main_crop_url
                    else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                ),
                cls="flex-shrink-0",
            ),
            # Right: Details + Actions
            Div(
                H3(name, cls="text-xl font-semibold text-white font-display"),
                Div(
                    P(
                        f"{face_count} face{'s' if face_count != 1 else ''}",
                        cls="text-sm text-slate-400",
                    ),
                    A(
                        "View Public Page",
                        href=f"{nav_prefix}/person/{identity_id}",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 ml-3",
                        data_testid="view-public-page",
                    ),
                    cls="flex items-center mt-1",
                ),
                # Proposal banner — shows ML match suggestion if one exists
                _proposal_banner(identity_id),
                # Face grid preview
                Div(*face_previews, cls="flex gap-2 mt-4 flex-wrap") if len(face_previews) > 1 else None,
                # Neighbors container — auto-load if proposals exist
                Div(
                    id=f"neighbors-{identity_id}",
                    cls="mt-4",
                    **(
                        {
                            "hx_get": f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                            "hx_trigger": "load",
                            "hx_swap": "innerHTML",
                        }
                        if identity_id in _get_identities_with_proposals()
                        else {}
                    ),
                ),
                actions,
                # Suggest Name form (hidden by default, shown via Hyperscript toggle)
                _suggest_name_form(identity_id, nav_prefix=nav_prefix),
                # Identity metadata (AN-012)
                _identity_metadata_display(identity, is_admin=is_admin),
                # Identity annotations (AN-013/AN-014)
                _identity_annotations_section(identity_id, is_admin=is_admin),
                # Notes section (loads via HTMX)
                Div(
                    Button(
                        "Notes",
                        cls="text-xs text-slate-400 hover:text-slate-300 underline",
                        hx_get=f"{nav_prefix}/api/identity/{identity_id}/notes",
                        hx_target=f"#notes-{identity_id}",
                        hx_swap="innerHTML",
                        type="button",
                    ),
                    Div(id=f"notes-{identity_id}", cls="mt-2"),
                    cls="mt-4 pt-3 border-t border-slate-700",
                ),
                cls="flex-1 min-w-0",
            ),
            cls="flex flex-col sm:flex-row gap-4 sm:gap-6",
        ),
        cls="identity-card-archival rounded-xl p-4 sm:p-6",
        id="focus-card",
    )


def _suggest_name_form(identity_id: str, nav_prefix: str = "") -> Div:
    """Hidden form for suggesting a name for an unidentified person."""
    return Div(
        H4("I Know This Person", cls="text-sm font-medium text-white mb-2"),
        Form(
            Input(type="hidden", name="target_type", value="identity"),
            Input(type="hidden", name="target_id", value=identity_id),
            Input(type="hidden", name="annotation_type", value="name_suggestion"),
            Input(
                name="value",
                placeholder="Enter name...",
                cls="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
                required=True,
            ),
            Select(
                Option("I'm certain", value="certain"),
                Option("Likely", value="likely", selected=True),
                Option("Just a guess", value="guess"),
                name="confidence",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white",
            ),
            Input(
                name="reason",
                placeholder="How do you know? (optional)",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
            ),
            Button(
                "Submit Suggestion",
                type="submit",
                cls="mt-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-500",
            ),
            hx_post=f"{nav_prefix}/api/annotations/submit",
            hx_swap="beforeend",
            hx_target="#toast-container",
            cls="space-y-0",
        ),
        cls="hidden mt-4 p-4 bg-slate-900/50 border border-indigo-500/30 rounded-lg",
        id=f"suggest-name-{identity_id}",
    )


def identity_card_mini(
    identity: dict, crop_files: set, clickable: bool = False, triage_filter: str = "", nav_prefix: str = ""
) -> Div:
    """
    Mini identity card for queue preview in Focus Mode.

    Args:
        identity: Identity dict
        crop_files: Set of available crop files
        clickable: If True, clicking loads this identity in focus mode
        triage_filter: Active filter to preserve in navigation links
    """
    identity_id = identity["identity_id"]

    # Get best-quality face for thumbnail
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_url = None
    best_fid = get_best_face_id(all_face_ids)
    if best_fid:
        crop_url = resolve_face_image_url(best_fid, crop_files)

    img_element = (
        Img(src=crop_url or "", cls="w-full h-full object-cover", loading="lazy")
        if crop_url
        else Span("?", cls="text-2xl text-slate-500")
    )

    if clickable:
        # Wrap in a link that loads this identity in focus mode (correct section)
        section = _section_for_state(identity.get("state", "INBOX"))
        filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        return A(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all",
            ),
            href=f"{nav_prefix}/?section={section}&view=focus&current={identity_id}{filter_suffix}",
            cls="w-24 flex-shrink-0 cursor-pointer",
            title="Click to review this identity",
        )
    else:
        return Div(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
            ),
            cls="w-24 flex-shrink-0",
        )


def render_to_review_section(
    to_review: list,
    crop_files: set,
    view_mode: str,
    counts: dict,
    current_id: str = None,
    is_admin: bool = True,
    sort_by: str = "newest",
    triage_filter: str = "",
    nav_prefix: str = "",
) -> Div:
    """Render the To Review section with Focus or Browse mode."""

    # Build triage bar (shown above all views)
    triage_bar = _build_triage_bar(to_review, view_mode, active_filter=triage_filter, nav_prefix=nav_prefix)

    # Apply triage filter if set
    if triage_filter in ("ready", "rediscovered", "unmatched"):
        to_review = [i for i in to_review if _triage_category(i) == triage_filter]

    # For focus mode, prioritize by actionability:
    # 1. Confirmed match promotions (one-click merge available)
    # 2. Faces with Very High proposals to confirmed identities
    # 3. Faces with new_face_match or group_discovery promotion
    # 4. Faces with High proposals
    # 5. Remaining inbox faces
    ids_with_proposals = _get_identities_with_proposals()

    def _focus_sort_key(x):
        iid = x.get("identity_id", "")
        has_proposal = iid in ids_with_proposals
        best = _get_best_proposal_for_identity(iid) if has_proposal else None
        has_promotion = x.get("promoted_from") is not None
        promotion_reason = x.get("promotion_reason", "")

        # Priority tiers (lower = higher priority):
        # 0: confirmed_match promotion (highest value)
        # 1: Very High confidence proposal
        # 2: new_face_match / group_discovery promotion
        # 3: High confidence proposal
        # 4: Other proposals (Moderate/Low)
        # 5: No proposals, no promotion (unmatched)
        if has_promotion and promotion_reason == "confirmed_match":
            tier = 0
        elif has_proposal and best and best.get("confidence") == "VERY HIGH":
            tier = 1
        elif has_promotion:
            tier = 2
        elif has_proposal and best and best.get("confidence") == "HIGH":
            tier = 3
        elif has_proposal:
            tier = 4
        else:
            tier = 5

        # Quality tiebreaker — clear faces first within same tier
        quality = _identity_quality_score(x)

        return (
            tier,
            best["distance"] if best else 999,
            -quality,
            -len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        )

    high_confidence = sorted(to_review, key=_focus_sort_key)[:10]

    # If a specific identity was requested, move it to the front
    if current_id and view_mode == "focus":
        # Find the requested identity
        current_identity = None
        remaining = []
        for item in high_confidence:
            if item["identity_id"] == current_id:
                current_identity = item
            else:
                remaining.append(item)
        # If not found in high_confidence, search full list
        if not current_identity:
            for item in to_review:
                if item["identity_id"] == current_id:
                    current_identity = item
                    break
        # Reorder with current at front
        if current_identity:
            high_confidence = [current_identity] + remaining[:9]

    if view_mode == "focus":
        if high_confidence:
            # Build Up Next carousel
            up_next = None
            if len(high_confidence) > 1:
                up_next = Div(
                    H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                    Div(
                        *[
                            identity_card_mini(
                                i, crop_files, clickable=True, triage_filter=triage_filter, nav_prefix=nav_prefix
                            )
                            for i in high_confidence[1:6]
                        ],
                        A(
                            f"+{len(high_confidence) - 6} more",
                            href=f"{nav_prefix}/?section=to_review&view=browse",
                            cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square hover:bg-slate-600 transition-colors cursor-pointer",
                        )
                        if len(high_confidence) > 6
                        else None,
                        cls="flex gap-3 overflow-x-auto pb-2",
                    ),
                    cls="mt-6",
                )
            # Show promotion banner above the expanded card if applicable
            banner = _promotion_banner(high_confidence[0])
            # Show one item expanded + queue preview, wrapped in focus-container for HTMX swap.
            # Keyboard shortcuts (C/S/R/F) are handled by the global keydown handler
            # in the page layout — no per-swap re-registration needed.
            content = Div(
                banner,
                identity_card_expanded(
                    high_confidence[0],
                    crop_files,
                    is_admin=is_admin,
                    triage_filter=triage_filter,
                    nav_prefix=nav_prefix,
                ),
                up_next,
                id="focus-container",
            )
        else:
            # Empty state
            content = Div(
                Div("🎉", cls="text-4xl mb-4"),
                H3("All caught up!", cls="text-lg font-medium text-white"),
                P("No items to review.", cls="text-slate-400 mt-1"),
                A(
                    "Upload more photos →",
                    href=f"{nav_prefix}/upload",
                    cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
                ),
                cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
            )
    elif view_mode == "match":
        # Match mode - gamified side-by-side pairing
        match_url = (
            f"{nav_prefix}/api/match/next-pair?filter={triage_filter}"
            if triage_filter
            else f"{nav_prefix}/api/match/next-pair"
        )
        content = Div(
            Div(
                Div(
                    Span("Matched: ", cls="text-slate-400"),
                    Span("0", id="match-counter", cls="text-white font-bold"),
                    Span(" pairs today", cls="text-slate-400"),
                    cls="text-sm",
                ),
                cls="flex items-center justify-between mb-4",
            ),
            Div(
                P("Loading next pair...", cls="text-slate-400 text-center py-8"),
                id="match-pair-container",
                hx_get=match_url,
                hx_trigger="load",
                hx_swap="innerHTML",
            ),
            Script("""
                // Match counter persistence via cookie
                function getMatchCount() {
                    var today = new Date().toISOString().slice(0, 10);
                    var stored = document.cookie.split(';').find(c => c.trim().startsWith('match_count_' + today + '='));
                    return stored ? parseInt(stored.split('=')[1]) : 0;
                }
                function incrementMatchCount() {
                    var today = new Date().toISOString().slice(0, 10);
                    var count = getMatchCount() + 1;
                    document.cookie = 'match_count_' + today + '=' + count + '; path=/; max-age=86400';
                    var el = document.getElementById('match-counter');
                    if (el) el.textContent = count;
                }
                // Initialize counter on load
                document.addEventListener('DOMContentLoaded', function() {
                    var el = document.getElementById('match-counter');
                    if (el) el.textContent = getMatchCount();
                });
            """),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-6",
        )
    else:
        # Browse mode - apply sorting
        if sort_by == "faces":
            to_review = sorted(
                to_review, key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])), reverse=True
            )
        elif sort_by == "name":
            to_review = sorted(to_review, key=lambda x: (x.get("name") or "").lower())
        # default: newest (already sorted by created_at desc above)

        display_limit = 150
        display_review = to_review[:display_limit]
        grid_items = []
        for identity in display_review:
            card = identity_card(
                identity,
                crop_files,
                lane_color="amber",
                show_actions=False,
                is_admin=is_admin,
                show_triage=True,
                nav_prefix=nav_prefix,
            )
            if card:
                grid_items.append(card)
                # Expansion panel for inline Find Similar
                _iid = identity["identity_id"]
                grid_items.append(Div(id=f"expand-{make_css_id(_iid)}", cls="expansion-panel"))
        cards = [c for c in grid_items if c]  # Filter None

        if cards:
            grid = Div(*cards, cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4")
            if len(to_review) > display_limit:
                content = Div(
                    Div(
                        f"Showing first {display_limit} review cards to keep the workstation responsive. "
                        f"Refine with triage filters, search, or sort to narrow the set.",
                        cls="text-sm text-slate-300 bg-slate-800/80 border border-slate-700 rounded-lg px-4 py-3",
                    ),
                    grid,
                    cls="space-y-4",
                )
            else:
                content = grid
        else:
            content = Div("All caught up! No new faces to review right now.", cls="text-center py-12 text-slate-400")

    # Build header with optional sort controls (browse mode only)
    header = section_header(
        "New Matches",
        f"{counts['to_review']} faces the AI matched — confirm or correct",
        view_mode=view_mode,
        section="to_review",
        nav_prefix=nav_prefix,
    )
    if view_mode == "browse":
        # Client-side search filter for admin browse grid (Session 83a)
        search_filter = (
            Div(
                Input(
                    type="text",
                    placeholder="Search by name or person number...",
                    cls="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-700 rounded-lg"
                    " text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                    id="card-search-input",
                ),
                Script("""
                document.addEventListener('input', function(e) {
                    if (e.target.id !== 'card-search-input') return;
                    var q = e.target.value.toLowerCase().trim();
                    var cards = document.querySelectorAll('.identity-card');
                    cards.forEach(function(card) {
                        var name = (card.getAttribute('data-name') || '').toLowerCase();
                        var id = card.id.replace('identity-', '');
                        var text = card.textContent.toLowerCase();
                        var match = !q || name.indexOf(q) !== -1 || id.indexOf(q) !== -1 || text.indexOf(q) !== -1;
                        card.style.display = match ? '' : 'none';
                        // Also hide the expansion panel after the card
                        var next = card.nextElementSibling;
                        if (next && next.classList.contains('expansion-panel')) {
                            next.style.display = match ? '' : 'none';
                        }
                    });
                });
            """),
                cls="mb-3",
            )
            if is_admin
            else None
        )
        return Div(
            Div(
                header,
                _sort_control("to_review", sort_by, view_mode=view_mode, nav_prefix=nav_prefix),
                cls="flex items-center justify-between flex-wrap gap-2 mb-6",
            ),
            search_filter,
            triage_bar,
            content,
            cls="space-y-4",
        )
    return Div(header, triage_bar, content, cls="space-y-6")


def _sort_control(
    section: str, current_sort: str, view_mode: str = None, nav_prefix: str = "", extra_query: str = ""
) -> Div:
    """Render sort control buttons for a section."""
    options = [
        ("name", "A-Z"),
        ("faces", "Faces"),
        ("newest", "Newest"),
    ]
    buttons = []
    view_param = f"&view={view_mode}" if view_mode else ""
    for value, label in options:
        is_active = current_sort == value
        cls = "px-2 py-1 text-xs font-medium rounded transition-colors "
        if is_active:
            cls += "bg-slate-600 text-white"
        else:
            cls += "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
        buttons.append(
            A(label, href=f"{nav_prefix}/?section={section}&sort_by={value}{view_param}{extra_query}", cls=cls)
        )
    return Div(Span("Sort:", cls="text-xs text-slate-500 mr-1"), *buttons, cls="flex items-center gap-1")


def render_confirmed_section(
    confirmed: list,
    crop_files: set,
    counts: dict,
    is_admin: bool = True,
    sort_by: str = "name",
    nav_prefix: str = "",
    confirmed_filter: str = "all",
) -> Div:
    """Render the Confirmed section with optional sorting."""
    linked_identities = _load_gedcom_face_links()
    total_confirmed = len(confirmed)

    def _has_tree_link(identity: dict) -> bool:
        identity_id = identity.get("identity_id", "")
        return bool(linked_identities.get(identity_id) or identity.get("gedcom_xref"))

    linked_total = sum(1 for identity in confirmed if _has_tree_link(identity))
    unlinked_total = max(total_confirmed - linked_total, 0)

    if confirmed_filter == "tree_unlinked":
        confirmed = [identity for identity in confirmed if not _has_tree_link(identity)]
    elif confirmed_filter == "tree_linked":
        confirmed = [identity for identity in confirmed if _has_tree_link(identity)]

    # Apply sorting
    if sort_by == "faces":
        confirmed = sorted(
            confirmed, key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])), reverse=True
        )
    elif sort_by == "newest":
        confirmed = sorted(confirmed, key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
    else:  # default: name (A-Z)
        confirmed = sorted(confirmed, key=lambda x: (x.get("name") or "").lower())

    grid_items = []
    for identity in confirmed:
        card = identity_card(
            identity, crop_files, lane_color="emerald", show_actions=False, is_admin=is_admin, nav_prefix=nav_prefix
        )
        if card:
            grid_items.append(card)
            _iid = identity["identity_id"]
            grid_items.append(Div(id=f"expand-{make_css_id(_iid)}", cls="expansion-panel"))

    if grid_items:
        content = Div(*grid_items, cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4")
    else:
        content = Div(
            "No confirmed identities yet. Browse the inbox to help identify faces.",
            cls="text-center py-12 text-slate-400",
        )

    if confirmed_filter == "tree_unlinked":
        subtitle = f"{len(confirmed)} of {counts['confirmed']} identified still need family tree links"
    elif confirmed_filter == "tree_linked":
        subtitle = f"{len(confirmed)} of {counts['confirmed']} identified already have family tree links"
    else:
        subtitle = (
            f"{counts['confirmed']} identified — {unlinked_total} still need family tree links"
            if is_admin
            else f"{counts['confirmed']} identified — click anyone to see all their photos"
        )

    filter_options = [
        ("all", f"All ({counts['confirmed']})"),
        ("tree_unlinked", f"Needs Tree ({unlinked_total})"),
        ("tree_linked", f"Linked ({linked_total})"),
    ]
    filter_buttons = []
    for value, label in filter_options:
        active = confirmed_filter == value
        filter_cls = "px-2 py-1 text-xs font-medium rounded transition-colors "
        if active:
            filter_cls += "bg-emerald-700/70 text-white"
        else:
            filter_cls += "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
        filter_buttons.append(
            A(
                label,
                href=f"{nav_prefix}/?section=confirmed&sort_by={sort_by}&confirmed_filter={value}",
                cls=filter_cls,
            )
        )

    return Div(
        Div(
            section_header("People", subtitle),
            Div(
                _sort_control(
                    "confirmed",
                    sort_by,
                    view_mode="browse",
                    nav_prefix=nav_prefix,
                    extra_query=f"&confirmed_filter={confirmed_filter}",
                ),
                Div(
                    Span("Filter:", cls="text-xs text-slate-500 mr-1"),
                    *filter_buttons,
                    cls="flex items-center gap-1",
                ),
                cls="flex flex-wrap items-center gap-2",
            ),
            cls="flex items-center justify-between flex-wrap gap-2 mb-6",
        ),
        P(
            "Use Needs Tree to sweep confirmed people who still need a family-tree link.",
            cls="text-xs text-slate-500",
            data_testid="confirmed-tree-helper",
        )
        if is_admin
        else None,
        content,
        cls="space-y-4",
    )


def render_skipped_section(
    skipped: list,
    crop_files: set,
    counts: dict,
    is_admin: bool = True,
    view_mode: str = "focus",
    current_id: str = None,
    nav_prefix: str = "",
) -> Div:
    """Render the Skipped section with Focus or Browse mode.

    Focus mode: guided one-at-a-time review with photo context and ML suggestions.
    Browse mode: grid of identity cards with lazy-loaded ML hints.
    """
    header = section_header(
        "Help Identify",
        f"{counts['skipped']} face{'s' if counts['skipped'] != 1 else ''} we need your help with \u2014 your family knowledge could be the key",
        view_mode=view_mode,
        section="skipped",
        nav_prefix=nav_prefix,
    )

    if view_mode == "focus":
        # Sort by actionability for focus mode
        sorted_skipped = _sort_skipped_by_actionability(skipped)

        # If a specific identity was requested, move it to the front
        if current_id:
            current_identity = None
            remaining = []
            for item in sorted_skipped:
                if item["identity_id"] == current_id:
                    current_identity = item
                else:
                    remaining.append(item)
            if not current_identity:
                for item in skipped:
                    if item["identity_id"] == current_id:
                        current_identity = item
                        break
            if current_identity:
                sorted_skipped = [current_identity] + remaining[:9]

        if sorted_skipped:
            # Build Up Next carousel
            up_next = None
            if len(sorted_skipped) > 1:
                up_next = Div(
                    H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                    Div(
                        *[
                            identity_card_mini(i, crop_files, clickable=True, nav_prefix=nav_prefix)
                            for i in sorted_skipped[1:6]
                        ],
                        A(
                            f"+{len(sorted_skipped) - 6} more",
                            href=f"{nav_prefix}/?section=to_review&view=browse",
                            cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square hover:bg-slate-600 transition-colors cursor-pointer",
                        )
                        if len(sorted_skipped) > 6
                        else None,
                        cls="flex gap-3 overflow-x-auto pb-2",
                    ),
                    cls="mt-6",
                )

            # Progress counter
            total = counts["skipped"]
            progress = _skipped_focus_progress(nav_prefix=nav_prefix)

            content = Div(
                progress,
                skipped_card_expanded(sorted_skipped[0], crop_files, is_admin=is_admin, nav_prefix=nav_prefix),
                up_next,
                id="skipped-focus-container",
                data_focus_mode="skipped",
            )
        else:
            content = Div(
                Div("🎉", cls="text-4xl mb-4"),
                H3("All caught up!", cls="text-lg font-medium text-white"),
                P("No faces need help right now.", cls="text-slate-400 mt-1"),
                A(
                    "← Back to Inbox",
                    href=f"{nav_prefix}/?section=to_review",
                    cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
                ),
                cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
                id="skipped-focus-container",
            )

        return Div(header, content, cls="space-y-6")

    # Browse mode (default fallback) — sort by actionability (best leads first)
    sorted_browse = _sort_skipped_by_actionability(skipped)
    ids_with_proposals = _get_identities_with_proposals()
    cards = []
    for identity in sorted_browse:
        card = identity_card(
            identity, crop_files, lane_color="stone", show_actions=False, is_admin=is_admin, nav_prefix=nav_prefix
        )
        if card:
            # Add lazy-loaded ML hint below each skipped card
            identity_id = identity["identity_id"]
            # Add actionability badge
            badge = _actionability_badge(identity_id, ids_with_proposals)
            hint = Div(
                id=f"skip-hint-{identity_id}",
                hx_get=f"{nav_prefix}/api/identity/{identity_id}/skip-hints",
                hx_trigger="revealed",
                hx_swap="innerHTML",
                cls="ml-4 mt-1 mb-3",
            )
            # Wrapper carries data-name so sidebar filter hides card+hint together
            raw_name = (identity.get("name") or "").lower()
            cards.append(Div(badge, card, hint, cls="identity-card-wrapper", data_name=raw_name))
            # Expansion panel OUTSIDE wrapper — direct grid child so grid-column: 1/-1 works
            cards.append(Div(id=f"expand-{make_css_id(identity_id)}", cls="expansion-panel"))

    if cards:
        content = Div(*cards, cls="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6")
    else:
        content = Div(
            "No unresolved faces right now. Check the inbox for new arrivals.", cls="text-center py-12 text-slate-400"
        )

    return Div(header, content, cls="space-y-6")


_skipped_neighbor_cache = None
_skipped_neighbor_cache_key = None


def _get_skipped_neighbor_distances(skipped: list) -> dict:
    """Get best-neighbor distances for all skipped identities.

    Uses proposals first, falls back to batch neighbor computation.
    Results are cached for the lifetime of the process (invalidated on data reload).
    """
    global _skipped_neighbor_cache, _skipped_neighbor_cache_key
    cache_key = len(skipped)  # Simple cache invalidation
    if _skipped_neighbor_cache is not None and _skipped_neighbor_cache_key == cache_key:
        return _skipped_neighbor_cache

    ids_with_proposals = _get_identities_with_proposals()
    result = {}

    # First, use proposals for any identities that have them
    for identity in skipped:
        iid = identity.get("identity_id", "")
        if iid in ids_with_proposals:
            best = _get_best_proposal_for_identity(iid)
            if best:
                target_name = best.get("target_name", best.get("name", ""))
                result[iid] = (best.get("distance", 999), best.get("confidence", "LOW"), target_name)

    # For identities without proposals, compute batch neighbors
    needs_computation = [i["identity_id"] for i in skipped if i["identity_id"] not in result]
    if needs_computation:
        try:
            from core.neighbors import batch_best_neighbor_distances

            registry = load_registry()
            face_data = get_face_data()
            batch_results = batch_best_neighbor_distances(needs_computation, registry, face_data)
            for iid, (dist, neighbor_id, neighbor_name) in batch_results.items():
                if dist < 999:
                    if dist < 0.80:
                        confidence = "VERY HIGH"
                    elif dist < 1.00:
                        confidence = "HIGH"
                    elif dist < 1.20:
                        confidence = "MODERATE"
                    else:
                        confidence = "LOW"
                    result[iid] = (dist, confidence, neighbor_name or "")
        except (ImportError, Exception) as e:
            print(f"[sort] Batch neighbor computation failed: {e}")

    _skipped_neighbor_cache = result
    _skipped_neighbor_cache_key = cache_key
    return result


def _identity_quality_score(identity: dict) -> float:
    """Get the best face quality score for an identity (0-100).

    Used for ordering — clear, high-quality faces should appear before
    blurry or small ones within the same confidence tier.
    """
    face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    if not face_ids:
        return 0.0
    best_id = get_best_face_id(face_ids)
    if best_id:
        return compute_face_quality_score(best_id)
    return 0.0


def _sort_skipped_by_actionability(skipped: list) -> list:
    """Sort skipped identities by actionability — best leads first.

    Priority tiers (lower = higher priority):
      0: Has VERY HIGH confidence match (near-certain)
      1: Has HIGH confidence match
      2: Has MODERATE or lower match
      3: No matches found

    Within each tier, sort by:
      1. Named match target bonus (named targets like "Rica Moussafer" before "Unidentified Person 310")
      2. Distance ascending (closest match first)
      3. Face quality descending (clear faces before blurry ones)

    Uses proposals when available, falls back to real-time neighbor computation.
    """
    neighbor_data = _get_skipped_neighbor_distances(skipped)

    def _actionability_key(x):
        iid = x.get("identity_id", "")
        match = neighbor_data.get(iid)

        if match:
            dist, confidence, target_name = match
            if confidence == "VERY HIGH":
                tier = 0
            elif confidence == "HIGH":
                tier = 1
            elif confidence == "MODERATE":
                tier = 2
            else:
                tier = 3

            # Named match bonus: 0 if target is named, 1 if unidentified
            is_unidentified = 1 if (not target_name or target_name.startswith("Unidentified")) else 0

            # Quality penalty (negative so higher quality sorts first)
            quality = _identity_quality_score(x)

            return (tier, is_unidentified, dist, -quality)
        else:
            quality = _identity_quality_score(x)
            return (4, 1, 999, -quality)

    return sorted(skipped, key=_actionability_key)


def _actionability_badge(identity_id: str, ids_with_proposals: set = None):
    """Return a visual badge for an identity's actionability level.

    Uses cached neighbor data from _get_skipped_neighbor_distances() when available,
    falls back to proposals. Returns None if the identity has no leads.
    """
    # Try cached neighbor distances first
    if _skipped_neighbor_cache and identity_id in _skipped_neighbor_cache:
        cached = _skipped_neighbor_cache[identity_id]
        confidence = cached[1]  # (distance, confidence, target_name)
    else:
        # Fallback to proposals
        if ids_with_proposals and identity_id not in ids_with_proposals:
            return None
        best = _get_best_proposal_for_identity(identity_id)
        if not best:
            return None
        confidence = best.get("confidence", "")

    if confidence in ("VERY HIGH", "HIGH"):
        return Div(
            Span("Strong lead", cls="text-xs font-bold text-emerald-300"),
            Span(" — ML found a likely match", cls="text-xs text-slate-400"),
            cls="px-3 py-1 bg-emerald-900/30 border border-emerald-500/30 rounded-lg mb-1",
        )
    elif confidence == "MODERATE":
        return Div(
            Span("Good lead", cls="text-xs font-bold text-amber-300"),
            Span(" — possible match found", cls="text-xs text-slate-400"),
            cls="px-3 py-1 bg-amber-900/30 border border-amber-500/30 rounded-lg mb-1",
        )
    return None


def _skipped_focus_progress(nav_prefix: str = "") -> Div:
    """Build progress counter for skipped focus mode.

    Uses client-side cookie to persist count across HTMX swaps.
    """
    return Div(
        Div(
            Span("Reviewed: ", cls="text-slate-400"),
            Span("0", id="skipped-reviewed-count", cls="text-white font-bold"),
            Span(" this session", cls="text-slate-400"),
            cls="text-sm",
        ),
        A(
            "← Exit Focus Mode",
            href=f"{nav_prefix}/?section=skipped&view=browse",
            cls="text-sm text-slate-400 hover:text-white transition-colors",
        ),
        Script("""
            (function() {
                var key = 'skipped_focus_count';
                function getCount() {
                    var stored = document.cookie.split(';').find(function(c) { return c.trim().startsWith(key + '='); });
                    return stored ? parseInt(stored.split('=')[1]) : 0;
                }
                function setCount(n) {
                    document.cookie = key + '=' + n + '; path=/; max-age=86400';
                    var el = document.getElementById('skipped-reviewed-count');
                    if (el) el.textContent = n;
                }
                // Initialize on load
                var el = document.getElementById('skipped-reviewed-count');
                if (el) el.textContent = getCount();
                // Increment when the focus container is swapped (action was taken)
                document.body.addEventListener('htmx:afterSwap', function(evt) {
                    if (evt.detail.target && evt.detail.target.id === 'skipped-focus-container') {
                        setCount(getCount() + 1);
                    }
                });
            })();
        """),
        cls="flex items-center justify-between mb-4",
        id="skipped-focus-progress",
    )


def skipped_card_expanded(identity: dict, crop_files: set, is_admin: bool = True, nav_prefix: str = "") -> Div:
    """
    Expanded identity card for Needs Help Focus Mode.

    Shows the face prominently, the best ML suggestion side-by-side,
    photo context (full photo with collection info), and action buttons:
    - Same Person (Y): merge with top suggestion
    - Not Same (N): reject top suggestion
    - I Know Them (Enter): name input + confirm
    - Skip (S): advance without action
    """
    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or "Unidentified Person"
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get best-quality face for main display
    main_crop_url = None
    main_photo_id = None
    main_face_id = get_best_face_id(all_face_ids)
    if main_face_id:
        main_crop_url = resolve_face_image_url(main_face_id, crop_files)
        main_photo_id = get_photo_id_for_face(main_face_id)

    # Get top ML suggestions for side-by-side display + strip (compute first so we know best match)
    suggestion_el, other_matches_strip, best_match_id = _build_skipped_suggestion_with_strip(
        identity_id, crop_files, nav_prefix=nav_prefix
    )

    # Get photo context (collection, other identified people) — includes best match photo
    photo_context_el = _build_skipped_photo_context(
        main_face_id, main_photo_id, identity_id, best_match_id=best_match_id, nav_prefix=nav_prefix
    )

    # Action buttons
    if is_admin:
        actions = _build_skipped_focus_actions(identity_id, state, nav_prefix=nav_prefix)
    else:
        actions = Div(
            Button(
                "I Know This Person",
                cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors min-h-[44px]",
                **{"_": f"on click toggle .hidden on #skipped-name-form-{identity_id}"},
                type="button",
            ),
            cls="flex items-center gap-3 mt-6",
        )

    # Inline name form (hidden by default)
    name_form = Div(
        Form(
            Input(
                type="text",
                name="name",
                placeholder="Type their name...",
                cls="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent min-h-[44px]",
                autofocus=True,
            ),
            Button(
                "Confirm Identity",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                type="submit",
            ),
            Button(
                "Cancel",
                cls="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors min-h-[44px]",
                type="button",
                **{"_": f"on click add .hidden to #skipped-name-form-{identity_id}"},
            ),
            hx_post=f"{nav_prefix}/api/skipped/{identity_id}/name-and-confirm",
            hx_target="#skipped-focus-container",
            hx_swap="outerHTML",
            cls="flex gap-3 items-center",
        ),
        cls="mt-4 hidden",
        id=f"skipped-name-form-{identity_id}",
    )

    # Additional faces preview
    face_previews = []
    for face_entry in all_face_ids[1:4]:
        fid = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")
        crop_url = resolve_face_image_url(fid, crop_files)
        if crop_url:
            face_photo_id = get_photo_id_for_face(fid)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(
                            src=crop_url,
                            cls="w-20 h-20 rounded-lg object-cover border border-slate-600 hover:border-indigo-400 transition-colors",
                            alt="Face",
                        ),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                        hx_get=f"{nav_prefix}/photo/{face_photo_id}/partial?face={fid}&identity_id={identity_id}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                        type="button",
                        title="Click to view photo",
                    )
                )

    return Div(
        # Top row: This Person + Best Match side by side (large faces ~300px)
        Div(
            # Left: This Person
            Div(
                Div("Who is this?", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
                Button(
                    Div(
                        Img(src=main_crop_url or "", alt=name, cls="w-full h-full object-cover")
                        if main_crop_url
                        else Span("?", cls="text-6xl text-slate-500"),
                        cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                    ),
                    cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                    hx_get=f"{nav_prefix}/photo/{main_photo_id}/partial?face={main_face_id}&identity_id={identity_id}"
                    if main_photo_id
                    else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                    title="Click to view full photo",
                )
                if main_photo_id
                else Div(
                    Img(src=main_crop_url, alt=name, cls="w-full h-full object-cover")
                    if main_crop_url
                    else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                ),
                Div(
                    P(name, cls="text-lg font-semibold text-white mt-2"),
                    P(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-400"),
                ),
                Div(
                    A(
                        "View Photo",
                        href="#",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 inline-block",
                        hx_get=f"{nav_prefix}/photo/{main_photo_id}/partial?face={main_face_id}&identity_id={identity_id}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                    ),
                    share_button(f"{nav_prefix}/photo/{main_photo_id}", style="link", label="Share Photo"),
                    share_button(
                        url=f"{nav_prefix}/identify/{identity_id}/match/{best_match_id}",
                        style="link",
                        label="Share This Match",
                        title="Are these the same person?",
                        text=f"Help identify: {name}",
                    )
                    if best_match_id
                    else None,
                    cls="flex items-center gap-3 mt-1",
                )
                if main_photo_id
                else None,
                # Additional faces
                Div(*face_previews, cls="flex gap-2 mt-3") if face_previews else None,
                cls="flex-1 flex flex-col items-center sm:items-start",
            ),
            # Right: Best Match suggestion
            suggestion_el,
            cls="flex flex-col sm:flex-row gap-8 items-start justify-center",
        ),
        # Other matches strip (horizontal scroll)
        other_matches_strip,
        # Photo context
        photo_context_el,
        # Neighbors container — always auto-loads ML suggestions
        Div(
            id=f"neighbors-{identity_id}",
            cls="mt-4",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true&focus_section=skipped",
            hx_trigger="load",
            hx_swap="innerHTML",
        ),
        # Name form (inline, hidden by default)
        name_form,
        # Sticky action bar at bottom
        actions,
        cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-4 sm:p-6 pb-24 sm:pb-6",
        id="skipped-focus-card",
        **{"data-focus-mode": "skipped"},
    )


def _build_skipped_photo_context(
    face_id: str, photo_id: str, identity_id: str, best_match_id: str = None, nav_prefix: str = ""
):
    """Build photo context panel showing collection info and co-identified faces.

    Shows both the "Who is this?" source photo and the Best Match source photo
    side by side when a best match exists.
    """
    if not photo_id:
        return None

    _build_caches()
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None

    collection = photo.get("collection") or photo.get("source") or ""
    photo_url = storage.get_photo_url(photo.get("path") or photo.get("filename") or "")

    # Find other identified faces in this photo
    registry = load_registry()
    other_people = []
    for fid in photo.get("face_ids", []):
        if fid == face_id:
            continue
        # Look up which identity this face belongs to
        for state_name in ["CONFIRMED", "PROPOSED", "INBOX", "SKIPPED"]:
            try:
                state_enum = IdentityState[state_name]
                identities = registry.list_identities(state=state_enum)
                for ident in identities:
                    if ident["identity_id"] == identity_id:
                        continue
                    all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
                    face_strs = [f if isinstance(f, str) else f.get("face_id", "") for f in all_faces]
                    if fid in face_strs:
                        ident_name = ensure_utf8_display(ident.get("name") or "")
                        if ident_name and not ident_name.startswith("Unidentified"):
                            other_people.append(ident_name)
                        break
            except (KeyError, AttributeError):
                continue

    other_people = list(set(other_people))[:5]  # Deduplicate, limit

    # Build "Who is this?" photo card
    who_context_items = []
    if collection:
        who_context_items.append(Span(collection, cls="text-xs text-slate-400 leading-snug"))
    if other_people:
        who_context_items.append(Span(f"Also: {', '.join(other_people)}", cls="text-xs text-slate-300 truncate"))

    who_card = Div(
        Div("Who is this?", cls="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1"),
        Button(
            Img(
                src=photo_url,
                cls="w-full h-20 object-cover rounded border border-slate-600 hover:border-indigo-400 transition-colors",
                alt="Source photo",
            ),
            cls="p-0 bg-transparent cursor-pointer w-full",
            hx_get=f"{nav_prefix}/photo/{photo_id}/partial?face={face_id}&identity_id={identity_id}",
            hx_target="#photo-modal-content",
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
            title="View full photo",
        ),
        Div(*who_context_items, cls="flex flex-col gap-0.5 mt-1") if who_context_items else None,
        A(
            "View Photo Page",
            href=f"{nav_prefix}/photo/{photo_id}",
            cls="text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 inline-block",
        ),
        cls="flex-1 min-w-0",
    )

    # Build Best Match photo card (if we have a best match)
    match_card = None
    if best_match_id:
        try:
            match_identity = registry.get_identity(best_match_id)
            match_faces = match_identity.get("anchor_ids", []) + match_identity.get("candidate_ids", [])
            match_face_id = get_best_face_id(match_faces)
            if match_face_id:
                match_photo_id = get_photo_id_for_face(match_face_id)
                if match_photo_id:
                    match_photo = _photo_cache.get(match_photo_id)
                    if match_photo:
                        match_collection = match_photo.get("collection") or match_photo.get("source") or ""
                        match_photo_url = storage.get_photo_url(
                            match_photo.get("path") or match_photo.get("filename") or ""
                        )
                        match_name = ensure_utf8_display(match_identity.get("name") or "Unknown")

                        match_context_items = []
                        if match_collection:
                            match_context_items.append(
                                Span(match_collection, cls="text-xs text-slate-400 leading-snug")
                            )
                        match_context_items.append(Span(match_name, cls="text-xs text-slate-300 truncate"))

                        match_card = Div(
                            Div(
                                "Best Match", cls="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1"
                            ),
                            Button(
                                Img(
                                    src=match_photo_url,
                                    cls="w-full h-20 object-cover rounded border border-slate-600 hover:border-indigo-400 transition-colors",
                                    alt=f"Source photo for {match_name}",
                                ),
                                cls="p-0 bg-transparent cursor-pointer w-full",
                                hx_get=f"{nav_prefix}/photo/{match_photo_id}/partial?face={match_face_id}&identity_id={best_match_id}",
                                hx_target="#photo-modal-content",
                                **{"_": "on click remove .hidden from #photo-modal"},
                                type="button",
                                title=f"View photo of {match_name}",
                            ),
                            Div(*match_context_items, cls="flex flex-col gap-0.5 mt-1")
                            if match_context_items
                            else None,
                            A(
                                "View Photo Page",
                                href=f"{nav_prefix}/photo/{match_photo_id}",
                                cls="text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 inline-block",
                            ),
                            cls="flex-1 min-w-0",
                        )
        except (KeyError, Exception):
            pass

    # Share button shares the source photo page, not the match comparison
    share_el = share_button(
        url=f"{nav_prefix}/photo/{photo_id}",
        style="link",
        label="Share",
        title="Check out this photo",
        text="From the Rhodesli archive",
    )

    return Div(
        Div(
            Span("Photo Context", cls="text-xs font-medium text-slate-400 uppercase tracking-wide"),
            share_el,
            cls="flex items-center justify-between mb-2",
        ),
        Div(who_card, match_card, cls="flex gap-3") if match_card else Div(who_card, cls="flex gap-3"),
        cls="mt-4 bg-slate-700/30 rounded-lg p-3 border border-slate-700/50",
    )


def _compute_best_neighbor(identity_id: str):
    """Compute best neighbor for an identity using real-time embedding distance.

    Returns a dict with keys matching proposal format:
      target_identity_id, target_identity_name, distance, confidence
    or None if no neighbor found.
    """
    try:
        from core.neighbors import find_nearest_neighbors

        registry = load_registry()
        photo_registry = load_photo_registry()
        face_data = get_face_data()
        neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=1)
        if not neighbors:
            return None
        n = neighbors[0]
        dist = n.get("distance", 999)
        # Map distance to confidence tier (same thresholds as clustering)
        if dist < 0.80:
            confidence = "VERY HIGH"
        elif dist < 1.00:
            confidence = "HIGH"
        elif dist < 1.20:
            confidence = "MODERATE"
        else:
            confidence = "LOW"
        return {
            "target_identity_id": n["identity_id"],
            "target_identity_name": n.get("name", "Unknown"),
            "distance": dist,
            "confidence": confidence,
        }
    except (ImportError, Exception):
        return None


def _compute_top_neighbors(identity_id: str, limit: int = 5):
    """Compute top N neighbors for an identity using real-time embedding distance.

    Returns a list of dicts with keys: target_identity_id, target_identity_name, distance, confidence.
    """
    try:
        from core.neighbors import find_nearest_neighbors

        registry = load_registry()
        photo_registry = load_photo_registry()
        face_data = get_face_data()
        neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=limit)
        results = []
        for n in neighbors:
            dist = n.get("distance", 999)
            if dist < 0.80:
                confidence = "VERY HIGH"
            elif dist < 1.00:
                confidence = "HIGH"
            elif dist < 1.20:
                confidence = "MODERATE"
            else:
                confidence = "LOW"
            results.append(
                {
                    "target_identity_id": n["identity_id"],
                    "target_identity_name": n.get("name", "Unknown"),
                    "distance": dist,
                    "confidence": confidence,
                }
            )
        return results
    except (ImportError, Exception):
        return []


def _get_best_match_for_identity(identity_id: str):
    """Get best match: first from proposals, then from real-time neighbors."""
    best = _get_best_proposal_for_identity(identity_id)
    if best:
        return best
    return _compute_best_neighbor(identity_id)


def _build_skipped_suggestion(identity_id: str, crop_files: set, nav_prefix: str = ""):
    """Build the 'Best Match' side-by-side panel for a skipped identity.

    Returns a single element (for backward compat with any callers).
    """
    el, _, _ = _build_skipped_suggestion_with_strip(identity_id, crop_files, nav_prefix=nav_prefix)
    return el


def _resolve_match_crop(target_id: str, crop_files: set):
    """Resolve the first available face crop URL for an identity."""
    try:
        registry = load_registry()
        target_identity = registry.get_identity(target_id)
        target_faces = target_identity.get("anchor_ids", []) + target_identity.get("candidate_ids", [])
        for f in target_faces:
            fid = f if isinstance(f, str) else f.get("face_id", "")
            url = resolve_face_image_url(fid, crop_files)
            if url:
                return url
    except (KeyError, Exception):
        pass
    return None


def _confidence_tier(distance: float) -> str:
    """Map embedding distance to confidence tier. Uses unified scoring (AD-200)."""
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(distance)
    # Map unified short_label → legacy tier names for backward compat
    _label_to_tier = {"Very High": "VERY HIGH", "High": "HIGH", "Moderate": "MODERATE", "Low": "LOW", "Very Low": "LOW"}
    return _label_to_tier.get(conf["short_label"], "LOW")


_CONFIDENCE_RING = {"VERY HIGH": "ring-emerald-400", "HIGH": "ring-blue-400", "MODERATE": "ring-amber-400"}
_CONFIDENCE_COLOR = {"VERY HIGH": "text-emerald-300", "HIGH": "text-blue-300", "MODERATE": "text-amber-300"}
_CONFIDENCE_LABEL = {
    "VERY HIGH": "Strong match",
    "HIGH": "Good match",
    "MODERATE": "Possible match",
    "LOW": "Weak match",
}

# =============================================================================
# DISCOVERY DETECTION — High-confidence matches to CONFIRMED identities
# =============================================================================

_discovery_cache = None
_discovery_cache_key = None

DISCOVERY_DISTANCE_THRESHOLD = 1.30  # Raised from 1.05 to match Tier 2 ceiling (Session 79, Nolan approved)


def _compute_discoveries(registry=None, community_identity_ids=None) -> list:
    """Find INBOX/PROPOSED identities with high-confidence matches to CONFIRMED identities.

    A "discovery" is an unreviewed face that has a nearest CONFIRMED neighbor
    with distance < DISCOVERY_DISTANCE_THRESHOLD. These are high-priority
    items because an admin can resolve them with a single click.

    Returns a list of dicts:
        [{source_id, source_name, target_id, target_name, distance, confidence}, ...]
    sorted by distance (best matches first).

    This is a read-only computation — no data mutation.
    """
    global _discovery_cache, _discovery_cache_key
    if registry is None:
        registry = load_registry()

    # Cache key: count of inbox + proposed + confirmed + community scope
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=IdentityState.CONFIRMED)
    community_key = frozenset(community_identity_ids) if community_identity_ids is not None else None
    cache_key = (len(inbox), len(proposed), len(confirmed_list), community_key)

    if _discovery_cache is not None and _discovery_cache_key == cache_key:
        return _discovery_cache

    unreviewed = inbox + proposed

    # Filter UNREVIEWED to community scope BEFORE expensive computation (performance critical)
    # Keep confirmed_list GLOBAL — cross-community matching is essential
    # (e.g., Fox Family INBOX faces should match Rhodes CONFIRMED identities like Betty Capeluto)
    if community_identity_ids is not None:
        unreviewed = [u for u in unreviewed if u["identity_id"] in community_identity_ids]
    if not unreviewed or not confirmed_list:
        _discovery_cache = []
        _discovery_cache_key = cache_key
        return _discovery_cache

    # Build confirmed identity set for filtering
    confirmed_ids = {c["identity_id"] for c in confirmed_list}

    discoveries = []

    # Proposal-only discovery: O(p) where p = number of proposals
    # No batch_best_neighbor_distances fallback — identities without proposals
    # simply don't appear in discoveries. Run clustering pipeline to generate proposals.
    ids_with_proposals = _get_identities_with_proposals()
    unreviewed_ids = {u["identity_id"] for u in unreviewed}

    for identity in unreviewed:
        iid = identity["identity_id"]
        if iid not in ids_with_proposals:
            continue
        best = _get_best_proposal_for_identity(iid)
        if best:
            target_id = best.get("target_identity_id", best.get("target_id", ""))
            if target_id in confirmed_ids and best.get("distance", 999) < DISCOVERY_DISTANCE_THRESHOLD:
                dist = best["distance"]
                discoveries.append(
                    {
                        "source_id": iid,
                        "source_name": ensure_utf8_display(identity.get("name", "")),
                        "target_id": target_id,
                        "target_name": ensure_utf8_display(best.get("target_name", best.get("name", ""))),
                        "distance": dist,
                        "confidence": _confidence_tier(dist),
                    }
                )

    # Batch-compute co-occurrence for all discoveries (cheaper than per-card)
    try:
        photo_reg = load_photo_registry()
        for disc in discoveries:
            disc["co_occurrence"] = _compute_co_occurrence(disc["source_id"], disc["target_id"], registry, photo_reg)
    except Exception:
        pass

    discoveries.sort(key=lambda d: d["distance"])
    _discovery_cache = discoveries
    _discovery_cache_key = cache_key

    # Community filtering already applied to unreviewed+confirmed lists before computation
    return discoveries


def _count_discoveries(registry=None, community_identity_ids=None) -> int:
    """Count high-confidence matches to CONFIRMED identities.

    Lightweight wrapper around _compute_discoveries for sidebar badge.
    When community_identity_ids is provided, only counts discoveries where
    the source or target identity is in the community set.
    """
    discoveries = _compute_discoveries(registry, community_identity_ids=community_identity_ids)
    return len(discoveries)


def _invalidate_discovery_cache():
    """Invalidate the discovery cache (call after merge/reject actions)."""
    global _discovery_cache, _discovery_cache_key
    _discovery_cache = None
    _discovery_cache_key = None


def _load_discovery_log() -> dict:
    """Load discovery_log.json. Returns {"schema_version": 1, "entries": []}."""
    log_path = Path("data/discovery_log.json")
    if not log_path.exists():
        return {"schema_version": 1, "entries": []}
    try:
        with open(log_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {"schema_version": 1, "entries": []}


def _get_pending_discovery_entries() -> tuple:
    """Get pending discovery log entries split by tier.

    Returns:
        (tier_1_entries, tier_2_entries) — only entries without a user_decision.
    """
    log = _load_discovery_log()
    tier_1 = []
    tier_2 = []
    for entry in log.get("entries", []):
        if entry.get("user_decision") is not None:
            continue  # Already acted on
        if entry.get("tier") == 1:
            tier_1.append(entry)
        elif entry.get("tier") == 2:
            tier_2.append(entry)
    return tier_1, tier_2


def _update_discovery_log_entry(face_id: str, target_identity_id: str, user_decision: str):
    """Update a discovery log entry with the user's decision."""
    log_path = Path("data/discovery_log.json")
    if not log_path.exists():
        return
    try:
        with open(log_path) as f:
            data = json.load(f)
        for entry in data.get("entries", []):
            if (
                entry.get("face_id") == face_id
                and entry.get("target_identity_id") == target_identity_id
                and entry.get("user_decision") is None
            ):
                entry["user_decision"] = user_decision
                entry["user_decision_timestamp"] = datetime.now(timezone.utc).isoformat()
                break
        tmp = str(log_path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(log_path))
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"[discovery_log] Failed to update: {e}")


def _build_skipped_suggestion_with_strip(identity_id: str, crop_files: set, nav_prefix: str = ""):
    """Build 'Best Match' panel + horizontal strip of other matches.

    Returns (suggestion_el, other_matches_strip_el, best_match_id).
    """
    # Fetch up to 5 neighbors
    top_matches = _compute_top_neighbors(identity_id, limit=5)

    # Also check proposals
    best_proposal = _get_best_proposal_for_identity(identity_id)
    if best_proposal:
        # Merge proposal into top of list if not already present
        proposal_id = best_proposal.get("target_identity_id", "")
        if not any(m.get("target_identity_id") == proposal_id for m in top_matches):
            top_matches.insert(0, best_proposal)

    if not top_matches:
        no_match_el = Div(
            Div("Best Match", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
            P("No ML suggestions yet", cls="text-sm text-slate-500 italic"),
            P("Try 'I Know Them' to name this person", cls="text-xs text-slate-500 mt-1"),
            cls="flex-1 flex flex-col items-center sm:items-start",
        )
        return no_match_el, None, None

    # Best match (primary comparison)
    best = top_matches[0]
    target_id = best.get("target_identity_id", "")
    target_name = ensure_utf8_display(best.get("target_identity_name", "Unknown"))
    confidence = best.get("confidence", "")
    ring_cls = _CONFIDENCE_RING.get(confidence, "ring-slate-500")
    color_cls = _CONFIDENCE_COLOR.get(confidence, "text-slate-300")
    confidence_label = _CONFIDENCE_LABEL.get(confidence, "Match")
    suggestion_crop_url = _resolve_match_crop(target_id, crop_files)

    # Resolve best match's photo ID for View Photo / share links
    match_photo_id = None
    match_face_id = None
    target_identity = None
    try:
        registry = load_registry()
        target_identity = registry.get_identity(target_id)
        target_faces = target_identity.get("anchor_ids", []) + target_identity.get("candidate_ids", [])
        match_face_id = get_best_face_id(target_faces)
        if match_face_id:
            match_photo_id = get_photo_id_for_face(match_face_id)
    except (KeyError, Exception):
        pass

    # Build links for best match (mirror "Who is this?" links)
    match_links = []
    if match_photo_id:
        match_links.append(
            A(
                "View Photo",
                href="#",
                cls="text-xs text-indigo-400 hover:text-indigo-300 inline-block",
                hx_get=f"{nav_prefix}/photo/{match_photo_id}/partial?face={match_face_id}&identity_id={target_id}",
                hx_target="#photo-modal-content",
                **{"_": "on click remove .hidden from #photo-modal"},
            )
        )
    # Profile link
    target_state = target_identity.get("state", "") if target_identity else ""
    if target_state == "CONFIRMED":
        match_links.append(
            A(
                "View Profile",
                href=f"{nav_prefix}/person/{target_id}",
                cls="text-xs text-indigo-400 hover:text-indigo-300 inline-block",
            )
        )
    else:
        match_links.append(
            A(
                "Help Identify",
                href=f"{nav_prefix}/identify/{target_id}",
                cls="text-xs text-indigo-400 hover:text-indigo-300 inline-block",
            )
        )

    suggestion_el = Div(
        Div("Best Match", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
        Div(
            Img(src=suggestion_crop_url or "", alt=target_name, cls="w-full h-full object-cover")
            if suggestion_crop_url
            else Span("?", cls="text-4xl text-slate-500"),
            cls=f"w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center ring-3 {ring_cls}",
        ),
        Div(
            P(target_name, cls="text-lg font-semibold text-white mt-2"),
            P(Span(confidence_label, cls=f"font-bold {color_cls}"), cls="text-sm mt-1"),
        ),
        Div(*match_links, cls="flex items-center gap-3 mt-1") if match_links else None,
        cls="flex-1 flex flex-col items-center sm:items-start",
    )

    # Other matches strip (2nd through 5th)
    other_matches_strip = None
    other_matches = top_matches[1:]
    if other_matches:
        strip_items = []
        for match in other_matches:
            m_id = match.get("target_identity_id", "")
            m_name = ensure_utf8_display(match.get("target_identity_name", "Unknown"))
            m_conf = match.get("confidence", "LOW")
            m_ring = _CONFIDENCE_RING.get(m_conf, "ring-slate-500")
            m_crop = _resolve_match_crop(m_id, crop_files)
            m_label = _CONFIDENCE_LABEL.get(m_conf, "Match")
            strip_items.append(
                Div(
                    Div(
                        Img(src=m_crop or "", alt=m_name, cls="w-full h-full object-cover")
                        if m_crop
                        else Span("?", cls="text-lg text-slate-500"),
                        cls=f"w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center ring-2 {m_ring} hover:scale-105 transition-transform",
                    ),
                    P(
                        m_name[:20] + ("..." if len(m_name) > 20 else ""),
                        cls="text-xs text-slate-300 mt-1 text-center truncate max-w-[80px]",
                    ),
                    P(m_label, cls=f"text-[10px] {_CONFIDENCE_COLOR.get(m_conf, 'text-slate-400')} text-center"),
                    cls="flex flex-col items-center flex-shrink-0 cursor-pointer hover:bg-slate-700/50 rounded-lg p-1 transition-colors",
                    title=f"{m_name} — {m_label}",
                )
            )
        other_matches_strip = Div(
            Div("More matches", cls="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide"),
            Div(*strip_items, cls="flex gap-3 overflow-x-auto pb-2"),
            cls="mt-5 pt-4 border-t border-slate-700/50",
        )

    return suggestion_el, other_matches_strip, target_id


def _build_skipped_focus_actions(identity_id: str, state: str, nav_prefix: str = "") -> Div:
    """Build action buttons for skipped focus mode."""
    best = _get_best_match_for_identity(identity_id)
    has_suggestion = best is not None

    buttons = []

    if has_suggestion:
        target_id = best.get("target_identity_id", "")
        target_name = ensure_utf8_display(best.get("target_identity_name", ""))
        buttons.append(
            Button(
                "✓ Same Person",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                hx_post=f"{nav_prefix}/api/identity/{target_id}/merge/{identity_id}?from_focus=true&focus_section=skipped",
                hx_target="#skipped-focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-confirm",
                title=f"Merge with {target_name}" if target_name else "Merge with suggestion",
                **{
                    "data-undo-url": f"{nav_prefix}/api/identity/{target_id}/undo-merge",
                    "data-undo-type": "merge",
                    "data-undo-identity": identity_id,
                },
            )
        )
        buttons.append(
            Button(
                "✗ Not Same",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors min-h-[44px]",
                hx_post=f"{nav_prefix}/api/skipped/{identity_id}/reject-suggestion?suggestion_id={target_id}",
                hx_target="#skipped-focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-reject",
                title="Not the same person — reject this suggestion",
                **{
                    "data-undo-url": f"{nav_prefix}/api/identity/{identity_id}/unreject/{target_id}",
                    "data-undo-type": "reject",
                    "data-undo-identity": identity_id,
                },
            )
        )

    buttons.append(
        Button(
            "I Know Them",
            cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors min-h-[44px]",
            type="button",
            id="focus-btn-name",
            **{
                "_": f"on click remove .hidden from #skipped-name-form-{identity_id} then set focus to the first <input/> in #skipped-name-form-{identity_id}"
            },
            title="I recognize this person — enter their name",
        )
    )
    buttons.append(
        Button(
            "→ Skip",
            cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors min-h-[44px]",
            hx_post=f"{nav_prefix}/api/skipped/{identity_id}/focus-skip",
            hx_target="#skipped-focus-container",
            hx_swap="outerHTML",
            type="button",
            id="focus-btn-skip",
            title="Skip — come back later",
            **{"data-undo-type": "skip", "data-undo-identity": identity_id},
        )
    )

    shortcut_text = "Y Same · N Different · Enter Name · S Skip · Z Undo" if has_suggestion else "Enter Name · S Skip"

    return Div(
        Div(*buttons, cls="flex flex-wrap items-center gap-3"),
        Div(shortcut_text, cls="text-xs text-slate-500 mt-2 hidden sm:block"),
        # Undo toast (hidden by default, shown after undo-able action)
        Div(
            id="undo-toast",
            cls="hidden fixed bottom-20 left-1/2 -translate-x-1/2 bg-slate-700 text-white px-4 py-2 rounded-lg shadow-lg z-50 text-sm flex items-center gap-3",
        ),
        cls="sticky bottom-0 bg-slate-800/95 backdrop-blur-sm border-t border-slate-700 p-4 -mx-4 sm:-mx-6 -mb-24 sm:-mb-6 mt-6 rounded-b-xl z-10",
    )


def get_next_skipped_focus_card(exclude_id: str = None, nav_prefix: str = "") -> Div:
    """
    Get the next skipped identity card for focus mode review.

    Returns an expanded identity card + Up Next carousel for skipped identities,
    sorted by actionability. Returns empty state if no items remain.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    skipped = registry.list_identities(state=IdentityState.SKIPPED)

    # Filter out the just-actioned item
    if exclude_id:
        skipped = [i for i in skipped if i["identity_id"] != exclude_id]

    # Sort by actionability
    sorted_skipped = _sort_skipped_by_actionability(skipped)

    if sorted_skipped:
        # Build Up Next carousel
        up_next = None
        if len(sorted_skipped) > 1:
            up_next = Div(
                H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                Div(
                    *[
                        identity_card_mini(i, crop_files, clickable=True, nav_prefix=nav_prefix)
                        for i in sorted_skipped[1:6]
                    ],
                    A(
                        f"+{len(sorted_skipped) - 6} more",
                        href=f"{nav_prefix}/?section=skipped&view=browse",
                        cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square",
                    )
                    if len(sorted_skipped) > 6
                    else None,
                    cls="flex gap-3 overflow-x-auto pb-2",
                ),
                cls="mt-6",
            )

        progress = _skipped_focus_progress(nav_prefix=nav_prefix)

        return Div(
            progress,
            skipped_card_expanded(sorted_skipped[0], crop_files, is_admin=True, nav_prefix=nav_prefix),
            up_next,
            id="skipped-focus-container",
            data_focus_mode="skipped",
        )
    else:
        return Div(
            Div("🎉", cls="text-4xl mb-4"),
            H3("All caught up!", cls="text-lg font-medium text-white"),
            P("You've reviewed all the faces that need help.", cls="text-slate-400 mt-1"),
            A(
                "← Back to Inbox",
                href=f"{nav_prefix}/?section=to_review",
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
            ),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
            id="skipped-focus-container",
        )


def render_rejected_section(
    dismissed: list, crop_files: set, counts: dict, is_admin: bool = True, nav_prefix: str = ""
) -> Div:
    """Render the Rejected/Dismissed section."""
    grid_items = []
    for identity in dismissed:
        card = identity_card(
            identity, crop_files, lane_color="rose", show_actions=False, is_admin=is_admin, nav_prefix=nav_prefix
        )
        if card:
            grid_items.append(card)
            _iid = identity["identity_id"]
            grid_items.append(Div(id=f"expand-{make_css_id(_iid)}", cls="expansion-panel"))

    if grid_items:
        content = Div(*grid_items, cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4")
    else:
        content = Div("No dismissed items. Rejected matches will appear here.", cls="text-center py-12 text-slate-400")

    return Div(section_header("Dismissed", f"{counts['rejected']} items dismissed"), content, cls="space-y-6")


def _photo_nav_url(photo_id: str, index: int, photos: list, total: int, nav_prefix: str = "") -> str:
    """Build /photo/{id}/partial URL with prev/next navigation context."""
    from urllib.parse import urlencode

    params = {"nav_idx": str(index), "nav_total": str(total)}
    if index > 0:
        params["prev_id"] = photos[index - 1]["photo_id"]
    if index < total - 1:
        params["next_id"] = photos[index + 1]["photo_id"]
    return f"{nav_prefix}/photo/{photo_id}/partial?{urlencode(params)}"


def render_photos_section(
    counts: dict,
    registry,
    crop_files: set,
    filter_source: str = "",
    sort_by: str = "newest",
    filter_collection: str = "",
    media_filter: str = "all",
    community: dict | None = None,
    nav_prefix: str = "",
) -> Div:
    """
    Render the Photos section - a grid view of all photos.

    This is the photo-centric workflow, complementing the face-centric inbox.

    Args:
        counts: Sidebar counts dict
        registry: Identity registry
        crop_files: Set of available crop filenames
        filter_source: Filter by source/provenance (empty = all)
        sort_by: Sort order (newest, oldest, most_faces, collection)
        filter_collection: Filter by collection/classification (empty = all)
        media_filter: "all" (default), "front_only" (no back images), "has_back" (only with backs)
        community: Optional community dict for filtering photos by community
    """
    _build_caches()
    if not _photo_cache:
        return Div(
            section_header("Photos", "0 photos"),
            Div("No photos uploaded yet.", cls="text-center py-12 text-slate-400"),
            cls="space-y-6",
        )

    # Community photo filter (PRD-035)
    community_photo_ids = _get_community_photo_ids(community)

    # Get all photos with metadata
    photos = []
    sources_set = set()
    collections_set = set()
    # Snapshot cache items so patched/shared test dictionaries cannot invalidate
    # the iterator mid-render under parallel test execution.
    for photo_id, photo_data in list(_photo_cache.items()):
        # Apply community filter
        if community_photo_ids is not None and photo_id not in community_photo_ids:
            continue
        source = photo_data.get("source", "")
        collection = photo_data.get("collection", "")
        if source:
            sources_set.add(source)
        if collection:
            collections_set.add(collection)

        # Get identified faces in this photo
        identified_faces = []
        confirmed_count = 0
        for face in photo_data.get("faces", []):
            face_id = face["face_id"]
            identity = get_identity_for_face(registry, face_id)
            if identity and identity.get("name"):
                identified_faces.append(
                    {
                        "name": identity.get("name"),
                        "face_id": face_id,
                        "identity_id": identity.get("identity_id"),
                    }
                )
                if identity.get("state") == "CONFIRMED":
                    confirmed_count += 1

        face_count = len(photo_data.get("faces", []))
        has_back = bool(photo_data.get("back_image", ""))
        photos.append(
            {
                "photo_id": photo_id,
                "filename": photo_data.get("filename", "unknown"),
                "source": source,
                "collection": collection,
                "face_count": face_count,
                "identified_count": len(identified_faces),
                "confirmed_count": confirmed_count,
                "identified_faces": identified_faces[:4],  # Max 4 for display
                "uploaded_by": photo_data.get("uploaded_by", ""),
                "upload_date": photo_data.get("upload_date", ""),
                "created_at": photo_data.get("created_at", ""),
                "updated_at": photo_data.get("updated_at", ""),
                "photo_index_order": photo_data.get("photo_index_order"),
                "has_back": has_back,
                "media_role": photo_data.get("media_role", "front"),
            }
        )

    sources = sorted(sources_set)
    collections = sorted(collections_set)

    # Apply filters
    if filter_source:
        photos = [p for p in photos if p["source"] == filter_source]
    if filter_collection:
        photos = [p for p in photos if p["collection"] == filter_collection]

    # Apply media filter
    if media_filter == "front_only":
        photos = [p for p in photos if p["media_role"] != "back"]
    elif media_filter == "has_back":
        photos = [p for p in photos if p["has_back"]]

    # Apply sorting
    photos = _sort_photos(photos, sort_by)

    # Workstation photos section renders inline inside the dashboard shell.
    # Cap the initial card set so the response stays browser-safe on large archives.
    photo_display_limit = 150
    total_matching_photos = len(photos)
    display_photos = photos[:photo_display_limit]

    # Build per-collection stats
    collection_stats = {}
    for p in photos:
        coll = p["collection"] or p["source"] or "Uncategorized"
        if coll not in collection_stats:
            collection_stats[coll] = {"photo_count": 0, "face_count": 0, "identified_count": 0}
        collection_stats[coll]["photo_count"] += 1
        collection_stats[coll]["face_count"] += p["face_count"]
        collection_stats[coll]["identified_count"] += p["identified_count"]

    # Build subtitle — scoped to current view
    active_filters = []
    if filter_collection:
        active_filters.append(filter_collection)
    if filter_source:
        active_filters.append(f"from {filter_source}")
    if active_filters:
        subtitle = f"{' '.join(active_filters)} \u2014 {len(photos)} photo{'s' if len(photos) != 1 else ''}"
    else:
        subtitle_parts = [f"{len(photos)} photo{'s' if len(photos) != 1 else ''}"]
        if len(collections) > 1:
            subtitle_parts.append(f"{len(collections)} collections")
        subtitle = " \u2022 ".join(subtitle_parts)

    # Build filter/sort options
    from urllib.parse import quote

    _fc = quote(filter_collection)
    _fs = quote(filter_source)
    _mf = quote(media_filter)

    collection_options = [Option("All Collections", value="", selected=not filter_collection)]
    for c in collections:
        collection_options.append(Option(c, value=c, selected=(filter_collection == c)))

    source_options = [Option("All Sources", value="", selected=not filter_source)]
    for s in sources:
        source_options.append(Option(s, value=s, selected=(filter_source == s)))

    sort_options = [
        Option("Upload Date (Newest)", value="upload_newest", selected=(sort_by == "upload_newest")),
        Option("Upload Date (Oldest)", value="upload_oldest", selected=(sort_by == "upload_oldest")),
        Option("Estimated Date (Newest)", value="newest", selected=(sort_by == "newest")),
        Option("Estimated Date (Oldest)", value="oldest", selected=(sort_by == "oldest")),
        Option("Filename (A-Z)", value="filename_az", selected=(sort_by == "filename_az")),
        Option("Most Faces", value="most_faces", selected=(sort_by == "most_faces")),
        Option("By Collection", value="collection", selected=(sort_by == "collection")),
        Option("By Source", value="by_source", selected=(sort_by == "by_source")),
    ]

    media_options = [
        Option("All Photos", value="all", selected=(media_filter == "all")),
        Option("Front Only", value="front_only", selected=(media_filter == "front_only")),
        Option("Has Back Image", value="has_back", selected=(media_filter == "has_back")),
    ]

    # Filter/sort controls
    filter_bar = Div(
        # Collection filter
        Div(
            Label("Collection:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *collection_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                "focus:ring-2 focus:ring-indigo-500 min-w-0 max-w-[10rem] sm:max-w-none truncate",
                onchange=f"window.location.href='{nav_prefix}/?section=photos&filter_collection=' + encodeURIComponent(this.value) + '&filter_source={_fs}&sort_by={sort_by}&media_filter={_mf}'",
            ),
            cls="flex items-center min-w-0",
        ),
        # Source filter
        Div(
            Label("Source:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *source_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                "focus:ring-2 focus:ring-indigo-500 min-w-0 max-w-[10rem] sm:max-w-none truncate",
                onchange=f"window.location.href='{nav_prefix}/?section=photos&filter_collection={_fc}&filter_source=' + encodeURIComponent(this.value) + '&sort_by={sort_by}&media_filter={_mf}'",
            ),
            cls="flex items-center min-w-0",
        ),
        # Sort
        Div(
            Label("Sort:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *sort_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                "focus:ring-2 focus:ring-indigo-500 min-w-0",
                onchange=f"window.location.href='{nav_prefix}/?section=photos&filter_collection={_fc}&filter_source={_fs}&sort_by=' + this.value + '&media_filter={_mf}'",
            ),
            cls="flex items-center min-w-0",
        ),
        # Media filter (front/back)
        Div(
            Label("Media:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *media_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                "focus:ring-2 focus:ring-indigo-500 min-w-0",
                onchange=f"window.location.href='{nav_prefix}/?section=photos&filter_collection={_fc}&filter_source={_fs}&sort_by={sort_by}&media_filter=' + this.value",
            ),
            cls="flex items-center min-w-0",
        ),
        # Select toggle button
        Button(
            "Select",
            id="photo-select-toggle",
            cls="px-3 py-1.5 text-sm border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors",
            type="button",
            data_action="toggle-photo-select",
        ),
        # Result count
        Span(
            (
                f"{len(display_photos)} of {total_matching_photos} photos"
                if total_matching_photos > photo_display_limit
                else f"{total_matching_photos} photo{'s' if total_matching_photos != 1 else ''}"
            ),
            cls="text-sm text-slate-500 ml-auto",
        ),
        cls="filter-bar flex flex-wrap items-center gap-4 bg-slate-800 rounded-lg p-3 border border-slate-700 mb-4",
    )

    # Photo grid — build with navigation context
    total_photos = len(display_photos)
    photo_cards = []
    for pi, photo in enumerate(display_photos):
        provenance = _get_upload_provenance_display(photo)
        # Face avatars for identified people
        face_avatars = []
        for i, face in enumerate(photo["identified_faces"][:3]):
            crop_file = f"{face['face_id']}.jpg"
            if crop_file in crop_files:
                face_avatars.append(
                    Div(
                        Img(
                            src=storage.get_crop_url_by_filename(crop_file),
                            cls="w-full h-full object-cover",
                            title=face["name"],
                        ),
                        cls="w-6 h-6 rounded-full border-2 border-slate-800 overflow-hidden",
                        style=f"margin-left: {-4 if i > 0 else 0}px; z-index: {10 - i};",
                    )
                )

        if photo["identified_count"] > 3:
            face_avatars.append(
                Div(
                    f"+{photo['identified_count'] - 3}",
                    cls="w-6 h-6 rounded-full border-2 border-slate-800 bg-slate-700 "
                    "flex items-center justify-center text-xs text-slate-300",
                    style="margin-left: -4px;",
                )
            )

        card = Div(
            # Photo thumbnail
            Div(
                Img(
                    src=photo_url(photo["filename"]),
                    cls="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300",
                    loading="lazy",
                ),
                # Select mode checkbox (hidden by default)
                Div(
                    Input(
                        type="checkbox",
                        name="photo_ids",
                        value=photo["photo_id"],
                        cls="w-5 h-5 rounded border-slate-500 bg-slate-700/80 text-indigo-500 focus:ring-indigo-500 cursor-pointer",
                        data_action="photo-select-check",
                    ),
                    cls="photo-select-checkbox absolute top-2 left-2 z-10 hidden",
                ),
                # Face count badge with completion indicator
                Div(
                    Span("\u2713 ", cls="text-emerald-400")
                    if photo["face_count"] > 0 and photo["confirmed_count"] == photo["face_count"]
                    else None,
                    f"{photo['confirmed_count']}/{photo['face_count']}"
                    if photo["confirmed_count"] > 0
                    else f"{photo['face_count']} face{'s' if photo['face_count'] != 1 else ''}",
                    cls="absolute top-2 right-2 text-white text-xs font-data "
                    "px-2 py-1 rounded-full backdrop-blur-sm "
                    + (
                        "bg-emerald-600/80"
                        if photo["face_count"] > 0 and photo["confirmed_count"] == photo["face_count"]
                        else "bg-black/70"
                        if photo["confirmed_count"] == 0
                        else "bg-indigo-600/70"
                    ),
                ),
                # Identified faces indicator
                Div(*face_avatars, cls="absolute bottom-2 left-2 flex") if face_avatars else None,
                # Back image indicator (flip icon)
                Div(
                    "\u21c5",
                    cls="absolute bottom-2 right-2 w-6 h-6 rounded-full bg-amber-600/80 "
                    "text-white text-xs flex items-center justify-center backdrop-blur-sm",
                    title="Has back image",
                )
                if photo.get("has_back")
                else None,
                # Date badge
                _render_date_badge_overlay(photo["photo_id"]),
                cls="aspect-[4/3] overflow-hidden relative",
            ),
            # Photo info
            Div(
                P(photo["filename"], cls="text-sm text-white truncate font-data"),
                Div(
                    P(f"\U0001f4c1 {photo['source']}", cls="text-xs text-slate-500 leading-snug")
                    if photo["source"]
                    else None,
                    Span(
                        share_button(url=f"{nav_prefix}/photo/{photo['photo_id']}", style="icon"),
                        A(
                            "Public Page",
                            href=f"{nav_prefix}/photo/{photo['photo_id']}",
                            cls="text-[10px] text-indigo-400 hover:text-indigo-300 underline ml-1",
                            target="_blank",
                        ),
                        cls="flex items-center gap-0.5 flex-shrink-0",
                        **{"_": "on click halt the event's bubbling"},
                    ),
                    cls="flex items-center justify-between mt-0.5",
                ),
                Div(
                    P(
                        provenance["headline"],
                        cls="text-[11px] text-slate-400 leading-tight",
                    ),
                    P(
                        provenance["subline"],
                        cls="text-[10px] text-slate-500 leading-tight",
                    )
                    if provenance.get("subline")
                    else None,
                    cls="mt-1 space-y-0.5",
                )
                if provenance
                else None,
                cls="p-3",
            ),
            cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden "
            "hover:border-slate-500 transition-colors cursor-pointer group",
            hx_get=_photo_nav_url(photo["photo_id"], pi, display_photos, total_photos, nav_prefix=nav_prefix),
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show modal and set navigation index
            **{"_": f"on htmx:afterOnLoad remove .hidden from #photo-modal then js window._photoNavIdx={pi} end"},
        )
        photo_cards.append(card)

    # Build ordered photo ID list for client-side navigation
    import json as _json

    photo_id_list = [p["photo_id"] for p in display_photos]
    photo_nav_script = Script(f"""
        window._photoNavIds = {_json.dumps(photo_id_list)};
        window._photoNavIdx = -1;
        function photoNavTo(idx) {{
            var ids = window._photoNavIds;
            if (idx < 0 || idx >= ids.length) return;
            window._photoNavIdx = idx;
            var prevId = idx > 0 ? ids[idx-1] : '';
            var nextId = idx < ids.length-1 ? ids[idx+1] : '';
            var url = '{nav_prefix}/photo/' + ids[idx] + '/partial?nav_idx=' + idx + '&nav_total=' + ids.length;
            if (prevId) url += '&prev_id=' + prevId;
            if (nextId) url += '&next_id=' + nextId;
            htmx.ajax('GET', url, {{target:'#photo-modal-content', swap:'innerHTML'}});
        }}
        // NOTE: Keyboard navigation is handled by the global event delegation
        // handler (data-action dispatch on document). Do NOT add a per-script
        // keydown listener here — it would double-fire with the global one,
        // causing 2 navigations per key press. (BUG-006 fix)
        // Touch swipe for photo modal navigation
        (function() {{
            var mc = document.getElementById('photo-modal-content');
            if (!mc) return;
            var sx = 0, sy = 0;
            mc.addEventListener('touchstart', function(e) {{ sx = e.touches[0].clientX; sy = e.touches[0].clientY; }}, {{passive: true}});
            mc.addEventListener('touchend', function(e) {{
                var dx = e.changedTouches[0].clientX - sx;
                var dy = e.changedTouches[0].clientY - sy;
                if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {{
                    if (dx > 0) photoNavTo(window._photoNavIdx - 1);
                    else photoNavTo(window._photoNavIdx + 1);
                }}
            }});
        }})();
    """)

    # Photo grid layout
    grid = Div(*photo_cards, photo_nav_script, cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4")

    # Collection stats cards (shown when viewing all collections, not filtered)
    collection_cards = None
    if not filter_collection and not filter_source and len(collection_stats) > 1:
        stat_cards = []
        for coll_name in sorted(collection_stats.keys()):
            stats = collection_stats[coll_name]
            stat_cards.append(
                Div(
                    Div(P(coll_name, cls="text-sm font-medium text-white leading-snug"), cls="mb-2"),
                    Div(
                        Span(
                            f"{stats['photo_count']} photo{'s' if stats['photo_count'] != 1 else ''}",
                            cls="text-xs text-slate-400",
                        ),
                        Span(" \u2022 ", cls="text-xs text-slate-600"),
                        Span(
                            f"{stats['face_count']} face{'s' if stats['face_count'] != 1 else ''}",
                            cls="text-xs text-slate-400",
                        ),
                        Span(" \u2022 ", cls="text-xs text-slate-600"),
                        Span(f"{stats['identified_count']} identified", cls="text-xs text-emerald-400"),
                    ),
                    cls="bg-slate-800/50 border border-slate-700 rounded-lg p-3 cursor-pointer "
                    "hover:border-indigo-500/50 transition-colors",
                    onclick=f"window.location.href='/?section=photos&filter_collection={quote(coll_name)}&sort_by={sort_by}'",
                )
            )
        # Use horizontal scroll for 5+ collections, grid for fewer
        if len(stat_cards) >= 5:
            # Make cards fixed-width for horizontal scrolling
            for card in stat_cards:
                card.attrs["class"] = card.attrs.get("class", "") + " min-w-[180px] flex-shrink-0"
            collection_cards = Div(*stat_cards, cls="flex gap-3 mb-4 overflow-x-auto pb-2 scrollbar-thin")
        else:
            collection_cards = Div(*stat_cards, cls="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4")

    # Bulk action bar (hidden until selections exist)
    collection_options_bulk = [Option("Set collection...", value="", disabled=True, selected=True)]
    for c in collections:
        collection_options_bulk.append(Option(c, value=c))

    source_options_bulk = [Option("Set source...", value="", disabled=True, selected=True)]
    for s in sources:
        source_options_bulk.append(Option(s, value=s))

    bulk_action_bar = Div(
        Div(
            Span("0 selected", id="photo-select-count", cls="text-sm font-medium text-white"),
            Button(
                "Select All",
                type="button",
                data_action="photo-select-all",
                cls="px-3 py-1 text-xs border border-slate-600 text-slate-300 rounded hover:bg-slate-700",
            ),
            Button(
                "Clear",
                type="button",
                data_action="photo-select-clear",
                cls="px-3 py-1 text-xs border border-slate-600 text-slate-300 rounded hover:bg-slate-700",
            ),
            Div(
                Select(
                    *collection_options_bulk,
                    id="bulk-move-collection",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5",
                ),
                Select(
                    *source_options_bulk,
                    id="bulk-move-source",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5",
                ),
                Input(
                    type="url",
                    id="bulk-source-url",
                    placeholder="Source URL...",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5 w-40",
                ),
                Button(
                    "Apply",
                    type="button",
                    data_action="photo-bulk-move",
                    cls="px-4 py-1.5 text-sm font-bold bg-indigo-600 text-white rounded hover:bg-indigo-500",
                ),
                cls="flex items-center gap-2 flex-wrap",
            ),
            Button(
                "Cancel",
                type="button",
                data_action="toggle-photo-select",
                cls="px-3 py-1 text-xs text-slate-400 hover:text-white",
            ),
            cls="flex items-center gap-4 max-w-5xl mx-auto px-4 flex-wrap",
        ),
        id="photo-bulk-bar",
        cls="hidden fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 py-3 z-40",
    )

    # Select mode script using event delegation (CLAUDE.md rule #12)
    select_script = Script("""
        (function() {
            var selectMode = false;

            document.addEventListener('click', function(e) {
                var action = e.target.closest('[data-action]');
                if (!action) return;
                var act = action.getAttribute('data-action');

                if (act === 'toggle-photo-select') {
                    selectMode = !selectMode;
                    var cbs = document.querySelectorAll('.photo-select-checkbox');
                    var bar = document.getElementById('photo-bulk-bar');
                    var toggle = document.getElementById('photo-select-toggle');
                    cbs.forEach(function(cb) { cb.classList.toggle('hidden', !selectMode); });
                    if (bar) bar.classList.toggle('hidden', !selectMode);
                    if (toggle) {
                        toggle.textContent = selectMode ? 'Cancel' : 'Select';
                        toggle.classList.toggle('bg-indigo-600', selectMode);
                        toggle.classList.toggle('text-white', selectMode);
                        toggle.classList.toggle('border-indigo-600', selectMode);
                    }
                    if (!selectMode) {
                        cbs.forEach(function(cb) { var inp = cb.querySelector('input'); if (inp) inp.checked = false; });
                        updateSelectCount();
                    }
                }
                else if (act === 'photo-select-check') {
                    updateSelectCount();
                }
                else if (act === 'photo-select-all') {
                    document.querySelectorAll('.photo-select-checkbox input').forEach(function(cb) { cb.checked = true; });
                    updateSelectCount();
                }
                else if (act === 'photo-select-clear') {
                    document.querySelectorAll('.photo-select-checkbox input').forEach(function(cb) { cb.checked = false; });
                    updateSelectCount();
                }
                else if (act === 'photo-bulk-move') {
                    var collSel = document.getElementById('bulk-move-collection');
                    var srcSel = document.getElementById('bulk-move-source');
                    var urlInp = document.getElementById('bulk-source-url');
                    var collection = collSel ? collSel.value : '';
                    var source = srcSel ? srcSel.value : '';
                    var sourceUrl = urlInp ? urlInp.value : '';
                    if (!collection && !source && !sourceUrl) { alert('Please set at least one field.'); return; }
                    var ids = [];
                    document.querySelectorAll('.photo-select-checkbox input:checked').forEach(function(cb) { ids.push(cb.value); });
                    if (ids.length === 0) { alert('No photos selected.'); return; }
                    htmx.ajax('POST', '/api/photos/bulk-update-source', {
                        values: { photo_ids: JSON.stringify(ids), collection: collection, source: source, source_url: sourceUrl },
                        target: '#toast-container',
                        swap: 'beforeend'
                    });
                }
            });

            // Also handle change events for checkboxes
            document.addEventListener('change', function(e) {
                if (e.target.closest('[data-action="photo-select-check"]')) {
                    updateSelectCount();
                }
            });

            function updateSelectCount() {
                var count = document.querySelectorAll('.photo-select-checkbox input:checked').length;
                var el = document.getElementById('photo-select-count');
                if (el) el.textContent = count + ' selected';
            }
        })();
    """)

    return Div(
        section_header("Photos", subtitle),
        filter_bar,
        Div(
            f"Showing first {photo_display_limit} of {total_matching_photos} photos in workstation mode. "
            "Use /photos for the full archive browser."
            if total_matching_photos > photo_display_limit
            else "",
            cls="text-xs text-slate-500",
        )
        if total_matching_photos > photo_display_limit
        else None,
        collection_cards,
        grid
        if photo_cards
        else Div(
            "No photos found." + (" Clear filter to see all." if (filter_source or filter_collection) else ""),
            cls="text-center py-12 text-slate-400",
        ),
        bulk_action_bar,
        select_script,
        cls="space-y-6",
    )


def get_next_focus_card(exclude_id: str = None, triage_filter: str = "", nav_prefix: str = ""):
    """
    Get the next identity card for focus mode review.

    Returns an expanded identity card + Up Next carousel for the top priority items,
    or an empty state if no items remain.

    Args:
        exclude_id: Identity ID to exclude (just-actioned item)
        triage_filter: Active triage filter to preserve through navigation

    IMPORTANT: This must use the same sorting as render_to_review_section to ensure
    the "Up Next" queue matches what appears after an action.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    # Get all to_review items
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    to_review = inbox + proposed

    # Filter out the just-actioned item
    if exclude_id:
        to_review = [i for i in to_review if i["identity_id"] != exclude_id]

    # Apply triage filter if set (must match render_to_review_section logic)
    if triage_filter in ("ready", "rediscovered", "unmatched"):
        to_review = [i for i in to_review if _triage_category(i) == triage_filter]

    # Sort by actionability priority (matches render_to_review_section's _focus_sort_key)
    ids_with_proposals = _get_identities_with_proposals()

    def _focus_sort_key(x):
        iid = x.get("identity_id", "")
        has_proposal = iid in ids_with_proposals
        best = _get_best_proposal_for_identity(iid) if has_proposal else None
        has_promotion = x.get("promoted_from") is not None
        promotion_reason = x.get("promotion_reason", "")

        if has_promotion and promotion_reason == "confirmed_match":
            tier = 0
        elif has_proposal and best and best.get("confidence") == "VERY HIGH":
            tier = 1
        elif has_promotion:
            tier = 2
        elif has_proposal and best and best.get("confidence") == "HIGH":
            tier = 3
        elif has_proposal:
            tier = 4
        else:
            tier = 5

        # Quality tiebreaker — clear faces first within same tier
        quality = _identity_quality_score(x)

        return (
            tier,
            best["distance"] if best else 999,
            -quality,
            -len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        )

    high_confidence = sorted(to_review, key=_focus_sort_key)[:10]

    if high_confidence:
        user_is_admin = True  # get_next_focus_card is only called from admin action routes
        # Build Up Next carousel
        up_next = None
        if len(high_confidence) > 1:
            up_next = Div(
                H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                Div(
                    *[
                        identity_card_mini(
                            i, crop_files, clickable=True, triage_filter=triage_filter, nav_prefix=nav_prefix
                        )
                        for i in high_confidence[1:6]
                    ],
                    A(
                        f"+{len(high_confidence) - 6} more",
                        href=f"{nav_prefix}/?section=to_review&view=browse{f'&filter={triage_filter}' if triage_filter else ''}",
                        cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square",
                    )
                    if len(high_confidence) > 6
                    else None,
                    cls="flex gap-3 overflow-x-auto pb-2",
                ),
                cls="mt-6",
            )

        # Show promotion banner above the expanded card if applicable
        banner = _promotion_banner(high_confidence[0])
        return Div(
            banner,
            identity_card_expanded(
                high_confidence[0],
                crop_files,
                is_admin=user_is_admin,
                triage_filter=triage_filter,
                nav_prefix=nav_prefix,
            ),
            up_next,
            id="focus-container",
        )
    else:
        # Empty state
        return Div(
            Div("🎉", cls="text-4xl mb-4"),
            H3("All caught up!", cls="text-lg font-medium text-white"),
            P("No more items to review.", cls="text-slate-400 mt-1"),
            A(
                "Upload more photos →",
                href=f"{nav_prefix}/upload",
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
            ),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
            id="focus-container",
        )


def inbox_badge(count: int) -> A:
    """
    New Matches badge showing count of items awaiting review.
    """
    if count == 0:
        return A(
            Span("\U0001f4e5", cls="mr-2"),
            "New Matches",
            Span("(0)", cls="text-slate-500 ml-1"),
            href="#inbox-lane",
            cls="text-slate-400 hover:text-slate-300 text-sm",
        )
    return A(
        Span("\U0001f4e5", cls="mr-2"),
        "New Matches",
        Span(f"({count})", cls="bg-blue-600 text-white text-xs px-1.5 py-0.5 rounded-full ml-1"),
        href="#inbox-lane",
        cls="text-slate-300 hover:text-blue-400 text-sm font-medium",
    )


def review_action_buttons(identity_id: str, state: str, is_admin: bool = True, nav_prefix: str = "") -> Div:
    """
    Unified action buttons based on identity state.
    Only rendered for admin users.
    """
    if not is_admin:
        return Div()  # No buttons for non-admins

    buttons = []

    # Confirm button - available for reviewable and skipped states
    if state in ("INBOX", "PROPOSED", "SKIPPED"):
        # Use different endpoint for INBOX vs PROPOSED/SKIPPED
        confirm_url = (
            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
        )
        buttons.append(
            Button(
                "\u2713 Confirm",
                cls="px-3 py-1.5 text-sm font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors min-h-[44px]",
                hx_post=confirm_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                hx_indicator=f"#loading-{identity_id}",
                aria_label="Confirm this identity",
                type="button",
            )
        )

    # Skip button - available for reviewable states only
    if state in ("INBOX", "PROPOSED"):
        buttons.append(
            Button(
                "\u23f8 Skip",
                cls="px-3 py-1.5 text-sm font-bold bg-amber-500 text-white rounded hover:bg-amber-600 transition-colors min-h-[44px]",
                hx_post=f"{nav_prefix}/identity/{identity_id}/skip",
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                hx_indicator=f"#loading-{identity_id}",
                aria_label="Skip for later",
                type="button",
            )
        )

    # Reject button - available for reviewable and skipped states
    if state in ("INBOX", "PROPOSED", "SKIPPED"):
        # Use different endpoint for INBOX vs PROPOSED/SKIPPED
        reject_url = (
            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
        )
        buttons.append(
            Button(
                "\u2717 Reject",
                cls="px-3 py-1.5 text-sm font-bold border-2 border-red-500 text-red-500 rounded hover:bg-red-500/20 transition-colors min-h-[44px]",
                hx_post=reject_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                hx_indicator=f"#loading-{identity_id}",
                aria_label="Reject this identity",
                type="button",
            )
        )

    # Reset button - available for terminal states (de-emphasized — admin edge case)
    if state in ("CONFIRMED", "SKIPPED", "REJECTED", "CONTESTED"):
        buttons.append(
            Button(
                "Reset",
                cls="px-2 py-1 text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 rounded transition-colors",
                hx_post=f"/identity/{identity_id}/reset",
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                hx_indicator=f"#loading-{identity_id}",
                aria_label="Return to Inbox",
                type="button",
            )
        )

    # Loading indicator
    buttons.append(
        Span(
            "...",
            id=f"loading-{identity_id}",
            cls="htmx-indicator ml-2 text-slate-400 animate-pulse",
            aria_hidden="true",
        )
    )

    return Div(
        *buttons,
        cls="flex gap-2 items-center flex-wrap mt-3",
    )


def state_badge(state: str) -> Span:
    """
    Render state as a colored badge.
    UX Intent: Instant state recognition via color coding.
    """
    colors = {
        "INBOX": "bg-blue-600 text-white",
        "CONFIRMED": "bg-emerald-600 text-white",
        "PROPOSED": "bg-amber-500 text-white",
        "CONTESTED": "bg-red-600 text-white",
        "REJECTED": "bg-rose-700 text-white",
        "SKIPPED": "bg-stone-500 text-white",
    }
    return Span(state, cls=f"text-xs font-bold px-2 py-1 rounded {colors.get(state, 'bg-gray-500 text-white')}")


def era_badge(era: str) -> Span:
    """
    Render era classification as a subtle badge.
    UX Intent: Temporal context without visual dominance.
    """
    if not era:
        return None
    return Span(era, cls="absolute top-2 right-2 bg-stone-700/80 text-white text-xs px-2 py-1 font-mono")


# Share icon SVG (three connected dots) — used everywhere for consistency
_SHARE_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'


def og_tags(
    title: str, description: str = "", image_url: str = "", canonical_url: str = "", og_type: str = "website"
) -> tuple:
    """
    Unified OG meta tags for social sharing previews.
    All URLs are converted to absolute (prepends SITE_URL if relative).
    Returns a tuple of Meta elements to spread into Title() or page head.
    """
    # Ensure absolute URLs
    if image_url and not image_url.startswith("http"):
        image_url = f"{SITE_URL}{image_url}"
    if canonical_url and not canonical_url.startswith("http"):
        canonical_url = f"{SITE_URL}{canonical_url}"
    tags = [
        Meta(property="og:title", content=title),
        Meta(property="og:description", content=description),
        Meta(property="og:url", content=canonical_url),
        Meta(property="og:type", content=og_type),
        Meta(property="og:site_name", content="Rhodesli \u2014 Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image" if image_url else "summary"),
        Meta(name="twitter:title", content=title),
        Meta(name="twitter:description", content=description),
        Meta(name="description", content=description),
    ]
    if image_url:
        tags.insert(2, Meta(property="og:image", content=image_url))
        tags.append(Meta(name="twitter:image", content=image_url))
    return tuple(tags)


def share_button(
    photo_id: str = None, *, url: str = None, style: str = "icon", label: str = "Share", title: str = "", text: str = ""
):
    """
    Reusable share button. Works with photo_id (legacy) or any url.
    Uses data-action="share-photo" for global event delegation.

    photo_id: Legacy param — generates /photo/{photo_id} URL
    url: Direct URL to share (takes precedence over photo_id)
    style: "icon" (compact), "button" (icon + text), "link" (text link), "prominent" (large CTA)
    title: Share title for native share sheet (optional)
    text: Share description for native share sheet (optional)
    """
    share_url = url or (f"/photo/{photo_id}" if photo_id else "")
    extra_attrs = {}
    if title:
        extra_attrs["data_share_title"] = title
    if text:
        extra_attrs["data_share_text"] = text
    if style == "button":
        return Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
            ),
            label,
            cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    elif style == "link":
        return Button(
            NotStr(_SHARE_ICON_SVG),
            f" {label}",
            cls="text-xs text-indigo-400 hover:text-indigo-300 underline inline-flex items-center gap-1",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    elif style == "prominent":
        return Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 mr-2 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
            ),
            label,
            cls="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-base font-medium rounded-xl transition-colors inline-flex items-center shadow-lg hover:shadow-xl",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    else:  # "icon" — compact, for grid overlays and card corners
        return Button(
            NotStr(_SHARE_ICON_SVG),
            cls="p-1.5 bg-black/60 hover:bg-indigo-600 text-white rounded transition-colors",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            title=label,
            **extra_attrs,
        )


def parse_transform_to_css(transform_str: str) -> str:
    """Convert a transform string like 'rotate:90,flipH' to CSS transform value.

    Supported transforms:
    - rotate:90, rotate:180, rotate:270 — clockwise rotation
    - flipH — horizontal mirror (scaleX(-1))
    - flipV — vertical mirror (scaleY(-1))
    - invert — handled separately via CSS filter, not transform

    Returns CSS transform property value (e.g., 'rotate(90deg) scaleX(-1)').
    """
    if not transform_str or not transform_str.strip():
        return ""

    parts = [p.strip() for p in transform_str.split(",") if p.strip()]
    css_parts = []
    for part in parts:
        if part.startswith("rotate:"):
            degrees = part.split(":")[1]
            css_parts.append(f"rotate({degrees}deg)")
        elif part == "flipH":
            css_parts.append("scaleX(-1)")
        elif part == "flipV":
            css_parts.append("scaleY(-1)")
        # 'invert' is handled via CSS filter, not transform
    return " ".join(css_parts)


def parse_transform_to_filter(transform_str: str) -> str:
    """Extract CSS filter from transform string (for 'invert')."""
    if not transform_str or "invert" not in transform_str:
        return ""
    return "invert(1)"


def image_transform_toolbar(photo_id: str, target: str = "front") -> Div:
    """Admin toolbar for non-destructive image orientation.

    target: 'front' or 'back' — which image side to transform.
    """
    field_name = "transform" if target == "front" else "back_transform"
    label = "Front orientation" if target == "front" else "Back orientation"

    def _btn(icon_label, transform_val, danger=False):
        cls_base = "px-2 py-1 text-xs rounded transition-colors"
        cls_color = (
            "bg-red-900/50 hover:bg-red-800/50 text-red-300"
            if danger
            else "bg-slate-700 hover:bg-slate-600 text-slate-300"
        )
        return Button(
            icon_label,
            cls=f"{cls_base} {cls_color}",
            type="button",
            hx_post=f"/api/photo/{photo_id}/transform?transform={transform_val}&field={field_name}",
            hx_target="#transform-result",
            hx_swap="innerHTML",
        )

    return Div(
        P(label, cls="text-xs text-slate-400 font-medium mb-1"),
        Div(
            _btn("\u21bb 90\u00b0", "rotate:90"),
            _btn("\u21ba -90\u00b0", "rotate:270"),
            _btn("\u2194 Flip H", "flipH"),
            _btn("\u2195 Flip V", "flipV"),
            _btn("\u25d0 Invert", "invert"),
            _btn("\u21a9 Reset", "reset", danger=True),
            cls="flex flex-wrap gap-1",
        ),
        cls="mt-2",
    )


def face_card(
    face_id: str,
    crop_url: str,
    quality: float = None,
    era: str = None,
    identity_id: str = None,
    photo_id: str = None,
    show_actions: bool = False,
    show_detach: bool = False,
    is_admin: bool = True,
) -> Div:
    """
    Single face card with optional action buttons.
    UX Intent: Face-first display with metadata secondary.

    Args:
        face_id: Canonical face identifier (for alt text)
        crop_url: Resolved URL path to the crop image (from backend)
        quality: Quality score (extracted from URL if not provided)
        era: Era classification for badge display
        identity_id: Parent identity ID
        photo_id: Photo ID for "View Photo" button
        show_actions: Whether to show action buttons
        show_detach: Whether to show "Detach" button (only when identity has > 1 face)
        is_admin: Whether to show admin-only info (quality score)
    """
    if quality is None:
        # Extract quality from URL: /crops/{name}_{quality}_{idx}.jpg
        quality = parse_quality_from_filename(crop_url)
    if quality == 0.0:
        # Inbox crops don't encode quality in filename — look up from embeddings
        emb_quality = get_face_quality(face_id)
        if emb_quality is not None:
            quality = emb_quality

    # View Photo button (only if photo_id is available)
    # Pass identity_id for navigation context between identity's photos
    view_photo_btn = None
    if photo_id:
        _vp_url = f"/photo/{photo_id}/partial?face={face_id}"
        if identity_id:
            _vp_url += f"&identity_id={identity_id}"
        view_photo_btn = Button(
            "View Photo",
            cls="text-xs text-slate-400 hover:text-slate-300 underline mt-1",
            hx_get=_vp_url,
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show the modal when clicked
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )

    # Share button for public photo viewer
    full_page_link = None
    if photo_id:
        full_page_link = Span(
            share_button(photo_id, style="link", label="Share"),
            cls="mt-1 ml-2",
        )

    # Detach button (only if show_detach is True)
    detach_btn = None
    if show_detach:
        # Generate safe DOM ID for targeting
        safe_dom_id = make_css_id(face_id)

        detach_btn = Button(
            "Detach",
            cls="text-xs text-slate-400 hover:text-slate-300 underline mt-1 ml-2",
            hx_post=f"/api/face/{quote(face_id)}/detach",
            hx_target=f"#{safe_dom_id}",
            hx_swap="outerHTML",
            hx_confirm="Move this face to its own identity? (You can merge it back later.)",
            type="button",
        )

    # Quality label text
    quality_word = None
    quality_label = None
    if quality > 0:
        quality_word = "Excellent" if quality >= 30 else "Good" if quality >= 20 else "Fair" if quality >= 10 else "Low"
        quality_label = f"{quality_word} quality"

    return Div(
        # Face hero — dominant visual element (min 200px desktop, 150px mobile)
        Div(
            Img(
                src=crop_url,
                alt=face_id,
                cls="w-full h-full object-cover sepia-[.15] hover:sepia-0 transition-all duration-300",
            ),
            era_badge(era) if era else None,
            cls="relative border border-amber-900/30 rounded-sm overflow-hidden min-h-[150px] sm:min-h-[200px]",
        ),
        # Compact metadata: quality label + secondary actions on hover
        Div(
            Span(
                quality_label,
                cls=f"text-xs font-data {'text-emerald-500' if quality >= 20 else 'text-amber-500' if quality >= 10 else 'text-slate-500'}",
                title=f"Quality score: {quality:.2f}" if is_admin else None,
            )
            if quality_label
            else None,
            # Secondary actions (View Photo, Share, Detach)
            # Detach is always visible for admin; other actions visible on hover
            Div(
                view_photo_btn,
                full_page_link,
                detach_btn,
                cls="flex items-center"
                + ("" if show_detach else " opacity-0 group-hover:opacity-100 transition-opacity"),
            )
            if view_photo_btn or detach_btn or full_page_link
            else None,
            cls="mt-1 px-0.5 flex items-center justify-between",
        ),
        cls="face-card-archival group p-1 rounded min-w-[150px]",
        # Fix: Apply the safe ID to the container
        id=make_css_id(face_id),
    )


def match_info_bar(
    distance: float,
    confidence_gap: float = 0.0,
    co_occurrence: int = 0,
    show_distance: bool = True,
    show_badge: bool = True,
) -> Div:
    """Shared match metrics bar — used by neighbor_card and discovery cards.

    Session 88: Unified component so all match displays show the same info.
    Args:
        show_badge: If False, skip the "X% match" badge (caller already shows pct).
    """
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(distance)
    pct = conf["confidence_pct"]
    label = conf["short_label"]

    _similarity_classes = {
        "Very High": "bg-emerald-500/30 text-emerald-300",
        "High": "bg-emerald-500/20 text-emerald-400",
        "Moderate": "bg-amber-500/20 text-amber-400",
        "Low": "bg-amber-500/15 text-amber-500",
        "Very Low": "bg-slate-600 text-slate-400",
    }
    similarity_class = _similarity_classes.get(label, "bg-slate-600 text-slate-400")

    badge = Span(f"{pct}% match", cls=f"text-xs px-2 py-0.5 rounded {similarity_class}") if show_badge else None

    details = []
    if show_distance:
        details.append(Span(f"Dist: {distance:.2f}", cls="text-xs font-data text-slate-400 bg-slate-700 px-1 rounded"))
    if confidence_gap > 0:
        details.append(
            Span(f"+{confidence_gap}% gap", cls="text-xs font-data text-emerald-400/70 bg-emerald-900/30 px-1 rounded")
        )
    if co_occurrence > 0:
        details.append(
            Span(
                f"Seen together in {co_occurrence} photo{'s' if co_occurrence != 1 else ''}",
                cls="text-[10px] text-amber-400 italic",
            )
        )

    return Div(
        badge,
        Div(*details, cls="flex items-center flex-wrap gap-1") if details else None,
        cls="flex flex-col gap-0.5",
        data_testid="match-info-bar",
    )


def neighbor_card(
    neighbor: dict,
    target_identity_id: str,
    crop_files: set,
    show_checkbox: bool = True,
    user_role: str = "admin",
    from_focus: bool = False,
    triage_filter: str = "",
    focus_section: str = "",
    target_name: str = "",
    current_community: dict | None = None,
    nav_prefix: str = "",
) -> Div:
    neighbor_id = neighbor["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    name = ensure_utf8_display(neighbor["name"])
    # For "Unidentified Person NNNN", show "Person NNNN" to prevent truncation
    if name.startswith("Unidentified Person "):
        name = "Person " + name[len("Unidentified Person ") :]
    # Get values directly (no more negative scaling)
    distance = neighbor["distance"]
    percentile = neighbor.get("percentile", 1.0)
    confidence_gap = neighbor.get("confidence_gap", 0.0)

    can_merge = neighbor["can_merge"]
    face_count = neighbor.get("face_count", 0)
    co_occurrence = neighbor.get("co_occurrence", 0)

    # --- Unified confidence scoring (AD-200) ---
    from core.confidence import compute_face_confidence

    _disc_conf = compute_face_confidence(distance)
    similarity_label = _disc_conf["short_label"]
    calibrated_pct = _disc_conf["confidence_pct"]

    _similarity_classes = {
        "Very High": "bg-emerald-500/30 text-emerald-300",
        "High": "bg-emerald-500/20 text-emerald-400",
        "Moderate": "bg-amber-500/20 text-amber-400",
        "Low": "bg-amber-500/15 text-amber-500",
        "Very Low": "bg-slate-600 text-slate-400",
    }
    similarity_class = _similarity_classes.get(similarity_label, "bg-slate-600 text-slate-400")
    # -----------------------------------------------

    # Merge button -- role-aware: admin merges directly, contributor suggests
    # In focus mode, target #focus-container and append from_focus=true so the merge
    # endpoint advances to the next identity instead of returning a browse-mode card.
    _focus_filter = f"&filter={triage_filter}" if triage_filter else ""
    _focus_section = f"&focus_section={focus_section}" if focus_section else ""
    focus_suffix = f"?from_focus=true{_focus_filter}{_focus_section}" if from_focus else ""
    if from_focus and focus_section == "skipped":
        merge_target = "#skipped-focus-container"
    elif from_focus:
        merge_target = "#focus-container"
    else:
        merge_target = f"#identity-{target_identity_id}"
    merge_swap = "outerHTML"
    if not can_merge:
        merge_btn = Button(
            "Blocked",
            cls="px-3 py-1 text-sm font-bold bg-slate-600 text-slate-400 rounded cursor-not-allowed",
            disabled=True,
            title=neighbor.get("merge_blocked_reason_display"),
        )
    elif user_role == "contributor":
        merge_btn = Button(
            "Suggest Merge",
            cls="px-3 py-1 text-sm font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/suggest-merge/{neighbor_id}",
            hx_target=f"#neighbor-{neighbor_id}",
            hx_swap="outerHTML",
            data_auth_action="suggest a merge",
        )
    else:
        # UX-037: Show merge direction — neighbor merges INTO target
        _merge_label = (
            f"Merge \u2192 {target_name}" if target_name and not target_name.startswith("Unidentified") else "Merge"
        )
        _confirm_msg = (
            f"Merge {name} into {target_name}? All faces will be combined."
            if target_name and not target_name.startswith("Unidentified")
            else "Merge these identities? This can be undone."
        )
        merge_btn = Button(
            _merge_label,
            cls="px-3 py-1 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/merge/{neighbor_id}{focus_suffix}",
            hx_target=merge_target,
            hx_swap=merge_swap,
            data_auth_action="merge these identities",
            hx_confirm=_confirm_msg,
            title=f"Merge {name} into {target_name}" if target_name else "Merge these identities",
        )

    # Compare button -- opens side-by-side comparison modal
    _compare_filter = f"?filter={triage_filter}" if triage_filter else ""
    compare_btn = Button(
        "Compare",
        cls="px-2 py-1 text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/compare/{neighbor_id}{_compare_filter}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    # Thumbnail logic — prefer best quality, fall back to any available crop
    thumbnail_img = Div(cls="w-16 h-16 sm:w-20 sm:h-20 bg-slate-600 rounded")
    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
    crop_url = None
    best_fid = get_best_face_id(anchor_face_ids) if anchor_face_ids else None
    if best_fid:
        crop_url = resolve_face_image_url(best_fid, crop_files)
    if not crop_url:
        for fid in anchor_face_ids:
            crop_url = resolve_face_image_url(fid, crop_files)
            if crop_url:
                break
    if crop_url:
        thumbnail_img = Img(
            src=crop_url,
            alt=name,
            cls="w-16 h-16 sm:w-20 sm:h-20 object-cover rounded border border-slate-600 hover:scale-105 transition-transform",
            loading="lazy",
        )

    # Checkbox for bulk selection (linked to bulk form via hyperscript)
    # Uses property assignment (not attribute toggle) so FormData picks it up
    checkbox = (
        Input(
            type="checkbox",
            cls="w-4 h-4 rounded border-slate-500 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer flex-shrink-0",
            **{"_": f"on change set #bulk-{neighbor_id}.checked to my.checked"},
        )
        if (show_checkbox and can_merge)
        else None
    )

    # Determine the correct section for this neighbor based on its state
    neighbor_section = _section_for_state(neighbor.get("state", "INBOX"))

    # Community-aware navigation prefix (COMMUNITY-015)
    # If neighbor belongs to a different community, link to THAT community's pages
    _cross_slug = _identity_home_community_slug(neighbor_id, current_community)
    if _cross_slug:
        _nav_prefix = community_url_prefix(_cross_slug)
    else:
        _community_slug = current_community.get("slug") if current_community else None
        _nav_prefix = nav_prefix or community_url_prefix(_community_slug)

    # Navigation script: try to scroll if element exists, otherwise navigate to browse mode
    nav_script = f"on click set target to #identity-{neighbor_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target else go to url '{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}'"

    return Div(
        Div(
            checkbox,
            A(
                thumbnail_img,
                href=f"{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}",
                cls="flex-shrink-0 cursor-pointer hover:opacity-80",
                **{"_": nav_script},
            ),
            Div(
                Div(
                    A(
                        name,
                        href=f"{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}",
                        cls="font-medium text-slate-200 hover:text-blue-400 hover:underline cursor-pointer text-sm leading-tight",
                        **{"_": nav_script},
                    ),
                    Span(
                        f"{calibrated_pct}% match" if calibrated_pct is not None else similarity_label,
                        cls=f"text-xs px-2 py-0.5 rounded ml-2 {similarity_class}",
                    ),
                    _cross_community_badge(neighbor_id, current_community),
                    cls="flex items-center flex-wrap gap-1",
                ),
                # EXPLAINABILITY: Distance + confidence gap (how much closer than next-best)
                Div(
                    Span(
                        f"Dist: {distance:.2f}", cls="text-xs font-data text-slate-400 ml-2 bg-slate-700 px-1 rounded"
                    ),
                    Span(
                        f"+{confidence_gap}% gap",
                        cls="text-xs font-data text-emerald-400/70 ml-1 bg-emerald-900/30 px-1 rounded",
                    )
                    if confidence_gap > 0
                    else None,
                    Span(
                        f"Seen together in {co_occurrence} photo{'s' if co_occurrence != 1 else ''}",
                        cls="text-[10px] text-amber-400 italic ml-1",
                    )
                    if co_occurrence > 0
                    else None,
                    cls="flex items-center flex-wrap",
                ),
                cls="flex-1 min-w-0 ml-3",
            ),
            Div(
                compare_btn,
                merge_btn,
                Button(
                    "Not Same",
                    cls="px-2 py-1 text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
                    hx_post=f"{_nav_prefix}/api/identity/{target_identity_id}/reject/{neighbor_id}",
                    hx_target=f"#neighbor-{neighbor_id}",
                    hx_swap="outerHTML",
                ),
                share_button(
                    url=f"{_nav_prefix}/identify/{target_identity_id}/match/{neighbor_id}",
                    style="icon",
                    title="Are these the same person?",
                    text=f"Help identify: {name}",
                ),
                cls="flex items-center gap-1 sm:gap-2 flex-shrink-0 sm:ml-2 mt-2 sm:mt-0",
            ),
            cls="flex flex-wrap sm:flex-nowrap items-center gap-2",
        ),
        id=f"neighbor-{neighbor_id}",
        cls="p-3 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg overflow-hidden",
    )


def search_result_card(
    result: dict,
    target_identity_id: str,
    crop_files: set,
    user_role: str = "admin",
    target_name: str = "",
    nav_prefix: str = "",
) -> Div:
    """
    Card for a manual search result.
    Similar styling to neighbor_card but simpler (no distance/percentile).
    """
    result_id = result["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    raw_name = ensure_utf8_display(result["name"])
    name = raw_name or f"Identity {result_id[:8]}..."
    face_count = result.get("face_count", 0)
    preview_face_id = result.get("preview_face_id")

    # Thumbnail from preview_face_id
    thumbnail_img = Div(cls="w-10 h-10 bg-slate-600 rounded")
    if preview_face_id:
        crop_url = resolve_face_image_url(preview_face_id, crop_files)
        if crop_url:
            thumbnail_img = Img(src=crop_url, alt=name, cls="w-12 h-12 object-cover rounded border border-slate-600")

    # Compare button -- opens side-by-side comparison modal (same pattern as neighbor_card)
    compare_btn = Button(
        "Compare",
        cls="px-2 py-1 text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/compare/{result_id}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    # Merge button -- role-aware: admin merges directly, contributor suggests
    if user_role == "contributor":
        merge_btn = Button(
            "Suggest Merge",
            cls="px-2 py-1 text-xs font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/suggest-merge/{result_id}",
            hx_target=f"#search-result-{result_id}",
            hx_swap="outerHTML",
            data_auth_action="suggest a merge",
        )
    else:
        _confirm_msg = (
            f"Merge {name} into {target_name}? All faces will be combined."
            if target_name and not target_name.startswith("Unidentified")
            else "Merge these identities? This can be undone."
        )
        merge_btn = Button(
            "Merge",
            cls="px-2 py-1 text-xs font-bold border border-blue-500/50 text-blue-400 rounded hover:bg-blue-500/20",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search",
            hx_target=f"#identity-{target_identity_id}",
            hx_swap="outerHTML",
            data_auth_action="merge these identities",
            hx_confirm=_confirm_msg,
        )

    # Navigation hyperscript (same as neighbor_card)
    nav_script = f"on click set target to #identity-{result_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target"

    return Div(
        Div(
            A(
                thumbnail_img,
                href=f"#identity-{result_id}",
                cls="flex-shrink-0 cursor-pointer hover:opacity-80",
                **{"_": nav_script},
            ),
            Div(
                A(
                    name,
                    href=f"#identity-{result_id}",
                    cls="font-medium text-slate-200 truncate text-sm hover:text-blue-400 hover:underline cursor-pointer",
                    **{"_": nav_script},
                ),
                Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-400 ml-2"),
                cls="flex items-center ml-2 flex-1 min-w-0",
            ),
            Div(compare_btn, merge_btn, cls="flex items-center gap-1 flex-shrink-0 ml-2"),
            cls="flex items-center",
        ),
        id=f"search-result-{result_id}",
        cls="p-2 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg",
    )


def search_results_panel(
    results: list,
    target_identity_id: str,
    crop_files: set,
    user_role: str = "admin",
    target_name: str = "",
    nav_prefix: str = "",
) -> Div:
    """Panel showing manual search results."""
    if not results:
        return Div(
            P("No matching identities found.", cls="text-slate-400 italic text-sm"),
            id=f"search-results-{target_identity_id}",
        )

    cards = [
        search_result_card(
            r, target_identity_id, crop_files, user_role=user_role, target_name=target_name, nav_prefix=nav_prefix
        )
        for r in results
    ]
    return Div(*cards, id=f"search-results-{target_identity_id}")


def manual_search_section(identity_id: str, nav_prefix: str = "") -> Div:
    """
    Manual search input and results container.
    Positioned in neighbors sidebar after Load More, before Rejected section.
    """
    return Div(
        H5("Manual Search", cls="text-sm font-semibold text-slate-300 mb-2"),
        Input(
            type="text",
            name="q",
            placeholder="Search by name...",
            cls="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-600 text-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder-slate-500",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/search",
            hx_trigger="keyup changed delay:300ms",
            hx_target=f"#search-results-{identity_id}",
            hx_include="this",
        ),
        Div(id=f"search-results-{identity_id}", cls="mt-2"),
        cls="mt-4 pt-3 border-t border-slate-600",
    )


def neighbors_sidebar(
    identity_id: str,
    neighbors: list,
    crop_files: set,
    offset: int = 0,
    has_more: bool = False,
    rejected_count: int = 0,
    user_role: str = "admin",
    from_focus: bool = False,
    focus_section: str = "",
    target_name: str = "",
    container_id: str = "",
    current_community: dict | None = None,
    nav_prefix: str = "",
) -> Div:
    # container_id allows targeting the browse expansion panel or the focus sidebar
    _target_id = container_id or f"neighbors-{identity_id}"
    close_btn = None
    if container_id and container_id.startswith("expand-"):
        close_btn = Button(
            NotStr("&times;"),
            cls="panel-close text-slate-400 hover:text-white text-xl font-bold bg-transparent border-0 p-1 leading-none",
            **{
                "_": f"on click set innerHTML of #{container_id} to '' then remove .find-similar-active from closest .identity-card"
            },
            type="button",
            title="Close",
        )
    toggle_btn = Button(
        "▾ Collapse",
        cls="text-sm text-slate-400 hover:text-slate-300",
        id=f"neighbors-toggle-{identity_id}",
        type="button",
        **{
            "_": f"on click toggle .hidden on #neighbors-body-{identity_id} then if my.textContent == '▸ Expand' set my.textContent to '▾ Collapse' else set my.textContent to '▸ Expand'"
        },
    )
    if not neighbors:
        return Div(
            Div(
                H4("Similar Identities", cls="text-lg font-serif font-bold text-white"),
                toggle_btn,
                close_btn,
                cls="flex items-center justify-between mb-3",
            ),
            Div(
                P("No similar identities.", cls="text-slate-400 italic"),
                cls="flex items-center justify-between",
            ),
            manual_search_section(identity_id, nav_prefix=nav_prefix),
            cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600 overflow-hidden",
        )

    # Mergeable neighbors get checkboxes for bulk operations
    mergeable = [n for n in neighbors if n.get("can_merge")]
    cards = [
        neighbor_card(
            n,
            identity_id,
            crop_files,
            user_role=user_role,
            from_focus=from_focus,
            focus_section=focus_section,
            target_name=target_name,
            current_community=current_community,
            nav_prefix=nav_prefix,
        )
        for n in neighbors
    ]
    _focus_section_param = f"&focus_section={focus_section}" if focus_section else ""
    _container_param = f"&container_id={container_id}" if container_id else ""
    focus_param = f"&from_focus=true{_focus_section_param}" if from_focus else ""
    load_more = (
        Button(
            "Load More",
            cls="w-full text-sm text-indigo-400 hover:text-indigo-300 py-2 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?offset={offset + len(neighbors)}{focus_param}{_container_param}",
            hx_target=f"#{_target_id}",
            hx_swap="innerHTML",
        )
        if has_more
        else None
    )

    # Bulk actions (only if there are mergeable neighbors)
    bulk_actions = None
    if len(mergeable) > 1:
        select_all_script = (
            "on click "
            "set cbs to <input[name='bulk_ids']/> in closest <form/> "
            "repeat for cb in cbs set cb.checked to my.checked end"
        )
        bulk_actions = Form(
            # Hidden inputs for each mergeable neighbor (checkboxes)
            Div(
                Label(
                    Input(type="checkbox", cls="mr-2 accent-blue-500", **{"_": select_all_script}),
                    Span("Select All", cls="text-xs text-slate-400"),
                    cls="flex items-center cursor-pointer mb-2",
                ),
                *[
                    Div(
                        Input(
                            type="checkbox",
                            name="bulk_ids",
                            value=n["identity_id"],
                            cls="hidden bulk-checkbox",
                            id=f"bulk-{n['identity_id']}",
                        ),
                        cls="hidden",
                    )
                    for n in mergeable
                ],
                cls="",
            ),
            Div(
                Button(
                    "Merge Selected",
                    type="button",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/bulk-merge",
                    hx_include="closest form",
                    hx_target=f"#{_target_id}",
                    hx_swap="innerHTML",
                    cls="px-3 py-1.5 text-xs font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
                ),
                Button(
                    "Not Same Selected",
                    type="button",
                    hx_post=f"{nav_prefix}/api/identity/{identity_id}/bulk-reject",
                    hx_include="closest form",
                    hx_target=f"#{_target_id}",
                    hx_swap="innerHTML",
                    cls="px-3 py-1.5 text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
                ),
                cls="flex gap-2",
            ),
            cls="mb-3 p-2 bg-slate-600/50 rounded border border-slate-600",
        )

    # Manual search section - between Load More and Rejected
    manual_search = manual_search_section(identity_id, nav_prefix=nav_prefix)

    rejected = (
        Div(
            Div(
                Span(f"{rejected_count} hidden matches", cls="text-xs text-slate-400 italic"),
                Button(
                    "Review",
                    cls="text-xs text-indigo-400 hover:text-indigo-300 ml-2",
                    hx_get=f"{nav_prefix}/api/identity/{identity_id}/rejected",
                    hx_target=f"#rejected-list-{identity_id}",
                    hx_swap="innerHTML",
                ),
                cls="flex items-center justify-between",
            ),
            Div(id=f"rejected-list-{identity_id}"),
            cls="mt-4 pt-3 border-t border-slate-600",
        )
        if rejected_count > 0
        else None
    )

    return Div(
        Div(
            H4("Similar Identities", cls="text-lg font-serif font-bold text-white"),
            toggle_btn,
            close_btn,
            cls="flex items-center justify-between mb-3",
        ),
        Div(
            bulk_actions,
            Div(*cards),
            Div(load_more, cls="mt-3") if load_more else None,
            manual_search,
            rejected,
            id=f"neighbors-body-{identity_id}",
        ),
        cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600 overflow-hidden",
    )


def name_display(
    identity_id: str, name: str, is_admin: bool = True, generation_qualifier: str = "", nav_prefix: str = ""
) -> Div:
    """
    Identity name display with edit button (admin only).
    Returns the name header component that can be swapped for inline editing.
    """
    # UI BOUNDARY: sanitize name for safe rendering
    safe_name = ensure_utf8_display(name)
    display_name = safe_name or f"Identity {identity_id[:8]}..."
    if generation_qualifier:
        display_name = f"{display_name} {generation_qualifier}"
    edit_btn = (
        Button(
            "Edit",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/rename-form",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-2 text-xs text-slate-400 hover:text-slate-300 underline",
            type="button",
        )
        if is_admin
        else None
    )
    return Div(
        H3(display_name, cls="text-lg font-display font-bold text-white"),
        edit_btn,
        id=f"name-{identity_id}",
        cls="flex items-center",
    )


FACES_PER_PAGE = 8


def _build_face_cards_for_entries(face_entries, crop_files, identity_id, can_detach, is_admin=True):
    """Build face card elements from a list of face entries."""
    cards = []
    for face_entry in face_entries:
        if isinstance(face_entry, str):
            face_id = face_entry
            era = None
        else:
            face_id = face_entry.get("face_id", "")
            era = face_entry.get("era_bin")

        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            photo_id = get_photo_id_for_face(face_id)
            cards.append(
                face_card(
                    face_id=face_id,
                    crop_url=crop_url,
                    era=era,
                    identity_id=identity_id,
                    photo_id=photo_id,
                    show_detach=can_detach,
                    is_admin=is_admin,
                )
            )
        else:
            cards.append(
                Div(
                    Div(
                        Span("?", cls="text-4xl text-slate-500"),
                        cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center",
                    ),
                    P("Image unavailable", cls="text-xs text-slate-400 mt-1"),
                    P(f"ID: {face_id[:12]}...", cls="text-xs font-data text-slate-500"),
                    cls="face-card",
                    id=make_css_id(face_id),
                )
            )
    return cards


def _face_pagination_controls(identity_id: str, page: int, total_faces: int, sort: str = "date", nav_prefix: str = ""):
    """Build pagination controls for face grid carousel."""
    total_pages = (total_faces + FACES_PER_PAGE - 1) // FACES_PER_PAGE
    if total_pages <= 1:
        return None

    start = page * FACES_PER_PAGE + 1
    end = min((page + 1) * FACES_PER_PAGE, total_faces)

    prev_btn = (
        Button(
            Span("<", cls="text-lg"),
            cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces?page={page - 1}&sort={sort}",
            hx_target=f"#faces-{identity_id}",
            hx_swap="outerHTML",
            type="button",
        )
        if page > 0
        else Button(
            Span("<", cls="text-lg"),
            cls="px-2 py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
            type="button",
            disabled=True,
        )
    )

    next_btn = (
        Button(
            Span(">", cls="text-lg"),
            cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces?page={page + 1}&sort={sort}",
            hx_target=f"#faces-{identity_id}",
            hx_swap="outerHTML",
            type="button",
        )
        if page < total_pages - 1
        else Button(
            Span(">", cls="text-lg"),
            cls="px-2 py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
            type="button",
            disabled=True,
        )
    )

    return Div(
        prev_btn,
        Span(f"{start}-{end} of {total_faces}", cls="text-xs text-slate-400 mx-2"),
        next_btn,
        cls="flex items-center justify-center gap-1 mt-3",
    )


def identity_card_compact(
    identity: dict,
    crop_files: set,
    is_admin: bool = True,
) -> Div:
    """Deprecated: delegates to identity_card(show_triage=True) for backward compat."""
    return identity_card(identity, crop_files, show_triage=True, is_admin=is_admin)


def identity_card(
    identity: dict,
    crop_files: set,
    lane_color: str = "stone",
    show_actions: bool = False,
    is_admin: bool = True,
    show_triage: bool = False,
    nav_prefix: str = "",
) -> Div:
    """
    Identity group card showing all faces (anchors + candidates).
    UX Intent: Group context with individual face visibility.
    Action buttons only shown for admin users.
    Shows first page of faces (max FACES_PER_PAGE) with pagination if more exist.
    """
    identity_id = identity["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or f"Identity {identity_id[:8]}..."
    state = identity["state"]

    # Combine anchors (confirmed) and candidates (proposed) for display
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    total_faces = len(all_face_ids)

    # Show detach button only if identity has more than one face AND user is admin
    can_detach = total_faces > 1 and is_admin

    # Show only first page of faces
    page_entries = all_face_ids[:FACES_PER_PAGE]
    face_cards = _build_face_cards_for_entries(page_entries, crop_files, identity_id, can_detach, is_admin=is_admin)

    if not face_cards:
        return None

    border_colors = {
        "blue": "border-l-blue-500",
        "emerald": "border-l-emerald-500",
        "amber": "border-l-amber-500",
        "red": "border-l-red-500",
        "stone": "border-l-stone-400",
        "rose": "border-l-rose-500",
    }

    # Sort dropdown for face ordering
    sort_dropdown = Select(
        Option("Sort by Date", value="date", selected=True),
        Option("Sort by Outlier", value="outlier"),
        cls="text-xs border border-slate-600 bg-slate-700 text-slate-300 rounded px-2 py-1",
        hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces",
        hx_target=f"#faces-{identity_id}",
        hx_swap="outerHTML",
        name="sort",
        hx_trigger="change",
    )

    # --- Compact pill-style action buttons for card layout (DD-005) ---
    _pill = "px-2.5 py-1 text-xs font-medium rounded-full transition-all duration-200"

    # View All Photos button (opens photo modal)
    view_all_photos_btn = (
        Button(
            "Photos",
            cls=f"{_pill} bg-amber-500/15 text-amber-300 hover:bg-amber-500/25",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index=0",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )
        if total_faces > 0
        else None
    )

    # Faces button — for multi-face identities, opens the admin face gallery
    _faces_detail_id = f"admin-details-{make_css_id(identity_id)}"
    faces_btn = None
    if total_faces > 1:
        faces_btn = Button(
            f"Faces ({total_faces})",
            cls=f"{_pill} bg-purple-500/15 text-purple-300 hover:bg-purple-500/25",
            type="button",
            data_testid="faces-button",
            onclick=f"var el=document.getElementById('{_faces_detail_id}');if(el)el.open=true;",
        )

    # View Public Page link (Gap 3: always show Profile link)
    view_public_link = A(
        "Profile",
        href=f"{nav_prefix}/person/{identity_id}",
        cls=f"{_pill} text-slate-400 hover:text-indigo-300 hover:bg-indigo-500/15",
    )

    _id_css = make_css_id(identity_id)

    # GEDCOM Tree link button (B3)
    gedcom_tree_btn = None
    if is_admin and state == "CONFIRMED":
        gedcom_links = _load_gedcom_face_links()
        gedcom_link = gedcom_links.get(identity_id)
        if gedcom_link:
            gedcom_tree_btn = A(
                "Tree",
                href=f"{nav_prefix}/tree?person={identity_id}",
                cls=f"{_pill} text-emerald-300 hover:bg-emerald-500/15",
            )
        else:
            # Tree icon (inline SVG, 12x12)
            _tree_icon = NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
                'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                'stroke-linejoin="round" style="display:inline;vertical-align:-1px;margin-right:3px">'
                '<path d="M17 18a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2"/>'
                '<rect width="18" height="18" x="3" y="3" rx="2"/>'
                '<circle cx="12" cy="10" r="3"/>'
                "</svg>"
            )
            gedcom_tree_btn = Button(
                _tree_icon,
                "Link Tree",
                hx_get=f"{nav_prefix}/api/cluster-review/gedcom-panel?identity_id={identity_id}",
                hx_target=f"#expand-{_id_css}",
                hx_swap="innerHTML",
                type="button",
                title="Connect this person to their family tree record",
                cls=f"{_pill} text-amber-300 bg-amber-500/10 hover:bg-amber-500/20",
            )

    # Find Similar — admin: inline expansion with full neighbors_sidebar, public: full-page link
    if is_admin:
        find_similar_btn = Button(
            "Similar",
            cls=f"{_pill} bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?container_id=expand-{_id_css}",
            hx_target=f"#expand-{_id_css}",
            hx_swap="innerHTML",
            type="button",
            **{"_": "on click toggle .find-similar-active on closest .identity-card"},
        )
    else:
        find_similar_btn = A(
            "Similar",
            href=f"{nav_prefix}/people/{identity_id}/similar",
            cls=f"{_pill} bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25",
        )

    proposal_count = _get_proposal_target_count(identity_id) if is_admin else 0
    review_proposals_btn = (
        A(
            f"Proposals ({proposal_count})",
            href=f"{nav_prefix}/admin/upload-review#identity-group-{identity_id}",
            cls=f"{_pill} bg-amber-500/15 text-amber-300 hover:bg-amber-500/25",
            data_testid="identity-card-review-proposals",
        )
        if proposal_count > 0
        else None
    )

    # Pagination controls
    pagination = _face_pagination_controls(identity_id, 0, total_faces, "date", nav_prefix=nav_prefix)

    # Badge for merged-unnamed identities (multiple faces but no human name)
    grouped_badge = None
    if total_faces > 1 and (name.startswith("Unidentified") or name.startswith("Identity ")):
        grouped_badge = Span(
            f"Grouped ({total_faces} faces)",
            cls="text-xs px-2 py-0.5 rounded bg-purple-600/20 text-purple-300 border border-purple-500/30 ml-2",
        )

    # Quality label from best face for compact header display
    best_face_id = get_best_face_id(all_face_ids) if all_face_ids else None
    best_quality = None
    if best_face_id:
        best_quality = get_face_quality(best_face_id)
    quality_label_text = None
    if best_quality and best_quality > 0:
        quality_label_text = (
            "Excellent"
            if best_quality >= 30
            else "Good"
            if best_quality >= 20
            else "Fair"
            if best_quality >= 10
            else "Low"
        )

    # --- Photo-dominant card design (DD-005) ---
    # Hero face: use the BEST QUALITY face, not just first
    best_face = best_face_id or (all_face_ids[0] if all_face_ids else None)
    hero_crop_url = resolve_face_image_url(best_face, crop_files) if best_face else None
    person_href = (
        f"{nav_prefix}/person/{identity_id}" if state == "CONFIRMED" else f"{nav_prefix}/identify/{identity_id}"
    )

    # Build cycle URLs for face cycling carousel (up to 5 faces)
    cycle_urls = []
    if hero_crop_url:
        cycle_urls.append(hero_crop_url)
    best_face_str = best_face if isinstance(best_face, str) else ""
    for fid_entry in all_face_ids:
        fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
        if fid == best_face_str:
            continue  # already added as hero
        url = resolve_face_image_url(fid, crop_files)
        if url:
            cycle_urls.append(url)
        if len(cycle_urls) >= 5:
            break
    has_cycling = len(cycle_urls) > 1

    # Share button for this person — show for any named identity
    person_share_btn = (
        share_button(
            url=f"{nav_prefix}/person/{identity_id}",
            style="icon",
            title=f"{name} — Jews of Rhodes Heritage Archive",
            text=f"Do you recognize {name}? Help us identify people in our heritage photo archive.",
        )
        if not name.startswith("Unidentified") and not name.startswith("Identity ")
        else None
    )

    # Multi-face gallery thumbnails for identities with 3+ faces
    multi_face_gallery = None
    if total_faces >= 3:
        # Get up to 3 additional faces (beyond the hero face)
        extra_faces = []
        for fid_entry in all_face_ids:
            fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
            if fid == best_face_str:
                continue  # skip the hero face
            extra_url = resolve_face_image_url(fid, crop_files)
            if extra_url:
                extra_faces.append(extra_url)
            if len(extra_faces) >= 3:
                break

        if extra_faces:
            thumb_items = []
            for idx, eurl in enumerate(extra_faces):
                thumb_items.append(
                    Img(
                        src=eurl,
                        alt=f"{name} face {idx + 2}",
                        cls="w-8 h-8 rounded-full object-cover border-2 border-slate-800"
                        " shadow-sm hover:scale-110 transition-transform",
                        loading="lazy",
                    )
                )
            remaining = total_faces - 1 - len(extra_faces)
            if remaining > 0:
                thumb_items.append(
                    Span(
                        f"+{remaining}",
                        cls="w-8 h-8 rounded-full bg-slate-700 border-2 border-slate-800"
                        " text-[10px] text-slate-300 font-medium flex items-center justify-center",
                    )
                )
            multi_face_gallery = A(
                *thumb_items,
                href=person_href,
                cls="flex items-center -space-x-2 mt-1.5 cursor-pointer",
                title=f"View all {total_faces} faces",
            )

    # Face cycling arrows (prev/next) — only for multi-face identities
    cycle_prev_btn = None
    cycle_next_btn = None
    cycle_dots = None
    if has_cycling:
        _arrow_cls = (
            "absolute top-1/2 -translate-y-1/2 z-10 w-7 h-7 flex items-center justify-center"
            " bg-black/60 hover:bg-black/80 text-white rounded-full text-sm font-bold"
            " opacity-60 group-hover:opacity-100 transition-opacity duration-200 cursor-pointer"
            " backdrop-blur-sm select-none"
        )
        cycle_prev_btn = Button(
            NotStr("&#8249;"),
            cls=f"{_arrow_cls} left-1.5",
            data_action="face-cycle-prev",
            type="button",
            aria_label="Previous face",
        )
        cycle_next_btn = Button(
            NotStr("&#8250;"),
            cls=f"{_arrow_cls} right-1.5",
            data_action="face-cycle-next",
            type="button",
            aria_label="Next face",
        )
        dots = []
        for i in range(len(cycle_urls)):
            dot_cls = "w-1.5 h-1.5 rounded-full transition-all duration-200 " + (
                "bg-white" if i == 0 else "bg-white/40"
            )
            dots.append(Span(cls=dot_cls, data_dot_index=str(i)))
        cycle_dots = Div(
            *dots,
            cls="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1 z-10"
            " opacity-70 group-hover:opacity-100 transition-opacity duration-200",
            data_cycle_dots="true",
        )

    hero_section = Div(
        # Face image — THE STAR of the card
        A(
            Img(
                src=hero_crop_url,
                alt=name,
                cls="w-full aspect-square object-cover rounded-xl transition-all duration-300",
                loading="lazy",
                data_cycle_img="true",
            )
            if hero_crop_url
            else Div(
                Span("?", cls="text-5xl text-slate-600"),
                cls="w-full aspect-square bg-slate-800 rounded-xl flex items-center justify-center",
            ),
            href=person_href,
            cls="block overflow-hidden rounded-xl",
        ),
        # Face cycling arrows
        cycle_prev_btn,
        cycle_next_btn,
        # Face cycling dot indicators
        cycle_dots,
        # Face count badge (top-right overlay)
        Span(
            f"{total_faces}",
            cls="absolute top-2 right-2 w-7 h-7 flex items-center justify-center"
            " bg-amber-600/90 text-white text-xs font-bold rounded-full"
            " shadow-lg backdrop-blur-sm",
        )
        if total_faces > 1
        else None,
        # Share button (top-left overlay)
        Span(
            person_share_btn,
            cls="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200",
        )
        if person_share_btn
        else None,
        # Multi-face thumbnail strip (bottom overlay)
        Div(
            multi_face_gallery,
            cls="absolute bottom-2 left-2 right-2",
        )
        if multi_face_gallery
        else None,
        cls="relative group",
        data_cycle_urls="|".join(cycle_urls) if has_cycling else None,
        data_cycle_index="0" if has_cycling else None,
    )

    # Name + state row
    # For "Unidentified Person NNNN", show "Person NNNN" to prevent truncation
    display_name = name
    if name.startswith("Unidentified Person "):
        display_name = "Person " + name[len("Unidentified Person ") :]
    name_section = Div(
        A(
            display_name,
            href=person_href,
            cls="text-sm font-semibold text-slate-100 hover:text-amber-300 transition-colors block truncate",
            title=name,
        ),
        Div(
            state_badge(state),
            _proposal_badge_inline(identity_id),
            _promotion_badge(identity),
            grouped_badge,
            cls="flex items-center gap-1.5 mt-1",
        ),
        cls="mt-3 px-1",
    )

    # Action buttons — clean icon pills
    action_section = Div(
        view_all_photos_btn,
        faces_btn,
        find_similar_btn,
        review_proposals_btn,
        gedcom_tree_btn,
        view_public_link,
        cls="flex flex-wrap gap-1.5 mt-3 px-1",
    )

    # Triage buttons — visible labeled row for quick review (when show_triage=True)
    triage_section = None
    if show_triage and is_admin and state in ("INBOX", "PROPOSED", "SKIPPED"):
        _triage_pill = "px-3 py-1.5 text-xs font-bold rounded-full transition-all duration-200 min-h-[32px]"
        confirm_url = (
            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
        )
        reject_url = (
            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
        )
        triage_btns = [
            Button(
                "\u2713 Confirm",
                cls=f"{_triage_pill} bg-emerald-600 text-white hover:bg-emerald-500",
                hx_post=confirm_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                type="button",
            ),
        ]
        if state in ("INBOX", "PROPOSED"):
            triage_btns.append(
                Button(
                    "\u23f8 Skip",
                    cls=f"{_triage_pill} bg-amber-600/80 text-white hover:bg-amber-500",
                    hx_post=f"{nav_prefix}/identity/{identity_id}/skip",
                    hx_target=f"#identity-{identity_id}",
                    hx_swap="outerHTML",
                    type="button",
                )
            )
        triage_btns.append(
            Button(
                "\u2717 Reject",
                cls=f"{_triage_pill} border border-red-500/60 text-red-400 hover:bg-red-500/20",
                hx_post=reject_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                type="button",
            )
        )
        triage_section = Div(
            *triage_btns,
            cls="flex flex-wrap gap-1.5 mt-2 px-1",
        )

    # Admin tools — collapsible to keep cards clean
    admin_tools = None
    if is_admin:
        admin_tools = Details(
            Summary(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/></svg>'
                ),
                cls="list-none cursor-pointer mt-2 px-1 flex items-center gap-1"
                " text-slate-500 hover:text-slate-300 transition-colors select-none",
            ),
            Div(
                Div(
                    sort_dropdown,
                    review_action_buttons(identity_id, state, is_admin=is_admin, nav_prefix=nav_prefix),
                    cls="flex flex-wrap items-center gap-2",
                ),
                _identity_metadata_display(identity, is_admin=is_admin),
                Div(
                    Div(
                        *face_cards,
                        cls="grid grid-cols-3 sm:grid-cols-4 gap-2",
                    ),
                    pagination,
                    id=f"faces-{identity_id}",
                    cls="mt-2",
                )
                if total_faces > 1
                else None,
                cls="mt-2 px-1 pt-2 border-t border-slate-700/50",
            ),
            id=_faces_detail_id,
        )

    return Div(
        hero_section,
        name_section,
        action_section,
        triage_section,
        admin_tools,
        cls="identity-card bg-slate-800/60 border border-slate-700/50 rounded-2xl p-3"
        " hover:border-slate-600 hover:bg-slate-800/80 transition-all duration-300"
        " hover:shadow-lg hover:shadow-slate-900/50",
        id=f"identity-{identity_id}",
        data_name=(raw_name or "").lower(),
    )


def photo_modal() -> Div:
    """
    Modal container for photo context viewer.
    Hidden by default, shown via HTMX when "View Photo" is clicked.

    Z-index hierarchy:
    - Confirm modal: z-[10002] (above compare — always topmost interactive)
    - Toast container: z-[10001] (above all content modals)
    - Compare modal: z-[10000] (above photo modal)
    - Photo modal: z-[9999] (above page content)
    - Backdrop: absolute, no z-index (first child, renders behind content)
    - Content: relative, no z-index (second child, renders above backdrop)
    """
    return Div(
        # Backdrop - absolute within the fixed parent, click to close
        Div(
            cls="absolute inset-0 bg-black/80",
            **{"_": "on click add .hidden to #photo-modal"},
        ),
        # Modal content - relative positioning to sit above backdrop
        Div(
            # Header with close button
            Div(
                H2("Photo Context", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #photo-modal"},
                    type="button",
                    aria_label="Close modal",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            # Content area (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="photo-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-5xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700",
        ),
        id="photo-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[9999]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
        tabindex="-1",
    )


def compare_modal() -> Div:
    """
    Side-by-side comparison modal for evaluating merge candidates.
    Shows the source identity's best face alongside the neighbor's best face.
    """
    return Div(
        # Backdrop
        Div(
            cls="absolute inset-0 bg-black/85",
            **{"_": "on click add .hidden to #compare-modal"},
        ),
        # Content
        Div(
            # Header
            Div(
                H2("Compare Faces", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #compare-modal"},
                    type="button",
                    aria_label="Close comparison",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            # Comparison content (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="compare-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-[90vw] lg:max-w-7xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700",
        ),
        id="compare-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[10000]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def login_modal() -> Div:
    """Login modal for unauthenticated HTMX action attempts.
    Shown by htmx:beforeSwap handler when server returns 401."""
    google_url = get_oauth_url("google")
    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click add .hidden to #login-modal"}),
        Div(
            Div(
                H2("Sign in to continue", cls="text-xl font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #login-modal"},
                    type="button",
                    aria_label="Close",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            P("Sign in to contribute to the archive.", id="login-modal-message", cls="text-slate-400 mb-6 text-sm"),
            Form(
                Div(
                    Label("Email", fr="modal-email", cls="block text-sm mb-1 text-slate-300"),
                    Input(
                        type="email",
                        name="email",
                        id="modal-email",
                        required=True,
                        cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                    ),
                    cls="mb-4",
                ),
                Div(
                    Label("Password", fr="modal-password", cls="block text-sm mb-1 text-slate-300"),
                    Input(
                        type="password",
                        name="password",
                        id="modal-password",
                        required=True,
                        cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                    ),
                    cls="mb-4",
                ),
                Button(
                    "Sign In",
                    type="submit",
                    cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
                ),
                Div(id="login-modal-error", cls="text-red-400 text-sm mt-2"),
                hx_post="/login/modal",
                hx_target="#login-modal-error",
                hx_swap="innerHTML",
            ),
            # Google OAuth divider + button
            Div(
                Div(cls="flex-grow border-t border-slate-600"),
                Span("or", cls="px-4 text-slate-500 text-sm"),
                Div(cls="flex-grow border-t border-slate-600"),
                cls="flex items-center my-4",
            )
            if google_url
            else None,
            A(
                NotStr(
                    '<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'
                ),
                Span("Sign in with Google"),
                href=google_url or "#",
                style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
                "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
                "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
                "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
            )
            if google_url
            else None,
            Div(
                P(A("Forgot password?", href="/forgot-password", cls="text-blue-400 hover:underline"), cls="text-sm"),
                P(
                    "No account? ",
                    A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                    cls="text-sm text-slate-400",
                ),
                cls="mt-4 text-center space-y-1",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700",
        ),
        id="login-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9998]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def _guest_or_login_modal(form_data: dict) -> Div:
    """Modal offering anonymous guest submission or sign-in to save.

    form_data: dict of original annotation form fields to preserve.
    Returns a modal Div that replaces #guest-or-login-modal.
    """
    # Build hidden inputs from original form data
    hidden_fields = []
    for key, val in form_data.items():
        if val is not None:
            hidden_fields.append(Input(type="hidden", name=key, value=str(val)))

    google_url = get_oauth_url("google")

    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click remove #guest-or-login-modal's children"}),
        Div(
            Div(
                H2("Save your suggestion", cls="text-xl font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click remove #guest-or-login-modal's children"},
                    type="button",
                    aria_label="Close",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            P("Your suggestion will be reviewed by a family member.", cls="text-slate-400 mb-6 text-sm"),
            # Option 1: Continue as guest
            Form(
                *hidden_fields,
                Button(
                    "Continue as guest",
                    type="submit",
                    cls="w-full p-2 bg-emerald-600 hover:bg-emerald-700 rounded text-white font-medium",
                ),
                P("Your suggestion will be saved anonymously.", cls="text-xs text-slate-500 mt-1 text-center"),
                hx_post="/api/annotations/guest-submit",
                hx_target="#guest-or-login-modal",
                hx_swap="innerHTML",
            ),
            # Divider
            Div(
                Div(cls="flex-grow border-t border-slate-600"),
                Span("or", cls="px-4 text-slate-500 text-sm"),
                Div(cls="flex-grow border-t border-slate-600"),
                cls="flex items-center my-4",
            ),
            # Option 2: Sign in to save
            Form(
                *[Input(type="hidden", name=k, value=str(v)) for k, v in form_data.items() if v is not None],
                Button(
                    "Sign in to save",
                    type="submit",
                    cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
                ),
                P("Track your contributions with your account.", cls="text-xs text-slate-500 mt-1 text-center"),
                hx_post="/api/annotations/stash-and-login",
                hx_target="#guest-or-login-modal",
                hx_swap="innerHTML",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700",
        ),
        id="guest-or-login-modal",
        cls="fixed inset-0 flex items-center justify-center p-4 z-[10000]",
        **{"_": "on keydown[key=='Escape'] remove my children"},
    )


def _get_onboarding_surnames() -> list[str]:
    """Get canonical surname list from surname_variants.json for the onboarding grid."""
    variants_path = Path(__file__).resolve().parent.parent / "data" / "surname_variants.json"
    if not variants_path.exists():
        return []
    try:
        with open(variants_path) as f:
            data = json.load(f)
        return [g["canonical"] for g in data.get("variant_groups", []) if g.get("canonical")]
    except Exception:
        return []


def _welcome_banner() -> Div:
    """
    Dismissible welcome banner for first-time visitors (replaces modal wall).

    Shows a non-blocking top bar with context about the archive.
    Dismissed via X button; uses rhodesli_welcomed cookie (1 year).
    Content is immediately visible underneath — no overlay, no blocking.
    """
    return Div(
        Div(
            Div(
                Span("Welcome to Rhodesli", cls="font-semibold text-amber-100"),
                Span(" — ", cls="text-amber-300/60 hidden sm:inline"),
                Span(
                    "a heritage photo archive for the Jewish community of Rhodes. ",
                    cls="text-amber-200/80 hidden sm:inline",
                ),
                Span(
                    "Know someone in these photos? Tap their face to help identify them.",
                    cls="text-amber-200/80 hidden sm:inline",
                ),
                # Mobile: shorter copy
                Span(" — Tap a face to help identify someone.", cls="text-amber-200/80 sm:hidden"),
                cls="flex-1 text-sm",
            ),
            Button(
                Svg(
                    Path(d="M6 18L18 6M6 6l12 12"),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                    stroke_width="2",
                    stroke_linecap="round",
                    stroke_linejoin="round",
                ),
                type="button",
                cls="text-amber-300/60 hover:text-white ml-3 p-1 min-w-[28px] min-h-[28px] flex items-center justify-center",
                data_action="welcome-banner-dismiss",
                aria_label="Dismiss welcome banner",
            ),
            cls="max-w-6xl mx-auto px-4 sm:px-8 flex items-center",
        ),
        Script("""
            (function() {
                var welcomed = document.cookie.split(';').some(function(c) {
                    return c.trim().startsWith('rhodesli_welcomed=');
                });
                if (welcomed) {
                    var el = document.getElementById('welcome-banner');
                    if (el) el.remove();
                }
                document.addEventListener('click', function(e) {
                    var action = e.target.closest('[data-action="welcome-banner-dismiss"]');
                    if (action) {
                        document.cookie = 'rhodesli_welcomed=1; path=/; max-age=31536000; SameSite=Lax';
                        var banner = document.getElementById('welcome-banner');
                        if (banner) banner.remove();
                    }
                });
            })();
        """),
        id="welcome-banner",
        cls="bg-amber-900/40 border-b border-amber-700/30 py-2",
    )


def confirm_modal() -> Div:
    """Styled confirmation modal replacing native browser confirm().
    Shown by htmx:confirm event handler."""
    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click add .hidden to #confirm-modal"}),
        Div(
            P("", id="confirm-modal-message", cls="text-white text-lg mb-6"),
            Div(
                Button(
                    "Cancel",
                    id="confirm-modal-no",
                    type="button",
                    cls="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-500",
                ),
                Button(
                    "Confirm",
                    id="confirm-modal-yes",
                    type="button",
                    cls="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-500 font-bold",
                ),
                cls="flex justify-end gap-3",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-6 relative border border-slate-700",
        ),
        id="confirm-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[10002]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def lane_section(
    title: str,
    identities: list,
    crop_files: set,
    color: str,
    icon: str,
    show_actions: bool = False,
    lane_id: str = None,
) -> Div:
    """
    A swimlane for a specific identity state.
    UX Intent: Clear separation of epistemic states.
    """
    cards = []
    for identity in identities:
        card = identity_card(identity, crop_files, lane_color=color, show_actions=show_actions)
        if card:
            cards.append(card)

    bg_colors = {
        "blue": "bg-blue-900/20",
        "emerald": "bg-emerald-900/20",
        "amber": "bg-amber-900/20",
        "red": "bg-red-900/20",
        "stone": "bg-slate-800/50",
        "rose": "bg-rose-900/20",
    }

    # Fix: Always render the container ID even if empty, so OOB swaps have a target.
    content_area = (
        Div(*cards, id=lane_id, cls="min-h-[50px]")
        if cards
        else Div(
            P(f"No {title.lower()} identities", cls="text-slate-400 italic text-center py-8"),
            id=lane_id,
            cls="min-h-[50px]",
        )
    )

    return Div(
        # Lane header
        Div(
            Span(icon, cls="text-2xl"),
            H2(title, cls="text-xl font-serif font-bold text-white"),
            Span(f"({len(cards)})", cls="text-sm text-slate-400"),
            cls="flex items-center gap-3 mb-4 pb-2 border-b border-slate-700",
        ),
        # Cards or empty state
        content_area,
        cls=f"mb-8 p-4 rounded {bg_colors.get(color, '')}",
    )


# --- page routes extracted to app/page_routes.py (lines 8905-11241) ---


# --- identity routes extracted to app/identity_routes.py (lines 11243-11371) ---


# --- page routes extracted to app/page_routes.py (lines 11372-15177) ---


# --- identity routes extracted to app/identity_routes.py (lines 15178-15272) ---


# --- page routes extracted to app/page_routes.py (lines 15273-17484) ---


# =============================================================================
# ROUTES - YEAR ESTIMATION TOOL
# =============================================================================


# --- Photo Detective Evidence Display Components (PRD-022, Session 61) ---


def _evidence_card(category: str, cues: list) -> object:
    """Render a single evidence category card for Photo Detective display.

    Args:
        category: Evidence category name (e.g., 'print_format', 'fashion').
        cues: List of cue dicts with 'cue', 'strength', 'suggested_range'.
    """
    icons = {
        "print_format": "Print/Physical",
        "fashion": "Fashion/Grooming",
        "environment": "Environment",
        "technology": "Technology",
        "cultural": "Cultural Context",
    }
    strength_colors = {
        "strong": "text-emerald-400 bg-emerald-900/30",
        "moderate": "text-amber-400 bg-amber-900/30",
        "weak": "text-slate-400 bg-slate-700/30",
    }
    display_name = icons.get(category, category.replace("_", " ").title())
    if not cues:
        return None

    cue_items = []
    for cue in cues[:3]:  # Show top 3 cues per category
        strength = cue.get("strength", "moderate")
        color_cls = strength_colors.get(strength, strength_colors["moderate"])
        date_range = cue.get("suggested_range", [])
        range_text = f" ({date_range[0]}-{date_range[1]})" if len(date_range) == 2 else ""
        cue_items.append(
            Div(
                P(cue.get("cue", ""), cls="text-xs text-slate-300"),
                Span(f"{strength}{range_text}", cls=f"text-[10px] px-1.5 py-0.5 rounded-full {color_cls}"),
                cls="flex items-start justify-between gap-2 py-1",
            )
        )

    return Div(
        H4(display_name, cls="text-sm font-semibold text-white mb-2"),
        *cue_items,
        cls="bg-slate-800/40 rounded-lg p-3 border border-slate-700/30",
        data_testid=f"evidence-card-{category}",
    )


def _detective_evidence_section(label: dict) -> object:
    """Build Photo Detective evidence display from a Gemini date label.

    Args:
        label: Date label dict from date_labels.json (Gemini output).
    """
    if not label:
        return None

    evidence = label.get("evidence", {})
    if not evidence and not label.get("date_estimation", {}).get("evidence"):
        return None

    # Handle nested date_estimation structure
    if "date_estimation" in label:
        evidence = label["date_estimation"].get("evidence", {})

    cards = []
    for category in ("print_format", "fashion", "environment", "technology"):
        cues = evidence.get(category, [])
        card = _evidence_card(category, cues)
        if card:
            cards.append(card)

    # Location evidence card (from Gemini location analysis + GEDCOM reasoning)
    location_evidence = label.get("location_evidence", {})
    loc_items = []
    if location_evidence.get("place"):
        loc_items.append(
            Div(
                P(f"Location: {location_evidence['place']}", cls="text-xs text-amber-200 font-semibold"),
                Span(
                    f"Confidence: {location_evidence.get('confidence', 'unknown')}",
                    cls="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400",
                ),
                cls="flex items-start justify-between gap-2 py-1",
            )
        )
    if location_evidence.get("visual_evidence"):
        loc_items.append(
            Div(
                P("Visual evidence", cls="text-[10px] text-slate-500 uppercase tracking-wide"),
                P(location_evidence["visual_evidence"], cls="text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if location_evidence.get("biographical_evidence"):
        loc_items.append(
            Div(
                P("Genealogical context", cls="text-[10px] text-indigo-400 uppercase tracking-wide"),
                P(location_evidence["biographical_evidence"], cls="text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if location_evidence.get("missing_child_analysis"):
        loc_items.append(
            Div(
                P("Missing child analysis", cls="text-[10px] text-emerald-400 uppercase tracking-wide"),
                P(location_evidence["missing_child_analysis"], cls="text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if loc_items:
        cards.append(
            Div(
                H4("Geographic Analysis", cls="text-sm font-semibold text-white mb-2"),
                *loc_items,
                cls="bg-slate-800/40 rounded-lg p-3 border border-slate-700/30",
                data_testid="evidence-card-location",
            )
        )

    if not cards:
        return None

    # Model badge with timestamp
    model = label.get("model", label.get("_model", ""))
    model_badge = None
    if model:
        display_model = model.replace("gemini-", "Gemini ").replace("-preview", "")
        # Build timestamp string from reanalyzed_at or analyzed_at
        timestamp_str = ""
        analysis_ts = label.get("reanalyzed_at") or label.get("analyzed_at") or label.get("timestamp")
        if analysis_ts:
            try:
                from datetime import datetime

                if isinstance(analysis_ts, str):
                    # Try ISO format
                    dt = datetime.fromisoformat(analysis_ts.replace("Z", "+00:00"))
                    timestamp_str = f" on {dt.strftime('%b %-d, %Y')}"
            except (ValueError, TypeError):
                pass
        prompt_version = label.get("prompt_version", "")
        version_str = f" ({prompt_version})" if prompt_version else ""
        model_badge = Span(
            f"Analyzed with {display_model}{timestamp_str}{version_str}",
            cls="text-[10px] text-indigo-300 bg-indigo-900/30 px-2 py-1 rounded-full",
            data_testid="model-badge",
        )

    # Cultural context note
    cultural_note = label.get("cultural_lag_note") or (label.get("date_estimation", {}).get("cultural_lag_note"))

    return Div(
        Div(
            H3("Photo Detective Analysis", cls="text-base font-serif font-semibold text-white"),
            model_badge,
            cls="flex items-center justify-between mb-3",
        ),
        Div(*cards, cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        P(f"Cultural context: {cultural_note}", cls="text-xs text-slate-500 mt-3 italic") if cultural_note else None,
        cls="mt-6 p-4 bg-slate-800/20 rounded-lg border border-slate-700/20",
        data_testid="detective-evidence",
    )


def _progressive_refinement_badge(label: dict) -> object:
    """Show badge when estimate was refined with verified facts."""
    if not label:
        return None
    metadata = label.get("_metadata", label.get("metadata", {}))
    if not metadata.get("refinement"):
        return None

    fact_count = metadata.get("fact_count", 0)
    return Span(
        f"Refined with {fact_count} verified fact{'s' if fact_count != 1 else ''}",
        cls="text-[10px] text-amber-300 bg-amber-900/30 px-2 py-1 rounded-full",
        data_testid="refinement-badge",
    )


# --- page routes extracted to app/page_routes.py (lines 17672-19985) ---


# --- identity routes extracted to app/identity_routes.py (lines 19987-22399) ---


# --- page routes extracted to app/page_routes.py (lines 22400-22508) ---


# --- identity routes extracted to app/identity_routes.py (lines 22509-22556) ---


# --- engagement routes extracted to app/engagement_routes.py (lines 22557-22743) ---


# --- identity routes extracted to app/identity_routes.py (lines 22744-24152) ---


# --- engagement routes extracted to app/engagement_routes.py (lines 24153-25069) ---


# --- relationship routes extracted to app/relationship_routes.py (lines 25070-25962) ---


# Sync routes moved to sync_routes.py

# Match mode and FaceCompare routes moved to match_facecompare_routes.py


from app import page_routes  # noqa: E402, F401
from app import identity_routes  # noqa: E402, F401
from app import discoveries_routes  # noqa: E402, F401
from app import engagement_routes  # noqa: E402, F401
from app import relationship_routes  # noqa: E402, F401

# Backward-compat: tests/code that import helpers from app.main
_load_annotations = engagement_routes._load_annotations
_save_annotations = engagement_routes._save_annotations
_invalidate_annotations_cache = engagement_routes._invalidate_annotations_cache
_create_merge_suggestion = engagement_routes._create_merge_suggestion
_photo_metadata_display = engagement_routes._photo_metadata_display
_photo_annotations_section = engagement_routes._photo_annotations_section
_load_person_comments = engagement_routes._load_person_comments
_save_person_comments = engagement_routes._save_person_comments
_identity_metadata_display = engagement_routes._identity_metadata_display
_identity_annotations_section = engagement_routes._identity_annotations_section
_merge_annotations = engagement_routes._merge_annotations
_fire_recalibration_hook = engagement_routes._fire_recalibration_hook
_load_gedcom_matches = relationship_routes._load_gedcom_matches
_load_relationship_graph = relationship_routes._load_relationship_graph
_save_relationship_graph = relationship_routes._save_relationship_graph
_load_gedcom_individuals = relationship_routes._load_gedcom_individuals
_load_gedcom_individual = relationship_routes._load_gedcom_individual
_load_gedcom_individuals_by_ids = relationship_routes._load_gedcom_individuals_by_ids
_load_gedcom_face_links = relationship_routes._load_gedcom_face_links
_load_current_gedcom_relationship_edges = relationship_routes._load_current_gedcom_relationship_edges
_load_gedcom_relationship_edges_for_ids = relationship_routes._load_gedcom_relationship_edges_for_ids
_invalidate_gedcom_cache = relationship_routes._invalidate_gedcom_cache
_search_gedcom_individuals = relationship_routes._search_gedcom_individuals
_person_gedcom_link_section = relationship_routes._person_gedcom_link_section
_gedcom_link_panel = relationship_routes._gedcom_link_panel
_load_gedcom_versions = relationship_routes._load_gedcom_versions
_load_gedcom_enrichment_queue_count = relationship_routes._load_gedcom_enrichment_queue_count
_load_corrections_log = page_routes._load_corrections_log
_save_corrections_log = page_routes._save_corrections_log
_check_merged_identity = page_routes._check_merged_identity
_ping_supabase = page_routes._ping_supabase
_compute_landing_stats = page_routes._compute_landing_stats
_get_featured_photos = page_routes._get_featured_photos
landing_page = page_routes.landing_page
_personalized_discovery_banner = page_routes._personalized_discovery_banner
_load_identification_responses = page_routes._load_identification_responses
_save_identification_responses = page_routes._save_identification_responses
_load_photo_locations = page_routes._load_photo_locations
_load_social_graph = page_routes._load_social_graph
photo_view_content = page_routes.photo_view_content
public_photo_page = page_routes.public_photo_page
_compute_shared_photos = page_routes._compute_shared_photos
_generate_result_id = page_routes._generate_result_id
_get_match_response_counts = page_routes._get_match_response_counts
_load_comparison_results = page_routes._load_comparison_results
_match_community_summary = page_routes._match_community_summary
_save_compare_upload = page_routes._save_compare_upload
_save_comparison_result = page_routes._save_comparison_result
_sort_photos = page_routes._sort_photos
_upload_stage_item = page_routes._upload_stage_item
health = page_routes.health
_name_conflict_modal = identity_routes._name_conflict_modal
toast_with_merge_undo = identity_routes.toast_with_merge_undo
_post_merge_suggestions = identity_routes._post_merge_suggestions
_build_discovery_card = discoveries_routes._build_discovery_card
_resolve_identity_crop = discoveries_routes._resolve_identity_crop
_collection_slug = identity_routes._collection_slug
_collection_from_slug = identity_routes._collection_from_slug
_get_collections_data = identity_routes._get_collections_data

# Backward-compat: tests that import tree navigation helpers from app.main
_bfs_immediate_family = page_routes._bfs_immediate_family
_bfs_shortest_path = page_routes._bfs_shortest_path
_is_nuclear_family = page_routes._is_nuclear_family
compute_subtree_for_photo = page_routes.compute_subtree_for_photo
_share_script = page_routes._share_script
_upload_progress_script = page_routes._upload_progress_script
_load_photo_bytes = page_routes._load_photo_bytes

# Backward-compat: engagement route helpers accessed via _main_mod
_submit_pending_annotation = engagement_routes._submit_pending_annotation
_annotations_cache = engagement_routes._annotations_cache

# Backward-compat: relationship route helpers accessed via _main_mod
_gedcom_matches_cache = relationship_routes._gedcom_matches_cache
_gedcom_face_links_cache = relationship_routes._gedcom_face_links_cache

# Backward-compat: page route cache variables accessed by tests via main_mod
_comparison_results_cache = page_routes._comparison_results_cache
_match_rate_limit = page_routes._match_rate_limit
_photo_locations_cache = page_routes._photo_locations_cache

# --- Route module imports (triggers route registration via @rt decorators) ---
from app import compare_routes  # noqa: E402, F401
from app import estimate_routes  # noqa: E402, F401
from app import tools_routes  # noqa: E402, F401
from app import auth_routes  # noqa: E402, F401
from app import sync_routes  # noqa: E402, F401
from app import match_facecompare_routes  # noqa: E402, F401
from app import admin_routes  # noqa: E402, F401
from app import photo_routes  # noqa: E402, F401
from app import browse_routes  # noqa: E402, F401
from app import person_routes  # noqa: E402, F401
from app import event_routes  # noqa: E402, F401

# Backward-compat: tests that import person helpers from app.main still work
public_person_page = person_routes.public_person_page
_comment_rate_limit = person_routes._comment_rate_limit

# Backward-compat: tests that import admin helpers from app.main still work
_admin_nav_bar = admin_routes._admin_nav_bar
_load_activity_feed = admin_routes._load_activity_feed

# Backward-compat: tests that reference admin helpers via app.main
_compute_correction_priority = admin_routes._compute_correction_priority
_get_priority_reason = admin_routes._get_priority_reason

from app import notification_routes  # noqa: E402, F401
from app import upload_routes  # noqa: E402, F401
from app import cluster_review_routes  # noqa: E402, F401

# Re-run route priority after all route modules are imported
_reorder_routes_atomic()

if __name__ == "__main__":
    # Startup diagnostics
    print("=" * 60)
    print("RHODESLI STARTUP")
    print("=" * 60)
    print(f"[config] Host: {HOST}")
    print(f"[config] Port: {PORT}")
    print(f"[config] Debug: {DEBUG}")
    print(f"[config] Processing enabled: {PROCESSING_ENABLED}")
    print(f"[config] Auth enabled: {is_auth_enabled()}")
    print(f"[paths] Data directory: {data_path.resolve()}")
    print(f"[paths] Photos directory: {photos_path.resolve()}")

    # Check photos directory
    if photos_path.exists():
        photo_count = len(list(photos_path.iterdir()))
        print(f"[data] Photos found: {photo_count}")
    else:
        print("[data] WARNING: raw_photos directory does not exist")

    # Check data files
    registry = load_registry()
    print(f"[data] Identities loaded: {len(registry.list_identities())}")

    # Count photos from photo_index.json
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))
        print(f"[data] Photos indexed: {photo_count}")
    else:
        print("[data] WARNING: photo_index.json not found")

    # Ensure staging directory exists for production uploads
    staging_dir = data_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Eagerly load hybrid models at startup to avoid 502 timeout on first request.
    # Only load det_500m + w600k_r50 (hybrid path) — NOT full buffalo_l FaceAnalysis,
    # which would double memory usage and OOM on Railway 512MB (AD-119).
    # buffalo_l FaceAnalysis is lazy-loaded only if hybrid models are unavailable.
    if PROCESSING_ENABLED:
        import time as _startup_time

        try:
            from core.ingest_inbox import get_face_analyzer, get_hybrid_models

            t_ml_start = _startup_time.time()

            # Load hybrid detection models (AD-114): det_500m + w600k_r50
            # These are individual ONNX models via get_model(), NOT full FaceAnalysis
            t0 = _startup_time.time()
            det, rec = get_hybrid_models()
            if det and rec:
                print(f"[ml] Hybrid models loaded in {_startup_time.time() - t0:.1f}s (det_500m + w600k_r50)")
            else:
                # Fallback: load buffalo_l FaceAnalysis (detection+recognition only)
                print("[ml] WARNING: Hybrid models NOT available, loading buffalo_l fallback...")
                import os

                models_dir = os.path.expanduser("~/.insightface/models")
                for pack in ["buffalo_l", "buffalo_sc"]:
                    pack_dir = os.path.join(models_dir, pack)
                    if os.path.isdir(pack_dir):
                        files = os.listdir(pack_dir)
                        print(f"[ml]   {pack}: {files}")
                    else:
                        print(f"[ml]   {pack}: DIRECTORY NOT FOUND")
                t0 = _startup_time.time()
                get_face_analyzer()
                print(f"[ml] buffalo_l fallback loaded in {_startup_time.time() - t0:.1f}s")

            # Warmup: run dummy inference to trigger ONNX JIT compilation (AD-119).
            # First real inference is 2-5x slower without this.
            t0 = _startup_time.time()
            import numpy as np

            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            if det and rec:
                # Warmup hybrid path (primary compare path)
                det.detect(dummy_img, max_num=0, metric="default")
                print(f"[ml] Hybrid warmup: {_startup_time.time() - t0:.1f}s")
            else:
                # Warmup full buffalo_l (fallback path)
                analyzer = get_face_analyzer()
                analyzer.get(dummy_img)
                print(f"[ml] buffalo_l warmup: {_startup_time.time() - t0:.1f}s")

            print(f"[ml] Total ML startup: {_startup_time.time() - t_ml_start:.1f}s")
        except Exception as e:
            print(f"[ml] InsightFace not available: {e}")

    print("=" * 60)
    print(f"Server starting at http://{HOST}:{PORT}")
    print("=" * 60)

    # Use 'app.main' as the module name so Uvicorn reimports via sys.modules["app.main"]
    # which is aliased to __main__. Without this, FastHTML derives appname="main" from
    # the filename stem, and Uvicorn does `import main` which creates a DUPLICATE module
    # with a different app/rt — causing extracted routes to register on the wrong app.
    serve(appname="app.main", host=HOST, port=PORT, reload=DEBUG)
