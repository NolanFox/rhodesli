# Public Attack Surface Security Audit - 2026-07-05

## VERDICT

The 51 anonymous `source: "Compare Upload"` / `uploader_email: "unknown"` pending uploads are best explained by the public compare tool working as designed, not by a secret-key breach: `/api/compare/upload` accepts anonymous uploads, stages them, and writes a `pending_uploads` entry with `source: "Compare Upload"` and `uploader_email: "unknown"` when no session user exists. I found no code path that renders the Supabase service-role key, R2 write keys, Gemini/Google key, session secret, Resend key, invite codes, or ML service token to normal browser HTML/JS/JSON. However, I did find actual public file-read path traversal risks in local file-serving routes; fix those immediately because they could expose local data files if reachable in production. The uploads themselves are also a real abuse/content-liability problem, even though the root cause is intentional product behavior rather than exploitation.

## Findings

No P0 findings: I found no evidence that the anonymous pending uploads required a breach or that service-role/R2/Gemini/session/Resend/invite secrets are exposed through normal unauthenticated browser surfaces.

| Sev | Title | File:line | Evidence | Fix |
|---|---|---|---|---|
| P1 | Actual vulnerability: public local file-read path traversal in file-serving routes | `app/main.py:1432`, `app/main.py:1439`, `app/main.py:1441`; `app/match_facecompare_routes.py:1847`, `app/match_facecompare_routes.py:1852`, `app/match_facecompare_routes.py:1858`; `core/config.py:36-43` | `/photos/{filename:path}` and `/uploads/facecompare/{filename:path}` join attacker-controlled path segments to local bases and serve `FileResponse` without resolved-path containment checks. In Railway single-volume mode, `raw_photos/../data/...` is the obvious sensitive target; in local/default mode, repo files may also be reachable. | Resolve target paths and require `target.is_relative_to(base.resolve())`; reject `..`, absolute paths, and encoded traversal; prefer registry/photo IDs over path params; add regression tests. |
| P1 | Public-tool-working-as-designed: anonymous compare upload creates the reported pending queue rows | `app/compare_routes.py:1571`, `app/compare_routes.py:1584-1587`, `app/compare_routes.py:1620-1622`, `app/compare_routes.py:1642-1652`, `app/compare_routes.py:1664-1700` | No login guard precedes the route. With auth enabled and no user, `uploader_email = "unknown"` and `user_is_admin` is false; the non-admin branch writes `pending["uploads"][job_id]` with `source: "Compare Upload"` and `status: "pending"`. | Split compare from contribution: make compare ephemeral, and require an explicit logged-in/captcha-gated "contribute to archive" step before queueing or durable R2 storage. |
| P1 | Actual vulnerability: `upload-multiple` no-ML branch persists unvalidated files | `app/compare_routes.py:3071-3082`; `app/page_routes.py:9794-9827`, `app/page_routes.py:9835-9838` | If InsightFace is unavailable, the route reads each submitted file and calls `_save_compare_upload()` before the later per-file extension/10 MB checks. The helper persists to R2/local and queues review. | Move extension, content type, per-file size, and total batch-size checks before the no-ML fallback; reject unknown suffixes; add tests with ML unavailable. |
| P2 | Public-tool-working-as-designed risk: anonymous uploads persist abusive content to storage | `app/compare_routes.py:1668-1677`; `app/admin_routes.py:681-685`; `core/storage.py:185-188`; `app/estimate_routes.py:1095-1112`; `app/match_facecompare_routes.py:1454-1458` | Anonymous compare uploads can be copied to R2 under `uploads/pending/...`; estimate and facecompare also save public-tool uploads. Admin thumbnails use public R2 URLs for pending compare uploads. | Make pending/contribution buckets private or expiring, add lifecycle deletion, content scanning/reporting workflow, and avoid durable storage until the user chooses to contribute. |
| P2 | Weak rate limiting for anonymous upload paths | `app/rate_limit.py:6-17`; `app/compare_routes.py:1584-1587`, `app/compare_routes.py:3032-3035`, `app/compare_routes.py:4214-4217`; `app/match_facecompare_routes.py:1325-1328` | The limiter is an in-memory process-local dict with a default 20/hour/IP. It resets on deploy/restart and is not shared across workers/instances. The app keys on `request.client.host`; it does not read `X-Forwarded-For`, so header spoofing is not evident in app code, but proxy/client-IP behavior depends on deployment. | Use Cloudflare/Railway edge limits plus Redis/Postgres-backed counters; add Turnstile/CAPTCHA on anonymous upload; enforce daily storage quotas. |
| P2 | Auth-boundary gap: public person comments are visible immediately | `app/person_routes.py:2291-2323`, `app/person_routes.py:2339-2345` | `/api/person/{person_id}/comment` has no login requirement, saves status `"visible"`, syncs to Supabase, and immediately renders author/text. This is not core photo/identity mutation, but it is public content mutation outside the admin queue. | Require login or queue comments for admin moderation; add spam controls and shared rate limiting. |
| P3 | Repository hygiene: historical ML service token-like value in docs, not browser-routed by the app | `docs/session_logs/session-116-log.md:49-50`; `app/main.py:1463` | A session log contains `ML_SERVICE_TOKEN=...`. The app mounts only `app/static` at `/static`, so this doc is not directly served by the normal static route, but the token should be treated as compromised if real. | Rotate `ML_SERVICE_TOKEN`, scrub docs/history where practical, and add secret scanning. |
| P3 | Benign expected exposure: PostHog browser key | `app/main.py:235-244` | `_posthog_script()` intentionally injects `POSTHOG_API_KEY` into client JS. This is a public analytics write key, not comparable to service-role/R2/Gemini/session secrets. | Keep using a public project key; do not reuse server-only analytics keys in this variable. |

## ROOT_CAUSE

### `/api/compare/upload`

This route is the exact source of the reported rows. It is registered as public at `app/compare_routes.py:1571` and rate-limited, but not login-gated, at `app/compare_routes.py:1584-1587`. It reads the uploaded file, checks suffix and 10 MB size, then resolves session user state at `app/compare_routes.py:1620-1622`. With normal production auth enabled and no session, `user` is `None`, `user_is_admin` is false, and `uploader_email` becomes `"unknown"` at `app/compare_routes.py:1642`.

The route stages the uploaded file under `data/staging/{job_id}` using a UUID-derived job id and a sanitized basename (`app/compare_routes.py:1623-1634`). It writes metadata with `source: "Compare Upload"`, empty `source_url`, and `compare_mode: True` at `app/compare_routes.py:1643-1655`.

The non-admin branch starts at `app/compare_routes.py:1664`. For anonymous users, `is_logged_in` is false (`app/compare_routes.py:1665-1667`), optional R2 backup writes to `uploads/pending/{job_id}/{safe_filename}` (`app/compare_routes.py:1668-1677`), and the queue entry is written at `app/compare_routes.py:1686-1700` with:

- `uploader_email: "unknown"`
- `source: "Compare Upload"`
- `source_url: ""`
- `status: "pending"`
- `compare_mode: True`

That is a direct match to the owner's data pattern. No secret, admin cookie, Supabase key, or exploit is needed.

### Other requested compare endpoints

`/api/compare/upload-multiple` is also public and rate-limited (`app/compare_routes.py:3024-3035`). In the normal ML path it validates each file before processing (`app/compare_routes.py:3103-3113`) and calls `_save_compare_upload()` (`app/compare_routes.py:3131-3133`), whose helper auto-queues compare uploads for review (`app/page_routes.py:9760-9786`, `app/page_routes.py:9835-9838`). In the no-InsightFace branch, validation is missing before persistence (`app/compare_routes.py:3071-3082`), which is a separate abuse bug.

`/api/compare/pair/upload` is public and rate-limited (`app/compare_routes.py:4207-4217`). It validates suffix and 10 MB size (`app/compare_routes.py:4228-4239`), runs image parsing/face detection (`app/compare_routes.py:4267-4277`), and stores comparison artifacts under `uploads/compare/...` (`app/compare_routes.py:4287-4317`). It does not create `pending_uploads`.

`/api/compare/realtime` is admin-only by explicit guard (`app/compare_routes.py:5997-6005`). It uses a temp file and requires `ML_SERVICE_URL` (`app/compare_routes.py:6017-6038`). It is not the source of anonymous pending uploads.

`/api/compare/contribute` requires login before queueing (`app/compare_routes.py:3355-3365`). It can create a pending upload for a prior compare artifact (`app/compare_routes.py:3388-3407`), but anonymous users should receive `_check_login` denial when auth is enabled.

## Secret Exposure

I found no normal unauthenticated browser route that returns service secrets. The important code paths are server-side:

- Supabase service role: only used to construct the server data client (`app/supabase_data.py:37-48`).
- Supabase anon key: read in auth helpers (`app/auth.py:21-23`) and sent server-side to Supabase auth endpoints (`app/auth.py:146-158`, `app/auth.py:354-365`); also used for a server-side health ping (`app/page_routes.py:60-70`). It is not a service-role key.
- R2 write keys: read into server globals (`core/storage.py:25-32`) and passed into boto3 only (`core/storage.py:136-150`). Public R2 URLs are expected and separate (`core/storage.py:56-58`, `core/storage.py:185-188`).
- Gemini/Google key: read server-side (`app/estimate_routes.py:1302`) and passed into Gemini calls (`app/estimate_routes.py:1310-1322`, `app/estimate_routes.py:2152-2156`); public errors say only "not configured" on guarded/admin paths (`app/admin_routes.py:5168-5175`).
- Session secret: used as FastHTML cookie signing secret (`app/main.py:266-270`), with a production warning if default (`app/auth.py:23-30`).
- ML service token: used as an Authorization header in the server HTTP client (`core/ml_client.py:46-69`); realtime compare is admin-only (`app/compare_routes.py:5997-6005`).
- Resend key: used only as an outbound Authorization header (`app/main.py:3115`, `app/main.py:3147-3159`).
- Invite codes: loaded into memory (`app/auth.py:31`) and checked by `validate_invite_code()` (`app/auth.py:139-141`); signup returns only "Invalid invite code" (`app/auth_routes.py:317-318`).
- Source maps/static: no `.map` files were present in the repo search, and no secret identifiers were found under app static JS/CSS. The app mounts only `app/static` at `/static` (`app/main.py:1463`).

Caveat: the public path traversal findings above are GET-route issues that can expose local files. They do not expose environment variables directly, but they could expose local JSON, source, or any secret-bearing files that exist on disk.

## Upload Abuse Vectors

- Arbitrary file write/path traversal: compare upload file writes use UUID job dirs and sanitized basenames (`app/compare_routes.py:1623-1634`), so I did not find arbitrary file write on that path. The actual traversal issue is public file read in `/photos` and `/uploads/facecompare`.
- RCE via image parsing: single anonymous `/api/compare/upload` queues before parsing in the non-admin path. Public `upload-multiple`, `pair/upload`, `facecompare/upload`, and `estimate/upload` do parse attacker-provided images through OpenCV/PIL/InsightFace after extension and size checks (`app/compare_routes.py:3121-3129`, `app/compare_routes.py:4267-4277`, `app/match_facecompare_routes.py:1397-1410`, `app/estimate_routes.py:1230-1235`). I found no direct RCE bug, but native image parser exposure remains a standard risk.
- SSRF: user-provided `source_url` is stored as metadata (`app/upload_routes.py:781-794`, `app/upload_routes.py:826-838`) and later copied to approved photos (`app/admin_routes.py:1294-1301`). I did not find public fetching of `source_url`. Server-side URL fetches are to configured R2/photo URLs (`app/estimate_routes.py:742-756`, `app/page_routes.py:3603-3614`), not arbitrary user URLs.
- Stored XSS: the admin pending page renders uploader/source/filename through FastHTML components and URL-quotes thumbnail paths (`app/admin_routes.py:585-600`, `app/admin_routes.py:674-710`, `app/admin_routes.py:739-745`). I found no `NotStr` use in the pending-card untrusted fields. Keep tests here, but this is not the top risk.
- Denial of service/storage exhaustion: public uploads are bounded per request in most paths, but anonymous users can still persist many files to staging/R2 (`app/compare_routes.py:1668-1700`, `app/estimate_routes.py:1095-1112`, `app/match_facecompare_routes.py:1454-1458`). Startup cleanup preserves pending staging dirs (`app/main.py:1290-1310`), and only expires entries if staging is already missing (`app/main.py:1321-1345`); it does not prove R2 cleanup.
- Content liability: random/abusive images can be stored in your R2/public upload areas and shown to admins (`app/admin_routes.py:670-710`). This is the practical owner risk from the 51 items.
- Rate limiting: in-memory 20/hour/IP (`app/rate_limit.py:6-17`) is not durable or shared. App code does not read `X-Forwarded-For`; spoofability depends on deployment/proxy behavior, not this code.

## Auth Boundary

For photos/identities, the intended boundary generally holds: anonymous compare uploads are queued, and archive ingestion requires admin approval. Approval is guarded by `_check_admin` and origin check (`app/admin_routes.py:1180-1188`), then the admin action can process the staged/R2 file into the archive (`app/admin_routes.py:1222-1307`). Rejection is admin-only and deletes staging files (`app/admin_routes.py:1390-1454`), but I did not find R2 pending-object deletion there.

Other public POSTs are intentionally public but not all are queue-only:

- Annotations are saved as `pending_unverified` for anonymous users (`app/engagement_routes.py:1052-1088`, `app/engagement_routes.py:1193-1223`).
- Person comments are public and immediately `visible` (`app/person_routes.py:2291-2323`) and rendered immediately (`app/person_routes.py:2339-2345`).
- Compare result responses are public and append to `comparison_results` (`app/compare_routes.py:3870-3892`).
- Main `/upload` is login-gated by `_check_login` (`app/upload_routes.py:579-623`).
- Sync mutation routes are bearer-token gated (`app/sync_routes.py:23-31`, `app/sync_routes.py:343-356`).

## Legitimacy Assessment

The probability that the 51 reported items are legitimate Rhodes heritage contributions is very low. The data pattern is exactly what the anonymous compare route produces: `source: "Compare Upload"`, `uploader_email: "unknown"`, no source URL, no collection, and pending review. The owner-observed content pattern, random modern selfies/social-media faces over about 11 days, is much more consistent with bots, curiosity usage, or low-effort probing of a public face-compare tool than with heritage contribution. Some could be benign visitors testing "compare my face to the archive," but without uploader identity/source and with modern random faces, they should not be treated as archive contributions.

## WHAT_TO_DO_NOW

1. Do not approve the 51 unknown compare uploads. Reject them in the admin UI or mark them rejected in the queue using the app's canonical admin path; then delete any matching `data/staging/{job_id}` directories and R2 objects under `uploads/pending/{job_id}/...`. The current reject path deletes staging (`app/admin_routes.py:1449-1454`) but I found no R2 pending-object delete.
2. Immediately fix the public file-read path traversal in `/photos/{filename:path}` and `/uploads/facecompare/{filename:path}`. Until fixed, use edge rules to block encoded/literal traversal attempts containing `..`, `%2e`, `%2f`, or suspicious `/photos/` and `/uploads/facecompare/` paths.
3. Temporarily disable anonymous durable compare uploads or require login/Turnstile before `/api/compare/upload`, `/api/compare/upload-multiple`, `/api/compare/pair/upload`, `/api/facecompare/upload`, and `/api/estimate/upload`.
4. Rotate `ML_SERVICE_TOKEN` if the value in `docs/session_logs/session-116-log.md` was ever real, even though it is not normally browser-routed.
5. Add Cloudflare/Railway edge rate limits and a shared Redis/Postgres limiter. Keep the in-process limiter only as defense-in-depth.
6. Add lifecycle cleanup: auto-expire pending compare uploads, delete R2 pending objects on reject/expiry, and keep compare-only uploads private or short-lived.
7. Product fix: separate "compare a face" from "contribute to archive." Compare should be ephemeral by default; contribution should require explicit consent, source/provenance fields, uploader contact/login, and admin moderation.
