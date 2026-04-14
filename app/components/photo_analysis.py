"""
Photo analysis UI builders extracted from app/main.py.

Includes: _get_date_badge, _build_photo_date_badge, _build_ai_analysis_section,
_build_ai_sections_list, _build_face_alignment_section, _render_date_badge_overlay.

Uses lazy imports for app.main dependencies to avoid circular imports.
"""

from urllib.parse import quote

from fasthtml.common import (
    A,
    Button,
    Details,
    Div,
    Form,
    H2,
    H3,
    Img,
    Input,
    Label,
    Li,
    Link,
    NotStr,
    P,
    Section,
    Span,
    Summary,
    Ul,
)

from app.components.badges import _progressive_refinement_badge
from app.components.layouts import _detective_evidence_section
from core.ui_safety import ensure_utf8_display


def _get_date_badge(photo_id: str) -> tuple:
    """Get date badge text, confidence, and tooltip for a photo.

    Returns (badge_text, confidence, tooltip) or (None, None, None) if no label.
    """
    import app.main as _main_mod

    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return None, None, None

    decade = label.get("estimated_decade")
    if not decade:
        return None, None, None

    badge_text = f"c. {decade}s"
    confidence = label.get("confidence", "medium")
    best_year = label.get("best_year_estimate", "")
    prob_range = label.get("probable_range", [])
    range_str = f"{prob_range[0]}\u2013{prob_range[1]}" if len(prob_range) == 2 else ""
    tooltip = f"Best estimate: {best_year} (range: {range_str})" if best_year and range_str else f"Estimated: {decade}s"

    return badge_text, confidence, tooltip


def _build_photo_date_badge(photo_id: str):
    """Build prominent date estimate badge for photo detail page.

    Returns a Section with the estimate badge, or None if no estimate.
    PRD-022: Show 'c. 1935 ± 5 years' prominently on photo pages.
    """
    import app.main as _main_mod

    date_text, confidence, tooltip = _get_date_badge(photo_id)
    if not date_text:
        return None

    # Load full label for range info
    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id, {})
    prob_range = label.get("probable_range", [])
    best_year = label.get("best_year_estimate")
    range_str = ""
    if best_year and len(prob_range) == 2:
        margin = max(abs(prob_range[1] - best_year), abs(best_year - prob_range[0]))
        range_str = f" \u00b1 {margin} years"

    conf_cls = {
        "high": "border-emerald-500/40 bg-emerald-950/20",
        "medium": "border-amber-500/40 bg-amber-950/20",
        "low": "border-slate-500/40 bg-slate-800/40",
    }.get(confidence, "border-slate-500/40 bg-slate-800/40")

    refinement_badge = _progressive_refinement_badge(label)

    return Section(
        Div(
            Div(
                Span(date_text + range_str, cls="text-xl font-serif text-amber-200", data_testid="photo-date-badge"),
                Span(f"{confidence} confidence", cls="text-[11px] text-slate-400 ml-3"),
                refinement_badge,
                cls="flex items-center gap-2 flex-wrap",
            ),
            cls=f"max-w-[900px] mx-auto border-l-2 {conf_cls} rounded-lg px-4 py-3",
        ),
        cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
        data_testid="photo-date-badge-section",
    )


def _build_ai_analysis_section(photo_id: str, is_admin: bool = False):
    """Build the AI Analysis metadata panel for a photo detail page.

    Shows date estimate, scene description, tags, visible text, evidence, subject ages.
    Each subsection has provenance styling (AI = indigo, human = emerald).
    Returns None if no AI data available for this photo.
    """
    import app.main as _main_mod

    def _build_reanalyze_controls(label: dict | None = None, button_label: str = "Re-analyze Photo"):
        if not is_admin:
            return None

        last_analyzed_el = None
        if label:
            analysis_ts = label.get("reanalyzed_at") or label.get("analyzed_at") or label.get("timestamp")
            analysis_label = _main_mod._format_display_date(analysis_ts, include_time=True)
            if analysis_label:
                last_analyzed_el = Span(
                    f"Last analyzed: {analysis_label}",
                    cls="text-[10px] text-slate-500 mr-2",
                    data_testid="last-analyzed",
                )

        safe_id = photo_id.replace(".", "_")
        return Div(
            last_analyzed_el,
            Button(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'
                ),
                button_label,
                hx_post=f"/api/photo/{photo_id}/reanalyze",
                hx_target=f"#reanalyze-result-{safe_id}",
                hx_swap="innerHTML",
                hx_indicator=f"#reanalyze-spinner-{safe_id}",
                cls="flex items-center text-[11px] text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 hover:border-indigo-400/50 rounded px-4 py-3 sm:px-2 sm:py-1 transition-colors cursor-pointer",
                data_testid="reanalyze-button",
                title="Date, location, and scene analysis",
            ),
            Span(
                cls="htmx-indicator animate-spin inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full ml-2",
                id=f"reanalyze-spinner-{safe_id}",
            ),
            cls="flex items-center",
        )

    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        if is_admin:
            return Section(
                Div(
                    Div(
                        Div(
                            Span("\u2728", cls="text-xl sm:text-lg mr-2"),
                            H2("AI Analysis", cls="text-xl sm:text-lg font-serif font-semibold text-white inline"),
                            cls="flex items-center",
                        ),
                        _build_reanalyze_controls(button_label="Run AI Analysis"),
                        cls="flex items-center justify-between mb-1",
                    ),
                    P("No Gemini analysis has been run on this photo yet.", cls="text-[11px] text-indigo-400/70 mb-2"),
                    P(
                        "Run the first analysis to generate date, location, scene, and evidence fields.",
                        cls="text-sm text-slate-400 mb-4",
                        data_testid="ai-analysis-empty",
                    ),
                    Div(id=f"reanalyze-result-{photo_id.replace('.', '_')}", cls="mb-3"),
                    cls="max-w-[900px] mx-auto",
                    data_testid="ai-analysis",
                ),
                cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
            )
        return None

    # Build search index entry for tags/scene (check both photo_id and cache_photo_id)
    docs = _main_mod._load_search_index()
    search_doc = next((d for d in docs if d.get("photo_id") == photo_id or d.get("cache_photo_id") == photo_id), None)

    # Track which specific fields have been human-corrected
    _date_is_human = label.get("source") == "human"

    def _field(title, content, field_key="ai", expanded=False):
        """Render a collapsible subsection with provenance styling.

        field_key: 'ai' (default), 'human' (force verified), or 'date' (uses date-specific source).
        """
        is_human = field_key == "human" or (field_key == "date" and _date_is_human)
        border_cls = "border-emerald-500/40 bg-emerald-950/20" if is_human else "border-indigo-500/40 bg-indigo-950/20"
        icon = "\u2713" if is_human else "\u2728"
        provenance_text = "Verified" if is_human else "AI Estimated"
        provenance_cls = "text-emerald-400" if is_human else "text-indigo-400"

        return Details(
            Summary(
                Div(
                    Span(icon, cls="mr-1.5"),
                    Span(title, cls="text-sm font-medium text-white"),
                    Span(f" \u2014 {provenance_text}", cls=f"text-[10px] {provenance_cls} ml-2"),
                    cls="flex items-center",
                ),
                cls="cursor-pointer list-none select-none py-2 px-3 hover:bg-slate-800/50 rounded-lg transition-colors",
            ),
            Div(content, cls="px-3 pb-3 text-sm text-slate-300 leading-relaxed"),
            cls=f"border-l-2 {border_cls} rounded-lg mb-2",
            open=expanded,
            data_provenance="human" if is_human else "ai",
            data_testid="verified-field" if is_human else None,
        )

    sections = []

    # Normalize old nested format: unwrap date_estimation and location dicts to top level
    # Old format: {"date_estimation": {"estimated_decade": 1920, ...}, "location": {"place": "..."}}
    # New format: {"estimated_decade": 1920, "location_estimate": "...", ...}
    if "date_estimation" in label and isinstance(label["date_estimation"], dict):
        for k, v in label["date_estimation"].items():
            if k not in label:
                label[k] = v
    if "location" in label and isinstance(label["location"], dict) and "location_estimate" not in label:
        loc = label["location"]
        label["location_estimate"] = loc.get("place", loc.get("visual_evidence", ""))
        label["location_evidence"] = loc
    if "visible_text" in label and isinstance(label["visible_text"], dict):
        label["visible_text"] = label["visible_text"].get("text", "")

    # Date estimate
    decade = label.get("estimated_decade")
    best_year = label.get("best_year_estimate")
    confidence = label.get("confidence", "medium")
    prob_range = label.get("probable_range", [])
    if decade:
        range_str = f"{prob_range[0]}\u2013{prob_range[1]}" if len(prob_range) == 2 else ""
        conf_badge_cls = {
            "high": "bg-emerald-500/20 text-emerald-400",
            "medium": "bg-amber-500/20 text-amber-400",
            "low": "bg-red-500/20 text-red-400",
        }.get(confidence, "bg-slate-500/20 text-slate-400")
        # Correction pencil button (visible to all, triggers form or login prompt)
        pencil_btn = Button(
            "\u270f\ufe0f",
            cls="text-sm sm:text-xs text-slate-500 hover:text-white transition-colors ml-2 px-1",
            data_testid="correct-date",
            data_action="toggle-date-correction",
            data_photo_id=photo_id,
            title="Correct this date",
            type="button",
        )
        # Inline correction form (hidden by default, shown on pencil click)
        correction_form = Div(
            Form(
                Div(
                    Label("Actual year:", fr="correction-year-input", cls="text-[11px] text-slate-400 mr-2"),
                    Input(
                        type="number",
                        name="correction_year",
                        id="correction-year-input",
                        min="1850",
                        max="2030",
                        placeholder=str(best_year or decade),
                        cls="w-20 bg-slate-800 border border-slate-600 rounded px-4 py-3 sm:px-2 sm:py-1 text-sm text-white",
                        data_testid="correction-year",
                    ),
                    Button(
                        "Submit",
                        cls="ml-2 px-3 py-1 text-sm sm:text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors",
                        data_testid="correction-submit",
                        type="submit",
                    ),
                    Button(
                        "Cancel",
                        cls="ml-1 px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs text-slate-400 hover:text-white transition-colors",
                        type="button",
                        data_action="toggle-date-correction",
                    ),
                    cls="flex items-center mt-2",
                ),
                method="post",
                action=f"/api/photo/{photo_id}/correct-date",
                hx_post=f"/api/photo/{photo_id}/correct-date",
                hx_target=f"#date-section-{photo_id[:8]}",
                hx_swap="outerHTML",
            ),
            id=f"date-correction-form-{photo_id[:8]}",
            cls="hidden",
        )
        # Decade probability distribution bars (from Gemini decade_probabilities)
        decade_probs = label.get("decade_probabilities", {})
        prob_bars_el = None
        if decade_probs and isinstance(decade_probs, dict):
            bars = []
            for dec_str in sorted(decade_probs.keys()):
                try:
                    dec_val = int(dec_str)
                    prob_val = float(decade_probs[dec_str])
                except (ValueError, TypeError):
                    continue
                pct = prob_val * 100
                bar_width = max(1, pct)
                is_predicted = dec_val == decade
                bar_color = "bg-amber-400" if is_predicted else "bg-slate-600"
                text_cls = "text-amber-400 font-semibold" if is_predicted else "text-slate-500"
                bars.append(
                    Div(
                        Span(f"{dec_val}s", cls=f"text-[10px] {text_cls} w-10 text-right mr-2 shrink-0"),
                        Div(
                            Div(cls=f"{bar_color} h-full rounded-r", style=f"width:{bar_width}%"),
                            cls="flex-1 bg-slate-800 rounded h-2.5",
                        ),
                        Span(f"{pct:.0f}%", cls=f"text-[10px] {text_cls} w-8 ml-2 shrink-0"),
                        cls="flex items-center",
                    )
                )
            if bars:
                prob_bars_el = Div(
                    *bars,
                    cls="flex flex-col gap-0.5 mt-3",
                    data_testid="decade-probability-bars",
                )

        date_content = Div(
            Div(
                P(
                    f"circa {best_year}" if best_year else f"{decade}s",
                    cls="text-xl sm:text-lg font-serif text-amber-200 mb-1 inline",
                ),
                pencil_btn,
                cls="flex items-center",
            ),
            Div(
                Span(f"Confidence: {confidence}", cls=f"text-[11px] px-2 py-0.5 rounded-full {conf_badge_cls}"),
                Span(f"Range: {range_str}", cls="text-[11px] text-slate-500 ml-2") if range_str else None,
                _progressive_refinement_badge(label),
                cls="flex items-center gap-2 flex-wrap",
            ),
            prob_bars_el,
            correction_form,
            id=f"date-section-{photo_id[:8]}",
        )
        sections.append(_field("Date Estimate", date_content, field_key="date", expanded=True))

    # Reasoning summary (from Gemini date estimation)
    reasoning = label.get("reasoning_summary", "")
    if reasoning:
        sections.append(_field("AI Reasoning", P(reasoning, cls="italic text-slate-400")))

    # Location estimate (from Gemini + geocoded data)
    # Handle both string (web re-analyze) and dict (batch) formats
    # Batch script writes location_estimate as string + location_evidence as dict
    # Old batch format may have location_estimate as dict
    raw_location = label.get("location_estimate", "")
    location_evidence_dict = label.get("location_evidence", {})
    if isinstance(raw_location, dict):
        # Old batch format — extract from dict
        location_estimate = raw_location.get("visual_evidence", "") or raw_location.get("place", "")
        if not location_evidence_dict:
            location_evidence_dict = raw_location
    else:
        location_estimate = raw_location
    # Enrich location_estimate with evidence from location_evidence if available
    if not location_estimate and isinstance(location_evidence_dict, dict):
        location_estimate = location_evidence_dict.get("visual_evidence", "") or location_evidence_dict.get("place", "")
    locations = _main_mod._load_photo_locations()
    location_data = locations.get(photo_id, {})
    location_name = location_data.get("location_name", "")
    location_region = location_data.get("region", "")
    location_confidence = location_data.get("confidence", "")
    has_location = bool(location_estimate or location_name)

    if has_location:
        location_parts = []
        # Location label
        if location_name:
            loc_label = location_name
            if location_region:
                loc_label += f", {location_region}"
            location_parts.append(P(loc_label, cls="text-xl sm:text-lg font-serif text-amber-200 mb-1"))
        # Confidence badge
        if location_confidence:
            loc_conf_cls = {
                "high": "bg-emerald-500/20 text-emerald-400",
                "medium": "bg-amber-500/20 text-amber-400",
                "low": "bg-red-500/20 text-red-400",
            }.get(location_confidence, "bg-slate-500/20 text-slate-400")
            location_parts.append(
                Span(f"Confidence: {location_confidence}", cls=f"text-[11px] px-2 py-0.5 rounded-full {loc_conf_cls}")
            )
        # Evidence text (Gemini's reasoning)
        if location_estimate:
            location_parts.append(
                P(
                    location_estimate,
                    cls="text-slate-400 text-sm sm:text-xs mt-2 italic",
                    data_testid="location-evidence",
                )
            )
        # Location candidates (AD-234: alternative locations considered)
        candidates = None
        if isinstance(label.get("location"), dict):
            candidates = label["location"].get("candidates", [])
        elif isinstance(location_evidence_dict, dict):
            candidates = location_evidence_dict.get("candidates", [])
        if candidates and isinstance(candidates, list):
            candidate_items = []
            for cand in candidates[:3]:
                if isinstance(cand, dict):
                    c_place = cand.get("place", "")
                    c_conf = cand.get("confidence", "")
                    c_reason = cand.get("reasoning", "")
                    c_source = cand.get("source", "")
                    if c_place:
                        item_parts = [Span(c_place, cls="text-slate-300 font-medium")]
                        if c_conf:
                            item_parts.append(Span(f" ({c_conf})", cls="text-slate-500 text-[11px]"))
                        if c_source:
                            item_parts.append(Span(f" [{c_source}]", cls="text-slate-600 text-[10px]"))
                        if c_reason:
                            item_parts.append(Span(f" — {c_reason}", cls="text-slate-500 text-[11px] italic"))
                        candidate_items.append(Li(*item_parts, cls="text-sm py-0.5"))
            if candidate_items:
                location_parts.append(
                    Details(
                        Summary(
                            "Other possible locations",
                            cls="text-[11px] text-indigo-400 cursor-pointer mt-2 hover:text-indigo-300",
                        ),
                        Ul(*candidate_items, cls="list-disc list-inside mt-1 ml-2"),
                        data_testid="location-candidates",
                    )
                )

        # Admin: Correct Location button (simple text input)
        if is_admin:
            location_parts.append(
                Div(
                    Form(
                        Div(
                            Label(
                                "Correct location:",
                                fr="correction-location-input",
                                cls="text-[11px] text-slate-400 mr-2",
                            ),
                            Input(
                                type="text",
                                name="correction_location",
                                id="correction-location-input",
                                placeholder=location_name or "City, Country",
                                cls="bg-slate-800 border border-slate-600 rounded px-4 py-3 sm:px-2 sm:py-1 text-sm text-white w-48",
                                data_testid="correction-location",
                            ),
                            Button(
                                "Submit",
                                cls="ml-2 px-3 py-1 text-sm sm:text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors",
                                type="button",
                                disabled=True,
                                title="Location correction coming soon",
                            ),
                            cls="flex items-center mt-2",
                        ),
                    ),
                    cls="mt-2",
                    data_testid="location-correction-form",
                )
            )

        # Embedded Leaflet map if geocoded data exists
        if location_data.get("lat") and location_data.get("lng"):
            map_id = f"location-map-{photo_id[:8]}"
            draggable = "true" if is_admin else "false"
            # Data attributes drive init; Leaflet loaded via onload callback
            location_parts.append(
                Div(
                    Div(
                        id=map_id,
                        style="height: 300px; border-radius: 8px; margin-top: 12px;",
                        data_testid="location-map",
                        data_lat=str(location_data["lat"]),
                        data_lng=str(location_data["lng"]),
                        data_label=location_name,
                        data_draggable=draggable,
                    ),
                    Link(rel="stylesheet", href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
                )
            )

        location_content = Div(
            *location_parts,
            id=f"location-section-{photo_id[:8]}",
            data_testid="location-estimate",
        )
        sections.append(_field("Location Estimate", location_content, expanded=True))

    # Scene description
    scene = label.get("scene_description", "")
    if not scene and search_doc:
        # Fall back to searchable text (first sentence)
        st = search_doc.get("searchable_text", "")
        scene = st.split(".")[0] + "." if "." in st else st[:200]
    if scene:
        sections.append(_field("Scene", P(scene), expanded=True))

    # Visible text (OCR) — handle both string and dict (text_signage) formats
    visible_text = label.get("visible_text", "")
    if not visible_text:
        text_signage = label.get("text_signage", {})
        if isinstance(text_signage, dict) and text_signage.get("detected"):
            visible_text = text_signage.get("text", "")
    if visible_text:
        sections.append(
            _field("Visible Text", P(visible_text, cls="italic font-mono text-sm sm:text-xs text-slate-400"))
        )

    # Tags
    tags = label.get("controlled_tags") or (search_doc.get("controlled_tags") if search_doc else None)
    if tags:
        tag_pills = [
            A(
                t.replace("_", " "),
                href=f"/photos?tag={quote(t)}",
                cls="px-2 py-0.5 text-[11px] bg-slate-700/60 text-slate-300 rounded-full hover:bg-indigo-600/40 hover:text-white transition-colors",
                data_testid="ai-tag",
            )
            for t in tags
        ]
        sections.append(
            _field(
                "Tags",
                Div(
                    *tag_pills, cls="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-1.5 w-full sm:w-auto text-center"
                ),
            )
        )

    # Dating evidence — Photo Detective card layout
    detective_section = _detective_evidence_section(label)
    if detective_section:
        sections.append(_field("Photo Detective Evidence", detective_section, expanded=True))
    else:
        # Fallback: simple list for labels without structured evidence
        evidence = label.get("evidence", {})
        if evidence:
            evidence_items = []
            for category, cues in evidence.items():
                if not isinstance(cues, list):
                    continue
                for cue in cues[:3]:  # Max 3 per category
                    cue_text = cue.get("cue", "") if isinstance(cue, dict) else str(cue)
                    strength = cue.get("strength", "") if isinstance(cue, dict) else ""
                    if cue_text:
                        strength_cls = {
                            "strong": "text-emerald-400",
                            "moderate": "text-amber-400",
                            "weak": "text-slate-500",
                        }.get(strength, "text-slate-500")
                        evidence_items.append(
                            Li(
                                Span(cue_text, cls="text-slate-400"),
                                Span(f" ({strength})", cls=f"text-[10px] {strength_cls}") if strength else None,
                                cls="text-sm sm:text-xs mb-1",
                            )
                        )
            if evidence_items:
                sections.append(_field("Dating Evidence", Ul(*evidence_items, cls="list-disc list-inside space-y-0.5")))

    # Subject ages
    ages = label.get("subject_ages")
    if ages:
        if isinstance(ages, list):
            ages_text = ", ".join(str(a) for a in ages)
        elif isinstance(ages, str):
            ages_text = ages
        else:
            ages_text = str(ages)
        if ages_text:
            sections.append(_field("Subject Ages", P(ages_text), expanded=True))

    # Face analysis (batch preset: per-face age/gender/description)
    face_analysis = label.get("face_analysis")
    if face_analysis and isinstance(face_analysis, list):
        # Build face_index → identity name mapping
        # Only reliable for single-face photos (Codex P1: face_index is
        # left-to-right from Gemini but face_ids are sorted lexically)
        face_index_to_name = {}
        photo_data = _main_mod._photo_cache.get(photo_id, {}) if _main_mod._photo_cache else {}
        faces = photo_data.get("faces", [])
        face_ids = [f["face_id"] for f in faces if isinstance(f, dict) and "face_id" in f]
        if len(face_ids) == 1:
            # Single face — index mapping is trivially correct
            registry = _main_mod.load_registry()
            identity = _main_mod.get_identity_for_face(registry, face_ids[0])
            if identity:
                name = identity.get("name", "")
                if name and not name.startswith("Unidentified"):
                    face_index_to_name[0] = name

        face_items = []
        for fa in face_analysis:
            if isinstance(fa, dict):
                age = fa.get("estimated_age", "")
                gender = fa.get("gender", "")
                desc = fa.get("description", "")
                idx = fa.get("face_index", "")
                parts = []
                if age:
                    parts.append(f"Age ~{age}")
                if gender:
                    parts.append(gender.capitalize())
                label_text = ", ".join(parts)
                # Use person name if face is identified, otherwise "Face N"
                face_label = face_index_to_name.get(idx, f"Face {idx}") if idx != "" else ""
                face_items.append(
                    Li(
                        Span(f"{face_label}: " if face_label else "", cls="text-slate-500"),
                        Span(label_text, cls="text-slate-300 font-medium") if label_text else None,
                        Span(f" — {desc}", cls="text-slate-400") if desc else None,
                        cls="text-sm sm:text-xs mb-1",
                    )
                )
        if face_items:
            sections.append(
                _field("Face Analysis", Ul(*face_items, cls="list-disc list-inside space-y-0.5"), expanded=True)
            )

    # Group composition (batch preset: type, count, arrangement)
    group_comp = label.get("group_composition")
    if group_comp and isinstance(group_comp, dict):
        comp_parts = []
        gtype = group_comp.get("type", "").replace("_", " ").title()
        count = group_comp.get("people_count")
        arrangement = group_comp.get("arrangement", "")
        if gtype:
            comp_parts.append(P(gtype, cls="text-amber-200 font-serif"))
        if count:
            comp_parts.append(P(f"{count} people", cls="text-sm text-slate-400"))
        if arrangement:
            comp_parts.append(P(arrangement, cls="text-sm text-slate-400 italic mt-1"))
        if comp_parts:
            sections.append(_field("Group Composition", Div(*comp_parts), expanded=True))

    # Clothing notes (batch preset: era clothing description)
    clothing = label.get("clothing_notes", "")
    if clothing and isinstance(clothing, str):
        sections.append(_field("Clothing & Attire", P(clothing, cls="italic text-slate-400"), expanded=True))

    if not sections:
        return None

    reanalyze_btn = _build_reanalyze_controls(label)

    return Section(
        Div(
            Div(
                Div(
                    Span("\u2728", cls="text-xl sm:text-lg mr-2"),
                    H2("AI Analysis", cls="text-xl sm:text-lg font-serif font-semibold text-white inline"),
                    cls="flex items-center",
                ),
                reanalyze_btn,
                cls="flex items-center justify-between mb-1",
            ),
            P("Estimated by AI \u2014 help us verify", cls="text-[11px] text-indigo-400/70 mb-4"),
            Div(id=f"reanalyze-result-{photo_id.replace('.', '_')}", cls="mb-3"),
            # Anchor Compare (AD-233) — admin only
            Div(
                Details(
                    Summary(
                        "Compare with anchor photo",
                        cls="text-[11px] text-indigo-400 cursor-pointer hover:text-indigo-300",
                    ),
                    Div(
                        Input(
                            type="text",
                            name="anchor_photo_id",
                            placeholder="Anchor photo ID",
                            cls="bg-slate-800 border border-slate-600 rounded px-3 py-1 text-sm text-white w-64",
                            id=f"anchor-input-{photo_id[:8]}",
                        ),
                        Button(
                            "Compare",
                            hx_post=f"/api/photo/{photo_id}/anchor-compare",
                            hx_include=f"#anchor-input-{photo_id[:8]}",
                            hx_target=f"#anchor-result-{photo_id[:8]}",
                            hx_swap="innerHTML",
                            cls="ml-2 px-3 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded",
                        ),
                        cls="flex items-center mt-2",
                    ),
                    Div(id=f"anchor-result-{photo_id[:8]}", cls="mt-2"),
                    data_testid="anchor-compare-panel",
                ),
                cls="mb-3",
            )
            if is_admin
            else None,
            Div(
                *sections,
                id=f"ai-analysis-sections-{photo_id}",
                hx_get=f"/api/photo/{photo_id}/ai-sections",
                hx_trigger="refreshAnalysis from:body",
                hx_swap="innerHTML",
            ),
            cls="max-w-[900px] mx-auto",
            data_testid="ai-analysis",
        ),
        cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
    )


def _build_ai_sections_list(photo_id: str, label: dict, is_admin: bool = False):
    """Build just the collapsible sections for AI Analysis (no wrapper).

    This is the inner content of the ai-analysis-sections-{photo_id} div,
    used both for initial render and for OOB refresh after re-analyze.
    """
    import app.main as _main_mod

    docs = _main_mod._load_search_index()
    search_doc = next((d for d in docs if d.get("photo_id") == photo_id or d.get("cache_photo_id") == photo_id), None)
    _date_is_human = label.get("source") == "human"

    def _field(title, content, field_key="ai", expanded=False):
        is_human = field_key == "human" or (field_key == "date" and _date_is_human)
        border_cls = "border-emerald-500/40 bg-emerald-950/20" if is_human else "border-indigo-500/40 bg-indigo-950/20"
        icon = "\u2713" if is_human else "\u2728"
        provenance_text = "Verified" if is_human else "AI Estimated"
        provenance_cls = "text-emerald-400" if is_human else "text-indigo-400"
        return Details(
            Summary(
                Div(
                    Span(icon, cls="mr-1.5"),
                    Span(title, cls="text-sm font-medium text-white"),
                    Span(f" \u2014 {provenance_text}", cls=f"text-[10px] {provenance_cls} ml-2"),
                    cls="flex items-center",
                ),
                cls="cursor-pointer list-none select-none py-2 px-3 hover:bg-slate-800/50 rounded-lg transition-colors",
            ),
            Div(content, cls="px-3 pb-3 text-sm text-slate-300 leading-relaxed"),
            cls=f"border-l-2 {border_cls} rounded-lg mb-2",
            open=expanded,
            data_provenance="human" if is_human else "ai",
            data_testid="verified-field" if is_human else None,
        )

    sections = []

    # Date estimate
    decade = label.get("estimated_decade")
    best_year = label.get("best_year_estimate")
    confidence = label.get("confidence", "medium")
    if decade:
        conf_badge_cls = {
            "high": "bg-emerald-500/20 text-emerald-400",
            "medium": "bg-amber-500/20 text-amber-400",
            "low": "bg-red-500/20 text-red-400",
        }.get(confidence, "bg-slate-500/20 text-slate-400")
        date_text = f"circa {best_year}" if best_year else f"{decade}s"
        date_content = Div(
            P(date_text, cls="text-xl sm:text-lg font-serif text-amber-200 mb-1"),
            Span(confidence.capitalize(), cls=f"text-[10px] px-2 py-0.5 rounded-full {conf_badge_cls}"),
        )
        sections.append(_field("Date Estimate", date_content, field_key="date", expanded=True))

    # Location
    locations = _main_mod._load_photo_locations()
    location_data = locations.get(photo_id, {})
    location_name = location_data.get("location_name", "")
    if location_name:
        location_parts = [P(location_name, cls="text-white font-medium")]
        location_estimate = location_data.get("location_estimate", "")
        if location_estimate:
            location_parts.append(P(location_estimate, cls="text-slate-400 text-sm sm:text-xs mt-2 italic"))
        location_content = Div(*location_parts, data_testid="location-estimate")
        sections.append(_field("Location Estimate", location_content, expanded=True))

    # Scene description
    scene = label.get("scene_description", "")
    if not scene and search_doc:
        st = search_doc.get("searchable_text", "")
        scene = st.split(".")[0] + "." if "." in st else st[:200]
    if scene:
        sections.append(_field("Scene", P(scene), expanded=True))

    # Photo Detective Evidence
    detective_section = _detective_evidence_section(label)
    if detective_section:
        sections.append(_field("Photo Detective Evidence", detective_section, expanded=True))

    if not sections:
        return Div()
    return Div(*sections)


def _build_face_alignment_section(photo_id: str, is_admin: bool = False):
    """Build the face alignment description panel for a photo page.

    Shows per-face Gemini descriptions (from PRD-015 coordinate bridging).
    Returns None if no alignment data exists for this photo.
    Also returns None if AI Analysis already has face_analysis data (avoid duplicate).
    Admin users see a "Detect Faces" trigger button if not yet aligned.
    """
    import app.main as _main_mod

    # Skip if AI Analysis already shows face analysis (avoid duplicate section)
    labels = _main_mod._load_date_labels()
    dl = labels.get(photo_id, {})
    if isinstance(dl.get("face_analysis"), list) and dl["face_analysis"]:
        return None

    from app.face_alignment import get_cached_alignment, load_alignments

    # Check for existing alignment data (Supabase-first, AD-152)
    alignment = get_cached_alignment(photo_id)
    if alignment is None:
        alignments = load_alignments(_main_mod.data_path)
        alignment = alignments.get(photo_id)

    # Admin trigger button if no alignment exists
    if alignment is None:
        if not is_admin:
            return None
        return Div(
            H3("Face Analysis", cls="text-xl sm:text-lg font-serif font-bold text-white mb-2"),
            P("No face descriptions available yet.", cls="text-slate-400 text-sm mb-2"),
            Div(
                Button(
                    "Detect Faces",
                    cls="text-sm px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white "
                    "rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                    hx_post=f"/api/face-alignment/{photo_id}",
                    hx_target=f"#face-alignment-{photo_id[:8]}",
                    hx_swap="innerHTML",
                    hx_indicator=f"#face-alignment-spinner-{photo_id[:8]}",
                    hx_disabled_elt="this",
                    type="button",
                ),
                Span(
                    Span(
                        cls="inline-block w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mr-2"
                    ),
                    "Analyzing faces...",
                    cls="htmx-indicator ml-3 text-sm text-indigo-300",
                    id=f"face-alignment-spinner-{photo_id[:8]}",
                ),
                cls="flex items-center",
            ),
            id=f"face-alignment-{photo_id[:8]}",
            cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
            data_testid="face-alignment-trigger",
        )

    # Render alignment results
    # Handle both AlignmentResult objects and raw dicts
    if isinstance(alignment, dict):
        aligned_faces = alignment.get("aligned_faces", [])
        faces_detected = alignment.get("faces_detected", 0)
        faces_described = alignment.get("faces_described", 0)
        gemini_only = alignment.get("gemini_only_faces", [])
        scene_context = alignment.get("scene_context", "")
        model_used = alignment.get("model_used", "")
        analyzed_at = alignment.get("analyzed_at", "")
    else:
        aligned_faces = [
            f
            if isinstance(f, dict)
            else {
                "face_id": f.face_id,
                "estimated_age": f.estimated_age,
                "gender": f.gender,
                "gemini_description": f.gemini_description,
                "clothing": f.clothing,
                "position_in_photo": f.position_in_photo,
                "identifying_features": f.identifying_features,
                "identity_name": f.identity_name,
                "is_subject": f.is_subject,
            }
            for f in alignment.aligned_faces
        ]
        faces_detected = alignment.faces_detected
        faces_described = alignment.faces_described
        gemini_only = alignment.gemini_only_faces
        scene_context = alignment.scene_context
        model_used = alignment.model_used
        analyzed_at = getattr(alignment, "analyzed_at", "")

    # Format model + timestamp line
    model_line = f"Gemini coordinate bridging ({model_used})" if model_used else "Gemini coordinate bridging"
    if analyzed_at:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(analyzed_at)
            model_line += f" on {dt.strftime('%b %-d, %Y')}"
        except (ValueError, TypeError):
            pass

    # Look up identities for face labels
    registry = _main_mod.load_registry()

    face_cards = []
    for i, face in enumerate(aligned_faces):
        is_subject = face.get("is_subject", True)
        if not is_subject:
            continue  # Skip non-subject faces in the display

        name = face.get("identity_name") or "Unidentified"
        age = face.get("estimated_age")
        gender = face.get("gender", "")
        clothing = face.get("clothing", "")
        description = face.get("gemini_description", "")
        position = face.get("position_in_photo", "")
        features = face.get("identifying_features", "")

        # Look up actual identity from registry for this face
        face_id = face.get("face_id", "")
        matched_identity = _main_mod.get_identity_for_face(registry, face_id) if face_id else None
        identity_id = matched_identity.get("identity_id") if matched_identity else None
        registry_name = ensure_utf8_display(matched_identity.get("name", "")) if matched_identity else ""
        is_confirmed = matched_identity and matched_identity.get("state") == "CONFIRMED"
        has_real_name = is_confirmed and registry_name and not registry_name.startswith("Unidentified")

        # Use registry name if available and confirmed, otherwise use Gemini name
        display_name = registry_name if has_real_name else name

        card_content = []
        # Header: face index + identity name (clickable link if identified)
        if has_real_name and identity_id:
            header_el = Div(
                A(
                    display_name,
                    href=f"/person/{identity_id}",
                    cls="text-emerald-400 hover:text-emerald-300 font-medium text-sm underline transition-colors",
                    data_testid="face-identity-link",
                ),
                cls="mb-1",
            )
        else:
            header_text = f"Face {i}"
            if display_name != "Unidentified":
                header_text += f": {display_name}"
            header_el = P(header_text, cls="text-white font-medium text-sm mb-1")
        card_content.append(header_el)

        # Demographics line
        demo_parts = []
        if age:
            demo_parts.append(f"Age: ~{age}")
        if gender:
            demo_parts.append(gender.capitalize())
        if demo_parts:
            card_content.append(P(" | ".join(demo_parts), cls="text-indigo-300 text-sm sm:text-xs mb-1"))

        # Description
        if description:
            card_content.append(P(description, cls="text-slate-300 text-sm sm:text-xs mb-1"))

        # Clothing
        if clothing:
            card_content.append(P(f"Attire: {clothing}", cls="text-slate-400 text-sm sm:text-xs mb-1"))

        # Position + Features
        if position:
            card_content.append(P(f"Position: {position}", cls="text-slate-500 text-sm sm:text-xs"))
        if features:
            card_content.append(P(f"Features: {features}", cls="text-slate-500 text-sm sm:text-xs italic"))

        face_cards.append(
            Div(
                *card_content,
                cls="border border-indigo-500/30 bg-indigo-950/20 rounded-lg p-3",
            )
        )

    # Mismatch warning
    mismatch_warning = None
    if faces_detected != faces_described:
        mismatch_warning = Div(
            P(
                f"InsightFace detected {faces_detected} faces, Gemini described {faces_described}.",
                cls="text-amber-300 text-sm sm:text-xs",
            ),
            P(
                f"{len(gemini_only)} additional face(s) seen by Gemini only." if gemini_only else "",
                cls="text-amber-400/70 text-sm sm:text-xs",
            )
            if gemini_only
            else None,
            cls="bg-amber-900/20 border border-amber-500/30 rounded px-3 py-2 mb-3",
            data_testid="face-alignment-mismatch",
        )

    # Scene context
    scene_el = None
    if scene_context:
        scene_el = P(f"Scene: {scene_context}", cls="text-slate-400 text-sm sm:text-xs italic mb-3")

    return Div(
        H3("Face Analysis", cls="text-xl sm:text-lg font-serif font-bold text-white mb-2"),
        P(model_line, cls="text-indigo-400/70 text-[11px] mb-3"),
        mismatch_warning,
        scene_el,
        Div(*face_cards, cls="grid gap-4 sm:gap-2 grid-cols-1 sm:grid-cols-2")
        if face_cards
        else P("No subject faces described.", cls="text-slate-500 text-sm"),
        # Re-run button for admin
        Button(
            "Re-run Analysis",
            cls="mt-3 text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors",
            hx_post=f"/api/face-alignment/{photo_id}",
            hx_target=f"#face-alignment-{photo_id[:8]}",
            hx_swap="innerHTML",
            type="button",
        )
        if is_admin
        else None,
        id=f"face-alignment-{photo_id[:8]}",
        cls="px-4 sm:px-6 py-4 border-t border-slate-800/50",
        data_testid="face-alignment-results",
    )


def _render_date_badge_overlay(photo_id: str) -> Span:
    """Render a date badge overlay for a photo card. Returns None if no label."""
    date_text, date_conf, date_tooltip = _get_date_badge(photo_id)
    if not date_text:
        return None

    if date_conf == "high":
        cls = "bg-amber-800/80 text-amber-100"
    elif date_conf == "medium":
        cls = "bg-amber-800/50 border border-amber-600/50 text-amber-200/90"
    else:
        cls = "border border-dashed border-amber-600/40 text-amber-400/60"

    return Span(
        date_text,
        cls=f"absolute bottom-2 right-2 text-[11px] font-serif px-1.5 py-0.5 rounded backdrop-blur-sm {cls}",
        title=date_tooltip,
        data_testid="date-badge",
        data_confidence=date_conf,
    )
