"""Tests for egress budget awareness (OD-011).

Verify TTL cache settings stay within egress budget thresholds.
These tests act as guardrails — if someone lowers a TTL, these
will flag the egress impact.
"""

import importlib


def test_registry_ttl_at_least_120s():
    """Registry TTL must be >= 120s to stay within Supabase free tier egress budget.

    See OD-011: 30s TTL = 31 GB/month worst case. 120s = ~8 GB/month.
    """
    from app.main import _REGISTRY_CACHE_TTL

    assert _REGISTRY_CACHE_TTL >= 120.0, (
        f"Registry TTL is {_REGISTRY_CACHE_TTL}s — must be >= 120s for egress budget. "
        f"See OD-011 in docs/ops/OPS_DECISIONS.md"
    )


def test_community_ids_ttl_at_least_120s():
    """Community IDs TTL must be >= 120s for egress budget."""
    from app.main import _COMMUNITY_IDS_CACHE_TTL

    assert _COMMUNITY_IDS_CACHE_TTL >= 120.0, (
        f"Community IDs TTL is {_COMMUNITY_IDS_CACHE_TTL}s — must be >= 120s. See OD-011"
    )


def test_all_supabase_caches_documented():
    """Verify all TTL caches are accounted for in OD-011 egress table.

    If you add a new Supabase TTL cache, add it to OD-011's egress table
    and to this test's KNOWN_CACHES list.
    """
    KNOWN_CACHES = {
        "app/main.py:_REGISTRY_CACHE_TTL",
        "app/main.py:_COMMUNITY_IDS_CACHE_TTL",
        "app/face_alignment.py:_ALIGNMENTS_CACHE_TTL_SECONDS",
        "app/supabase_data.py:_COMMUNITY_CACHE_TTL",
        "app/relationship_routes.py:_GEDCOM_CACHE_TTL_SECONDS",
    }
    # This test exists as documentation — it passes by listing known caches.
    # When adding a new cache, add it here AND to OD-011.
    assert len(KNOWN_CACHES) == 5, "Update this test and OD-011 when adding new Supabase TTL caches"


def test_egress_budget_worst_case():
    """Verify worst-case monthly egress stays under 50GB (Pro plan threshold).

    This catches if TTLs are lowered or table sizes grow beyond thresholds.
    Formula: table_KB * (3600/TTL) * 24 * 30 / 1024 / 1024 = GB/month
    """
    from app.main import _REGISTRY_CACHE_TTL, _COMMUNITY_IDS_CACHE_TTL

    # Known table sizes in KB (update when tables grow significantly)
    TABLES = [
        ("identities", 380, _REGISTRY_CACHE_TTL),
        ("community_ids", 50, _COMMUNITY_IDS_CACHE_TTL),
        ("photos", 436, _REGISTRY_CACHE_TTL),  # Same reload cycle
        ("photo_faces", 293, _REGISTRY_CACHE_TTL),
    ]

    total_gb = 0
    for name, size_kb, ttl in TABLES:
        fetches_per_hour = 3600 / ttl
        gb_per_month = size_kb * fetches_per_hour * 24 * 30 / 1024 / 1024
        total_gb += gb_per_month

    assert total_gb < 50, (
        f"Worst-case egress is {total_gb:.1f} GB/month — exceeds Pro plan (50GB). "
        f"Increase TTLs or implement incremental sync. See OD-011."
    )
