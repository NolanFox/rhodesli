# Session 82a: Comprehensive UX Audit + Ideation
# Tool: Google Antigravity (Planning Mode)
# Branch: session-82a/ux-audit

---

## SETUP

```bash
# Create branch
git checkout -b session-82a/ux-audit
git push -u origin session-82a/ux-audit
```

Read these files first (in order):
1. `CLAUDE.md`
2. All files in `.claude/rules/`
3. `docs/session_context/session-82-context.md`
4. `ROADMAP.md`
5. `BACKLOG.md`
6. `docs/ALGORITHMIC_DECISIONS.md` (scan for UX-related decisions)
7. `docs/feedback/FEEDBACK_INDEX.md`

This session is READ-FIRST, IDEATE-WIDE, THEN NARROW. You are the creative director. Think divergently before converging.

---

## PHASE 1: COMPREHENSIVE APP AUDIT (Browser Agent)

### 1A: Screenshot Every Page

Use your browser agent to navigate the LIVE production app at `https://rhodesli.nolanandrewfox.com/`.

Screenshot and catalog EVERY page:
- Landing page / home
- `/photos` — Browse all photos
- `/people` — Browse all people
- `/photo/{id}` — Individual photo page (pick 3 different photos)
- `/person/{id}` — Individual person page (pick 2: one with many faces, one with few)
- `/collections` — Collections page
- `/timeline` — Timeline page
- `/map` — Map page
- `/identify/{id}` — Help identify flow
- `/compare` — Compare faces
- `/estimate` — Estimate date
- Admin identify flow (if accessible)
- Any other pages you discover

For EACH page, document:
- What works well
- What's broken or confusing
- What's missing
- Navigation paths to/from this page
- Mobile vs desktop issues (resize browser to test)
- Sharing: can you share this page? Does the URL work standalone?
- Loading speed: does anything feel slow?

Save all screenshots as Artifacts.

### 1B: User Flow Testing

Test these complete flows end-to-end:
1. **New visitor discovers a photo** — Land on home → find a photo → learn who's in it → share with someone
2. **Family member identifies a face** — Receive a shared link → view the match → vote yes/no → leave a comment
3. **Admin reviews matches** — Log in → check inbox → review suggested matches → confirm/reject → check if person page updated
4. **Community member browses people** — Go to /people → find a specific person → see all their photos → share the person page

For each flow, note every friction point, dead end, broken link, or confusing moment.

### 1C: Cross-Page Consistency Audit

Check these elements across ALL pages:
- [ ] Share buttons: present? consistent icon? consistent behavior?
- [ ] Face cards: same size? same layout? same actions available?
- [ ] Navigation: can you always get back? breadcrumbs? sidebar?
- [ ] Loading states: spinners? skeleton screens? or silent waits?
- [ ] Error states: what happens when something breaks?
- [ ] Mobile: does everything work on a phone-width viewport?

---

## PHASE 2: COMPETITOR RESEARCH (Browser Agent)

Use your browser agent to visit and screenshot relevant pages from:

1. **MyHeritage** (myheritage.com) — How do they display face matches? Photo galleries? Person pages?
2. **FamilySearch** (familysearch.org) — How do they handle photo sharing? Community identification?
3. **Ancestry** (ancestry.com) — Photo management UX. How do they show people across photos?
4. **Find A Grave** (findagrave.com) — How do they handle community-contributed photos?
5. **Any other relevant site** you discover during research

For each competitor, note:
- Face card / photo card design patterns
- Sharing mechanisms
- Navigation between people ↔ photos
- How they handle unidentified people
- Any innovative UX patterns Rhodesli could learn from

Compile findings into an Artifact: `competitor-ux-analysis.md`

---

## PHASE 3: DIVERGENT IDEATION ("Yes, And" Phase)

This is the creative brainstorm. Generate AS MANY ideas as possible. No filtering yet. Think wild.

### Categories to ideate on:
1. **Face card redesign** — What if face cards were interactive? Flippable? Had hover states? What if they showed relationship webs on hover?
2. **Find Similar reinvention** — What if Find Similar was a visual comparison matrix? A swipe-based interface? A side-by-side gallery?
3. **Sharing as a core loop** — What if every shareable page had a QR code? What if sharing auto-generated a story ("Help us identify this person from Rhodes, 1935")?
4. **Navigation rethink** — What if there was a command palette (Cmd+K)? What if people/photos/timeline were tabs, not separate pages?
5. **Admin workflow** — What if the admin review queue was a Kanban board? What if it had keyboard shortcuts for rapid review?
6. **Community engagement** — What if there was a "This Week in Rhodes" digest? What if identification progress was gamified?
7. **Visual design** — What would Rhodesli look like as a museum exhibition? As a family scrapbook? As a modern photo app?
8. **Performance** — What if every page loaded in under 1 second? What would need to change?
9. **Mobile-first** — What if Rhodesli was designed mobile-first? What changes?
10. **Accessibility** — What if a vision-impaired person used Rhodesli? What's missing?

Generate at least 30 ideas total. Don't self-censor. Write them all down.

---

## PHASE 4: NANO BANANA MOCKUPS (Top 5 Proposals)

From your ideation, select the **Top 5 most impactful, feasible proposals**.

For EACH of the Top 5:
1. Write a 1-paragraph description of the change
2. **Use Nano Banana to generate a UI mockup image** showing the proposed design
   - Prompt Nano Banana with: "Generate a UI mockup for a heritage photo archive app showing [specific change]. The aesthetic is warm archival — museum exhibition catalog meets modern photo app. Cream/warm backgrounds, serif typography for headings, amber accent color (#D4A574). Desktop layout, clean and professional."
   - If Nano Banana is unavailable/overloaded, generate an HTML/CSS mockup page instead
3. Save the mockup as an Artifact
4. List pros/cons/effort estimate
5. Map dependencies (what else needs to change)

### Evaluation Criteria for Top 5:
- Impact on user engagement (how many more people will use this feature?)
- Effort vs reward (can this ship in one session?)
- Consistency improvement (does this fix the fragmentation problem?)
- Portfolio value (does this showcase ML + UX skill?)

---

## PHASE 5: CONVERGENT PLAN

Take your Top 5 and write a detailed implementation plan:

### For each proposal:
- Exact files to modify
- Components to create/refactor
- Tests to write
- Estimated time
- Risk assessment
- Dependencies on other proposals

### Priority ranking:
Rank all 5 by: (Impact × Confidence) / Effort

### Phased rollout:
Group into:
- **Ship immediately** (bug fixes, consistency)
- **Ship this week** (high-impact, moderate effort)
- **Ship next sprint** (larger redesigns)
- **Backlog** (great ideas that need more thought)

---

## PHASE 6: DELIVERABLES

Create these files and commit them:

1. `docs/session_context/82a-ux-audit-report.md` — Full audit findings with screenshot references
2. `docs/session_context/82a-competitor-analysis.md` — Competitor research
3. `docs/session_context/82a-ideation-log.md` — All 30+ ideas (the raw brainstorm)
4. `docs/session_context/82a-top5-proposals.md` — Top 5 with mockups, pros/cons, effort
5. `docs/session_context/82a-implementation-plan.md` — Detailed plan for approved proposals
6. `docs/session_context/82a-mockups/` — Directory with all Nano Banana/HTML mockup files
7. Update `ALGORITHMIC_DECISIONS.md` with any UX architecture decisions
8. Update `BACKLOG.md` with new items discovered during audit

### Git Operations
```bash
git add .
git commit -m "feat(ux): session 82a comprehensive UX audit + proposals"
git push origin session-82a/ux-audit
```

### Create Pull Request
```bash
# Use gh CLI or git to create PR
gh pr create \
  --title "Session 82a: Comprehensive UX Audit + Top 5 Proposals" \
  --body "## Summary
  
Comprehensive UX audit of Rhodesli production app using browser agent + competitor research + Nano Banana mockups.

### Deliverables
- Full app audit with screenshots
- Competitor analysis (MyHeritage, FamilySearch, Ancestry, FindAGrave)
- 30+ ideation items
- Top 5 proposals with mockups
- Implementation plan

### NO CODE CHANGES — this is a research/planning PR only.
Merge at Nolan's discretion after review by assistant, expert, and prompter." \
  --base main \
  --head session-82a/ux-audit
```

---

## IMPORTANT CONSTRAINTS

- **DO NOT modify any application code.** This is audit + planning only.
- **DO NOT modify any data files.** Read-only access to data.
- **DO NOT run any ML pipeline code.**
- **DO commit all your research artifacts** — screenshots, mockups, analysis docs.
- Use sub-agents freely for parallel research tasks (e.g., one agent per competitor site).
- Use git worktrees if helpful for organizing work.
- Clean up any worktrees when done: `git worktree list` → `git worktree remove <path>`
- All work on branch `session-82a/ux-audit`.

---

## SUCCESS CRITERIA

This session succeeds if:
1. Every page of the live app has been audited with screenshots
2. At least 3 competitor sites have been analyzed
3. At least 30 divergent ideas were generated
4. Top 5 proposals have visual mockups (Nano Banana or HTML)
5. Implementation plan is detailed enough for a developer to execute
6. A PR exists with all deliverables
7. No application code was modified
8. No data was mutated
