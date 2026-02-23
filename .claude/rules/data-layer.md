# Data Layer Rules
- Postgres/Supabase is the source of truth for ALL structured data
- JSON files are cache-only or deprecated — never primary store
- User-entered data MUST be in Supabase (AD-135)
- Never overwrite user data with ML predictions
- Dual-write is a temporary bridge, not permanent architecture
- New features store in Postgres from day one
