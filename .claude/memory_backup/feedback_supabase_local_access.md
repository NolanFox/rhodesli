---
name: Supabase local access via dotenv
description: How to query Supabase from local machine — load .env with dotenv, credentials are there
type: feedback
---

Always load .env before trying to use Supabase locally.

**Why:** Session 111 — wasted 5 minutes trying to query Supabase without loading .env, got "NOT AVAILABLE". User had to remind me that credentials are in .env and I should know this.

**How to apply:** When investigating production data issues, always start with:
```python
from dotenv import load_dotenv
load_dotenv()
```
Then `get_supabase_client()` will work. Don't waste time trying browser workarounds or Railway logs.
