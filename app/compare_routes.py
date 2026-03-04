"""
Compare routes extracted from app/main.py.

All /compare/* and /api/compare/* routes plus compare-exclusive helpers.
Shared helpers (caches, social graph, evidence sections) remain in app.main.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
from fasthtml.common import *
from starlette.datastructures import UploadFile
from starlette.responses import RedirectResponse

from core.registry import IdentityState
from core.config import PROCESSING_ENABLED
from core.ui_safety import ensure_utf8_display
from core import storage

# Import route decorator only (bound once, never reassigned)
from app.main import rt
from app.utils import _section_for_state

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)


@rt("/compare")
def get(face_id: str = "", photo_id: str = "", person_id: str = "", sess=None):
    """
    Universal Comparison Workspace (PRD-026).

    Two-slot design: Source (left) + Targets (right) → Results (below).
    Supports all entity combinations: Person, Photo, Upload.

    Query params for backward compat:
        face_id: pre-select person as source (find identity for face)
        photo_id: pre-select photo as source
        person_id: pre-select person as target
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    nav_links = _main_mod._public_nav_links(active="compare", user=user)

    # Resolve backward-compat URL params
    pre_source_type = ""
    pre_source_id = ""
    pre_source_name = ""
    pre_source_crop = ""
    pre_target_id = ""
    pre_target_name = ""
    pre_target_crop = ""

    if face_id:
        # Find identity for this face → use as source person
        ident = _main_mod.get_identity_for_face(registry, face_id)
        if ident:
            pre_source_type = "person"
            pre_source_id = ident["identity_id"]
            pre_source_name = ensure_utf8_display(ident.get("name", "Unknown"))
            fids = ident.get("anchor_ids", [])
            if fids:
                first_fid = fids[0] if isinstance(fids[0], str) else fids[0].get("face_id", "")
                pre_source_crop = _resolve_crop_url(first_fid, crop_files)

    if photo_id:
        photo_meta = _main_mod.get_photo_metadata(photo_id)
        if photo_meta:
            pre_source_type = "photo"
            pre_source_id = photo_id
            pre_source_name = photo_meta.get("filename", photo_meta.get("path", "Photo"))
            fname = photo_meta.get("filename") or photo_meta.get("path", "")
            pre_source_crop = storage.get_photo_url(fname) if fname else ""

    if person_id:
        try:
            ident = registry.get_identity(person_id)
        except (KeyError, Exception):
            ident = None
        if ident:
            pre_target_id = person_id
            pre_target_name = ensure_utf8_display(ident.get("name", "Unknown"))
            fids = ident.get("anchor_ids", [])
            if fids:
                first_fid = fids[0] if isinstance(fids[0], str) else fids[0].get("face_id", "")
                pre_target_crop = _resolve_crop_url(first_fid, crop_files)

    # Auto-trigger comparison if both source and target are pre-populated
    auto_compare_attrs = {}
    if pre_source_type and pre_source_id and pre_target_id:
        auto_compare_attrs = {
            "hx_post": "/api/compare/execute",
            "hx_trigger": "load",
            "hx_target": "#compare-results-area",
            "hx_swap": "innerHTML",
            "hx_vals": json.dumps({
                "source_type": pre_source_type,
                "source_id": pre_source_id,
                "target_type": "person",
                "target_ids": pre_target_id,
            }),
        }

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator,
        .htmx-request.htmx-indicator { display: inline; }
        div.htmx-request.htmx-indicator,
        .htmx-request div.htmx-indicator { display: block; }

        /* Workspace animations */
        @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes barFill { from { width: 0; } }
        @keyframes pillPop { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }
        @keyframes photoAppear { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        @keyframes barColorIn { from { filter: saturate(0); } to { filter: saturate(1); } }

        .compare-section-animate { animation: slideIn 0.3s ease-out both; }
        .compare-bar-animate { animation: barFill 0.6s cubic-bezier(0.16, 1, 0.3, 1) both, barColorIn 0.8s ease-out both; }
        .compare-pill-animate { animation: pillPop 0.2s ease-out both; }
        .compare-fade-in { animation: fadeIn 0.3s ease-out both; }
        .compare-photo-appear { animation: photoAppear 0.4s ease-out both; }
        .compare-face-thumb { animation: slideUp 0.25s ease-out both; }
        .compare-pulse { animation: pulse 2s ease-in-out infinite; }

        /* Upload drag state */
        .upload-zone-drag { border-color: rgb(99 102 241) !important; background-color: rgba(99, 102, 241, 0.05); }

        /* Progress shimmer */
        @keyframes shimmer { 0% { background-position: -200px 0; } 100% { background-position: calc(200px + 100%) 0; } }
        .progress-shimmer {
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            background-size: 200px 100%;
            animation: shimmer 1.5s infinite;
        }

        /* Skeleton loading */
        .skeleton-block {
            background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 0.5rem;
        }

        /* Confidence bar inner glow */
        .bar-glow-emerald { box-shadow: inset 0 0 6px rgba(16, 185, 129, 0.3); }
        .bar-glow-amber { box-shadow: inset 0 0 6px rgba(245, 158, 11, 0.3); }
        .bar-glow-blue { box-shadow: inset 0 0 6px rgba(59, 130, 246, 0.3); }

        /* Card hover effects */
        .compare-card { transition: transform 0.2s ease, box-shadow 0.2s ease; }
        .compare-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

        /* Face section collapse */
        .face-section-content { transition: max-height 0.3s ease, opacity 0.2s ease; overflow: hidden; }
        .face-section-collapsed .face-section-content { max-height: 0 !important; opacity: 0; }
        .face-section-collapsed .face-collapse-icon { transform: rotate(-90deg); }
        .face-collapse-icon { transition: transform 0.2s ease; }

        /* Best match highlight */
        .best-match-glow { box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.3), 0 0 12px rgba(251, 191, 36, 0.08); }
    """)

    # Workspace JS — event delegation for all interactions
    # Pre-compute escaped JS strings (no backslashes in f-strings)
    js_source_name = pre_source_name.replace("'", "\\'")
    js_target_name = pre_target_name.replace("'", "\\'")
    js_target_push = ""
    if pre_target_id:
        js_target_push = (
            "state.targets.push({"
            f"type: 'person', id: '{pre_target_id}', "
            f"name: '{js_target_name}', crop: '{pre_target_crop}'"
            "});"
        )

    workspace_js = Script("""
    (function() {
        // State
        var state = {
            sourceType: '""" + pre_source_type + """',
            sourceId: '""" + pre_source_id + """',
            sourceName: '""" + js_source_name + """',
            targets: [],
            allArchive: false
        };

        // Expose state globally so upload completion can set source
        window.compareState = state;

        // Pre-populate target if URL param provided
        """ + js_target_push + """

        // Tab switching for source slot
        document.addEventListener('click', function(e) {
            var tab = e.target.closest('[data-source-tab]');
            if (tab) {
                var tabName = tab.getAttribute('data-source-tab');
                document.querySelectorAll('[data-source-tab]').forEach(function(t) {
                    t.classList.remove('bg-indigo-600', 'text-white');
                    t.classList.add('bg-slate-700', 'text-slate-300');
                });
                tab.classList.remove('bg-slate-700', 'text-slate-300');
                tab.classList.add('bg-indigo-600', 'text-white');

                document.querySelectorAll('[data-source-panel]').forEach(function(p) {
                    p.classList.add('hidden');
                });
                var panel = document.querySelector('[data-source-panel="' + tabName + '"]');
                if (panel) panel.classList.remove('hidden');
            }
        });

        // Tab switching for target slot
        document.addEventListener('click', function(e) {
            var tab = e.target.closest('[data-target-tab]');
            if (tab) {
                var tabName = tab.getAttribute('data-target-tab');
                document.querySelectorAll('[data-target-tab]').forEach(function(t) {
                    t.classList.remove('bg-indigo-600', 'text-white');
                    t.classList.add('bg-slate-700', 'text-slate-300');
                });
                tab.classList.remove('bg-slate-700', 'text-slate-300');
                tab.classList.add('bg-indigo-600', 'text-white');

                document.querySelectorAll('[data-target-panel]').forEach(function(p) {
                    p.classList.add('hidden');
                });
                var panel = document.querySelector('[data-target-panel="' + tabName + '"]');
                if (panel) panel.classList.remove('hidden');
            }
        });

        // Select source from search results
        document.addEventListener('click', function(e) {
            var el = e.target.closest('[data-action="select-compare-source"]');
            if (!el) return;
            e.preventDefault();
            state.sourceType = el.getAttribute('data-entity-type');
            state.sourceId = el.getAttribute('data-entity-id');
            state.sourceName = el.getAttribute('data-entity-name');
            updateSourceDisplay();
            triggerCompare();
        });

        // Select target from search results
        document.addEventListener('click', function(e) {
            var el = e.target.closest('[data-action="select-compare-target"]');
            if (!el) return;
            e.preventDefault();
            if (state.targets.length >= 5) return;
            var tid = el.getAttribute('data-entity-id');
            // Don't add duplicates
            for (var i = 0; i < state.targets.length; i++) {
                if (state.targets[i].id === tid) return;
            }
            state.allArchive = false;
            state.targets.push({
                type: el.getAttribute('data-entity-type'),
                id: tid,
                name: el.getAttribute('data-entity-name'),
                crop: el.getAttribute('data-entity-crop') || ''
            });
            updateTargetPills();
            triggerCompare();
            // Clear target search inputs and results
            var searchInput = document.getElementById('target-search-input');
            if (searchInput) { searchInput.value = ''; }
            ['target-person-results', 'target-photo-results'].forEach(function(rid) {
                var el = document.getElementById(rid);
                if (el) el.innerHTML = '';
            });
        });

        // Remove target pill
        document.addEventListener('click', function(e) {
            var el = e.target.closest('[data-action="remove-target"]');
            if (!el) return;
            var idx = parseInt(el.getAttribute('data-target-index'));
            state.targets.splice(idx, 1);
            updateTargetPills();
            if (state.targets.length > 0) triggerCompare();
            else {
                var area = document.getElementById('compare-results-area');
                if (area) area.innerHTML = '<p class="text-slate-400 text-sm text-center py-8">Select targets to compare against.</p>';
            }
        });

        // All Archive button
        document.addEventListener('click', function(e) {
            var el = e.target.closest('[data-action="compare-all-archive"]');
            if (!el) return;
            state.allArchive = true;
            state.targets = [];
            updateTargetPills();
            triggerCompare();
        });

        function updateSourceDisplay() {
            var display = document.getElementById('source-selected-display');
            if (!display) return;
            if (state.sourceType && state.sourceId) {
                display.innerHTML = '<div class="flex items-center gap-3 p-3 bg-slate-800/50 rounded-lg border border-indigo-500/30">' +
                    '<span class="text-sm text-white font-medium">' + escapeHtml(state.sourceName) + '</span>' +
                    '<span class="text-xs bg-indigo-900/50 text-indigo-400 px-1.5 py-0.5 rounded">' + state.sourceType + '</span>' +
                    '</div>';
            }
        }

        function updateTargetPills() {
            var container = document.getElementById('target-pills');
            if (!container) return;

            if (state.allArchive) {
                container.innerHTML = '<div class="flex items-center gap-2 px-3 py-1.5 bg-indigo-600/20 border border-indigo-500/30 rounded-full compare-pill-animate">' +
                    '<span class="text-xs text-indigo-300 font-medium">All Archive</span>' +
                    '<button data-action="clear-all-archive" class="text-indigo-400 hover:text-white text-xs ml-1">&times;</button>' +
                    '</div>';
                return;
            }

            var html = '';
            for (var i = 0; i < state.targets.length; i++) {
                var t = state.targets[i];
                html += '<div class="flex items-center gap-1.5 px-2 py-1 bg-slate-700 rounded-full compare-pill-animate" style="animation-delay: ' + (i * 50) + 'ms">';
                if (t.crop) html += '<img src="' + t.crop + '" class="w-5 h-5 rounded-full object-cover" alt="' + escapeHtml(t.name) + '">';
                html += '<span class="text-xs text-white truncate max-w-[120px]">' + escapeHtml(t.name) + '</span>';
                html += '<button data-action="remove-target" data-target-index="' + i + '" class="text-slate-400 hover:text-white text-xs ml-0.5">&times;</button>';
                html += '</div>';
            }
            if (state.targets.length > 0) {
                html += '<span class="text-[10px] text-slate-500">' + state.targets.length + '/5</span>';
            }
            container.innerHTML = html;
        }

        // Clear all archive
        document.addEventListener('click', function(e) {
            if (e.target.closest('[data-action="clear-all-archive"]')) {
                state.allArchive = false;
                updateTargetPills();
                var area = document.getElementById('compare-results-area');
                if (area) area.innerHTML = '<p class="text-slate-400 text-sm text-center py-8">Select targets to compare against.</p>';
            }
        });

        // Toggle face section collapse
        document.addEventListener('click', function(e) {
            var el = e.target.closest('[data-action="toggle-face-section"]');
            if (!el) return;
            var idx = el.getAttribute('data-face-idx');
            var section = document.getElementById('compare-face-section-' + idx);
            if (section) section.classList.toggle('face-section-collapsed');
        });

        function triggerCompare() {
            if (!state.sourceType || !state.sourceId) return;
            if (!state.allArchive && state.targets.length === 0) return;

            var targetType = state.allArchive ? 'archive' : (state.targets[0] ? state.targets[0].type : 'person');
            var targetIds = state.targets.map(function(t) { return t.id; }).join(',');

            var area = document.getElementById('compare-results-area');
            if (!area) return;

            // Show skeleton loading UI
            area.innerHTML = '<div class="space-y-4">' +
                '<div class="p-4 bg-slate-800/50 rounded-lg border border-slate-700/30">' +
                  '<div class="flex items-center gap-3 mb-3"><div class="skeleton-block w-14 h-14 rounded-full"></div><div class="skeleton-block h-4 w-24"></div></div>' +
                  '<div class="space-y-2"><div class="flex items-center gap-3"><div class="skeleton-block w-10 h-10 rounded-full"></div><div class="flex-1"><div class="skeleton-block h-3 w-32 mb-2"></div><div class="skeleton-block h-2 w-full"></div></div></div></div>' +
                '</div>' +
                '<div class="p-4 bg-slate-800/50 rounded-lg border border-slate-700/30 opacity-60" style="animation-delay:100ms">' +
                  '<div class="flex items-center gap-3"><div class="skeleton-block w-10 h-10 rounded-full"></div><div class="flex-1"><div class="skeleton-block h-3 w-28 mb-2"></div><div class="skeleton-block h-2 w-3/4"></div></div></div>' +
                '</div>' +
                '<p class="text-slate-500 text-xs text-center">Computing comparisons...</p>' +
              '</div>';

            htmx.ajax('POST', '/api/compare/execute', {
                target: '#compare-results-area',
                swap: 'innerHTML',
                values: {
                    source_type: state.sourceType,
                    source_id: state.sourceId,
                    target_type: targetType,
                    target_ids: targetIds
                }
            });
        }

        function escapeHtml(s) {
            var div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }

        // Expose functions globally for upload completion callback
        window.triggerCompare = triggerCompare;
        window.updateSourceDisplay = updateSourceDisplay;
        window.updateTargetPills = updateTargetPills;

        // Initialize display if pre-populated
        if (state.sourceType) updateSourceDisplay();
        if (state.targets.length > 0) updateTargetPills();
    })();
    """)

    # Upload form for source slot
    upload_panel = Div(
        Form(
            Div(
                Div(
                    NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-500 mb-2 mx-auto" id="ws-upload-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>'),
                    P("Drop a photo here", cls="text-slate-400 text-sm"),
                    P("JPG, PNG up to 10 MB", cls="text-slate-600 text-xs mt-0.5"),
                    Input(type="file", name="photo", accept="image/jpeg,image/png",
                          cls="absolute inset-0 w-full h-full opacity-0 cursor-pointer",
                          data_testid="ws-upload-input",
                          onchange="var f=this.files[0];if(!f)return;if(!['image/jpeg','image/png'].includes(f.type)||f.size>10*1024*1024)return;this.closest('form').requestSubmit()"),
                    cls="relative border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-lg p-6 transition-colors cursor-pointer text-center",
                ),
            ),
            Input(type="hidden", name="ws", value="1"),
            action="/api/compare/upload",
            method="post",
            enctype="multipart/form-data",
            hx_encoding="multipart/form-data",
            hx_post="/api/compare/upload",
            hx_target="#ws-upload-result",
            hx_swap="innerHTML",
            hx_indicator="#ws-upload-spinner",
            data_testid="ws-upload-form",
        ),
        Div(
            Div(cls="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"),
            P("Processing...", cls="text-slate-400 text-xs mt-2"),
            id="ws-upload-spinner", cls="htmx-indicator text-center py-4",
        ),
        # Container for upload results (faces detected, state updates)
        Div(id="ws-upload-result", data_testid="ws-upload-result"),
        data_source_panel="upload",
        data_testid="source-upload-panel",
    )

    # Person search for source slot
    person_panel = Div(
        Input(
            type="text", name="q",
            placeholder="Search by name...",
            hx_get="/api/compare/search-unified?types=person&slot=source",
            hx_trigger="keyup changed delay:300ms",
            hx_target="#source-person-results",
            hx_include="this",
            cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
            data_testid="source-person-search",
        ),
        Div(id="source-person-results", cls="mt-2 max-h-48 overflow-y-auto",
            data_testid="source-person-results"),
        Div(id="source-selected-display", cls="mt-2"),
        data_source_panel="person",
        cls="hidden",
        data_testid="source-person-panel",
    )

    # Photo search/browse for source slot
    photo_panel = Div(
        Input(
            type="text", name="q",
            placeholder="Search photos by name or collection...",
            hx_get="/api/compare/search-unified?types=photo&slot=source",
            hx_trigger="keyup changed delay:300ms",
            hx_target="#source-photo-results",
            hx_include="this",
            cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
            data_testid="source-photo-search",
        ),
        Div(id="source-photo-results", cls="mt-2 max-h-48 overflow-y-auto"),
        data_source_panel="photo",
        cls="hidden",
        data_testid="source-photo-panel",
    )

    # Source slot
    source_slot = Div(
        H3("Source", cls="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wide"),
        # Tabs
        Div(
            Button("Upload", data_source_tab="upload",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-indigo-600 text-white transition-colors"),
            Button("Person", data_source_tab="person",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"),
            Button("Photo", data_source_tab="photo",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"),
            cls="flex gap-2 mb-4",
            data_testid="source-tabs",
        ),
        upload_panel,
        person_panel,
        photo_panel,
        cls="bg-slate-800/50 rounded-xl p-5 border border-slate-700/30",
        data_testid="source-slot",
    )

    # Target upload form (mirrors source upload form but targets target slot)
    target_upload_panel = Div(
        Form(
            Div(
                Div(
                    NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-500 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>'),
                    P("Drop a photo here", cls="text-slate-400 text-sm"),
                    P("JPG, PNG up to 10 MB", cls="text-slate-600 text-xs mt-0.5"),
                    Input(type="file", name="photo", accept="image/jpeg,image/png",
                          cls="absolute inset-0 w-full h-full opacity-0 cursor-pointer",
                          data_testid="ws-target-upload-input",
                          onchange="var f=this.files[0];if(!f)return;if(!['image/jpeg','image/png'].includes(f.type)||f.size>10*1024*1024)return;this.closest('form').requestSubmit()"),
                    cls="relative border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-lg p-6 transition-colors cursor-pointer text-center",
                ),
            ),
            Input(type="hidden", name="ws", value="1"),
            Input(type="hidden", name="target_ws", value="1"),
            action="/api/compare/upload",
            method="post",
            enctype="multipart/form-data",
            hx_encoding="multipart/form-data",
            hx_post="/api/compare/upload",
            hx_target="#ws-target-upload-result",
            hx_swap="innerHTML",
            hx_indicator="#ws-target-upload-spinner",
            data_testid="ws-target-upload-form",
        ),
        Div(
            Div(cls="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"),
            P("Processing...", cls="text-slate-400 text-xs mt-2"),
            id="ws-target-upload-spinner", cls="htmx-indicator text-center py-4",
        ),
        Div(id="ws-target-upload-result", data_testid="ws-target-upload-result"),
        data_target_panel="upload",
        data_testid="target-upload-panel",
    )

    # Person search for target slot
    target_person_panel = Div(
        Input(
            type="text", name="q",
            id="target-search-input",
            placeholder="Search by name...",
            hx_get="/api/compare/search-unified?types=person&slot=target",
            hx_trigger="keyup changed delay:300ms",
            hx_target="#target-person-results",
            hx_include="this",
            cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
            data_testid="target-search-input",
        ),
        Div(id="target-person-results", cls="mt-2 max-h-48 overflow-y-auto",
            data_testid="target-person-results"),
        data_target_panel="person",
        cls="hidden",
        data_testid="target-person-panel",
    )

    # Photo search for target slot
    target_photo_panel = Div(
        Input(
            type="text", name="q",
            placeholder="Search photos by name or collection...",
            hx_get="/api/compare/search-unified?types=photo&slot=target",
            hx_trigger="keyup changed delay:300ms",
            hx_target="#target-photo-results",
            hx_include="this",
            cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
            data_testid="target-photo-search",
        ),
        Div(id="target-photo-results", cls="mt-2 max-h-48 overflow-y-auto"),
        data_target_panel="photo",
        cls="hidden",
        data_testid="target-photo-panel",
    )

    # Target slot
    target_slot = Div(
        H3("Compare With", cls="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wide"),
        # Tabs (mirrors source slot)
        Div(
            Button("Upload", data_target_tab="upload",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-indigo-600 text-white transition-colors"),
            Button("Person", data_target_tab="person",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"),
            Button("Photo", data_target_tab="photo",
                   cls="px-3 py-1.5 text-xs rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"),
            cls="flex gap-2 mb-4",
            data_testid="target-tabs",
        ),
        target_upload_panel,
        target_person_panel,
        target_photo_panel,
        # Target pills
        Div(id="target-pills", cls="flex flex-wrap gap-2 mt-3", data_testid="target-pills"),
        # All Archive button
        Div(
            Div(cls="border-t border-slate-700/50 my-3"),
            Button(
                "Compare against all archive",
                data_action="compare-all-archive",
                cls="w-full px-3 py-2 bg-slate-700/50 text-slate-300 text-sm rounded-lg hover:bg-slate-600 transition-colors border border-slate-600/50",
                data_testid="compare-all-archive",
            ),
        ),
        cls="bg-slate-800/50 rounded-xl p-5 border border-slate-700/30",
        data_testid="target-slot",
    )

    compare_og = _main_mod.og_tags(
        "Compare Faces \u2014 Rhodesli Heritage Archive",
        "Find connections across the Rhodes Jewish heritage photo archive",
        canonical_url="/compare",
    )

    return (
        Title("Compare Faces \u2014 Rhodesli Heritage Archive"),
        *compare_og,
        page_style,
        NotStr(_main_mod._upload_progress_script()),
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="flex items-center gap-3 sm:gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            # Header
            Section(
                Div(
                    H1("Compare Faces", cls="text-3xl font-serif font-bold text-white mb-2"),
                    P("Find connections across the Rhodes Jewish heritage archive.",
                      cls="text-slate-400 text-sm"),
                    cls="max-w-6xl mx-auto px-6 pt-6 pb-4",
                ),
            ),
            # Workspace: Source + Target slots
            Section(
                Div(
                    Div(source_slot, cls="flex-1 min-w-[300px]"),
                    Div(target_slot, cls="flex-1 min-w-[300px]"),
                    cls="flex flex-col lg:flex-row gap-4",
                ),
                cls="max-w-6xl mx-auto px-6 pb-4",
                data_testid="workspace-slots",
            ),
            # Results area
            Section(
                Div(
                    Div(
                        P("Select a source and one or more targets to begin comparing.",
                          cls="text-slate-500 text-center py-8") if not (pre_source_type and pre_target_id) else
                        P("Loading comparison...", cls="text-slate-300 text-sm animate-pulse text-center py-8"),
                        id="compare-results-area",
                        data_testid="compare-results-area",
                        **auto_compare_attrs,
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-8",
                ),
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P("Preserving the memory of the Jewish community of Rhodes",
                      cls="text-[10px] text-slate-600 italic"),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
        workspace_js,
    )
def _compare_result_card(result: dict, crop_files: set, index: int) -> object | None:
    """Build a single compare result card."""
    fid = result["face_id"]
    dist = result["distance"]
    tier = result.get("tier", "WEAK")
    confidence_pct = result.get("confidence_pct", 50)
    name = ensure_utf8_display(result.get("identity_name", "Unknown"))
    state = result.get("state", "")
    identity_id = result.get("identity_id", "")

    crop_url = _main_mod.resolve_face_image_url(fid, crop_files)
    if not crop_url:
        return None

    photo_id = _main_mod.get_photo_id_for_face(fid)
    photo_link = f"/photo/{photo_id}" if photo_id else "#"

    # Tier-specific styling
    tier_styles = {
        "STRONG MATCH": {
            "border": "border-emerald-700/50 hover:border-emerald-500/50",
            "badge_cls": "text-emerald-400 bg-emerald-900/30 border-emerald-700/50",
            "ring": "ring-2 ring-emerald-500/30",
        },
        "POSSIBLE MATCH": {
            "border": "border-amber-700/50 hover:border-amber-500/50",
            "badge_cls": "text-amber-400 bg-amber-900/30 border-amber-700/50",
            "ring": "ring-1 ring-amber-500/20",
        },
        "SIMILAR": {
            "border": "border-blue-700/30 hover:border-blue-500/30",
            "badge_cls": "text-blue-400 bg-blue-900/30 border-blue-700/50",
            "ring": "",
        },
        "WEAK": {
            "border": "border-slate-700/30 hover:border-slate-600/30",
            "badge_cls": "text-slate-400 bg-slate-800/50 border-slate-700/50",
            "ring": "",
        },
    }
    style = tier_styles.get(tier, tier_styles["WEAK"])

    # State badge
    state_badge = None
    if state == "CONFIRMED":
        state_badge = Span("Identified", cls="text-[9px] px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-400 border border-emerald-700/30")

    # Person page link (for confirmed identities)
    person_link = None
    if state == "CONFIRMED" and identity_id:
        person_link = A(
            f"View {name.split()[0]}'s page",
            href=f"/person/{identity_id}",
            cls="text-[10px] text-indigo-400 hover:text-indigo-300 block text-center mt-1",
        )

    # Timeline link (for confirmed identities with metadata)
    timeline_link = None
    if state == "CONFIRMED" and identity_id:
        timeline_link = A(
            "Timeline",
            href=f"/timeline?person={identity_id}",
            cls="text-[10px] text-slate-400 hover:text-indigo-300 block text-center",
        )

    display_name = name if state == "CONFIRMED" else f"Face #{index + 1}"

    # Calibrated confidence label based on percentage (AD-091)
    if confidence_pct >= 85:
        conf_label = "Very likely same person"
    elif confidence_pct >= 70:
        conf_label = "Strong match"
    elif confidence_pct >= 50:
        conf_label = "Possible match"
    else:
        conf_label = "Unlikely match"

    return Div(
        A(
            Img(src=crop_url, cls=f"w-28 h-28 rounded-lg object-cover mx-auto {style['ring']}"),
            href=photo_link,
            cls="block",
        ),
        Div(
            P(display_name, cls="text-sm text-white font-medium mt-2 truncate text-center"),
            Div(
                Span(f"{confidence_pct}%", cls=f"text-[10px] sm:text-xs font-medium px-1.5 sm:px-2 py-0.5 rounded border {style['badge_cls']}"),
                state_badge,
                cls="flex flex-wrap items-center justify-center gap-1 sm:gap-2 mt-1",
            ),
            P(conf_label, cls="text-[10px] text-slate-500 text-center mt-0.5", data_testid="confidence-label"),
            A("View Photo", href=photo_link, cls="text-[10px] text-indigo-400 hover:text-indigo-300 block text-center mt-2") if photo_id else None,
            person_link,
            timeline_link,
            cls="px-2",
        ),
        cls=f"bg-slate-800/70 rounded-lg border {style['border']} p-4 transition-colors",
        data_testid="compare-result",
        data_tier=tier.lower().replace(" ", "-"),
    )
def _compare_results_grid(results: list, crop_files: set, result_id: str = "") -> object:
    """Build the tiered results grid for face comparison (AD-067/AD-068).
    If result_id is provided, includes a shareable permalink."""
    if not results:
        return Div(
            P("No similar faces found.", cls="text-slate-500 text-center py-8"),
            id="compare-results",
        )

    _main_mod._build_caches()

    # Group results by tier
    tier_order = ["STRONG MATCH", "POSSIBLE MATCH", "SIMILAR", "WEAK"]
    tiered: dict[str, list] = {t: [] for t in tier_order}
    for i, result in enumerate(results):
        tier = result.get("tier", "WEAK")
        card = _compare_result_card(result, crop_files, i)
        if card:
            tiered[tier].append(card)

    # Build sections
    sections = []

    # Calibrated tier labels (AD-091): labels match what the confidence
    # percentages actually mean. "Very likely" reserved for 85%+ only.
    tier_config = {
        "STRONG MATCH": {
            "title": "Strong Matches",
            "subtitle": "High confidence — likely the same person",
            "icon": "text-emerald-400",
            "border": "border-emerald-800/30",
            "testid": "tier-strong-match",
        },
        "POSSIBLE MATCH": {
            "title": "Possible Matches",
            "subtitle": "Moderate confidence — worth investigating",
            "icon": "text-amber-400",
            "border": "border-amber-800/20",
            "testid": "tier-possible-match",
        },
        "SIMILAR": {
            "title": "Similar Faces",
            "subtitle": "Some resemblance — may be related",
            "icon": "text-blue-400",
            "border": "border-blue-800/20",
            "testid": "tier-similar",
        },
        "WEAK": {
            "title": "Other Faces",
            "subtitle": "Low similarity",
            "icon": "text-slate-500",
            "border": "border-slate-800/20",
            "testid": "tier-weak",
        },
    }

    total_shown = 0
    for tier in tier_order:
        cards = tiered[tier]
        if not cards:
            continue
        total_shown += len(cards)
        cfg = tier_config[tier]
        sections.append(
            Div(
                Div(
                    H3(cfg["title"], cls=f"text-base font-serif {cfg['icon']}"),
                    Span(f"{len(cards)} result{'s' if len(cards) != 1 else ''} — {cfg['subtitle']}",
                         cls="text-[10px] sm:text-xs text-slate-500 mt-0.5 sm:mt-0 sm:ml-2 line-clamp-2 sm:line-clamp-none"),
                    cls="flex flex-col sm:flex-row items-start sm:items-baseline sm:gap-1 mb-3",
                ),
                Div(*cards, cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 sm:gap-4"),
                cls=f"mb-6 pb-4 border-b {cfg['border']}",
                data_testid=cfg["testid"],
            )
        )

    # Action CTAs below results
    share_url = f"/compare/result/{result_id}" if result_id else "/compare"
    cta_section = Div(
        _main_mod.share_button(url=share_url, style="button", label="Share Results",
                     title="Face Comparison Results", text="Check out these face comparison results from the Rhodes archive"),
        A("Try Another Photo",
          href="/compare",
          cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded-lg transition-colors inline-flex items-center"),
        cls="flex flex-wrap items-center justify-center gap-3 mt-6 pt-4 border-t border-slate-800",
        data_testid="compare-ctas",
    )

    return Div(
        H2(f"{total_shown} Match{'es' if total_shown != 1 else ''}", cls="text-lg font-serif text-white mb-4"),
        *sections,
        cta_section,
        id="compare-results",
        data_testid="compare-results",
    )


def _compare_summary_section(results_by_face: list, crop_files: set, user_is_admin: bool,
                              registry, rid: str = "") -> object | None:
    """Build a Best Matches summary section aggregating top matches across all faces.

    Collects matches where confidence >= 40%, sorts by confidence descending
    with CONFIRMED identities first. Shows source + matched crop side by side
    with large confidence badge, name, and share/admin action buttons.

    Returns None if no matches meet the threshold.
    """
    # Collect all matches across all faces where confidence >= 40%
    summary_matches = []
    for fr in results_by_face:
        source_crop = fr.get("crop_url", "")
        source_face_id = fr.get("face_id", "")
        for tr in fr.get("targets", []):
            pct = tr.get("confidence_pct", 0)
            if pct < 40:
                continue
            # Look up identity state
            state = ""
            if tr.get("target_type") == "person" and tr.get("target_id"):
                try:
                    ident = registry.get_identity(tr["target_id"])
                    state = ident.get("state", "") if ident else ""
                except (KeyError, Exception):
                    pass
            summary_matches.append({
                "source_crop": source_crop,
                "source_face_id": source_face_id,
                "target_name": tr.get("target_name", "Unknown"),
                "target_id": tr.get("target_id", ""),
                "target_type": tr.get("target_type", ""),
                "target_crop_url": tr.get("target_crop_url", ""),
                "matched_face_id": tr.get("matched_face_id", ""),
                "confidence_pct": pct,
                "tier": tr.get("tier", "WEAK"),
                "distance": tr.get("distance", 99),
                "state": state,
            })

    if not summary_matches:
        return None

    # Sort: CONFIRMED first, then by confidence descending
    def _sort_key(m):
        confirmed_priority = 0 if m["state"] == "CONFIRMED" else 1
        return (confirmed_priority, -m["confidence_pct"])
    summary_matches.sort(key=_sort_key)

    # Build summary cards
    cards = []
    for i, m in enumerate(summary_matches[:8]):  # Cap at 8 best matches
        pct = m["confidence_pct"]

        # Color and label based on tier
        if pct >= 85:
            badge_bg = "bg-emerald-600"
            badge_text = "text-white"
            border_cls = "border-emerald-700/50"
            conf_label = "Very likely same person"
        elif pct >= 70:
            badge_bg = "bg-amber-600"
            badge_text = "text-white"
            border_cls = "border-amber-700/50"
            conf_label = "Strong match"
        elif pct >= 50:
            badge_bg = "bg-blue-600"
            badge_text = "text-white"
            border_cls = "border-blue-700/50"
            conf_label = "Possible match"
        else:
            badge_bg = "bg-slate-600"
            badge_text = "text-slate-200"
            border_cls = "border-slate-700/50"
            conf_label = "Worth investigating"

        # State badge
        state_badge = None
        if m["state"] == "CONFIRMED":
            state_badge = Span("Identified",
                               cls="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-400 border border-emerald-700/30")

        # Target link
        target_link = "#"
        if m["target_type"] == "person" and m["target_id"]:
            target_link = f"/person/{m['target_id']}"
        elif m["target_type"] == "photo" and m["target_id"]:
            target_link = f"/photo/{m['target_id']}"

        display_name = ensure_utf8_display(m["target_name"])

        # Share button for this match
        share_btn = None
        if rid:
            share_btn = _main_mod.share_button(
                url=f"/compare/result/{rid}",
                style="icon",
                label="Share",
                title=f"Could this be {display_name}? {pct}% match",
                text=f"Check out this {pct}% face match in the Rhodes archive",
            )

        # Admin actions: Merge / Not Same
        admin_actions = []
        if user_is_admin and m["target_type"] == "person" and m["target_id"] and m["source_face_id"]:
            face_identity = _main_mod.get_identity_for_face(registry, m["source_face_id"])
            face_iid = face_identity.get("identity_id") if face_identity else None
            if face_iid and face_iid != m["target_id"]:
                _face_name = face_identity.get("name", "") if face_identity else ""
                _target_name = m.get("target_name", "")
                _merge_confirm = f"Merge {_face_name} into {_target_name}? All faces will be combined." if _target_name and not _target_name.startswith("Unidentified") else "Merge these identities? This can be undone."
                admin_actions.append(
                    Button("Merge",
                           hx_post=f"/api/identity/{m['target_id']}/merge/{face_iid}?source=compare",
                           hx_target=f"#summary-card-{i}",
                           hx_swap="outerHTML",
                           hx_confirm=_merge_confirm,
                           cls="px-2 py-1 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors",
                           data_testid=f"summary-merge-{i}"))
                admin_actions.append(
                    Button("Not Same",
                           hx_post=f"/api/identity/{m['target_id']}/not-same/{face_iid}?source=compare",
                           hx_target=f"#summary-card-{i}",
                           hx_swap="outerHTML",
                           cls="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
                           data_testid=f"summary-not-same-{i}"))

        card = Div(
            # Side-by-side face images
            Div(
                # Source face
                Div(
                    Img(src=m["source_crop"], cls="w-[150px] h-[150px] rounded-lg object-cover border border-slate-600",
                        alt="Source face") if m["source_crop"] else Div(cls="w-[150px] h-[150px] rounded-lg bg-slate-700"),
                    P("Source", cls="text-[10px] text-slate-500 text-center mt-1"),
                    cls="text-center",
                ),
                # Arrow / VS indicator
                Div(
                    Span(f"{pct}%", cls=f"text-2xl font-bold {badge_bg} {badge_text} px-3 py-1 rounded-lg"),
                    P(conf_label, cls="text-[11px] text-slate-400 text-center mt-1"),
                    cls="flex flex-col items-center justify-center px-3",
                ),
                # Matched face
                Div(
                    A(
                        Img(src=m["target_crop_url"], cls="w-[150px] h-[150px] rounded-lg object-cover border border-slate-600",
                            alt=display_name) if m["target_crop_url"] else Div(cls="w-[150px] h-[150px] rounded-lg bg-slate-700"),
                        href=target_link,
                    ),
                    P(A(display_name, href=target_link, cls="text-white hover:text-indigo-300 text-sm font-medium"),
                      cls="text-center mt-1"),
                    state_badge if state_badge else None,
                    cls="text-center",
                ),
                cls="flex items-center justify-center gap-2 sm:gap-4",
            ),
            # Actions row
            Div(
                share_btn if share_btn else None,
                *(admin_actions if admin_actions else []),
                cls="flex items-center justify-center gap-2 mt-3",
            ) if (share_btn or admin_actions) else None,
            cls=f"p-4 bg-slate-800/70 rounded-xl border {border_cls} compare-card compare-section-animate",
            id=f"summary-card-{i}",
            data_testid=f"summary-card-{i}",
            style=f"animation-delay: {i * 80}ms",
        )
        cards.append(card)

    return Div(
        H3("Best Matches", cls="text-lg font-serif text-white mb-1"),
        P(f"{len(summary_matches)} match{'es' if len(summary_matches) != 1 else ''} above 40% confidence",
          cls="text-xs text-slate-400 mb-4"),
        Div(*cards, cls="space-y-4"),
        cls="mb-6 pb-6 border-b border-slate-700/50",
        data_testid="compare-summary-section",
    )


@rt("/api/compare")
def get(face_id: str = "", limit: int = 20, sess=None):
    """API endpoint for face comparison — returns results HTML partial."""
    if not face_id:
        return Div(P("No face selected.", cls="text-slate-500 text-center py-4"))

    face_data = _main_mod.get_face_data()
    if face_id not in face_data:
        return Div(P("Face not found in archive.", cls="text-amber-500 text-center py-4"))

    from core.neighbors import find_similar_faces
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()
    results = find_similar_faces(
        face_data[face_id]["mu"], face_data, registry=registry,
        limit=limit, exclude_face_ids={face_id},
    )
    # Save shareable result
    ident = _main_mod.get_identity_for_face(registry, face_id)
    query_name = ensure_utf8_display(ident.get("name", "Unknown")) if ident else "Unknown"
    rid = _main_mod._generate_result_id()
    _main_mod._save_comparison_result({
        "result_id": rid,
        "created_at": datetime.now().isoformat(),
        "query_type": "archive",
        "query_face_id": face_id,
        "query_name": query_name,
        "matches": [{"face_id": r["face_id"], "identity_id": r.get("identity_id", ""),
                     "identity_name": r.get("identity_name", ""), "distance": r["distance"],
                     "confidence_pct": r.get("confidence_pct", 0), "tier": r.get("tier", "WEAK")}
                    for r in results[:10]],
        "responses": [],
    })
    return _compare_results_grid(results, crop_files, result_id=rid)
def _build_compare_results_view(face_ids: list, job_id: str, sess=None) -> object:
    """Build the interactive comparison results view after upload + ingest.

    Called when background ingest completes. Shows:
    - Uploaded photo with face bounding box overlays
    - Per-face top archive matches with scores
    - Person search box for targeted comparison
    - Links to person pages and photo pages
    """
    from core.neighbors import find_similar_faces

    _main_mod._build_caches()
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True
    user_role = "admin" if user_is_admin else "viewer"

    # Look up photo_id from face_ids
    photo_id = None
    photo_url = None
    photo_data = None
    for fid in face_ids:
        pid = _main_mod.get_photo_id_for_face(fid)
        if pid:
            photo_id = pid
            break

    if photo_id:
        photo_data = _main_mod.get_photo_metadata(photo_id)
        if photo_data and photo_data.get("filename"):
            photo_url = storage.get_photo_url(photo_data["filename"])

    # Build per-face results
    per_face_results = []
    for fid in face_ids:
        emb = face_data.get(fid)
        if not emb or "mu" not in emb:
            continue
        matches = find_similar_faces(
            emb["mu"], face_data, registry=registry,
            limit=5, exclude_face_ids=set(face_ids),
        )
        # Get identity info for this face
        face_ident = _main_mod.get_identity_for_face(registry, fid)
        identity_id = face_ident.get("identity_id") if face_ident else None
        identity_name = face_ident.get("name", "Unknown") if face_ident else None
        per_face_results.append({
            "face_id": fid,
            "identity_id": identity_id,
            "identity_name": identity_name or "Unknown",
            "matches": matches,
        })

    parts = []

    # Header
    face_count = len(per_face_results)
    parts.append(
        Div(
            H2(f"{face_count} face{'s' if face_count != 1 else ''} detected",
               cls="text-xl font-serif text-white mb-1"),
            P("Photo saved to archive. Select a face to see matches, or search for a specific person.",
              cls="text-sm text-slate-400"),
            cls="mb-6",
        )
    )

    # Uploaded photo with face overlay data
    if photo_url and photo_data:
        photo_w = photo_data.get("width", 0)
        photo_h = photo_data.get("height", 0)
        photo_link = f"/photo/{photo_id}" if photo_id else "#"
        parts.append(
            Div(
                A(
                    Img(src=photo_url, cls="max-h-64 rounded-lg object-contain mx-auto",
                        alt="Uploaded photo", data_testid="compare-uploaded-photo"),
                    href=photo_link,
                    cls="block",
                ),
                P(A("View photo page", href=photo_link,
                    cls="text-indigo-400 hover:text-indigo-300 text-xs"),
                  cls="text-center mt-2"),
                cls="mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
                data_testid="upload-preview",
            )
        )

    # Person search box for targeted comparison
    parts.append(
        Div(
            P("Compare against a specific person", cls="text-sm text-slate-300 mb-2 font-medium"),
            Input(
                type="text", name="q",
                placeholder="Search by name (e.g., Isaac Cohen)...",
                hx_get=f"/api/compare/search-person?job_id={job_id}",
                hx_trigger="keyup changed delay:300ms",
                hx_target="#compare-person-search-results",
                hx_include="this",
                cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg "
                    "text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                data_testid="compare-person-search",
            ),
            Div(id="compare-person-search-results", cls="mt-2"),
            cls="mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
        )
    )

    # Per-face results
    for i, face_result in enumerate(per_face_results):
        fid = face_result["face_id"]
        iid = face_result["identity_id"]
        iname = face_result["identity_name"]
        matches = face_result["matches"]

        # Face crop
        crop_url = _resolve_crop_url(fid, crop_files)
        person_link = f"/person/{iid}" if iid else "#"

        match_cards = []
        for m in matches[:5]:
            m_crop_url = _resolve_crop_url(m.get("face_id", ""), crop_files)
            m_iid = m.get("identity_id", "")
            m_name = m.get("identity_name", "Unknown")
            m_pct = m.get("confidence_pct", 0)
            m_dist = m.get("distance", 99)
            m_tier = m.get("tier", "WEAK")

            # Color based on tier
            if m_pct >= 85:
                bar_color = "bg-emerald-500"
                label_color = "text-emerald-400"
            elif m_pct >= 70:
                bar_color = "bg-amber-500"
                label_color = "text-amber-400"
            elif m_pct >= 50:
                bar_color = "bg-blue-500"
                label_color = "text-blue-400"
            else:
                bar_color = "bg-slate-600"
                label_color = "text-slate-400"

            tier_label = m_tier.replace("_", " ").title()
            dist_str = f" (dist: {m_dist:.2f})" if user_is_admin else ""

            match_cards.append(
                Div(
                    Div(
                        Img(src=m_crop_url, cls="w-16 h-16 rounded-lg object-cover border border-slate-600",
                            alt=m_name) if m_crop_url else Div(cls="w-16 h-16 rounded-lg bg-slate-700"),
                        Div(
                            A(m_name, href=f"/person/{m_iid}" if m_iid else "#",
                              cls="text-sm text-white hover:text-indigo-300 font-medium"),
                            Div(
                                Div(
                                    Div(cls=f"h-1.5 rounded-full {bar_color}", style=f"width: {m_pct}%"),
                                    cls="flex-1 bg-slate-700 rounded-full h-1.5",
                                ),
                                Span(f"{m_pct}%", cls=f"text-xs {label_color} ml-2 font-mono min-w-[3rem] text-right"),
                                cls="flex items-center gap-2 mt-1",
                            ),
                            Span(f"{tier_label}{dist_str}", cls=f"text-xs {label_color}"),
                            cls="flex-1 min-w-0",
                        ),
                        cls="flex items-center gap-3",
                    ),
                    cls="p-3 bg-slate-800/50 rounded-lg border border-slate-700/30",
                )
            )

        # Face section
        parts.append(
            Div(
                Div(
                    Div(
                        Img(src=crop_url, cls="w-20 h-20 rounded-lg object-cover border-2 border-slate-500",
                            alt=iname) if crop_url else Div(cls="w-20 h-20 rounded-lg bg-slate-700"),
                        cls="flex-shrink-0",
                    ),
                    Div(
                        A(iname, href=person_link,
                          cls="text-white font-medium hover:text-indigo-300"),
                        P(f"Face {i + 1} — Top archive matches",
                          cls="text-xs text-slate-400 mt-0.5"),
                        cls="min-w-0",
                    ),
                    cls="flex items-center gap-3 mb-3",
                ),
                Div(*match_cards, cls="space-y-2") if match_cards else P("No matches found", cls="text-slate-500 text-sm"),
                cls="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50 mb-4",
                data_testid=f"face-result-{i}",
            )
        )

    # Save comparison result for sharing
    result_data = {
        "query_type": "compare_upload",
        "query_name": f"Compare Upload ({face_count} faces)",
        "photo_id": photo_id,
        "face_ids": face_ids,
        "job_id": job_id,
        "matches": [],
    }
    for fr in per_face_results:
        for m in fr["matches"][:3]:
            result_data["matches"].append({
                "face_id": m.get("face_id", ""),
                "identity_id": m.get("identity_id", ""),
                "identity_name": m.get("identity_name", "Unknown"),
                "distance": m.get("distance", 99),
                "confidence_pct": m.get("confidence_pct", 0),
                "tier": m.get("tier", "WEAK"),
            })
    result_id = _main_mod._save_comparison_result(result_data)

    # Share link
    share_url = f"{_main_mod.SITE_URL}/compare/result/{result_id}"
    parts.append(
        Div(
            A("Share this comparison", href=share_url, target="_blank",
              cls="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors inline-block"),
            cls="text-center mt-4",
            data_testid="compare-share-link",
        )
    )

    return Div(*parts, id="compare-results", data_testid="compare-results-complete")
def _resolve_crop_url(face_id: str, crop_files: set) -> str:
    """Resolve crop URL for a face_id, handling both legacy and inbox formats."""
    if not face_id:
        return ""
    # Try direct match
    fname = f"{face_id}.jpg"
    if fname in crop_files:
        return storage.get_crop_url_by_filename(fname)
    # Try identity-based crop
    return _main_mod.resolve_face_image_url(face_id, crop_files)
def _build_face_selector_for_upload(upload_id: str, faces: list, image_path: str) -> object:
    """Build a face selector UI for multi-face uploads."""
    face_buttons = []
    for i, face in enumerate(faces):
        bbox = face.get("bbox", [0, 0, 0, 0])
        if hasattr(bbox, 'tolist'):
            bbox = bbox.tolist()
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
        w = x2 - x1
        h = y2 - y1

        face_buttons.append(
            Button(
                f"Face {i + 1}",
                hx_post=f"/api/compare/upload/select?upload_id={upload_id}&face_idx={i}",
                hx_target="#compare-results",
                hx_swap="innerHTML",
                cls=f"px-3 py-1.5 text-sm rounded-lg border transition-colors "
                    f"{'bg-amber-600 border-amber-500 text-white' if i == 0 else 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}",
                data_testid=f"face-select-{i}",
            )
        )

    return Div(
        P(f"{len(faces)} face{'s' if len(faces) != 1 else ''} detected. Select which face to compare:",
          cls="text-sm text-slate-400 mb-3"),
        Div(*face_buttons, cls="flex flex-wrap gap-2 justify-center"),
        cls="text-center mb-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700/50",
        data_testid="face-selector-upload",
    )
@rt("/api/compare/upload")
async def post(photo: UploadFile = None, ws: str = "", target_ws: str = "", sess=None):
    """Upload a photo for face comparison via the unified upload pipeline.

    Uses the SAME staging + background ingest pipeline as the Upload page.
    Photos persist to the archive: photo_index, identities, embeddings, R2.
    Compare is a LENS on uploaded photos, not a separate storage system.

    Admin: immediate processing via background thread (AD-161).
    Non-admin: queued to pending_uploads for admin review (Lesson 19/22).
    ws=1: workspace mode — results go to #ws-upload-result instead of #compare-results.
    target_ws=1: target workspace mode — results go to #ws-target-upload-result.
    """
    import uuid
    from datetime import datetime, timezone

    # Workspace mode: determine correct result container
    if target_ws == "1":
        result_id = "ws-target-upload-result"
    elif ws == "1":
        result_id = "ws-upload-result"
    else:
        result_id = "compare-results"

    if not photo:
        return Div(P("No photo uploaded.", cls="text-amber-500 text-center py-4"),
                   id=result_id)

    from pathlib import Path as _Path

    # Read upload content
    content = await photo.read()
    original_filename = photo.filename or "upload.jpg"
    suffix = _Path(original_filename).suffix.lower() or ".jpg"

    # Server-side file type validation
    if suffix not in (".jpg", ".jpeg", ".png"):
        return Div(P("Please upload a JPG or PNG image.", cls="text-red-400 text-center py-4"),
                   id=result_id)

    # Server-side file size validation (10 MB)
    if len(content) > 10 * 1024 * 1024:
        return Div(P("File is too large (max 10 MB).", cls="text-red-400 text-center py-4"),
                   id=result_id)

    # Determine user and admin status (Lesson 19: admin-only for data modification)
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    # Generate job ID and stage file — SAME as Upload page
    job_id = str(uuid.uuid4())[:8]
    job_dir = _main_mod.data_path / "staging" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize and save file
    safe_filename = original_filename.replace(" ", "_").replace("/", "_")
    upload_path = job_dir / safe_filename
    with open(upload_path, "wb") as out:
        out.write(content)

    # Write metadata (same format as Upload page)
    import json as _json_compare
    uploader_email = user.email if user else "anonymous"
    metadata = {
        "job_id": job_id,
        "source": "Compare Upload",
        "collection": "",
        "source_url": "",
        "files": [safe_filename],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "processing_enabled": PROCESSING_ENABLED,
        "uploader_email": uploader_email,
        "compare_mode": True,
    }
    with open(job_dir / "_metadata.json", "w") as f:
        _json_compare.dump(metadata, f, indent=2)

    # Non-admin flow: queue for admin review (same as Upload page)
    if not user_is_admin:
        pending = _main_mod._load_pending_uploads()
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "uploader_email": uploader_email,
            "source": "Compare Upload",
            "collection": "",
            "source_url": "",
            "files": [safe_filename],
            "file_count": 1,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "compare_mode": True,
        }
        _main_mod._save_pending_uploads(pending)

        return Div(
            Div(
                Span("&#10003;", cls="text-3xl text-emerald-400"),
                cls="flex justify-center mb-3"
            ),
            P("Photo Submitted", cls="text-lg font-semibold text-white text-center"),
            P("Your photo has been submitted for review. An admin will process it shortly.",
              cls="text-sm text-slate-400 text-center mt-2 max-w-md mx-auto"),
            P(f"Reference: {job_id}", cls="text-xs text-slate-500 text-center mt-3 font-mono"),
            cls="py-8 px-4",
            id=result_id,
            data_testid="upload-saved-pending",
        )

    # Admin + processing disabled: stage for local pipeline
    if not PROCESSING_ENABLED:
        return Div(
            P("Photo staged for processing.", cls="text-slate-300 text-center py-4"),
            P("Run the local pipeline to detect faces.", cls="text-slate-400 text-center text-sm mt-2"),
            P(f"Reference: {job_id}", cls="text-xs text-slate-500 text-center mt-3 font-mono"),
            id=result_id,
        )

    # Admin + processing enabled: spawn background ingest thread (AD-161)
    # SAME pipeline as Upload page — uses shared hybrid models, no OOM.
    import threading
    inbox_dir = _main_mod.data_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    initial_status = {
        "status": "starting",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_files": 1,
        "files_succeeded": 0,
        "files_failed": 0,
    }
    with open(inbox_dir / f"{job_id}.status.json", "w") as _sf:
        _json_compare.dump(initial_status, _sf)

    def _background_compare_ingest():
        """Run face detection via unified pipeline, then run comparison.

        Uses same process_directory as Upload page (AD-161, AD-165).
        """
        import logging as _bg_logging
        log_path = inbox_dir / f"{job_id}.log"
        try:
            file_handler = _bg_logging.FileHandler(str(log_path))
            file_handler.setLevel(_bg_logging.INFO)
            _bg_logging.getLogger("core.ingest_inbox").addHandler(file_handler)

            from core.ingest_inbox import process_directory
            result = process_directory(
                directory=job_dir,
                job_id=job_id,
                data_dir=_main_mod.data_path,
                source="Compare Upload",
                collection="",
                prefer_hybrid=True,
            )

            # Upload to R2 (same as Upload page — AD-165)
            from core.storage import can_write_r2, upload_bytes_to_r2
            if can_write_r2() and result.get("status") in ("success", "partial"):
                try:
                    import mimetypes
                    r2_count = 0
                    for fpath in job_dir.iterdir():
                        if fpath.is_file() and fpath.suffix.lower() in (".jpg", ".jpeg", ".png"):
                            ct = mimetypes.guess_type(fpath.name)[0] or "image/jpeg"
                            upload_bytes_to_r2(f"raw_photos/{fpath.name}", fpath.read_bytes(), content_type=ct)
                            r2_count += 1
                    crops_dir = Path("app/static/crops")
                    if crops_dir.exists():
                        for fid in result.get("face_ids", []):
                            crop_path = crops_dir / f"{fid}.jpg"
                            if crop_path.exists():
                                upload_bytes_to_r2(f"crops/{crop_path.name}", crop_path.read_bytes(), content_type="image/jpeg")
                                r2_count += 1
                    # Update status with R2 info
                    status_path = inbox_dir / f"{job_id}.status.json"
                    if status_path.exists():
                        with open(status_path) as _rf:
                            status_data = _json_compare.load(_rf)
                        status_data["r2_uploaded"] = True
                        status_data["r2_count"] = r2_count
                        with open(status_path, "w") as _wf:
                            _json_compare.dump(status_data, _wf, indent=2)
                    print(f"[compare-upload] R2 upload complete: {r2_count} files for job {job_id}")
                except Exception as e:
                    print(f"[compare-upload] R2 upload error for job {job_id}: {e}")

            # Invalidate caches so web app sees new data
            import app.main as _main_mod
            _main_mod._photo_cache = None
            _main_mod._face_to_photo_cache = None
            _main_mod._photo_id_aliases = None
            _main_mod._face_data_cache = None
            _main_mod._photo_registry_cache = None
            print(f"[compare-upload] Caches invalidated for job {job_id}")

        except Exception as e:
            error_status = {
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "started_at": initial_status["started_at"],
                "total_files": 1,
                "files_succeeded": 0,
                "files_failed": 1,
            }
            try:
                with open(inbox_dir / f"{job_id}.status.json", "w") as _ef:
                    _json_compare.dump(error_status, _ef)
            except Exception:
                pass
            import traceback
            try:
                with open(log_path, "a") as _lf:
                    traceback.print_exc(file=_lf)
            except Exception:
                pass
        finally:
            import shutil as _shutil_cleanup
            try:
                if job_dir.exists():
                    _shutil_cleanup.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass

    thread = threading.Thread(target=_background_compare_ingest, daemon=True, name=f"compare-ingest-{job_id}")
    thread.start()

    # Return polling component — polls compare-specific status endpoint
    poll_params = []
    if ws == "1":
        poll_params.append("ws=1")
    if target_ws == "1":
        poll_params.append("target_ws=1")
    poll_suffix = "?" + "&".join(poll_params) if poll_params else ""
    return Div(
        Div(
            P("Processing photo...", cls="text-slate-300 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            cls="flex items-center gap-2",
        ),
        P("Detecting faces and comparing against the archive",
          cls="text-slate-400 text-xs mt-1"),
        hx_get=f"/api/compare/status/{job_id}{poll_suffix}",
        hx_trigger="every 2s",
        hx_swap="outerHTML",
        id=result_id,
        cls="p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg",
        data_testid="compare-processing",
    )
def _build_workspace_upload_complete(face_ids: list, job_id: str, target_mode: bool = False) -> object:
    """Build workspace panel content after upload + ingest completes.

    Shows detected face thumbnails and sets JS state.
    target_mode=True: adds photo as target instead of source.
    """
    _main_mod._build_caches()
    crop_files = _main_mod.get_crop_files()

    face_thumbs = []
    for i, fid in enumerate(face_ids):
        crop_url = _resolve_crop_url(fid, crop_files)
        face_thumbs.append(
            Div(
                Img(src=crop_url, cls="w-12 h-12 rounded-lg object-cover border border-slate-600",
                    alt=f"Face {i+1}") if crop_url else
                Div(f"F{i+1}", cls="w-12 h-12 rounded-lg bg-slate-700 flex items-center justify-center text-xs text-slate-400"),
                Span(f"Face {i+1}", cls="text-[10px] text-slate-500 mt-0.5 block text-center"),
                cls="compare-face-thumb",
                style=f"animation-delay: {i * 50}ms",
            )
        )

    face_count = len(face_ids)

    if target_mode:
        # Add uploaded photo as a target
        js_script = Script(f"""
            if (window.compareState && window.compareState.targets.length < 5) {{
                window.compareState.allArchive = false;
                window.compareState.targets.push({{
                    type: 'upload',
                    id: '{job_id}',
                    name: 'Uploaded Photo',
                    crop: ''
                }});
                if (window.updateTargetPills) window.updateTargetPills();
                if (window.triggerCompare) window.triggerCompare();
            }}
        """)
        container_id = "ws-target-upload-result"
    else:
        # Set as source
        js_script = Script(f"""
            if (window.compareState) {{
                window.compareState.sourceType = 'upload';
                window.compareState.sourceId = '{job_id}';
                window.compareState.sourceName = 'Uploaded Photo';
                if (window.updateSourceDisplay) window.updateSourceDisplay();
                if (window.triggerCompare) window.triggerCompare();
            }}
        """)
        container_id = "ws-upload-result"

    return Div(
        Div(
            Span("&#10003;", cls="text-emerald-400 text-lg"),
            Span(f"{face_count} face{'s' if face_count != 1 else ''} detected",
                 cls="text-sm text-white font-medium"),
            cls="flex items-center gap-2 mb-3",
        ),
        Div(*face_thumbs, cls="flex flex-wrap gap-3 justify-center"),
        js_script,
        id=container_id,
        cls="p-3 bg-emerald-900/10 border border-emerald-500/20 rounded-lg",
        data_testid="ws-upload-complete",
    )
@rt("/api/compare/status/{job_id}")
def get(job_id: str, ws: str = "", target_ws: str = "", sess=None):
    """Poll compare upload status. On completion, show comparison results.

    Uses the same status file as Upload page (data/inbox/{job_id}.status.json).
    When ingest completes, reads face_ids, runs find_similar_faces per face,
    and returns the interactive comparison view.
    ws=1: workspace mode — results go to #ws-upload-result, sets JS source state on success.
    target_ws=1: target workspace mode — results go to #ws-target-upload-result, adds as target.
    """
    import json as _json_status
    from datetime import datetime as _dt_cstatus, timezone as _tz_cstatus

    if target_ws == "1":
        result_id = "ws-target-upload-result"
    elif ws == "1":
        result_id = "ws-upload-result"
    else:
        result_id = "compare-results"
    poll_params = []
    if ws == "1":
        poll_params.append("ws=1")
    if target_ws == "1":
        poll_params.append("target_ws=1")
    ws_suffix = "?" + "&".join(poll_params) if poll_params else ""

    status_path = _main_mod.data_path / "inbox" / f"{job_id}.status.json"

    if not status_path.exists():
        return Div(
            P("Starting...", cls="text-slate-300 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            hx_get=f"/api/compare/status/{job_id}{ws_suffix}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            id=result_id,
            cls="p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg flex items-center gap-2",
        )

    with open(status_path) as f:
        status = _json_status.load(f)

    # Handle error status
    if status.get("status") == "error":
        return Div(
            P("Error processing photo.", cls="text-red-400 text-sm font-medium"),
            P(status.get("error", "Unknown error"), cls="text-slate-400 text-xs mt-1"),
            id=result_id,
            cls="p-4 bg-red-900/20 border border-red-500/30 rounded-lg",
        )

    # Still processing — show progress
    if status.get("status") in ("starting", "processing"):
        # Check for timeout (2 min for starting, 5 min for processing)
        started_at = status.get("started_at", "")
        try:
            start_time = _dt_cstatus.fromisoformat(started_at)
            elapsed = (_dt_cstatus.now(_tz_cstatus.utc) - start_time).total_seconds()
        except (ValueError, TypeError):
            elapsed = 0

        timeout = 120 if status["status"] == "starting" else 300
        if elapsed > timeout:
            return Div(
                P("Processing timed out.", cls="text-red-400 text-sm font-medium"),
                P("Your photo was saved. An admin can process it later.",
                  cls="text-slate-400 text-xs mt-1"),
                id=result_id,
                cls="p-4 bg-red-900/20 border border-red-500/30 rounded-lg",
            )

        faces_so_far = status.get("faces_extracted", 0)
        progress_text = "Detecting faces..." if faces_so_far == 0 else f"{faces_so_far} face{'s' if faces_so_far != 1 else ''} found, comparing..."
        return Div(
            Div(
                P(progress_text, cls="text-slate-300 text-sm"),
                Span("\u23f3", cls="animate-pulse"),
                cls="flex items-center gap-2",
            ),
            hx_get=f"/api/compare/status/{job_id}{ws_suffix}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            id=result_id,
            cls="p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg",
        )

    # SUCCESS — ingest complete, build comparison results
    face_ids = status.get("face_ids", [])
    if not face_ids:
        return Div(
            P("No faces detected in the uploaded photo.", cls="text-amber-500 text-center py-4"),
            P("Try uploading a clearer photo with visible faces.",
              cls="text-slate-500 text-center text-sm mt-2"),
            id=result_id,
        )

    # Workspace mode: show face thumbnails + set JS state
    if target_ws == "1":
        return _build_workspace_upload_complete(face_ids, job_id, target_mode=True)
    if ws == "1":
        return _build_workspace_upload_complete(face_ids, job_id)

    return _build_compare_results_view(face_ids, job_id, sess)
@rt("/api/compare/search-person")
def get(q: str = "", job_id: str = "", sess=None):
    """Search for a person to compare against. Returns clickable results."""
    if len(q.strip()) < 2:
        return Div(id="compare-person-search-results")

    registry = _main_mod.load_registry()
    results = registry.search_identities(q.strip(), limit=8)
    crop_files = _main_mod.get_crop_files()

    if not results:
        return Div(
            P("No matching people found.", cls="text-slate-500 text-sm"),
            id="compare-person-search-results",
        )

    cards = []
    for r in results:
        iid = r["identity_id"]
        name = r["name"]
        state = r.get("state", "INBOX")
        preview_fid = r.get("preview_face_id", "")
        crop_url = _resolve_crop_url(preview_fid, crop_files)

        state_badge = ""
        if state == "CONFIRMED":
            state_badge = Span("Confirmed", cls="text-xs bg-emerald-900/50 text-emerald-400 px-1.5 py-0.5 rounded ml-2")
        elif state == "PROPOSED":
            state_badge = Span("Proposed", cls="text-xs bg-amber-900/50 text-amber-400 px-1.5 py-0.5 rounded ml-2")

        cards.append(
            Button(
                Div(
                    Img(src=crop_url, cls="w-10 h-10 rounded-full object-cover border border-slate-600",
                        alt=name) if crop_url else Div(cls="w-10 h-10 rounded-full bg-slate-700"),
                    Div(
                        Span(name, cls="text-sm text-white font-medium"),
                        state_badge if state_badge else None,
                        cls="flex items-center",
                    ),
                    cls="flex items-center gap-3",
                ),
                hx_post=f"/api/compare/vs-person?job_id={job_id}&identity_id={iid}",
                hx_target="#compare-results",
                hx_swap="innerHTML",
                cls="w-full text-left p-2 hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer",
                data_testid=f"compare-person-{iid}",
            )
        )

    return Div(*cards, id="compare-person-search-results",
               cls="space-y-1 max-h-64 overflow-y-auto")
@rt("/api/compare/vs-person")
def post(job_id: str = "", identity_id: str = "", sess=None):
    """Compare all faces from a compare upload against a specific person.

    Returns per-face match scores with context about the person's existing
    top archive matches. Supports merge/reject actions.
    """
    import json as _json_vs

    if not job_id or not identity_id:
        return Div(P("Missing parameters.", cls="text-red-400 text-sm"), id="compare-results")

    # Load the status to get face_ids
    status_path = _main_mod.data_path / "inbox" / f"{job_id}.status.json"
    if not status_path.exists():
        return Div(P("Upload not found.", cls="text-red-400 text-sm"), id="compare-results")

    with open(status_path) as f:
        status = _json_vs.load(f)

    face_ids = status.get("face_ids", [])
    if not face_ids:
        return Div(P("No faces found for this upload.", cls="text-amber-500 text-sm"), id="compare-results")

    _main_mod._build_caches()
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    # Get reference person info
    ref_identity = registry.get_identity(identity_id)
    if not ref_identity:
        return Div(P("Person not found.", cls="text-red-400 text-sm"), id="compare-results")

    ref_name = ref_identity.get("name", "Unknown")
    ref_anchor_ids = ref_identity.get("anchor_ids", [])
    ref_candidate_ids = ref_identity.get("candidate_ids", [])
    ref_all_face_ids = ref_anchor_ids + ref_candidate_ids

    # Get reference person's best crop
    ref_crop_url = ""
    if ref_anchor_ids:
        ref_crop_url = _resolve_crop_url(ref_anchor_ids[0], crop_files)
    elif ref_candidate_ids:
        ref_crop_url = _resolve_crop_url(ref_candidate_ids[0], crop_files)

    # Get reference person's embedding (best anchor)
    ref_embeddings = []
    for rfid in ref_all_face_ids:
        emb = face_data.get(rfid)
        if emb and "mu" in emb:
            ref_embeddings.append(emb["mu"])

    if not ref_embeddings:
        return Div(P(f"No embeddings found for {ref_name}.", cls="text-amber-500 text-sm"), id="compare-results")

    # Get reference person's existing top archive matches (Find Similar context)
    from core.neighbors import find_similar_faces, find_nearest_neighbors
    ref_neighbors = find_nearest_neighbors(
        identity_id, registry, _main_mod.load_photo_registry(), face_data, limit=3,
    )

    # Compute per-face distances against reference person
    import numpy as np
    per_face_scores = []
    for fid in face_ids:
        emb = face_data.get(fid)
        if not emb or "mu" not in emb:
            continue

        # Distance against each reference embedding, take the best (minimum)
        distances = []
        for ref_emb in ref_embeddings:
            dist = float(np.linalg.norm(emb["mu"] - ref_emb))
            distances.append(dist)
        best_dist = min(distances) if distances else 99.0

        # Unified confidence scoring (AD-200)
        from core.confidence import compute_face_confidence
        conf = compute_face_confidence(best_dist)
        confidence_pct = conf["confidence_pct"]
        tier = conf["tier"]

        # Get identity info for this face
        face_identity = _main_mod.get_identity_for_face(registry, fid)
        face_identity_id = face_identity.get("identity_id") if face_identity else None
        face_identity_name = face_identity.get("name", "Unknown") if face_identity else None

        per_face_scores.append({
            "face_id": fid,
            "identity_id": face_identity_id,
            "identity_name": face_identity_name or "Unknown",
            "distance": best_dist,
            "confidence_pct": confidence_pct,
            "tier": tier,
        })

    # Sort by confidence (best first)
    per_face_scores.sort(key=lambda x: x["distance"])

    # Look up photo info
    photo_id = None
    photo_url = None
    for fid in face_ids:
        pid = _main_mod.get_photo_id_for_face(fid)
        if pid:
            photo_id = pid
            break
    if photo_id:
        photo_meta = _main_mod.get_photo_metadata(photo_id)
        if photo_meta and photo_meta.get("filename"):
            photo_url = storage.get_photo_url(photo_meta["filename"])

    # Build the response
    parts = []

    # Header with reference person
    parts.append(
        Div(
            H2(f"Comparing against {ref_name}", cls="text-xl font-serif text-white mb-1"),
            P(f"{len(per_face_scores)} face{'s' if len(per_face_scores) != 1 else ''} scored",
              cls="text-sm text-slate-400"),
            cls="mb-4",
        )
    )

    # Side-by-side: uploaded photo + reference person
    ref_person_link = f"/person/{identity_id}"
    photo_link = f"/photo/{photo_id}" if photo_id else "#"
    parts.append(
        Div(
            # Uploaded photo
            Div(
                A(
                    Img(src=photo_url, cls="max-h-48 rounded-lg object-contain",
                        alt="Uploaded photo") if photo_url else Div("Photo", cls="w-32 h-32 bg-slate-700 rounded-lg flex items-center justify-center text-slate-500"),
                    href=photo_link,
                ),
                P(A("View photo", href=photo_link, cls="text-indigo-400 hover:text-indigo-300 text-xs"),
                  cls="text-center mt-1"),
                cls="flex-1 text-center",
            ),
            # Reference person
            Div(
                A(
                    Img(src=ref_crop_url, cls="w-24 h-24 rounded-full object-cover border-2 border-indigo-500 mx-auto",
                        alt=ref_name) if ref_crop_url else Div(cls="w-24 h-24 rounded-full bg-slate-700 mx-auto"),
                    href=ref_person_link,
                ),
                P(A(ref_name, href=ref_person_link,
                    cls="text-white font-medium hover:text-indigo-300 text-sm"),
                  cls="text-center mt-2"),
                P("Reference person", cls="text-xs text-slate-500 text-center"),
                cls="flex-1 text-center",
            ),
            cls="flex gap-4 items-center mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
            data_testid="compare-hero",
        )
    )

    # Per-face match scores with merge/reject actions
    for i, score in enumerate(per_face_scores):
        fid = score["face_id"]
        fiid = score["identity_id"]
        fname = score["identity_name"]
        dist = score["distance"]
        pct = score["confidence_pct"]
        tier = score["tier"]
        crop_url = _resolve_crop_url(fid, crop_files)

        # Color based on confidence
        if pct >= 85:
            bar_color = "bg-emerald-500"
            label_color = "text-emerald-400"
            border_color = "border-emerald-700/50"
        elif pct >= 70:
            bar_color = "bg-amber-500"
            label_color = "text-amber-400"
            border_color = "border-amber-700/50"
        elif pct >= 50:
            bar_color = "bg-blue-500"
            label_color = "text-blue-400"
            border_color = "border-blue-700/50"
        else:
            bar_color = "bg-slate-600"
            label_color = "text-slate-400"
            border_color = "border-slate-700/50"

        tier_label = tier.replace("_", " ").title()
        dist_str = f" (dist: {dist:.2f})" if user_is_admin else ""

        # Admin actions (merge/reject) — same as Find Similar
        action_buttons = []
        if user_is_admin and fiid:
            _merge_confirm = f"Merge {fname} into {ref_name}? All faces will be combined." if ref_name and not ref_name.startswith("Unidentified") else "Merge these identities? This can be undone."
            action_buttons.append(
                Button(
                    "Merge",
                    hx_post=f"/api/identity/{identity_id}/merge/{fiid}?source=compare",
                    hx_target=f"#compare-face-{i}",
                    hx_swap="outerHTML",
                    cls="px-2 py-1 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors",
                    data_testid=f"merge-{i}",
                    hx_confirm=_merge_confirm,
                )
            )
            action_buttons.append(
                Button(
                    "Not Same",
                    hx_post=f"/api/identity/{identity_id}/not-same/{fiid}?source=compare",
                    hx_target=f"#compare-face-{i}",
                    hx_swap="outerHTML",
                    cls="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
                    data_testid=f"not-same-{i}",
                )
            )

        person_link = f"/person/{fiid}" if fiid else "#"

        parts.append(
            Div(
                Div(
                    # Face crop
                    A(
                        Img(src=crop_url, cls="w-14 h-14 rounded-full object-cover border border-slate-600",
                            alt=fname) if crop_url else Div(cls="w-14 h-14 rounded-full bg-slate-700"),
                        href=person_link,
                    ),
                    # Score info
                    Div(
                        A(fname, href=person_link,
                          cls="text-sm text-white hover:text-indigo-300 font-medium"),
                        # Confidence bar
                        Div(
                            Div(
                                Div(cls=f"h-2 rounded-full {bar_color}", style=f"width: {pct}%"),
                                cls="flex-1 bg-slate-700 rounded-full h-2",
                            ),
                            Span(f"{pct}%", cls=f"text-sm {label_color} ml-3 font-mono min-w-[3rem] text-right font-semibold"),
                            cls="flex items-center gap-2 mt-1",
                        ),
                        Span(f"{tier_label}{dist_str}", cls=f"text-xs {label_color} mt-0.5"),
                        cls="flex-1 min-w-0",
                    ),
                    cls="flex items-center gap-3",
                ),
                # Admin actions
                Div(*action_buttons, cls="flex gap-2 mt-2 justify-end") if action_buttons else None,
                cls=f"p-4 bg-slate-800/50 rounded-lg border {border_color}",
                id=f"compare-face-{i}",
                data_testid=f"compare-face-score-{i}",
            )
        )

    # Context: reference person's existing top matches
    if ref_neighbors:
        context_parts = []
        for n in ref_neighbors[:3]:
            n_name = n.get("name", "Unknown")
            n_dist = n.get("distance", 99)
            context_parts.append(f"{n_name} (dist: {n_dist:.2f})")
        context_str = ", ".join(context_parts)

        best_uploaded_dist = per_face_scores[0]["distance"] if per_face_scores else 99
        best_uploaded_name = per_face_scores[0]["identity_name"] if per_face_scores else "Unknown"

        parts.append(
            Div(
                P(f"Context: {ref_name}'s closest existing archive matches:",
                  cls="text-sm text-slate-300 font-medium mb-1"),
                P(context_str, cls="text-xs text-slate-400 mb-2"),
                P(f"Your best match ({best_uploaded_name}) scores distance {best_uploaded_dist:.2f}.",
                  cls="text-xs text-slate-400"),
                cls="mt-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700/30",
                data_testid="compare-context",
            )
        )

    # Save vs-person result for sharing
    result_data = {
        "query_type": "upload_vs_person",
        "query_name": f"vs {ref_name}",
        "photo_id": photo_id,
        "face_ids": face_ids,
        "job_id": job_id,
        "reference_person": {
            "identity_id": identity_id,
            "name": ref_name,
        },
        "matches": [
            {
                "face_id": s["face_id"],
                "identity_id": s.get("identity_id", ""),
                "identity_name": s["identity_name"],
                "distance": s["distance"],
                "confidence_pct": s["confidence_pct"],
                "tier": s["tier"],
            }
            for s in per_face_scores
        ],
    }
    result_id = _main_mod._save_comparison_result(result_data)
    share_url = f"{_main_mod.SITE_URL}/compare/result/{result_id}"

    parts.append(
        Div(
            Div(
                A("Share this comparison", href=share_url, target="_blank",
                  cls="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors inline-block"),
                A("Find Similar for " + ref_name, href=f"/person/{identity_id}",
                  cls="px-4 py-2 bg-slate-700 text-slate-300 text-sm font-medium rounded-lg hover:bg-slate-600 transition-colors inline-block"),
                cls="flex gap-3 justify-center flex-wrap",
            ),
            # Search for another person
            Div(
                P("Compare against another person:", cls="text-sm text-slate-400 mt-4 mb-2"),
                Input(
                    type="text", name="q",
                    placeholder="Search by name...",
                    hx_get=f"/api/compare/search-person?job_id={job_id}",
                    hx_trigger="keyup changed delay:300ms",
                    hx_target="#compare-person-search-results-2",
                    hx_include="this",
                    cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg "
                        "text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                ),
                Div(id="compare-person-search-results-2", cls="mt-2"),
            ),
            cls="mt-6",
            data_testid="compare-actions",
        )
    )

    return Div(*parts, id="compare-results", data_testid="compare-vs-person-results")
@rt("/api/compare/from-photo")
def get(photo_id: str = "", identity_id: str = "", sess=None):
    """Compare an existing archive photo's faces against a specific person.

    This enables the archive-to-compare flow: click "Compare" on a photo page,
    select a person, and see per-face match scores. No upload needed.

    Reuses the same vs-person scoring engine (L2 distance + calibration).
    Saves result for sharing via /compare/result/{id}.
    """
    import json as _json_fp
    import numpy as np

    if not photo_id:
        return Div(P("Missing photo_id.", cls="text-red-400 text-sm"), id="compare-results")

    _main_mod._build_caches()
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    # Get photo metadata and face IDs
    photo_meta = _main_mod.get_photo_metadata(photo_id)
    if not photo_meta:
        return Div(P("Photo not found.", cls="text-red-400 text-sm"), id="compare-results")

    # face_ids from photo_index (string list) or from cache (dict list with face_id key)
    face_ids = photo_meta.get("face_ids", [])
    if not face_ids:
        face_ids = [f["face_id"] for f in photo_meta.get("faces", []) if isinstance(f, dict) and f.get("face_id")]
    if not face_ids:
        return Div(P("No faces found in this photo.", cls="text-amber-500 text-sm"), id="compare-results")

    photo_url = storage.get_photo_url(photo_meta.get("filename") or photo_meta.get("path", "")) if (photo_meta.get("filename") or photo_meta.get("path")) else None

    # If no identity_id, show the photo's faces + person search
    if not identity_id:
        parts = []
        parts.append(
            Div(
                H2(f"{len(face_ids)} face{'s' if len(face_ids) != 1 else ''} in this photo",
                   cls="text-xl font-serif text-white mb-1"),
                P("Search for a person to compare against.",
                  cls="text-sm text-slate-400"),
                cls="mb-4",
            )
        )
        if photo_url:
            parts.append(
                Div(
                    A(Img(src=photo_url, cls="max-h-48 rounded-lg object-contain mx-auto",
                           alt="Archive photo"), href=f"/photo/{photo_id}"),
                    P(A("View photo page", href=f"/photo/{photo_id}",
                        cls="text-indigo-400 hover:text-indigo-300 text-xs"), cls="text-center mt-2"),
                    cls="mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
                )
            )
        # Face thumbnails
        face_thumbs = []
        for fid in face_ids:
            crop_url = _resolve_crop_url(fid, crop_files)
            if crop_url:
                face_thumbs.append(
                    Img(src=crop_url, cls="w-12 h-12 rounded-full object-cover border border-slate-600", alt="Face")
                )
        if face_thumbs:
            parts.append(Div(*face_thumbs, cls="flex gap-2 justify-center mb-4"))

        parts.append(
            Div(
                P("Compare against a specific person", cls="text-sm text-slate-300 mb-2 font-medium"),
                Input(
                    type="text", name="q",
                    placeholder="Search by name (e.g., Isaac Cohen)...",
                    hx_get=f"/api/compare/search-person-photo?photo_id={photo_id}",
                    hx_trigger="keyup changed delay:300ms",
                    hx_target="#compare-person-search-results",
                    hx_include="this",
                    cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg "
                        "text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                    data_testid="compare-person-search",
                ),
                Div(id="compare-person-search-results", cls="mt-2"),
                cls="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
            )
        )
        return Div(*parts, id="compare-results", data_testid="compare-from-photo-select")

    # --- Full comparison: photo_id + identity_id ---
    ref_identity = registry.get_identity(identity_id)
    if not ref_identity:
        return Div(P("Person not found.", cls="text-red-400 text-sm"), id="compare-results")

    ref_name = ref_identity.get("name", "Unknown")
    ref_anchor_ids = ref_identity.get("anchor_ids", [])
    ref_candidate_ids = ref_identity.get("candidate_ids", [])
    ref_all_face_ids = ref_anchor_ids + ref_candidate_ids

    ref_crop_url = ""
    if ref_anchor_ids:
        ref_crop_url = _resolve_crop_url(ref_anchor_ids[0], crop_files)
    elif ref_candidate_ids:
        ref_crop_url = _resolve_crop_url(ref_candidate_ids[0], crop_files)

    ref_embeddings = []
    for rfid in ref_all_face_ids:
        emb = face_data.get(rfid)
        if emb and "mu" in emb:
            ref_embeddings.append(emb["mu"])

    if not ref_embeddings:
        return Div(P(f"No embeddings found for {ref_name}.", cls="text-amber-500 text-sm"), id="compare-results")

    # Reference person's existing top archive matches
    from core.neighbors import find_nearest_neighbors
    photo_reg = _main_mod.load_photo_registry()
    ref_neighbors = find_nearest_neighbors(identity_id, registry, photo_reg, face_data, limit=3)

    # Per-face distances
    per_face_scores = []
    for fid in face_ids:
        emb = face_data.get(fid)
        if not emb or "mu" not in emb:
            continue
        distances = []
        for ref_emb in ref_embeddings:
            dist = float(np.linalg.norm(emb["mu"] - ref_emb))
            distances.append(dist)
        best_dist = min(distances) if distances else 99.0

        # Unified confidence scoring (AD-200)
        from core.confidence import compute_face_confidence
        conf = compute_face_confidence(best_dist)
        confidence_pct = conf["confidence_pct"]
        tier = conf["tier"]

        face_identity = _main_mod.get_identity_for_face(registry, fid)
        face_identity_id = face_identity.get("identity_id") if face_identity else None
        face_identity_name = face_identity.get("name", "Unknown") if face_identity else None

        per_face_scores.append({
            "face_id": fid,
            "identity_id": face_identity_id,
            "identity_name": face_identity_name or "Unknown",
            "distance": best_dist,
            "confidence_pct": confidence_pct,
            "tier": tier,
        })

    per_face_scores.sort(key=lambda x: x["distance"])

    # Build the response — reuse vs-person layout
    parts = []
    ref_person_link = f"/person/{identity_id}"
    photo_link = f"/photo/{photo_id}"

    parts.append(
        Div(
            H2(f"Comparing against {ref_name}", cls="text-xl font-serif text-white mb-1"),
            P(f"{len(per_face_scores)} face{'s' if len(per_face_scores) != 1 else ''} in photo scored",
              cls="text-sm text-slate-400"),
            cls="mb-4",
        )
    )

    parts.append(
        Div(
            Div(
                A(Img(src=photo_url, cls="max-h-48 rounded-lg object-contain",
                       alt="Archive photo") if photo_url else Div("Photo", cls="w-32 h-32 bg-slate-700 rounded-lg"),
                  href=photo_link),
                P(A("View photo", href=photo_link, cls="text-indigo-400 hover:text-indigo-300 text-xs"),
                  cls="text-center mt-1"),
                cls="flex-1 text-center",
            ),
            Div(
                A(Img(src=ref_crop_url, cls="w-24 h-24 rounded-full object-cover border-2 border-indigo-500 mx-auto",
                       alt=ref_name) if ref_crop_url else Div(cls="w-24 h-24 rounded-full bg-slate-700 mx-auto"),
                  href=ref_person_link),
                P(A(ref_name, href=ref_person_link, cls="text-white font-medium hover:text-indigo-300 text-sm"),
                  cls="text-center mt-2"),
                P("Reference person", cls="text-xs text-slate-500 text-center"),
                cls="flex-1 text-center",
            ),
            cls="flex gap-4 items-center mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50",
            data_testid="compare-hero",
        )
    )

    # Per-face scores
    for i, score in enumerate(per_face_scores):
        fid = score["face_id"]
        fiid = score["identity_id"]
        fname = score["identity_name"]
        dist = score["distance"]
        pct = score["confidence_pct"]
        tier = score["tier"]
        crop_url = _resolve_crop_url(fid, crop_files)

        if pct >= 85:
            bar_color, label_color, border_color = "bg-emerald-500", "text-emerald-400", "border-emerald-700/50"
        elif pct >= 70:
            bar_color, label_color, border_color = "bg-amber-500", "text-amber-400", "border-amber-700/50"
        elif pct >= 50:
            bar_color, label_color, border_color = "bg-blue-500", "text-blue-400", "border-blue-700/50"
        else:
            bar_color, label_color, border_color = "bg-slate-600", "text-slate-400", "border-slate-700/50"

        tier_label = tier.replace("_", " ").title()
        dist_str = f" (dist: {dist:.2f})" if user_is_admin else ""

        action_buttons = []
        if user_is_admin and fiid:
            _merge_confirm = f"Merge {fname} into {ref_name}? All faces will be combined." if ref_name and not ref_name.startswith("Unidentified") else "Merge these identities? This can be undone."
            action_buttons.append(
                Button("Merge",
                       hx_post=f"/api/identity/{identity_id}/merge/{fiid}?source=compare",
                       hx_target=f"#compare-face-{i}", hx_swap="outerHTML",
                       hx_confirm=_merge_confirm,
                       cls="px-2 py-1 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors",
                       data_testid=f"merge-{i}"))
            action_buttons.append(
                Button("Not Same",
                       hx_post=f"/api/identity/{identity_id}/not-same/{fiid}?source=compare",
                       hx_target=f"#compare-face-{i}", hx_swap="outerHTML",
                       cls="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
                       data_testid=f"not-same-{i}"))

        person_link_face = f"/person/{fiid}" if fiid else "#"
        parts.append(
            Div(
                Div(
                    A(Img(src=crop_url, cls="w-14 h-14 rounded-full object-cover border border-slate-600",
                           alt=fname) if crop_url else Div(cls="w-14 h-14 rounded-full bg-slate-700"),
                      href=person_link_face),
                    Div(
                        A(fname, href=person_link_face, cls="text-sm text-white hover:text-indigo-300 font-medium"),
                        Div(Div(Div(cls=f"h-2 rounded-full {bar_color}", style=f"width: {pct}%"),
                                cls="flex-1 bg-slate-700 rounded-full h-2"),
                            Span(f"{pct}%", cls=f"text-sm {label_color} ml-3 font-mono min-w-[3rem] text-right font-semibold"),
                            cls="flex items-center gap-2 mt-1"),
                        Span(f"{tier_label}{dist_str}", cls=f"text-xs {label_color} mt-0.5"),
                        cls="flex-1 min-w-0",
                    ),
                    cls="flex items-center gap-3",
                ),
                Div(*action_buttons, cls="flex gap-2 mt-2 justify-end") if action_buttons else None,
                cls=f"p-4 bg-slate-800/50 rounded-lg border {border_color}",
                id=f"compare-face-{i}",
                data_testid=f"compare-face-score-{i}",
            )
        )

    # Context
    if ref_neighbors:
        context_parts = []
        for n in ref_neighbors[:3]:
            n_name = n.get("name", "Unknown")
            n_dist = n.get("distance", 99)
            context_parts.append(f"{n_name} (dist: {n_dist:.2f})")
        context_str = ", ".join(context_parts)
        best_uploaded_dist = per_face_scores[0]["distance"] if per_face_scores else 99
        best_uploaded_name = per_face_scores[0]["identity_name"] if per_face_scores else "Unknown"
        parts.append(
            Div(
                P(f"Context: {ref_name}'s closest existing archive matches:",
                  cls="text-sm text-slate-300 font-medium mb-1"),
                P(context_str, cls="text-xs text-slate-400 mb-2"),
                P(f"Best match in this photo ({best_uploaded_name}) scores distance {best_uploaded_dist:.2f}.",
                  cls="text-xs text-slate-400"),
                cls="mt-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700/30",
                data_testid="compare-context",
            )
        )

    # Save result for sharing
    rid = _main_mod._generate_result_id()
    result_data = {
        "result_id": rid,
        "created_at": datetime.now().isoformat(),
        "query_type": "archive_vs_person",
        "query_name": f"Photo vs {ref_name}",
        "photo_id": photo_id,
        "face_ids": face_ids,
        "reference_person": {"identity_id": identity_id, "name": ref_name},
        "matches": [
            {"face_id": s["face_id"], "identity_id": s.get("identity_id", ""),
             "identity_name": s["identity_name"], "distance": s["distance"],
             "confidence_pct": s["confidence_pct"], "tier": s["tier"]}
            for s in per_face_scores
        ],
        "responses": [],
    }
    result_id = _main_mod._save_comparison_result(result_data)
    share_url = f"{_main_mod.SITE_URL}/compare/result/{result_id}"

    parts.append(
        Div(
            Div(
                A("Share this comparison", href=share_url, target="_blank",
                  cls="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors inline-block"),
                A(f"Find Similar for {ref_name}", href=f"/person/{identity_id}",
                  cls="px-4 py-2 bg-slate-700 text-slate-300 text-sm font-medium rounded-lg hover:bg-slate-600 transition-colors inline-block"),
                cls="flex gap-3 justify-center flex-wrap",
            ),
            Div(
                P("Compare against another person:", cls="text-sm text-slate-400 mt-4 mb-2"),
                Input(
                    type="text", name="q",
                    placeholder="Search by name...",
                    hx_get=f"/api/compare/search-person-photo?photo_id={photo_id}",
                    hx_trigger="keyup changed delay:300ms",
                    hx_target="#compare-person-search-results-2",
                    hx_include="this",
                    cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg "
                        "text-white text-sm placeholder-slate-500 focus:border-indigo-500 focus:outline-none",
                ),
                Div(id="compare-person-search-results-2", cls="mt-2"),
            ),
            cls="mt-6",
            data_testid="compare-actions",
        )
    )

    return Div(*parts, id="compare-results", data_testid="compare-from-photo-results")
@rt("/api/compare/search-person-photo")
def get(q: str = "", photo_id: str = "", sess=None):
    """Search for a person to compare an archive photo against. Returns clickable results."""
    if len(q.strip()) < 2:
        return Div(id="compare-person-search-results")

    registry = _main_mod.load_registry()
    results = registry.search_identities(q.strip(), limit=8)
    crop_files = _main_mod.get_crop_files()

    if not results:
        return Div(
            P("No matching people found.", cls="text-slate-500 text-sm"),
            id="compare-person-search-results",
        )

    cards = []
    for r in results:
        iid = r["identity_id"]
        name = r["name"]
        state = r.get("state", "INBOX")
        preview_fid = r.get("preview_face_id", "")
        crop_url = _resolve_crop_url(preview_fid, crop_files)

        state_badge = ""
        if state == "CONFIRMED":
            state_badge = Span("Confirmed", cls="text-xs bg-emerald-900/50 text-emerald-400 px-1.5 py-0.5 rounded ml-2")
        elif state == "PROPOSED":
            state_badge = Span("Proposed", cls="text-xs bg-amber-900/50 text-amber-400 px-1.5 py-0.5 rounded ml-2")

        cards.append(
            A(
                Div(
                    Img(src=crop_url, cls="w-10 h-10 rounded-full object-cover border border-slate-600",
                        alt=name) if crop_url else Div(cls="w-10 h-10 rounded-full bg-slate-700"),
                    Div(
                        Span(name, cls="text-sm text-white font-medium"),
                        state_badge if state_badge else None,
                        cls="flex items-center",
                    ),
                    cls="flex items-center gap-3",
                ),
                href=f"/compare?photo_id={photo_id}&person_id={iid}",
                cls="block w-full text-left p-2 hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer",
                data_testid=f"compare-person-{iid}",
            )
        )

    return Div(*cards, id="compare-person-search-results",
               cls="space-y-1 max-h-64 overflow-y-auto")
@rt("/api/compare/upload-multiple")
async def post(request, sess=None):
    """Upload 2-5 photos for cross-comparison and archive matching.

    Accepts multiple files via 'photos' form field. Detects faces in each,
    cross-compares between uploaded photos, and matches against archive.
    All photos saved for pipeline processing. (PRD-021, Session 61)
    """
    import time as _time
    t0 = _time.time()

    form = await request.form()
    photos = form.getlist("photos")

    if not photos or len(photos) < 2:
        return Div(P("Please upload at least 2 photos for cross-comparison.",
                     cls="text-amber-500 text-center py-4"),
                   P("For single photo comparison, use the form above.",
                     cls="text-slate-500 text-center text-sm mt-2"),
                   id="compare-results")

    if len(photos) > 5:
        return Div(P("Maximum 5 photos per batch.",
                     cls="text-red-400 text-center py-4"),
                   id="compare-results")

    from pathlib import Path as _Path
    import tempfile

    # Check ML availability
    has_insightface = False
    try:
        import cv2
        from insightface.app import FaceAnalysis  # noqa: F401
        from core.ingest_inbox import extract_faces_hybrid
        has_insightface = True
    except ImportError:
        pass

    if not has_insightface:
        # Save all photos to R2 for later processing
        from core.storage import can_write_r2
        if can_write_r2():
            upload_ids = []
            for photo_file in photos:
                content = await photo_file.read()
                filename = photo_file.filename or "upload.jpg"
                uid = _main_mod._save_compare_upload(content, filename, faces=[], results=[], status="awaiting_analysis")
                upload_ids.append(uid)
            return Div(
                P("Photos received!", cls="text-lg font-semibold text-white text-center"),
                P(f"{len(upload_ids)} photos saved for offline analysis by the archive team.",
                  cls="text-sm text-slate-400 text-center mt-2"),
                cls="py-8 px-4", id="compare-results",
            )
        return Div(P("Multi-photo uploads not available yet.",
                     cls="text-amber-500 text-center py-4"),
                   id="compare-results")

    # Process each photo
    photo_results = []
    all_faces = []  # (photo_idx, face_idx, embedding, bbox)
    tmp_files = []

    try:
        for pi, photo_file in enumerate(photos):
            content = await photo_file.read()
            filename = photo_file.filename or f"upload_{pi}.jpg"
            suffix = _Path(filename).suffix.lower() or ".jpg"

            if suffix not in (".jpg", ".jpeg", ".png"):
                photo_results.append({"idx": pi, "filename": filename, "error": "Invalid file type"})
                continue
            if len(content) > 10 * 1024 * 1024:
                photo_results.append({"idx": pi, "filename": filename, "error": "File too large (max 10 MB)"})
                continue

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = _Path(tmp.name)
                tmp_files.append(tmp_path)

            # Resize for ML
            img = cv2.imread(str(tmp_path))
            if img is not None:
                h, w = img.shape[:2]
                if max(h, w) > 640:
                    scale = 640 / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(str(tmp_path), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

            faces, _, _ = extract_faces_hybrid(tmp_path)

            # Save upload
            upload_id = _main_mod._save_compare_upload(content, filename, faces, [], status="uploaded")

            # Compare each face to archive
            results_for_photo = []
            if faces:
                face_data = _main_mod.get_face_data()
                _registry = _main_mod.load_registry()
                from core.neighbors import find_similar_faces
                results_for_photo = find_similar_faces(
                    faces[0]["mu"], face_data, registry=_registry, limit=10,
                )

            for fi, face in enumerate(faces):
                all_faces.append((pi, fi, face["mu"], face.get("bbox", [0, 0, 0, 0])))

            photo_results.append({
                "idx": pi,
                "filename": filename,
                "upload_id": upload_id,
                "face_count": len(faces),
                "archive_matches": results_for_photo,
                "suffix": suffix,
            })

        # Cross-compare faces between different photos
        import numpy as np
        cross_matches = []
        for i, (pi_a, fi_a, emb_a, _) in enumerate(all_faces):
            for j, (pi_b, fi_b, emb_b, _) in enumerate(all_faces):
                if j <= i:
                    continue
                if pi_a == pi_b:
                    continue  # Skip same-photo comparisons
                # Cosine similarity
                sim = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-8))
                if sim > 0.3:  # Only show meaningful matches
                    cross_matches.append({
                        "photo_a": pi_a, "face_a": fi_a,
                        "photo_b": pi_b, "face_b": fi_b,
                        "similarity": sim,
                        "filename_a": photo_results[pi_a]["filename"],
                        "filename_b": photo_results[pi_b]["filename"],
                    })
        cross_matches.sort(key=lambda x: x["similarity"], reverse=True)

        # Build response
        parts = []
        parts.append(
            Div(
                H3(f"Compared {len(photos)} Photos", cls="text-lg font-serif text-white mb-2"),
                P(f"Detected {sum(pr.get('face_count', 0) for pr in photo_results)} total faces",
                  cls="text-sm text-slate-400"),
                cls="text-center mb-6",
            )
        )

        # Cross-matches section
        if cross_matches:
            match_items = []
            for cm in cross_matches[:10]:
                conf_pct = int(cm["similarity"] * 100)
                tier = "Very likely" if conf_pct >= 85 else "Strong" if conf_pct >= 70 else "Possible" if conf_pct >= 50 else "Unlikely"
                match_items.append(
                    Div(
                        P(f"Photo {cm['photo_a']+1} ↔ Photo {cm['photo_b']+1}",
                          cls="text-sm font-medium text-white"),
                        P(f"{tier} match ({conf_pct}%)",
                          cls=f"text-xs {'text-green-400' if conf_pct >= 70 else 'text-amber-400' if conf_pct >= 50 else 'text-slate-400'}"),
                        cls="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50",
                    )
                )
            parts.append(
                Div(
                    H3("Cross-Matches Between Your Photos", cls="text-base font-semibold text-indigo-300 mb-3"),
                    Div(*match_items, cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                    cls="mb-8 p-4 bg-slate-800/30 rounded-lg border border-indigo-500/20",
                    data_testid="cross-matches",
                )
            )

        # Per-photo results
        crop_files = _main_mod.get_crop_files()
        for pr in photo_results:
            if "error" in pr:
                parts.append(
                    Div(P(f"Photo {pr['idx']+1}: {pr['error']}", cls="text-red-400 text-sm"),
                        cls="mb-4")
                )
                continue

            upload_url = storage.get_upload_url(f"uploads/compare/{pr['upload_id']}{pr.get('suffix', '.jpg')}")
            parts.append(
                Div(
                    H3(f"Photo {pr['idx']+1}: {pr['filename']}", cls="text-base font-medium text-white mb-2"),
                    Div(
                        Img(src=upload_url, cls="max-h-32 rounded-lg object-contain",
                            alt=f"Uploaded photo {pr['idx']+1}"),
                        P(f"{pr['face_count']} face{'s' if pr['face_count'] != 1 else ''} detected",
                          cls="text-xs text-slate-400 mt-1"),
                        cls="flex flex-col items-center mb-3",
                    ),
                    _compare_results_grid(pr.get("archive_matches", []), crop_files)
                        if pr.get("archive_matches") else
                        P("No archive matches found.", cls="text-sm text-slate-500"),
                    cls="mb-8 p-4 bg-slate-800/20 rounded-lg border border-slate-700/30",
                    data_testid=f"photo-result-{pr['idx']}",
                )
            )

        timing = _time.time() - t0
        print(f"[compare-multi] Processed {len(photos)} photos in {timing:.2f}s")
        return Div(*parts, id="compare-results")

    except Exception as e:
        print(f"[compare-multi] Error: {e}")
        return Div(P(f"Error processing photos: {str(e)}",
                     cls="text-red-500 text-center py-4"),
                   id="compare-results")
    finally:
        for tf in tmp_files:
            tf.unlink(missing_ok=True)
@rt("/api/compare/upload/select")
def post(upload_id: str = "", face_idx: int = 0, sess=None):
    """Select a specific face from a multi-face upload for comparison."""
    from pathlib import Path as _Path
    import pickle
    from core.storage import can_write_r2, download_bytes_from_r2

    # Try R2 first, then local filesystem
    faces_data = None
    if can_write_r2():
        faces_data = download_bytes_from_r2(f"uploads/compare/{upload_id}_faces.pkl")

    if faces_data is None:
        embeddings_path = _Path("uploads/compare") / f"{upload_id}_faces.pkl"
        if embeddings_path.exists():
            faces_data = embeddings_path.read_bytes()

    if faces_data is None:
        return Div(P("Upload not found. Please re-upload the photo.", cls="text-amber-500 text-center py-4"))

    face_save_data = pickle.loads(faces_data)
    if face_idx < 0 or face_idx >= len(face_save_data):
        return Div(P("Invalid face selection.", cls="text-amber-500 text-center py-4"))

    query_embedding = np.array(face_save_data[face_idx]["mu"], dtype=np.float32)
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    from core.neighbors import find_similar_faces
    results = find_similar_faces(
        query_embedding, face_data, registry=registry,
        limit=20,
    )

    parts = []

    # Face selector with updated active state
    if len(face_save_data) > 1:
        face_buttons = []
        for i in range(len(face_save_data)):
            is_active = i == face_idx
            face_buttons.append(
                Button(
                    f"Face {i + 1}",
                    hx_post=f"/api/compare/upload/select?upload_id={upload_id}&face_idx={i}",
                    hx_target="#compare-results",
                    hx_swap="innerHTML",
                    cls=f"px-3 py-1.5 text-sm rounded-lg border transition-colors "
                        f"{'bg-amber-600 border-amber-500 text-white' if is_active else 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}",
                    data_testid=f"face-select-{i}",
                )
            )
        parts.append(
            Div(
                P(f"Comparing Face {face_idx + 1} of {len(face_save_data)}:",
                  cls="text-sm text-slate-400 mb-3"),
                Div(*face_buttons, cls="flex flex-wrap gap-2 justify-center"),
                cls="text-center mb-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700/50",
                data_testid="face-selector-upload",
            )
        )

    parts.append(_compare_results_grid(results, crop_files))
    return Div(*parts, id="compare-results")
@rt("/api/compare/contribute")
def post(upload_id: str = "", sess=None):
    """Submit a compare upload to the admin moderation queue.

    Creates an entry in pending_uploads.json so the admin can approve/reject
    the photo for inclusion in the archive.
    """
    denied = _main_mod._check_login(sess)
    if denied:
        return denied
    user = _main_mod.get_current_user(sess or {})

    if not upload_id:
        return Div(P("Missing upload ID.", cls="text-amber-500 text-sm"), id="contribute-cta-container")

    # Read the upload metadata
    from pathlib import Path as _Path
    from core.storage import can_write_r2, download_bytes_from_r2

    meta = None
    if can_write_r2():
        meta_bytes = download_bytes_from_r2(f"uploads/compare/{upload_id}_meta.json")
        if meta_bytes:
            meta = json.loads(meta_bytes)

    if meta is None:
        meta_path = _Path("uploads/compare") / f"{upload_id}_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

    if meta is None:
        return Div(P("Upload not found.", cls="text-amber-500 text-sm"), id="contribute-cta-container")

    # Create pending upload entry
    pending = _main_mod._load_pending_uploads()
    job_id = f"compare_{upload_id}"
    if job_id not in pending["uploads"]:
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "status": "pending",
            "submitted_at": datetime.now().isoformat(),
            "submitted_by": user.email if user else "anonymous",
            "source": "compare_upload",
            "collection": "",
            "file_count": 1,
            "files": [meta.get("original_filename", f"{upload_id}.jpg")],
            "compare_upload_id": upload_id,
            "image_key": meta.get("image_key", f"uploads/compare/{upload_id}.jpg"),
            "faces_detected": meta.get("faces_detected", 0),
            "top_match": meta.get("top_match"),
        }
        _main_mod._save_pending_uploads(pending)

    return Div(
        Span("✓", cls="text-green-400 mr-2"),
        Span("Submitted for review!", cls="text-sm text-green-300"),
        P("An admin will review your photo for inclusion in the archive.", cls="text-xs text-slate-500 mt-1"),
        cls="text-center py-3",
        id="contribute-cta-container",
        data_testid="contribute-submitted",
    )
@rt("/compare/result/{result_id}")
def get(result_id: str, sess=None):
    """
    Shareable comparison result page — permalink for a specific comparison.
    No authentication required. Shows matches + response form.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None

    data = _main_mod._load_comparison_results()
    result = data.get("results", {}).get(result_id)
    if not result:
        return Title("Not Found"), Main(
            Div(
                H1("Comparison Not Found", cls="text-2xl font-serif text-white mb-4"),
                P("This comparison result may have expired or been removed after a server restart.",
                  cls="text-slate-400 mb-2"),
                P("Please upload your photo again to get fresh results.",
                  cls="text-slate-500 text-sm mb-6"),
                A("Upload a Photo to Compare \u2192", href="/compare",
                  cls="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors inline-block"),
                cls="max-w-4xl mx-auto px-6 py-20 text-center",
            ),
            cls="min-h-screen bg-slate-900",
        )

    _main_mod._build_caches()
    crop_files = _main_mod.get_crop_files()
    matches = result.get("matches", [])
    query_type = result.get("query_type", "archive")
    query_face_id = result.get("query_face_id", "")
    responses = result.get("responses", [])
    ref_person = result.get("reference_person")
    photo_id = result.get("photo_id")

    # Query face info
    query_face_url = None
    query_name = "Uploaded Photo"
    if query_face_id:
        query_face_url = _main_mod.resolve_face_image_url(query_face_id, crop_files)
    if result.get("query_name"):
        query_name = result["query_name"]

    # Photo URL for uploaded photo
    photo_url = None
    if photo_id:
        photo_meta = _main_mod.get_photo_metadata(photo_id)
        if photo_meta and photo_meta.get("filename"):
            photo_url = storage.get_photo_url(photo_meta["filename"])

    # Reference person info
    ref_name = ref_person.get("name", "Unknown") if ref_person else None
    ref_id = ref_person.get("identity_id", "") if ref_person else None
    ref_crop_url = None
    if ref_id:
        try:
            ref_identity = _main_mod.load_registry().get_identity(ref_id)
            if ref_identity:
                ref_face_ids = ref_identity.get("anchor_ids", []) + ref_identity.get("candidate_ids", [])
                if ref_face_ids:
                    ref_crop_url = _resolve_crop_url(ref_face_ids[0], crop_files)
        except KeyError:
            pass  # Reference person may have been deleted

    # Top match info for OG tags
    top_match = matches[0] if matches else {}
    top_confidence = top_match.get("confidence_pct", 0)
    top_name = ensure_utf8_display(top_match.get("identity_name", "Unknown"))
    top_identity_id = top_match.get("identity_id", "")

    # Positive/curious framing for OG tags: "Could this be [Name]? [N]% match"
    # Determine the best name to feature in the OG title
    og_person_name = None
    if top_name and top_name != "Unknown":
        og_person_name = top_name
    elif ref_name and ref_name != "Unknown":
        og_person_name = ref_name

    if og_person_name and matches:
        og_title = f"Could this be {og_person_name}? {top_confidence}% match in Rhodes Archive"
    else:
        og_title = "Face Comparison — Rhodes Jewish Heritage Archive"
    og_desc = f"Help identify people in the Rhodes Jewish heritage photo archive. {len(matches)} potential match{'es' if len(matches) != 1 else ''} found."
    og_image = ref_crop_url or query_face_url or ""
    result_og = _main_mod.og_tags(og_title, og_desc, og_image, f"/compare/result/{result_id}")

    nav_links = _main_mod._public_nav_links(active="compare", user=user)
    share_url = f"{_main_mod.SITE_URL}/compare/result/{result_id}"
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    # Build hero section — large side-by-side faces (200px each)
    hero_section = None
    # Determine the source and best match images for the hero
    hero_source_url = query_face_url or photo_url
    hero_match_url = None
    hero_match_name = None
    hero_match_link = "#"
    hero_match_pct = 0

    if matches:
        best = matches[0]
        hero_match_pct = best.get("confidence_pct", 0)
        hero_match_name = ensure_utf8_display(best.get("identity_name", "Unknown"))
        hero_match_id = best.get("identity_id", "")
        hero_match_fid = best.get("face_id", "")
        hero_match_url = _main_mod.resolve_face_image_url(hero_match_fid, crop_files)
        if not hero_match_url:
            hero_match_url = _resolve_crop_url(hero_match_fid, crop_files)
        if hero_match_id:
            hero_match_link = f"/person/{hero_match_id}"

    # For upload_vs_person, prefer reference person as match side
    if ref_crop_url and ref_name and query_type == "upload_vs_person":
        hero_match_url = ref_crop_url
        hero_match_name = ref_name
        hero_match_link = f"/person/{ref_id}" if ref_id else "#"

    if hero_source_url or hero_match_url:
        # Positive question framing
        if hero_match_name and hero_match_name != "Unknown":
            hero_question = f"Could this be {hero_match_name}?"
        else:
            hero_question = "Do you recognize this person?"

        # Confidence badge color
        if hero_match_pct >= 85:
            badge_cls = "bg-emerald-600 text-white"
        elif hero_match_pct >= 70:
            badge_cls = "bg-amber-600 text-white"
        elif hero_match_pct >= 50:
            badge_cls = "bg-blue-600 text-white"
        else:
            badge_cls = "bg-slate-600 text-slate-200"

        hero_parts = []
        if hero_source_url:
            hero_parts.append(
                Div(
                    Img(src=hero_source_url, cls="w-[200px] h-[200px] rounded-xl object-cover border-2 border-slate-600 mx-auto",
                        alt="Source face"),
                    P("Source", cls="text-xs text-slate-500 text-center mt-2"),
                    cls="text-center",
                    data_testid="result-hero-source",
                )
            )
        hero_parts.append(
            Div(
                Span(f"{hero_match_pct}%", cls=f"text-3xl font-bold {badge_cls} px-4 py-2 rounded-xl"),
                cls="flex items-center justify-center px-2 sm:px-4",
            )
        )
        if hero_match_url:
            hero_parts.append(
                Div(
                    A(
                        Img(src=hero_match_url, cls="w-[200px] h-[200px] rounded-xl object-cover border-2 border-slate-600 mx-auto",
                            alt=hero_match_name or "Match"),
                        href=hero_match_link,
                    ),
                    P(A(hero_match_name or "Unknown", href=hero_match_link,
                        cls="text-white hover:text-indigo-300 text-sm font-medium"),
                      cls="text-center mt-2"),
                    cls="text-center",
                    data_testid="result-hero-match",
                )
            )

        hero_section = Div(
            H2(hero_question, cls="text-xl font-serif text-white text-center mb-4",
               data_testid="result-hero-question"),
            Div(*hero_parts, cls="flex items-center justify-center gap-3 sm:gap-6"),
            cls="mb-8 p-6 bg-slate-800/40 rounded-2xl border border-slate-700/50",
            data_testid="result-hero",
        )

    # Source photo with face highlighted (if available, separate from hero crops)
    source_photo_section = None
    if photo_url and photo_id and query_face_id:
        source_photo_section = Div(
            P("From this photo:", cls="text-xs text-slate-500 mb-2"),
            A(
                Img(src=photo_url, cls="max-h-48 rounded-lg object-contain mx-auto",
                    alt="Source photo"),
                href=f"/photo/{photo_id}",
            ),
            P(A("View full photo", href=f"/photo/{photo_id}",
                cls="text-indigo-400 hover:text-indigo-300 text-xs"),
              cls="text-center mt-1"),
            cls="mb-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/30 text-center",
            data_testid="result-source-photo",
        )

    # Reference person context — show top archive neighbors for comparison
    ref_context_section = None
    if ref_id and matches:
        try:
            from core.neighbors import find_nearest_neighbors
            face_data = _main_mod.get_face_data()
            ref_neighbors = find_nearest_neighbors(
                ref_id, _main_mod.load_registry(), _main_mod.load_photo_registry(), face_data, limit=3,
            )
            if ref_neighbors:
                context_names = [ensure_utf8_display(n.get("name", "Unknown")) for n in ref_neighbors[:3]]
                context_str = ", ".join(context_names)

                ref_context_section = Div(
                    P(f"In the archive, {ref_name}'s closest matches are: {context_str}",
                      cls="text-sm text-slate-300"),
                    cls="mb-6 p-4 bg-slate-900/50 rounded-lg border border-slate-700/30",
                    data_testid="result-reference-context",
                )
        except Exception:
            pass  # Reference context is supplementary, don't break the page

    # Build match cards with positive framing + admin actions
    result_cards = []
    for i, match in enumerate(matches[:10]):
        fid = match.get("face_id", "")
        match_url = _main_mod.resolve_face_image_url(fid, crop_files)
        if not match_url:
            match_url = _resolve_crop_url(fid, crop_files)
        pct = match.get("confidence_pct", 0)
        name = ensure_utf8_display(match.get("identity_name", f"Face #{i+1}"))
        m_identity_id = match.get("identity_id", "")

        # Positive/curious framing instead of "Unlikely match"
        if pct >= 85:
            label = "Very likely the same person"
            color = "text-emerald-400"
            bar_color = "bg-emerald-500"
        elif pct >= 70:
            label = "Strong resemblance"
            color = "text-amber-400"
            bar_color = "bg-amber-500"
        elif pct >= 50:
            label = "Possible match -- worth a look"
            color = "text-blue-400"
            bar_color = "bg-blue-500"
        else:
            label = "Some similarity"
            color = "text-slate-400"
            bar_color = "bg-slate-600"

        person_link = A(name, href=f"/person/{m_identity_id}", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium") if m_identity_id else Span(name, cls="text-sm text-white font-medium")
        # Admin-only distance info
        dist = match.get("distance", 99)
        dist_str = f" (dist: {dist:.2f})" if user_is_admin and dist < 99 else ""

        # Admin merge/not-same actions (same pattern as vs-person endpoint)
        action_buttons = []
        if user_is_admin and m_identity_id and ref_id:
            _merge_confirm = f"Merge {name} into {ref_name}? All faces will be combined." if ref_name and ref_name != "Unknown" else "Merge these identities? This can be undone."
            action_buttons.append(
                Button(
                    "Merge",
                    hx_post=f"/api/identity/{ref_id}/merge/{m_identity_id}?source=compare",
                    hx_target=f"#result-face-{i}",
                    hx_swap="outerHTML",
                    hx_confirm=_merge_confirm,
                    cls="px-2 py-1 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors",
                    data_testid=f"result-merge-{i}",
                )
            )
            action_buttons.append(
                Button(
                    "Not Same",
                    hx_post=f"/api/identity/{ref_id}/not-same/{m_identity_id}?source=compare",
                    hx_target=f"#result-face-{i}",
                    hx_swap="outerHTML",
                    cls="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
                    data_testid=f"result-not-same-{i}",
                )
            )

        result_cards.append(Div(
            Div(
                Img(src=match_url, cls="w-16 h-16 rounded-lg object-cover border border-slate-600") if match_url else Div(cls="w-16 h-16 rounded-lg bg-slate-700"),
                Div(
                    person_link,
                    # Confidence bar
                    Div(
                        Div(
                            Div(cls=f"h-2 rounded-full {bar_color}", style=f"width: {pct}%"),
                            cls="flex-1 bg-slate-700 rounded-full h-2",
                        ),
                        Span(f"{pct}%", cls=f"text-sm {color} ml-3 font-mono min-w-[3rem] text-right font-semibold"),
                        cls="flex items-center gap-2 mt-1",
                    ),
                    P(f"{label}{dist_str}", cls=f"text-xs {color} mt-0.5"),
                    cls="flex-1 min-w-0",
                ),
                cls="flex items-center gap-4",
            ),
            Div(*action_buttons, cls="flex gap-2 mt-2 justify-end") if action_buttons else None,
            cls="p-3 bg-slate-800/70 rounded-lg",
            id=f"result-face-{i}",
            data_testid=f"result-card-{i}",
        ))

    # Empty state with help CTA
    empty_state = None
    if not result_cards:
        empty_state = Div(
            H3("No strong matches yet", cls="text-lg font-serif text-white mb-2"),
            P("We haven't found a strong match yet -- can you help?",
              cls="text-slate-400 text-sm mb-4"),
            P("If you recognize this person, let us know below.",
              cls="text-slate-500 text-xs"),
            cls="text-center py-8",
            data_testid="result-empty-state",
        )

    # Response form (no login required)
    response_count = len(responses)
    response_form = Div(
        H3("Do you recognize anyone?", cls="text-base font-serif text-white mb-3"),
        P(f"{response_count} response{'s' if response_count != 1 else ''} so far" if response_count else "Be the first to respond!", cls="text-xs text-slate-500 mb-3"),
        Form(
            Div(
                Textarea(
                    name="note", placeholder="I think this is... / I recognize the person on the left...",
                    cls="w-full bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 resize-none",
                    rows="3",
                ),
                cls="mb-3",
            ),
            Input(type="hidden", name="result_id", value=result_id),
            Button("Submit Response", type="submit",
                   cls="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg transition-colors"),
            hx_post=f"/api/compare/result/{result_id}/respond",
            hx_target="#result-response-section",
            hx_swap="innerHTML",
            data_testid="result-response-form",
        ),
        id="result-response-section",
        cls="mt-8 pt-6 border-t border-slate-800",
        data_testid="response-section",
    )

    return (
        Title(og_title),
        *result_og,
        Style("html, body { margin: 0; } body { background-color: #0f172a; }"),
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="flex items-center gap-3 sm:gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    # Hero section — large side-by-side face comparison
                    hero_section if hero_section else H1("Face Comparison Result", cls="text-2xl font-serif font-bold text-white mb-6"),

                    # Source photo (if available)
                    source_photo_section if source_photo_section else None,

                    # Reference person context (archive neighbors)
                    ref_context_section if ref_context_section else None,

                    # Match list or empty state
                    Div(*result_cards, cls="space-y-3") if result_cards else empty_state,

                    # Share
                    Div(
                        _main_mod.share_button(url=f"/compare/result/{result_id}", style="prominent",
                                     label="Share with someone who might know",
                                     title=og_title, text=og_desc),
                        cls="mt-6 text-center",
                    ),

                    # Response form
                    response_form,

                    # Back link
                    Div(
                        A("Try Another Comparison", href="/compare",
                          cls="text-indigo-400 hover:text-indigo-300 text-sm"),
                        cls="mt-6 text-center",
                    ),
                    cls="max-w-2xl mx-auto px-6 py-10",
                ),
            ),
            _main_mod._share_script(),
            cls="min-h-screen bg-slate-900",
        ),
    )
@rt("/api/compare/result/{result_id}/respond")
def post(result_id: str, note: str = "", sess=None):
    """Save a response to a comparison result. No login required."""
    data = _main_mod._load_comparison_results()
    result = data.get("results", {}).get(result_id)
    if not result:
        return P("Result not found.", cls="text-amber-500 text-sm")

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    response = {
        "note": note.strip(),
        "submitted_at": datetime.now().isoformat(),
        "submitted_by": user.email if user else "anonymous",
    }
    if "responses" not in result:
        result["responses"] = []
    result["responses"].append(response)
    _main_mod._save_comparison_result(result)

    return Div(
        P("Thank you for your response!", cls="text-emerald-400 text-sm mb-2"),
        P(f"{len(result['responses'])} response{'s' if len(result['responses']) != 1 else ''} total.",
          cls="text-xs text-slate-500"),
        id="result-response-section",
    )
@rt("/compare/pair")
def get(sess=None):
    """Two-photo face comparison — upload two photos, select a face in each,
    and see how similar they are.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    nav_links = _main_mod._public_nav_links(active="compare", user=user)

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .panel-upload { min-height: 14rem; }
        .face-thumb { cursor: pointer; transition: all 0.15s ease; }
        .face-thumb:hover { transform: scale(1.05); }
        .face-thumb.selected { ring: 2px; }
        @media (max-width: 767px) { .pair-grid { flex-direction: column; } }
    """)

    pair_script = Script("""
    (function(){
        var stateA = null, stateB = null;
        window.selectPairFace = function(panel, uploadId, faceIdx, el) {
            // Deselect all in this panel
            document.querySelectorAll('#panel-' + panel + ' .face-thumb').forEach(function(t) {
                t.classList.remove('ring-2', 'ring-amber-400');
            });
            el.classList.add('ring-2', 'ring-amber-400');
            if (panel === 'a') stateA = {uploadId: uploadId, faceIdx: faceIdx};
            else stateB = {uploadId: uploadId, faceIdx: faceIdx};
            // Enable compare button if both selected
            var btn = document.getElementById('pair-compare-btn');
            if (stateA && stateB) {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
                btn.classList.add('hover:bg-indigo-500');
            }
        };
        window.runPairCompare = function() {
            if (!stateA || !stateB) return;
            var btn = document.getElementById('pair-compare-btn');
            btn.textContent = 'Comparing...';
            btn.disabled = true;
            fetch('/api/compare/pair/match', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'upload_a=' + stateA.uploadId + '&face_a=' + stateA.faceIdx
                    + '&upload_b=' + stateB.uploadId + '&face_b=' + stateB.faceIdx
            })
            .then(function(r) { return r.text(); })
            .then(function(html) {
                document.getElementById('pair-result').innerHTML = html;
                document.getElementById('pair-result').scrollIntoView({behavior: 'smooth'});
                btn.textContent = 'Compare Selected Faces';
                btn.disabled = false;
            })
            .catch(function(e) {
                document.getElementById('pair-result').innerHTML =
                    '<p class="text-red-400 text-sm">Error: ' + e.message + '</p>';
                btn.textContent = 'Compare Selected Faces';
                btn.disabled = false;
            });
        };
    })();
    """)

    def _pair_panel(panel_id: str, label: str) -> object:
        return Div(
            H3(label, cls="text-sm font-medium text-slate-400 mb-3 text-center"),
            Form(
                Div(
                    NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-500 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>'),
                    P("Drop a photo or click to upload", cls="text-slate-400 text-sm"),
                    P("JPG, PNG up to 10 MB", cls="text-slate-600 text-xs mt-1"),
                    Input(type="file", name="photo", accept="image/jpeg,image/png,image/webp",
                          cls="absolute inset-0 w-full h-full opacity-0 cursor-pointer"),
                    Hidden(name="panel", value=panel_id),
                    cls="relative border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-xl p-6 text-center transition-colors cursor-pointer panel-upload",
                ),
                hx_post="/api/compare/pair/upload",
                hx_encoding="multipart/form-data",
                hx_target=f"#panel-{panel_id}",
                hx_swap="innerHTML",
                data_testid=f"pair-upload-{panel_id}",
            ),
            id=f"panel-{panel_id}",
            cls="flex-1 min-w-[280px] bg-slate-800/50 rounded-xl p-4",
            data_testid=f"pair-panel-{panel_id}",
        )

    return (
        Title("Compare Two Photos \u2014 Rhodesli Heritage Archive"),
        *_main_mod.og_tags(
            "Compare Two Photos \u2014 Rhodesli Heritage Archive",
            "Upload two photos and compare faces side-by-side",
            canonical_url="/compare/pair",
        ),
        page_style,
        pair_script,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="flex items-center gap-3 sm:gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    H1("Compare Two Photos", cls="text-3xl font-serif font-bold text-white mb-2"),
                    P("Upload two photos, select a face in each, and see how similar they are.",
                      cls="text-slate-400 text-sm"),
                    P(A("\u2190 Back to Compare", href="/compare",
                        cls="text-indigo-400 hover:text-indigo-300 text-sm"),
                      cls="mt-2"),
                    cls="max-w-5xl mx-auto px-6 pt-6 pb-4",
                ),
            ),
            Section(
                Div(
                    Div(
                        _pair_panel("a", "Photo A"),
                        Div(
                            NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/></svg>'),
                            cls="flex items-center justify-center px-2 py-8 sm:py-0",
                        ),
                        _pair_panel("b", "Photo B"),
                        cls="flex gap-4 pair-grid",
                    ),
                    Button(
                        "Compare Selected Faces",
                        id="pair-compare-btn",
                        onclick="runPairCompare()",
                        disabled=True,
                        cls="mt-6 w-full px-6 py-3 bg-indigo-600 text-white font-medium rounded-xl opacity-50 cursor-not-allowed transition-colors",
                        data_testid="pair-compare-btn",
                    ),
                    P("Select one face in each photo, then click Compare.", cls="text-xs text-slate-500 text-center mt-2"),
                    cls="max-w-5xl mx-auto px-6",
                ),
            ),
            Section(
                Div(id="pair-result", cls="max-w-5xl mx-auto px-6 py-4",
                    data_testid="pair-result"),
            ),
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P("Preserving the memory of the Jewish community of Rhodes", cls="text-[10px] text-slate-600 italic"),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )
@rt("/api/compare/pair/upload")
async def post(request):
    """Handle photo upload for two-photo pair comparison.

    Detects faces in the uploaded photo and returns face thumbnails
    for user selection.
    """
    import time as _time
    import tempfile

    form = await request.form()
    photo = form.get("photo")
    panel = form.get("panel", "a")

    if not photo:
        return Div(P("No photo uploaded.", cls="text-red-400 text-sm"),
                   id=f"panel-{panel}")

    content = await photo.read()
    original_filename = photo.filename or "upload.jpg"
    suffix = Path(original_filename).suffix.lower() or ".jpg"

    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        return Div(
            P("Please upload a JPEG, PNG, or WebP image.", cls="text-red-400 text-sm"),
            id=f"panel-{panel}",
        )

    if len(content) > 10 * 1024 * 1024:
        return Div(P("File is too large (max 10 MB).", cls="text-red-400 text-sm"),
                   id=f"panel-{panel}")

    # Check ML availability
    has_ml = False
    try:
        import cv2
        from insightface.app import FaceAnalysis  # noqa: F401
        from core.ingest_inbox import extract_faces_hybrid
        has_ml = True
    except ImportError:
        pass

    if not has_ml:
        return Div(
            P("Face detection is not available on this server.", cls="text-amber-400 text-sm"),
            id=f"panel-{panel}",
        )

    # Detect faces
    import cv2
    from core.ingest_inbox import extract_faces_hybrid

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Resize for ML
        img = cv2.imread(str(tmp_path))
        if img is not None:
            h, w = img.shape[:2]
            _MAX_DIM = 1024
            if max(h, w) > _MAX_DIM:
                scale = _MAX_DIM / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(tmp_path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

        faces, _, _ = extract_faces_hybrid(tmp_path)

        if not faces:
            return Div(
                H3(f"Photo {panel.upper()}", cls="text-sm font-medium text-slate-400 mb-3 text-center"),
                P("No faces detected. Try a clearer photo.", cls="text-amber-400 text-sm text-center"),
                id=f"panel-{panel}",
                cls="flex-1 min-w-[280px] bg-slate-800/50 rounded-xl p-4",
            )

        # Save upload and face data for later comparison
        upload_id = _main_mod._generate_result_id()

        # Save the image for display
        from core.storage import can_write_r2, upload_bytes_to_r2
        img_key = f"uploads/compare/{upload_id}{suffix}"
        if can_write_r2():
            upload_bytes_to_r2(img_key, content)
        else:
            upload_dir = Path("uploads/compare")
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / f"{upload_id}{suffix}").write_bytes(content)

        # Save face embeddings
        import pickle
        face_save_data = [
            {"mu": f["mu"].tolist(),
             "bbox": f.get("bbox", [0, 0, 0, 0]) if not hasattr(f.get("bbox"), 'tolist') else f["bbox"].tolist()}
            for f in faces
        ]
        faces_pkl = pickle.dumps(face_save_data)
        if can_write_r2():
            upload_bytes_to_r2(f"uploads/compare/{upload_id}_faces.pkl", faces_pkl)
        else:
            upload_dir = Path("uploads/compare")
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / f"{upload_id}_faces.pkl").write_bytes(faces_pkl)

        # Generate face crop thumbnails
        face_thumbs = []
        for i, face in enumerate(faces):
            bbox = face.get("bbox", [0, 0, 0, 0])
            if hasattr(bbox, 'tolist'):
                bbox = bbox.tolist()
            # Crop face from original image for thumbnail
            orig_img = cv2.imread(str(tmp_path))
            if orig_img is not None:
                oh, ow = orig_img.shape[:2]
                x1 = max(0, int(bbox[0]))
                y1 = max(0, int(bbox[1]))
                x2 = min(ow, int(bbox[2]))
                y2 = min(oh, int(bbox[3]))
                if x2 > x1 and y2 > y1:
                    crop = orig_img[y1:y2, x1:x2]
                    _, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    crop_key = f"uploads/compare/{upload_id}_face{i}.jpg"
                    if can_write_r2():
                        upload_bytes_to_r2(crop_key, buf.tobytes())
                    else:
                        (upload_dir / f"{upload_id}_face{i}.jpg").write_bytes(buf.tobytes())

        # Build face selector UI
        from core.storage import get_upload_url
        image_url = get_upload_url(img_key)

        face_elements = []
        for i in range(len(faces)):
            crop_url = get_upload_url(f"uploads/compare/{upload_id}_face{i}.jpg")
            face_elements.append(
                Div(
                    Img(src=crop_url, cls="w-16 h-16 rounded-lg object-cover"),
                    P(f"Face {i + 1}", cls="text-[10px] text-slate-400 mt-1 text-center"),
                    cls="face-thumb p-1 rounded-lg hover:bg-slate-600/50",
                    onclick=f"selectPairFace('{panel}','{upload_id}',{i},this)",
                    data_testid=f"pair-face-{panel}-{i}",
                )
            )

        return Div(
            H3(f"Photo {panel.upper()}", cls="text-sm font-medium text-slate-400 mb-3 text-center"),
            Div(
                Img(src=image_url, cls="max-h-40 rounded-lg mx-auto border border-slate-600"),
                cls="mb-3",
            ),
            P(f"{len(faces)} face{'s' if len(faces) != 1 else ''} detected \u2014 select one:",
              cls="text-xs text-slate-400 mb-2 text-center"),
            Div(*face_elements, cls="flex flex-wrap gap-2 justify-center"),
            id=f"panel-{panel}",
            cls="flex-1 min-w-[280px] bg-slate-800/50 rounded-xl p-4",
        )

    except Exception as e:
        return Div(
            H3(f"Photo {panel.upper()}", cls="text-sm font-medium text-slate-400 mb-3 text-center"),
            P(f"Error: {str(e)}", cls="text-red-400 text-sm text-center"),
            id=f"panel-{panel}",
            cls="flex-1 min-w-[280px] bg-slate-800/50 rounded-xl p-4",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
@rt("/api/compare/pair/match")
def post(upload_a: str = "", face_a: int = 0, upload_b: str = "", face_b: int = 0):
    """Compute similarity between selected faces and summarize all cross matches."""
    import pickle
    import numpy as np
    from core.storage import can_write_r2, download_bytes_from_r2, get_upload_url

    if not upload_a or not upload_b:
        return Div(P("Both photos must have a face selected.", cls="text-red-400 text-sm"))

    # Load face embeddings for both uploads
    def _load_faces(uid):
        data = None
        if can_write_r2():
            data = download_bytes_from_r2(f"uploads/compare/{uid}_faces.pkl")
        if data is None:
            local = Path("uploads/compare") / f"{uid}_faces.pkl"
            if local.exists():
                data = local.read_bytes()
        if data:
            return pickle.loads(data)
        return None

    faces_a = _load_faces(upload_a)
    faces_b = _load_faces(upload_b)

    if not faces_a or not faces_b:
        return Div(P("Could not load face data. Please re-upload.", cls="text-red-400 text-sm"))

    if face_a >= len(faces_a) or face_b >= len(faces_b):
        return Div(P("Invalid face selection.", cls="text-red-400 text-sm"))

    # Compute selected pair similarity
    mu_a = np.array(faces_a[face_a]["mu"])
    mu_b = np.array(faces_b[face_b]["mu"])
    distance = float(np.linalg.norm(mu_a - mu_b))
    from core.confidence import compute_face_confidence, compute_confidence_pct, distance_to_cosine_sim
    cosine_sim = distance_to_cosine_sim(distance)

    # Unified confidence scoring (AD-200)
    conf = compute_face_confidence(distance)
    display_pct = conf["confidence_pct"]

    _tier_ui = {
        "STRONG MATCH": ("Very Likely Match", "text-green-400 border-green-500/30 bg-green-900/20", "bg-green-500"),
        "POSSIBLE MATCH": ("Strong Match", "text-blue-400 border-blue-500/30 bg-blue-900/20", "bg-blue-500"),
        "SIMILAR": ("Possible Match", "text-amber-400 border-amber-500/30 bg-amber-900/20", "bg-amber-500"),
        "WEAK": ("Unlikely Match", "text-slate-400 border-slate-500/30 bg-slate-800", "bg-slate-500"),
    }
    label, badge_cls, bar_color = _tier_ui.get(conf["tier"], _tier_ui["WEAK"])

    crop_a_url = get_upload_url(f"uploads/compare/{upload_a}_face{face_a}.jpg")
    crop_b_url = get_upload_url(f"uploads/compare/{upload_b}_face{face_b}.jpg")

    # Cross-compare all faces A ↔ B (excluding same-photo comparisons by design)
    cross_pairs = []
    for idx_a, fa in enumerate(faces_a):
        mu_vec_a = np.array(fa["mu"])
        for idx_b, fb in enumerate(faces_b):
            mu_vec_b = np.array(fb["mu"])
            d = float(np.linalg.norm(mu_vec_a - mu_vec_b))
            pct = compute_confidence_pct(d)
            cross_pairs.append({"face_a": idx_a, "face_b": idx_b, "distance": d, "confidence_pct": pct})
    cross_pairs.sort(key=lambda p: p["distance"])

    cross_rows = [
        Div(
            Span(f"A{pair['face_a'] + 1} ↔ B{pair['face_b'] + 1}", cls="text-xs text-slate-300"),
            Span(f"{pair['confidence_pct']}%", cls="text-xs text-slate-400"),
            cls="flex items-center justify-between py-1 border-b border-slate-800/50 last:border-0",
        )
        for pair in cross_pairs[:5]
    ]

    archive_sections = []
    try:
        from core.neighbors import find_similar_faces

        face_data = _main_mod.get_face_data()
        registry = _main_mod.load_registry()
        crop_files = _main_mod.get_crop_files()

        def _best_archive_hits(faces, label_prefix):
            hits = []
            for i, face in enumerate(faces):
                matches = find_similar_faces(face["mu"], face_data, registry=registry, limit=1)
                if matches:
                    top = matches[0]
                    hits.append(Div(
                        Span(f"{label_prefix}{i + 1}", cls="text-xs text-slate-300"),
                        Span(f"{top.get('identity_name', 'Unknown')} · {top.get('confidence_pct', 0)}%", cls="text-xs text-slate-400"),
                        cls="flex items-center justify-between py-1 border-b border-slate-800/50 last:border-0",
                    ))
            return hits

        archive_sections.append(
            Div(
                H4("Top cross-photo matches", cls="text-sm font-medium text-slate-300 mb-2"),
                Div(*cross_rows, cls="rounded-lg border border-slate-700/60 bg-slate-900/30 p-3"),
                data_testid="pair-cross-matches",
                cls="mt-8",
            )
        )

        archive_a = find_similar_faces(mu_a.tolist(), face_data, registry=registry, limit=5)
        archive_b = find_similar_faces(mu_b.tolist(), face_data, registry=registry, limit=5)

        if archive_a:
            archive_sections.append(
                Div(
                    H4("Top archive matches for selected face A", cls="text-sm font-medium text-slate-300 mb-2"),
                    _compare_results_grid(archive_a, crop_files),
                    cls="mt-8",
                    data_testid="pair-archive-a",
                )
            )
        if archive_b:
            archive_sections.append(
                Div(
                    H4("Top archive matches for selected face B", cls="text-sm font-medium text-slate-300 mb-2"),
                    _compare_results_grid(archive_b, crop_files),
                    cls="mt-8",
                    data_testid="pair-archive-b",
                )
            )

        all_archive_summary_a = _best_archive_hits(faces_a, "A")
        all_archive_summary_b = _best_archive_hits(faces_b, "B")
        if all_archive_summary_a or all_archive_summary_b:
            archive_sections.append(
                Div(
                    H4("Archive best hit per detected face", cls="text-sm font-medium text-slate-300 mb-2"),
                    Div(
                        Div(H5("Photo A", cls="text-xs text-slate-400 mb-1"), Div(*all_archive_summary_a), cls="flex-1 min-w-[220px]"),
                        Div(H5("Photo B", cls="text-xs text-slate-400 mb-1"), Div(*all_archive_summary_b), cls="flex-1 min-w-[220px]"),
                        cls="flex flex-wrap gap-4",
                    ),
                    cls="mt-8",
                    data_testid="pair-archive-summary",
                )
            )
    except Exception:
        archive_sections = []

    return Div(
        Div(
            H3("Comparison Result", cls="text-lg font-serif text-white mb-4 text-center"),
            Div(
                Div(
                    Img(src=crop_a_url, cls="w-24 h-24 rounded-full object-cover ring-2 ring-slate-600"),
                    P("Photo A", cls="text-xs text-slate-400 mt-2"),
                    cls="flex flex-col items-center",
                ),
                Div(
                    Span(f"{display_pct}%", cls="text-2xl font-bold text-white"),
                    Span(label, cls=f"text-xs font-medium px-2 py-1 rounded border mt-1 {badge_cls}"),
                    cls="flex flex-col items-center justify-center px-6",
                ),
                Div(
                    Img(src=crop_b_url, cls="w-24 h-24 rounded-full object-cover ring-2 ring-slate-600"),
                    P("Photo B", cls="text-xs text-slate-400 mt-2"),
                    cls="flex flex-col items-center",
                ),
                cls="flex items-center justify-center gap-4 mb-6",
            ),
            Div(
                Div(cls=f"{bar_color} h-2 rounded-full transition-all", style=f"width: {display_pct}%"),
                cls="w-full max-w-xs mx-auto bg-slate-700 rounded-full h-2 mb-4",
            ),
            Div(
                P(f"Euclidean distance: {distance:.3f}", cls="text-[10px] text-slate-600"),
                P(f"Cosine similarity: {cosine_sim:.4f}", cls="text-[10px] text-slate-600"),
                P("Confidence", cls="text-[10px] text-slate-600"),
                cls="text-center",
            ),
            Button(
                "Compare Another Pair",
                onclick="window.location.reload()",
                cls="mt-4 px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 text-sm",
            ),
            Div(
                A("Explore the full archive →", href="/photos", cls="text-xs text-indigo-400 hover:text-indigo-300"),
                A("Know someone in this photo? Help identify them →", href="/compare", cls="text-xs text-indigo-400 hover:text-indigo-300 ml-4"),
                cls="mt-4 flex flex-wrap gap-3 justify-center",
            ),
            cls="text-center",
        ),
        *archive_sections,
        cls="bg-slate-800/50 rounded-2xl p-8 max-w-3xl mx-auto mt-4",
        data_testid="pair-comparison-result",
    )
def _resolve_entity_faces(entity_type: str, entity_id: str, face_data: dict, registry=None) -> list:
    """Resolve face embeddings from any entity type.

    Returns list of dicts: {face_id, embedding, crop_url}
    """
    crop_files = _main_mod.get_crop_files()
    faces = []

    if entity_type == "person":
        if not registry:
            return []
        try:
            ident = registry.get_identity(entity_id)
        except (KeyError, Exception):
            return []
        if not ident:
            return []
        all_fids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        for entry in all_fids:
            fid = entry if isinstance(entry, str) else entry.get("face_id", "")
            emb = face_data.get(fid)
            if emb and "mu" in emb:
                faces.append({
                    "face_id": fid,
                    "embedding": emb["mu"],
                    "crop_url": _resolve_crop_url(fid, crop_files),
                })

    elif entity_type == "photo":
        photo_meta = _main_mod.get_photo_metadata(entity_id)
        if not photo_meta:
            return []
        face_ids = photo_meta.get("face_ids", [])
        if not face_ids:
            face_ids = [f["face_id"] for f in photo_meta.get("faces", []) if isinstance(f, dict) and f.get("face_id")]
        for fid in face_ids:
            emb = face_data.get(fid)
            if emb and "mu" in emb:
                faces.append({
                    "face_id": fid,
                    "embedding": emb["mu"],
                    "crop_url": _resolve_crop_url(fid, crop_files),
                })

    elif entity_type == "upload":
        import json as _json_resolve
        status_path = _main_mod.data_path / "inbox" / f"{entity_id}.status.json"
        if not status_path.exists():
            return []
        with open(status_path) as f:
            status = _json_resolve.load(f)
        face_ids = status.get("face_ids", [])
        for fid in face_ids:
            emb = face_data.get(fid)
            if emb and "mu" in emb:
                faces.append({
                    "face_id": fid,
                    "embedding": emb["mu"],
                    "crop_url": _resolve_crop_url(fid, crop_files),
                })

    return faces
def _compute_comparison_score(source_emb, target_embs: list) -> dict:
    """Compute best match score between a source embedding and list of target embeddings.

    Returns: {distance, confidence_pct, tier}
    """
    import numpy as np

    if not target_embs:
        return {"distance": 99.0, "confidence_pct": 0, "tier": "WEAK"}

    distances = [float(np.linalg.norm(source_emb - t)) for t in target_embs]
    best_dist = min(distances)

    # Unified confidence scoring (AD-200)
    from core.confidence import compute_face_confidence
    conf = compute_face_confidence(best_dist)

    return {"distance": best_dist, "confidence_pct": conf["confidence_pct"], "tier": conf["tier"]}
@rt("/api/compare/execute")
def post(source_type: str = "", source_id: str = "", target_type: str = "",
         target_ids: str = "", sess=None):
    """Unified comparison endpoint — any entity type against any other.

    Supports: person/photo/upload as source, person/photo/upload/archive as target.
    Multiple targets supported (comma-separated IDs, max 5).
    Returns HTMX fragment with matrix results.
    """
    import numpy as np

    if not source_type or not source_id:
        return Div(P("Select a source to compare.", cls="text-slate-400 text-sm text-center py-8"),
                   id="compare-results-area", data_testid="compare-empty")

    if not target_type and not target_ids:
        return Div(P("Select one or more targets to compare against.",
                     cls="text-slate-400 text-sm text-center py-8"),
                   id="compare-results-area", data_testid="compare-empty")

    _main_mod._build_caches()
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = user and user.is_admin if _main_mod.is_auth_enabled() else True

    # Resolve source faces
    source_faces = _resolve_entity_faces(source_type, source_id, face_data, registry)
    if not source_faces:
        return Div(P("No faces found in the source.", cls="text-amber-500 text-sm text-center py-8"),
                   id="compare-results-area")

    # Resolve targets
    results_by_face = []  # [{face_id, crop_url, targets: [{name, id, type, distance, pct, tier}]}]

    if target_type == "archive":
        # Compare against entire archive — use find_similar_faces
        from core.neighbors import find_similar_faces
        for sf in source_faces:
            matches = find_similar_faces(
                sf["embedding"], face_data, registry=registry,
                limit=10, exclude_face_ids={sf["face_id"]},
            )
            results_by_face.append({
                "face_id": sf["face_id"],
                "crop_url": sf["crop_url"],
                "targets": [{
                    "target_id": m.get("identity_id", ""),
                    "target_type": "person",
                    "target_name": m.get("identity_name", "Unknown"),
                    "target_crop_url": _resolve_crop_url(m["face_id"], crop_files),
                    "distance": m["distance"],
                    "confidence_pct": m.get("confidence_pct", 0),
                    "tier": m.get("tier", "WEAK"),
                    "matched_face_id": m["face_id"],
                } for m in matches],
            })
    else:
        # Specific targets
        tid_list = [t.strip() for t in target_ids.split(",") if t.strip()][:5]
        if not tid_list:
            return Div(P("No targets selected.", cls="text-slate-400 text-sm text-center py-8"),
                       id="compare-results-area")

        # Build target info
        targets_info = []
        for tid in tid_list:
            ttype = target_type
            target_faces = _resolve_entity_faces(ttype, tid, face_data, registry)
            target_name = "Unknown"
            target_crop = ""
            if ttype == "person":
                try:
                    ident = registry.get_identity(tid)
                except (KeyError, Exception):
                    ident = None
                if ident:
                    target_name = ensure_utf8_display(ident.get("name", "Unknown"))
                    # Get best crop
                    anchor_ids = ident.get("anchor_ids", [])
                    if anchor_ids:
                        first_fid = anchor_ids[0] if isinstance(anchor_ids[0], str) else anchor_ids[0].get("face_id", "")
                        target_crop = _resolve_crop_url(first_fid, crop_files)
            elif ttype == "photo":
                pmeta = _main_mod.get_photo_metadata(tid)
                if pmeta:
                    target_name = pmeta.get("filename", pmeta.get("path", "Photo"))
                    target_crop = storage.get_photo_url(pmeta.get("filename") or pmeta.get("path", "")) if (pmeta.get("filename") or pmeta.get("path")) else ""

            targets_info.append({
                "id": tid,
                "type": ttype,
                "name": target_name,
                "crop_url": target_crop,
                "faces": target_faces,
            })

        # Compute matrix: source face × target
        for sf in source_faces:
            face_targets = []
            for ti in targets_info:
                target_embs = [f["embedding"] for f in ti["faces"]]
                score = _compute_comparison_score(sf["embedding"], target_embs)

                # Find best matching target face
                best_face_id = ""
                if ti["faces"] and target_embs:
                    dists = [float(np.linalg.norm(sf["embedding"] - t)) for t in target_embs]
                    best_idx = int(np.argmin(dists))
                    best_face_id = ti["faces"][best_idx]["face_id"]

                face_targets.append({
                    "target_id": ti["id"],
                    "target_type": ti["type"],
                    "target_name": ti["name"],
                    "target_crop_url": ti["crop_url"],
                    "distance": score["distance"],
                    "confidence_pct": score["confidence_pct"],
                    "tier": score["tier"],
                    "matched_face_id": best_face_id,
                })

            results_by_face.append({
                "face_id": sf["face_id"],
                "crop_url": sf["crop_url"],
                "targets": face_targets,
            })

    # Find best overall match
    best_pct = 0
    best_face_idx = -1
    best_target_idx = -1
    for fi, fr in enumerate(results_by_face):
        for ti, tr in enumerate(fr["targets"]):
            if tr["confidence_pct"] > best_pct:
                best_pct = tr["confidence_pct"]
                best_face_idx = fi
                best_target_idx = ti

    # Compute per-target context: best existing match + rank
    target_context = {}  # target_id -> {best_pct, best_name, matches_ranked}
    from core.neighbors import find_similar_faces
    for fr in results_by_face:
        for tr in fr["targets"]:
            tid = tr["target_id"]
            if tid in target_context:
                continue
            if tr["target_type"] == "person" and tid:
                try:
                    t_ident = registry.get_identity(tid)
                except (KeyError, Exception):
                    t_ident = None
                if t_ident:
                    t_fids = t_ident.get("anchor_ids", []) + t_ident.get("candidate_ids", [])
                    t_fid = t_fids[0] if t_fids else ""
                    if isinstance(t_fid, dict):
                        t_fid = t_fid.get("face_id", "")
                    t_emb = face_data.get(t_fid, {}).get("mu") if t_fid else None
                    if t_emb is not None:
                        t_matches = find_similar_faces(
                            t_emb, face_data, registry=registry,
                            limit=5, exclude_face_ids=set(t_fids if isinstance(t_fids[0], str) else [f.get("face_id", "") for f in t_fids] if t_fids else []),
                        )
                        if t_matches:
                            target_context[tid] = {
                                "best_pct": t_matches[0].get("confidence_pct", 0),
                                "best_name": t_matches[0].get("identity_name", "Unknown"),
                            }
            if tid not in target_context:
                target_context[tid] = {"best_pct": 0, "best_name": ""}

    # Build source entity name
    source_name = "Upload"
    if source_type == "person":
        try:
            si = registry.get_identity(source_id)
        except (KeyError, Exception):
            si = None
        if si:
            source_name = ensure_utf8_display(si.get("name", "Unknown"))
    elif source_type == "photo":
        pm = _main_mod.get_photo_metadata(source_id)
        if pm:
            source_name = pm.get("filename", pm.get("path", "Photo"))

    # Count targets
    n_targets = len(results_by_face[0]["targets"]) if results_by_face else 0
    n_faces = len(results_by_face)

    # Save result for sharing
    result_data = {
        "result_id": _main_mod._generate_result_id(),
        "created_at": datetime.now().isoformat(),
        "query_type": "unified",
        "source_type": source_type,
        "source_id": source_id,
        "source_name": source_name,
        "matches": [],
        "responses": [],
    }
    for fr in results_by_face:
        for tr in fr["targets"]:
            result_data["matches"].append({
                "face_id": fr["face_id"],
                "target_id": tr["target_id"],
                "target_name": tr["target_name"],
                "distance": tr["distance"],
                "confidence_pct": tr["confidence_pct"],
                "tier": tr["tier"],
            })
    rid = _main_mod._save_comparison_result(result_data)

    # --- Build results HTML ---
    parts = []

    # Header
    target_label = "the archive" if target_type == "archive" else f"{n_targets} target{'s' if n_targets != 1 else ''}"
    parts.append(
        Div(
            H3(f"Comparing {n_faces} face{'s' if n_faces != 1 else ''} against {target_label}",
               cls="text-lg font-serif text-white"),
            cls="mb-4",
            data_testid="compare-results-header",
        )
    )

    # Best Matches summary section (above per-face details)
    summary_section = _compare_summary_section(
        results_by_face, crop_files, user_is_admin, registry, rid=rid,
    )
    has_summary = summary_section is not None
    if has_summary:
        parts.append(summary_section)

    # Per-face sections
    for fi, fr in enumerate(results_by_face):
        face_id = fr["face_id"]
        crop_url = fr["crop_url"]

        # Skip face section header if only 1 face
        show_face_header = n_faces > 1

        target_rows = []
        for ti, tr in enumerate(fr["targets"]):
            pct = tr["confidence_pct"]
            tier = tr["tier"]
            is_best = (fi == best_face_idx and ti == best_target_idx)

            # Color based on tier (with glow classes for visual polish)
            if pct >= 85:
                bar_color = "bg-emerald-500"
                label_color = "text-emerald-400"
                bar_glow = "bar-glow-emerald"
            elif pct >= 70:
                bar_color = "bg-amber-500"
                label_color = "text-amber-400"
                bar_glow = "bar-glow-amber"
            elif pct >= 50:
                bar_color = "bg-blue-500"
                label_color = "text-blue-400"
                bar_glow = "bar-glow-blue"
            else:
                bar_color = "bg-slate-600"
                label_color = "text-slate-400"
                bar_glow = ""

            # Confidence label
            if pct >= 85:
                conf_label = "Strong match"
            elif pct >= 70:
                conf_label = "Possible match"
            elif pct >= 50:
                conf_label = "Similar"
            else:
                conf_label = "Unlikely"

            dist_str = f" · dist: {tr['distance']:.2f}" if user_is_admin else ""

            # Build context line
            ctx = target_context.get(tr["target_id"], {})
            ctx_parts = []
            ctx_best_pct = ctx.get("best_pct", 0)
            ctx_best_name = ctx.get("best_name", "")
            if ctx_best_pct > 0 and tr["target_type"] == "person":
                if pct > ctx_best_pct:
                    ctx_parts.append(f"Better than any existing match!")
                elif ctx_best_name:
                    ctx_parts.append(f"{tr['target_name']}'s best is {ctx_best_pct}% ({ctx_best_name})")
            context_line = " · ".join(ctx_parts) if ctx_parts else ""

            # Target link
            target_link = "#"
            if tr["target_type"] == "person" and tr["target_id"]:
                target_link = f"/person/{tr['target_id']}"
            elif tr["target_type"] == "photo" and tr["target_id"]:
                target_link = f"/photo/{tr['target_id']}"

            # Admin action buttons
            action_btns = []
            face_identity = _main_mod.get_identity_for_face(registry, face_id)
            face_iid = face_identity.get("identity_id") if face_identity else None
            if user_is_admin and tr["target_type"] == "person" and tr["target_id"] and face_iid:
                _face_name = face_identity.get("name", "") if face_identity else ""
                _target_name = tr.get("target_name", "")
                _merge_confirm = f"Merge {_face_name} into {_target_name}? All faces will be combined." if _target_name and not _target_name.startswith("Unidentified") else "Merge these identities? This can be undone."
                action_btns.append(
                    Button("Merge", hx_post=f"/api/identity/{tr['target_id']}/merge/{face_iid}?source=compare",
                           hx_target=f"#compare-row-{fi}-{ti}", hx_swap="outerHTML",
                           hx_confirm=_merge_confirm,
                           cls="px-2 py-0.5 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded"))
                action_btns.append(
                    Button("Not Same", hx_post=f"/api/identity/{tr['target_id']}/not-same/{face_iid}?source=compare",
                           hx_target=f"#compare-row-{fi}-{ti}", hx_swap="outerHTML",
                           cls="px-2 py-0.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded"))

            highlight_cls = "best-match-glow bg-amber-950/10" if is_best else ""

            target_rows.append(
                Div(
                    Div(
                        # Target crop + name
                        Div(
                            Img(src=tr["target_crop_url"], cls="w-16 h-16 rounded-lg object-cover border border-slate-600",
                                alt=tr["target_name"]) if tr["target_crop_url"] else Div(cls="w-16 h-16 rounded-lg bg-slate-700"),
                            cls="flex-shrink-0",
                        ),
                        Div(
                            A(tr["target_name"], href=target_link,
                              cls="text-sm text-white hover:text-indigo-300 font-medium truncate block"),
                            # Confidence bar with inner glow
                            Div(
                                Div(
                                    Div(cls=f"h-2.5 rounded-full {bar_color} {bar_glow} compare-bar-animate",
                                        style=f"width: {pct}%"),
                                    cls=f"flex-1 bg-slate-700/80 rounded-full h-2.5",
                                ),
                                Span(f"{pct}%", cls=f"text-sm {label_color} ml-3 font-mono min-w-[3rem] text-right font-semibold"),
                                cls="flex items-center gap-2 mt-1",
                            ),
                            Span(f"{conf_label}{dist_str}", cls=f"text-xs {label_color} mt-0.5"),
                            Span(context_line, cls="text-[11px] text-slate-500 mt-0.5 block",
                                 data_testid=f"context-{fi}-{ti}") if context_line else None,
                            cls="flex-1 min-w-0",
                        ),
                        cls="flex items-center gap-3",
                    ),
                    Div(*action_btns, cls="flex gap-2 mt-2 justify-end") if action_btns else None,
                    cls=f"p-3 rounded-lg {highlight_cls}",
                    id=f"compare-row-{fi}-{ti}",
                    data_testid=f"compare-row-{fi}-{ti}",
                )
            )

        # Face section with hide/show toggle
        face_section_parts = []
        if show_face_header:
            face_section_parts.append(
                Div(
                    Img(src=crop_url, cls="w-20 h-20 rounded-lg object-cover border-2 border-slate-600",
                        alt=f"Face {fi+1}") if crop_url else Div(cls="w-20 h-20 rounded-lg bg-slate-700"),
                    Span(f"Face {fi + 1}", cls="text-sm text-white font-medium ml-3"),
                    # Hide/show toggle
                    Button(
                        NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 face-collapse-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>'),
                        cls="ml-auto text-slate-500 hover:text-white transition-colors p-1",
                        data_action="toggle-face-section",
                        data_face_idx=str(fi),
                    ),
                    cls="flex items-center mb-3 cursor-pointer",
                    data_testid=f"compare-face-header-{fi}",
                )
            )

        # Wrap target rows in collapsible container
        # Collapse per-face detail sections when summary is showing best matches
        collapsed_cls = " face-section-collapsed" if has_summary else ""
        content_style = "max-height: 0" if has_summary else f"max-height: {len(target_rows) * 120}px"
        content_div = Div(
            *target_rows,
            cls=f"face-section-content space-y-2",
            style=content_style,
            data_testid=f"compare-face-content-{fi}",
        )

        parts.append(
            Div(
                *(face_section_parts + [content_div]),
                cls=f"p-4 bg-slate-800/50 rounded-xl border border-slate-700/30 compare-section-animate compare-card{collapsed_cls}",
                id=f"compare-face-section-{fi}",
                data_testid=f"compare-face-section-{fi}",
                style=f"animation-delay: {fi * 100}ms",
            )
        )

    # Smart defaults: empathetic message if all unlikely
    all_pcts = [tr["confidence_pct"] for fr in results_by_face for tr in fr["targets"]]
    if all_pcts and max(all_pcts) < 50:
        parts.append(
            Div(
                P("No strong matches found.", cls="text-slate-300 text-sm font-medium"),
                P("Try uploading a clearer photo or comparing against different people.",
                  cls="text-slate-500 text-xs mt-1"),
                cls="p-3 bg-slate-800/30 rounded-lg border border-slate-700/20 text-center compare-fade-in",
                data_testid="compare-no-strong-matches",
            )
        )

    # Cross-target insight: face matches multiple targets strongly
    if n_targets > 1 and n_faces > 0:
        for fi, fr in enumerate(results_by_face):
            strong_targets = [tr for tr in fr["targets"] if tr["confidence_pct"] >= 70]
            if len(strong_targets) >= 2:
                names = " and ".join(ensure_utf8_display(t["target_name"]) for t in strong_targets[:3])
                parts.append(
                    Div(
                        P(f"Face {fi + 1} strongly matches both {names}.",
                          cls="text-sm text-amber-300"),
                        P("These people may be related.", cls="text-xs text-slate-500 mt-0.5"),
                        cls="p-3 bg-amber-950/20 border border-amber-500/20 rounded-lg compare-fade-in",
                        data_testid=f"cross-target-insight-{fi}",
                    )
                )

    # Share + try again footer
    share_url = f"{_main_mod.SITE_URL}/compare/result/{rid}"
    parts.append(
        Div(
            A("Share this comparison", href=share_url, target="_blank",
              cls="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors inline-block"),
            Button("Try another comparison", onclick="location.href='/compare'",
                   cls="px-4 py-2 bg-slate-700 text-slate-300 text-sm font-medium rounded-lg hover:bg-slate-600 transition-colors"),
            cls="flex gap-3 justify-center flex-wrap mt-6",
            data_testid="compare-results-actions",
        )
    )

    return Div(*parts, id="compare-results-area", cls="space-y-4",
               data_testid="compare-results-area")
@rt("/api/compare/search-unified")
def get(q: str = "", types: str = "person,photo", slot: str = "target", sess=None):
    """Unified search across people and photos for the comparison workspace.

    Returns type-badged results with preview images.
    slot=source: results use data-action="select-compare-source" for source slot selection.
    slot=target (default): results use data-action="select-compare-target" for target slot.
    Result container ID matches the slot+types so HTMX targets the correct panel.
    """
    # Determine correct result container ID based on slot and types
    type_list = [t.strip() for t in types.split(",")]
    if slot == "source":
        if type_list == ["person"]:
            result_id = "source-person-results"
        elif type_list == ["photo"]:
            result_id = "source-photo-results"
        else:
            result_id = "source-person-results"
    else:
        if type_list == ["person"]:
            result_id = "target-person-results"
        elif type_list == ["photo"]:
            result_id = "target-photo-results"
        else:
            result_id = "target-person-results"

    if len(q.strip()) < 2:
        return Div(id=result_id)

    query = q.strip()
    data_action = "select-compare-source" if slot == "source" else "select-compare-target"
    results_html = []

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Track photo IDs already shown (to avoid duplicates when person search adds tagged photos)
    shown_photo_ids = set()

    # Search people (all states: CONFIRMED, PROPOSED, INBOX)
    matched_people = []
    if "person" in type_list:
        for state in [IdentityState.CONFIRMED, IdentityState.PROPOSED, IdentityState.INBOX]:
            identities = registry.list_identities(state=state)
            for ident in identities:
                if ident.get("merged_into"):
                    continue
                name = ident.get("name", "")
                if query.lower() not in name.lower():
                    continue
                matched_people.append(ident)
                iid = ident["identity_id"]
                state_str = ident.get("state", "INBOX")
                all_fids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
                preview_fid = ""
                if all_fids:
                    entry = all_fids[0]
                    preview_fid = entry if isinstance(entry, str) else entry.get("face_id", "")
                crop_url = _resolve_crop_url(preview_fid, crop_files)

                state_badge_cls = {
                    "CONFIRMED": "bg-emerald-900/50 text-emerald-400",
                    "PROPOSED": "bg-amber-900/50 text-amber-400",
                    "INBOX": "bg-slate-700 text-slate-400",
                }.get(state_str, "bg-slate-700 text-slate-400")
                state_label = {
                    "CONFIRMED": "Confirmed",
                    "PROPOSED": "Proposed",
                    "INBOX": "Unidentified",
                }.get(state_str, state_str)

                face_count = len(all_fids)

                results_html.append(
                    Div(
                        Img(src=crop_url, cls="w-10 h-10 rounded-full object-cover border border-slate-600",
                            alt=name) if crop_url else Div(cls="w-10 h-10 rounded-full bg-slate-700"),
                        Div(
                            Span(ensure_utf8_display(name), cls="text-sm text-white font-medium truncate block"),
                            Div(
                                Span("Person", cls="text-[10px] bg-indigo-900/50 text-indigo-400 px-1.5 py-0.5 rounded"),
                                Span(state_label, cls=f"text-[10px] {state_badge_cls} px-1.5 py-0.5 rounded"),
                                Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-[10px] text-slate-500"),
                                cls="flex items-center gap-1.5 mt-0.5",
                            ),
                            cls="min-w-0 flex-1",
                        ),
                        cls="flex items-center gap-3 p-2 hover:bg-slate-700/50 rounded-lg cursor-pointer transition-colors",
                        data_entity_type="person",
                        data_entity_id=iid,
                        data_entity_name=ensure_utf8_display(name),
                        data_entity_crop=crop_url or "",
                        data_testid=f"search-result-person-{iid}",
                        data_action=data_action,
                    )
                )

    # Also find photos containing matched people's faces (Bug 4 fix)
    if matched_people and _main_mod._face_to_photo_cache and _main_mod._photo_cache:
        for ident in matched_people:
            person_name = ensure_utf8_display(ident.get("name", ""))
            all_fids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            for entry in all_fids:
                fid = entry if isinstance(entry, str) else entry.get("face_id", "")
                pid = _main_mod._face_to_photo_cache.get(fid)
                if not pid or pid in shown_photo_ids:
                    continue
                shown_photo_ids.add(pid)
                pmeta = _main_mod._photo_cache.get(pid, {})
                fname = pmeta.get("filename") or pmeta.get("path", "")
                if not fname:
                    continue
                photo_url = storage.get_photo_url(fname)
                collection = pmeta.get("collection", "")
                faces = pmeta.get("faces", [])
                face_count = len(faces)

                results_html.append(
                    Div(
                        Img(src=photo_url, cls="w-10 h-10 rounded object-cover border border-slate-600",
                            alt=fname) if photo_url else Div(cls="w-10 h-10 rounded bg-slate-700"),
                        Div(
                            Span(fname[:30] + ("..." if len(fname) > 30 else ""), cls="text-sm text-white font-medium truncate block"),
                            Div(
                                Span("Photo", cls="text-[10px] bg-purple-900/50 text-purple-400 px-1.5 py-0.5 rounded"),
                                Span(f"Contains {person_name[:15]}", cls="text-[10px] text-slate-400 truncate"),
                                Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-[10px] text-slate-500"),
                                cls="flex items-center gap-1.5 mt-0.5",
                            ),
                            cls="min-w-0 flex-1",
                        ),
                        cls="flex items-center gap-3 p-2 hover:bg-slate-700/50 rounded-lg cursor-pointer transition-colors",
                        data_entity_type="photo",
                        data_entity_id=pid,
                        data_entity_name=fname,
                        data_entity_crop=photo_url or "",
                        data_testid=f"search-result-photo-{pid}",
                        data_action=data_action,
                    )
                )

    # Search photos by filename/collection
    if "photo" in type_list and _main_mod._photo_cache:
        for pid, pmeta in _main_mod._photo_cache.items():
            if pid in shown_photo_ids:
                continue
            fname = pmeta.get("filename") or pmeta.get("path", "")
            collection = pmeta.get("collection", "")
            faces = pmeta.get("faces", [])
            searchable = f"{fname} {collection}".lower()
            if query.lower() not in searchable:
                continue
            shown_photo_ids.add(pid)
            photo_url = storage.get_photo_url(fname) if fname else ""
            face_count = len(faces)

            results_html.append(
                Div(
                    Img(src=photo_url, cls="w-10 h-10 rounded object-cover border border-slate-600",
                        alt=fname) if photo_url else Div(cls="w-10 h-10 rounded bg-slate-700"),
                    Div(
                        Span(fname[:30] + ("..." if len(fname) > 30 else ""), cls="text-sm text-white font-medium truncate block"),
                        Div(
                            Span("Photo", cls="text-[10px] bg-purple-900/50 text-purple-400 px-1.5 py-0.5 rounded"),
                            Span(collection[:20] if collection else "No collection", cls="text-[10px] text-slate-500 truncate"),
                            Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-[10px] text-slate-500"),
                            cls="flex items-center gap-1.5 mt-0.5",
                        ),
                        cls="min-w-0 flex-1",
                    ),
                    cls="flex items-center gap-3 p-2 hover:bg-slate-700/50 rounded-lg cursor-pointer transition-colors",
                    data_entity_type="photo",
                    data_entity_id=pid,
                    data_entity_name=fname,
                    data_entity_crop=photo_url or "",
                    data_testid=f"search-result-photo-{pid}",
                    data_action=data_action,
                )
            )

    if not results_html:
        return Div(P("No results found.", cls="text-sm text-slate-500 py-2"),
                   id=result_id)

    # Limit to 10 results
    return Div(*results_html[:10], id=result_id,
               cls="space-y-1 max-h-64 overflow-y-auto")
@rt("/api/compare/find-similar-targets")
def get(identity_id: str = "", face_id: str = "", sess=None):
    """Find visually similar people to auto-populate target pills.

    Returns target entities as pills for the comparison workspace.
    """
    _main_mod._build_caches()
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    query_emb = None
    if face_id and face_id in face_data:
        query_emb = face_data[face_id]["mu"]
    elif identity_id:
        try:
            ident = registry.get_identity(identity_id)
        except (KeyError, Exception):
            ident = None
        if ident:
            fids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            for entry in fids:
                fid = entry if isinstance(entry, str) else entry.get("face_id", "")
                if fid in face_data:
                    query_emb = face_data[fid]["mu"]
                    break

    if query_emb is None:
        return Div(P("No embedding found.", cls="text-sm text-slate-500"), id="compare-similar-results")

    from core.neighbors import find_similar_faces
    results = find_similar_faces(query_emb, face_data, registry=registry, limit=5)

    pills = []
    seen_ids = set()
    for r in results:
        iid = r.get("identity_id", "")
        if not iid or iid in seen_ids:
            continue
        seen_ids.add(iid)
        name = ensure_utf8_display(r.get("identity_name", "Unknown"))
        crop_url = _resolve_crop_url(r["face_id"], crop_files)

        pills.append(
            Div(
                Img(src=crop_url, cls="w-6 h-6 rounded-full object-cover", alt=name) if crop_url else None,
                Span(name, cls="text-xs text-white truncate max-w-[100px]"),
                Span(f"{r.get('confidence_pct', 0)}%", cls="text-[10px] text-slate-400"),
                data_entity_type="person",
                data_entity_id=iid,
                data_entity_name=name,
                data_entity_crop=crop_url or "",
                data_action="select-compare-target",
                cls="flex items-center gap-1.5 px-2 py-1 bg-slate-700 rounded-full cursor-pointer hover:bg-slate-600 transition-colors",
                data_testid=f"similar-target-{iid}",
            )
        )

    if not pills:
        return Div(P("No similar people found.", cls="text-sm text-slate-500"), id="compare-similar-results")

    return Div(
        P("Visually similar people:", cls="text-xs text-slate-400 mb-2"),
        Div(*pills, cls="flex flex-wrap gap-2"),
        id="compare-similar-results",
        data_testid="compare-similar-results",
    )
def _compare_photo_with_overlays(photo_url_str: str, photo_id: str, highlight_face_id: str, registry, img_height_cls: str) -> Div:
    """Render a photo with face bounding box overlays for the compare modal.

    Shows all faces in the photo with state-based colors. The face being
    compared (highlight_face_id) gets a bright amber highlight.
    """
    photo = _main_mod.get_photo_metadata(photo_id) if photo_id else None
    if not photo or not photo_url_str:
        return Div(
            Img(src=photo_url_str or "", cls=f"max-w-full {img_height_cls} object-contain rounded") if photo_url_str else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2")

    width, height = _main_mod.get_photo_dimensions(photo["filename"])
    has_dimensions = width > 0 and height > 0

    face_overlays = []
    if has_dimensions:
        for face_data in photo.get("faces", []):
            face_id = face_data["face_id"]
            bbox = face_data.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox

            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            identity = _main_mod.get_identity_for_face(registry, face_id)
            raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
            display_name = ensure_utf8_display(raw_name)
            identity_id = identity["identity_id"] if identity else None

            is_highlighted = face_id == highlight_face_id

            if is_highlighted:
                overlay_cls = "border-2 border-amber-400 bg-amber-400/25"
            elif identity:
                state = identity.get("state", "INBOX")
                if state == "CONFIRMED":
                    overlay_cls = "border-2 border-emerald-500/60 bg-emerald-500/10"
                elif state == "PROPOSED":
                    overlay_cls = "border-2 border-indigo-400/60 bg-indigo-400/10"
                else:
                    overlay_cls = "border-2 border-slate-400/60 bg-slate-400/5"
            else:
                overlay_cls = "border-2 border-dashed border-slate-400/40 bg-slate-400/5"

            # Click handler: navigate to identity card, closing the modal
            nav_section = _section_for_state(identity.get("state", "INBOX")) if identity else "to_review"
            click_script = (
                f"on click halt the event's bubbling "
                f"then add .hidden to #compare-modal "
                f"then go to url '/?section={nav_section}&view=browse#identity-{identity_id}'"
            ) if identity_id else ""

            overlay = Div(
                Span(
                    display_name,
                    cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10"
                ),
                cls=f"absolute cursor-pointer transition-all group {overlay_cls}",
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=display_name,
                data_face_id=face_id,
                **{"_": click_script} if click_script else {},
            )
            face_overlays.append(overlay)

    return Div(
        Div(
            Img(src=photo_url_str, cls=f"max-w-full {img_height_cls} object-contain rounded"),
            *face_overlays,
            cls="relative inline-block max-w-full"),
        cls="flex justify-center bg-slate-700/50 rounded p-2")
@rt("/api/identity/{target_id}/compare/{neighbor_id}")
def get(target_id: str, neighbor_id: str, target_idx: int = 0, neighbor_idx: int = 0, view: str = "faces", filter: str = "", sess=None):
    """Side-by-side comparison view for evaluating merge candidates."""
    try:
        registry = _main_mod.load_registry()
        tgt = registry.get_identity(target_id)
        nbr = registry.get_identity(neighbor_id)
    except KeyError:
        return P("Identity not found", cls="text-red-400")
    crop_files = _main_mod.get_crop_files()
    tf = tgt.get("anchor_ids", []) + tgt.get("candidate_ids", [])
    nf = nbr.get("anchor_ids", []) + nbr.get("candidate_ids", [])
    if not tf or not nf:
        return P("No faces available for comparison", cls="text-slate-400")
    target_idx = max(0, min(target_idx, len(tf) - 1))
    neighbor_idx = max(0, min(neighbor_idx, len(nf) - 1))

    def _rf(entries, idx):
        e = entries[idx]
        fid = e if isinstance(e, str) else e.get("face_id", "")
        return fid, _main_mod.resolve_face_image_url(fid, crop_files)

    t_fid, t_url = _rf(tf, target_idx)
    n_fid, n_url = _rf(nf, neighbor_idx)
    t_name = ensure_utf8_display(tgt.get("name")) or f"Identity {target_id[:8]}..."
    n_name = ensure_utf8_display(nbr.get("name")) or f"Identity {neighbor_id[:8]}..."

    # Resolve photo IDs (always needed for View Photo links) and photo URLs (for photos view)
    t_photo_url = None
    n_photo_url = None
    _main_mod._build_caches()
    t_photo_id = _main_mod._face_to_photo_cache.get(t_fid, "")
    n_photo_id = _main_mod._face_to_photo_cache.get(n_fid, "")
    if view == "photos":
        if t_photo_id and _main_mod._photo_cache and t_photo_id in _main_mod._photo_cache:
            t_photo_url = storage.get_photo_url(_main_mod._photo_cache[t_photo_id].get("filename", ""))
        if n_photo_id and _main_mod._photo_cache and n_photo_id in _main_mod._photo_cache:
            n_photo_url = storage.get_photo_url(_main_mod._photo_cache[n_photo_id].get("filename", ""))

    # Determine which image URLs to show
    t_display_url = t_photo_url if view == "photos" and t_photo_url else t_url
    n_display_url = n_photo_url if view == "photos" and n_photo_url else n_url

    # Section routing for clickable names
    t_section = _section_for_state(tgt.get("state", "INBOX"))
    n_section = _section_for_state(nbr.get("state", "INBOX"))
    _filter_suffix = f"&filter={filter}" if filter else ""

    def _cn(side, cur, tot, oth):
        if tot <= 1:
            return None
        b = f"/api/identity/{target_id}/compare/{neighbor_id}"
        if side == "t":
            pu = f"{b}?target_idx={cur-1}&neighbor_idx={oth}&view={view}{_filter_suffix}"
            nu = f"{b}?target_idx={cur+1}&neighbor_idx={oth}&view={view}{_filter_suffix}"
        else:
            pu = f"{b}?target_idx={oth}&neighbor_idx={cur-1}&view={view}{_filter_suffix}"
            nu = f"{b}?target_idx={oth}&neighbor_idx={cur+1}&view={view}{_filter_suffix}"
        pb = Button("\u2190", cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded text-sm",
                    hx_get=pu, hx_target="#compare-modal-content", hx_swap="innerHTML",
                    type="button") if cur > 0 else Button(
                    "\u2190", cls="px-2 py-1 text-slate-500 opacity-30 rounded text-sm", disabled=True, type="button")
        nb = Button("\u2192", cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded text-sm",
                    hx_get=nu, hx_target="#compare-modal-content", hx_swap="innerHTML",
                    type="button") if cur < tot - 1 else Button(
                    "\u2192", cls="px-2 py-1 text-slate-500 opacity-30 rounded text-sm", disabled=True, type="button")
        return Div(pb, Span(f"{cur+1} of {tot}", cls="text-xs text-slate-400 mx-2"), nb,
                   cls="flex items-center justify-center gap-1 mt-2")

    # Face/Photo toggle
    base_url = f"/api/identity/{target_id}/compare/{neighbor_id}?target_idx={target_idx}&neighbor_idx={neighbor_idx}{_filter_suffix}"
    toggle = Div(
        Button("Faces",
               cls=f"px-3 py-1 text-xs font-medium rounded-l {'bg-amber-600 text-white' if view == 'faces' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}",
               hx_get=f"{base_url}&view=faces", hx_target="#compare-modal-content", hx_swap="innerHTML", type="button"),
        Button("Photos",
               cls=f"px-3 py-1 text-xs font-medium rounded-r {'bg-amber-600 text-white' if view == 'photos' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}",
               hx_get=f"{base_url}&view=photos", hx_target="#compare-modal-content", hx_swap="innerHTML", type="button"),
        cls="flex justify-center mb-4"
    )

    # Action buttons -- role-aware
    _role = _main_mod._get_user_role(sess)
    if _role == "contributor":
        m_btn = Button("Suggest Merge", cls="px-4 py-2 text-sm font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"/api/identity/{target_id}/suggest-merge/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML",
            **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    else:
        _merge_confirm = f"Merge {n_name} into {t_name}? All faces will be combined." if t_name and not t_name.startswith("Unidentified") and not t_name.startswith("Identity ") else "Merge these identities? This can be undone."
        m_btn = Button("Merge", cls="px-4 py-2 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
            hx_post=f"/api/identity/{target_id}/merge/{neighbor_id}", hx_target=f"#identity-{target_id}", hx_swap="outerHTML",
            hx_confirm=_merge_confirm,
            **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    ns_btn = Button("Not Same", cls="px-4 py-2 text-sm font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
        hx_post=f"/api/identity/{target_id}/reject/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML",
        **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    cl_btn = Button("Close", cls="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600 rounded",
        **{"_": "on click add .hidden to #compare-modal"}, type="button")

    img_h = "max-h-[60vh]" if view == "photos" else "max-h-[50vh]"

    # Hyperscript for click-to-zoom on face crop images in compare modal
    _zoom_script = (
        "on click toggle .compare-crop-zoomed on me "
        "then if I match .compare-crop-zoomed "
        "set my style.transform to 'scale(2)' "
        "then set my style.cursor to 'zoom-out' "
        "else "
        "set my style.transform to 'scale(1)' "
        "then set my style.cursor to 'zoom-in' "
        "end"
    )

    # Build photo containers — with face overlays when in photos view
    if view == "photos" and t_photo_url:
        t_photo_div = _compare_photo_with_overlays(t_photo_url, t_photo_id, t_fid, registry, img_h)
    else:
        t_photo_div = Div(
            Img(src=t_display_url or "", alt=t_name,
                cls=f"max-w-full {img_h} object-contain rounded cursor-zoom-in transition-transform duration-200",
                data_compare_zoom="true",
                **{"_": _zoom_script}) if t_display_url else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2 overflow-hidden")

    if view == "photos" and n_photo_url:
        n_photo_div = _compare_photo_with_overlays(n_photo_url, n_photo_id, n_fid, registry, img_h)
    else:
        n_photo_div = Div(
            Img(src=n_display_url or "", alt=n_name,
                cls=f"max-w-full {img_h} object-contain rounded cursor-zoom-in transition-transform duration-200",
                data_compare_zoom="true",
                **{"_": _zoom_script}) if n_display_url else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2 overflow-hidden")

    # View Photo links — open the full photo lightbox from compare modal
    # Pass from_compare=1 so the photo view shows a "Back to Compare" button
    t_view_photo = Button(
        "View Photo \u2192",
        cls="text-xs text-amber-400/70 hover:text-amber-400 mt-1",
        hx_get=f"/photo/{t_photo_id}/partial?face={t_fid}&from_compare=1",
        hx_target="#photo-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #photo-modal then add .hidden to #compare-modal"},
        type="button",
    ) if t_photo_id else None
    n_view_photo = Button(
        "View Photo \u2192",
        cls="text-xs text-indigo-400/70 hover:text-indigo-400 mt-1",
        hx_get=f"/photo/{n_photo_id}/partial?face={n_fid}&from_compare=1",
        hx_target="#photo-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #photo-modal then add .hidden to #compare-modal"},
        type="button",
    ) if n_photo_id else None

    return Div(
        toggle,
        Div(
            Div(
                A(t_name, href=f"/?section={t_section}&current={target_id}{_filter_suffix}",
                  cls="text-sm font-medium text-amber-400 mb-2 text-center truncate block hover:underline",
                  **{"_": "on click add .hidden to #compare-modal"}),
                t_photo_div,
                t_view_photo,
                _cn("t", target_idx, len(tf), neighbor_idx),
                cls="flex-1 min-w-0"),
            Div(Span("vs", cls="text-slate-500 text-sm font-bold"), cls="flex items-center px-4"),
            Div(
                A(n_name, href=f"/?section={n_section}&current={neighbor_id}{_filter_suffix}",
                  cls="text-sm font-medium text-indigo-400 mb-2 text-center truncate block hover:underline",
                  **{"_": "on click add .hidden to #compare-modal"}),
                n_photo_div,
                n_view_photo,
                _cn("n", neighbor_idx, len(nf), target_idx),
                cls="flex-1 min-w-0"),
            cls="flex flex-col sm:flex-row gap-4 items-center sm:items-start"),
        Div(m_btn, ns_btn, cl_btn,
            cls="flex flex-wrap items-center justify-center gap-3 mt-6 pt-4 border-t border-slate-700"))
