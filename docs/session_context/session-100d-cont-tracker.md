# Session 100d Continuation — Master Tracker

**Goal:** Make the platform usable for Claude Benatar and other external contributors.
**Rule:** Every item below must be DONE or have a BACKLOG entry with specific next steps. No deferrals without explanation.

## Items from "What's Broken for External Users"

### BROKEN-1: Upload → Approve → Visible is not seamless
- **Status:** PARTIALLY FIXED (commits 08089d9, befd978, af1ae9b)
- **What was fixed:** HTMX swap IDs, staging cleanup preservation, R2 fallback
- **What remains:** End-to-end production verification not done
- **Action:** Browser verify on production

### BROKEN-2: No feedback loop for contributors
- **Status:** NOT FIXED — notification infrastructure exists but is NEVER CALLED on annotation approval
- **Root cause:** `create_annotation_approved_notification()` exists in notification_routes.py but is never called from the approval handler in admin_routes.py
- **Action:** Wire notification calls into single + batch annotation approval handlers

### BROKEN-3: Two different email addresses for Benatar
- **Status:** INVESTIGATED — poisson1957@hotmail.com (Supabase auth account) and lil_lover_52388@yahoo.com (annotation submissions)
- **Root cause:** He likely signed up with one email but the annotation form uses a different email field, OR he has two accounts
- **Action:** Check annotation submission code to understand how submitted_by is set

### BROKEN-4: Admin workflow is the only workflow
- **Status:** NOT FIXED — no contributor self-service path exists
- **Action:** Build "My Contributions" page showing user's own submissions + their status

## Items from "What Needs to Happen"

### NEED-1: End-to-end upload flow test on production
- **Status:** NOT DONE
- **Action:** Use browser tools to verify full flow

### NEED-2: Contributor dashboard ("My Contributions" page)
- **Status:** NOT BUILT
- **Action:** Build /my-contributions page showing all of a user's annotations + uploads + their status

### NEED-3: Email notifications when suggestions reviewed
- **Status:** NOT WIRED — see BROKEN-2
- **Action:** Wire notification creation into approval handlers

### NEED-4: Simplify navigation for non-admin users
- **Status:** NOT DONE
- **Current state:** Non-admin sees ~15 nav items including Review section (New Matches 466, Discoveries 0, Help Identify 203)
- **Problem:** Review items are admin concepts. Contributors need: Upload, My Contributions, Photos, People, Help Identify
- **Action:** Simplify sidebar for non-admin role

### NEED-5: Quickstart guide
- **Status:** DONE — docs/guides/claude-benatar-quickstart.md

## Data Integrity Questions

### DATA-1: Where are the proposals Nolan added today?
- **Status:** NEEDS INVESTIGATION
- **Root cause hypothesis:** Proposals live in proposals.json on Railway volume. They are NOT synced to Supabase. If proposals.json was overwritten by a deploy, they're gone.
- **Action:** Check proposals.json on production, verify proposal pipeline

### DATA-2: Are uploads/annotations being properly logged in Supabase?
- **Status:** AUDITED — see Supabase audit findings below
- **Key findings:**
  - Annotations: SYNCED (via _save_annotations → sync_annotations_to_supabase)
  - Pending uploads: SYNCED (3 call sites)
  - Proposals: NOT SYNCED TO SUPABASE — JSON only, no backup
  - Identity shadow writes: fire-and-forget with `except Exception: pass` (SILENT FAILURE)
  - 3 sync functions are dead code (never called)

### DATA-3: Fox archive clustering issues
- **Status:** NEEDS ANSWER
- **Action:** Investigate current state of Fox family clustering, what's blocking usability

## Session Housekeeping
- [ ] CHANGELOG update
- [ ] ROADMAP update
- [ ] BACKLOG updates for all remaining items
- [ ] Lessons learned entries
- [ ] Assessment update
