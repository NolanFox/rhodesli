# Dual Test Suite Rule

## Always run BOTH test suites

There are TWO test suites that must BOTH pass before any commit:

1. **App tests**: `source venv/bin/activate && pytest tests/ -x -q`
   - 2545+ tests covering web app, routes, UI, data
   - MUST activate venv first (Lesson 80) — system Python lacks fasthtml/torch

2. **ML tests**: `source venv/bin/activate && pytest rhodesli_ml/tests/ -x -q`
   - 306+ tests covering date estimation, training, augmentations
   - Located in rhodesli_ml/ package, NOT in tests/

## Common mistakes
- Running `pytest` without venv → only ~1293 tests collected instead of ~2909
- Running only app tests → ML regressions go undetected
- Using `--ignore=tests/e2e/` unnecessarily — e2e tests are fine to skip locally but app tests must not be ignored

## Session checklist
Before every commit: both suites pass.
Before session end: both suites pass.

See: Lesson 80 in tasks/lessons/testing-lessons.md
