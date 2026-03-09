# Doc Size Enforcement — Split, Don't Trim

Triggers: After any Edit or Write to a .md file in docs/.

## Rule (Lesson 106)
When a doc exceeds 300 lines, **split it into sub-files** — never trim content.

### How to split:
1. Create a subdirectory named after the doc (e.g., `docs/architecture/ml_service/`)
2. Move detailed sections into sub-files (e.g., `API.md`, `DEPLOYMENT.md`)
3. Each sub-file gets a `**Parent:** [hub doc](../HUB.md)` link at the top
4. Rewrite the hub doc with summaries + links to sub-files
5. Hub doc must stay under 300 lines

### What NOT to do:
- Do NOT condense tables, remove code examples, or shorten descriptions
- Do NOT delete valuable context just to meet a line count
- Do NOT create a single monolithic "appendix" — split semantically by topic

### Example:
```
docs/architecture/ML_SERVICE.md (409 lines — over limit!)
  → Split into:
    docs/architecture/ML_SERVICE.md (193 lines — hub with summaries + links)
    docs/architecture/ml_service/API.md (detailed API spec)
    docs/architecture/ml_service/DEPLOYMENT.md (deployment options + sizing)
    docs/architecture/ml_service/PIPELINE.md (automated pipeline + integration)
    docs/architecture/ml_service/MIGRATION.md (migration plan + risks)
```

### Enforcement:
- The test `test_ml_service_doc_exists` checks line count ≤ 300
- PostToolUse hooks should warn when any doc in docs/ exceeds 300 lines

See: Lesson 106 in `tasks/lessons/ui-lessons.md`
