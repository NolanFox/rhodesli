"""
Self-service archive onboarding routes — "Create Your Archive" (PRD-060 / TOOLS-006).

Session 167, Track C. Lets a community/family start its own photo archive:
landing page + create form (name, description, contact) + the create flow,
wired to the EXISTING `create_community()` Supabase primitive (reuse, not
reinvent). Builds on WORKSPACE-001 (`create_personal_archive`, already shipped).

Self-registers via `from app.main import rt` (same pattern as
`app/estimate_routes.py`); imported once at the bottom of `app/main.py`.

IMPORTANT — permission policy is DEFERRED to the archive owner (Nolan).
See `docs/feedback/session-167-track-c-decisions.md` (track-c decisions). The actual
`create_community()` WRITE is gated behind the `SELF_SERVICE_ARCHIVE_ENABLED`
env flag (default OFF) so this module makes ZERO production behavior change
until Nolan explicitly enables it AND picks the auth gate. When the flag is
OFF the landing page renders an informational "coming soon" state and the POST
refuses to write.
"""

import logging
import os
import re

from fasthtml.common import *

# Route decorator only (self-registration pattern, mirrors estimate_routes.py).
from app.main import rt
from app.rate_limit import check_rate_limit

# All other main.py functions accessed via module reference.
import app.main as _main_mod

logger = logging.getLogger(__name__)

# Strict-ish email shape: no whitespace/control chars (blocks header injection into
# admin_emails), exactly one @, a dot in the domain.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A slug must be lowercase alnum + hyphens (matches what we generate + the /c/<slug>/ route).
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# --- Limits (validation only — the *policy* numbers are Nolan's to set) -------
MAX_NAME_LEN = 100
MAX_DESCRIPTION_LEN = 2000
MAX_CONTACT_LEN = 200
MAX_ARCHIVES_PER_USER = 3  # PRD-060 v1 rate-limit suggestion; see docs/feedback/session-167-track-c-decisions.md


def _self_service_enabled() -> bool:
    """Feature flag. OFF by default so production behavior is unchanged until
    Nolan explicitly enables self-service archive creation (and decides the
    permission model). See docs/feedback/session-167-track-c-decisions.md."""
    return os.getenv("SELF_SERVICE_ARCHIVE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _slugify(name: str) -> str:
    """Lowercase, hyphenated, URL-safe slug from a display name.

    Strips to ascii alnum + single hyphens, collapses runs, trims edges.
    Returns "" if nothing usable remains (caller must handle)."""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:60]


def _dedupe_slug(base_slug: str, existing_slugs: set) -> str:
    """Return base_slug, or base_slug-<n> if taken. Caps suffix scan; falls
    back to a random suffix so we never loop forever."""
    if base_slug and base_slug not in existing_slugs:
        return base_slug
    for n in range(2, 50):
        candidate = f"{base_slug}-{n}"
        if candidate not in existing_slugs:
            return candidate
    # Pathological collision — append short random hex (re-roll until unique).
    import secrets

    for _ in range(10):
        candidate = f"{base_slug}-{secrets.token_hex(3)}"
        if candidate not in existing_slugs:
            return candidate
    return f"{base_slug}-{secrets.token_hex(6)}"


def _load_communities_or_none():
    """All communities, or None on Supabase failure (Codex P1: the POST write
    path must FAIL CLOSED on a load failure — otherwise slug-dedup and the
    per-user cap silently bypass). Never raises."""
    try:
        from app.supabase_data import load_communities

        return load_communities()  # list, or None on failure
    except Exception:  # noqa: BLE001
        logger.warning("onboarding: load_communities failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Shared UI fragments
# ---------------------------------------------------------------------------

def _onboarding_page_style():
    return Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
    """)


def _onboarding_nav():
    return Nav(
        Div(
            A(Span("Rhodesli", cls="text-lg font-serif font-bold text-white"), href="/"),
            Div(
                A("Tools", href="/tools", cls="text-slate-300 hover:text-white text-sm"),
                cls="hidden sm:flex items-center gap-6",
            ),
            cls="max-w-3xl mx-auto px-6 flex items-center justify-between h-16",
        ),
        cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
    )


def _create_archive_form(name="", description="", contact="", error=None):
    """The create-archive form fragment (also re-rendered with errors on POST)."""
    error_banner = (
        Div(
            P(error, cls="text-red-300 text-sm"),
            cls="bg-red-900/30 border border-red-700/40 rounded-lg p-3 mb-4",
            data_testid="create-archive-error",
        )
        if error
        else None
    )
    return Div(
        error_banner,
        Form(
            Div(
                Label(
                    "Archive name ",
                    Span("*", cls="text-indigo-400"),
                    cls="text-sm text-slate-300 mb-1 block font-medium",
                ),
                Input(
                    type="text",
                    name="name",
                    value=name,
                    required=True,
                    maxlength=str(MAX_NAME_LEN),
                    placeholder="e.g., The Cohen Family of Rhodes",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 "
                    "text-slate-100 placeholder-slate-500 text-sm",
                    data_testid="create-archive-name",
                ),
                cls="mb-4",
            ),
            Div(
                Label("Description (optional)", cls="text-sm text-slate-300 mb-1 block font-medium"),
                Textarea(
                    description or "",
                    name="description",
                    rows="3",
                    maxlength=str(MAX_DESCRIPTION_LEN),
                    placeholder="A sentence or two about whose photos this archive will hold.",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 "
                    "text-slate-100 placeholder-slate-500 text-sm resize-y",
                    data_testid="create-archive-description",
                ),
                cls="mb-4",
            ),
            Div(
                Label("Contact email (optional)", cls="text-sm text-slate-300 mb-1 block font-medium"),
                Input(
                    type="email",
                    name="contact",
                    value=contact,
                    maxlength=str(MAX_CONTACT_LEN),
                    placeholder="you@example.com",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 "
                    "text-slate-100 placeholder-slate-500 text-sm",
                    data_testid="create-archive-contact",
                ),
                P(
                    "So family members know who curates the archive. Never shown publicly without your say-so.",
                    cls="text-xs text-slate-500 mt-1",
                ),
                cls="mb-6",
            ),
            Button(
                "Create archive",
                type="submit",
                cls="w-full p-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white font-medium transition-colors",
                data_testid="create-archive-submit",
            ),
            action="/create-archive",
            method="post",
            data_testid="create-archive-form",
        ),
        cls="bg-slate-800/40 rounded-2xl p-6 border border-slate-700/40",
    )


def _coming_soon_panel():
    return Div(
        Div(
            P(
                "Self-service archives are coming soon.",
                cls="text-slate-200 text-sm font-medium mb-1",
            ),
            P(
                "We're putting the finishing touches on letting families spin up their own "
                "photo archives. Want early access? Reach out and we'll set you up.",
                cls="text-slate-400 text-sm",
            ),
            cls="bg-amber-900/20 border border-amber-700/30 rounded-2xl p-6",
            data_testid="create-archive-coming-soon",
        ),
        Div(
            A(
                "Explore the tools",
                href="/tools",
                cls="text-indigo-400 hover:text-indigo-300 text-sm",
            ),
            cls="text-center mt-6",
        ),
    )


def _sign_in_panel():
    return Div(
        P(
            "You need an account to create an archive.",
            cls="text-slate-200 text-sm font-medium mb-3",
        ),
        A(
            "Sign in",
            href="/login",
            cls="inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium",
            data_testid="create-archive-signin",
        ),
        cls="bg-slate-800/40 border border-slate-700/40 rounded-2xl p-6 text-center",
        data_testid="create-archive-auth-required",
    )


def _archive_page_body(inner):
    """Wrap an inner panel in the full editorial page chrome."""
    og = _main_mod.og_tags(
        title="Create Your Archive — Rhodesli",
        description="Start a photo archive for your family or community. Upload photos, "
        "get automatic face detection, and share what you find.",
        canonical_url=f"{_main_mod.SITE_URL}/create-archive",
    )
    return (
        Title("Create Your Archive — Rhodesli"),
        *og,
        _onboarding_page_style(),
        Main(
            _onboarding_nav(),
            Section(
                Div(
                    H1(
                        "Create Your Archive",
                        cls="text-2xl sm:text-3xl font-serif font-bold text-white text-center mb-2",
                    ),
                    P(
                        "Bring your family's photographs together. Upload them, let our AI find "
                        "the faces, and invite relatives to help fill in the names.",
                        cls="text-slate-400 text-sm text-center mb-8 max-w-lg mx-auto",
                    ),
                    inner,
                    cls="max-w-xl mx-auto px-6 py-10",
                ),
            ),
            cls="min-h-screen bg-slate-900 text-white",
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@rt("/create-archive")
def get(sess=None):
    """Landing + form for self-service archive creation.

    Gate order (Codex P3): feature flag FIRST — when disabled the feature is off
    for everyone, so the coming-soon state is the honest message regardless of
    auth. Then auth.

    - Feature flag OFF              -> coming-soon panel
    - Auth enabled + not logged in  -> sign-in panel
    - Otherwise                     -> the create form
    """
    if not _self_service_enabled():
        return _archive_page_body(_coming_soon_panel())

    auth_on = _main_mod.is_auth_enabled()
    user = _main_mod.get_current_user(sess or {}) if auth_on else None
    if auth_on and not user:
        return _archive_page_body(_sign_in_panel())

    return _archive_page_body(_create_archive_form())


@rt("/create-archive")
def post(sess=None, name: str = "", description: str = "", contact: str = "", request=None):
    """Handle archive creation.

    Validation happens unconditionally; the actual Supabase WRITE is gated by
    BOTH login (when auth is enabled) AND the SELF_SERVICE_ARCHIVE_ENABLED flag.
    The permission MODEL (who may create) is Nolan's decision — see
    docs/feedback/session-167-track-c-decisions.md. This handler ships a conservative default (logged-in
    users only, behind a default-OFF flag) so nothing changes in production
    until that decision is made.
    """
    # --- Feature-flag gate FIRST (defers the permission decision to Nolan) -
    if not _self_service_enabled():
        return _archive_page_body(_coming_soon_panel())

    auth_on = _main_mod.is_auth_enabled()
    user = _main_mod.get_current_user(sess or {}) if auth_on else None

    # --- Auth gate (when auth is enabled) ---------------------------------
    if auth_on and not user:
        return _archive_page_body(_sign_in_panel())

    # --- IP throttle (defense in depth; Codex P2) -------------------------
    client_ip = getattr(getattr(request, "client", None), "host", None) if request else None
    if client_ip and not check_rate_limit(f"create-archive:{client_ip}", max_per_hour=10):
        return _archive_page_body(
            _create_archive_form(
                name=name, description=description, contact=contact,
                error="Too many attempts. Please wait a little while and try again.",
            )
        )

    # --- Validation (always runs) -----------------------------------------
    name = (name or "").strip()
    description = (description or "").strip()
    contact = (contact or "").strip()

    def _reform(err):
        return _archive_page_body(
            _create_archive_form(name=name, description=description, contact=contact, error=err)
        )

    if not name:
        return _reform("Please enter a name for your archive.")
    if len(name) > MAX_NAME_LEN:
        return _reform(f"Archive name must be {MAX_NAME_LEN} characters or fewer.")
    if len(description) > MAX_DESCRIPTION_LEN:
        return _reform(f"Description must be {MAX_DESCRIPTION_LEN} characters or fewer.")
    if contact and (len(contact) > MAX_CONTACT_LEN or not _EMAIL_RE.match(contact)):
        return _reform("Please enter a valid contact email, or leave it blank.")

    base_slug = _slugify(name)
    if not base_slug:
        return _reform("Please use at least one letter or number in the archive name.")

    # Fail CLOSED on community-load failure (Codex P1): we cannot safely dedup
    # the slug or enforce the per-user cap without the current community list.
    communities = _load_communities_or_none()
    if communities is None:
        return _reform("We couldn't verify existing archives right now. Please try again in a moment.")
    existing_slugs = {c.get("slug") for c in communities if c.get("slug")}

    # --- Per-user rate limit (count owned, non-personal archives) ----------
    if user is not None:
        owned = [
            c
            for c in communities
            if c.get("owner_id") == user.id and not c.get("is_personal")
        ]
        if len(owned) >= MAX_ARCHIVES_PER_USER:
            return _reform(
                f"You've reached the limit of {MAX_ARCHIVES_PER_USER} archives. "
                "Contact us if you need more."
            )

    slug = _dedupe_slug(base_slug, existing_slugs)

    payload = {
        "slug": slug,
        "name": name,
        "description": description or None,
        "r2_prefix": f"archives/{slug}",
        "is_personal": False,
        "privacy": "unlisted",  # PRD-060 default; see docs/feedback/session-167-track-c-decisions.md
        "config": {"created_via": "self_service", "onboarding_version": 1},
    }
    if user is not None:
        payload["owner_id"] = user.id
        # admin_emails: owner's account email, plus the optional contact.
        emails = []
        if getattr(user, "email", None):
            emails.append(user.email)
        if contact and contact not in emails:
            emails.append(contact)
        if emails:
            payload["admin_emails"] = emails
    elif contact:
        payload["admin_emails"] = [contact]

    try:
        from app.supabase_data import create_community

        created = create_community(payload)
    except Exception:  # noqa: BLE001
        logger.error("onboarding: create_community raised", exc_info=True)
        created = None

    if not created:
        return _reform(
            "We couldn't create your archive right now. Please try again in a moment."
        )

    # Trust our locally-validated slug for the redirect; only use the returned
    # slug if it also matches the slug shape (Codex P2 — avoid an unroutable
    # redirect from an unexpected DB-returned value).
    created_slug = created.get("slug")
    redirect_slug = created_slug if (created_slug and _SLUG_RE.match(created_slug)) else slug
    # Redirect to the new (empty) archive dashboard — the first-upload entrypoint.
    return RedirectResponse(f"/c/{redirect_slug}/", status_code=303)
