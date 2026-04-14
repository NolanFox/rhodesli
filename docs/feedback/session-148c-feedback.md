# Session 148c Feedback

## FB-001: Head Table Context for Wedding Identification
- **Severity:** P3 (informational/methodology)
- **Context:** User identified 8-person group as Sherry's 1965 wedding based on matching dress and head table setup. Head tables traditionally seat bride, groom, and immediate family members — this narrows identification candidates significantly.
- **Fix:** N/A — methodology note for future identification sessions
- **Feature idea:** Gemini API could analyze photo context (formal setting, head table, wedding cake) to suggest "event type" which constrains who might be present

## FB-002: Mother-Daughter Similarity Search as Identification Strategy
- **Severity:** P2 (feature gap)
- **Context:** User wants to identify Nellie Kubrin (Sherry's mother) by looking at older women across photos and evaluating both contextual likelihood (age, era, proximity to Sherry) and visual similarity. This is a manual process today — could be a Gemini-assisted feature.
- **Fix:** Manual analysis this session. Future: Gemini visual reasoning for kinship/age-based identification.
- **BACKLOG candidate:** "Gemini-assisted kinship identification" — use visual reasoning to suggest parent/sibling relationships

## FB-003: Ancestry Integration for Event Attendee Narrowing
- **Severity:** P2 (feature gap)
- **Context:** User wants to cross-reference Ancestry records (who was alive, who lived nearby) with event dates to narrow down who could appear in photos. Currently manual research.
- **Fix:** Manual Ancestry research this session
- **Feature idea:** Import family tree data to auto-generate "who could be in photos from year X" lists

## FB-004: Gemini API for Visual Context Analysis
- **Severity:** P2 (feature opportunity)
- **Context:** User noted that the visual reasoning being done manually (evaluating photo context, estimating ages, assessing similarity) could eventually use Gemini API. This is exactly the kind of multi-signal reasoning Gemini excels at.
- **Fix:** N/A — future feature
- **BACKLOG candidate:** "Gemini visual context analysis for identification" — analyze group photos to suggest relationships, ages, event types

## FB-005: Codex Audit of Visual Analysis
- **Severity:** P3 (process)
- **Context:** User wants Codex to audit the visual analysis methodology and findings
- **Fix:** Codex was at capacity; self-audit performed instead
- **Commit:** 9ab7ef16

## FB-006: Name Collision is Common in Genealogical Research
- **Severity:** P2 (methodology / feature opportunity)
- **Context:** During investigation, the 1958 death date for "Abraham Fader" turned out to be a DIFFERENT Abe Fader (son of Isaac and Rachel Fader, buried at Montefiore Cemetery). User notes this kind of false lead from similarly-named relatives is "fairly common, especially with further off family." Ancestry trees can propagate incorrect links.
- **Root cause:** Common surnames + common first names + overlapping geographies = frequent name collisions in genealogical records
- **Methodology learning:** Always validate death/birth dates against primary sources (death certificates, cemetery records), not just other trees. Check burial plots for family groupings. Verify informant relationships on death certificates.
- **Feature ideas:**
  - When importing GEDCOM or linking identities to records, flag potential name collisions (same name, overlapping dates, same geography)
  - "Confidence level" on GEDCOM links: primary source vs. other-tree-derived
  - Disambiguation helper: show all people with same name in same geography/time period
- **Fix:** Documented as methodology learning in investigation log

## FB-007: Use Local Photos Instead of Chrome Browser
- **Severity:** P1 (process efficiency)
- **Context:** Session started by viewing photos via Chrome browser plugin, which is expensive in credits/context and makes it hard for Codex to audit. User pointed out all photos exist locally and should be read with the Read tool instead.
- **Fix:** Switched to local photo reading mid-session. Future sessions should default to local.
- **Rule:** For photo analysis work, ALWAYS use local Read tool. Chrome is for production verification only.

## FB-008: Log Everything for Future Reuse and Feature Development
- **Severity:** P2 (process)
- **Context:** User emphasized: (1) findings must be structured for future searches of other relatives, (2) methodology must be recorded so we know what works, (3) similarity scores to known relatives are kinship signals, (4) data should fit existing API call format
- **Fix:** Created structured investigation JSON + detailed search log with methodology learnings
