"""Tests for Session 125 P2 UX fixes: avatar rounding, touch targets, contrast."""

import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_person_avatar_uses_rounded_2xl():
    """Avatar on person page should use rounded-2xl, not rounded-full (historical photos crop badly)."""
    src = _read("app/person_routes.py")
    # The w-32 h-32 avatar classes should use rounded-2xl
    assert "w-32 h-32 rounded-2xl object-cover" in src
    assert "w-32 h-32 rounded-2xl bg-slate-800" in src
    # Should NOT have rounded-full on the 32x32 avatar
    assert "w-32 h-32 rounded-full" not in src


def test_compare_footer_no_text_10px():
    """Compare tool footer and distance metrics should use text-xs, not text-[10px]."""
    src = _read("app/compare_routes.py")
    # Footer tagline should be text-xs text-slate-500, not text-[10px] text-slate-600
    assert "text-[10px] text-slate-600 italic" not in src
    assert "text-xs text-slate-500 italic" in src
    # Distance metrics should not use text-[10px] text-slate-600
    assert "text-[10px] text-slate-600" not in src


def test_people_sort_dropdown_touch_target():
    """People grid sort dropdown should use py-2.5 for adequate touch target."""
    src = _read("app/browse_routes.py")
    # The sort select on the people page
    assert 'rounded-lg px-3 py-2.5"' in src


def test_person_bottom_nav_uses_py2_text_sm():
    """Bottom nav action bar chips should use py-2 text-sm for touch targets."""
    src = _read("app/person_routes.py")
    # Timeline, Map, Family Tree, Connections chips
    assert "py-2 min-h-[44px] inline-flex items-center text-sm rounded-full bg-slate-800/60" in src


def test_person_admin_chips_use_py2():
    """Admin action chips (Find Similar, Tree Linked, etc.) should use py-2."""
    src = _read("app/person_routes.py")
    assert "py-2 rounded-full bg-indigo-500/15" in src
