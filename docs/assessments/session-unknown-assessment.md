# Session 100b-cont2 Assessment

## Shipped
- [x] Tree multi-spouse layout fix (Roland Fox) — Evidence: browser screenshot, Margie-Roland-Betty correctly ordered
- [x] Face cycling on identity cards — arrows + dots + JS handler — Evidence: 10 tests pass, visibility fix (opacity-60)
- [x] Photo overlay repositioned (top instead of bottom) — Evidence: deployed, browser verified
- [x] Session99 variant collapse (-136 lines) — Evidence: deployed, test updated
- [x] Link Tree affordance (amber styling + icon + tooltip) — Evidence: 4 new tests pass
- [x] Yaacov Jacob Franco face swap — Evidence: Supabase updated, local git committed
- [x] Solomon Solly Galante orphan face removed — Evidence: Supabase updated, local git committed
- [x] Full Session 100 audit (26 items) — Evidence: parallel agent completed comprehensive table
- [x] User feedback saved to persistent memory — Evidence: 2 memory files created

## Deferred / BLOCKED
- **Production Supabase not reading** — DATA_SOURCE=postgres is set but app falls back to JSON on volume. Yaacov fix NOT visible in production. BLOCKING. See continuation prompt.
- **Face cycling production verification** — Cannot verify until deploy with correct data is confirmed
- **Lessons learned documentation** — Needs Lessons 131-134 added to tasks/lessons.md
- **BACKLOG entries** — Visual confirm gate, data integrity CI, date ordering transparency
- **Session documentation** — ROADMAP, CHANGELOG, SESSION_HISTORY updates

## Red Flags
- CRITICAL: Production app not reading from Supabase despite DATA_SOURCE=postgres. Health says "Supabase connection skipped." This means ALL Supabase data fixes are invisible in production. Root cause unknown — needs Railway deploy log investigation.
- CRITICAL: The Yaacov Jacob Franco face misassignment was from Session 93 (March 8) and went undetected for 5 days. No automated check catches this class of error.
- HIGH: Face cycling arrows were invisible (opacity-0) — claimed "fixed" without production verification.
- HIGH: BUG 1 was marked "NOT A BUG" in previous assessment — was actually a real data bug.

## Next Session Should Verify FIRST
1. Why is production not reading from Supabase? Check Railway deploy logs.
2. Fix the Supabase connection or push corrected JSON to volume as fallback
3. Browser verify Yaacov Jacob Franco shows correct face (bearded man, not young woman)
4. Browser verify face cycling arrows visible on Roland Fox card
5. Add lessons 131-134 and BACKLOG entries
