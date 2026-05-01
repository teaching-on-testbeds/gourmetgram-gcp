import json
import os
from datetime import datetime, timezone
from collections import defaultdict
from google.cloud import storage

TRAINING_BUCKET = os.environ["GCS_TRAINING_BUCKET"]
LABELED_BUCKET = os.environ["GCS_LABELED_BUCKET"]
SEED_PREFIX = "seed/Food-11/training"
SEED_VALIDATION_PREFIX = "seed/Food-11/validation"
SEED_EVALUATION_PREFIX = "seed/Food-11/evaluation"
SEED_LIMIT_PER_CLASS = 100
SEED_VALIDATION_LIMIT_PER_CLASS = 20
SEED_EVALUATION_LIMIT_PER_CLASS = 20

client = storage.Client()
t_bucket = client.bucket(TRAINING_BUCKET)
l_bucket = client.bucket(LABELED_BUCKET)

def next_version(bucket):
    max_v = 0
    for blob in client.list_blobs(bucket, prefix="datasets/Food-11/"):
        parts = blob.name.split("/")
        for p in parts:
            if p.startswith("v") and p[1:].isdigit():
                max_v = max(max_v, int(p[1:]))
    return max_v + 1

version = next_version(TRAINING_BUCKET)
OUT_BASE = f"datasets/Food-11/v{version}"

copied = 0
per_class = defaultdict(lambda: {"seed": 0, "labeled": 0})

for c in range(11):
    class_dir = f"class_{c:02d}"
    prefix = f"{SEED_PREFIX}/{class_dir}/"
    blobs = list(client.list_blobs(TRAINING_BUCKET, prefix=prefix))
    for blob in blobs[:SEED_LIMIT_PER_CLASS]:
        name = blob.name.split("/")[-1]
        dst = f"{OUT_BASE}/training/{class_dir}/seed_{name}"
        t_bucket.copy_blob(blob, t_bucket, new_name=dst)
        copied += 1
        per_class[class_dir]["seed"] += 1

# Copy fixed-size seed validation split into versioned validation directory
for c in range(11):
    class_dir = f"class_{c:02d}"
    prefix = f"{SEED_VALIDATION_PREFIX}/{class_dir}/"
    blobs = list(client.list_blobs(TRAINING_BUCKET, prefix=prefix))
    for blob in blobs[:SEED_VALIDATION_LIMIT_PER_CLASS]:
        name = blob.name.split("/")[-1]
        dst = f"{OUT_BASE}/validation/{class_dir}/seed_{name}"
        t_bucket.copy_blob(blob, t_bucket, new_name=dst)

# Copy fixed-size seed evaluation split into versioned evaluation directory
for c in range(11):
    class_dir = f"class_{c:02d}"
    prefix = f"{SEED_EVALUATION_PREFIX}/{class_dir}/"
    blobs = list(client.list_blobs(TRAINING_BUCKET, prefix=prefix))
    for blob in blobs[:SEED_EVALUATION_LIMIT_PER_CLASS]:
        name = blob.name.split("/")[-1]
        dst = f"{OUT_BASE}/evaluation/{class_dir}/seed_{name}"
        t_bucket.copy_blob(blob, t_bucket, new_name=dst)

for c in range(11):
    class_dir = f"class_{c:02d}"
    prefix = f"{class_dir}/"
    for blob in client.list_blobs(LABELED_BUCKET, prefix=prefix):
        name = blob.name.split("/")[-1]
        dst = f"{OUT_BASE}/training/{class_dir}/prod_{name}"
        l_bucket.copy_blob(blob, t_bucket, new_name=dst)
        copied += 1
        per_class[class_dir]["labeled"] += 1

metadata = {
    "version": version,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "total_images": copied,
    "seed_limit_per_class": SEED_LIMIT_PER_CLASS,
    "seed_validation_limit_per_class": SEED_VALIDATION_LIMIT_PER_CLASS,
    "seed_evaluation_limit_per_class": SEED_EVALUATION_LIMIT_PER_CLASS,
    "class_counts": per_class,
}
t_bucket.blob(f"datasets/Food-11/v{version}/metadata.json").upload_from_string(
    json.dumps(metadata, indent=2),
    content_type="application/json",
)
print(f"Prepared v{version} with {copied} images")
