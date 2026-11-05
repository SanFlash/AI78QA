"""Train a UI element classifier from reviewed CSV observations.

Required columns: tag, role, type, name_tokens, label, site_id.
The holdout split is grouped by website to avoid training/test leakage.
"""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", default="artifacts/ui-element-classifier.joblib")
    args = parser.parse_args()

    data = pd.read_csv(args.dataset)
    required = {"tag", "role", "type", "name_tokens", "label", "site_id"}
    missing = required - set(data.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")
    if data[list(required)].isna().any().any():
        raise SystemExit("Dataset contains null required values; curate it before training.")
    if data["site_id"].nunique() < 3:
        raise SystemExit("At least three distinct websites are required for grouped evaluation.")

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(data, data["label"], groups=data["site_id"]))
    train, test = data.iloc[train_idx], data.iloc[test_idx]
    if set(train["site_id"]) & set(test["site_id"]):
        raise SystemExit("Website leakage detected in the evaluation split.")

    features = ColumnTransformer([
        ("name", TfidfVectorizer(ngram_range=(1, 2), min_df=1), "name_tokens"),
        ("metadata", OneHotEncoder(handle_unknown="ignore"), ["tag", "role", "type"]),
    ])
    pipeline = Pipeline([
        ("features", features),
        ("classifier", LogisticRegression(max_iter=1200, class_weight="balanced")),
    ])
    pipeline.fit(train, train["label"])
    predictions = pipeline.predict(test)
    report = classification_report(test["label"], predictions, output_dict=True, zero_division=0)

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, output)
    metrics = {
        "held_out_sites": sorted(test["site_id"].unique().tolist()),
        "training_sites": sorted(train["site_id"].unique().tolist()),
        "sample_count": int(len(data)),
        "report": report,
        "promotion_status": "candidate_only",
    }
    output.with_suffix(output.suffix + ".metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({"macro_f1": report["macro avg"]["f1-score"], "metrics_file": str(output) + ".metrics.json"}, indent=2))


if __name__ == "__main__":
    main()
