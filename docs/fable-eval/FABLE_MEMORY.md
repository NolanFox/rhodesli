# FABLE_MEMORY — lessons learned during the Fable eval run (2026-07-02)

One lesson per entry: one-line summary first, then why it mattered + source evidence.

- **App monolith has moved: `app/page_routes.py` (13,389 lines) is now larger than `app/main.py` (8,255).** The brief's orientation note said to verify sizes — verified via `wc -l app/*.py`. Any "main.py refactor" framing in docs is stale; the true hotspot for route-sweeps is page_routes.py.
