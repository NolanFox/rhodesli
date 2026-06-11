"""Session 165 — Person-scoped photo navigation (FB-004).

Root cause: a dual photo-ID-space split-brain. The photo-view layer uses
canonical (``_photo_cache``) SHA256-style IDs while the identity nav set was
built via ``get_photos_for_faces`` (durable PhotoRegistry / ``inbox_*`` IDs).
The membership check ``photo_id in identity_photo_ids`` silently failed across
the two spaces, collapsing person-scoped navigation into whole-collection
navigation (Lesson 25 / Lesson 63).

These tests pin the fix: build the identity set in canonical space and
normalize the incoming photo_id before the membership check, while preserving
the explicit-nav-wins contract (compare modal / seq-mode / direct callers).
"""

from unittest.mock import patch, MagicMock

import pytest


# --------------------------------------------------------------------------
# canonical_photo_id — the normalization primitive
# --------------------------------------------------------------------------
class TestCanonicalPhotoId:
    def test_canonical_id_passthrough(self):
        """An ID already in the canonical cache returns unchanged."""
        from app import main as m

        with patch.object(m, "_build_caches"), \
             patch.object(m, "_photo_cache", {"a58504ab20bbb741": {"filename": "x.jpg"}}), \
             patch.object(m, "_photo_id_aliases", {}):
            assert m.canonical_photo_id("a58504ab20bbb741") == "a58504ab20bbb741"

    def test_inbox_id_resolves_to_canonical(self):
        """An inbox_* ID is mapped to its canonical cache ID via the alias bridge."""
        from app import main as m

        with patch.object(m, "_build_caches"), \
             patch.object(m, "_photo_cache", {"a58504ab20bbb741": {"filename": "x.jpg"}}), \
             patch.object(m, "_photo_id_aliases", {"inbox_fox_212": "a58504ab20bbb741"}):
            assert m.canonical_photo_id("inbox_fox_212") == "a58504ab20bbb741"

    def test_unknown_id_passthrough(self):
        """An unknown ID degrades gracefully (returned unchanged)."""
        from app import main as m

        with patch.object(m, "_build_caches"), \
             patch.object(m, "_photo_cache", {}), \
             patch.object(m, "_photo_id_aliases", {}):
            assert m.canonical_photo_id("mystery") == "mystery"

    def test_empty_passthrough(self):
        from app import main as m

        assert m.canonical_photo_id("") == ""
        assert m.canonical_photo_id(None) is None


# --------------------------------------------------------------------------
# _ordered_identity_photo_ids — builds in canonical space
# --------------------------------------------------------------------------
class TestOrderedIdentityPhotoIdsCanonicalSpace:
    def _identity(self):
        return {
            "identity_id": "id1",
            "name": "Harry Fox",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"],
            "candidate_ids": [],
        }

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main._load_date_labels", return_value={})
    @patch("app.main.get_photo_metadata", return_value={})
    def test_set_built_from_face_to_photo_canonical(self, _meta, _labels, mock_face_photo):
        """The identity set uses get_photo_id_for_face (canonical), not the
        PhotoRegistry inbox-space resolver."""
        from app.page_routes import _ordered_identity_photo_ids

        # Canonical SHA-style IDs (what the photo view / entry links use).
        mock_face_photo.side_effect = lambda fid: {
            "f1": "canonA",
            "f2": "canonB",
            "f3": "canonC",
        }.get(fid)
        reg = MagicMock()
        reg.get_identity.return_value = self._identity()

        ids, name = _ordered_identity_photo_ids(reg, "id1", "date_asc")
        assert set(ids) == {"canonA", "canonB", "canonC"}
        assert name == "Harry Fox"

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main._load_date_labels", return_value={})
    @patch("app.main.get_photo_metadata", return_value={})
    def test_deduplicates_faces_in_same_photo(self, _meta, _labels, mock_face_photo):
        from app.page_routes import _ordered_identity_photo_ids

        mock_face_photo.side_effect = lambda fid: {"f1": "canonA", "f2": "canonA", "f3": "canonB"}.get(fid)
        reg = MagicMock()
        reg.get_identity.return_value = self._identity()

        ids, _ = _ordered_identity_photo_ids(reg, "id1", "date_asc")
        assert ids.count("canonA") == 1
        assert set(ids) == {"canonA", "canonB"}


# --------------------------------------------------------------------------
# photo_view_content (partial path) — identity-scoped prev/next
# --------------------------------------------------------------------------
class TestPhotoViewIdentityScoping:
    def _identity(self):
        return {
            "identity_id": "id1",
            "name": "Harry Fox",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"],
            "candidate_ids": [],
        }

    def _photo_view(self, photo_id, **kwargs):
        from app.main import photo_view_content, to_xml

        defaults = dict(is_partial=True, identity_id="id1")
        defaults.update(kwargs)
        return to_xml(photo_view_content(photo_id, **defaults))

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Charlie Fox"})
    def test_prev_next_only_from_identity_set(self, _meta, mock_reg, _dim, mock_face_photo):
        """Arrows cycle ONLY the person's photos — middle photo has both, scoped."""
        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = self._identity()
        mock_reg.return_value = inst

        html = self._photo_view("pB")
        assert "/photo/pA/partial" in html  # prev = in-set
        assert "/photo/pC/partial" in html  # next = in-set
        assert "2 / 3" in html

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Charlie Fox"})
    def test_ends_clamp_first(self, _meta, mock_reg, _dim, mock_face_photo):
        """First photo: no prev button, next present, no wrap into collection."""
        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = self._identity()
        mock_reg.return_value = inst

        html = self._photo_view("pA")
        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' in html
        assert "1 / 3" in html

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Charlie Fox"})
    def test_ends_clamp_last(self, _meta, mock_reg, _dim, mock_face_photo):
        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = self._identity()
        mock_reg.return_value = inst

        html = self._photo_view("pC")
        assert 'id="photo-nav-prev"' in html
        assert 'id="photo-nav-next"' not in html
        assert "3 / 3" in html

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Charlie Fox"})
    def test_arrow_hrefs_carry_identity_and_sort(self, _meta, mock_reg, _dim, mock_face_photo):
        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = self._identity()
        mock_reg.return_value = inst

        html = self._photo_view("pB", sort_by="date_desc")
        assert "identity_id=id1" in html
        assert "sort_by=date_desc" in html

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Charlie Fox"})
    def test_inbox_entry_id_normalizes_to_canonical_membership(self, _meta, mock_reg, _dim, mock_face_photo):
        """Entering from the photos gallery (inbox_* photo_id) still scopes to
        the person — the incoming ID is normalized to canonical first."""
        from app import main as m

        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = self._identity()
        mock_reg.return_value = inst

        with patch.object(m, "_build_caches"), \
             patch.object(m, "_photo_cache", {"pA": {}, "pB": {}, "pC": {}}), \
             patch.object(m, "_photo_id_aliases", {"inbox_pB": "pB"}):
            html = self._photo_view("inbox_pB")
        # Membership resolved via alias → scoped prev/next, position 2 of 3.
        assert "2 / 3" in html
        assert "/photo/pA/partial" in html
        assert "/photo/pC/partial" in html


# --------------------------------------------------------------------------
# Explicit-nav-wins contract preserved (compare modal / seq / direct callers)
# --------------------------------------------------------------------------
class TestExplicitNavContractPreserved:
    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Test"})
    def test_explicit_prev_next_override_identity(self, _meta, mock_reg, _dim, mock_face_photo):
        """When explicit prev/next are passed (compare modal, direct callers),
        they win even if identity_id is present and the photo is in the set."""
        from app.main import photo_view_content, to_xml

        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        inst = MagicMock()
        inst.get_identity.return_value = {
            "identity_id": "id1", "name": "Harry", "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"], "candidate_ids": [],
        }
        mock_reg.return_value = inst

        html = to_xml(photo_view_content(
            "pB", is_partial=True, identity_id="id1",
            prev_id="X9", next_id="Y9", nav_idx=4, nav_total=9, from_compare=True,
        ))
        # Explicit nav respected (5 / 9), NOT the identity-computed 2 / 3.
        assert "5 / 9" in html
        assert "/photo/X9/partial" in html
        assert "/photo/Y9/partial" in html

    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_metadata", return_value={"filename": "t.jpg", "faces": [], "source": "Test"})
    def test_no_identity_collection_nav_unchanged(self, _meta, mock_reg, _dim):
        """No identity_id → explicit collection prev/next render unchanged."""
        from app.main import photo_view_content, to_xml

        mock_reg.return_value = MagicMock()
        html = to_xml(photo_view_content(
            "p2", is_partial=True, prev_id="p1", next_id="p3", nav_idx=1, nav_total=5,
        ))
        assert "2 / 5" in html
        assert "/photo/p1/partial" in html
        assert "/photo/p3/partial" in html


# --------------------------------------------------------------------------
# public_photo_page (full-page path) — same scoping as the partial path (d)
# --------------------------------------------------------------------------
_PCACHE = {
    "pA": {"photo_id": "pA", "filename": "a.jpg", "collection": "Charlie Fox", "source": "Charlie Fox", "faces": []},
    "pB": {"photo_id": "pB", "filename": "b.jpg", "collection": "Charlie Fox", "source": "Charlie Fox", "faces": []},
    "pC": {"photo_id": "pC", "filename": "c.jpg", "collection": "Charlie Fox", "source": "Charlie Fox", "faces": []},
    # A collection sibling NOT belonging to the person — must never be an arrow target.
    "pZ": {"photo_id": "pZ", "filename": "z.jpg", "collection": "Charlie Fox", "source": "Charlie Fox", "faces": []},
}


class TestPublicPhotoPageIdentityScoping:
    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main._photo_cache", _PCACHE)
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_full_page_arrows_scoped_to_person(
        self, _badge, _align, _ai, _datemeta, _upline, _adminbar, _pubnav, _navlinks,
        mock_reg, _dim, mock_meta, mock_face_photo,
    ):
        """Full page: a person's middle photo cycles ONLY the person's photos —
        the collection sibling pZ is never an arrow target. Mirrors the partial
        path (both unified on _ordered_identity_photo_ids)."""
        from app.main import public_photo_page, to_xml
        import re

        mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
        mock_meta.side_effect = lambda pid: _PCACHE.get(pid)
        inst = MagicMock()
        inst.get_identity.return_value = {
            "identity_id": "id1", "name": "Harry Fox", "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"], "candidate_ids": [],
        }
        mock_reg.return_value = inst

        html = to_xml(public_photo_page("pB", identity_id="id1", sort_by="date_asc", community_slug="fox-family"))

        # Counter is position-in-person-set, not the collection.
        assert "Photo 2 of 3" in html
        targets = set(re.findall(r"/photo/([A-Za-z0-9_\-]+)\?identity_id=id1", html))
        assert "pA" in targets and "pC" in targets
        assert "pZ" not in targets  # collection sibling never leaks in

    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main._photo_cache", _PCACHE)
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_full_page_no_identity_uses_collection(
        self, _badge, _align, _ai, _datemeta, _upline, _adminbar, _pubnav, _navlinks,
        mock_reg, _dim, mock_meta, mock_face_photo,
    ):
        """Regression: with NO identity_id, the full page still falls back to
        collection navigation (the collection sibling IS reachable)."""
        from app.main import public_photo_page, to_xml
        import re

        mock_face_photo.side_effect = lambda fid: None
        mock_meta.side_effect = lambda pid: _PCACHE.get(pid)
        mock_reg.return_value = MagicMock()

        html = to_xml(public_photo_page("pB", community_slug="fox-family"))
        # Collection nav active (4 photos in the Charlie Fox collection).
        assert re.search(r"Photo \d+ of 4", html)


# --------------------------------------------------------------------------
# Phase 3 — public-appropriate banner: admin alarm vs anonymous gentle copy.
# A raw deep link to an off-person photo (pZ — not in Harry's set) lands in the
# context_identity_missing state. Admins see the rose "Needs review" alarm;
# anonymous viewers get amber styling + gentle wording, never admin language.
# --------------------------------------------------------------------------
class TestPublicPhotoPageBannerMessaging:
    _BANNER_PATCHES = (
        patch("app.main.get_photo_id_for_face"),
        patch("app.main.get_photo_metadata"),
        patch("app.main.get_photo_dimensions", return_value=(800, 600)),
        patch("app.main.load_registry"),
        patch("app.main._photo_cache", _PCACHE),
        patch("app.main._public_nav_links", return_value=[]),
        patch("app.main._public_page_nav", return_value=()),
        patch("app.main._admin_bar", return_value=()),
        patch("app.main._build_upload_provenance_line", return_value=None),
        patch("app.main._get_date_badge", return_value=("", "low", "")),
        patch("app.main._build_ai_analysis_section", return_value=None),
        patch("app.main._build_face_alignment_section", return_value=None),
        patch("app.main._build_photo_date_badge", return_value=None),
    )

    def _render(self, is_admin):
        """Render an off-person deep link (pZ) under the given admin flag."""
        from contextlib import ExitStack
        from app.main import public_photo_page, to_xml

        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in self._BANNER_PATCHES]
            mock_face_photo = mocks[0]
            mock_meta = mocks[1]
            mock_reg = mocks[3]
            mock_face_photo.side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
            mock_meta.side_effect = lambda pid: _PCACHE.get(pid)
            inst = MagicMock()
            inst.get_identity.return_value = {
                "identity_id": "id1", "name": "Harry Fox", "state": "CONFIRMED",
                "anchor_ids": ["f1", "f2", "f3"], "candidate_ids": [],
            }
            mock_reg.return_value = inst
            return to_xml(
                public_photo_page(
                    "pZ", identity_id="id1", sort_by="date_asc",
                    is_admin=is_admin, community_slug="fox-family",
                )
            )

    def test_admin_sees_review_alarm(self):
        html = self._render(is_admin=True)
        assert "Needs review" in html
        assert "Review before trusting this link." in html
        assert "bg-rose-950/40" in html  # alarm container

    def test_anonymous_sees_gentle_amber(self):
        html = self._render(is_admin=False)
        # No admin review language for the public.
        assert "Needs review" not in html
        assert "Review before trusting this link." not in html
        # Gentle public wording + amber (not rose) styling.
        assert "haven't tagged Harry Fox" in html
        assert "bg-amber-950/30" in html
        assert "bg-rose-950/40" not in html

    def test_off_person_deep_link_does_not_leak_collection_nav(self):
        """Codex P1 regression: a raw/stale deep link to an off-person photo
        (pZ) with identity_id present must NOT fall back to whole-collection
        navigation. The collection has 4 photos — the off-person page must not
        render a 'Photo N of 4' counter, and pZ must have no arrow neighbors."""
        import re

        html = self._render(is_admin=False)
        assert "Photo 4 of 4" not in html  # no collection counter
        assert not re.search(r"Photo \d+ of 4", html)
        # No identity-scoped arrow targets either (pZ is not in Harry's set).
        assert not re.findall(r"/photo/p[ABC]\?identity_id=id1", html)


# --------------------------------------------------------------------------
# Phase 1 boundary — full-page first/last clamp + XSS hardening of the inline
# keyboard/touch nav scripts (Codex P1/P3, Session 165).
# --------------------------------------------------------------------------
class TestPublicPhotoPageClampAndXss:
    _PATCHES = (
        patch("app.main.get_photo_id_for_face"),
        patch("app.main.get_photo_metadata"),
        patch("app.main.get_photo_dimensions", return_value=(800, 600)),
        patch("app.main.load_registry"),
        patch("app.main._photo_cache", _PCACHE),
        patch("app.main._public_nav_links", return_value=[]),
        patch("app.main._public_page_nav", return_value=()),
        patch("app.main._admin_bar", return_value=()),
        patch("app.main._build_upload_provenance_line", return_value=None),
        patch("app.main._get_date_badge", return_value=("", "low", "")),
        patch("app.main._build_ai_analysis_section", return_value=None),
        patch("app.main._build_face_alignment_section", return_value=None),
        patch("app.main._build_photo_date_badge", return_value=None),
    )

    def _render(self, photo_id, identity_id="id1"):
        from contextlib import ExitStack
        from app.main import public_photo_page, to_xml

        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in self._PATCHES]
            mocks[0].side_effect = lambda fid: {"f1": "pA", "f2": "pB", "f3": "pC"}.get(fid)
            mocks[1].side_effect = lambda pid: _PCACHE.get(pid)
            inst = MagicMock()
            inst.get_identity.return_value = {
                "identity_id": identity_id, "name": "Harry Fox", "state": "CONFIRMED",
                "anchor_ids": ["f1", "f2", "f3"], "candidate_ids": [],
            }
            mocks[3].return_value = inst
            return to_xml(
                public_photo_page(photo_id, identity_id=identity_id, sort_by="date_asc",
                                  community_slug="fox-family")
            )

    def test_first_photo_clamps_no_prev(self):
        import re
        html = self._render("pA")
        assert "Photo 1 of 3" in html
        # pA is first → next is pB, but there is no prev (no pC/pB-as-prev wrap).
        targets = re.findall(r"/photo/(p[ABC])\?identity_id=id1", html)
        assert "pB" in targets  # next exists
        # No wrap: the last photo (pC) must never be reachable as a neighbor of pA.
        assert "pC" not in targets

    def test_last_photo_clamps_no_next(self):
        import re
        html = self._render("pC")
        assert "Photo 3 of 3" in html
        targets = re.findall(r"/photo/(p[ABC])\?identity_id=id1", html)
        assert "pB" in targets  # prev exists
        assert "pA" not in targets  # no wrap to first

    def test_keyboard_nav_script_escapes_identity_id(self):
        """Codex P1: identity_id must be url/JSON-escaped inside the inline nav
        <script> blocks — never break out of the JS string. A quote-bearing
        identity that still resolves in-set must not yield an executable breakout
        in any <script> tag (href attributes are single-quoted and inert)."""
        import re
        html = self._render("pB", identity_id="id1\");alert(1)//")
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        joined = "\n".join(scripts)
        # The breakout sequence must not appear executable in any script block.
        assert ");alert(1)//" not in joined
        assert "alert(1)" not in joined
        # The nav scripts serialize URLs via JSON string vars (not raw interpolation).
        assert "var prevUrl =" in joined and "nextUrl =" in joined
        # identity_id is url-encoded in the emitted nav URLs (quote/paren escaped).
        assert "%22" in joined and "%29" in joined
