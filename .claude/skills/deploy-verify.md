---
description: "Deploy to Railway and verify production. Use after completing code changes."
---
# Deploy and Verify

## Steps
1. `git push origin main`
2. Wait 60 seconds for Railway deploy
3. Verify these routes return 200 (not 500):
   - `/` (landing page)
   - `/map`
   - `/connect`
   - `/tree`
   - `/timeline`
   - `/collections`
   - `/compare`
4. Pick one photo with face data -> verify face overlays render
5. Pick one photo with alignment data -> verify per-face cards show
6. Report: all routes OK / which failed

## If any route fails:
- Do NOT proceed with other work
- Fix the 500 first
- Re-deploy and re-verify
