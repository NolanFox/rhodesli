"""Structural tests to prevent split-brain regression.

Session 105b: These tests read source code and verify that dual-write patterns
are maintained. They catch if someone removes a Supabase write path in a future session.
"""

import ast
import inspect
import textwrap

import pytest


class TestSaveRegistryDualWrite:
    """save_registry() must write to both JSON and Supabase."""

    def test_save_registry_calls_shadow_write_identities_batch(self):
        """save_registry() must call shadow_write_identities_batch."""
        from app.main import save_registry

        source = inspect.getsource(save_registry)
        assert "shadow_write_identities_batch" in source, (
            "save_registry() must call shadow_write_identities_batch for Supabase dual-write"
        )

    def test_save_photo_registry_calls_shadow_write_photos_batch(self):
        """save_photo_registry() must call shadow_write_photos_batch."""
        from app.main import save_photo_registry

        source = inspect.getsource(save_photo_registry)
        assert "shadow_write_photos_batch" in source, (
            "save_photo_registry() must call shadow_write_photos_batch for Supabase dual-write"
        )

    def test_save_photo_registry_calls_shadow_write_photo_faces_batch(self):
        """save_photo_registry() must call shadow_write_photo_faces_batch (Lesson 145)."""
        from app.main import save_photo_registry

        source = inspect.getsource(save_photo_registry)
        assert "shadow_write_photo_faces_batch" in source, (
            "save_photo_registry() must call shadow_write_photo_faces_batch — "
            "photo_faces must be written alongside photos (Lesson 145)"
        )


class TestBackgroundIngestDualWrite:
    """_background_ingest() must write photo_faces to Supabase."""

    def test_background_ingest_calls_shadow_write_photo_faces_batch(self):
        """_background_ingest() must call shadow_write_photo_faces_batch."""
        import app.upload_routes

        source = inspect.getsource(app.upload_routes)
        assert "shadow_write_photo_faces_batch" in source, (
            "upload_routes must call shadow_write_photo_faces_batch — "
            "upload pipeline must write photo_faces to Supabase (Lesson 145)"
        )


class TestSyncPushDualWrite:
    """sync push handler must write photo_faces to Supabase."""

    def test_sync_push_calls_shadow_write_photo_faces_batch(self):
        """/api/sync/push handler must call shadow_write_photo_faces_batch."""
        import app.sync_routes

        source = inspect.getsource(app.sync_routes)
        # The sync_routes module must contain calls to all three batch writers
        assert "shadow_write_photo_faces_batch" in source, (
            "sync_routes must call shadow_write_photo_faces_batch — /api/sync/push must write photo_faces (Lesson 145)"
        )


class TestNoSilentExceptionSwallowing:
    """supabase_data.py must not silently swallow exceptions with bare pass."""

    def test_no_broad_except_pass_in_supabase_data(self):
        """No broad `except Exception` blocks should use bare `pass` — must at minimum log.

        Narrow exceptions (ImportError for optional deps, json.JSONDecodeError for parsing)
        are acceptable with pass since they have well-defined fallback behavior.
        """
        import app.supabase_data

        source = inspect.getsource(app.supabase_data)

        # Parse the AST and find except handlers that catch broad Exception with bare pass
        tree = ast.parse(source)
        broad_pass_handlers = []

        # Narrow exception types that are OK to silently pass
        allowed_narrow = {"ImportError", "JSONDecodeError", "TypeError", "ValueError"}

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if body is just `pass`
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    # Check what exception type is caught
                    if node.type is None:
                        # Bare `except:` — always bad
                        broad_pass_handlers.append(node.lineno)
                    elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                        # `except Exception: pass` — bad
                        broad_pass_handlers.append(node.lineno)
                    elif isinstance(node.type, ast.Tuple):
                        # `except (A, B): pass` — check if all are narrow
                        names = {elt.id for elt in node.type.elts if isinstance(elt, ast.Name)}
                        if not names.issubset(allowed_narrow):
                            broad_pass_handlers.append(node.lineno)
                    elif isinstance(node.type, ast.Name) and node.type.id not in allowed_narrow:
                        broad_pass_handlers.append(node.lineno)

        assert len(broad_pass_handlers) == 0, (
            f"supabase_data.py has broad `except: pass` at lines {broad_pass_handlers} — "
            "all broad exception handlers must at minimum log the error (Lesson 136)"
        )


class TestHealthParityUsesTotalIdentities:
    """Health endpoint must compare total identities (including merged) for parity."""

    def test_health_passes_include_merged_to_parity_check(self):
        """Health endpoint must use include_merged=True for identity count."""
        from app import page_routes

        source = inspect.getsource(page_routes.health)
        assert "include_merged=True" in source, (
            "Health endpoint must pass include_merged=True to _check_data_parity "
            "so JSON count matches Supabase (which stores all identities including merged)"
        )


class TestStartupParityCheck:
    """Startup event must include a parity check."""

    def test_startup_event_has_parity_check(self):
        """startup_event must reference _startup_parity_check or _check_data_parity."""
        from app.main import startup_event

        source = inspect.getsource(startup_event)
        assert "_startup_parity_check" in source or "_check_data_parity" in source, (
            "startup_event must include a parity check (Session 105b Phase 2)"
        )
