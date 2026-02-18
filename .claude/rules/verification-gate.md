# Verification Gate — Feature Reality Contract

Triggers: After all phases of a multi-phase session are complete,
BEFORE declaring the session done or pushing to main.

## Mandatory end-of-session verification:

1. **Re-read the original prompt:** `cat docs/prompts/session_NN_prompt.md`

2. **For each phase, verify the Feature Reality Contract:**

   For UI features:
   | Check | Method |
   |-------|--------|
   | Data exists? | `find` / `grep` for expected files |
   | App loads it? | `grep` for import/load in app code |
   | Route exposes it? | `grep` for route definition |
   | UI renders it? | `curl` the route or run browser test |
   | Test verifies it? | Run the specific test |

   For infrastructure/data work:
   | Check | Method |
   |-------|--------|
   | File created? | `ls` / `find` |
   | Referenced correctly? | `grep` for imports/paths |
   | Deployed correctly? | Check .gitignore, Dockerfile, deploy config |
   | Tests pass? | Run relevant test suite |

   For documentation:
   | Check | Method |
   |-------|--------|
   | File exists? | `ls` the expected path |
   | Under 300 lines? | `wc -l` |
   | Breadcrumbs present? | `grep` for cross-references |
   | CLAUDE.md updated? | Check key docs table |

3. **Update session log with PASS/FAIL per check**

4. **If any FAIL: fix it, don't skip it.**
   The verification gate is not advisory. Fix failures before proceeding.

5. **Only after all PASS:**
   - Push to main
   - Update ROADMAP.md
   - Declare session complete

## Common failure patterns to watch for:
- Data file exists in ML directory but not copied to app data/
- Route defined but not wired to navigation
- Test passes with mocks but feature doesn't work in browser
- Documentation created but no breadcrumbs to BACKLOG
- .gitignore or .dockerignore blocking required files

See: docs/HARNESS_DECISIONS.md HD-003
