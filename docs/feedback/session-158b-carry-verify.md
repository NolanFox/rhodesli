=== 1. v2 row counts (must match 157b end) ===
  [OK ] gedcom_individuals_v2: 21998 (expected: >=21998)
  [OK ] gedcom_families_v2: 6741 (expected: >=6741)
  [OK ] gedcom_change_manifest: 9 (expected: >=9)

=== 2. v1 still intact ===
  [INFO] gedcom_individuals: total=196645, is_current=TRUE=21998, historical=174647
  [INFO] gedcom_families: total=33324, is_current=TRUE=6741, historical=26583

=== 3. Harry Fox + Belle Isle intact ===
  [OK ] Harry anchors: 5 (expected: ==5)
  [OK ] Harry version_id: 14 (expected: >=14)
  [OK ] Belle Isle name contains 'Belle Isle': True (expected: ==True)
  [OK ] Belle Isle state: INBOX (expected: ==INBOX)
  [OK ] Belle Isle has notes in metadata: True (expected: ==True)

=== 4. R2 archive readability (CRITICAL gate) ===
  [INFO] R2 archive at gedcom-version-snapshots/2026-05-08-session-156/: 42 files
  [INFO] total bytes: 277,042,447
  [INFO] v9/ files: 7
  [OK ] gedcom-version-snapshots/2026-05-08-session-156/v9/gedcom_change_log.jsonl.gz: 32,288,272 bytes, etag="709385023bb91215a55d9d210440c670-4"
  [OK ] gedcom-version-snapshots/2026-05-08-session-156/v9/gedcom_events.jsonl.gz: 158,574 bytes, etag="ef665f85e9f7411046e8816e5710d97f"
  [OK ] gedcom-version-snapshots/2026-05-08-session-156/v9/gedcom_families.jsonl.gz: 1,552,152 bytes, etag="e7ca8911f74d9ad1f30c9a885a9f7a00"

=== Summary ===
ALL OK — Phase 158-0 carry verification passed
