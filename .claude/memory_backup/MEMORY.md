# Rhodesli Project Memory

## User
- [user_fox_family_names.md](user_fox_family_names.md) — Correct spellings: Esther Burd (B-U-R-D), Albert Fox, Charles Fox, Roland Fox
- [user_voice_mode.md](user_voice_mode.md) — Voice dictation yields stream-of-consciousness; distill into structured FB items

## CRITICAL: Memory Protection
- [feedback_memory_protection.md](feedback_memory_protection.md) — Never delete topic files. Trim index entries only. Back up to git.

## CRITICAL Feedback (behavioral rules)
- [feedback_data_repair_protocol.md](feedback_data_repair_protocol.md) — Per-step snapshots, dry-run, restore script. User demands reversibility.
- [feedback_merge_orphan_crisis.md](feedback_merge_orphan_crisis.md) — Never declare data fix done without browser-verifying the SPECIFIC affected page
- [feedback_screenshot_evaluation.md](feedback_screenshot_evaluation.md) — Evaluate ALL visible issues in every screenshot, not just what user mentions
- [feedback_browser_verification_thoroughness.md](feedback_browser_verification_thoroughness.md) — Check ALL admin surfaces after deploy, not just changed pages
- [feedback_never_modify_production_data.md](feedback_never_modify_production_data.md) — ABSOLUTE: never click action buttons on production. READ-ONLY.
- [feedback_never_claim_fixed.md](feedback_never_claim_fixed.md) — Never claim fixed without production browser verification
- [feedback_platform_reliability.md](feedback_platform_reliability.md) — Data integrity and reliability trump all new features
- [feedback_implicit_harness.md](feedback_implicit_harness.md) — Harness compliance is DEFAULT — user should never repeat standard instructions
- [feedback_fox_family_relations.md](feedback_fox_family_relations.md) — Definitive Fox siblings from 1894 Minsk list. Rose Scheckzner = Harry's WIFE.
- [feedback_reva_heft_correction.md](feedback_reva_heft_correction.md) — Reva Heft = Meyer's wife (mother), NOT Irving's wife. Verify GEDCOM before stating relations.
- [feedback_face_photo_mapping.md](feedback_face_photo_mapping.md) — Face IDs (inbox_*) vs photo URLs (SHA256) differ. Hash-verify before mutations.
- [feedback_feedback_persistence.md](feedback_feedback_persistence.md) — Write all feedback to disk via background subagents immediately
- [feedback_mobile_usability_critical.md](feedback_mobile_usability_critical.md) — App "almost unusable" on mobile. Blocks adoption. Trumps new features.
- [feedback_confirm_merge_needs_prd.md](feedback_confirm_merge_needs_prd.md) — Complex workflow changes need PRD, not inline fixes
- [feedback_audit_logging_critical.md](feedback_audit_logging_critical.md) — All identity mutations need audit_log rows (AUDIT-001, P0)
- [feedback_user_action_audit.md](feedback_user_action_audit.md) — Every user interaction logged to Supabase (proposals shown, actions, navigation)

## Feedback (operational)
- [feedback_ai_tool_audit.md](feedback_ai_tool_audit.md) — Every session using Codex/Antigravity must log findings + value rating
- [feedback_hooks_dont_block.md](feedback_hooks_dont_block.md) — Hooks must exit 2 to block; exit 0 is advisory only
- [feedback_hook_modes.md](feedback_hook_modes.md) — 3 modes (implementation/interactive/continuation) via `.claude/session_mode.txt`
- [feedback_hooks_friction.md](feedback_hooks_friction.md) — Hooks cause friction at session end; need continuation vs full-end distinction
- [feedback_stop_hook_nonsession.md](feedback_stop_hook_nonsession.md) — Stop hook fires in ad-hoc conversations; needs escape hatch
- [feedback_counter_file_handling.md](feedback_counter_file_handling.md) — Never commit commits_since_clear.txt
- [feedback_retry_tools.md](feedback_retry_tools.md) — Never give up on Chrome/MCP tools after first failure — retry, persist
- [feedback_codex_audit_mandate.md](feedback_codex_audit_mandate.md) — Every session with code changes must include security audit phase
- [feedback_codex_iteration.md](feedback_codex_iteration.md) — Use Codex to audit plans BEFORE and outcomes AFTER. Iterate.
- [feedback_antigravity_cli.md](feedback_antigravity_cli.md) — Antigravity for visual/design only, not logic/data
- [feedback_antigravity_constraints.md](feedback_antigravity_constraints.md) — Never touch data/ files, never --no-verify, scope explicitly
- [feedback_gemini_model_version.md](feedback_gemini_model_version.md) — Always use most recent Gemini model. Log downgrades.
- [feedback_gemini_face_coordinates.md](feedback_gemini_face_coordinates.md) — Always include bbox coordinates in Gemini face calls
- [feedback_supabase_local_access.md](feedback_supabase_local_access.md) — Always load_dotenv() before querying Supabase locally
- [feedback_browser_vs_api.md](feedback_browser_vs_api.md) — Chrome for testing/verification; API/scripts for analysis
- [feedback_remote_session_workflow.md](feedback_remote_session_workflow.md) — tmux + /rc for remote iOS sessions; set interactive mode
- [feedback_upload_ux_issues.md](feedback_upload_ux_issues.md) — Upload broken 6 times. Consider removing approval gate.
- [feedback_clustering_cross_batch.md](feedback_clustering_cross_batch.md) — Cross-batch matching (PRD-049) is #1 ML gap
- [feedback_james_fields_ux.md](feedback_james_fields_ux.md) — 9 bugs from Session 109b triage
- [feedback_notification_ux.md](feedback_notification_ux.md) — Too many surfaces; need single high-signal inbox PRD
- [feedback_cluster_splitting_ux.md](feedback_cluster_splitting_ux.md) — No way to split contaminated clusters. Needs PRD. BACKLOG UX-130.
- [feedback_collage_same_photo_override.md](feedback_collage_same_photo_override.md) — Co-occurrence false positives on collages need override
- [feedback_comparison_workflow.md](feedback_comparison_workflow.md) — Manual comparison should be an admin UI tool
- [feedback_complete_ml_pipeline.md](feedback_complete_ml_pipeline.md) — Don't stop at dry-run. Execute full pipeline end-to-end.
- [feedback_identification_methodology.md](feedback_identification_methodology.md) — Event context > embedding distance for identification. Full-collection clustering, not filtered. Verify genealogical data.

## Project State
- [project_supabase_egress.md](project_supabase_egress.md) — Upgraded to Pro for 1 month; TTL reductions should allow downgrade back to free
- [project_fox_sibling_resemblance.md](project_fox_sibling_resemblance.md) — Albert/Harry indistinguishable by ML. Need temporal + co-occurrence.
- [project_active_learning_opportunity.md](project_active_learning_opportunity.md) — PRD-038 gates closed. ~8 confirmed Fox people may suffice to test.
- [project_reranker_revisit.md](project_reranker_revisit.md) — Zero improvement at current scale. Revisit at 50+ confirmed Fox or 200+ total.
- [project_parallel_agent_strategy.md](project_parallel_agent_strategy.md) — Subagents for bug fixes, agent teams for multi-module features
- [project_ml_service_railway.md](project_ml_service_railway.md) — Service ID, rootDirectory config, env vars, troubleshooting
- [project_session130_findings.md](project_session130_findings.md) — identity_overrides startup bug + 212 missing photo_faces rows (both fixed)
- [project_upload_testing_reminder.md](project_upload_testing_reminder.md) — AD-229: 1/3 uploads done, 0/1 cosine comparison (as of 2026-03-19)
- [project_fader_identification_status.md](project_fader_identification_status.md) — Fader collection: Sherry, Ira, Al confirmed. Nellie identified not confirmed. Anna/David Josowitz TBD.
- [agent_comparison.md](agent_comparison.md) — Claude Code vs Codex CLI vs Antigravity comparison

## Reference
- [reference_antigravity_invocation.md](reference_antigravity_invocation.md) — Paste prompt into GUI; future: `gemini -p "..." -y`
