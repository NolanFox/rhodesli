# Session 140 Context — P0 Auth Fix + OAuth Redirect

**Predecessor:** Session 139 (v0.99.50) — Mega Fix Sprint
**Date:** 2026-03-27

## Problem
All auth operations (OAuth, login, signup, password reset) broken since Session 90b.
Root cause: auth_routes.py extraction removed 7 function imports from main.py.
Tests masked the breakage with `create=True` mock patches.

## Scope
Emergency hotfix — no formal prompt written (reactive P0 fix).

## Deliverables
1. Re-export 7 auth functions in main.py
2. OAuth redirect: fetch()+JS → form POST→303
3. Root page logged-in state
4. Lessons 157 (create=True masking) and 158 (fetch cookie race)

Backfilled from Session 140 assessment.
