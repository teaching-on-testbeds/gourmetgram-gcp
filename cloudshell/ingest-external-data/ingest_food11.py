import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from google.cloud import storage

DATA_URL = "https://nyu.box.com/shared/static/m5kvcl25hfpljul3elhu6xz8y2w61op4.zip"
TRAINING_BUCKET = os.environ["GCS_TRAINING_BUCKET"]
SEED_PREFIX = "seed/Food-11"
SUBDIRS = ["training", "validation", "evaluation"]

tmp = Path(tempfile.mkdtemp(prefix="food11-"))
zip_path = tmp / "Food-11.zip"
extract_dir = tmp / "extract"
extract_dir.mkdir(parents=True, exist_ok=True)

urllib.request.urlretrieve(DATA_URL, zip_path)
with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(extract_dir)

candidate = extract_dir / "Food-11"
dataset_root = candidate if candidate.exists() else extract_dir

for subdir in SUBDIRS:
    d = dataset_root / subdir
    if not d.exists():
        continue
    for i in range(11):
        (d / f"class_{i:02d}").mkdir(parents=True, exist_ok=True)
    for f in list(d.iterdir()):
        if not f.is_file():
            continue
        parts = f.name.split("_", 1)
        if parts and parts[0].isdigit():
            cid = int(parts[0])
            if 0 <= cid <= 10:
                shutil.move(str(f), str(d / f"class_{cid:02d}" / f.name))

client = storage.Client()
bucket = client.bucket(TRAINING_BUCKET)
for subdir in SUBDIRS:
    d = dataset_root / subdir
    if not d.exists():
        continue
    for p in d.rglob("*"):
        if p.is_file():
            rel = p.relative_to(dataset_root).as_posix()
            bucket.blob(f"{SEED_PREFIX}/{rel}").upload_from_filename(str(p))

print(f"Done: gs://{TRAINING_BUCKET}/{SEED_PREFIX}/")
