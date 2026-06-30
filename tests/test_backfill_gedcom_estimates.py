"""Unit tests for scripts/backfill_gedcom_estimates.py (ESTIMATE-BACKFILL-166).

Pure logic tests — NO network, NO app caches. The survey() orchestrator that
touches Supabase + app caches is exercised via a monkeypatched module surface in
one integration-style test; the classification/guard helpers are tested directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import scripts.backfill_gedcom_estimates as bf


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def test_parse_iso_handles_z_and_naive():
    assert bf._parse_iso("2026-05-01T12:00:00Z").tzinfo is not None
    assert bf._parse_iso("2026-05-01T12:00:00").tzinfo == timezone.utc
    assert bf._parse_iso(None) is None
    assert bf._parse_iso("garbage") is None
    assert bf._parse_iso(12345) is None


def test_as_dict_parses_json_string_and_passthrough():
    assert bf._as_dict('{"a": 1}') == {"a": 1}
    assert bf._as_dict({"a": 1}) == {"a": 1}
    assert bf._as_dict("not json") == {}
    assert bf._as_dict(None) == {}
    assert bf._as_dict(7) == {}


# --------------------------------------------------------------------------- #
# _build_gedcom_linked_photos
# --------------------------------------------------------------------------- #
def _fake_main_with_photos(photo_cache, face_to_identity):
    """Build a fake `app.main`-like module for linkage tests."""

    def get_identity_for_face(registry, fid):
        iid = face_to_identity.get(fid)
        return {"identity_id": iid} if iid else None

    return SimpleNamespace(
        _photo_cache=photo_cache,
        get_identity_for_face=get_identity_for_face,
        canonical_photo_id=lambda p: p,
    )


def test_linked_photos_detects_gedcom_face():
    photo_cache = {
        "photoA": {"faces": [{"face_id": "f1"}, {"face_id": "f2"}]},
        "photoB": {"faces": [{"face_id": "f3"}]},
        "photoC": {"face_ids": ["f4"]},  # flat fallback format
    }
    face_to_identity = {"f1": "idLINKED", "f2": "idOTHER", "f3": "idOTHER", "f4": "idLINKED"}
    m = _fake_main_with_photos(photo_cache, face_to_identity)
    linked = bf._build_gedcom_linked_photos(m, registry=None, gedcom_identities={"idLINKED"})
    assert linked == {"photoA", "photoC"}


def test_linked_photos_empty_when_no_gedcom_identities():
    photo_cache = {"photoA": {"faces": [{"face_id": "f1"}]}}
    m = _fake_main_with_photos(photo_cache, {"f1": "idX"})
    assert bf._build_gedcom_linked_photos(m, None, set()) == set()


# --------------------------------------------------------------------------- #
# _latest_enrichment_by_photo
# --------------------------------------------------------------------------- #
def test_latest_enrichment_picks_most_recent():
    rows = [
        {"photo_id": "p1", "created_at": "2026-04-01T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
        {"photo_id": "p1", "created_at": "2026-06-20T00:00:00Z", "gemini_config": {"enrichment_level": "gedcom+faces"}},
        {"photo_id": "p2", "created_at": "2026-05-01T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
    ]
    latest = bf._latest_enrichment_by_photo(rows)
    assert latest["p1"][0] == "gedcom+faces"  # later enriched call wins
    assert latest["p2"][0] == "none"


def test_latest_enrichment_parses_json_string_config_and_missing_level():
    rows = [
        {"photo_id": "p1", "created_at": "2026-05-01T00:00:00Z", "gemini_config": '{"enrichment_level": "faces"}'},
        {"photo_id": "p2", "created_at": "2026-05-01T00:00:00Z", "gemini_config": {}},
    ]
    latest = bf._latest_enrichment_by_photo(rows)
    assert latest["p1"][0] == "faces"
    assert latest["p2"][0] is None  # unknown, not visual-only


# --------------------------------------------------------------------------- #
# survey orchestrator (gemini_api_calls signal, everything mocked)
# --------------------------------------------------------------------------- #
def _patch_survey_deps(monkeypatch, tmp_path, *, date_labels, gemini_rows, photo_cache, face_to_identity, gedcom_links):
    """Monkeypatch the imports survey() pulls so it runs offline."""
    fake_m = _fake_main_with_photos(photo_cache, face_to_identity)
    fake_m._build_caches = lambda: None
    fake_m.load_registry = lambda: None
    fake_m._load_gedcom_face_links = lambda: gedcom_links

    import app.main as real_main
    import app.supabase_data as real_sd

    monkeypatch.setattr(real_main, "_build_caches", fake_m._build_caches)
    monkeypatch.setattr(real_main, "load_registry", fake_m.load_registry)
    monkeypatch.setattr(real_main, "_load_gedcom_face_links", fake_m._load_gedcom_face_links)
    monkeypatch.setattr(real_main, "get_identity_for_face", fake_m.get_identity_for_face)
    monkeypatch.setattr(real_main, "_photo_cache", photo_cache, raising=False)
    monkeypatch.setattr(real_main, "canonical_photo_id", lambda p: p, raising=False)
    monkeypatch.setattr(real_sd, "load_date_labels_from_supabase", lambda: date_labels)
    monkeypatch.setattr(real_sd, "get_supabase_client", lambda: object())  # truthy sentinel
    # bypass the real REST loader; feed canned gemini rows (or None for unreachable)
    monkeypatch.setattr(bf, "_load_gemini_calls", lambda sb: gemini_rows)
    monkeypatch.setattr(bf, "REPORT_PATH", tmp_path / "survey.md")


def test_survey_flags_latest_visual_only_linked_photo(monkeypatch, tmp_path, capsys):
    photo_cache = {
        "pVisualNow": {"faces": [{"face_id": "fL"}]},   # latest call visual-only → candidate
        "pSuperseded": {"faces": [{"face_id": "fL"}]},  # visual-only then enriched → NOT candidate
        "pUnlinked": {"faces": [{"face_id": "fU"}]},    # visual-only but not gedcom-linked → ignored
    }
    face_to_identity = {"fL": "idLINKED", "fU": "idUNLINKED"}
    gedcom_links = {"idLINKED": {"gedcom_id": "@I1@"}}
    gemini_rows = [
        {"photo_id": "pVisualNow", "created_at": "2026-05-10T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
        {"photo_id": "pSuperseded", "created_at": "2026-05-01T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
        {"photo_id": "pSuperseded", "created_at": "2026-06-25T00:00:00Z", "gemini_config": {"enrichment_level": "gedcom+faces"}},
        {"photo_id": "pUnlinked", "created_at": "2026-05-10T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
    ]
    date_labels = {"pVisualNow": {"best_year_estimate": 1915, "location_estimate": "NYC"}}
    _patch_survey_deps(
        monkeypatch, tmp_path,
        date_labels=date_labels, gemini_rows=gemini_rows, photo_cache=photo_cache,
        face_to_identity=face_to_identity, gedcom_links=gedcom_links,
    )
    rc = bf.survey("2026-04-13", "2026-06-12")
    assert rc == 0
    out = capsys.readouterr().out
    assert "BACKFILL candidates (latest call visual-only): 1" in out
    assert "inside outage window 2026-04-13..2026-06-12: 1" in out
    report = (tmp_path / "survey.md").read_text()
    assert "pVisualNow" in report
    assert "pSuperseded" not in report  # latest enriched
    assert "pUnlinked" not in report  # not gedcom-linked


def test_survey_out_of_window_candidate_counted_but_flagged(monkeypatch, tmp_path, capsys):
    photo_cache = {"pOld": {"faces": [{"face_id": "fL"}]}}
    gemini_rows = [
        {"photo_id": "pOld", "created_at": "2025-01-01T00:00:00Z", "gemini_config": {"enrichment_level": "none"}},
    ]
    _patch_survey_deps(
        monkeypatch, tmp_path,
        date_labels={}, gemini_rows=gemini_rows, photo_cache=photo_cache,
        face_to_identity={"fL": "idLINKED"}, gedcom_links={"idLINKED": {}},
    )
    bf.survey("2026-04-13", "2026-06-12")
    out = capsys.readouterr().out
    assert "BACKFILL candidates (latest call visual-only): 1" in out
    assert "inside outage window 2026-04-13..2026-06-12: 0" in out


def test_survey_returns_2_when_date_labels_unreachable(monkeypatch, tmp_path, capsys):
    _patch_survey_deps(
        monkeypatch, tmp_path,
        date_labels=None, gemini_rows=[], photo_cache={}, face_to_identity={}, gedcom_links={},
    )
    assert bf.survey("2026-04-13", "2026-06-12") == 2
    assert "could not read date_labels" in capsys.readouterr().err


def test_survey_returns_2_when_gemini_calls_unreachable(monkeypatch, tmp_path, capsys):
    _patch_survey_deps(
        monkeypatch, tmp_path,
        date_labels={}, gemini_rows=None, photo_cache={}, face_to_identity={}, gedcom_links={},
    )
    assert bf.survey("2026-04-13", "2026-06-12") == 2
    assert "could not read gemini_api_calls" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# execute guard
# --------------------------------------------------------------------------- #
def test_execute_refuses_without_approval(capsys):
    rc = bf.execute(approved=False)
    assert rc == 3
    assert "REFUSING" in capsys.readouterr().err


def test_execute_with_approval_is_guard_only_no_spend(capsys):
    rc = bf.execute(approved=True)
    assert rc == 0
    assert "does not" in capsys.readouterr().err  # still a guard, never auto-spends


def test_main_execute_without_approval_refuses(capsys):
    assert bf.main(["--execute"]) == 3


def test_main_defaults_to_survey(monkeypatch):
    called = {}

    def fake_survey(ws, we):
        called["ran"] = (ws, we)
        return 0

    monkeypatch.setattr(bf, "survey", fake_survey)
    assert bf.main([]) == 0
    assert called["ran"] == (bf.DEFAULT_WINDOW_START, bf.DEFAULT_WINDOW_END)
