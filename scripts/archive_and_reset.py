# scripts/archive_and_reset.py
import os
import shutil
import json
import datetime
import sys
from core.run_context import get_or_create_run_id, clear_run_id

# Configuration
DATA_DIR = "data"
LOG_DIR = "logs"
ARCHIVE_ROOT = "data/archive"

# Files to move (Evidence)
FILES_TO_ARCHIVE = ["identities.json", "clusters.json"]
LOG_FILE = os.path.join(LOG_DIR, "events.jsonl")

# Files to delete (State to clear)
FILES_TO_DELETE = ["identities.json", "clusters.json", "embeddings.npy"]

def main():
    print("⚠️  STARTING SCIENTIFIC ARCHIVE & RESET ⚠️")
    
    # 1. Get current Run ID (The one we are archiving)
    run_id = get_or_create_run_id()
    print(f"📌 Archiving Run ID: {run_id}")
    
    # 2. Create Archive Folder
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_path = os.path.join(ARCHIVE_ROOT, f"{run_id}_archived_{timestamp}")
    
    if os.path.exists(archive_path):
        print(f"❌ Archive path {archive_path} already exists. Aborting.")
        sys.exit(1)
    
    os.makedirs(archive_path)
    print(f"✅ Created archive: {archive_path}")
    
    # 3. Archive Data Files
    for filename in FILES_TO_ARCHIVE:
        src = os.path.join(DATA_DIR, filename)
        if os.path.exists(src):
            shutil.copy2(src, archive_path)
            print(f"   -> Archived {filename}")
            
    # 4. Archive Logs (MOVE, don't copy)
    # We move the log file because the new run needs a fresh, empty log.
    if os.path.exists(LOG_FILE):
        shutil.move(LOG_FILE, os.path.join(archive_path, "events.jsonl"))
        print(f"   -> Moved events.jsonl to archive")
        
    # 5. Generate Manifest
    manifest = {
        "archived_at": datetime.datetime.now().isoformat(),
        "original_run_id": run_id,
        "files_archived": os.listdir(archive_path)
    }
    with open(os.path.join(archive_path, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        
    print("✅ Archive Complete.")
    
    # 6. RESET (Clear active state)
    confirm = input("Are you sure you want to WIPE the active database for a NEW run? (y/n): ")
    if confirm.lower() != 'y':
        print("Reset cancelled. Archive was successful.")
        sys.exit(0)
        
    for filename in FILES_TO_DELETE:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            os.remove(path)
            print(f"   🗑️  Deleted {filename}")
            
    # 7. Clear Run ID to force a new one
    clear_run_id()
    print("   🗑️  Cleared Run ID")

    print("\n✨ System is clean. Ready for Scientific Run #2. ✨")

if __name__ == "__main__":
    main()
