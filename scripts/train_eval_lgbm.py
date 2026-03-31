#!/usr/bin/env python3
import argparse
import csv
import json
import math
import random
from pathlib import Path


META_DROP = {
    "game_id", "ply_index", "fen", "game_date", "split",
    "y_cp_raw", "y_cp_clip", "y_tanh",
}
CATEGORICAL = {"eco", "opening_family"}


def read_rows(path):
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def build_feature_spec(train_rows):
    numeric_cols = []
    cat_values = {c: set() for c in CATEGORICAL}

    for c in train_rows[0].keys():
        if c in META_DROP:
            continue
        if c in CATEGORICAL:
            continue
        numeric_cols.append(c)

    for row in train_rows:
        for c in CATEGORICAL:
            if c in row:
                cat_values[c].add(row[c] or "UNK")

    cat_values = {k: sorted(v) for k, v in cat_values.items()}
    return numeric_cols, cat_values


def featurize_rows(rows, numeric_cols, cat_values):
    X = []
    y = []
    for row in rows:
        vec = [1.0]  # bias
        for c in numeric_cols:
            v = row.get(c, "0")
            try:
                vec.append(float(v) if v != "" else 0.0)
            except ValueError:
                vec.append(0.0)

        for c in sorted(cat_values.keys()):
            cur = row.get(c, "UNK") or "UNK"
            for v in cat_values[c]:
                vec.append(1.0 if cur == v else 0.0)

        X.append(vec)
        y.append(float(row["y_tanh"]))
    return X, y


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def train_sgd(X, y, epochs=20, lr=0.01, l2=1e-6, seed=42):
    rnd = random.Random(seed)
    d = len(X[0])
    w = [0.0] * d
    idx = list(range(len(X)))

    for _ in range(epochs):
        rnd.shuffle(idx)
        for i in idx:
            xi = X[i]
            yi = y[i]
            pred = dot(w, xi)
            err = pred - yi
            for j in range(d):
                grad = err * xi[j] + l2 * w[j]
                w[j] -= lr * grad
    return w


def predict(X, w):
    return [dot(w, x) for x in X]


def tanh_to_cp(v):
    v = max(-0.999999, min(0.999999, v))
    return math.atanh(v) * 400.0


def mae(vals_true, vals_pred):
    n = len(vals_true)
    if n == 0:
        return 0.0
    return sum(abs(a - b) for a, b in zip(vals_true, vals_pred)) / n


def r2(vals_true, vals_pred):
    n = len(vals_true)
    if n == 0:
        return 0.0
    mu = sum(vals_true) / n
    ss_tot = sum((v - mu) ** 2 for v in vals_true)
    if ss_tot == 0:
        return 0.0
    ss_res = sum((a - b) ** 2 for a, b in zip(vals_true, vals_pred))
    return 1.0 - (ss_res / ss_tot)


def eval_metrics(y_true_tanh, y_pred_tanh):
    true_cp = [tanh_to_cp(v) for v in y_true_tanh]
    pred_cp = [tanh_to_cp(v) for v in y_pred_tanh]
    return {
        "mae_cp": mae(true_cp, pred_cp),
        "r2_cp": r2(true_cp, pred_cp),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features-dir", default="data/features")
    ap.add_argument("--report", default="reports/lc0_feature_baseline_report.md")
    ap.add_argument("--model-out", default="data/features/model_metrics.json")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--lr", type=float, default=0.005)
    args = ap.parse_args()

    fd = Path(args.features_dir)
    train_rows = read_rows(fd / "features_train.csv")
    valid_rows = read_rows(fd / "features_valid.csv")
    test_rows = read_rows(fd / "features_test.csv")

    if not train_rows or not valid_rows or not test_rows:
        raise RuntimeError("Feature files are empty or missing rows. Run extract_lc0_features.py first.")

    numeric_cols, cat_values = build_feature_spec(train_rows)
    X_train, y_train = featurize_rows(train_rows, numeric_cols, cat_values)
    X_valid, y_valid = featurize_rows(valid_rows, numeric_cols, cat_values)
    X_test, y_test = featurize_rows(test_rows, numeric_cols, cat_values)

    w = train_sgd(X_train, y_train, epochs=args.epochs, lr=args.lr)
    valid_pred = predict(X_valid, w)
    test_pred = predict(X_test, w)

    valid_m = eval_metrics(y_valid, valid_pred)
    test_m = eval_metrics(y_test, test_pred)

    metrics = {
        "model": "SGDLinearRegressor",
        "rows": {"train": len(train_rows), "valid": len(valid_rows), "test": len(test_rows)},
        "valid": valid_m,
        "test": test_m,
        "feature_count": len(w),
    }

    model_out = Path(args.model_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    model_out.write_text(json.dumps(metrics, indent=2))

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# LC0 Feature Baseline Report",
                "",
                "Model: **SGDLinearRegressor (stdlib)**",
                "",
                "## Dataset sizes",
                f"- Train: {metrics['rows']['train']}",
                f"- Valid: {metrics['rows']['valid']}",
                f"- Test: {metrics['rows']['test']}",
                "",
                "## Validation",
                f"- MAE(cp): {valid_m['mae_cp']:.2f}",
                f"- R2(cp): {valid_m['r2_cp']:.4f}",
                "",
                "## Test",
                f"- MAE(cp): {test_m['mae_cp']:.2f}",
                f"- R2(cp): {test_m['r2_cp']:.4f}",
                "",
                "## Notes",
                "- Target trained on y_tanh = tanh(clip(cp,-1000,1000)/400).",
                "- Metrics are reported after inverse transform to cp space.",
                "- This is dependency-free baseline; upgrade path is LightGBM/CNN when libs are installed.",
            ]
        )
    )

    print(metrics)


if __name__ == "__main__":
    main()
