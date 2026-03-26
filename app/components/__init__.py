"""
Rhodesli UI Components — extracted from app/main.py (Session 137).

All component modules re-export their public symbols here for convenience.
Route files should continue using `_main_mod.function_name()` — these components
are re-exported in main.py for backward compatibility.
"""

from app.components.badges import (  # noqa: F401
    state_badge,
    era_badge,
    _confidence_tier_label,
    _confidence_tier,
    _promotion_badge,
    _promotion_banner,
    _progressive_refinement_badge,
    _actionability_badge,
    _CONFIDENCE_RING,
    _CONFIDENCE_COLOR,
    _CONFIDENCE_LABEL,
)

from app.components.modals import (  # noqa: F401
    photo_modal,
    compare_modal,
    confirm_modal,
    login_modal,
)

from app.components.toasts import (  # noqa: F401
    toast_container,
    toast,
    toast_with_undo,
)

from app.components.nav import (  # noqa: F401
    og_tags,
    share_button,
    _SHARE_ICON_SVG,
    mobile_header,
    _public_nav_links,
    _public_page_nav,
    _admin_bar,
    _admin_dashboard_banner,
    inbox_badge,
)

from app.components.forms import (  # noqa: F401
    _suggest_name_form,
    manual_search_section,
    parse_transform_to_css,
    parse_transform_to_filter,
)

from app.components.layouts import (  # noqa: F401
    section_header,
    _evidence_card,
    _detective_evidence_section,
    _welcome_banner,
    _get_onboarding_surnames,
)

from app.components.cards import (  # noqa: F401
    FACES_PER_PAGE,
    match_info_bar,
    face_card,
    identity_card_mini,
    neighbor_card,
    search_result_card,
    search_results_panel,
    _build_face_cards_for_entries,
    _face_pagination_controls,
)
