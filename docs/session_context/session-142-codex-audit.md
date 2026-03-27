OpenAI Codex v0.115.0 (research preview)
--------
workdir: /Users/nolanfox/rhodesli
model: gpt-5.4
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/nolanfox/.codex/memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019d2dca-2eca-7353-a2f0-18f129ef85f6
--------
user
Audit these files changed in Session 142 of the Rhodesli project. Focus on: security issues, data integrity, race conditions, error handling, test coverage gaps. Rate each finding P0/P1/P2/P3. Files: app/compare_routes.py, app/components/cards.py, app/components/identity_cards.py, app/identity_routes.py, app/page_routes.py, scripts/batch_gemini_for_person.py, tests/test_photo_navigation.py, tests/test_skipped_faces.py. Use git diff origin/main~12..HEAD to see all changes.
mcp startup: no servers
codex
Reviewing the Session 142 diff for the listed files and checking the changed code paths for security, data integrity, race conditions, error handling, and test coverage gaps. I’m starting with `git diff origin/main~12..HEAD` and the current contents of the touched files so the findings are tied to exact changes rather than assumptions.
exec
/bin/zsh -lc 'git status --short' in /Users/nolanfox/rhodesli succeeded in 0ms:
 M .claude/current_session.txt
 M .claude/session_mode.txt
?? docs/session_context/session-142-codex-audit.md
exec
/bin/zsh -lc 'git diff --stat origin/main~12..HEAD -- app/compare_routes.py app/components/cards.py app/components/identity_cards.py app/identity_routes.py app/page_routes.py scripts/batch_gemini_for_person.py tests/test_photo_navigation.py tests/test_skipped_faces.py' in /Users/nolanfox/rhodesli succeeded in 0ms:
 app/compare_routes.py              |   4 +-
 app/components/cards.py            |  10 +-
 app/components/identity_cards.py   |  24 ++-
 app/identity_routes.py             | 249 ++++++++++++++++++++--
 app/page_routes.py                 |   4 +-
 scripts/batch_gemini_for_person.py | 409 +++++++++++++++++++++++++++++++++++++
 tests/test_photo_navigation.py     |   4 +-
 tests/test_skipped_faces.py        |  46 +++--
 8 files changed, 699 insertions(+), 51 deletions(-)
exec
/bin/zsh -lc 'git diff --unified=80 origin/main~12..HEAD -- app/compare_routes.py app/components/cards.py app/components/identity_cards.py app/identity_routes.py app/page_routes.py scripts/batch_gemini_for_person.py tests/test_photo_navigation.py tests/test_skipped_faces.py' in /Users/nolanfox/rhodesli succeeded in 0ms:
diff --git a/app/compare_routes.py b/app/compare_routes.py
index 97d5dfa..5cdee03 100644
--- a/app/compare_routes.py
+++ b/app/compare_routes.py
@@ -5807,174 +5807,174 @@ def get(
             hx_swap="outerHTML",
             hx_confirm=_merge_confirm,
             **{"_": "on htmx:afterRequest add .hidden to #compare-modal"},
             type="button",
         )
     ns_btn = Button(
         "Not Same",
         cls="px-4 py-2 text-sm font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
         hx_post=f"{nav_prefix}/api/identity/{target_id}/reject/{neighbor_id}",
         hx_target=f"#neighbor-{neighbor_id}",
         hx_swap="outerHTML",
         **{"_": "on htmx:afterRequest add .hidden to #compare-modal"},
         type="button",
     )
     cl_btn = Button(
codex
The diff is large and most of the risk sits in `app/identity_routes.py` and the new Gemini batch script. I’m narrowing to the changed hunks in those files, then I’ll validate whether the updated tests actually cover the failure modes they introduce.
exec
/bin/zsh -lc 'git diff --unified=60 origin/main~12..HEAD -- scripts/batch_gemini_for_person.py' in /Users/nolanfox/rhodesli succeeded in 0ms:
diff --git a/scripts/batch_gemini_for_person.py b/scripts/batch_gemini_for_person.py
new file mode 100644
index 0000000..d80f4a0
--- /dev/null
+++ b/scripts/batch_gemini_for_person.py
@@ -0,0 +1,409 @@
+#!/usr/bin/env python3
+"""Batch Gemini date estimation for all photos containing specific identities.
+
+Uses the production _call_gemini_date_estimate() function with:
+- GEDCOM genealogical context for identified faces
+- Full Supabase logging to gemini_api_calls table
+- Prompt manifest tracking
+- Retry logic with exponential backoff
+- Incremental results saved to date_labels.json
+
+Usage:
+    # Dry run: count photos, show cost estimate
+    python scripts/batch_gemini_for_person.py --dry-run \\
+        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
exec
/bin/zsh -lc 'git diff --unified=60 origin/main~12..HEAD -- app/identity_routes.py' in /Users/nolanfox/rhodesli succeeded in 0ms:
diff --git a/app/identity_routes.py b/app/identity_routes.py
index 66430df..2f7435f 100644
--- a/app/identity_routes.py
+++ b/app/identity_routes.py
@@ -22,345 +22,436 @@ from app.main import rt
 from app.utils import photo_url, _section_for_state
 from app.audit import _log_audit
 
 import app.main as _main_mod
 
 logger = logging.getLogger(__name__)
 
 
 # ---------------------------------------------------------------------------
 # Neighbors (similar panel) TTL cache — 5 min per identity_id
 # ---------------------------------------------------------------------------
 _neighbors_cache: dict = {}  # identity_id -> (timestamp, results_list)
 _NEIGHBORS_CACHE_TTL: float = 300.0  # 5 minutes
 
 
exec
/bin/zsh -lc "rg -n \"merge_target_id|person/|skip|confirm\\(|batch_gemini|estimate_age_with_gemini|labels_path|skip_existing|max_cost|delay_between\" app/identity_routes.py app/page_routes.py app/components/identity_cards.py app/components/cards.py scripts/batch_gemini_for_person.py tests/test_photo_navigation.py tests/test_skipped_faces.py" in /Users/nolanfox/rhodesli succeeded in 0ms:
app/components/identity_cards.py:191:    # Build face grid for additional faces (skip best since it's shown as main thumbnail)
app/components/identity_cards.py:239:        skip_url = f"{nav_prefix}/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"
app/components/identity_cards.py:257:                hx_post=skip_url,
app/components/identity_cards.py:262:                id="focus-btn-skip",
app/components/identity_cards.py:358:                        href=f"{nav_prefix}/person/{identity_id}",
app/components/identity_cards.py:534:        href=f"{nav_prefix}/person/{identity_id}",
app/components/identity_cards.py:634:        f"{nav_prefix}/person/{identity_id}" if state == "CONFIRMED" else f"{nav_prefix}/identify/{identity_id}"
app/components/identity_cards.py:656:            url=f"{nav_prefix}/person/{identity_id}",
app/components/identity_cards.py:842:                # Pass merge_target_id so confirm also auto-merges
app/components/identity_cards.py:844:                _confirm_url = f"{_confirm_url}{_sep}merge_target_id={match_target_id}"
app/components/identity_cards.py:877:                    hx_post=f"{nav_prefix}/identity/{identity_id}/skip",
tests/test_skipped_faces.py:1:"""Tests for skipped face handling across clustering, UI, and navigation.
tests/test_skipped_faces.py:7:BUG 2: Lightbox face overlays for skipped faces not clickable
tests/test_skipped_faces.py:9:BUG 4: Footer stats exclude skipped from denominator
tests/test_skipped_faces.py:33:    def test_skipped_faces_are_clustering_candidates(self):
tests/test_skipped_faces.py:42:        skipped_face = np.zeros(512, dtype=np.float32)
tests/test_skipped_faces.py:43:        skipped_face[0] = 0.95
tests/test_skipped_faces.py:47:            "skipped_f1": self._make_face("skipped_f1", skipped_face),
tests/test_skipped_faces.py:60:                "skipped-1": {
tests/test_skipped_faces.py:61:                    "identity_id": "skipped-1",
codex
I have enough context now to audit the risky paths systematically.

Plan:
1. Read the current implementations around the changed confirm/merge, person-link, and batch-script code with line numbers.
2. Compare the changed behavior against existing invariants: admin-only mutation, canonical-save paths, merged-identity handling, and source-of-truth rules.
3. Cross-check the updated tests to see which regression paths are still untested.
4. Report findings ordered by severity with exact file references and concrete failure modes.
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '70,340p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
    70	
    71	def _community_from_request(request):
    72	    """Return the community dict from request.state (set by CommunityMiddleware)."""
    73	    return getattr(request.state, "community", None) if request else None
    74	
    75	
    76	@rt("/confirm/{identity_id}")
    77	def post(
    78	    identity_id: str,
    79	    from_focus: bool = False,
    80	    filter: str = "",
    81	    from_person_page: bool = False,
    82	    merge_target_id: str = "",
    83	    sess=None,
    84	    request=None,
    85	):
    86	    """
    87	    Confirm an identity (move from PROPOSED to CONFIRMED).
    88	    When merge_target_id is provided, also auto-merges into that target (FB-004).
    89	    Requires admin.
exec
/bin/zsh -lc "nl -ba scripts/batch_gemini_for_person.py | sed -n '1,260p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
     1	#!/usr/bin/env python3
     2	"""Batch Gemini date estimation for all photos containing specific identities.
     3	
     4	Uses the production _call_gemini_date_estimate() function with:
     5	- GEDCOM genealogical context for identified faces
     6	- Full Supabase logging to gemini_api_calls table
     7	- Prompt manifest tracking
     8	- Retry logic with exponential backoff
     9	- Incremental results saved to date_labels.json
    10	
    11	Usage:
    12	    # Dry run: count photos, show cost estimate
    13	    python scripts/batch_gemini_for_person.py --dry-run \\
    14	        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
    15	        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19
    16	
    17	    # Run estimation for Esther + Albert
    18	    python scripts/batch_gemini_for_person.py \\
    19	        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
    20	        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19 \\
exec
/bin/zsh -lc "nl -ba app/components/identity_cards.py | sed -n '820,900p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '4060,4255p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   820	    )
   821	
   822	    # Triage buttons — visible labeled row for quick review (when show_triage=True)
   823	    triage_section = None
   824	    if show_triage and is_admin and state in ("INBOX", "PROPOSED", "SKIPPED"):
   825	        _triage_pill = "px-5 py-4 sm:px-3 sm:py-1.5 text-sm sm:text-xs font-bold rounded-full transition-all duration-200 min-h-[32px]"
   826	        confirm_url = (
   827	            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
   828	        )
   829	        reject_url = (
   830	            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
   831	        )
   832	
   833	        # FB-004: Show merge context when strong match exists, and wire auto-merge
   834	        best_match = _m._get_best_match_for_identity(identity_id)
   835	        confirm_label = "\u2713 Confirm"
   836	        _confirm_url = confirm_url
   837	        if best_match:
   838	            match_name = best_match.get("target_identity_name", "")
   839	            match_target_id = best_match.get("target_identity_id", "")
 succeeded in 0ms:
  4060	    return (
  4061	        _main_mod.identity_card(
  4062	            updated_identity, crop_files, lane_color="amber", show_actions=True, nav_prefix=nav_prefix
  4063	        ),
  4064	        _main_mod.toast("Moved to Proposed for review.", "success"),
  4065	    )
  4066	
  4067	
  4068	@rt("/inbox/{identity_id}/confirm")
  4069	def post(
  4070	    identity_id: str,
  4071	    from_focus: bool = False,
  4072	    filter: str = "",
  4073	    from_person_page: bool = False,
  4074	    merge_target_id: str = "",
  4075	    sess=None,
  4076	    request=None,
  4077	):
  4078	    """Confirm identity from INBOX state (INBOX -> CONFIRMED). Requires admin.
  4079	    When merge_target_id is provided, also auto-merges into that target (FB-004).
exec
/bin/zsh -lc "nl -ba app/components/cards.py | sed -n '620,700p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba scripts/batch_gemini_for_person.py | sed -n '260,430p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   260	        for pid, photo in photo_list[:10]:
   261	            filename = photo.get("filename", photo.get("path", "unknown"))
   262	            identities_str = ", ".join(photo.get("identities", []))
   263	            logger.info(f"  {pid[:12]}... {filename} [{identities_str}]")
   264	        if len(photo_list) > 10:
   265	            logger.info(f"  ... and {len(photo_list) - 10} more")
   266	        return
   267	
   268	    # Import the production estimation function
   269	    from app.estimate_routes import _call_gemini_date_estimate, _build_gedcom_context_for_photo
   270	
   271	    # Load existing labels for incremental save
   272	    labels_path = Path("rhodesli_ml/data/date_labels.json")
   273	    if labels_path.exists():
   274	        with open(labels_path) as f:
   275	            labels_data = json.load(f)
   276	    else:
   277	        labels_data = {"schema_version": 2, "labels": []}
   278	
   279	    existing_labels = {e["photo_id"]: i for i, e in enumerate(labels_data["labels"])}
 succeeded in 0ms:
   620	
   621	    thumbnail_img = Div(cls="w-16 h-16 sm:w-20 sm:h-20 bg-slate-600 rounded")
   622	    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
   623	    crop_url = None
   624	    best_fid = _m.get_best_face_id(anchor_face_ids) if anchor_face_ids else None
   625	    if best_fid:
   626	        crop_url = _m.resolve_face_image_url(best_fid, crop_files)
   627	    if not crop_url:
   628	        for fid in anchor_face_ids:
   629	            crop_url = _m.resolve_face_image_url(fid, crop_files)
   630	            if crop_url:
   631	                break
   632	    if crop_url:
   633	        thumbnail_img = Img(
   634	            src=crop_url,
   635	            alt=name,
   636	            cls="w-16 h-16 sm:w-20 sm:h-20 object-cover rounded border border-slate-600 hover:scale-105 transition-transform",
   637	            loading="lazy",
   638	        )
   639	
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '2230,2510p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  2230	    from_person_page: bool = False,
  2231	    sess=None,
  2232	    request=None,
  2233	):
  2234	    """
  2235	    Merge source identity into target identity. Requires admin.
  2236	
  2237	    Enhanced behavior:
  2238	    - Auto-corrects merge direction (named identity always survives)
  2239	    - Detects name conflicts (both named) and shows resolution modal
  2240	    - Records merge_history on target for undo capability
  2241	    - Promotes target state if source had higher-trust state
  2242	    """
  2243	    origin_err = _check_origin(request)
  2244	    if origin_err:
  2245	        return origin_err
  2246	    denied = _main_mod._check_admin(sess)
  2247	    if denied:
  2248	        return denied
  2249	    try:
exec
/bin/zsh -lc 'git diff --unified=40 origin/main~12..HEAD -- app/page_routes.py app/compare_routes.py app/components/cards.py app/components/identity_cards.py tests/test_photo_navigation.py tests/test_skipped_faces.py' in /Users/nolanfox/rhodesli succeeded in 0ms:
diff --git a/app/compare_routes.py b/app/compare_routes.py
index 97d5dfa..5cdee03 100644
--- a/app/compare_routes.py
+++ b/app/compare_routes.py
@@ -5847,94 +5847,94 @@ def get(
             Img(
                 src=t_display_url or "",
                 alt=t_name,
                 cls=f"max-w-full {img_h} object-contain rounded cursor-zoom-in transition-transform duration-200",
                 data_compare_zoom="true",
                 **{"_": _zoom_script},
             )
             if t_display_url
             else Div(
                 Span("?", cls="text-6xl text-slate-500"),
                 cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center",
             ),
             cls="flex justify-center bg-slate-700/50 rounded p-2 overflow-hidden",
         )
 
codex
I’m checking the underlying merge/confirm semantics and the surrounding tests now. The main question is whether the new “confirm as X” flow preserves the same guarantees as the existing explicit merge route, or silently bypasses some of them.
exec
/bin/zsh -lc "rg -n \"confirm_and_merge|merge_target_id|inbox_confirm_and_merge|/confirm/|/inbox/.*/confirm|bulk-merge|merge_identities\\(\" tests app | sed -n '1,260p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
tests/test_csrf_protection.py:81:        """POST /confirm/<id> with bad Origin header returns 403."""
tests/test_csrf_protection.py:83:            "/confirm/fake-id",
tests/test_merge_enhancements.py:77:        result = registry.merge_identities(
tests/test_merge_enhancements.py:97:        result = registry.merge_identities(
tests/test_merge_enhancements.py:115:        registry.merge_identities(
tests/test_merge_enhancements.py:269:        result = registry.merge_identities("id-a", "id-b", "test", photo_reg)
tests/test_merge_enhancements.py:293:        registry.merge_identities("source", "target", "test", photo_reg)
tests/test_merge_enhancements.py:321:        result = registry.merge_identities("named", "unnamed", "test", photo_reg)
tests/test_merge_face_transfer.py:3:Root cause: merge_identities() copies faces from source to target in memory,
tests/test_merge_face_transfer.py:55:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:74:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:98:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:109:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:143:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:174:        r1 = registry.merge_identities(a_id, b_id, "test", photo_registry)
tests/test_merge_face_transfer.py:178:        r2 = registry.merge_identities(b_id, c_id, "test", photo_registry)
tests/test_merge_face_transfer.py:234:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
tests/test_merge_face_transfer.py:267:        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
app/main.py:1189:        # When merge_identities() runs, it should transfer all faces from source to
app/main.py:8099:            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
exec
/bin/zsh -lc "nl -ba core/registry.py | sed -n '1965,2145p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1965	                        return val
  1966	                    if isinstance(val, str):
  1967	                        try:
  1968	                            parsed = json.loads(val)
  1969	                            if isinstance(parsed, list):
  1970	                                return parsed
  1971	                        except (json.JSONDecodeError, TypeError):
  1972	                            pass
  1973	                    return []
  1974	
  1975	                identity = {
  1976	                    "identity_id": identity_id,
  1977	                    "name": row.get("name", ""),
  1978	                    "display_name": row.get("display_name"),
  1979	                    "state": row.get("state", "INBOX"),
  1980	                    "anchor_ids": _ensure_list(row.get("anchor_ids", [])),
  1981	                    "candidate_ids": _ensure_list(row.get("candidate_ids", [])),
  1982	                    "negative_ids": _ensure_list(row.get("negative_ids", [])),
  1983	                    "version_id": row.get("version_id", 1),
  1984	                    "created_at": row.get("created_at"),
exec
/bin/zsh -lc "nl -ba core/registry.py | sed -n '1770,1965p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1770	
  1771	        elif target_event["action"] == ActionType.CANDIDATE_ADD.value:
  1772	            face_id = target_event["face_ids"][0]
  1773	            self._remove_candidate_by_face_id(identity, face_id)
  1774	
  1775	        elif target_event["action"] == ActionType.CANDIDATE_REMOVE.value:
  1776	            face_id = target_event["face_ids"][0]
  1777	            if face_id not in self._face_id_set(identity.get("candidate_ids", [])):
  1778	                identity.setdefault("candidate_ids", []).append(face_id)
  1779	
  1780	        elif target_event["action"] == ActionType.NEGATIVE_ADD.value:
  1781	            negative_ref = (target_event.get("metadata") or {}).get("negative_ref")
  1782	            if negative_ref in identity.get("negative_ids", []):
  1783	                identity["negative_ids"].remove(negative_ref)
  1784	
  1785	        elif target_event["action"] == ActionType.REJECT.value:
  1786	            face_id = target_event["face_ids"][0]
  1787	            if face_id in identity["negative_ids"]:
  1788	                identity["negative_ids"].remove(face_id)
  1789	            if face_id not in identity["candidate_ids"]:
exec
/bin/zsh -lc "rg -n \"def merge_identities|class .*Registry|co_occurrence|name_conflict|already_merged|direction_swapped|merged_into\" core app | sed -n '1,260p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "rg -n \"def save_registry|changed_ids|confirmed_identity_info|save_registry\\(\" app/main.py core app | sed -n '1,260p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
app/main.py:1228:                save_registry(registry, changed_ids=repaired_targets)
app/main.py:1710:def save_registry(registry, confirmed_identity_info=None, changed_ids=None):
app/main.py:1719:        confirmed_identity_info: Optional dict with keys:
app/main.py:1724:        changed_ids: Optional set/list of identity IDs that were modified.
app/main.py:1749:        if changed_ids:
app/main.py:1750:            for cid in changed_ids:
app/main.py:1769:        if changed_ids:
app/main.py:1770:            invalidate_cluster_review_caches(changed_ids=changed_ids)
app/main.py:1813:    # FB-069: Only write changed identities to Supabase when changed_ids is provided
app/main.py:1814:    if changed_ids:
app/main.py:1815:        identities_copy = {k: dict(registry._identities[k]) for k in changed_ids if k in registry._identities}
app/main.py:1857:    if confirmed_identity_info:
app/main.py:1885:        threading.Thread(target=_fire_notification, args=(confirmed_identity_info,), daemon=True).start()
app/engagement_routes.py:46:        _main_mod.save_registry(registry, changed_ids={identity_id})
app/engagement_routes.py:437:            _main_mod.save_registry(registry, changed_ids={source_id, target_id})
app/engagement_routes.py:479:            _main_mod.save_registry(registry, changed_ids={source_id})
app/supabase_data.py:6:- All user writes go through save_registry() → this module
app/page_routes.py:5245:            _main_mod.save_registry(registry, confirmed_identity_info=_notify, changed_ids={person_id})
app/upload_routes.py:1003:                    # Supabase which doesn't have them yet. If grouping merges, save_registry()
app/upload_routes.py:1017:                        _main_mod.save_registry(registry)
 succeeded in 0ms:
app/page_routes.py:300:    unid_identities = [i for i in inbox + proposed if not i.get("merged_into")]
app/page_routes.py:463:            and not ident.get("merged_into")
app/page_routes.py:4401:    if identity and identity.get("merged_into"):
app/page_routes.py:4402:        return True, identity["merged_into"]
app/page_routes.py:4516:        if ident.get("merged_into"):
app/page_routes.py:4707:    if identity and identity.get("merged_into"):
app/page_routes.py:4708:        return RedirectResponse(f"{nav_prefix}/identify/{identity['merged_into']}", status_code=301)
app/page_routes.py:6889:        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
app/page_routes.py:8313:        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
app/page_routes.py:9822:    cooccur_path = _main_mod.data_path / "co_occurrence_graph.json"
app/page_routes.py:10274:        if not ident.get("merged_into"):
app/page_routes.py:10318:        if ident and not ident.get("merged_into"):
app/page_routes.py:10808:        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
app/person_routes.py:267:    if identity and identity.get("merged_into"):
app/person_routes.py:268:        canonical_id = identity["merged_into"]
app/person_routes.py:275:            if not target or not target.get("merged_into"):
app/person_routes.py:277:            next_id = target["merged_into"]
app/person_routes.py:715:            json.loads((_main_mod.data_path / "co_occurrence_graph.json").read_text(encoding="utf-8"))
app/person_routes.py:716:            if (_main_mod.data_path / "co_occurrence_graph.json").exists()
app/browse_routes.py:798:    all_confirmed = [i for i in registry.list_identities(state=IdentityState.CONFIRMED) if not i.get("merged_into")]
exec
/bin/zsh -lc "nl -ba core/registry.py | sed -n '496,780p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   496	    def merge_identities(
   497	        self,
   498	        source_id: str,
   499	        target_id: str,
   500	        user_source: str,
   501	        photo_registry: "PhotoRegistry",
   502	        resolved_name: str = None,
   503	        auto_correct_direction: bool = True,
   504	        allow_co_occurrence: bool = False,
   505	    ) -> dict:
   506	        """
   507	        Merge source identity INTO target identity.
   508	
   509	        Safety Foundation: Calls validate_merge() first - merge is blocked if
   510	        the two identities have faces appearing in the same photo.
   511	
   512	        Enhanced behavior:
   513	        - Auto-corrects merge direction (named identity always survives)
   514	        - Detects name conflicts (both identities named) and returns 'name_conflict'
   515	        - Records merge_history on target for undo capability
exec
/bin/zsh -lc "nl -ba app/main.py | sed -n '1710,1895p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1710	def save_registry(registry, confirmed_identity_info=None, changed_ids=None):
  1711	    """Save registry with atomic write + sync to Supabase (AD-135).
  1712	
  1713	    When DATA_SOURCE=postgres (default), writes Supabase synchronously + JSON as backup.
  1714	    When DATA_SOURCE=json (rollback), writes JSON + shadow-writes to Supabase.
  1715	    JSON write is backup only — never read in production (PRD-051).
  1716	
  1717	    Args:
  1718	        registry: The IdentityRegistry to save
  1719	        confirmed_identity_info: Optional dict with keys:
  1720	            - identity_id: str
  1721	            - identity_name: str
  1722	            - user_id: str (Supabase auth user ID of the admin)
  1723	            - user_email: str (email for Resend notification delivery)
  1724	        changed_ids: Optional set/list of identity IDs that were modified.
  1725	            When provided, only these identities are written to Supabase
  1726	            instead of the full batch (~3400 identities). FB-069 performance fix.
  1727	    """
  1728	    global _registry_cache, _registry_cache_key, _registry_cache_ts
  1729	    # Repopulate cache with the registry we just saved (avoid redundant reload)
exec
/bin/zsh -lc "nl -ba tests/test_person_page_actions.py | sed -n '140,220p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba tests/test_cluster_review_routes.py | sed -n '1200,1275p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba tests/test_permissions.py | sed -n '20,70p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba tests/test_csrf_protection.py | sed -n '70,120p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   140	    def test_confirm_from_person_page_returns_status(self, person_page_registries):
   141	        """When from_person_page=true, confirm returns status badge."""
   142	        identity_reg, photo_reg, target_id, source_id = person_page_registries
   143	
   144	        # Create an INBOX identity to confirm
   145	        inbox_id = identity_reg.create_identity(
   146	            anchor_ids=["face_b"],
   147	            user_source="test",
   148	            name="Test Person",
   149	            state=IdentityState.INBOX,
   150	        )
   151	
   152	        with (
   153	            patch("app.main.load_registry", return_value=identity_reg),
   154	            patch("app.main.save_registry"),
   155	            patch("app.main.is_auth_enabled", return_value=False),
   156	        ):
   157	            from app.main import app
   158	
   159	            client = TestClient(app)
 succeeded in 0ms:
  1200	            stack.enter_context(
  1201	                patch("app.identity_routes._main_mod._check_merged_identity", return_value=(False, None))
  1202	            )
  1203	            stack.enter_context(patch("app.identity_routes._main_mod.posthog_capture"))
  1204	            stack.enter_context(patch("app.identity_routes._main_mod.log_user_action"))
  1205	            stack.enter_context(
  1206	                patch(
  1207	                    "app.identity_routes._main_mod.get_current_user",
  1208	                    return_value=MagicMock(id="u1", email="admin@test.com"),
  1209	                )
  1210	            )
  1211	            stack.enter_context(patch("app.identity_routes._main_mod.is_auth_enabled", return_value=True))
  1212	            stack.enter_context(patch("app.identity_routes._main_mod._fire_recalibration_hook"))
  1213	            resp = client.post("/confirm/unid-1?from_person_page=true")
  1214	
  1215	        assert resp.status_code == 200
  1216	        html = resp.text
  1217	        assert "CONFIRMED" in html
  1218	
  1219	    def test_confirm_named_person_page_succeeds(self):
 succeeded in 0ms:
    20	
    21	# ---------------------------------------------------------------------------
    22	# Route lists for matrix testing
    23	# ---------------------------------------------------------------------------
    24	
    25	# Routes that should ALWAYS return 200 (public, no auth needed)
    26	PUBLIC_GET_ROUTES = [
    27	    "/",
    28	    "/health",
    29	]
    30	
    31	# Admin-only POST routes (all use _check_admin)
    32	# Using dummy IDs — the 401/403 check happens before any data lookup
    33	ADMIN_POST_ROUTES = [
    34	    "/confirm/test-id-123",
    35	    "/reject/test-id-123",
    36	    "/api/identity/src-id/reject/tgt-id",
    37	    "/api/identity/src-id/unreject/tgt-id",
    38	    "/api/identity/tgt-id/merge/src-id",
    39	    "/api/identity/test-id-123/rename",
 succeeded in 0ms:
    70	        import app.main
    71	
    72	        # Read the source of main.py and check for same_site="Strict"
    73	        source = inspect.getsource(app.main)
    74	        assert 'same_site="Strict"' in source or "same_site='Strict'" in source
    75	
    76	
    77	class TestCsrfOnProtectedRoutes:
    78	    """Integration tests: POST to protected routes with bad Origin gets 403."""
    79	
    80	    def test_confirm_route_rejects_bad_origin(self, client, auth_disabled):
    81	        """POST /confirm/<id> with bad Origin header returns 403."""
    82	        response = client.post(
    83	            "/confirm/fake-id",
    84	            headers={"Origin": "https://evil-site.com"},
    85	        )
    86	        assert response.status_code == 403
    87	
    88	    def test_reject_route_rejects_bad_origin(self, client, auth_disabled):
    89	        """POST /reject/<id> with bad Origin header returns 403."""
🌐 Searching the web...
🌐 Searched the web
exec
/bin/zsh -lc "rg -n \"inbox/.*/confirm|/identity/.*/skip|/inbox/.*/reject|bad Origin|csrf\" tests/test_csrf_protection.py tests | sed -n '1,220p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
tests/test_csrf_protection.py:78:    """Integration tests: POST to protected routes with bad Origin gets 403."""
tests/test_csrf_protection.py:81:        """POST /confirm/<id> with bad Origin header returns 403."""
tests/test_csrf_protection.py:89:        """POST /reject/<id> with bad Origin header returns 403."""
tests/test_csrf_protection.py:97:        """POST /api/identity/<t>/merge/<s> with bad Origin returns 403."""
tests/test_csrf_protection.py:105:        """POST /api/identity/<id>/rename with bad Origin returns 403."""
tests/test_csrf_protection.py:113:        """POST /api/face/<fid>/detach with bad Origin returns 403."""
tests/test_csrf_protection.py:121:        """POST /api/identity/<id>/skip with bad Origin returns 403."""
tests/test_csrf_protection.py:123:            "/api/identity/fake-id/skip",
tests/test_csrf_protection.py:129:        """POST /api/admin/run-migrations with bad Origin returns 403."""
tests/test_csrf_protection.py:137:        """POST /admin/pending/<id>/approve with bad Origin returns 403."""
tests/test_csrf_protection.py:149:            "/api/identity/fake-id/skip",
tests/test_csrf_protection.py:78:    """Integration tests: POST to protected routes with bad Origin gets 403."""
tests/test_csrf_protection.py:81:        """POST /confirm/<id> with bad Origin header returns 403."""
tests/test_csrf_protection.py:89:        """POST /reject/<id> with bad Origin header returns 403."""
tests/test_csrf_protection.py:97:        """POST /api/identity/<t>/merge/<s> with bad Origin returns 403."""
tests/test_csrf_protection.py:105:        """POST /api/identity/<id>/rename with bad Origin returns 403."""
tests/test_csrf_protection.py:113:        """POST /api/face/<fid>/detach with bad Origin returns 403."""
tests/test_csrf_protection.py:121:        """POST /api/identity/<id>/skip with bad Origin returns 403."""
tests/test_csrf_protection.py:123:            "/api/identity/fake-id/skip",
tests/test_csrf_protection.py:129:        """POST /api/admin/run-migrations with bad Origin returns 403."""
exec
/bin/zsh -lc "rg -n \"_merge_annotations\\(\" app | sed -n '1,120p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
app/engagement_routes.py:979:def _merge_annotations(source_id: str, target_id: str):
app/admin_routes.py:2615:                _main_mod._merge_annotations(s_id, actual_target)
app/identity_routes.py:2379:    _main_mod._merge_annotations(actual_source_id, actual_target_id)
exec
/bin/zsh -lc "nl -ba app/engagement_routes.py | sed -n '960,1025p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   960	            ),
   961	            cls="mt-2",
   962	        ),
   963	        cls="mt-2",
   964	    )
   965	
   966	    pending_badge = (
   967	        Span(f" ({pending_count} pending)", cls="text-amber-400 text-xs") if pending_count and is_admin else None
   968	    )
   969	
   970	    return Div(
   971	        *ann_items,
   972	        form,
   973	        pending_badge,
   974	        id=f"identity-annotations-{identity_id}",
   975	        cls="mt-3 border-t border-slate-700 pt-2" if ann_items else "mt-2",
   976	    )
   977	
   978	
   979	def _merge_annotations(source_id: str, target_id: str):
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '1570,1625p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1570	            status_code=404,
  1571	            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
  1572	        )
  1573	
  1574	    source_id = source_identity["identity_id"]
  1575	    if source_id == target_id:
  1576	        return Response(
  1577	            to_xml(_main_mod.toast("Face already belongs to this identity.", "info")),
  1578	            status_code=200,
  1579	            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
  1580	        )
  1581	
  1582	    # Get target name for toast
  1583	    try:
  1584	        target = registry.get_identity(target_id)
  1585	        target_name = ensure_utf8_display(target.get("name")) or f"Identity {target_id[:8]}..."
  1586	    except KeyError:
  1587	        target_name = f"Identity {target_id[:8]}..."
  1588	
  1589	    # Merge
exec
/bin/zsh -lc "rg -n \"from_person_page=true|person-admin-actions|merge_target_id\" app | sed -n '1,220p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
app/identity_routes.py:82:    merge_target_id: str = "",
app/identity_routes.py:88:    When merge_target_id is provided, also auto-merges into that target (FB-004).
app/identity_routes.py:166:    # FB-004: Auto-merge with best match when merge_target_id provided
app/identity_routes.py:168:    if merge_target_id:
app/identity_routes.py:173:                target_id=merge_target_id,
app/identity_routes.py:193:                    merge_target_id=merge_target_id,
app/identity_routes.py:200:                    merge_target_id[:8],
app/identity_routes.py:207:                    merge_target_id[:8],
app/identity_routes.py:211:            logger.exception("Confirm+merge error: %s -> %s", identity_id[:8], merge_target_id[:8])
app/identity_routes.py:314:        if merge_target_id and (not merge_result or not merge_result.get("success")):
app/identity_routes.py:343:                id="person-admin-actions",
app/identity_routes.py:479:                id="person-admin-actions",
app/identity_routes.py:4074:    merge_target_id: str = "",
app/identity_routes.py:4079:    When merge_target_id is provided, also auto-merges into that target (FB-004).
app/identity_routes.py:4144:    # FB-004: Auto-merge with best match when merge_target_id provided
app/identity_routes.py:4146:    if merge_target_id:
app/identity_routes.py:4151:                target_id=merge_target_id,
app/identity_routes.py:4171:                    merge_target_id=merge_target_id,
app/identity_routes.py:4178:                    merge_target_id[:8],
app/identity_routes.py:4185:                    merge_target_id[:8],
exec
/bin/zsh -lc "rg -n \"@rt\\(\\\"/person/\\{person_id\\}\\\"|def get\\(person_id|identify/\\{person_id\\}|redirect.*identify|state == \\\"CONFIRMED\\\"\" app/person_routes.py app/page_routes.py | sed -n '1,220p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
app/person_routes.py:366:    is_state_confirmed = state == "CONFIRMED"
app/person_routes.py:400:        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))
app/person_routes.py:1279:                            href=f"{nav_prefix}/identify/{person_id}",
app/person_routes.py:1391:                                    if state == "CONFIRMED"
app/person_routes.py:1709:                            href=f"{nav_prefix}/identify/{person_id}",
app/person_routes.py:1772:@rt("/person/{person_id}")
app/person_routes.py:1773:def get(person_id: str, view: str = "faces", sort_by: str = "date_asc", sess=None, request=None):
app/person_routes.py:1811:def get(person_id: str, view: str = "faces", sort_by: str = "date_asc", sess=None, request=None):
app/person_routes.py:1847:        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))
app/page_routes.py:3593:        is_named = ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified")
app/page_routes.py:3751:            elif state == "CONFIRMED":
app/page_routes.py:3789:            if state == "CONFIRMED" and face_identity_id:
app/page_routes.py:3977:            if state == "CONFIRMED":
app/page_routes.py:4522:        if state == "CONFIRMED" and not name.startswith("Unidentified"):
app/page_routes.py:4664:@rt("/identify/{person_id}")
app/page_routes.py:4665:def get(person_id: str, submitted: str = "", name: str = "", sess=None, request=None):
app/page_routes.py:4720:    is_identified = state == "CONFIRMED" and not display_name.startswith("Unidentified")
app/page_routes.py:4863:                            href=f"{nav_prefix}/identify/{person_id}/match/{n_id}",
app/page_routes.py:4944:            hx_post=f"{nav_prefix}/api/identify/{person_id}/respond",
app/page_routes.py:5009:                        hx_post=f"{nav_prefix}/api/identify/{person_id}/respond",
exec
/bin/zsh -lc "nl -ba app/person_routes.py | sed -n '1772,1865p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1772	@rt("/person/{person_id}")
  1773	def get(person_id: str, view: str = "faces", sort_by: str = "date_asc", sess=None, request=None):
  1774	    """
  1775	    Public shareable person page showing all photos of a specific person.
  1776	
  1777	    No authentication required — anyone can view.
  1778	
  1779	    Query params:
  1780	    - view: "faces" (default) or "photos" — gallery view mode
  1781	    - sort_by: date_asc (default), date_desc, uploaded_desc, uploaded_asc
  1782	    """
  1783	    _main_mod.touch_user_activity()  # SWR bot guard (egress reduction)
  1784	    user = get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
  1785	    user_is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
  1786	    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
  1787	
  1788	    # FB-063: If no explicit community prefix was used, auto-detect the person's
  1789	    # primary community and redirect so all links on the page get the right prefix.
  1790	    community_explicit = getattr(request.state, "community_explicit", False) if request else False
  1791	    if not community_explicit and user_is_admin:
exec
/bin/zsh -lc "rg -n \"date_labels|_load_date_labels|save_date_labels|write_date_labels|schema_version\" app rhodesli_ml scripts | sed -n '1,260p'" in /Users/nolanfox/rhodesli succeeded in 3ms:
odesli_ml/data/date_labels.json") -> list[DateLabel]:
rhodesli_ml/data/date_labels.py:109:def load_photo_metadata(path: str = "rhodesli_ml/data/date_labels.json") -> list[PhotoMetadata]:
rhodesli_ml/scripts/clean_labels.py:1:"""Validate and clean date_labels.json.
rhodesli_ml/scripts/clean_labels.py:10:    python rhodesli_ml/scripts/clean_labels.py --path /alt/path/date_labels.json
rhodesli_ml/scripts/clean_labels.py:23:from rhodesli_ml.data.date_labels import VALID_CONTROLLED_TAGS
rhodesli_ml/scripts/clean_labels.py:46:DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "date_labels.json"
rhodesli_ml/scripts/clean_labels.py:62:    """Validate and clean date_labels.json.
rhodesli_ml/scripts/clean_labels.py:65:        labels_path: Path to date_labels.json.
rhodesli_ml/scripts/clean_labels.py:211:        description="Validate and clean date_labels.json"
rhodesli_ml/scripts/clean_labels.py:222:        help=f"Path to date_labels.json (default: {DEFAULT_PATH})",
app/sync_routes.py:364:    accepted_keys = {"identities", "photo_index", "annotations", "photo_locations", "date_labels"}
app/sync_routes.py:464:    # Push date_labels.json
app/sync_routes.py:465:    if body.get("date_labels"):
app/sync_routes.py:466:        dl_data = body["date_labels"]
app/sync_routes.py:468:            return Response("date_labels must be a JSON object", status_code=400)
app/sync_routes.py:470:        fpath = data_path / "date_labels.json"
app/sync_routes.py:471:        backup_path = data_path / f"date_labels.json.bak.{ts}"
app/sync_routes.py:480:        results["date_labels"] = {
rhodesli_ml/scripts/run_evaluation.py:6:        --data rhodesli_ml/data/date_labels.json
rhodesli_ml/scripts/export_search_metadata.py:34:DEFAULT_DATE_LABELS = Path(__file__).resolve().parent.parent / "data" / "date_labels.json"
exec
/bin/zsh -lc "nl -ba app/estimate_routes.py | sed -n '1285,1365p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1285	        photo_id=photo_id,
  1286	        gedcom_context=gedcom_context,
  1287	        call_type="re_analysis",
  1288	        trigger="admin_rerun",
  1289	        photo_metadata=p_metadata,
  1290	    )
  1291	
  1292	    if not result:
  1293	        return Div(
  1294	            P("Gemini analysis failed. Check logs for details.", cls="text-amber-400 text-sm"),
  1295	            data_testid="reanalyze-error",
  1296	        )
  1297	
  1298	    # Extract results
  1299	    new_decade = result.get("estimated_decade")
  1300	    new_year = result.get("best_year_estimate")
  1301	    new_confidence = result.get("confidence", "unknown")
  1302	    location_data = result.get("location", {})
  1303	    new_location = location_data.get("place", "") if isinstance(location_data, dict) else ""
  1304	
exec
/bin/zsh -lc "git diff --unified=10 origin/main~12..HEAD -- app/identity_routes.py | rg '"'^@@|''^diff --git|''^'"\\+{3}|"'^---'"'" in /Users/nolanfox/rhodesli succeeded in 0ms:
diff --git a/app/identity_routes.py b/app/identity_routes.py
--- a/app/identity_routes.py
+++ b/app/identity_routes.py
@@ -72,25 +72,27 @@ def _community_from_request(request):
@@ -154,20 +156,67 @@ def post(
@@ -247,25 +296,37 @@ def post(
@@ -275,42 +336,72 @@ def post(
@@ -544,21 +635,23 @@ def get(
@@ -603,20 +696,25 @@ def get(
@@ -2144,33 +2242,53 @@ def post(
@@ -2189,47 +2307,49 @@ def post(
@@ -2624,27 +2744,40 @@ def post(
@@ -3931,24 +4064,27 @@ def post(identity_id: str, sess=None, request=None):
@@ -3998,25 +4134,84 @@ def post(
@@ -4026,33 +4221,51 @@ def post(
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '725,770p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '630,725p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '3930,4070p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   725	        # Add state for correct section routing in neighbor_card links
   726	        try:
   727	            n_identity = registry.get_identity(n["identity_id"])
   728	            n["state"] = n_identity.get("state", "INBOX")
   729	        except KeyError:
   730	            n["state"] = "INBOX"
   731	
   732	        # Compute co-occurrence: how many photos these two identities share
   733	        n["co_occurrence"] = _main_mod._compute_co_occurrence(identity_id, n["identity_id"], registry, photo_registry)
   734	
   735	        # Enhance blocked merge reason with photo filename
   736	        if not n["can_merge"] and n["merge_blocked_reason"] == "co_occurrence":
   737	            filename = _main_mod.find_shared_photo_filename(identity_id, n["identity_id"], registry, photo_registry)
   738	            if filename:
   739	                n["merge_blocked_reason_display"] = f"Appear together in {filename}"
   740	            else:
   741	                n["merge_blocked_reason_display"] = "Appear together in a photo"
   742	
   743	    # Filter out duplicate face detections: same face detected twice in same photo
   744	    # These show as Dist ~0.00 with co-occurrence (seen together in same photo)
 succeeded in 0ms:
   630	    # Request one extra to determine if more exist (B3: pagination)
   631	    total_to_fetch = offset + limit + 1
   632	    try:
   633	        # Check cache first
   634	        cached = _get_cached_neighbors(identity_id)
   635	        if cached is not None and len(cached) >= total_to_fetch:
   636	            all_neighbors = cached[:total_to_fetch]
   637	            cache_hit = True
   638	        else:
   639	            from app.perf_cache import get_all_neighbors
   640	
   641	            # Use precomputed global embedding matrix (Session 135b)
   642	            # Eliminates 100-200ms matrix construction per request
   643	            # Session 138: Fetch more when community filter is active, since filtering
   644	            # may eliminate most results from the raw pool (Codex P1 finding)
   645	            # FB-008 (Session 142): Fetch 100 base to survive merged_into + negative_ids
   646	            # filtering. ~51% of identities are merged, so 20 was far too few.
   647	            _base_limit = 100 if community_filter in ("same", "cross") else 100
   648	            fetch_limit = max(total_to_fetch, _base_limit)
   649	            all_neighbors = get_all_neighbors(identity_id, limit=fetch_limit)
 succeeded in 0ms:
  3930	        metadata={"route": "detach"},
  3931	    )
  3932	
  3933	    # 1. Get crop files for rendering
  3934	    crop_files = _main_mod.get_crop_files()
  3935	    nav_prefix = _nav_prefix_from_request(request)
  3936	
  3937	    # 2. Render the NEW identity card (detached face's new home)
  3938	    new_identity = registry.get_identity(result["to_identity_id"])
  3939	    new_card_html = _main_mod.identity_card(
  3940	        new_identity,
  3941	        crop_files,
  3942	        lane_color="amber",  # New identities are PROPOSED
  3943	        show_actions=True,
  3944	        nav_prefix=nav_prefix,
  3945	    )
  3946	
  3947	    # 3. Render the UPDATED old identity card (with correct face count)
  3948	    old_identity = registry.get_identity(identity_id)
  3949	    state_colors = {
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '585,635p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   585	                if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
   586	                    identified.add(ident.get("identity_id"))
   587	                elif ident:
   588	                    unidentified += 1
   589	        col_data["identified_count"] = len(identified)
   590	        col_data["unidentified_count"] = unidentified
   591	
   592	    return collections
   593	
   594	
   595	# =============================================================================
   596	# ROUTES - PHASE 3: DISCOVERY & ACTION
   597	# =============================================================================
   598	
   599	
   600	@rt("/api/identity/{identity_id}/neighbors")
   601	def get(
   602	    identity_id: str,
   603	    limit: int = 5,
   604	    offset: int = 0,
exec
/bin/zsh -lc "rg -n \"def public_person_page|is_identified|Help Identify|Unidentified\" app/person_routes.py | sed -n '1,220p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
244:def public_person_page(
367:    is_confirmed = is_state_confirmed and not display_name.startswith("Unidentified")
399:        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
400:        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))
580:            if other_state != "CONFIRMED" or other_name.startswith("Unidentified"):
1708:                            "Help Identify",
1846:        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
1847:        return not (ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified"))
exec
/bin/zsh -lc "nl -ba app/person_routes.py | sed -n '244,390p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   244	def public_person_page(
   245	    person_id: str,
   246	    view: str = "faces",
   247	    sort_by: str = "date_asc",
   248	    user=None,
   249	    is_admin: bool = False,
   250	    community_slug: str = "rhodes",
   251	) -> tuple:
   252	    """
   253	    Build the public shareable person page.
   254	
   255	    Shows all photos of a specific identified person — the page you share
   256	    when you want to say "Look at all these photos of Aunt Selma!"
   257	    No authentication required.
   258	    """
   259	    registry = _main_mod.load_registry()
   260	    nav_prefix = _main_mod.community_url_prefix(community_slug)
   261	    try:
   262	        identity = registry.get_identity(person_id)
   263	    except KeyError:
codex
The main failure modes are clear from the code paths, but I’m running the directly changed tests plus a couple of confirm-route suites to verify what is and isn’t covered in practice.
exec
/bin/zsh -lc 'test -d venv && echo venv-present || echo no-venv' in /Users/nolanfox/rhodesli succeeded in 0ms:
venv-present
exec
/bin/zsh -lc 'pytest -q tests/test_photo_navigation.py tests/test_skipped_faces.py tests/test_person_page_actions.py tests/test_cluster_review_routes.py -q' in /Users/nolanfox/rhodesli exited 2 in 1.63s:

==================================== ERRORS ====================================
______________ ERROR collecting tests/test_person_page_actions.py ______________
ImportError while importing test module '/Users/nolanfox/rhodesli/tests/test_person_page_actions.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_person_page_actions.py:14: in <module>
    from fasthtml.common import to_xml
E   ModuleNotFoundError: No module named 'fasthtml'
_____________ ERROR collecting tests/test_cluster_review_routes.py _____________
ImportError while importing test module '/Users/nolanfox/rhodesli/tests/test_cluster_review_routes.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_cluster_review_routes.py:13: in <module>
codex
The first pytest run hit the system interpreter, so it stopped at import-time before exercising anything. I’m rerunning inside the project `venv` to get the actual coverage picture for these routes.
exec
/bin/zsh -lc 'source venv/bin/activate && pytest -q tests/test_photo_navigation.py tests/test_skipped_faces.py tests/test_person_page_actions.py tests/test_cluster_review_routes.py -q' in /Users/nolanfox/rhodesli succeeded in 6.89s:
........................................................................ [ 82%]
...............                                                          [100%]
=============================== warnings summary ===============================
tests/test_photo_navigation.py::TestPhotoNavUrl::test_first_photo_has_next_only
  /Users/nolanfox/rhodesli/venv/lib/python3.11/site-packages/starlette/applications.py:161: DeprecationWarning: The `exception_handler` decorator is deprecated, and will be removed in version 1.0.0. Refer to https://starlette.dev/exceptions/ for the recommended approach.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
codex
I want one concrete check on the CSRF concern rather than leaving it as pure inference, so I’m probing the two confirm routes under a bad `Origin` header with the registry/admin pieces patched out.
exec
/bin/zsh -lc "source venv/bin/activate && python - <<'PY'
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

fake_registry = MagicMock()
fake_registry.get_identity.return_value = {\"identity_id\": \"x\", \"name\": \"X\", \"state\": \"INBOX\", \"anchor_ids\": [], \"candidate_ids\": []}

with patch('app.identity_routes._main_mod._check_admin', return_value=None), \\
     patch('app.identity_routes._main_mod.load_registry', return_value=fake_registry), \\
     patch('app.identity_routes._main_mod._check_merged_identity', return_value=(False, None)), \\
     patch('app.identity_routes._main_mod.save_registry'), \\
     patch('app.identity_routes._main_mod.is_auth_enabled', return_value=False):
    r_inbox = client.post('/inbox/x/confirm', headers={'Origin': 'https://evil.example'})

with patch('app.identity_routes._main_mod._check_admin', return_value=None), \\
     patch('app.identity_routes._main_mod.load_registry', return_value=fake_registry), \\
     patch('app.identity_routes._main_mod._check_merged_identity', return_value=(False, None)), \\
     patch('app.identity_routes._main_mod.save_registry'), \\
     patch('app.identity_routes._main_mod.posthog_capture'), \\
     patch('app.identity_routes._main_mod.log_user_action'), \\
     patch('app.identity_routes._main_mod.is_auth_enabled', return_value=False):
    r_confirm = client.post('/confirm/x', headers={'Origin': 'https://evil.example'})

print('inbox_confirm', r_inbox.status_code)
print('confirm', r_confirm.status_code)
PY" in /Users/nolanfox/rhodesli succeeded in 4.78s:
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.l1dcachesize'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.l2cachesize'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.l3cachesize'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.sse4_2'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx1_0'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx2_0'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.bmi1'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.bmi2'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx512f'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx512cd'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx512dq'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx512bw'. Detail: [errno 1] Operation not permitted
/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: IOError: sysctlbyname failed for 'hw.optional.avx512vl'. Detail: [errno 1] Operation not permitted
Supabase community lookup failed for 'rhodes': [Errno 8] nodename nor servname provided, or not known
Supabase audit log sync failed: [Errno 8] nodename nor servname provided, or not known
audit_log write failed: action=confirm entity=x
Traceback (most recent call last):
  File "/Users/nolanfox/rhodesli/venv/lib/python3.11/site-packages/httpx/_transports/default.py", line 101, in map_httpcore_exceptions
    yield
  File "/Users/nolanfox/rhodesli/venv/lib/python3.11/site-packages/httpx/_transports/default.py", line 250, in handle_request
exec
/bin/zsh -lc "nl -ba app/supabase_data.py | sed -n '910,965p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   910	            "scene_description": label_data.get("scene_description"),
   911	            "model": label_data.get("model"),
   912	            "prompt_version": label_data.get("prompt_version"),
   913	            "reanalyzed_at": label_data.get("reanalyzed_at"),
   914	            "location_evidence": label_data.get("location_estimate"),
   915	            "gemini_raw_location": label_data.get("gemini_raw_location"),
   916	        }
   917	        client.table("date_labels").upsert(row, on_conflict="photo_id").execute()
   918	        logger.debug(f"Synced date label for {photo_id}")
   919	    except _SUPABASE_ERRORS as e:
   920	        logger.warning(f"Supabase date label sync failed for {photo_id}: {e}")
   921	
   922	
   923	def sync_date_labels_batch(labels_list: list) -> int:
   924	    """Upsert a batch of date labels. Returns count written."""
   925	    client = get_supabase_client()
   926	    if not client:
   927	        return 0
   928	
   929	    written = 0
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '2368,2385p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  2368	        new_value={"merged_into": actual_target_id, "faces_merged": result.get("faces_merged", 0)},
  2369	        metadata={"route": "merge_search", "user_source": user_source, "override_co_occurrence": allow_co_occurrence},
  2370	    )
  2371	
  2372	    # AD-150: Fire recalibration hook (best-effort, non-blocking)
  2373	    try:
  2374	        _main_mod._fire_recalibration_hook("merge", actual_target_id, actual_source_id)
  2375	    except Exception:
  2376	        pass  # Never block merge on calibration
  2377	
  2378	    # BE-006: Retarget annotations from source to target
  2379	    _main_mod._merge_annotations(actual_source_id, actual_target_id)
  2380	
  2381	    crop_files = _main_mod.get_crop_files()
  2382	    updated_identity = registry.get_identity(actual_target_id)
  2383	    target_name = ensure_utf8_display(updated_identity.get("name")) or "identity"
  2384	    is_unnamed = target_name.startswith("Unidentified") or target_name.startswith("identity")
  2385	
exec
/bin/zsh -lc "nl -ba app/main.py | sed -n '2294,2360p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  2294	def _load_date_labels() -> dict:
  2295	    """Load date labels from ML pipeline output, keyed by photo_id for O(1) lookup.
  2296	
  2297	    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
  2298	    When DATA_SOURCE=json (default), loads from JSON file.
  2299	
  2300	    Labels are indexed by BOTH their original photo_index ID (e.g. inbox_*)
  2301	    AND the SHA256 cache ID used by _photo_cache. This dual-keying handles
  2302	    the ID mismatch between photo_index.json and the embeddings-based cache.
  2303	    """
  2304	    global _date_labels_cache
  2305	    if _date_labels_cache is not None:
  2306	        return _date_labels_cache
  2307	
  2308	    if DATA_SOURCE == "postgres":
  2309	        try:
  2310	            from app.supabase_data import load_date_labels_from_supabase
  2311	
  2312	            result = load_date_labels_from_supabase()
  2313	            if result is not None:
exec
/bin/zsh -lc "rg -n \"merge_target_id|batch_gemini_for_person|sync_date_labels_batch|inbox/.*/confirm.*Origin|confirm as\" tests | sed -n '1,200p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
tests/test_supabase_migration.py:27:    sync_date_labels_batch,
tests/test_supabase_migration.py:96:            count = sync_date_labels_batch(labels)
tests/test_supabase_migration.py:101:            assert sync_date_labels_batch([{"photo_id": "p1"}]) == 0
tests/test_supabase_migration.py:106:            count = sync_date_labels_batch(labels)
tests/test_data_parity_invariants.py:197:        """Estimate routes must call sync_date_label or sync_date_labels_batch."""
exec
/bin/zsh -lc "nl -ba tests/test_data_parity_invariants.py | sed -n '180,215p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   180	            "new identities from uploads must be assigned to their community"
   181	        )
   182	
   183	    def test_sync_push_writes_photo_communities(self):
   184	        """Sync push must call add_photo_to_community."""
   185	        import app.sync_routes
   186	
   187	        source = inspect.getsource(app.sync_routes)
   188	        assert "add_photo_to_community" in source, (
   189	            "sync_routes must call add_photo_to_community — pushed photos must be assigned to their community"
   190	        )
   191	
   192	
   193	class TestDateEstimationSyncsToSupabase:
   194	    """Date estimation must sync results to Supabase."""
   195	
   196	    def test_estimate_routes_syncs_date_labels(self):
   197	        """Estimate routes must call sync_date_label or sync_date_labels_batch."""
   198	        import app.estimate_routes
   199	
exec
/bin/zsh -lc "rg -n \"def identity_card\\(|from_focus=true|show_triage\" app/main.py app/components/identity_cards.py tests/test_triage.py | sed -n '1,240p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
tests/test_triage.py:493:        assert "/identity/abc123/skip?from_focus=true&amp;filter=ready" in html
tests/test_triage.py:503:        assert "/inbox/abc123/confirm?from_focus=true&amp;filter=rediscovered" in html
tests/test_triage.py:513:        assert "/inbox/abc123/reject?from_focus=true&amp;filter=unmatched" in html
tests/test_triage.py:523:        assert "/identity/abc123/skip?from_focus=true" in html
app/components/identity_cards.py:237:        confirm_url = f"{base_confirm_url}?from_focus=true{_filter_suffix}"
app/components/identity_cards.py:238:        reject_url = f"{base_reject_url}?from_focus=true{_filter_suffix}"
app/components/identity_cards.py:239:        skip_url = f"{nav_prefix}/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"
app/components/identity_cards.py:277:                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
app/components/identity_cards.py:298:                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
app/components/identity_cards.py:374:                            "hx_get": f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
app/components/identity_cards.py:440:    """Deprecated: delegates to identity_card(show_triage=True) for backward compat."""
app/components/identity_cards.py:441:    return identity_card(identity, crop_files, show_triage=True, is_admin=is_admin)
app/components/identity_cards.py:449:def identity_card(
app/components/identity_cards.py:455:    show_triage: bool = False,
app/components/identity_cards.py:822:    # Triage buttons — visible labeled row for quick review (when show_triage=True)
app/components/identity_cards.py:824:    if show_triage and is_admin and state in ("INBOX", "PROPOSED", "SKIPPED"):
app/main.py:5844:                show_triage=True,
app/main.py:6563:            hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true&focus_section=skipped",
app/main.py:7158:                hx_post=f"{nav_prefix}/api/identity/{target_id}/merge/{identity_id}?from_focus=true&focus_section=skipped",
app/main.py:8303:        _focus_p = f"&from_focus=true{_focus_section_p}" if from_focus else ""
exec
/bin/zsh -lc "nl -ba app/components/identity_cards.py | sed -n '220,260p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   220	                face_previews.append(
   221	                    Img(
   222	                        src=crop_url,
   223	                        cls="w-16 h-16 rounded object-cover border border-slate-600",
   224	                        alt=f"Face {face_id[:8]}",
   225	                    )
   226	                )
   227	
   228	    # Action buttons - only for admins
   229	    if is_admin:
   230	        base_confirm_url = (
   231	            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
   232	        )
   233	        base_reject_url = (
   234	            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
   235	        )
   236	        _filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
   237	        confirm_url = f"{base_confirm_url}?from_focus=true{_filter_suffix}"
   238	        reject_url = f"{base_reject_url}?from_focus=true{_filter_suffix}"
   239	        skip_url = f"{nav_prefix}/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"
codex
I’ve got the actionable defects. I’m grabbing exact line numbers for the supporting refs, then I’ll write the audit in severity order with the residual coverage gaps called out separately.
exec
/bin/zsh -lc "nl -ba tests/test_photo_navigation.py | sed -n '390,425p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   390	    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
   391	    @patch("app.main.load_registry")
   392	    def test_confirmed_face_navigates_not_tags(self, mock_reg, mock_dim, mock_meta):
   393	        """Clicking a confirmed face should navigate to identity card, not open tag dialog."""
   394	        from app.main import photo_view_content, to_xml
   395	
   396	        mock_meta.return_value = {
   397	            "filename": "test.jpg",
   398	            "faces": [{"face_id": "f1", "bbox": [10, 10, 100, 100]}],
   399	            "source": "Test",
   400	        }
   401	        mock_identity = {
   402	            "identity_id": "id1",
   403	            "name": "Leon Capeluto",
   404	            "state": "CONFIRMED",
   405	            "anchor_ids": ["f1"],
   406	            "candidate_ids": [],
   407	            "negative_ids": [],
   408	        }
   409	        mock_reg_inst = MagicMock()
exec
/bin/zsh -lc "nl -ba tests/test_skipped_faces.py | sed -n '270,295p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   270	        from app.main import load_registry
   271	        from core.registry import IdentityState
   272	
   273	        registry = load_registry()
   274	
   275	        # Find a confirmed identity to test neighbors endpoint
   276	        confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
   277	        if not confirmed:
   278	            pytest.skip("No confirmed identities available")
   279	
   280	        identity_id = confirmed[0]["identity_id"]
   281	        response = client.get(f"/api/identity/{identity_id}/neighbors")
   282	        assert response.status_code == 200
   283	        text = response.text
   284	
   285	        # Neighbor cards should link to /person/{uuid}, not to review grid
   286	        if "neighbor-" in text:
   287	            assert "/person/" in text, "Neighbor links should point to person detail page"
   288	            # Must NOT use old review grid anchor pattern
   289	            assert "section=to_review&amp;view=browse#identity-" not in text, (
exec
/bin/zsh -lc "nl -ba app/estimate_routes.py | sed -n '1334,1359p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
  1334	            if visible_text:
  1335	                new_entry["visible_text"] = visible_text
  1336	            # Replace existing entry or append
  1337	            replaced = False
  1338	            for i, lbl in enumerate(labels_list):
  1339	                if lbl.get("photo_id") == photo_id:
  1340	                    labels_list[i] = {**lbl, **new_entry}
  1341	                    replaced = True
  1342	                    break
  1343	            if not replaced:
  1344	                labels_list.append(new_entry)
  1345	            all_labels["labels"] = labels_list
  1346	            date_labels_path.write_text(_json.dumps(all_labels, indent=2, ensure_ascii=False))
  1347	            # Invalidate cache — MUST invalidate page_routes cache directly
  1348	            _main_mod._date_labels_cache = None
  1349	            try:
  1350	                from app import page_routes as _pr
  1351	
  1352	                _pr._date_labels_cache = None
  1353	            except Exception:
exec
/bin/zsh -lc "nl -ba app/identity_routes.py | sed -n '220,305p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba core/registry.py | sed -n '668,676p'" in /Users/nolanfox/rhodesli succeeded in 0ms:
   668	                target.setdefault("negative_ids", []).append(negative)
   669	                negatives_added.append(negative)
   670	
   671	        # Mark source as merged (soft delete)
   672	        now = datetime.now(timezone.utc).isoformat()
   673	        source["merged_into"] = actual_target_id
   674	        source["updated_at"] = now
   675	
   676	        # State promotion: target gets max(target.state, source.state)
 succeeded in 0ms:
   220	    # PRD-049: Post-confirm re-matching — find new proposals for confirmed identity
   221	    try:
   222	        import threading
   223	
   224	        def _post_confirm_rematch(iid, data_path):
   225	            try:
   226	                from core.cross_batch_matching import find_cross_batch_matches
   227	                from scripts.cluster_new_faces import load_face_data, load_identities
   228	
   229	                identities_data = load_identities(data_path)
   230	                face_data_dict = load_face_data(data_path)
   231	                photo_reg = _main_mod.load_photo_registry()
   232	                confirmed_identity = identities_data.get("identities", {}).get(iid, {})
   233	                confirmed_face_ids = []
   234	                for fid in confirmed_identity.get("anchor_ids", []):
   235	                    if isinstance(fid, str):
   236	                        confirmed_face_ids.append(fid)
   237	
   238	                if not confirmed_face_ids:
   239	                    return
codex
**Findings**
- `P1` The new inbox confirm path is CSRF-exposed. [app/identity_routes.py#L4068](/Users/nolanfox/rhodesli/app/identity_routes.py#L4068) goes straight into admin/state mutation and now accepts `merge_target_id`, but unlike [app/identity_routes.py#L76](/Users/nolanfox/rhodesli/app/identity_routes.py#L76) it never calls `_check_origin()`. I reproduced this with a bad `Origin`: `/inbox/x/confirm` returned `200`, while `/confirm/x` returned `403`. With Session 142’s new parameter, that cross-site POST can confirm-and-merge inbox identities.

- `P1` The new “Confirm as X” flow bypasses the normal merge side effects that preserve related data. Both auto-merge branches at [app/identity_routes.py#L166](/Users/nolanfox/rhodesli/app/identity_routes.py#L166) and [app/identity_routes.py#L4144](/Users/nolanfox/rhodesli/app/identity_routes.py#L4144) call `registry.merge_identities()` and save, but they never run the explicit merge cleanup at [app/identity_routes.py#L2372](/Users/nolanfox/rhodesli/app/identity_routes.py#L2372), especially `_fire_recalibration_hook("merge", ...)` and `_merge_annotations(...)`. Result: contributor annotations stay attached to the absorbed source identity, and merge lineage recalibration is skipped, even though the UI presents this as a normal merge.

- `P1` The new batch Gemini script is disconnected from the canonical date-label store. It only reads existing labels from local JSON at [scripts/batch_gemini_for_person.py#L161](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L161) and only writes local JSON at [scripts/batch_gemini_for_person.py#L272](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L272). In postgres mode the app reads Supabase first at [app/main.py#L2308](/Users/nolanfox/rhodesli/app/main.py#L2308), and there is already a batch sync helper at [app/supabase_data.py#L923](/Users/nolanfox/rhodesli/app/supabase_data.py#L923). So `--skip-existing` can miss canonical labels, and successful batch runs may never show up in the live app.

- `P2` `POST /confirm/{id}?merge_target_id=...` still launches post-confirm rematching on the original source ID after that identity has been merged away. The merge happens at [app/identity_routes.py#L166](/Users/nolanfox/rhodesli/app/identity_routes.py#L166), but the background worker is always started with `args=(identity_id, ...)` at [app/identity_routes.py#L220](/Users/nolanfox/rhodesli/app/identity_routes.py#L220). Since merge marks the source as `merged_into` without clearing its face lists at [core/registry.py#L671](/Users/nolanfox/rhodesli/core/registry.py#L671), this worker can emit new proposals for a non-canonical identity and write them from a stale JSON snapshot.

- `P2` The batch script rewrites `date_labels.json` destructively and without any write-safety. Existing entries are replaced wholesale at [scripts/batch_gemini_for_person.py#L362](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L362), unlike the existing estimate flow which merges with the prior row at [app/estimate_routes.py#L1337](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1337). It then rewrites the whole file with plain `open(..., "w")` at [scripts/batch_gemini_for_person.py#L373](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L373) and [scripts/batch_gemini_for_person.py#L384](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L384), so reruns can drop manual fields and interrupted/concurrent runs can leave truncated JSON.

**Coverage gaps**
- No test in the changed suite exercises `merge_target_id`, bad-origin handling on `/inbox/{identity_id}/confirm`, or the new batch script. The Session 142 test edits in [tests/test_photo_navigation.py#L392](/Users/nolanfox/rhodesli/tests/test_photo_navigation.py#L392) and [tests/test_skipped_faces.py#L280](/Users/nolanfox/rhodesli/tests/test_skipped_faces.py#L280) only verify navigation changes, so the state-mutating regressions above were not catchable there.

**Verification**
- Ran `source venv/bin/activate && pytest -q tests/test_photo_navigation.py tests/test_skipped_faces.py tests/test_person_page_actions.py tests/test_cluster_review_routes.py -q` and it passed.
- Also manually probed bad-`Origin` behavior for `/inbox/x/confirm` vs `/confirm/x`; the inbox route accepted the request, the normal confirm route rejected it.
tokens used
396,106
**Findings**
- `P1` The new inbox confirm path is CSRF-exposed. [app/identity_routes.py#L4068](/Users/nolanfox/rhodesli/app/identity_routes.py#L4068) goes straight into admin/state mutation and now accepts `merge_target_id`, but unlike [app/identity_routes.py#L76](/Users/nolanfox/rhodesli/app/identity_routes.py#L76) it never calls `_check_origin()`. I reproduced this with a bad `Origin`: `/inbox/x/confirm` returned `200`, while `/confirm/x` returned `403`. With Session 142’s new parameter, that cross-site POST can confirm-and-merge inbox identities.

- `P1` The new “Confirm as X” flow bypasses the normal merge side effects that preserve related data. Both auto-merge branches at [app/identity_routes.py#L166](/Users/nolanfox/rhodesli/app/identity_routes.py#L166) and [app/identity_routes.py#L4144](/Users/nolanfox/rhodesli/app/identity_routes.py#L4144) call `registry.merge_identities()` and save, but they never run the explicit merge cleanup at [app/identity_routes.py#L2372](/Users/nolanfox/rhodesli/app/identity_routes.py#L2372), especially `_fire_recalibration_hook("merge", ...)` and `_merge_annotations(...)`. Result: contributor annotations stay attached to the absorbed source identity, and merge lineage recalibration is skipped, even though the UI presents this as a normal merge.

- `P1` The new batch Gemini script is disconnected from the canonical date-label store. It only reads existing labels from local JSON at [scripts/batch_gemini_for_person.py#L161](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L161) and only writes local JSON at [scripts/batch_gemini_for_person.py#L272](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L272). In postgres mode the app reads Supabase first at [app/main.py#L2308](/Users/nolanfox/rhodesli/app/main.py#L2308), and there is already a batch sync helper at [app/supabase_data.py#L923](/Users/nolanfox/rhodesli/app/supabase_data.py#L923). So `--skip-existing` can miss canonical labels, and successful batch runs may never show up in the live app.

- `P2` `POST /confirm/{id}?merge_target_id=...` still launches post-confirm rematching on the original source ID after that identity has been merged away. The merge happens at [app/identity_routes.py#L166](/Users/nolanfox/rhodesli/app/identity_routes.py#L166), but the background worker is always started with `args=(identity_id, ...)` at [app/identity_routes.py#L220](/Users/nolanfox/rhodesli/app/identity_routes.py#L220). Since merge marks the source as `merged_into` without clearing its face lists at [core/registry.py#L671](/Users/nolanfox/rhodesli/core/registry.py#L671), this worker can emit new proposals for a non-canonical identity and write them from a stale JSON snapshot.

- `P2` The batch script rewrites `date_labels.json` destructively and without any write-safety. Existing entries are replaced wholesale at [scripts/batch_gemini_for_person.py#L362](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L362), unlike the existing estimate flow which merges with the prior row at [app/estimate_routes.py#L1337](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1337). It then rewrites the whole file with plain `open(..., "w")` at [scripts/batch_gemini_for_person.py#L373](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L373) and [scripts/batch_gemini_for_person.py#L384](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L384), so reruns can drop manual fields and interrupted/concurrent runs can leave truncated JSON.

**Coverage gaps**
- No test in the changed suite exercises `merge_target_id`, bad-origin handling on `/inbox/{identity_id}/confirm`, or the new batch script. The Session 142 test edits in [tests/test_photo_navigation.py#L392](/Users/nolanfox/rhodesli/tests/test_photo_navigation.py#L392) and [tests/test_skipped_faces.py#L280](/Users/nolanfox/rhodesli/tests/test_skipped_faces.py#L280) only verify navigation changes, so the state-mutating regressions above were not catchable there.

**Verification**
- Ran `source venv/bin/activate && pytest -q tests/test_photo_navigation.py tests/test_skipped_faces.py tests/test_person_page_actions.py tests/test_cluster_review_routes.py -q` and it passed.
- Also manually probed bad-`Origin` behavior for `/inbox/x/confirm` vs `/confirm/x`; the inbox route accepted the request, the normal confirm route rejected it.
