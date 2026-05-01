import argparse
import io
import json
import os
from collections import defaultdict

import joblib
import numpy as np
from google.cloud import storage
from PIL import Image
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def parse_gs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {uri}")
    no_scheme = uri[5:]
    bucket, _, prefix = no_scheme.partition("/")
    return bucket, prefix.rstrip("/")


def image_feature(blob_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(blob_bytes)).convert("RGB").resize((64, 64))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = arr.mean(axis=(0, 1))
    std = arr.std(axis=(0, 1))
    return np.concatenate([mean, std], axis=0)


def list_class_blobs(client, bucket_name, prefix):
    by_class = defaultdict(list)
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if blob.name.endswith("/"):
            continue
        parts = blob.name.split("/")
        for part in parts:
            if part.startswith("class_"):
                by_class[part].append(blob.name)
                break
    return by_class


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-uri", required=True, help="gs://.../datasets/Food-11/vN/training")
    parser.add_argument("--output-uri", required=True, help="gs://.../models/model_vN")
    parser.add_argument("--max-per-class", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    storage_client = storage.Client()

    data_bucket, data_prefix = parse_gs_uri(args.dataset_uri)
    out_bucket, out_prefix = parse_gs_uri(args.output_uri)

    print(f"Reading training data from {args.dataset_uri}")
    by_class = list_class_blobs(storage_client, data_bucket, data_prefix)
    if not by_class:
        raise RuntimeError("No class folders found under dataset URI")

    class_names = sorted(by_class.keys())
    class_to_id = {c: i for i, c in enumerate(class_names)}

    X, y = [], []
    for class_name in class_names:
        files = sorted(by_class[class_name])[: args.max_per_class]
        print(f"Class {class_name}: using {len(files)} samples")
        for name in files:
            blob = storage_client.bucket(data_bucket).blob(name)
            feats = image_feature(blob.download_as_bytes())
            X.append(feats)
            y.append(class_to_id[class_name])

    X = np.asarray(X)
    y = np.asarray(y)

    if len(np.unique(y)) < 2:
        raise RuntimeError("Need at least two classes to train")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=args.random_state, stratify=y
    )

    model = SGDClassifier(loss="log_loss", max_iter=1000, tol=1e-3, random_state=args.random_state)
    model.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, model.predict(X_train))
    val_acc = accuracy_score(y_val, model.predict(X_val))

    metrics = {
        "num_samples": int(len(y)),
        "num_classes": int(len(class_names)),
        "train_acc": float(train_acc),
        "val_acc": float(val_acc),
    }

    os.makedirs("/tmp/model", exist_ok=True)
    model_path = "/tmp/model/model.joblib"
    meta_path = "/tmp/model/metrics.json"
    joblib.dump({"model": model, "class_to_id": class_to_id}, model_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    out_bkt = storage_client.bucket(out_bucket)
    out_bkt.blob(f"{out_prefix}/model.joblib").upload_from_filename(model_path)
    out_bkt.blob(f"{out_prefix}/metrics.json").upload_from_filename(meta_path)

    print("Training complete")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
