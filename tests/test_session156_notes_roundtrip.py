"""Session 156 — Round-trip identity notes through Supabase via metadata JSONB.

Top-level identity["notes"] is appended by registry.add_note() but only
persisted via Supabase's metadata JSONB column (shadow_write doesn't include
"notes" at the row top-level). load_from_postgres extracts metadata.notes
back to identity["notes"] so the notes panel renders.

These tests verify both halves of the round-trip.
"""

from unittest.mock import MagicMock, patch


class TestNotesEmbeddedInMetadataOnWrite:
    def test_shadow_write_identity_embeds_notes_in_metadata(self):
        from app import supabase_data

        captured = {}

        def fake_upsert(rows):
            captured["rows"] = rows
            mock_exec = MagicMock()
            mock_exec.execute = MagicMock(return_value=MagicMock(data=rows))
            return mock_exec

        mock_table = MagicMock()
        mock_table.upsert = fake_upsert

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        identity_data = {
            "identity_id": "test-id-1",
            "name": "Test",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {"existing_field": "keep_me"},
            "notes": [
                {"id": "n1", "text": "A note", "author": "session-156", "timestamp": "2026-05-08T00:00:00Z"}
            ],
            "version_id": 1,
        }

        with patch.object(supabase_data, "get_supabase_client", return_value=mock_client):
            supabase_data.shadow_write_identity(identity_data, strict=True)

        assert captured["rows"]["identity_id"] == "test-id-1"
        meta = captured["rows"]["metadata"]
        assert meta["existing_field"] == "keep_me", "must preserve existing metadata fields"
        assert "notes" in meta, "notes must be embedded in metadata JSONB"
        assert meta["notes"][0]["text"] == "A note"

    def test_shadow_write_identities_batch_embeds_notes(self):
        from app import supabase_data

        captured_rows = []

        def fake_upsert(rows):
            captured_rows.extend(rows)
            mock_exec = MagicMock()
            mock_exec.execute = MagicMock(return_value=MagicMock(data=rows))
            return mock_exec

        mock_table = MagicMock()
        mock_table.upsert = fake_upsert
        # select() chain for prefetch returns empty
        mock_select = MagicMock()
        mock_select.in_ = MagicMock(return_value=MagicMock(execute=MagicMock(return_value=MagicMock(data=[]))))
        mock_table.select = MagicMock(return_value=mock_select)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        identities = [
            {
                "identity_id": "test-id-2",
                "name": "Test 2",
                "state": "INBOX",
                "anchor_ids": [],
                "candidate_ids": [],
                "negative_ids": [],
                "metadata": {},
                "notes": [{"id": "n1", "text": "Provenance note", "author": "session-156"}],
                "version_id": 1,
            }
        ]

        with patch.object(supabase_data, "get_supabase_client", return_value=mock_client):
            supabase_data.shadow_write_identities_batch(identities, strict=True)

        assert len(captured_rows) == 1
        assert "notes" in captured_rows[0]["metadata"]
        assert captured_rows[0]["metadata"]["notes"][0]["text"] == "Provenance note"


class TestNotesExtractedFromMetadataOnLoad:
    def test_load_from_postgres_extracts_notes_from_metadata(self):
        from core.registry import IdentityRegistry

        # Mock the supabase client to return one identity row with metadata.notes
        mock_result = MagicMock()
        mock_result.data = [
            {
                "identity_id": "id-1",
                "name": "Test",
                "display_name": None,
                "state": "INBOX",
                "anchor_ids": ["face-1"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-05-08T00:00:00Z",
                "updated_at": "2026-05-08T00:00:00Z",
                "merged_into": None,
                "metadata": {
                    "notes": [
                        {
                            "id": "n1",
                            "text": "Originally misidentified as Harry Fox",
                            "author": "session-156",
                            "timestamp": "2026-05-08T00:00:00Z",
                        }
                    ]
                },
                "primary_face_id": None,
            }
        ]
        # Second call returns empty -> exits paginator
        mock_empty = MagicMock()
        mock_empty.data = []

        mock_table_select = MagicMock()
        mock_table_select.range = MagicMock(side_effect=[
            MagicMock(execute=MagicMock(return_value=mock_result)),
            MagicMock(execute=MagicMock(return_value=mock_empty)),
        ])

        mock_table = MagicMock()
        mock_table.select = MagicMock(return_value=mock_table_select)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client), \
             patch("app.supabase_data.load_identity_history_from_supabase", return_value=[]):
            registry = IdentityRegistry.load_from_postgres()

        assert registry is not None
        notes = registry.get_notes("id-1")
        assert len(notes) == 1
        assert notes[0]["text"] == "Originally misidentified as Harry Fox"


class TestRoundTripPreservesNotes:
    def test_notes_survive_write_then_read(self):
        """Full round-trip: add note -> shadow_write embeds in metadata -> load extracts back to top-level."""
        from app import supabase_data
        from core.registry import IdentityRegistry

        captured_metadata = {}

        # Capture the metadata that shadow_write produces
        def fake_upsert(rows):
            captured_metadata["meta"] = rows["metadata"]
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[rows])))

        mock_table_write = MagicMock()
        mock_table_write.upsert = fake_upsert
        mock_client_write = MagicMock()
        mock_client_write.table = MagicMock(return_value=mock_table_write)

        identity_data = {
            "identity_id": "rt-1",
            "name": "RoundTrip",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {},
            "notes": [{"id": "n1", "text": "RT note", "author": "session-156"}],
            "version_id": 1,
        }

        with patch.object(supabase_data, "get_supabase_client", return_value=mock_client_write):
            supabase_data.shadow_write_identity(identity_data, strict=True)

        # Now simulate load with that metadata
        meta = captured_metadata["meta"]
        assert "notes" in meta

        mock_result = MagicMock()
        mock_result.data = [{
            "identity_id": "rt-1", "name": "RoundTrip", "display_name": None,
            "state": "INBOX", "anchor_ids": [], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": None, "updated_at": None,
            "merged_into": None, "metadata": meta, "primary_face_id": None,
        }]
        mock_empty = MagicMock(); mock_empty.data = []
        mock_table_read = MagicMock()
        mock_table_read.select = MagicMock(return_value=MagicMock(
            range=MagicMock(side_effect=[
                MagicMock(execute=MagicMock(return_value=mock_result)),
                MagicMock(execute=MagicMock(return_value=mock_empty)),
            ])
        ))
        mock_client_read = MagicMock()
        mock_client_read.table = MagicMock(return_value=mock_table_read)

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client_read), \
             patch("app.supabase_data.load_identity_history_from_supabase", return_value=[]):
            registry = IdentityRegistry.load_from_postgres()

        notes = registry.get_notes("rt-1")
        assert len(notes) == 1
        assert notes[0]["text"] == "RT note"
