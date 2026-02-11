---
paths:
  - "scripts/push_to_production.py"
  - "scripts/process_uploads.py"
---

# Post-Pipeline Verification Rules

After any push to production, verify by fetching rendered HTML — never rely on local data files alone (Lesson #53).

## Verification Checklist
```bash
# 1. Photo count matches local
curl -s https://rhodesli.nolanandrewfox.com/?section=photos | grep -o '[0-9]* photos'

# 2. Confirmed identities count
curl -s https://rhodesli.nolanandrewfox.com/ | grep -o '[0-9]* confirmed'

# 3. Specific identity exists (e.g., after merge)
curl -s https://rhodesli.nolanandrewfox.com/?section=confirmed | grep 'Identity Name'

# 4. Match mode has proposals (if proposals.json was pushed)
curl -s https://rhodesli.nolanandrewfox.com/api/match/next-pair | grep -o 'ML Match\|Same Person'

# 5. Pending uploads cleared (after staging cleanup)
curl -s https://rhodesli.nolanandrewfox.com/admin/pending-uploads | grep -o '[0-9]* pending'
```

## Post-Reclustering Checks
```bash
# 6. Check for promotions
python3 -c "import json; ids=json.load(open('data/identities.json')); print(sum(1 for v in ids.get('identities',{}).values() if isinstance(v,dict) and v.get('promoted_from'))), 'promoted')"

# 7. Triage bar renders with correct counts
curl -s 'https://rhodesli.nolanandrewfox.com/?section=to_review&view=focus' | grep -o 'Ready to Confirm\|Rediscovered\|Unmatched\|triage' | head -5

# 8. Focus mode shows highest-priority face first (should be proposal or promotion)
curl -s 'https://rhodesli.nolanandrewfox.com/?section=to_review&view=focus' | grep -o 'promotion-banner\|Rediscovered\|New Context' | head -3
```

## Data Integrity Before Push
Always run `python scripts/check_data_integrity.py` before pushing.

## Push Failure Recovery
If `git push` fails after commit:
- The commit exists locally — retry with `git push origin main`
- NEVER force-push. Investigate the conflict first.
- If merge needed, `push_to_production.py` already handles production-wins merge.
