# Feature Reality Contract

A feature is NOT considered "done" unless ALL of these are true:

1. **Data exists**: The source data file is present and valid
2. **App loads it**: The app explicitly loads the data at startup or on-demand
3. **Route exposes it**: A route makes the data available to the UI
4. **UI renders it**: The feature is visible to the appropriate user role
5. **Production test verifies it**: A test confirms end-to-end functionality

## Verification Checklist (run at end of every session)

For each feature built or modified in this session:
- [ ] Data source file exists and is valid JSON/etc.
- [ ] App code imports/loads the data
- [ ] Route returns 200 and includes the data
- [ ] UI element renders (verify in browser or production)
- [ ] Test covers the feature path

## Anti-Phantom Rule

If a session builds a data pipeline, the session MUST ALSO:
- Wire the data to at least one UI surface
- Add a test that verifies the data appears in the UI
- Verify in production (not just curl/unit test)

If a session cannot complete the UI wiring, it must:
- Create a TODO in BACKLOG.md with specific wiring instructions
- Add a failing test that will remind the next session
