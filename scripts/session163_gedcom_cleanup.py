#!/usr/bin/env python3
"""Session 163 — GEDCOM DB cleanup to fit Supabase Free tier (<500 MB).

Root cause (Session 163): Supabase plan reverted Pro->Free; DB at 1309 MB exceeds
the 500 MB free quota (402 exceed_db_size_quota). ~96% of the DB is GEDCOM, and
most of that is redundant historical version rows. PRD-063 only migrated
individuals+families to the efficient v2 design; relationships/events/records were
never canonicalized and still store every version.

Strategy (NO DATA LOSS — everything archived to R2 first; current data preserved):
  1. snapshot : dump gedcom_events, gedcom_records, gedcom_relationships (FULL) to
                R2 as gzipped CSV + manifest (row counts + sha256). Verify.
  2. cleanup  : DROP gedcom_events + gedcom_records (vestigial: 0 app serving refs;
                events live inline in individuals_v2.events_json; both in R2).
                DELETE superseded (is_current=false) rows from gedcom_relationships
                (keeps all current rows + the current_gedcom_relationships view).
                VACUUM FULL gedcom_relationships. Measure DB size.

Reversibility:
  - events/records: re-import from R2 cleanup snapshot (or session-156 archive).
  - relationships superseded rows: re-import from R2 cleanup snapshot.

Connection: pooler SESSION mode (port 5432) — required for VACUUM FULL (Lesson 175).
Run:
  source venv/bin/activate
  python scripts/session163_gedcom_cleanup.py snapshot
  python scripts/session163_gedcom_cleanup.py cleanup --yes-i-have-a-snapshot
  python scripts/session163_gedcom_cleanup.py measure
"""
import os, sys, gzip, hashlib, json, subprocess, tempfile, time
import psycopg2

REF = "fvynibivlphxwfowzkjl"
POOLER_HOST = "aws-0-us-west-2.pooler.supabase.com"
POOLER_PORT = 5432  # session mode — needed for VACUUM FULL
SNAP_PREFIX = "gedcom-cleanup-snapshots/2026-06-08-session-163"
TABLES = ["gedcom_events", "gedcom_records", "gedcom_relationships"]


def _env():
    from dotenv import load_dotenv
    load_dotenv()


def _conn():
    pw = os.environ["SUPABASE_DB_PASSWORD"]
    c = psycopg2.connect(host=POOLER_HOST, port=POOLER_PORT, user=f"postgres.{REF}",
                         password=pw, dbname="postgres", connect_timeout=20)
    c.autocommit = True
    return c


def _r2_env():
    return {
        **os.environ,
        "AWS_ACCESS_KEY_ID": os.environ["R2_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": os.environ["R2_SECRET_ACCESS_KEY"],
        "AWS_DEFAULT_REGION": "auto",
    }


def _r2_endpoint():
    return f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"


def _bucket():
    return os.environ["R2_BUCKET_NAME"]


def row_count(cur, table):
    cur.execute(f"SELECT count(*) FROM {table};")
    return cur.fetchone()[0]


def snapshot():
    _env()
    c = _conn(); cur = c.cursor()
    manifest = {"session": "163", "prefix": SNAP_PREFIX, "tables": {}}
    tmpdir = tempfile.mkdtemp(prefix="s163snap_")
    for t in TABLES:
        n = row_count(cur, t)
        path = os.path.join(tmpdir, f"{t}.csv.gz")
        print(f"[snapshot] dumping {t} ({n} rows) -> {path}")
        h = hashlib.sha256()
        with gzip.open(path, "wb") as f:
            copy_cur = c.cursor()
            # stream COPY directly into the gzip file
            class _W:
                def write(self, b):
                    if isinstance(b, str):
                        b = b.encode()
                    h.update(b); f.write(b)
            copy_cur.copy_expert(
                f"COPY (SELECT * FROM {t}) TO STDOUT WITH (FORMAT csv, HEADER true)", _W())
            copy_cur.close()
        size = os.path.getsize(path)
        sha = h.hexdigest()
        key = f"{SNAP_PREFIX}/{t}.csv.gz"
        print(f"[snapshot] uploading {t}: {size} bytes sha256={sha[:16]}…")
        subprocess.run(["aws", "s3", "cp", path, f"s3://{_bucket()}/{key}",
                        "--endpoint-url", _r2_endpoint()], env=_r2_env(), check=True,
                       stdout=subprocess.DEVNULL)
        manifest["tables"][t] = {"row_count": n, "size_bytes": size, "sha256": sha,
                                 "r2_key": key, "uncompressed_dump_sha256": sha}
    # write + upload manifest
    mpath = os.path.join(tmpdir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    subprocess.run(["aws", "s3", "cp", mpath,
                    f"s3://{_bucket()}/{SNAP_PREFIX}/manifest.json",
                    "--endpoint-url", _r2_endpoint()], env=_r2_env(), check=True,
                   stdout=subprocess.DEVNULL)
    print("\n[snapshot] DONE. Manifest:")
    print(json.dumps(manifest, indent=2))
    c.close()
    return manifest


def _snapshot_exists():
    """Verify the cleanup snapshot exists in R2 with all 3 tables."""
    _env()
    out = subprocess.run(["aws", "s3", "ls", f"s3://{_bucket()}/{SNAP_PREFIX}/",
                          "--endpoint-url", _r2_endpoint()], env=_r2_env(),
                         capture_output=True, text=True)
    listing = out.stdout
    have = all(f"{t}.csv.gz" in listing for t in TABLES) and "manifest.json" in listing
    return have, listing


def measure():
    _env()
    c = _conn(); cur = c.cursor()
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())), pg_database_size(current_database());")
    pretty, raw = cur.fetchone()
    print(f"DB size: {pretty} ({raw} bytes)")
    cur.execute("""SELECT c.relname, pg_size_pretty(pg_total_relation_size(c.oid))
                   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='public' AND c.relkind='r'
                   ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 8;""")
    print("Top tables:")
    for r in cur.fetchall():
        print(f"  {r[0]:32} {r[1]:>10}")
    c.close()
    return raw


def cleanup(confirmed):
    _env()
    have, listing = _snapshot_exists()
    if not have:
        print("ABORT: cleanup snapshot not found in R2. Run `snapshot` first.")
        print("R2 listing:\n" + listing)
        sys.exit(1)
    if not confirmed:
        print("ABORT: pass --yes-i-have-a-snapshot to execute mutations.")
        sys.exit(1)
    c = _conn(); cur = c.cursor()
    print("[cleanup] BEFORE:")
    measure()
    # 1. Drop vestigial tables (and their current_* views)
    for t, v in [("gedcom_events", "current_gedcom_events"),
                 ("gedcom_records", "current_gedcom_records")]:
        print(f"[cleanup] DROP VIEW {v}; DROP TABLE {t};")
        cur.execute(f"DROP VIEW IF EXISTS {v};")
        cur.execute(f"DROP TABLE IF EXISTS {t};")
    # 2. Delete superseded relationships (keep is_current=true)
    before = row_count(cur, "gedcom_relationships")
    cur.execute("DELETE FROM gedcom_relationships WHERE is_current = false;")
    deleted = cur.rowcount
    after = row_count(cur, "gedcom_relationships")
    print(f"[cleanup] relationships: {before} -> {after} (deleted {deleted} superseded)")
    # 3. Reclaim disk
    print("[cleanup] VACUUM FULL gedcom_relationships; (statement_timeout=0)")
    cur.execute("SET statement_timeout = 0;")
    t0 = time.time()
    cur.execute("VACUUM FULL gedcom_relationships;")
    print(f"[cleanup] VACUUM FULL done in {time.time()-t0:.1f}s")
    print("[cleanup] ANALYZE gedcom_relationships;")
    cur.execute("ANALYZE gedcom_relationships;")
    print("\n[cleanup] AFTER:")
    measure()
    c.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "snapshot":
        snapshot()
    elif cmd == "cleanup":
        cleanup("--yes-i-have-a-snapshot" in sys.argv)
    elif cmd == "measure":
        measure()
    else:
        print(__doc__)
