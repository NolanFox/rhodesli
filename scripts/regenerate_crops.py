import sys
import os
import re
import numpy as np
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PHOTOS_DIR = PROJECT_ROOT / "raw_photos"
CROPS_DIR = PROJECT_ROOT / "app" / "static" / "crops"

CROPS_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_stem(stem: str) -> str:
    """Must match app/main.py exactly"""
    sanitized = stem.lower()
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized

def main():
    print("--- REGENERATING FACE CROPS ---")
    
    # 1. Load Embeddings (Source of Truth)
    emb_path = DATA_DIR / "embeddings.npy"
    if not emb_path.exists():
        print("Error: embeddings.npy not found!")
        sys.exit(1)
        
    embeddings = np.load(emb_path, allow_pickle=True)
    print(f"Loaded {len(embeddings)} faces from embeddings.npy")
    
    generated_count = 0
    skipped_count = 0
    error_count = 0
    
    # 2. Group by Photo to minimize file opens
    faces_by_photo = {}
    filename_counters = {} # To track face index per file
    
    for entry in embeddings:
        fname = entry["filename"]
        if fname not in faces_by_photo:
            faces_by_photo[fname] = []
            filename_counters[fname] = 0
            
        # Reconstruct the index exactly as ingest does
        face_idx = filename_counters[fname]
        filename_counters[fname] += 1
        
        faces_by_photo[fname].append({
            "bbox": entry["bbox"],
            "index": face_idx,
            "quality": entry.get("quality", 0.0)
        })

    # 3. Process Photos
    for filename, faces in tqdm(faces_by_photo.items(), desc="Processing Photos"):
        src_path = PHOTOS_DIR / filename
        if not src_path.exists():
            print(f"Warning: Source photo missing {filename}")
            error_count += len(faces)
            continue
            
        try:
            with Image.open(src_path) as img:
                # Handle orientation/exif if needed, but usually PIL handles it
                img = img.convert("RGB")
                
                sanitized_stem = sanitize_stem(src_path.stem)
                
                for face in faces:
                    # Construct target filename: {stem}_{quality}_{index}.jpg
                    quality_str = f"{face['quality']:.2f}"
                    idx = face['index']
                    crop_name = f"{sanitized_stem}_{quality_str}_{idx}.jpg"
                    crop_path = CROPS_DIR / crop_name
                    
                    if crop_path.exists():
                        skipped_count += 1
                        continue
                        
                    # Crop
                    bbox = face["bbox"]
                    if hasattr(bbox, 'tolist'): bbox = bbox.tolist()
                    x1, y1, x2, y2 = map(int, bbox)
                    
                    # Pad slightly for better visuals (optional, keeping tight for now)
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(img.width, x2)
                    y2 = min(img.height, y2)
                    
                    face_img = img.crop((x1, y1, x2, y2))
                    face_img.save(crop_path, quality=90)
                    generated_count += 1
                    
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            error_count += len(faces)

    print("\n--- SUMMARY ---")
    print(f"Generated: {generated_count}")
    print(f"Skipped (Existed): {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Total Crops in Folder: {len(list(CROPS_DIR.glob('*.jpg')))}")

if __name__ == "__main__":
    main()
