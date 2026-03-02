# Session 82b Follow-up Regression Audit

## Find Similar Regression Trace
- Candidate regression chain identified from git history:
  - `7fbe154` introduced full-page Find Similar route behavior.
  - `3a93561` and `ce11ca3` iterated card UX.
  - `34c4950` added inline endpoint but also changed face cards to horizontal.
- Current mixed state before follow-up:
  - Some UI paths still link to full-page similar routes.
  - Newly added inline endpoint exists but was not integrated as grid expansion slots across card grids.

## Feature Checklist (from older behavior) vs current
- [⚠️] Find Similar inline expansion with results panel
- [✅] Compare action exists in neighbor/similar contexts
- [✅] Merge action exists in neighbor/similar contexts
- [✅] Not Same action exists in neighbor/similar contexts
- [✅] View Photo modal actions exist
- [✅] Share button component exists and is widely used
- [⚠️] Edit/Tag availability inconsistent across card contexts
- [✅] Confirm / Skip / Reject actions exist (focus/triage)
- [✅] Quality indicator exists (admin)
- [⚠️] AI suggestions display consistency uncertain across sections
- [⚠️] Confidence tier labeling consistency uncertain across sections
- [✅] Face count badges present in several surfaces
- [⚠️] Collection/era metadata inconsistent by context
- [⚠️] Keyboard shortcut coverage varies by section
- [✅] Undo toasts exist for some destructive actions

## Summary
Primary follow-up priority remains unifying inline Find Similar expansion with retained vertical cards and consistent admin card affordances across surfaces.
