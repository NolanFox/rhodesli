"""
Layout and structural components — extracted from app/main.py (Session 137).

Section headers, lane sections, evidence cards, welcome banner, and other
structural UI elements that organize page content.
"""

import json
from pathlib import Path

from fasthtml.common import (
    A,
    Button,
    Div,
    H2,
    H3,
    H4,
    P,
    Script,
    Span,
    Svg,
)
from fasthtml.common import Path as SvgPath


def section_header(
    title: str,
    subtitle: str,
    view_mode: str = None,
    section: str = None,
    nav_prefix: str = "",
) -> Div:
    """
    Section header with optional Focus/Browse toggle.
    """
    header_content = [
        Div(
            H2(title, cls="text-3xl font-bold text-slate-100 font-display tracking-tight ui99-title"),
            P(subtitle, cls="text-sm text-slate-400 font-serif italic mt-1"),
        )
    ]
    _tab_active = "bg-amber-900/40 text-amber-100 shadow-inner shadow-black/50 font-medium border border-amber-700/50"
    _tab_inactive = "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-transparent"
    _tab_match_active = "bg-amber-600 text-white shadow-md shadow-amber-900/50 font-semibold border border-amber-500"

    if section == "to_review" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href=f"{nav_prefix}/?section=to_review&view=focus",
                cls=f"px-5 py-4 sm:px-3 sm:py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'focus' else _tab_inactive}",
            ),
            A(
                "View All",
                href=f"{nav_prefix}/?section=to_review&view=browse",
                cls=f"px-5 py-4 sm:px-3 sm:py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'browse' else _tab_inactive}",
            ),
            A(
                "Match",
                href=f"{nav_prefix}/?section=to_review&view=match",
                cls=f"px-5 py-4 sm:px-3 sm:py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_match_active if view_mode == 'match' else _tab_inactive}",
            ),
            cls="flex items-center gap-2",
        )
        header_content.append(toggle)
    elif section == "skipped" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href=f"{nav_prefix}/?section=skipped&view=focus",
                cls=f"px-5 py-4 sm:px-3 sm:py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'focus' else _tab_inactive}",
            ),
            A(
                "View All",
                href=f"{nav_prefix}/?section=skipped&view=browse",
                cls=f"px-5 py-4 sm:px-3 sm:py-1.5 text-sm font-medium rounded-lg transition-colors {_tab_active if view_mode == 'browse' else _tab_inactive}",
            ),
            cls="flex items-center gap-2",
        )
        header_content.append(toggle)

    return Div(*header_content, cls="section-header flex items-center justify-between mb-8")


def _evidence_card(category: str, cues: list) -> object:
    """Render a single evidence category card for Photo Detective display.

    Args:
        category: Evidence category name (e.g., 'print_format', 'fashion').
        cues: List of cue dicts with 'cue', 'strength', 'suggested_range'.
    """
    icons = {
        "print_format": "Print/Physical",
        "fashion": "Fashion/Grooming",
        "environment": "Environment",
        "technology": "Technology",
        "cultural": "Cultural Context",
    }
    strength_colors = {
        "strong": "text-emerald-400 bg-emerald-900/30",
        "moderate": "text-amber-400 bg-amber-900/30",
        "weak": "text-slate-400 bg-slate-700/30",
    }
    display_name = icons.get(category, category.replace("_", " ").title())
    if not cues:
        return None

    cue_items = []
    for cue in cues[:3]:  # Show top 3 cues per category
        strength = cue.get("strength", "moderate")
        color_cls = strength_colors.get(strength, strength_colors["moderate"])
        date_range = cue.get("suggested_range", [])
        range_text = f" ({date_range[0]}-{date_range[1]})" if len(date_range) == 2 else ""
        cue_items.append(
            Div(
                P(cue.get("cue", ""), cls="text-sm sm:text-xs text-slate-300"),
                Span(f"{strength}{range_text}", cls=f"text-[10px] px-1.5 py-0.5 rounded-full {color_cls}"),
                cls="flex items-start justify-between gap-2 py-1",
            )
        )

    return Div(
        H4(display_name, cls="text-sm font-semibold text-white mb-2"),
        *cue_items,
        cls="bg-slate-800/40 rounded-lg p-3 border border-slate-700/30",
        data_testid=f"evidence-card-{category}",
    )


def _detective_evidence_section(label: dict) -> object:
    """Build Photo Detective evidence display from a Gemini date label.

    Args:
        label: Date label dict from date_labels.json (Gemini output).
    """
    if not label:
        return None

    evidence = label.get("evidence", {})
    if not evidence and not label.get("date_estimation", {}).get("evidence"):
        return None

    # Handle nested date_estimation structure
    if "date_estimation" in label:
        evidence = label["date_estimation"].get("evidence", {})

    cards = []
    for category in ("print_format", "fashion", "environment", "technology"):
        cues = evidence.get(category, [])
        card = _evidence_card(category, cues)
        if card:
            cards.append(card)

    # Location evidence card (from Gemini location analysis + GEDCOM reasoning)
    location_evidence = label.get("location_evidence", {})
    loc_items = []
    if location_evidence.get("place"):
        loc_items.append(
            Div(
                P(f"Location: {location_evidence['place']}", cls="text-sm sm:text-xs text-amber-200 font-semibold"),
                Span(
                    f"Confidence: {location_evidence.get('confidence', 'unknown')}",
                    cls="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400",
                ),
                cls="flex items-start justify-between gap-2 py-1",
            )
        )
    if location_evidence.get("visual_evidence"):
        loc_items.append(
            Div(
                P("Visual evidence", cls="text-[10px] text-slate-500 uppercase tracking-wide"),
                P(location_evidence["visual_evidence"], cls="text-sm sm:text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if location_evidence.get("biographical_evidence"):
        loc_items.append(
            Div(
                P("Genealogical context", cls="text-[10px] text-indigo-400 uppercase tracking-wide"),
                P(location_evidence["biographical_evidence"], cls="text-sm sm:text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if location_evidence.get("missing_child_analysis"):
        loc_items.append(
            Div(
                P("Missing child analysis", cls="text-[10px] text-emerald-400 uppercase tracking-wide"),
                P(location_evidence["missing_child_analysis"], cls="text-sm sm:text-xs text-slate-300"),
                cls="py-1",
            )
        )
    if loc_items:
        cards.append(
            Div(
                H4("Geographic Analysis", cls="text-sm font-semibold text-white mb-2"),
                *loc_items,
                cls="bg-slate-800/40 rounded-lg p-3 border border-slate-700/30",
                data_testid="evidence-card-location",
            )
        )

    if not cards:
        return None

    # Model badge with timestamp
    model = label.get("model", label.get("_model", ""))
    model_badge = None
    if model:
        display_model = model.replace("gemini-", "Gemini ").replace("-preview", "")
        # Build timestamp string from reanalyzed_at or analyzed_at
        timestamp_str = ""
        analysis_ts = label.get("reanalyzed_at") or label.get("analyzed_at") or label.get("timestamp")
        if analysis_ts:
            try:
                from datetime import datetime

                if isinstance(analysis_ts, str):
                    # Try ISO format
                    dt = datetime.fromisoformat(analysis_ts.replace("Z", "+00:00"))
                    timestamp_str = f" on {dt.strftime('%b %-d, %Y')}"
            except (ValueError, TypeError):
                pass
        prompt_version = label.get("prompt_version", "")
        version_str = f" ({prompt_version})" if prompt_version else ""
        model_badge = Span(
            f"Analyzed with {display_model}{timestamp_str}{version_str}",
            cls="text-[10px] text-indigo-300 bg-indigo-900/30 px-4 py-3 sm:px-2 sm:py-1 rounded-full",
            data_testid="model-badge",
        )

    # Cultural context note
    cultural_note = label.get("cultural_lag_note") or (label.get("date_estimation", {}).get("cultural_lag_note"))

    return Div(
        Div(
            H3("Photo Detective Analysis", cls="text-base font-serif font-semibold text-white"),
            model_badge,
            cls="flex items-center justify-between mb-3",
        ),
        Div(*cards, cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        P(f"Cultural context: {cultural_note}", cls="text-sm sm:text-xs text-slate-500 mt-3 italic")
        if cultural_note
        else None,
        cls="mt-6 p-4 bg-slate-800/20 rounded-lg border border-slate-700/20",
        data_testid="detective-evidence",
    )


def _get_onboarding_surnames() -> list[str]:
    """Get canonical surname list from surname_variants.json for the onboarding grid."""
    from core.config import DATA_DIR

    variants_path = Path(DATA_DIR) / "surname_variants.json"
    if not variants_path.exists():
        return []
    try:
        with open(variants_path) as f:
            data = json.load(f)
        return [g["canonical"] for g in data.get("variant_groups", []) if g.get("canonical")]
    except Exception:
        return []


def _welcome_banner() -> Div:
    """
    Dismissible welcome banner for first-time visitors (replaces modal wall).

    Shows a non-blocking top bar with context about the archive.
    Dismissed via X button; uses rhodesli_welcomed cookie (1 year).
    Content is immediately visible underneath -- no overlay, no blocking.
    """
    return Div(
        Div(
            Div(
                Span("Welcome to Rhodesli", cls="font-semibold text-amber-100"),
                Span(" — ", cls="text-amber-300/60 hidden sm:inline"),
                Span(
                    "a heritage photo archive for the Jewish community of Rhodes. ",
                    cls="text-amber-200/80 hidden sm:inline",
                ),
                Span(
                    "Know someone in these photos? Tap their face to help identify them.",
                    cls="text-amber-200/80 hidden sm:inline",
                ),
                # Mobile: shorter copy
                Span(" — Tap a face to help identify someone.", cls="text-amber-200/80 sm:hidden"),
                cls="flex-1 text-sm",
            ),
            Button(
                Svg(
                    SvgPath(d="M6 18L18 6M6 6l12 12"),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                    stroke_width="2",
                    stroke_linecap="round",
                    stroke_linejoin="round",
                ),
                type="button",
                cls="text-amber-300/60 hover:text-white ml-3 p-1 min-w-[28px] min-h-[28px] flex items-center justify-center",
                data_action="welcome-banner-dismiss",
                aria_label="Dismiss welcome banner",
            ),
            cls="max-w-6xl mx-auto px-4 sm:px-8 flex items-center",
        ),
        Script("""
            (function() {
                var welcomed = document.cookie.split(';').some(function(c) {
                    return c.trim().startsWith('rhodesli_welcomed=');
                });
                if (welcomed) {
                    var el = document.getElementById('welcome-banner');
                    if (el) el.remove();
                }
                document.addEventListener('click', function(e) {
                    var action = e.target.closest('[data-action="welcome-banner-dismiss"]');
                    if (action) {
                        document.cookie = 'rhodesli_welcomed=1; path=/; max-age=31536000; SameSite=Lax';
                        var banner = document.getElementById('welcome-banner');
                        if (banner) banner.remove();
                    }
                });
            })();
        """),
        id="welcome-banner",
        cls="bg-amber-900/40 border-b border-amber-700/30 py-2",
    )
