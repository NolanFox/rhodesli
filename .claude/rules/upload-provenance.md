---
paths:
  - "app/main.py"
  - "core/photo_registry.py"
  - "core/storage.py"
  - "scripts/upload*.py"
  - "scripts/migrate*.py"
---

# Upload & Photo Provenance Rules

When modifying upload or photo metadata logic:

1. Photos have THREE distinct provenance fields:
   - `collection` = classification (how the archive organizes it)
   - `source` = provenance (where the photo came from)
   - `source_url` = citation (link to original)

2. These are SEPARATE concepts. Never conflate them. A photo's source is its origin; its collection is its classification.

3. Default collection = copy of source value (via migration). When not specified, photos get "Uncategorized".

4. All three fields must be:
   - Filterable on the photos page
   - Editable after upload (admin direct, contributor via annotation)
   - Supported in bulk operations

5. Read `docs/PHOTO_WORKFLOW.md` section 1b for the full model.

6. Route handlers MUST use `save_photo_registry()`/`save_registry()`, not `.save()` directly.
