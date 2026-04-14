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
- **Fix:** Run Codex audit after completing the photo review
