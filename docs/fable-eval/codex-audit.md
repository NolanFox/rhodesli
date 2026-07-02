# Codex Audit: FABLE_EVAL_PROMPT.md

**VERDICT: BLOCK.** The brief captures most of Nolan's intent and the Fable-5 advice, but it should
not be handed to Fable as-is. Two issues are blocking: W8 authorizes ambiguous source changes that
contradict the exclusion list, and the production read-only rule is not technically enforced enough
for a repo with a documented prod-click data incident. After the P0/P1 fixes below, the prompt is
close to "ship with fixes."

## P0 Findings

### P0-1: Cut W8(a) implementation; "additive-only Quick Wins" is not actually safe as written

**Problem:** Lines 48-55 exclude production-data mutation, schema/migrations, global head/nav/layout,
frozen files, and `data/*`, but lines 174-178 authorize copy fixes, OG/meta/SEO tags, alt text,
aria labels, mobile CSS, doc corrections, tests, and commits. OG/meta commonly touches global head
layout; mobile CSS commonly touches global layout; "doc corrections" can mutate existing source-of-
truth docs; tests/source edits plus commits conflict with the repo's full-suite pre-commit rule. The
"purely additive" label does not make these changes safe or unambiguous.

**Risk:** Fable may spend the run implementing small-but-real product changes instead of doing the
evaluation, edit excluded layout surfaces, commit without the required full test gates, or create
merge pressure around code that was supposed to be independently audited.

**Exact fix:** remove implementation from this evaluation run. Replace the relevant language with:

```markdown
In "What you produce", replace "a bounded set of safe shipped improvements on a branch" with:
"a bounded, ranked Quick-Wins queue with patch plans; no source-code implementation in this eval run."

Replace the hard-boundary bullet beginning "The only code you may edit..." with:
"Do not edit existing app/source/test/script files, existing project docs outside `docs/fable-eval/`,
global head/nav/layout, CSS, schema/migrations, frozen files, or `data/*`. The only files you may
create or edit in this run are `docs/fable-eval/**` and new repo-local skill directories under
`.claude/skills/<new-skill>/SKILL.md` after the skill safety gates pass. Do not commit code."

Replace W8(a) with:
"From W1/W2/W4, identify up to five highest-confidence Quick-Win candidates. Do not implement them.
For each candidate write: user impact, exact files likely involved, why it is outside the exclusion
list, acceptance tests, rollback plan, and whether it is new / already-logged / stale / synthesis.
Write these to `docs/fable-eval/QUICK_WINS_QUEUE.md` for the independent follow-up sprint."

Replace the Definition of Done clause "W8 additive fixes committed..." with:
"`QUICK_WINS_QUEUE.md` exists; no source-code commits or pushes were made."
```

If Nolan insists on live-code Quick Wins, run them as a separate post-audit sprint with an explicit
file allowlist and full project test gates before commit. Do not mix that with the Fable evaluation.

### P0-2: Production read-only is policy-level, not tool-enforced

**Problem:** Lines 40-44 correctly say production is read-only, but they do not require a logged-out
browser context or request blocking. They also do not cover local commands that may use `.env` and
write to Supabase/R2/Railway/Gemini. Lesson 149 was caused by a browser click on prod; this prompt
still lets an authenticated browser session expose dangerous controls.

**Risk:** A single accidental admin click, form submit, file upload, POST from browser tooling, or
local script using production credentials could mutate live data despite the written rule.

**Exact fix:** add this block under "Hard boundaries":

```markdown
- **Live-site browser safety is technically enforced.** Use a fresh logged-out/private browser
  context for the live site. Do not log in to production. If the browser is already authenticated,
  close that context and start a clean one. Configure request interception, if available, to abort
  all non-GET/HEAD requests and all file uploads to `https://rhodesli.nolanandrewfox.com`. If the
  browser tool cannot block writes, navigate only by typed URL or ordinary read-only links and do
  not interact with forms, buttons, upload controls, or admin-only surfaces.
- **Local command safety.** Before running any command that could import app code, call scripts, or
  touch external services, confirm it is read-only, mocked, or dry-run. Never run scripts with
  `--execute`, migrations, deploy/sync commands, R2 writes, Supabase writes, Railway changes, or
  Gemini/paid API calls. Do not source production credentials for write-capable commands; unset
  production write credentials when possible.
```

## P1 Findings

### P1-1: The run is too broad and encourages usage-limit stalls

**Problem:** W1 says "Rank every issue"; W2 requires many surfaces at two viewports; W3/W4 scan
large route monoliths; W5 does product strategy; W6 does Gemini readiness; W7 installs 3-5 skills;
W8 packages the eval. Even with subagents, this is a lot for one bounded run and may produce partial
artifacts plus a forced "complete" claim.

**Exact fix:** add a bounded-run rule after "Working method":

```markdown
**Bounded completion rule:** optimize for high-confidence, evidence-backed top findings, not
exhaustive coverage. Caps: W1 top 15 issues; W2 all required screenshots plus top 12 findings; W3
top 10 risks; W4 top 8 verified defects plus a search-coverage appendix; W5 exactly 3 bets; W6 one
readiness decision table; W7 exactly 3 installed skills unless two more are clearly higher-value;
W8 up to 5 Quick-Win candidates. If coverage is incomplete, label the missing scope explicitly
instead of extending the run or fabricating completion.
```

### P1-2: EVALS are measurable proxies, not proof of Fable-unique capability

**Problem:** Lines 187-201 ask Fable to prove what Opus/Sonnet/Codex "could not" do, but the prompt
does not provide a controlled baseline. The current metrics are useful, but they demonstrate
Fable-leveraged value, not uniqueness.

**Exact fix:** replace the Evals intro with:

```markdown
These are proxy evals, not proof of model uniqueness. For each metric include numerator,
denominator, evidence path, and baseline comparator where available (`BACKLOG.md`, `codex-draft.md`,
`opus-draft.md`, prior session docs, or code-only review). Label each result as Evidence-backed,
Proxy, or Unverified. Do not claim another model "could not" do something unless the comparator
actually supports that claim; otherwise say "likely Fable-leveraged."
```

Also add one skill usability check:

```markdown
Skill usability delta: run a fresh-context verifier subagent over one new skill and one held-out
repo issue. The verifier must say whether the skill contains enough triggers, reads, gates, and
anti-patterns to be usable by Opus without Fable.
```

### P1-3: Generated artifacts may violate the repo's 300-line document cap

**Problem:** The prompt audits docs over 300 lines, but does not constrain its own artifacts. Given
the requested scope, Fable can easily create new oversized docs under `docs/fable-eval/`.

**Exact fix:** add:

```markdown
All generated Markdown files must stay under 300 lines. If an artifact would exceed that, split it
into `docs/fable-eval/<artifact>/INDEX.md` plus focused child files. The index should carry the
ranked summary and link to evidence appendices.
```

### P1-4: Skill installation mutates future agent behavior and needs gates

**Problem:** W7 says installing `.claude/skills/<name>/SKILL.md` is inert until invoked. That is too
optimistic: skill discovery metadata can affect future routing, and a bad skill can encode unsafe
habits. The prompt also does not make portability to fox-genealogy operational.

**Exact fix:** replace the W7 install sentence with:

```markdown
Draft each skill first under `docs/fable-eval/skill-drafts/<name>/SKILL.md`. A verifier subagent
must check it for: no reasoning-extraction language, no permission expansion, no instructions to
edit excluded files, required reads, verification gates, anti-patterns, and a concrete rhodesli
incident. Only then copy approved new skill directories to repo-local `.claude/skills/<name>/SKILL.md`.
Do not edit existing skills, `.claude/rules`, `.claude/settings.json`, or user-level `~/.claude`.
Write `docs/fable-eval/PORTABLE_SKILLS.md` listing which skills should later be installed at user
level for sibling repos and what repo-specific paths must be adapted.
```

### P1-5: Branch/commit behavior lacks dirty-worktree protection

**Problem:** The prompt tells Fable to commit to `session-169/fable-full-eval`, but never says to
check for existing user changes, branch collisions, or unrelated staged files. This is unsafe in a
shared workspace.

**Exact fix:** if implementation is not cut, add:

```markdown
Before any branch or commit operation, run `git status --short` and `git branch --show-current`.
If the worktree is dirty with files you did not create in this run, do not switch branches or
commit; continue with read-only artifacts and record the blocker. If a branch is created, stage
only files from the explicit allowlist and never stage unrelated local changes.
```

Cutting W8(a) makes this mostly unnecessary, but the guard is still useful if the owner keeps any
commit path.

## P2 Findings

### P2-1: Borderline reasoning-extraction wording should be softened

**Problem:** There is no direct "show chain of thought" instruction, and lines 58-60 plus W7
explicitly prohibit it. Still, "teach Opus 4.8 how to think" appears in the brief and can be
replaced with safer wording without losing intent.

**Exact fix:** replace "teach Opus 4.8 how to think" everywhere with "teach Opus 4.8 reusable
judgment patterns and verification habits." Add: "Before installing any generated skill or prompt,
scan it for forbidden phrases such as `show your reasoning`, `chain of thought`, `hidden reasoning`,
or `think step by step`; rewrite them as rationale/evidence/verification requirements."

### P2-2: The prompt omits several high-value feedback sources

**Problem:** The workstreams read the major architecture and roadmap docs, but W2/W5/W6 do not name
several feedback files that are likely to prevent rediscovering stale issues or missing user pain.

**Exact fix:** add to the relevant read lists:

```markdown
For W2/W5, also read `docs/feedback/FEEDBACK_INDEX.md`,
`docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/feedback/session-167-track-c-decisions.md`, and
any existing `docs/ux_audit/` tracker if present. For W6, read
`docs/feedback/session-167-detroit-eval.md` explicitly. For orientation, include
`docs/session_context/session-168-path-forward.md` if present.
```

### P2-3: W4's "verify reproduces" rule is too binary for architecture risks

**Problem:** Requiring every code finding to "reproduce" may cause Fable to drop real cross-file
risks that are visible by static path analysis but hard to execute safely. That is good for bug
claims, but bad for route-safety risk discovery.

**Exact fix:** replace the W4 verification sentence with:

```markdown
Classify W4 entries as `Verified defect` only when reproduced by a targeted check or airtight
code-path proof. Classify non-reproduced but credible issues as `Risk finding`, with the exact
missing evidence and the targeted test needed. Do not mix the two in the EVALS bug-recall count.
```

### P2-4: Subagent append guidance can cause file races

**Problem:** Having multiple subagents append findings to "its artifact file" is good for stall
resilience but ambiguous for concurrent writes.

**Exact fix:** add:

```markdown
Subagents write only to `docs/fable-eval/subagents/<workstream>-<scope>.md`. The main agent later
synthesizes those into the canonical artifact. Do not have multiple agents write the same file.
```

## P3 Findings

### P3-1: Treat prompt facts as unverified orientation, not reportable truth

**Problem:** The prompt includes counts, CI status, and route line counts. These are useful
orientation, but they may drift quickly.

**Exact fix:** add: "All counts, CI status, file sizes, and line counts in this brief are
orientation only. Verify them before citing them in an artifact; otherwise mark them Unverified."

### P3-2: "No safe Quick Wins" needs to be an acceptable outcome

**Problem:** As written, the Definition of Done assumes shipped fixes. That can pressure Fable to
invent a safe change.

**Exact fix:** if W8(a) is retained, add: "If no Quick-Win candidate passes every safety gate, ship
zero fixes and say so. A zero-fix outcome is acceptable and should score higher than a speculative
change."

### P3-3: The final report should include an explicit safety ledger

**Problem:** The prompt asks for shipped vs queued decisions, but not an explicit "nothing forbidden
happened" ledger.

**Exact fix:** add to `FABLE_REPORT.md`: "Safety ledger: production auth state, production request
methods observed, external API spend, files edited, branches/commits made, tests run, and any
unverified claims."

