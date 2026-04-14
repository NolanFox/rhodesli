---
name: Platform reliability is existential
description: Data errors and broken features make the platform unusable. Reliability is the #1 priority over new features.
type: feedback
---

Data errors (wrong face assigned to identity) are the most severe type of error. They ruin the point of the entire app. If Nolan, who built the platform, can't reliably use it, no one else ever will.

**Why:** Session 100b had a face misassignment that went undetected for days. Face cycling was "fixed" but invisible. Multiple issues claimed done were superficial or unverified. The platform has been "breaking left and right" including major data errors.

**How to apply:**
1. Reliability and data integrity trump all new feature work
2. Before building new features, ALL outstanding bugs must be fixed and verified
3. Every data-touching operation needs audit — never assume the data is correct
4. The bar for "done" is: deployed + browser verified + screenshot evidence
5. When in doubt, investigate the data layer, not just the rendering code
