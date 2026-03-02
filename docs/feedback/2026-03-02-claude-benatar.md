# Claude Benatar Feedback — March 2, 2026

## Source
Facebook Messenger conversation between Claude Benatar and Nolan Fox.

## Verbatim Feedback
1. "Why does it say unidentified person?" — referring to a photo that clearly shows Isaac Cohen with biographical text (born Rhodes July 17, 1906, arrived Congo 1928, merchant)
2. "See if you can find a match with this picture..." — sent a group family photo wanting face comparison

## What Was Broken

| Feature | Expected | Actual |
|---------|----------|--------|
| Help Identify submission | Creates pending annotation for admin review | Saved to separate file (`identification_responses.json`), never reached admin Approvals |
| Compare results | Shows face matches after pipeline completes | Pipeline completed but result page 404'd — results never saved to `comparison_results.json` |
| Naming a person | Admin can set display name | Only "Maiden Name" field existed; names displayed as "née Isaac Cohen" |

## Fixes Shipped (Session 83a)

1. **Display Name field** (AD-196) — primary name field in Edit Details form
2. **Help Identify → Annotations** (AD-197) — submissions now appear in admin Approvals tab
3. **Compare result storage** (AD-198) — SSE handler saves results, result pages load
4. **Admin card search** (AD-199) — filter by name or person number

## Follow-up Items for Future Sessions

- "Unidentified Person" label needs contextual explanation when photo contains visible name/text
- Compare page not discoverable for "match this person with this photo" use case
- Help Identify page should persist submission state across refresh
- Consider auto-suggest from Gemini OCR when photo contains visible text with names
