"""
Estimate routes extracted from app/main.py.

All /tools/estimate/* and /api/estimate/* routes plus estimate-exclusive helpers.
"""

import logging
import os
from datetime import datetime, timezone

from fasthtml.common import *
from starlette.datastructures import UploadFile

from core import storage

# Import route decorator only
from app.main import rt

# All other main.py functions accessed via module reference
import app.main as _main_mod

logger = logging.getLogger(__name__)


def _tools_nav_bar(active_tool=None):
    """Lazy import of tools_nav_bar to avoid circular imports."""
    from app.tools_routes import tools_nav_bar

    return tools_nav_bar(active_tool=active_tool)


@rt("/tools/estimate")
def get(photo: str = "", sess=None):
    """
    Year Estimation Tool — estimate when a photo was taken.

    Uses apparent ages + known birth years + scene analysis.
    Public page, no auth required.
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True

    _main_mod._build_caches()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    # Build photo selector from archive
    photo_options = []
    photo_reg = _main_mod.load_photo_registry()
    labels = _main_mod._load_date_labels()

    # Get all photos, sorted by those with most identified faces first
    all_photo_ids = list(_main_mod._photo_cache.keys()) if _main_mod._photo_cache else []

    # Estimation results
    estimate_result = None
    selected_photo = None
    if photo and photo in (_main_mod._photo_cache or {}):
        from core.year_estimation import estimate_photo_year

        selected_photo = _main_mod._photo_cache[photo]
        estimate_result = estimate_photo_year(
            photo_id=photo,
            date_labels=labels,
            photo_cache=_main_mod._photo_cache,
            identity_registry=registry,
            birth_year_fn=_main_mod._get_birth_year,
            face_to_identity_fn=_main_mod.get_identity_for_face,
        )

    # Build the page
    nav_links = _main_mod._public_nav_links(active="estimate", user=user)

    # Photo grid selector — paginated (24 per page via query param)
    page_size = 24
    page_num = 0  # Will be overridden by HTMX partial endpoint
    photo_grid_items = []
    visible_photos = all_photo_ids[:page_size]
    has_more = len(all_photo_ids) > page_size
    for pid in visible_photos:
        pm = _main_mod._photo_cache.get(pid, {})
        if not pm:
            continue
        photo_path = pm.get("path") or pm.get("filename", "")
        if not photo_path:
            continue
        purl = storage.get_photo_url(photo_path)
        face_count = len(pm.get("faces", []))
        is_selected = pid == photo

        photo_grid_items.append(
            A(
                Img(
                    src=purl,
                    alt="Archive photo",
                    cls=f"w-full h-20 object-cover rounded-lg {'ring-2 ring-amber-400' if is_selected else 'hover:ring-2 hover:ring-indigo-400'} transition-all",
                ),
                Span(
                    f"{face_count} face{'s' if face_count != 1 else ''}",
                    cls="text-[10px] text-slate-500 block text-center mt-0.5",
                ),
                href=f"/estimate?photo={pid}",
                cls="block",
            )
        )

    # Result display
    result_section = None
    if estimate_result and selected_photo:
        photo_path = selected_photo.get("path") or selected_photo.get("filename", "")
        photo_url_val = storage.get_photo_url(photo_path)

        # Per-face evidence cards
        face_cards = []
        for ev in estimate_result.get("face_evidence", []):
            if not ev.get("apparent_age"):
                continue
            person_name = ev.get("person_name") or "Unknown person"
            birth_text = f"born ~{ev['birth_year']}" if ev.get("birth_year") else "birth year unknown"
            year_text = f"c. {ev['estimated_year']}" if ev.get("estimated_year") else "—"
            source_badge = ""
            if ev.get("birth_year_source") == "confirmed":
                source_badge = Span(
                    "verified", cls="text-[10px] bg-emerald-900/50 text-emerald-300 px-1.5 py-0.5 rounded-full ml-2"
                )
            elif ev.get("birth_year_source") == "ml_inferred":
                source_badge = Span(
                    "estimated", cls="text-[10px] bg-indigo-900/50 text-indigo-300 px-1.5 py-0.5 rounded-full ml-2"
                )

            face_cards.append(
                Div(
                    Div(
                        Span(person_name, cls="text-sm font-semibold text-white"),
                        source_badge,
                        cls="flex items-center",
                    ),
                    P(f"Appears ~{ev['apparent_age']} years old ({birth_text})", cls="text-xs text-slate-400 mt-0.5"),
                    P(year_text, cls="text-lg font-bold text-amber-400 mt-1") if ev.get("estimated_year") else None,
                    cls="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
                )
            )

        # Scene evidence
        scene_card = None
        scene = estimate_result.get("scene_evidence")
        if scene and scene.get("clues"):
            scene_card = Div(
                Div(
                    Span("Scene Analysis", cls="text-sm font-semibold text-white"),
                    cls="flex items-center",
                ),
                P(", ".join(scene["clues"][:4]), cls="text-xs text-slate-400 mt-0.5"),
                P(f"Suggests: {scene['scene_estimate']}", cls="text-sm text-slate-300 mt-1")
                if scene.get("scene_estimate")
                else None,
                cls="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50",
            )

        # Confidence styling
        conf = estimate_result.get("confidence", "low")
        conf_color = {"high": "text-emerald-400", "medium": "text-amber-400", "low": "text-slate-400"}.get(
            conf, "text-slate-400"
        )
        conf_label = {"high": "High confidence", "medium": "Moderate confidence", "low": "Low confidence"}.get(conf, "")
        margin = estimate_result.get("margin", 10)
        method_label = (
            "Based on facial age analysis"
            if estimate_result.get("method") == "facial_age_aggregation"
            else "Based on scene analysis"
        )

        result_section = Div(
            # Photo with estimate badge
            Div(
                Img(src=photo_url_val, alt="Selected photo", cls="w-full max-w-lg mx-auto rounded-xl shadow-lg"),
                cls="mb-6",
            ),
            # Main estimate
            Div(
                H2(
                    f"Estimated: c. {estimate_result['year']}",
                    cls="text-3xl font-serif font-bold text-white text-center",
                ),
                P(f"+/- {margin} years", cls="text-lg text-slate-400 text-center"),
                Div(
                    Span(conf_label, cls=f"text-sm font-medium {conf_color}"),
                    Span(" · ", cls="text-slate-600"),
                    Span(method_label, cls="text-xs text-slate-500"),
                    cls="flex items-center justify-center gap-1 mt-2",
                ),
                cls="text-center mb-8",
            ),
            # How we estimated this
            H3("How we estimated this", cls="text-lg font-serif font-semibold text-white mb-4"),
            Div(*face_cards, scene_card, cls="flex flex-col gap-3 mb-6")
            if face_cards or scene_card
            else P(
                "Based on visual analysis. Identify more people to improve this estimate.",
                cls="text-sm text-slate-500 italic",
            ),
            # Photo Detective evidence from Gemini (PRD-022)
            _main_mod._detective_evidence_section(labels.get(photo, {})),
            _main_mod._progressive_refinement_badge(labels.get(photo, {})),
            # CTAs
            Div(
                _main_mod.share_button(
                    url=f"/tools/estimate?photo={photo}",
                    style="button",
                    label="Share Estimate",
                    title=f"This photo was taken c. {estimate_result['year']}",
                    text="AI-powered year estimation from historical photo analysis",
                ),
                A(
                    "View Photo Page",
                    href=f"/photo/{photo}",
                    cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded-lg transition-colors",
                ),
                A(
                    "Try Another",
                    href="/tools/estimate",
                    cls="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition-colors border border-slate-700",
                ),
                cls="flex flex-wrap justify-center gap-3 mt-6",
            ),
            cls="bg-slate-800/30 rounded-xl p-6 border border-slate-700/30 mt-8",
        )
    elif photo and not estimate_result:
        # Photo selected but no estimate possible
        photo_path = (selected_photo or {}).get("path") or (selected_photo or {}).get("filename", "")
        photo_url_val = storage.get_photo_url(photo_path) if photo_path else ""
        result_section = Div(
            Img(src=photo_url_val, alt="Selected photo", cls="w-full max-w-lg mx-auto rounded-xl shadow-lg mb-4")
            if photo_url_val
            else None,
            P("Not enough data to estimate the year for this photo.", cls="text-slate-400 text-center"),
            P(
                "Photos with identified people and known birth years produce the best estimates.",
                cls="text-xs text-slate-500 text-center mt-2",
            ),
            A(
                "Try another photo",
                href="/tools/estimate",
                cls="text-indigo-400 hover:text-indigo-300 text-sm text-center block mt-4",
            ),
            cls="bg-slate-800/30 rounded-xl p-6 border border-slate-700/30 mt-8 text-center",
        )

    # Tab links: Compare Faces | Estimate Year
    og = _main_mod.og_tags(
        title="When Was This Photo Taken? — Date Estimator",
        description="Our AI estimates the year a photo was taken using facial age analysis and historical clues.",
        canonical_url=f"{_main_mod.SITE_URL}/tools/estimate",
    )

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator,
        .htmx-request.htmx-indicator { display: inline; }
        div.htmx-request.htmx-indicator,
        .htmx-request div.htmx-indicator { display: block; }
        form.htmx-request button[type="submit"] {
            opacity: 0.5;
            pointer-events: none;
        }
    """)

    return (
        Title("When Was This Photo Taken? — Date Estimator"),
        *og,
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-lg font-serif font-bold text-white"), href="/"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            _tools_nav_bar(active_tool="estimate"),
            Section(
                Div(
                    H1(
                        "When Was This Photo Taken?",
                        cls="text-2xl sm:text-3xl font-serif font-bold text-white text-center mb-2",
                    ),
                    P(
                        "Upload a photo or select one from the archive. Our AI estimates the year using facial age analysis and historical clues.",
                        cls="text-slate-400 text-sm text-center mb-8 max-w-lg mx-auto",
                    ),
                    # Upload zone
                    Div(
                        Form(
                            Div(
                                Div(
                                    NotStr(
                                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-500 mb-2 mx-auto" id="estimate-upload-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>'
                                    ),
                                    Img(
                                        id="estimate-preview",
                                        cls="hidden max-h-24 rounded-lg mx-auto mb-2 border border-slate-600",
                                        alt="Selected photo",
                                    ),
                                    P(
                                        "Upload a photo to estimate its date",
                                        id="estimate-upload-text",
                                        cls="text-slate-400 text-sm mb-1",
                                    ),
                                    P("JPG, PNG up to 10 MB", cls="text-slate-600 text-xs"),
                                    Input(
                                        type="file",
                                        name="photo",
                                        accept="image/jpeg,image/png",
                                        cls="absolute inset-0 w-full h-full opacity-0 cursor-pointer",
                                        onchange="var f=this.files[0];if(!f)return;var err=document.getElementById('estimate-upload-error');if(err)err.remove();if(!['image/jpeg','image/png'].includes(f.type)){var e=document.createElement('p');e.id='estimate-upload-error';e.className='text-red-400 text-sm text-center mt-2';e.textContent='Please select a JPG or PNG image.';this.closest('form').parentNode.insertBefore(e,this.closest('form').nextSibling);this.value='';return}if(f.size>10*1024*1024){var e=document.createElement('p');e.id='estimate-upload-error';e.className='text-red-400 text-sm text-center mt-2';e.textContent='File is too large (max 10 MB).';this.closest('form').parentNode.insertBefore(e,this.closest('form').nextSibling);this.value='';return}var preview=document.getElementById('estimate-preview');var icon=document.getElementById('estimate-upload-icon');var txt=document.getElementById('estimate-upload-text');if(preview){var r=new FileReader();r.onload=function(e){preview.src=e.target.result;preview.classList.remove('hidden');if(icon)icon.classList.add('hidden');if(txt)txt.textContent='Photo selected - analyzing...'};r.readAsDataURL(f)}this.closest('form').requestSubmit()",
                                        data_testid="estimate-upload-input",
                                    ),
                                    cls="relative border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-xl p-6 transition-colors cursor-pointer",
                                ),
                                cls="mb-3",
                            ),
                            action="/api/estimate/upload",
                            method="post",
                            enctype="multipart/form-data",
                            hx_post="/api/estimate/upload",
                            hx_target="#estimate-upload-result",
                            hx_swap="innerHTML show:#estimate-upload-result:top",
                            hx_indicator="#estimate-upload-spinner",
                            data_testid="estimate-upload-form",
                            **{"hx-on::after-request": "if(event.detail.successful) this.reset()"},
                        ),
                        Div(
                            id="estimate-upload-spinner",
                            cls="htmx-indicator text-center py-3",
                            children=[
                                Div(
                                    Svg(
                                        viewBox="0 0 24 24",
                                        fill="none",
                                        cls="animate-spin h-5 w-5 text-amber-400 inline-block mr-2",
                                        children=[
                                            NotStr(
                                                '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" class="opacity-75"></path>'
                                            )
                                        ],
                                    ),
                                    Span("Analyzing your photo for date clues...", cls="text-slate-400 text-sm"),
                                    cls="flex items-center justify-center",
                                ),
                                P("This may take a moment for group photos.", cls="text-slate-500 text-xs mt-1"),
                            ],
                        ),
                        Div(
                            id="estimate-upload-result",
                            **{
                                "hx-on::after-settle": "if(this.children.length>0)this.scrollIntoView({behavior:'smooth'})"
                            },
                        ),
                        cls="bg-slate-800/50 rounded-2xl p-6 max-w-md mx-auto mb-8",
                        data_testid="estimate-upload-area",
                    )
                    if not photo
                    else None,
                    # Results (if photo selected)
                    result_section,
                    # Photo selector with pagination
                    Div(
                        H3(
                            "Select a Photo" if not photo else "Try Another Photo",
                            cls="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3",
                        ),
                        Div(
                            *photo_grid_items,
                            cls="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2",
                            id="estimate-photo-grid",
                        ),
                        Div(
                            Button(
                                "Load More Photos",
                                hx_get="/api/estimate/photos?page=1",
                                hx_target="#estimate-photo-grid",
                                hx_swap="beforeend",
                                hx_swap_oob="true",
                                cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm font-medium rounded-lg transition-colors",
                                id="load-more-estimate",
                            ),
                            cls="flex justify-center mt-4",
                        )
                        if has_more
                        else None,
                        cls="mt-8",
                    )
                    if photo_grid_items
                    else None,
                    P(
                        "The more people you identify, the better the estimate.",
                        cls="text-xs text-slate-500 text-center mt-6",
                    ),
                    cls="max-w-4xl mx-auto pt-8 pb-16 px-6",
                ),
            ),
            cls="min-h-screen bg-slate-900 text-white",
        ),
        _main_mod._share_script(),
    )


@rt("/api/estimate/photos")
def get(page: int = 0, sess=None):
    """Load more photos for the estimate grid (HTMX partial)."""
    _main_mod._build_caches()
    page_size = 24
    all_photo_ids = list(_main_mod._photo_cache.keys()) if _main_mod._photo_cache else []
    start = page * page_size
    end = start + page_size
    visible_photos = all_photo_ids[start:end]
    has_more = end < len(all_photo_ids)

    items = []
    for pid in visible_photos:
        pm = _main_mod._photo_cache.get(pid, {})
        if not pm:
            continue
        photo_path = pm.get("path") or pm.get("filename", "")
        if not photo_path:
            continue
        purl = storage.get_photo_url(photo_path)
        face_count = len(pm.get("faces", []))
        items.append(
            A(
                Img(
                    src=purl,
                    alt="Archive photo",
                    cls="w-full h-20 object-cover rounded-lg hover:ring-2 hover:ring-indigo-400 transition-all",
                ),
                Span(
                    f"{face_count} face{'s' if face_count != 1 else ''}",
                    cls="text-[10px] text-slate-500 block text-center mt-0.5",
                ),
                href=f"/estimate?photo={pid}",
                cls="block",
            )
        )

    # Replace the Load More button with an updated one (or remove if no more)
    if has_more:
        items.append(
            Div(
                Button(
                    "Load More Photos",
                    hx_get=f"/api/estimate/photos?page={page + 1}",
                    hx_target="#estimate-photo-grid",
                    hx_swap="beforeend",
                    hx_swap_oob="true",
                    cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm font-medium rounded-lg transition-colors",
                    id="load-more-estimate",
                ),
                cls="flex justify-center mt-4",
                id="load-more-container",
                hx_swap_oob="true",
            )
        )

    return tuple(items)


def _call_gemini_date_estimate(
    image_bytes: bytes,
    suffix: str,
    api_key: str,
    photo_id: str | None = None,
    gedcom_context: str | None = None,
    call_type: str = "date_estimation",
    trigger: str = "interactive_upload",
    photo_metadata: dict | None = None,
) -> dict | None:
    """Call Gemini Vision API for date/location estimation using the enriched prompt.

    Uses build_extraction_prompt() with the "quick" preset (date + location + text).
    Optionally includes GEDCOM genealogical context for identified faces.
    Logs every call to Supabase gemini_api_calls for cost tracking.

    Returns parsed dict with date_estimation + location fields, or None on failure.
    """
    import time as _time

    from google import genai
    from google.genai import types
    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from rhodesli_ml.gemini_extraction import build_extraction_prompt
    import json as _json

    # Build enriched prompt (quick preset: date + location + text_signage)
    prompt_text = build_extraction_prompt(
        preset="quick",
        gedcom_context=gedcom_context,
        photo_metadata=photo_metadata,
    )
    enrichment_level = "gedcom" if gedcom_context else "none"
    gedcom_variant = "first_order" if gedcom_context else "none"

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 180_000 if gedcom_context else 30_000},
    )

    mime_type = "image/png" if suffix.lower() == ".png" else "image/jpeg"

    max_retries = 2
    retry_delays = [5, 15]  # seconds
    start_time = _time.time()
    status = "success"
    error_msg = None
    parsed = None

    try:
        for attempt in range(1 + max_retries):
            try:
                if attempt > 0:
                    delay = retry_delays[attempt - 1]
                    logger.info(f"[estimate] Retry {attempt}/{max_retries} after {delay}s for photo {photo_id}")
                    _time.sleep(delay)
                    start_time = _time.time()

                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[
                        types.Content(
                            parts=[
                                types.Part.from_text(text=prompt_text),
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )

                latency_ms = int((_time.time() - start_time) * 1000)

                text = response.text
                if not text:
                    status = "error"
                    error_msg = "Empty response"
                    return None

                parsed = _json.loads(text)

                # Gemini sometimes wraps response in an array — unwrap it
                if isinstance(parsed, list) and len(parsed) > 0:
                    parsed = parsed[0]

                # Extract date_estimation (may be nested or top-level)
                date_est = parsed.get("date_estimation", parsed)

                # Basic validation
                decade = date_est.get("estimated_decade")
                if not isinstance(decade, int) or decade < 1800 or decade > 2030:
                    status = "error"
                    error_msg = f"Invalid decade: {decade}"
                    return None

                # Merge location into date_est for backward-compatible return
                if "location" in parsed and "location" not in date_est:
                    date_est["location"] = parsed["location"]

                return date_est

            except Exception as e:
                latency_ms = int((_time.time() - start_time) * 1000)
                error_msg = str(e)
                # Retry on timeout/server errors (504, 503, DEADLINE_EXCEEDED)
                is_retryable = any(s in error_msg for s in ["504", "503", "DEADLINE_EXCEEDED", "timeout", "Timeout"])
                if is_retryable and attempt < max_retries:
                    logger.warning(f"[estimate] Retryable Gemini error (attempt {attempt + 1}): {e}")
                    continue
                status = "error"
                logger.warning(f"[estimate] Gemini API error (final): {e}")
                return None

    finally:
        # Log every call to Supabase (AD-152) — fire-and-forget
        if photo_id:
            try:
                from app.supabase_data import log_gemini_call

                pricing = get_model_pricing(GEMINI_MODEL)
                # Estimate tokens from prompt length (rough: ~4 chars/token)
                prompt_tokens = len(prompt_text) // 4
                # Response tokens estimated from response size
                resp_text = _json.dumps(parsed) if parsed else ""
                completion_tokens = len(resp_text) // 4
                total_tokens = prompt_tokens + completion_tokens
                cost_usd = (
                    prompt_tokens * pricing.get("input", 2.0) / 1_000_000
                    + completion_tokens * pricing.get("output", 12.0) / 1_000_000
                )

                # Build response summary for analysis
                response_summary = None
                if parsed:
                    date_est = parsed.get("date_estimation", parsed)
                    loc = parsed.get("location", {})
                    response_summary = {
                        "estimated_decade": date_est.get("estimated_decade"),
                        "best_year_estimate": date_est.get("best_year_estimate"),
                        "confidence": date_est.get("confidence"),
                        "location_place": loc.get("place") if isinstance(loc, dict) else None,
                        "location_confidence": loc.get("confidence") if isinstance(loc, dict) else None,
                    }

                log_gemini_call(
                    photo_id=photo_id,
                    model_used=GEMINI_MODEL,
                    call_type=call_type,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=round(cost_usd, 6),
                    latency_ms=latency_ms,
                    status=status,
                    error_message=error_msg,
                    gemini_config={
                        "enrichment_level": enrichment_level,
                        "prompt_version": "v3_enriched",
                        "gedcom_variant": gedcom_variant,
                        "temperature": 0.1,
                        "trigger": trigger,
                        "model_generation": "3.1",
                        "model_variant": "pro-preview",
                        "preset": "quick",
                    },
                    response_summary=response_summary,
                    prompt_text=prompt_text,
                    full_response=parsed if parsed else None,
                    gedcom_context=gedcom_context,
                )
            except Exception as log_err:
                logger.warning(f"[estimate] Failed to log Gemini call: {log_err}")


@rt("/api/estimate/upload")
async def post(photo: UploadFile = None, sess=None):
    """Upload a photo for date estimation.

    Graceful degradation matrix:
    | ML Available | Gemini Key | Behavior                          |
    |-------------|-----------|-----------------------------------|
    | Yes         | Yes       | Full: faces + AI date + evidence  |
    | Yes         | No        | Partial: faces detected            |
    | No          | Yes       | Partial: AI date only              |
    | No          | No        | Minimal: photo saved, honest msg   |
    """
    if not photo:
        return Div(P("No photo uploaded.", cls="text-amber-500 text-center py-4"))

    from pathlib import Path as _Path

    content = await photo.read()
    original_filename = photo.filename or "upload.jpg"
    suffix = _Path(original_filename).suffix.lower() or ".jpg"

    # Server-side validation
    if suffix not in (".jpg", ".jpeg", ".png"):
        return Div(P("Please upload a JPG or PNG image.", cls="text-red-400 text-center py-4"))
    if len(content) > 10 * 1024 * 1024:
        return Div(P("File is too large (max 10 MB).", cls="text-red-400 text-center py-4"))

    # Save the upload
    import uuid as _uuid

    upload_id = _uuid.uuid4().hex[:12]
    image_key = f"uploads/estimate/{upload_id}{suffix}"

    from core.storage import can_write_r2, upload_bytes_to_r2, get_upload_url
    import mimetypes

    content_type = mimetypes.guess_type(original_filename)[0] or "image/jpeg"

    if can_write_r2():
        upload_bytes_to_r2(image_key, content, content_type=content_type)
    else:
        upload_dir = _Path("uploads/estimate")
        upload_dir.mkdir(parents=True, exist_ok=True)
        (_Path("uploads/estimate") / f"{upload_id}{suffix}").write_bytes(content)

    # UX-053: Build photo preview URL for results display
    photo_preview_url = get_upload_url(image_key)

    # Check for existing date labels matching the filename
    labels = _main_mod._load_date_labels()
    fname_stem = _Path(original_filename).stem
    matched_label = None
    for key, label in (labels or {}).items():
        if fname_stem in key:
            matched_label = label
            break

    if matched_label:
        year = matched_label.get("estimated_year", "Unknown")
        conf_range = matched_label.get("confidence_range", [])
        scene = matched_label.get("scene_analysis", {})
        clues = scene.get("photography_style", []) + scene.get("clothing_and_fashion", [])
        clues_text = ", ".join(clues[:4]) if clues else "Based on visual analysis"

        return Div(
            # UX-053: Photo preview
            Div(
                Img(
                    src=photo_preview_url,
                    alt="Uploaded photo",
                    cls="max-h-48 rounded-lg mx-auto border border-slate-600/50 shadow-lg",
                    data_testid="estimate-photo-preview",
                ),
                cls="flex justify-center mb-4",
            ),
            Div(
                Span("~", cls="text-2xl text-amber-400 font-serif"),
                cls="flex justify-center mb-2",
            ),
            P(f"Estimated: c. {year}", cls="text-xl font-serif font-bold text-white text-center"),
            P(
                f"Range: {conf_range[0]}–{conf_range[1]}" if len(conf_range) >= 2 else "",
                cls="text-sm text-slate-400 text-center mt-1",
            ),
            P(clues_text, cls="text-xs text-slate-500 text-center mt-2 italic"),
            # UX-056: CTAs
            Div(
                Button(
                    "Try Another Photo",
                    onclick="var form=document.querySelector('[data-testid=\"estimate-upload-form\"]');if(form){form.reset();var p=document.getElementById('estimate-preview');if(p){p.classList.add('hidden');p.src=''}var i=document.getElementById('estimate-upload-icon');if(i)i.classList.remove('hidden');var t=document.getElementById('estimate-upload-text');if(t)t.textContent='Upload a photo to estimate its date';document.getElementById('estimate-upload-result').innerHTML=''}",
                    cls="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors cursor-pointer",
                    data_testid="estimate-try-another",
                ),
                A(
                    "Browse the Archive",
                    href="/photos",
                    cls="px-4 py-2 text-sm border border-slate-600 text-slate-400 rounded-lg hover:bg-slate-700/50 transition-colors",
                ),
                cls="flex flex-wrap justify-center gap-3 mt-6 pt-4 border-t border-slate-700/50",
                data_testid="estimate-ctas",
            ),
            cls="py-4",
            data_testid="estimate-upload-result",
        )

    # --- Real-time processing: face detection + CORAL model + Gemini ---
    parts = []

    # 1. Face detection (if InsightFace available)
    face_count = 0
    has_insightface = False
    try:
        import cv2  # noqa: F811
        from insightface.app import FaceAnalysis  # noqa: F401
        from core.ingest_inbox import extract_faces_hybrid

        has_insightface = True
    except ImportError:
        pass

    if has_insightface:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = _Path(tmp.name)
        try:
            # Resize to 640px for ML — InsightFace det_size=(640,640) (AD-110)
            ml_img = cv2.imread(str(tmp_path))
            if ml_img is not None:
                mh, mw = ml_img.shape[:2]
                _ML_MAX = 640
                if max(mh, mw) > _ML_MAX:
                    sc = _ML_MAX / max(mh, mw)
                    ml_img = cv2.resize(ml_img, (int(mw * sc), int(mh * sc)), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(str(tmp_path), ml_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            # Use hybrid detection (AD-114) for faster response
            faces, img_w, img_h = extract_faces_hybrid(tmp_path)
            face_count = len(faces)
            if face_count > 0:
                parts.append(
                    Div(
                        P(
                            f"{face_count} {'face' if face_count == 1 else 'faces'} detected",
                            cls="text-sm text-emerald-400 text-center",
                        ),
                        cls="mb-3",
                        data_testid="estimate-face-count",
                    )
                )
        except Exception:
            pass  # Face detection failure should not block date estimation
        finally:
            tmp_path.unlink(missing_ok=True)

    # 2. CORAL date estimation model (local ONNX, instant, free — AD-129)
    coral_result = None
    try:
        from rhodesli_ml.date_inference.inference import predict_date
        from PIL import Image as _PILImage
        import io as _io

        pil_img = _PILImage.open(_io.BytesIO(content)).convert("RGB")
        import numpy as _np

        rgb_array = _np.array(pil_img)
        coral_result = predict_date(rgb_array)
    except Exception as e:
        print(f"[estimate] CORAL model error: {e}")

    if coral_result:
        decade = coral_result["predicted_decade"]
        confidence = coral_result["confidence"]
        expected_year = coral_result["expected_year"]
        decade_probs = coral_result["decade_probabilities"]

        # Confidence tier for display
        if confidence >= 0.5:
            conf_label = "High confidence"
            conf_color = "text-emerald-400"
        elif confidence >= 0.3:
            conf_label = "Moderate confidence"
            conf_color = "text-amber-400"
        else:
            conf_label = "Low confidence"
            conf_color = "text-slate-400"

        # Build probability bar chart
        prob_bars = []
        for dec_str, prob in sorted(decade_probs.items()):
            dec = int(dec_str)
            pct = prob * 100
            bar_width = max(1, pct)  # Minimum 1% width for visibility
            is_predicted = dec == decade
            bar_color = "bg-amber-400" if is_predicted else "bg-slate-600"
            text_color = "text-amber-400 font-semibold" if is_predicted else "text-slate-500"
            prob_bars.append(
                Div(
                    Span(f"{dec}s", cls=f"text-[10px] {text_color} w-10 text-right mr-2 shrink-0"),
                    Div(
                        Div(cls=f"{bar_color} h-full rounded-r", style=f"width:{bar_width}%"),
                        cls="flex-1 bg-slate-800 rounded h-3",
                    ),
                    Span(f"{pct:.0f}%", cls=f"text-[10px] {text_color} w-8 ml-2 shrink-0"),
                    cls="flex items-center",
                )
            )

        parts.append(
            Div(
                P(
                    f"Estimated era: circa {decade}s",
                    cls="text-xl font-serif font-bold text-white text-center",
                    data_testid="estimate-coral-decade",
                ),
                P(f"Expected year: ~{expected_year}", cls="text-sm text-slate-400 text-center mt-1"),
                Div(
                    Span(conf_label, cls=f"text-xs font-medium {conf_color}"),
                    Span(" · ", cls="text-slate-600"),
                    Span("CORAL ordinal regression model", cls="text-xs text-slate-500"),
                    cls="flex items-center justify-center gap-1 mt-2",
                ),
                # Decade probability distribution
                Div(
                    P("Decade probability distribution", cls="text-xs text-slate-500 uppercase tracking-wider mb-2"),
                    Div(*prob_bars, cls="flex flex-col gap-1"),
                    cls="mt-4 bg-slate-800/30 rounded-lg p-3 border border-slate-700/30",
                ),
                cls="py-3",
                data_testid="estimate-coral-result",
            )
        )

    # 3. Gemini date estimation (if API key available — supplementary, richer evidence)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_result = None
    if gemini_key:
        try:
            gemini_result = _call_gemini_date_estimate(
                content,
                suffix,
                gemini_key,
                photo_id=f"upload_{upload_id}",
                trigger="interactive_upload",
            )
        except Exception as e:
            logger.warning(f"[estimate] Gemini API error: {e}")

    if gemini_result:
        year = gemini_result.get("best_year_estimate") or gemini_result.get("estimated_decade", "Unknown")
        prob_range = gemini_result.get("probable_range", [])
        confidence = gemini_result.get("confidence", "unknown")
        reasoning = gemini_result.get("reasoning_summary", "")

        # Collect evidence clues
        evidence = gemini_result.get("evidence", {})
        clues = []
        for category in ("print_format", "fashion", "environment", "technology"):
            for cue in evidence.get(category, []):
                if isinstance(cue, dict):
                    clues.append(cue.get("cue", ""))
        clues_text = "; ".join(clues[:4]) if clues else reasoning[:120] if reasoning else "Based on AI analysis"

        # Location from enriched prompt (if available)
        location_info = gemini_result.get("location", {})
        location_place = location_info.get("place") if isinstance(location_info, dict) else None

        # If we already have CORAL result, show Gemini as supplementary
        heading = "Detailed AI Analysis" if coral_result else "AI Date Estimate"
        parts.append(
            Div(
                Div(
                    Span("~", cls="text-2xl text-amber-400 font-serif") if not coral_result else None,
                    cls="flex justify-center mb-2" if not coral_result else "hidden",
                ),
                P(
                    heading if coral_result else f"Estimated: c. {year}",
                    cls=f"text-{'sm text-slate-400 font-semibold' if coral_result else 'xl font-serif font-bold text-white'} text-center",
                ),
                P(f"Gemini suggests c. {year}" if coral_result else "", cls="text-sm text-slate-400 text-center mt-1")
                if coral_result
                else None,
                P(
                    f"Range: {prob_range[0]}–{prob_range[1]}" if len(prob_range) >= 2 else "",
                    cls="text-sm text-slate-400 text-center mt-1",
                )
                if not coral_result
                else None,
                P(
                    f"Location: {location_place}",
                    cls="text-sm text-indigo-400 text-center mt-1",
                    data_testid="estimate-gemini-location",
                )
                if location_place
                else None,
                P(f"Confidence: {confidence}", cls="text-xs text-slate-500 text-center mt-1"),
                P(clues_text, cls="text-xs text-slate-500 text-center mt-2 italic max-w-md mx-auto"),
                cls="py-3 mt-3 border-t border-slate-700/30" if coral_result else "py-3",
                data_testid="estimate-gemini-result",
            )
        )
    elif not coral_result and not has_insightface:
        # No CORAL + no Gemini + no InsightFace = honest minimal message
        parts.append(
            Div(
                Div(
                    Span("?", cls="text-2xl text-slate-500"),
                    cls="flex justify-center mb-2",
                ),
                P("Photo saved!", cls="text-lg font-semibold text-white text-center"),
                P(
                    "Date estimation is being configured. Check back soon.",
                    cls="text-sm text-slate-400 text-center mt-1",
                ),
                P(f"Upload ID: {upload_id}", cls="text-xs text-slate-500 text-center mt-3 font-mono"),
                cls="py-4",
            )
        )
    elif not coral_result:
        # No CORAL + no Gemini but has InsightFace = faces only
        parts.append(
            Div(
                P("Face detection complete — date estimation model loading.", cls="text-sm text-slate-400 text-center"),
                cls="py-2",
            )
        )

    if not parts:
        parts.append(P("Photo saved.", cls="text-sm text-slate-400 text-center py-4"))

    # UX-053: Photo preview at the top of results
    photo_preview = Div(
        Img(
            src=photo_preview_url,
            alt="Uploaded photo",
            cls="max-h-48 rounded-lg mx-auto border border-slate-600/50 shadow-lg",
            data_testid="estimate-photo-preview",
        ),
        cls="flex justify-center mb-4",
    )

    # UX-056: CTAs after estimate results
    cta_section = Div(
        Button(
            "Try Another Photo",
            onclick="var form=document.querySelector('[data-testid=\"estimate-upload-form\"]');if(form){form.reset();var p=document.getElementById('estimate-preview');if(p){p.classList.add('hidden');p.src=''}var i=document.getElementById('estimate-upload-icon');if(i)i.classList.remove('hidden');var t=document.getElementById('estimate-upload-text');if(t)t.textContent='Upload a photo to estimate its date';document.getElementById('estimate-upload-result').innerHTML=''}",
            cls="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors cursor-pointer",
            data_testid="estimate-try-another",
        ),
        Button(
            "Share Estimate",
            onclick="if(navigator.share){navigator.share({title:'Photo Date Estimate',text:'Check out this AI-powered date estimate!',url:window.location.href}).catch(()=>{})}else{navigator.clipboard.writeText(window.location.href).then(()=>{this.textContent='Link copied!';setTimeout(()=>{this.textContent='Share Estimate'},2000)})}",
            cls="px-4 py-2 text-sm border border-indigo-500/50 text-indigo-400 rounded-lg hover:bg-indigo-500/10 transition-colors cursor-pointer",
            data_testid="estimate-share",
        ),
        A(
            "Browse the Archive",
            href="/photos",
            cls="px-4 py-2 text-sm border border-slate-600 text-slate-400 rounded-lg hover:bg-slate-700/50 transition-colors",
        ),
        cls="flex flex-wrap justify-center gap-3 mt-6 pt-4 border-t border-slate-700/50",
        data_testid="estimate-ctas",
    )

    return Div(photo_preview, *parts, cta_section, cls="py-4", data_testid="estimate-upload-result")


# =============================================================================
# ADMIN RE-ANALYZE ENDPOINT
# =============================================================================


def _load_photo_image_bytes(photo_id: str) -> tuple[bytes | None, str]:
    """Load photo image bytes for a given photo_id.

    Returns (image_bytes, suffix) or (None, "") if photo not found.
    Works in both R2 and local modes.
    """
    import urllib.request

    _main_mod._build_caches()
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return None, ""

    filename = photo.get("filename", "")
    suffix = Path(filename).suffix.lower() or ".jpg"

    if storage.is_r2_mode():
        url = storage.get_photo_url(filename)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Rhodesli/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read(), suffix
        except Exception as e:
            logger.warning(f"Failed to fetch photo from R2: {e}")
            return None, ""
    else:
        local_path = Path("raw_photos") / Path(filename).name
        if local_path.exists():
            return local_path.read_bytes(), suffix
        return None, ""


def _build_gedcom_context_for_photo(photo_id: str, visible_text: str | None = None) -> str | None:
    """Build GEDCOM context string for identified faces in a photo.

    Args:
        photo_id: Photo ID to build context for.
        visible_text: Text visible in photo (signage, storefronts) for
            business owner GEDCOM lookup (AD-210).

    Returns context string or None if no GEDCOM data available.
    """
    _main_mod._build_caches()
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        logger.info(f"GEDCOM context: photo {photo_id} not found")
        return None

    registry = _main_mod.load_registry()
    # _photo_cache stores faces as list of dicts with "face_id" key,
    # not as flat "face_ids" list (that's the photo_index.json format).
    faces_list = photo.get("faces", [])
    face_ids = [f["face_id"] for f in faces_list if "face_id" in f]
    if not face_ids:
        # Fallback to flat face_ids if present (photo_index.json format)
        face_ids = photo.get("face_ids", [])
    if not face_ids:
        logger.info(f"GEDCOM context: no face_ids for photo {photo_id}")
        return None

    # Get GEDCOM face links from Supabase
    gedcom_links = _main_mod._load_gedcom_face_links()
    if not gedcom_links:
        logger.info("GEDCOM context: no gedcom links loaded")
        return None

    # Check if any identified faces have GEDCOM links
    has_linked_faces = False
    for face_id in face_ids:
        identity = _main_mod.get_identity_for_face(registry, face_id)
        iid = identity.get("identity_id") if identity else None
        linked = iid in gedcom_links if iid else False
        logger.info(f"GEDCOM context: face {face_id} -> identity {iid} linked={linked}")
        if linked:
            has_linked_faces = True
            break

    if not has_linked_faces:
        logger.info(f"GEDCOM context: no linked faces found for photo {photo_id}")
        return None

    # Load GEDCOM data via the batch pipeline's loader
    try:
        from scripts.run_combined_pipeline import load_gedcom_data

        gedcom_data = load_gedcom_data()
        if not gedcom_data:
            logger.info("GEDCOM context: load_gedcom_data() returned None")
            return None

        logger.info(f"GEDCOM context: loaded data with {len(gedcom_data.get('face_links', {}))} links")

        from scripts.run_combined_pipeline import build_gedcom_context

        # Build face list matching the expected format
        class _FaceStub:
            def __init__(self, face_id, identity_name):
                self.face_id = face_id
                self.identity_name = identity_name

        faces = []
        for face_id in face_ids:
            identity = _main_mod.get_identity_for_face(registry, face_id)
            name = identity.get("name") if identity else None
            faces.append(_FaceStub(face_id, name))

        identities_dict = registry._identities
        context = build_gedcom_context(photo_id, faces, identities_dict, gedcom_data)

        # If visible_text provided, add business owner context (AD-210)
        if visible_text and gedcom_data:
            parsed_gedcom = gedcom_data.get("parsed_gedcom")
            if parsed_gedcom:
                from rhodesli_ml.gedcom_context import find_business_owner_context

                owner_ctx = find_business_owner_context(visible_text, parsed_gedcom)
                if owner_ctx:
                    context = (context + "\n\n" + owner_ctx) if context else owner_ctx

        logger.info(
            f"GEDCOM context: build_gedcom_context returned {len(context)} chars"
            if context
            else "GEDCOM context: build_gedcom_context returned empty"
        )
        return context or None
    except Exception as e:
        logger.warning(f"Failed to build GEDCOM context: {e}", exc_info=True)
        return None


@rt("/api/photo/{photo_id}/reanalyze")
async def post(photo_id: str, sess=None):
    """Admin-only: Re-run Gemini analysis on a photo with GEDCOM context.

    Useful after linking GEDCOM records to identified faces.
    Returns HTMX partial showing what changed.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        return Div(
            P("Gemini API key not configured.", cls="text-red-400 text-sm"),
            data_testid="reanalyze-error",
        )

    # Load photo image
    image_bytes, suffix = _load_photo_image_bytes(photo_id)
    if not image_bytes:
        return Div(
            P("Could not load photo image.", cls="text-red-400 text-sm"),
            data_testid="reanalyze-error",
        )

    # Get old data for comparison
    old_labels = _main_mod._load_date_labels()
    old_label = old_labels.get(photo_id, {})
    old_locations = _main_mod._load_photo_locations()
    old_location = old_locations.get(photo_id, {})
    old_location_name = old_location.get("location_name", "Unknown")

    # Build photo metadata for collection/source context
    _main_mod._build_caches()
    photo_meta = _main_mod.get_photo_metadata(photo_id)
    p_metadata = None
    visible_text = None
    if photo_meta:
        p_metadata = {
            "collection": photo_meta.get("collection", ""),
            "source": photo_meta.get("source", ""),
            "filename": photo_meta.get("filename", ""),
        }
        # Extract visible text from previous analysis for business owner lookup (AD-210)
        visible_text = photo_meta.get("visible_text")
    # Also check previous date label for visible_text
    if not visible_text and old_label:
        visible_text = old_label.get("visible_text")
    # Fallback: extract visible text from previous scene_description (AD-210)
    # Gemini often detects signage like "Leon's Restaurant" in scene analysis
    # but doesn't store it as a separate visible_text field
    if not visible_text and old_label:
        scene = old_label.get("scene_description", "")
        if scene:
            import re

            # Extract quoted text that looks like business names/signage
            # Handle possessives like "Leon's Restaurant" where ' is part of the name
            quoted = re.findall(r"'([A-Z][^']*(?:'s[^']*)?[^']*)'", scene)
            if not quoted:
                quoted = re.findall(r'"([A-Z][^"]{2,50})"', scene)
            # Also look for "named X" or "called X" patterns
            if not quoted:
                named = re.findall(
                    r"(?:named|called|titled|signed?)\s+['\"]?([A-Z][A-Za-z'\s]{2,50})['\"]?",
                    scene,
                )
                if named:
                    quoted = [named[0].strip().rstrip("'.\"")]
            if quoted:
                visible_text = quoted[0]
    # Also try extracting from evidence.environment if available
    if not visible_text and old_label:
        evidence = old_label.get("evidence", {})
        if isinstance(evidence, dict):
            env = evidence.get("environment", {})
            if isinstance(env, dict):
                desc = env.get("description", "")
                if desc:
                    import re

                    quoted = re.findall(r"'([A-Z][^']*(?:'s[^']*)?[^']*)'", desc)
                    if not quoted:
                        quoted = re.findall(r'"([A-Z][^"]{2,50})"', desc)
                    if quoted:
                        visible_text = quoted[0]

    # Build GEDCOM context (with visible_text for business owner lookup)
    gedcom_context = _build_gedcom_context_for_photo(photo_id, visible_text=visible_text)

    # Call Gemini with enriched prompt
    result = _call_gemini_date_estimate(
        image_bytes,
        suffix,
        gemini_key,
        photo_id=photo_id,
        gedcom_context=gedcom_context,
        call_type="re_analysis",
        trigger="admin_rerun",
        photo_metadata=p_metadata,
    )

    if not result:
        return Div(
            P("Gemini analysis failed. Check logs for details.", cls="text-amber-400 text-sm"),
            data_testid="reanalyze-error",
        )

    # Extract results
    new_decade = result.get("estimated_decade")
    new_year = result.get("best_year_estimate")
    new_confidence = result.get("confidence", "unknown")
    location_data = result.get("location", {})
    new_location = location_data.get("place", "") if isinstance(location_data, dict) else ""

    # Update date_labels.json
    import json as _json
    from core.config import DATA_DIR

    date_labels_path = Path(DATA_DIR) / "date_labels.json"
    if date_labels_path.exists():
        try:
            all_labels = _json.loads(date_labels_path.read_text())
            # date_labels.json has schema_version + "labels" array
            labels_list = all_labels.get("labels", [])
            from rhodesli_ml.gemini_config import GEMINI_MODEL as _reanalyze_model

            new_entry = {
                "photo_id": photo_id,
                "estimated_decade": new_decade,
                "best_year_estimate": new_year,
                "confidence": new_confidence,
                "probable_range": result.get("probable_range", []),
                "reasoning_summary": result.get("reasoning_summary", ""),
                "scene_description": result.get("scene_description", ""),
                "evidence": result.get("evidence", {}),
                "location_estimate": new_location,
                "model": _reanalyze_model,
                "location_evidence": location_data if isinstance(location_data, dict) else {},
                "reanalyzed_at": datetime.now(timezone.utc).isoformat(),
                "reanalyzed_with_gedcom": bool(gedcom_context),
                "prompt_version": "v3_enriched" if gedcom_context else "v3_visual_only",
            }
            # Store visible_text for future re-analyses (AD-210)
            if visible_text:
                new_entry["visible_text"] = visible_text
            # Replace existing entry or append
            replaced = False
            for i, lbl in enumerate(labels_list):
                if lbl.get("photo_id") == photo_id:
                    labels_list[i] = {**lbl, **new_entry}
                    replaced = True
                    break
            if not replaced:
                labels_list.append(new_entry)
            all_labels["labels"] = labels_list
            date_labels_path.write_text(_json.dumps(all_labels, indent=2, ensure_ascii=False))
            # Invalidate cache — MUST invalidate page_routes cache directly
            _main_mod._date_labels_cache = None
            try:
                from app import page_routes as _pr

                _pr._date_labels_cache = None
            except Exception:
                pass
            # Dual-write to Supabase
            from app.supabase_data import sync_date_label

            sync_date_label(photo_id, new_entry)
        except Exception as e:
            logger.warning(f"Failed to update date_labels.json: {e}")

    # Update photo_locations.json
    if new_location:
        locations_path = Path(DATA_DIR) / "photo_locations.json"
        try:
            if locations_path.exists():
                all_locations = _json.loads(locations_path.read_text())
            else:
                all_locations = {"photos": {}}
            # photo_locations.json has a "photos" envelope
            photos_dict = all_locations.setdefault("photos", {})
            # Try to geocode the new location
            new_lat, new_lng = _geocode_location(new_location)
            # Use clean display name when available (e.g., "Asheville, NC" instead of vague Gemini text)
            display_name = _geocode_display_name(new_location)
            photos_dict[photo_id] = {
                "photo_id": photo_id,
                "lat": new_lat,
                "lng": new_lng,
                "location_name": display_name,
                "location_estimate": location_data.get("visual_evidence", ""),
                "biographical_evidence": location_data.get("biographical_evidence", ""),
                "missing_child_analysis": location_data.get("missing_child_analysis", ""),
                "confidence": location_data.get("confidence", "medium"),
                "region": _guess_region(new_location),
                "gemini_raw_location": new_location,  # preserve Gemini's raw output
                "reanalyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            locations_path.write_text(_json.dumps(all_locations, indent=2, ensure_ascii=False))
            # Invalidate cache — MUST invalidate page_routes cache directly (not just main alias)
            _main_mod._photo_locations_cache = None
            try:
                from app import page_routes as _pr

                _pr._photo_locations_cache = None
            except Exception:
                pass
            # Dual-write to Supabase
            from app.supabase_data import sync_photo_location

            sync_photo_location(photo_id, photos_dict[photo_id])
        except Exception as e:
            logger.warning(f"Failed to update photo_locations.json: {e}")

    # Build diff summary
    changes = []
    old_decade = old_label.get("estimated_decade")
    if old_decade and new_decade and old_decade != new_decade:
        changes.append(f"Date: {old_decade}s → {new_decade}s")
    if old_location_name and new_location and old_location_name != new_location:
        changes.append(f"Location: {old_location_name} → {new_location}")

    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing

    pricing = get_model_pricing(GEMINI_MODEL)
    est_cost = pricing.get("per_photo", 0.037)

    # Build summary div + trigger refresh of AI sections via HX-Trigger
    from starlette.responses import HTMLResponse

    summary_html = to_xml(
        Div(
            Div(
                Span("Re-analysis complete", cls="text-sm font-semibold text-emerald-400"),
                cls="mb-2",
            ),
            Div(
                P(f"Date: c. {new_year or new_decade}", cls="text-sm text-white"),
                P(f"Location: {new_location}", cls="text-sm text-white") if new_location else None,
                P(f"Confidence: {new_confidence}", cls="text-xs text-slate-400"),
                P(f"GEDCOM context: {'Yes' if gedcom_context else 'No'}", cls="text-xs text-slate-400"),
                cls="mb-2",
            ),
            Div(
                *[P(change, cls="text-xs text-amber-400") for change in changes],
                cls="mb-2",
            )
            if changes
            else P("No changes detected.", cls="text-xs text-slate-500 mb-2"),
            P(f"Est. cost: ${est_cost:.3f} · Model: {GEMINI_MODEL}", cls="text-[10px] text-slate-600"),
            cls="bg-slate-800/50 rounded-lg p-3 border border-emerald-500/30",
            data_testid="reanalyze-result",
        )
    )

    return HTMLResponse(
        content=summary_html,
        headers={"HX-Trigger": "refreshAnalysis"},
    )


LOCATION_GEOCODE = {
    "asheville": {"coords": (35.5951, -82.5515), "display": "Asheville, North Carolina"},
    "rhodes": {"coords": (36.4341, 28.2176), "display": "Rhodes, Greece"},
    "brooklyn": {"coords": (40.6782, -73.9442), "display": "Brooklyn, New York"},
    "new york": {"coords": (40.7128, -74.0060), "display": "New York, New York"},
    "miami": {"coords": (25.7617, -80.1918), "display": "Miami, Florida"},
    "tampa": {"coords": (27.9506, -82.4572), "display": "Tampa, Florida"},
    "montgomery": {"coords": (32.3792, -86.3077), "display": "Montgomery, Alabama"},
    "atlanta": {"coords": (33.7490, -84.3880), "display": "Atlanta, Georgia"},
    "havana": {"coords": (23.1136, -82.3666), "display": "Havana, Cuba"},
    "seattle": {"coords": (47.6062, -122.3321), "display": "Seattle, Washington"},
    "los angeles": {"coords": (34.0522, -118.2437), "display": "Los Angeles, California"},
    "congo": {"coords": (-4.3250, 15.3222), "display": "Congo"},
    "jerusalem": {"coords": (31.7683, 35.2137), "display": "Jerusalem, Israel"},
    "israel": {"coords": (31.0461, 34.8516), "display": "Israel"},
    "greece": {"coords": (37.9838, 23.7275), "display": "Greece"},
}


def _geocode_location(location_text: str) -> tuple[float, float]:
    """Simple geocoding from location text to lat/lng.

    Uses the geocoding dictionary from scripts/geocode_photos.py patterns.
    Returns (0, 0) if no match found.
    """
    text_lower = location_text.lower()

    for key, data in LOCATION_GEOCODE.items():
        if key in text_lower:
            return data["coords"]
    return (0.0, 0.0)


def _geocode_display_name(location_text: str) -> str:
    """Get clean display name for a location, or return original text.

    When Gemini returns vague text like 'United States (Specific city tied to...)',
    but we can match a known city, return the clean display name instead.
    """
    text_lower = location_text.lower()
    for key, data in LOCATION_GEOCODE.items():
        if key in text_lower:
            return data["display"]
    return location_text


def _guess_region(location_text: str) -> str:
    """Guess the region from location text."""
    text_lower = location_text.lower()
    us_cities = [
        "asheville",
        "new york",
        "brooklyn",
        "miami",
        "tampa",
        "montgomery",
        "atlanta",
        "seattle",
        "los angeles",
        "north carolina",
        "florida",
        "georgia",
        "alabama",
    ]
    if any(c in text_lower for c in us_cities):
        return "United States"
    if "rhodes" in text_lower or "greece" in text_lower:
        return "Greece"
    if "israel" in text_lower or "jerusalem" in text_lower:
        return "Israel"
    if "havana" in text_lower or "cuba" in text_lower:
        return "Cuba"
    if "congo" in text_lower:
        return "Congo"
    return "Unknown"
