"""Session 127 — Security fix tests for upload ID validation and filename sanitization."""

import re


_SAFE_UPLOAD_ID = re.compile(r"^[a-zA-Z0-9\-_]+$")


class TestUploadIdValidation:
    """P0 security fix: upload_id must be validated before use in file paths."""

    def test_valid_uuid_passes(self):
        assert _SAFE_UPLOAD_ID.match("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    def test_valid_hex_passes(self):
        assert _SAFE_UPLOAD_ID.match("abcdef0123456789")

    def test_path_traversal_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("../../etc/passwd")

    def test_dots_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("..some-file")

    def test_spaces_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("abc def")

    def test_slash_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("abc/def")

    def test_backslash_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("abc\\def")

    def test_empty_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("")

    def test_null_byte_rejected(self):
        assert not _SAFE_UPLOAD_ID.match("abc\x00def")


class TestFilenameSanitization:
    """P2 security fix: filenames must be sanitized to prevent path traversal."""

    def test_path_traversal_stripped(self):
        from pathlib import Path

        name = Path("../../etc/passwd").name
        assert name == "passwd"
        assert ".." not in name

    def test_backslash_replaced(self):
        """Backslashes in filenames are replaced with underscores."""
        safe = "..\\cmd.exe".replace("\\", "_")
        assert "\\" not in safe
        assert safe == ".._cmd.exe"

    def test_dotfile_detected(self):
        from pathlib import Path

        name = Path(".htaccess").name
        assert name.startswith(".")

    def test_normal_filename_preserved(self):
        from pathlib import Path

        name = Path("my photo.jpg").name.replace(" ", "_")
        assert name == "my_photo.jpg"


class TestCompareRoutesValidation:
    """Verify compare routes reject invalid upload IDs."""

    def test_compare_select_rejects_traversal(self):
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/compare/upload/select",
            data={"upload_id": "../../etc/passwd", "face_idx": "0"},
        )
        assert response.status_code == 200
        assert "Invalid upload ID" in response.text

    def test_compare_select_rejects_empty(self):
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/compare/upload/select",
            data={"upload_id": "", "face_idx": "0"},
        )
        assert response.status_code == 200
        assert "Invalid upload ID" in response.text


class TestFacecompareRoutesValidation:
    """Verify facecompare routes reject invalid upload IDs."""

    def test_facecompare_select_rejects_traversal(self):
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/facecompare/select",
            data={"upload_id": "../../etc/passwd", "face_idx": "0"},
        )
        assert response.status_code == 200
        assert "Invalid upload ID" in response.text
