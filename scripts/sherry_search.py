"""One-time analysis: find Sherry Fader candidates in the Fader collection.
READ-ONLY — does not modify any data."""

import os
import sys
from pathlib import Path

# Load env
for line in Path(__file__).resolve().parent.parent.joinpath(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from app.supabase_data import get_supabase_client
from core.embeddings_io import generate_face_id

client = get_supabase_client()

FADER_COMM_ID = "1a2c23d6-fc5e-4d0e-b020-1721579485bf"

# Get Fader faces
fader_photos = client.table("photo_communities").select("photo_id").eq("community_id", FADER_COMM_ID).execute()
fader_pids = set(r["photo_id"] for r in fader_photos.data)
fader_faces = []
for pid in fader_pids:
    faces = client.table("photo_faces").select("face_id,photo_id").eq("photo_id", pid).execute()
    fader_faces.extend(faces.data)
fader_face_ids = set(f["face_id"] for f in fader_faces)

# Load embeddings — handle both 'mu' and 'embeddings' field names
emb = np.load("data/embeddings.npy", allow_pickle=True)
emb_dict = {}
face_counts = {}
for entry in emb:
    fid = entry.get("face_id", None)
    if fid is None:
        fn = entry.get("filename", "")
        idx = face_counts.get(fn, 0)
        face_counts[fn] = idx + 1
        fid = generate_face_id(fn, idx)
    vec = entry.get("mu", entry.get("embeddings", None))
    if vec is not None:
        emb_dict[fid] = np.array(vec).flatten()

# Sherry's single local anchor
sherry_vec = emb_dict["inbox_bf466c0ee9b5"]
sherry_norm = sherry_vec / np.linalg.norm(sherry_vec)

distances = []
for fid in fader_face_ids:
    if fid in emb_dict:
        vec = emb_dict[fid] / np.linalg.norm(emb_dict[fid])
        dist = float(np.linalg.norm(sherry_norm - vec))
        distances.append((fid, dist))

distances.sort(key=lambda x: x[1])
print(f"Fader faces with embeddings: {len(distances)}/{len(fader_face_ids)}")
print("\nTop 25 closest to Sherry:")
for fid, dist in distances[:25]:
    pf = [f for f in fader_faces if f["face_id"] == fid]
    pid = pf[0]["photo_id"] if pf else "?"
    photo = client.table("photos").select("path").eq("photo_id", pid).execute()
    fname = photo.data[0]["path"].split("/")[-1][:55] if photo.data else "?"
    dl = client.table("date_labels").select("data").eq("photo_id", pid).execute()
    year = ""
    if dl.data and dl.data[0].get("data"):
        d = dl.data[0]["data"]
        if isinstance(d, dict):
            year = d.get("estimated_year", d.get("year_estimate", ""))
    pfaces = [f for f in fader_faces if f["photo_id"] == pid]
    print(f"  {dist:.4f} | {len(pfaces)}f | ~{year:>5} | {fname}")

all_dists = [d for _, d in distances]
print(f"\nUnder 0.8: {sum(1 for d in all_dists if d < 0.8)}")
print(f"Under 0.9: {sum(1 for d in all_dists if d < 0.9)}")
print(f"Under 1.0: {sum(1 for d in all_dists if d < 1.0)}")

# Check wedding photo
print("\n=== Photo 4bb9897005241971 (wedding?) ===")
p = client.table("photos").select("path").eq("photo_id", "4bb9897005241971").execute()
if p.data:
    print(f"Path: {p.data[0]['path']}")
    faces = client.table("photo_faces").select("face_id").eq("photo_id", "4bb9897005241971").execute()
    print(f"Faces in photo: {len(faces.data)}")
    for f in faces.data:
        fid = f["face_id"]
        if fid in emb_dict:
            vec = emb_dict[fid] / np.linalg.norm(emb_dict[fid])
            d = float(np.linalg.norm(sherry_norm - vec))
            print(f"  {fid} -> Sherry dist: {d:.4f}")
        else:
            print(f"  {fid} -> no local embedding")
