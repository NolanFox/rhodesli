"""Tests for GEDCOM match data consistency.

Regression tests for:
- Matilda (a2889099) GEDCOM xref correctness (Session 81 fix)
- No duplicate identity_id entries with conflicting xrefs
- All confirmed matches have required fields
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATCHES_PATH = PROJECT_ROOT / "data" / "gedcom_matches.json"


@pytest.fixture
def gedcom_matches():
    """Load gedcom_matches.json."""
    if not MATCHES_PATH.exists():
        pytest.skip("data/gedcom_matches.json not found")
    return json.loads(MATCHES_PATH.read_text(encoding="utf-8"))


class TestMatildaGedcomLink:
    """Regression: Matilda (a2889099) must link to @I132127360994@, not @I132423679471@."""

    def test_matilda_xref_is_correct(self, gedcom_matches):
        """Matilda Capouano Capelouto (a2889099) must have the correct GEDCOM xref."""
        matches = gedcom_matches.get("matches", [])
        matilda = [m for m in matches if m.get("identity_id", "").startswith("a2889099")]

        assert len(matilda) == 1, f"Expected exactly 1 Matilda match, found {len(matilda)}"
        assert matilda[0]["gedcom_xref"] == "@I132127360994@", (
            f"Matilda xref is {matilda[0]['gedcom_xref']}, "
            f"expected @I132127360994@ (not the wrong @I132423679471@)"
        )

    def test_matilda_is_confirmed(self, gedcom_matches):
        """Matilda's match must be confirmed."""
        matches = gedcom_matches.get("matches", [])
        matilda = [m for m in matches if m.get("identity_id", "").startswith("a2889099")]

        assert len(matilda) == 1
        assert matilda[0]["status"] == "confirmed"

    def test_matilda_gedcom_name_matches(self, gedcom_matches):
        """Matilda's GEDCOM name must reference the correct person."""
        matches = gedcom_matches.get("matches", [])
        matilda = [m for m in matches if m.get("identity_id", "").startswith("a2889099")]

        assert len(matilda) == 1
        # The correct person is "Matilda Cap Capelouto" (daughter of Abraham)
        assert "Matilda" in matilda[0]["gedcom_name"]


class TestGedcomMatchConsistency:
    """Ensure gedcom_matches.json data integrity."""

    def test_no_duplicate_identity_ids_with_different_xrefs(self, gedcom_matches):
        """Each identity_id should map to at most one GEDCOM xref in confirmed matches.

        This catches the class of bug where an identity gets linked to the wrong
        GEDCOM person because of a stale or conflicting entry.
        """
        matches = gedcom_matches.get("matches", [])
        confirmed = [m for m in matches if m.get("status") == "confirmed"]

        id_to_xrefs = {}
        for m in confirmed:
            iid = m.get("identity_id", "")
            xref = m.get("gedcom_xref", "")
            if iid not in id_to_xrefs:
                id_to_xrefs[iid] = set()
            id_to_xrefs[iid].add(xref)

        conflicts = {iid: xrefs for iid, xrefs in id_to_xrefs.items() if len(xrefs) > 1}
        assert not conflicts, (
            f"Found identity IDs with conflicting GEDCOM xrefs: "
            + ", ".join(f"{iid}: {xrefs}" for iid, xrefs in conflicts.items())
        )

    def test_no_duplicate_xrefs_for_different_identities(self, gedcom_matches):
        """Each GEDCOM xref should map to at most one identity_id in confirmed matches.

        Two different identities should not be linked to the same GEDCOM person.
        """
        matches = gedcom_matches.get("matches", [])
        confirmed = [m for m in matches if m.get("status") == "confirmed"]

        xref_to_ids = {}
        for m in confirmed:
            xref = m.get("gedcom_xref", "")
            iid = m.get("identity_id", "")
            if xref not in xref_to_ids:
                xref_to_ids[xref] = set()
            xref_to_ids[xref].add(iid)

        conflicts = {xref: ids for xref, ids in xref_to_ids.items() if len(ids) > 1}
        assert not conflicts, (
            f"Found GEDCOM xrefs linked to multiple identities: "
            + ", ".join(f"{xref}: {ids}" for xref, ids in conflicts.items())
        )

    def test_confirmed_matches_have_required_fields(self, gedcom_matches):
        """All confirmed matches must have the essential fields."""
        matches = gedcom_matches.get("matches", [])
        confirmed = [m for m in matches if m.get("status") == "confirmed"]

        required_fields = ["gedcom_xref", "identity_id", "identity_name", "gedcom_name",
                           "match_score", "match_reason", "status"]

        for m in confirmed:
            for field in required_fields:
                assert field in m, (
                    f"Confirmed match for {m.get('identity_name', '?')} "
                    f"missing required field '{field}'"
                )

    def test_all_xrefs_have_valid_format(self, gedcom_matches):
        """All GEDCOM xrefs should match the @INNN@ format."""
        matches = gedcom_matches.get("matches", [])
        for m in matches:
            xref = m.get("gedcom_xref", "")
            assert xref.startswith("@") and xref.endswith("@"), (
                f"Invalid xref format '{xref}' for {m.get('identity_name', '?')}"
            )

    def test_schema_version_present(self, gedcom_matches):
        """gedcom_matches.json must have schema_version."""
        assert "schema_version" in gedcom_matches
        assert gedcom_matches["schema_version"] >= 1


class TestFixScript:
    """Test the fix script logic (without Supabase)."""

    def test_fix_script_validates_json_data(self):
        """The fix script should verify gedcom_matches.json has the correct xref."""
        if not MATCHES_PATH.exists():
            pytest.skip("data/gedcom_matches.json not found")

        data = json.loads(MATCHES_PATH.read_text(encoding="utf-8"))
        matches = data.get("matches", [])

        # Find Matilda
        matilda = [m for m in matches if m.get("identity_id", "").startswith("a2889099")]
        assert len(matilda) == 1, "Matilda entry must exist"
        assert matilda[0]["gedcom_xref"] == "@I132127360994@", (
            "Fix script depends on gedcom_matches.json having correct xref"
        )
