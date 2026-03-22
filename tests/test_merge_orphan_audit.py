"""Production data audit: no merged identity should have orphaned faces (Lesson 154).

This test runs against the LIVE Supabase data to detect faces that were
lost during merges — faces that exist in a merged identity's anchor_ids
but NOT in the target identity's anchor_ids.

This is a CI-safe test: it reads from Supabase if available, skips otherwise.
"""

import json
import pytest


@pytest.fixture()
def supabase_client():
    """Get Supabase client, skip if unavailable."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        from app.supabase_data import get_supabase_client

        client = get_supabase_client()
        if not client:
            pytest.skip("Supabase client not available")
        return client
    except ImportError:
        pytest.skip("supabase_data not importable")


def _load_all_identities(client):
    """Load all identities with pagination."""
    all_identities = []
    offset = 0
    page_size = 1000
    while True:
        r = (
            client.table("identities")
            .select("identity_id, name, state, merged_into, anchor_ids, candidate_ids")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not r.data:
            break
        all_identities.extend(r.data)
        if len(r.data) < page_size:
            break
        offset += page_size
    return all_identities


def _ensure_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


class TestMergeOrphanAudit:
    """No merged identity should have faces missing from its target."""

    def test_no_merge_orphans_in_production(self, supabase_client):
        """Every face in a merged identity must also exist in its merge target."""
        all_identities = _load_all_identities(supabase_client)
        id_to_ident = {i["identity_id"]: i for i in all_identities}

        orphans = []
        for ident in all_identities:
            merged_into = ident.get("merged_into")
            if not merged_into:
                continue

            target = id_to_ident.get(merged_into)
            if not target:
                continue

            src_faces = set(
                f for f in _ensure_list(ident.get("anchor_ids")) + _ensure_list(ident.get("candidate_ids")) if f
            )
            tgt_faces = set(
                f for f in _ensure_list(target.get("anchor_ids")) + _ensure_list(target.get("candidate_ids")) if f
            )

            for fid in src_faces - tgt_faces:
                orphans.append(
                    {
                        "face_id": fid,
                        "source": ident.get("name", ""),
                        "target": target.get("name", ""),
                    }
                )

        assert len(orphans) == 0, (
            f"Found {len(orphans)} orphaned faces from merges. "
            f"First 5: {orphans[:5]}. "
            f"Run the merge orphan repair script to fix."
        )
