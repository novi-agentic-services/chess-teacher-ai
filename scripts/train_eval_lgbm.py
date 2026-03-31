#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score


DROP_COLS = {
    "game_id", "ply_index", "fen", "game_date", "split",
    "y_cp_raw", "y_cp_clip", "y_tanh",
}


def load_split(path):
    return pd.read_csv(path)


def prepare_xy(df):
    y_tanh = df["y_tanh"].astype(float)
    y_cp_clip = df["y_cp_clip"].astype(float)

    x = df[[c for c in df.columns if c not in DROP_COLS]].copy()
    cat_cols = [c for c in ["eco", "opening_family"] if c in x.columns]
    x = pd.get_dummies(x, columns=cat_cols, dummy_na=True)
    return x, y_tanh, y_cp_clip


def align_columns(train_x, other_x):
    for c in train_x.columns:
        if c not in other_x.columns:
            other_x[c] = 0
    extra = [c for c in other_x.columns if c not in train_x.columns]
    if extra:
        other_x = other_x.drop(columns=extra)
    return other_x[train_x.columns]


def tanh_to_cp(y_tanh):
    y = np.clip(np.array(y_tanh, dtype=float), -0.999999, 0.999999)
    return np.arctanh(y) * 400.0


def eval_metrics(y_true_tanh, y_pred_tanh):
    true_cp = tanh_to_cp(y_true_tanh)
    pred_cp = tanh_to_cp(y_pred_tanh)
    return {
        "mae_cp": float(mean_absolute_error(true_cp, pred_cp)),
        "r2_cp": float(r2_score(true_cp, pred_cp)),
    }


def phase_bucket(phase):
    if phase < 0.33:
        return "endgame"
    if phase < 0.66:
        return "middlegame"
    return "opening"


def eval_bucket(cp):
    a = abs(cp)
    if a < 80:
        return "equal"
    if a < 250:
        return "slight"
    if a < 600:
        return "clear"
    return "decisive"


def bucket_report(df, y_pred_tanh):
    pred_cp = tanh_to_cp(y_pred_tanh)
    tmp = df.copy()
    tmp["pred_cp"] = pred_cp
    tmp["err"] = (tmp["y_cp_clip"] - tmp["pred_cp"]).abs()
    tmp["phase_bucket"] = tmp["phase"].apply(phase_bucket)
    tmp["eval_bucket"] = tmp["y_cp_clip"].apply(eval_bucket)

    phase_stats = (
        tmp.groupby("phase_bucket")["err"]
        .mean()
        .sort_index()
        .to_dict()
    )
    eval_stats = (
        tmp.groupby("eval_bucket")["err"]
        .mean()
        .sort_index()
        .to_dict()
    )
    return {
        "phase_mae_cp": {k: float(v) for k, v in phase_stats.items()},
        "eval_bucket_mae_cp": {k: float(v) for k, v in eval_stats.items()},
    }


def train_model(x_train, y_train):
    model_name = ""
    try:
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=1000,
            learning_rate=0.03,
            num_leaves=63,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
        )
        model.fit(x_train, y_train)
        model_name = "LightGBM"
        return model, model_name
    except Exception:
        from sklearn.ensemble import HistGradientBoostingRegressor

        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=10,
            max_iter=500,
            random_state=42,
        )
        model.fit(x_train, y_train)
        model_name = "HistGradientBoostingRegressor"
        return model, model_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features-dir", default="data/features")
    ap.add_argument("--report", default="reports/lc0_feature_baseline_report.md")
    ap.add_argument("--model-out", default="data/features/model_metrics.json")
    args = ap.parse_args()

    fd = Path(args.features_dir)
    train_df = load_split(fd / "features_train.csv")
    valid_df = load_split(fd / "features_valid.csv")
    test_df = load_split(fd / "features_test.csv")

    if len(train_df) == 0 or len(valid_df) == 0 or len(test_df) == 0:
        raise RuntimeError("Feature splits are empty. Run extract_lc0_features.py after LC0 eval data exists.")

    x_train, y_train_tanh, _ = prepare_xy(train_df)
    x_valid, y_valid_tanh, _ = prepare_xy(valid_df)
    x_test, y_test_tanh, _ = prepare_xy(test_df)

    x_valid = align_columns(x_train, x_valid)
    x_test = align_columns(x_train, x_test)

    model, model_name = train_model(x_train, y_train_tanh)
    valid_pred = model.predict(x_valid)
    test_pred = model.predict(x_test)

    valid_m = eval_metrics(y_valid_tanh, valid_pred)
    test_m = eval_metrics(y_test_tanh, test_pred)
    valid_b = bucket_report(valid_df, valid_pred)
    test_b = bucket_report(test_df, test_pred)

    metrics = {
        "model": model_name,
        "rows": {
            "train": int(len(train_df)),
            "valid": int(len(valid_df)),
            "test": int(len(test_df)),
        },
        "valid": {**valid_m, **valid_b},
        "test": {**test_m, **test_b},
    }

    model_out = Path(args.model_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    model_out.write_text(json.dumps(metrics, indent=2))

    report_lines = [
        "# LC0 Feature Baseline Report",
        "",
        f"Model: **{model_name}**",
        "",
        "## Dataset sizes",
        f"- Train: {metrics['rows']['train']}",
        f"- Valid: {metrics['rows']['valid']}",
        f"- Test: {metrics['rows']['test']}",
        "",
        "## Validation",
        f"- MAE(cp): {valid_m['mae_cp']:.2f}",
        f"- R2(cp): {valid_m['r2_cp']:.4f}",
        "- Phase MAE(cp):",
    ]
    for k, v in valid_b["phase_mae_cp"].items():
        report_lines.append(f"  - {k}: {v:.2f}")
    report_lines.append("- Eval-bucket MAE(cp):")
    for k, v in valid_b["eval_bucket_mae_cp"].items():
        report_lines.append(f"  - {k}: {v:.2f}")

    report_lines += [
        "",
        "## Test",
        f"- MAE(cp): {test_m['mae_cp']:.2f}",
        f"- R2(cp): {test_m['r2_cp']:.4f}",
        "- Phase MAE(cp):",
    ]
    for k, v in test_b["phase_mae_cp"].items():
        report_lines.append(f"  - {k}: {v:.2f}")
    report_lines.append("- Eval-bucket MAE(cp):")
    for k, v in test_b["eval_bucket_mae_cp"].items():
        report_lines.append(f"  - {k}: {v:.2f}")

    report_lines += [
        "",
        "## Notes",
        "- Target: y_tanh = tanh(clip(cp,-1000,1000)/400).",
        "- Metrics converted back to cp-space for readability.",
    ]

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(report_lines) + "\n")

    print(metrics)


if __name__ == "__main__":
    main()
