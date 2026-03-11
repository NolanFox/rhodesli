"""
Upload routes extracted from app/main.py.

All /upload/* routes plus upload-exclusive helpers (upload_area).
"""

import io
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from fasthtml.common import *
from starlette.datastructures import UploadFile

# Import route decorator only (bound once, never reassigned)
from app.main import rt

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)


# --- TIFF Detection and Conversion (PRD-035) ---


def is_tiff(filename: str, file_bytes: bytes) -> bool:
    """Detect TIFF files by extension or magic bytes."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("tif", "tiff"):
        return True
    # Magic bytes check: little-endian (II) or big-endian (MM)
    if len(file_bytes) >= 4:
        header = file_bytes[:4]
        if header in (b"II\x2a\x00", b"MM\x00\x2a"):
            return True
    return False


def convert_tiff_to_jpg(file_bytes: bytes, quality: int = 95) -> bytes:
    """Convert TIFF image bytes to JPEG. Preserves EXIF if available."""
    from PIL import Image

    img = Image.open(io.BytesIO(file_bytes))
    output = io.BytesIO()
    # Convert to RGB if necessary (TIFF can be CMYK, RGBA, etc.)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    exif = img.info.get("exif", b"")
    if exif:
        img.save(output, "JPEG", quality=quality, exif=exif)
    else:
        img.save(output, "JPEG", quality=quality)
    output.seek(0)
    return output.read()


def upload_area(existing_sources: list[str] = None, existing_collections: list[str] = None) -> Div:
    """
    Drag-and-drop file upload area with separate collection, source, and source URL fields.
    UX Intent: Easy bulk ingestion into inbox with provenance tracking.

    Args:
        existing_sources: List of existing source labels for autocomplete
        existing_collections: List of existing collection labels for autocomplete
    """
    if existing_sources is None:
        existing_sources = []
    if existing_collections is None:
        existing_collections = []

    # JS for two-step upload: select files → preview list → click Upload
    upload_script = Script("""
    (function() {
        var selectedFiles = [];

        document.addEventListener('change', function(e) {
            if (e.target && e.target.id === 'upload-file-input') {
                selectedFiles = Array.from(e.target.files);
                renderFileList();
            }
        });

        // Drag-and-drop support
        document.addEventListener('dragover', function(e) {
            var dropZone = document.getElementById('upload-drop-zone');
            if (dropZone && dropZone.contains(e.target)) {
                e.preventDefault();
                dropZone.classList.add('border-indigo-400', 'bg-slate-700/50');
            }
        });
        document.addEventListener('dragleave', function(e) {
            var dropZone = document.getElementById('upload-drop-zone');
            if (dropZone && !dropZone.contains(e.relatedTarget)) {
                dropZone.classList.remove('border-indigo-400', 'bg-slate-700/50');
            }
        });
        document.addEventListener('drop', function(e) {
            var dropZone = document.getElementById('upload-drop-zone');
            if (dropZone && dropZone.contains(e.target)) {
                e.preventDefault();
                dropZone.classList.remove('border-indigo-400', 'bg-slate-700/50');
                var dt = e.dataTransfer;
                if (dt && dt.files.length) {
                    selectedFiles = selectedFiles.concat(Array.from(dt.files));
                    renderFileList();
                }
            }
        });

        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }

        function renderFileList() {
            var preview = document.getElementById('upload-file-preview');
            var uploadBtn = document.getElementById('upload-submit-btn');
            var addMoreBtn = document.getElementById('upload-add-more-btn');
            var dropPrompt = document.getElementById('upload-drop-prompt');
            if (!preview) return;

            if (selectedFiles.length === 0) {
                preview.innerHTML = '';
                preview.classList.add('hidden');
                if (uploadBtn) uploadBtn.classList.add('hidden');
                if (addMoreBtn) addMoreBtn.classList.add('hidden');
                if (dropPrompt) dropPrompt.classList.remove('hidden');
                return;
            }

            if (dropPrompt) dropPrompt.classList.add('hidden');
            if (addMoreBtn) addMoreBtn.classList.remove('hidden');

            var totalSize = selectedFiles.reduce(function(s, f) { return s + f.size; }, 0);
            var html = '<div class="flex items-center justify-between mb-2">' +
                '<span class="text-sm font-medium text-slate-200">' + selectedFiles.length +
                ' file' + (selectedFiles.length !== 1 ? 's' : '') + ' selected</span>' +
                '<span class="text-xs text-slate-400">' + formatSize(totalSize) + ' total</span></div>';
            html += '<div class="max-h-48 overflow-y-auto space-y-1">';
            for (var i = 0; i < selectedFiles.length; i++) {
                var f = selectedFiles[i];
                html += '<div class="flex items-center justify-between py-1.5 px-2 bg-slate-700/50 rounded text-sm">' +
                    '<span class="text-slate-300 truncate mr-2" style="max-width:70%">' + f.name + '</span>' +
                    '<div class="flex items-center gap-2 shrink-0">' +
                    '<span class="text-xs text-slate-500">' + formatSize(f.size) + '</span>' +
                    '<button type="button" data-action="remove-upload-file" data-index="' + i + '" ' +
                    'class="text-slate-500 hover:text-red-400 text-xs px-1">&times;</button>' +
                    '</div></div>';
            }
            html += '</div>';
            preview.innerHTML = html;
            preview.classList.remove('hidden');
            if (uploadBtn) uploadBtn.classList.remove('hidden');
        }

        // Remove individual file
        document.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-action="remove-upload-file"]');
            if (btn) {
                var idx = parseInt(btn.getAttribute('data-index'));
                selectedFiles.splice(idx, 1);
                renderFileList();
            }
        });

        // Upload button click — build FormData and submit via HTMX-compatible fetch
        document.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-action="upload-submit"]');
            if (!btn || selectedFiles.length === 0) return;

            var fd = new FormData();
            for (var i = 0; i < selectedFiles.length; i++) {
                fd.append('files', selectedFiles[i]);
            }
            var src = document.getElementById('upload-source');
            var col = document.getElementById('upload-collection');
            var url = document.getElementById('upload-source-url');
            if (src) fd.append('source', src.value);
            if (col) fd.append('collection', col.value);
            if (url) fd.append('source_url', url.value);

            var status = document.getElementById('upload-status');
            if (status) status.innerHTML = '<div class="flex items-center gap-2 py-3"><div class="animate-spin h-5 w-5 border-2 border-indigo-400 border-t-transparent rounded-full"></div><span class="text-sm text-slate-300">Uploading ' + selectedFiles.length + ' file' + (selectedFiles.length !== 1 ? 's' : '') + '...</span></div>';
            btn.disabled = true;
            btn.textContent = 'Uploading...';

            fetch('/upload', {
                method: 'POST',
                body: fd,
                credentials: 'same-origin'
            }).then(function(r) { return r.text(); })
            .then(function(html) {
                if (status) {
                    status.innerHTML = html;
                    // CRITICAL: Tell HTMX to process new content (enables polling attributes)
                    if (window.htmx) htmx.process(status);
                }
                selectedFiles = [];
                renderFileList();
                btn.disabled = false;
                btn.textContent = 'Upload Files';
                // Reset file input
                var inp = document.getElementById('upload-file-input');
                if (inp) inp.value = '';
            }).catch(function(err) {
                if (status) status.innerHTML = '<div class="p-2 text-red-400 text-sm">Upload failed: ' + err.message + '</div>';
                btn.disabled = false;
                btn.textContent = 'Upload Files';
            });
        });

        // "Add more" click re-opens file picker
        document.addEventListener('click', function(e) {
            if (e.target.closest('[data-action="upload-add-more"]')) {
                var inp = document.getElementById('upload-file-input');
                if (inp) inp.click();
            }
        });
    })();
    """)

    return Div(
        upload_script,
        # Metadata fields — optional, can be filled before or after upload
        Div(
            P("Categorize your photos (optional — you can do this later)", cls="text-sm text-slate-400 mb-3"),
            # Collection field
            Div(
                Label("Collection", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="text",
                    name="collection",
                    id="upload-collection",
                    placeholder="e.g., Immigration Records, Wedding Photos",
                    list="collection-suggestions",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                    "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                    "focus:border-transparent",
                ),
                Datalist(*[Option(value=c) for c in existing_collections], id="collection-suggestions")
                if existing_collections
                else None,
                P("How you want to organize these in the archive", cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3",
            ),
            # Source field
            Div(
                Label("Source", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="text",
                    name="source",
                    id="upload-source",
                    placeholder="e.g., Newspapers.com, Betty's Album, Rhodes Facebook Group",
                    list="source-suggestions",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                    "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                    "focus:border-transparent",
                ),
                Datalist(*[Option(value=s) for s in existing_sources], id="source-suggestions")
                if existing_sources
                else None,
                P("Where did these photos come from?", cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3",
            ),
            # Source URL field
            Div(
                Label("Source URL", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="url",
                    name="source_url",
                    id="upload-source-url",
                    placeholder="https://...",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                    "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                    "focus:border-transparent",
                ),
                P("Link to the original (for citation)", cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3",
            ),
            cls="mb-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700",
        ),
        # File selection area (two-step: select → preview → upload)
        Div(
            # Drop zone prompt (hidden after files selected)
            Div(
                Span("\u2191", cls="text-4xl text-slate-500"),
                P("Drop photos here or click to select", cls="text-slate-300 mt-2 font-medium"),
                P("Multiple files allowed \u2022 JPG, PNG, or ZIP", cls="text-xs text-slate-500 mt-1"),
                id="upload-drop-prompt",
                cls="text-center py-8",
            ),
            # Hidden file input
            Input(
                type="file",
                name="files",
                id="upload-file-input",
                accept="image/*,.zip",
                multiple=True,
                cls="absolute inset-0 opacity-0 cursor-pointer",
            ),
            # File preview list (populated by JS)
            Div(id="upload-file-preview", cls="hidden px-2 py-3"),
            id="upload-drop-zone",
            cls="relative",
        ),
        # Action buttons (below the drop zone)
        Div(
            Button(
                "+ Add more files",
                type="button",
                data_action="upload-add-more",
                cls="px-3 py-1.5 text-xs text-slate-400 border border-slate-600 rounded hover:text-slate-200 hover:border-slate-500 hidden",
                id="upload-add-more-btn",
            ),
            Button(
                "Upload Files",
                type="button",
                data_action="upload-submit",
                id="upload-submit-btn",
                cls="hidden px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg "
                "hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
            ),
            cls="flex items-center justify-between mt-3",
        ),
        Div(id="upload-status", cls="mt-2"),
        cls="border-2 border-dashed border-slate-600 rounded-lg p-4 hover:border-slate-500 hover:bg-slate-800/50 transition-colors mb-4",
    )


# =============================================================================
# ROUTES - INBOX INGESTION
# =============================================================================


@rt("/upload")
def get(sess=None, request=None):
    """
    Render the upload page. Requires login when auth is enabled.
    Non-admin uploads go through the moderation queue (pending_uploads.json).
    """
    denied = _main_mod._check_login(sess)
    if denied:
        return denied
    user = _main_mod.get_current_user(sess or {})
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
            overflow-x: hidden;
        }
        body {
            background-color: #0f172a;
        }
        /* Mobile responsive layout */
        @media (max-width: 767px) {
            .mobile-header { display: flex !important; }
            .main-content { margin-left: 0 !important; padding-top: 3.5rem; }
            .main-content .main-inner { padding: 1rem; }
        }
        @media (min-width: 768px) and (max-width: 1023px) {
            .mobile-header { display: flex !important; }
            .main-content { margin-left: 0 !important; padding-top: 3.5rem; }
            .main-content .main-inner { padding: 1.5rem; }
        }
        @media (min-width: 1024px) {
            .mobile-header { display: none !important; }
            .main-content { margin-left: 16rem; }
        }
    """)

    # Canonical sidebar counts
    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry, community=community)

    # Load existing sources and collections for autocomplete
    existing_sources = []
    existing_collections = []
    try:
        from core.photo_registry import PhotoRegistry

        photo_registry = PhotoRegistry.load(_main_mod.data_path / "photo_index.json")
        sources_set = set()
        collections_set = set()
        for photo_id in photo_registry._photos:
            source = photo_registry.get_source(photo_id)
            if source:
                sources_set.add(source)
            collection = photo_registry.get_collection(photo_id)
            if collection:
                collections_set.add(collection)
        existing_sources = sorted(sources_set)
        existing_collections = sorted(collections_set)
    except FileNotFoundError:
        pass  # No photos yet

    upload_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    mobile_header = Div(
        Button(
            Svg(
                Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
            ),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center",
        ),
        Span("Upload Photos", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30",
    )
    sidebar_overlay = Div(
        onclick="closeSidebar()", cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )
    sidebar_script = Script("""
        function toggleSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.toggle('open');
            sb.classList.toggle('-translate-x-full');
            ov.classList.toggle('hidden');
        }
        function closeSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.remove('open');
            sb.classList.add('-translate-x-full');
            ov.classList.add('hidden');
        }
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
        })();
    """)

    return (
        Title("Upload Photos - Rhodesli"),
        style,
        upload_style,
        Div(
            _main_mod.toast_container(),
            mobile_header,
            sidebar_overlay,
            _main_mod.sidebar(
                counts, current_section=None, user=user, community_slug=community_slug, community=community
            ),
            # Sidebar overlay for mobile
            Div(
                cls="fixed inset-0 bg-black bg-opacity-50 z-30 hidden",
                id="sidebar-overlay",
                onclick="closeSidebar()",
            ),
            Main(
                Div(
                    # Header
                    Div(
                        H2("Upload Photos", cls="text-2xl font-bold text-white"),
                        P("Add new photos for identity analysis", cls="text-sm text-slate-400 mt-1"),
                        cls="mb-6",
                    ),
                    # Upload form
                    upload_area(existing_sources=existing_sources, existing_collections=existing_collections),
                    cls="max-w-3xl mx-auto px-4 sm:px-8 py-6",
                ),
                cls="main-content min-h-screen overflow-x-hidden",
            ),
            sidebar_script,
            cls="h-full",
        ),
    )


@rt("/upload")
async def post(
    files: list[UploadFile], source: str = "", collection: str = "", source_url: str = "", sess=None, request=None
):
    """
    Accept file upload(s) and optionally spawn subprocess for processing.
    Requires login. Non-admin uploads go to moderation queue.

    Handles multiple files (images and/or ZIPs) in a single batch job.
    All files are saved to a job directory.

    All uploads go to data/staging/{job_id}/.

    Admin flow:
        When PROCESSING_ENABLED=True (default, local + Railway):
            - Subprocess spawned to run core/ingest_inbox.py
            - Real-time status polling
            - R2 upload of photos + crops on completion (if R2 configured)
        When PROCESSING_ENABLED=False:
            - No subprocess spawned
            - Shows "staged for local processing" message

    Non-admin flow:
        - Pending upload record created in pending_uploads.json
        - Admin email notification sent (if RESEND_API_KEY configured)
        - Shows "submitted for review" message

    Args:
        files: Uploaded image files or ZIPs
        source: Provenance/origin label (e.g., "Newspapers.com")
        collection: Classification label (e.g., "Immigration Records")
        source_url: Citation URL (e.g., "https://newspapers.com/article/123")

    Returns HTML partial with upload status.
    """
    denied = _main_mod._check_login(sess)
    if denied:
        return denied

    # Community context from middleware (PRD-035)
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None
    # Capture community_id for background thread (avoids request state access after response)
    upload_community_id = None
    if community and community.get("id"):
        upload_community_id = community["id"]

    import uuid

    # Filter out empty uploads
    valid_files = [f for f in files if f and f.filename]

    if not valid_files:
        return Div(P("No files selected.", cls="text-red-600 text-sm"), cls="p-2")

    # --- Upload safety checks ---
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
    MAX_BATCH_SIZE = 500 * 1024 * 1024  # 500 MB per batch
    MAX_FILES_PER_UPLOAD = 200
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".zip"}

    if len(valid_files) > MAX_FILES_PER_UPLOAD:
        return Div(
            P(f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} per upload.", cls="text-red-400 text-sm"), cls="p-2"
        )

    # Validate file extensions before reading content
    for f in valid_files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Div(
                P(f"File type '{ext}' not allowed. Accepted: images and .zip archives.", cls="text-red-400 text-sm"),
                cls="p-2",
            )

    # Determine if current user is admin
    user = _main_mod.get_current_user(sess or {})
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True
    uploader_email = user.email if user else "unknown"

    data_path = _main_mod.data_path

    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]

    # All uploads go to staging first (processing or moderation)
    job_dir = data_path / "staging" / job_id

    job_dir.mkdir(parents=True, exist_ok=True)

    # Save all files to job directory with size checks
    saved_files = []
    total_size = 0
    for f in valid_files:
        # Sanitize filename
        safe_filename = f.filename.replace(" ", "_").replace("/", "_")
        upload_path = job_dir / safe_filename

        # Read and check file size
        content = await f.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            # Clean up job dir on failure
            import shutil

            shutil.rmtree(job_dir, ignore_errors=True)
            mb = file_size / (1024 * 1024)
            return Div(
                P(
                    f"File '{safe_filename}' is too large ({mb:.1f} MB). Maximum is 50 MB per file.",
                    cls="text-red-400 text-sm",
                ),
                cls="p-2",
            )

        total_size += file_size
        if total_size > MAX_BATCH_SIZE:
            import shutil

            shutil.rmtree(job_dir, ignore_errors=True)
            return Div(P("Total batch size exceeds 500 MB limit.", cls="text-red-400 text-sm"), cls="p-2")

        # TIFF auto-conversion to JPEG (PRD-035)
        if is_tiff(safe_filename, content):
            try:
                content = convert_tiff_to_jpg(content)
                # Update filename to .jpg
                safe_filename = safe_filename.rsplit(".", 1)[0] + ".jpg"
                upload_path = job_dir / safe_filename
                logger.info(f"Converted TIFF to JPEG: {f.filename} -> {safe_filename}")
            except Exception as e:
                logger.warning(f"TIFF conversion failed for {safe_filename}: {e}")
                # Fall through and save as-is

        with open(upload_path, "wb") as out:
            out.write(content)
        saved_files.append(safe_filename)

    # Save metadata for staged uploads (helps admin know context)
    metadata = {
        "job_id": job_id,
        "source": source or "Unknown",
        "collection": collection or "",
        "source_url": source_url or "",
        "files": saved_files,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "processing_enabled": _main_mod.PROCESSING_ENABLED,
        "uploader_email": uploader_email,
        "community_id": upload_community_id or "",
    }
    metadata_path = job_dir / "_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Track upload event
    _main_mod.posthog_capture(
        "photo_uploaded",
        distinct_id=uploader_email or "anonymous",
        properties={
            "file_count": len(saved_files),
            "source": source or "Unknown",
            "collection": collection or "",
            "is_admin": user_is_admin,
        },
    )

    # Non-admin flow: create pending upload record and notify admin
    if not user_is_admin:
        pending = _main_mod._load_pending_uploads()
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "uploader_email": uploader_email,
            "source": source or "Unknown",
            "collection": collection or "",
            "source_url": source_url or "",
            "files": saved_files,
            "file_count": len(saved_files),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        _main_mod._save_pending_uploads(pending)

        # Dual-write to Supabase
        from app.supabase_data import sync_pending_upload

        sync_pending_upload(job_id, pending["uploads"][job_id])

        # Fire-and-forget email notification to admin
        try:
            await _main_mod._notify_admin_upload(uploader_email, job_id, len(saved_files), source)
        except Exception:
            pass  # Email notification failure should never block upload

        file_count = len(saved_files)
        file_msg = "1 photo" if file_count == 1 else f"{file_count} photos"

        return Div(
            Div(
                Span("\u2713", cls="text-green-400 text-lg"),
                P(f"Submitted {file_msg} for review", cls="text-slate-200 font-medium"),
                cls="flex items-center gap-2",
            ),
            P(
                "Your upload has been submitted for admin review. "
                "You'll see the photos once they are approved and processed.",
                cls="text-slate-400 text-sm mt-1",
            ),
            P(f"Reference: {job_id}", cls="text-slate-500 text-xs mt-2 font-mono"),
            cls="p-3 bg-green-900/20 border border-green-500/30 rounded",
        )

    # Admin flow: If processing is disabled (production), stage for local processing
    if not _main_mod.PROCESSING_ENABLED:
        file_count = len(saved_files)
        file_msg = "1 photo" if file_count == 1 else f"{file_count} photos"

        # Create a pending upload record so it appears on the admin pending page
        pending = _main_mod._load_pending_uploads()
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "uploader_email": uploader_email,
            "source": source or "Unknown",
            "collection": collection or "",
            "source_url": source_url or "",
            "files": saved_files,
            "file_count": file_count,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "staged",
        }
        _main_mod._save_pending_uploads(pending)

        # Build metadata detail line
        detail_parts = []
        if collection:
            detail_parts.append(f"Collection: {collection}")
        if source:
            detail_parts.append(f"Source: {source}")
        detail_line = " \u00b7 ".join(detail_parts) if detail_parts else ""

        return Div(
            Div(
                Span("\u2713", cls="text-green-400 text-lg"),
                P(f"{file_msg} uploaded successfully", cls="text-slate-200 font-medium"),
                cls="flex items-center gap-2",
            ),
            P(detail_line, cls="text-slate-300 text-sm mt-1") if detail_line else None,
            P(
                "Staged for processing. Run the local pipeline to detect faces and push to production.",
                cls="text-slate-400 text-sm mt-1",
            ),
            A(
                "View in Pending Uploads \u2192",
                href="/admin/pending",
                cls="inline-block text-blue-400 hover:text-blue-300 text-sm mt-2 underline",
            ),
            P(f"Reference: {job_id}", cls="text-slate-500 text-xs mt-2 font-mono"),
            cls="p-3 bg-green-900/20 border border-green-500/30 rounded",
        )

    # Processing enabled: run ML processing in background thread (AD-161).
    # CRITICAL: Uses a thread (not subprocess) to share the already-loaded hybrid
    # InsightFace models from the main process. A subprocess would load buffalo_l
    # (~300-500MB) separately, causing OOM on Railway's 512MB container.

    import json as _json_upload

    inbox_dir = data_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    # Write initial status file
    initial_status = {
        "status": "starting",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(saved_files),
        "files_succeeded": 0,
        "files_failed": 0,
    }
    with open(inbox_dir / f"{job_id}.status.json", "w") as _sf:
        _json_upload.dump(initial_status, _sf)

    def _background_ingest():
        """Run face detection in background thread using shared hybrid models.

        AD-165: This thread handles the FULL pipeline including R2 upload.
        Previous bug: R2 upload was in the status polling endpoint, but the
        staging directory was deleted here before the poll could upload.
        Now: R2 upload happens here, BEFORE staging cleanup.
        """
        import logging as _bg_logging

        log_path = inbox_dir / f"{job_id}.log"
        try:
            # Redirect logging to file for debugging
            file_handler = _bg_logging.FileHandler(str(log_path))
            file_handler.setLevel(_bg_logging.INFO)
            _bg_logging.getLogger("core.ingest_inbox").addHandler(file_handler)

            from core.ingest_inbox import process_directory

            result = process_directory(
                directory=job_dir,
                job_id=job_id,
                data_dir=data_path,
                source=source,
                collection=collection,
                prefer_hybrid=True,  # Use already-loaded hybrid models (AD-161)
                uploaded_by=uploader_email,
                upload_date=datetime.now(timezone.utc).isoformat(),
            )

            # AD-165: Upload to R2 INSIDE the thread, BEFORE staging cleanup.
            # Previous bug: staging dir was deleted before R2 upload could happen.
            from core.storage import can_write_r2, upload_bytes_to_r2

            if can_write_r2() and result.get("status") in ("success", "partial"):
                try:
                    import mimetypes

                    r2_count = 0

                    # Upload original photos from staging directory (still exists!)
                    for fpath in job_dir.iterdir():
                        if fpath.is_file() and fpath.suffix.lower() in (".jpg", ".jpeg", ".png"):
                            ct = mimetypes.guess_type(fpath.name)[0] or "image/jpeg"
                            upload_bytes_to_r2(f"raw_photos/{fpath.name}", fpath.read_bytes(), content_type=ct)
                            r2_count += 1

                    # Upload new crop files
                    crops_dir = Path("app/static/crops")
                    if crops_dir.exists():
                        for fid in result.get("face_ids", []):
                            crop_path = crops_dir / f"{fid}.jpg"
                            if crop_path.exists():
                                upload_bytes_to_r2(
                                    f"crops/{crop_path.name}", crop_path.read_bytes(), content_type="image/jpeg"
                                )
                                r2_count += 1

                    # Update status file with R2 info
                    status_path = inbox_dir / f"{job_id}.status.json"
                    if status_path.exists():
                        with open(status_path) as _rf:
                            status_data = _json_upload.load(_rf)
                        status_data["r2_uploaded"] = True
                        status_data["r2_count"] = r2_count
                        with open(status_path, "w") as _wf:
                            _json_upload.dump(status_data, _wf, indent=2)

                    print(f"[upload] R2 upload complete: {r2_count} files for job {job_id}")
                except Exception as e:
                    print(f"[upload] R2 upload error for job {job_id}: {e}")

            # Tag photos to community (PRD-035)
            if upload_community_id and result.get("status") in ("success", "partial"):
                try:
                    from app.supabase_data import add_photo_to_community

                    for pid in result.get("photo_ids", []):
                        add_photo_to_community(pid, upload_community_id)
                    print(
                        f"[upload] Tagged {len(result.get('photo_ids', []))} photos to community {upload_community_id}"
                    )
                except Exception as e:
                    print(f"[upload] Community tagging error for job {job_id}: {e}")

            # PRD-037 Phase 1: Auto-cluster new faces after ingest (AD-215)
            if result.get("status") in ("success", "partial") and result.get("face_ids"):
                try:
                    from scripts.cluster_new_faces import (
                        find_matches,
                        load_face_data,
                        load_identities,
                    )
                    from core.config import MATCH_THRESHOLD_HIGH

                    identities_data = load_identities(data_path)
                    face_data_dict = load_face_data(data_path)
                    suggestions = find_matches(identities_data, face_data_dict, MATCH_THRESHOLD_HIGH)

                    if suggestions:
                        import json as _json_cluster
                        from datetime import datetime as _dt_cluster, timezone as _tz_cluster

                        # BUG-7 fix: Do NOT auto-apply suggestions. Write proposals only.
                        # Applying suggestions merges source identities, making them invisible
                        # to discoveries (which looks for INBOX/PROPOSED source identities).
                        # Gatekeeper pattern: proposals are for admin review, not auto-merge.
                        proposals_path = data_path / "proposals.json"
                        proposals_data = {
                            "generated_at": _dt_cluster.now(_tz_cluster.utc).isoformat(),
                            "threshold": MATCH_THRESHOLD_HIGH,
                            "proposals": suggestions,
                        }
                        with open(proposals_path, "w") as _pf:
                            _json_cluster.dump(proposals_data, _pf, indent=2)

                    cluster_result = f"{len(suggestions)} matches found"
                    print(f"[upload] Auto-cluster complete for job {job_id}: {cluster_result}")

                    # Update status file with cluster info
                    status_path = inbox_dir / f"{job_id}.status.json"
                    if status_path.exists():
                        with open(status_path) as _rf:
                            status_data = _json_upload.load(_rf)
                        status_data["cluster_complete"] = True
                        status_data["cluster_result"] = str(cluster_result)
                        with open(status_path, "w") as _wf:
                            _json_upload.dump(status_data, _wf, indent=2)
                except Exception as e:
                    print(f"[upload] Auto-cluster error for job {job_id}: {e}")
                    # Auto-cluster failure should NOT block the upload

            # AD-216: Group similar unknown faces into clusters after auto-cluster
            if result.get("status") in ("success", "partial") and result.get("face_ids"):
                try:
                    from core.grouping import group_inbox_identities

                    registry = _main_mod.load_registry()
                    photo_reg = _main_mod.load_photo_registry()
                    # Load face data the same way auto-cluster does
                    from scripts.cluster_new_faces import load_face_data as _load_fd

                    face_data_for_grouping = _load_fd(data_path)
                    grouping_result = group_inbox_identities(registry, face_data_for_grouping, photo_reg, dry_run=False)
                    if grouping_result.get("total_merged", 0) > 0:
                        _main_mod.save_registry(registry)
                        print(
                            f"[upload] Grouping: {grouping_result['total_merged']} merges "
                            f"in {len(grouping_result.get('groups', []))} clusters for job {job_id}"
                        )
                    else:
                        print(f"[upload] Grouping: no merges needed for job {job_id}")
                except Exception as e:
                    print(f"[upload] Face grouping failed (non-fatal): {e}")

            # AD-216: Tag identities to community after clustering
            # Photo-derived identity set handles this automatically via cache,
            # but explicit tagging in identity_communities improves query performance.
            if upload_community_id and result.get("status") in ("success", "partial"):
                try:
                    from app.supabase_data import add_identity_to_community

                    # Find identities with faces in the newly uploaded photos
                    # Must load from JSON (not Postgres) because new identities only exist in JSON
                    from core.registry import IdentityRegistry as _IR_tag

                    registry = _IR_tag.load(data_path / "identities.json")
                    tagged_count = 0
                    for fid in result.get("face_ids", []):
                        identity = _main_mod.get_identity_for_face(registry, fid)
                        if identity:
                            iid = identity.get("identity_id")
                            if iid:
                                add_identity_to_community(iid, upload_community_id)
                                tagged_count += 1
                    print(f"[upload] Tagged {tagged_count} identities to community {upload_community_id}")
                except Exception as e:
                    print(f"[upload] Identity community tagging error: {e}")

            # Sync identities and photos to Supabase so DATA_SOURCE=postgres sees them.
            # process_directory() writes to JSON only. We MUST load from JSON (not Postgres)
            # because the new data only exists in JSON at this point. Loading from Postgres
            # would read the old data (missing new photos/identities) and write it back,
            # silently losing the new uploads. (Session 96e-cont5 fix)
            if result.get("status") in ("success", "partial"):
                try:
                    from core.registry import IdentityRegistry
                    from core.photo_registry import PhotoRegistry
                    from app.supabase_data import shadow_write_photos_batch, shadow_write_identities_batch

                    # Load from JSON files (where process_directory wrote the new data)
                    json_registry = IdentityRegistry.load(data_path / "identities.json")
                    json_photo_reg = PhotoRegistry.load(data_path / "photo_index.json")

                    # Write ALL photos to Supabase (upsert is idempotent)
                    photo_items = [dict(v, photo_id=k) for k, v in json_photo_reg._photos.items()]
                    shadow_write_photos_batch(photo_items)

                    # Write ALL identities to Supabase (upsert is idempotent)
                    id_items = [dict(v, identity_id=k) for k, v in json_registry._identities.items()]
                    shadow_write_identities_batch(id_items)

                    print(
                        f"[upload] Synced {len(photo_items)} photos + {len(id_items)} identities to Supabase for job {job_id}"
                    )
                except Exception as e:
                    print(f"[upload] Supabase sync error for job {job_id}: {e}")

            # AD-165: Invalidate ALL in-memory caches so the web app sees new data.
            # Without this, the sidebar counts and photo grid remain stale until restart.
            _main_mod._invalidate_all_caches()
            # Also invalidate face_data and photo_registry caches
            _main_mod._face_data_cache = None
            _main_mod._photo_registry_cache = None
            print(f"[upload] Caches invalidated for job {job_id}")

        except Exception as e:
            # Write error to status file so the poller can show it
            error_status = {
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "started_at": initial_status["started_at"],
                "total_files": len(saved_files),
                "files_succeeded": 0,
                "files_failed": len(saved_files),
            }
            try:
                with open(inbox_dir / f"{job_id}.status.json", "w") as _ef:
                    _json_upload.dump(error_status, _ef)
            except Exception:
                pass
            # Also log the traceback
            import traceback

            try:
                with open(log_path, "a") as _lf:
                    traceback.print_exc(file=_lf)
            except Exception:
                pass
        finally:
            # AD-162: Always clean up staging directory to prevent disk exhaustion.
            # R2 upload happens ABOVE (before this finally block), so files are
            # already uploaded before cleanup.
            import shutil as _shutil_cleanup

            try:
                if job_dir.exists():
                    _shutil_cleanup.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass

    thread = threading.Thread(target=_background_ingest, daemon=True, name=f"ingest-{job_id}")
    thread.start()

    # Build initial status message
    file_count = len(saved_files)
    if file_count == 1:
        msg = f"Processing {saved_files[0]}..."
    else:
        msg = f"Processing {file_count} files..."

    # Return status component that polls for completion
    return Div(
        P(msg, cls="text-slate-300 text-sm"),
        Span("\u23f3", cls="animate-pulse"),
        hx_get=f"/upload/status/{job_id}",
        hx_trigger="every 2s",
        hx_swap="outerHTML",
        cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded flex items-center gap-2",
    )


@rt("/upload/status/{job_id}")
def get(job_id: str):
    """
    Poll job status for upload processing.

    Returns HTML partial with current status driven by backend job state.
    Shows real progress (% complete, files processed) and error counts.
    """
    data_path = _main_mod.data_path

    status_path = data_path / "inbox" / f"{job_id}.status.json"

    if not status_path.exists():
        # Status file not yet created - job just started
        return Div(
            P("Starting...", cls="text-slate-300 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded flex items-center gap-2",
        )

    with open(status_path) as f:
        status = json.load(f)

    # Detect stuck "starting" status — subprocess wrote initial file but never
    # progressed to "processing" (likely crashed on import or OOM)
    if status["status"] == "starting":
        from datetime import datetime as _dt_status, timezone as _tz_status

        started_at = status.get("started_at", "")
        try:
            start_time = _dt_status.fromisoformat(started_at)
            elapsed = (_dt_status.now(_tz_status.utc) - start_time).total_seconds()
        except (ValueError, TypeError):
            elapsed = 0

        if elapsed > 120:
            # Process has been "starting" for > 2 minutes — it's dead
            log_path = data_path / "inbox" / f"{job_id}.log"
            log_excerpt = ""
            if log_path.exists():
                try:
                    log_text = log_path.read_text()
                    # Last 500 chars of the log
                    log_excerpt = log_text[-500:] if len(log_text) > 500 else log_text
                except Exception:
                    log_excerpt = "(could not read log)"

            elements = [
                P("Processing failed to start.", cls="text-red-400 text-sm font-medium"),
                P(
                    "The background processing task did not complete. "
                    "This may be due to insufficient memory or missing dependencies.",
                    cls="text-slate-400 text-xs mt-1",
                ),
            ]
            if log_excerpt:
                elements.append(
                    Div(
                        P("Log output:", cls="text-slate-500 text-xs mb-1"),
                        Pre(log_excerpt, cls="text-xs text-red-300 bg-slate-900 p-2 rounded overflow-x-auto max-h-32"),
                        cls="mt-2",
                    )
                )
            return Div(*elements, cls="p-3 bg-red-900/20 border border-red-500/30 rounded")

        # Still within timeout — keep polling
        return Div(
            P("Starting processing...", cls="text-slate-300 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded flex items-center gap-2",
        )

    if status["status"] == "processing":
        # Check for timeout (5 min safety net for stuck threads/processes)
        from datetime import datetime as _dt_proc, timezone as _tz_proc

        started_at = status.get("started_at", "")
        try:
            start_time = _dt_proc.fromisoformat(started_at)
            elapsed_proc = (_dt_proc.now(_tz_proc.utc) - start_time).total_seconds()
        except (ValueError, TypeError):
            elapsed_proc = 0

        if elapsed_proc > 300:
            # Processing timed out — show error with log excerpt
            log_path = data_path / "inbox" / f"{job_id}.log"
            log_excerpt = ""
            if log_path.exists():
                try:
                    log_text = log_path.read_text()
                    log_excerpt = log_text[-500:] if len(log_text) > 500 else log_text
                except Exception:
                    log_excerpt = "(could not read log)"

            reason = "Processing timed out after 5 minutes."
            elements = [
                P("Processing failed.", cls="text-red-400 text-sm font-medium"),
                P(reason, cls="text-slate-400 text-xs mt-1"),
                P(
                    "Your photo was saved. An admin can process it later from the staging area.",
                    cls="text-slate-400 text-xs mt-1",
                ),
            ]
            if log_excerpt:
                elements.append(
                    Div(
                        P("Log output:", cls="text-slate-500 text-xs mb-1"),
                        Pre(log_excerpt, cls="text-xs text-red-300 bg-slate-900 p-2 rounded overflow-x-auto max-h-32"),
                        cls="mt-2",
                    )
                )
            return Div(*elements, cls="p-3 bg-red-900/20 border border-red-500/30 rounded")

        # Show real progress from job state
        total = status.get("total_files")
        succeeded = status.get("files_succeeded", 0)
        failed = status.get("files_failed", 0)
        current_file = status.get("current_file")
        faces = status.get("faces_extracted", 0)

        # Build progress message driven by actual job state
        if total and total > 0:
            processed = succeeded + failed
            pct = int((processed / total) * 100)
            progress_text = f"Processing {processed}/{total} ({pct}%)"
            if current_file:
                progress_text = f"{progress_text}: {current_file}"
            progress_elements = [
                P(progress_text, cls="text-slate-300 text-sm"),
                # Real progress bar based on actual completion
                Div(
                    Div(cls="h-1 bg-blue-500 rounded", style=f"width: {pct}%"),
                    cls="w-full bg-slate-700 rounded h-1 mt-1",
                ),
            ]
            if faces > 0:
                progress_elements.append(
                    P(f"{_main_mod._pl(faces, 'face')} found so far", cls="text-slate-400 text-xs mt-1")
                )
        else:
            progress_elements = [
                P("Processing...", cls="text-slate-300 text-sm"),
                Span("\u23f3", cls="animate-pulse"),
            ]

        return Div(
            *progress_elements,
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded",
        )

    if status["status"] == "error":
        # Total failure
        error_msg = status.get("error", "Unknown error")
        errors = status.get("errors", [])

        elements = [P(f"Error: {error_msg}", cls="text-red-400 text-sm font-medium")]

        # Show per-file errors if available
        if errors:
            # UI BOUNDARY: sanitize filenames for safe rendering
            error_list = Ul(
                *[
                    Li(
                        f"{_main_mod.ensure_utf8_display(e['filename'])}: {_main_mod.ensure_utf8_display(e['error'])}",
                        cls="text-xs",
                    )
                    for e in errors[:5]
                ],
                cls="text-red-400 mt-1 ml-4 list-disc",
            )
            elements.append(error_list)
            if len(errors) > 5:
                elements.append(P(f"... and {len(errors) - 5} more errors", cls="text-red-500 text-xs"))

        return Div(*elements, cls="p-2 bg-red-900/30 border border-red-500/30 rounded")

    if status["status"] == "partial":
        # Some files succeeded, some failed
        faces = status.get("faces_extracted", 0)
        identities = len(status.get("identities_created", []))
        total = status.get("total_files", 0)
        succeeded = status.get("files_succeeded", 0)
        failed = status.get("files_failed", 0)
        errors = status.get("errors", [])

        elements = [
            P(
                f"\u2713 {_main_mod._pl(faces, 'face')} extracted from {succeeded}/{total} images",
                cls="text-amber-600 text-sm font-medium",
            ),
        ]

        # Show failure summary
        if failed > 0:
            elements.append(P(f"\u26a0 {failed} image(s) failed", cls="text-red-400 text-sm"))
            # Show first few errors
            if errors:
                # UI BOUNDARY: sanitize filenames for safe rendering
                error_summary = ", ".join(_main_mod.ensure_utf8_display(e["filename"]) for e in errors[:3])
                if len(errors) > 3:
                    error_summary += f", +{len(errors) - 3} more"
                elements.append(P(f"Failed: {error_summary}", cls="text-red-500 text-xs"))

        elements.append(
            A(
                "Refresh to see inbox",
                href="/?section=to_review&view=browse",
                cls="text-indigo-400 hover:underline text-xs mt-1 block",
            )
        )

        return Div(*elements, cls="p-2 bg-amber-900/30 border border-amber-500/30 rounded")

    # Success (all files processed successfully)
    # AD-165: R2 upload now happens in the background thread (not here).
    # The thread uploads to R2 BEFORE cleaning up the staging directory.
    faces = status.get("faces_extracted", 0)
    identities = len(status.get("identities_created", []))
    total = status.get("total_files")

    # Handle 0 faces: photo was processed but no faces detected.
    # This is NOT a success — show a clear warning so users don't think their photo was lost.
    if faces == 0:
        return Div(
            P(
                "\u26a0 No faces detected in your photo.",
                cls="text-amber-400 text-sm font-medium",
            ),
            P(
                "This can happen with extreme close-crops, very small faces, or non-portrait images. "
                "Try uploading a wider shot where faces are clearly visible.",
                cls="text-slate-400 text-xs mt-1",
            ),
            P(
                "The photo was not added to the archive.",
                cls="text-slate-500 text-xs mt-1",
            ),
            cls="p-3 bg-amber-900/20 border border-amber-500/30 rounded",
        )

    success_text = f"\u2713 {_main_mod._pl(faces, 'face')} extracted"
    if total and total > 1:
        success_text = f"\u2713 {_main_mod._pl(faces, 'face')} extracted from {_main_mod._pl(total, 'image')}"
    success_text += f", {identities} added to Inbox"

    return Div(
        P(success_text, cls="text-emerald-400 text-sm font-medium"),
        A(
            "Refresh to see inbox",
            href="/?section=to_review&view=browse",
            cls="text-indigo-400 hover:underline text-xs ml-2",
        ),
        cls="p-2 bg-emerald-900/30 border border-emerald-500/30 rounded flex items-center",
    )
