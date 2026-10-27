"""
Smart Battery AI - Baseline ML Model Training & Comparison Pipeline
===================================================================
Trains circular time predictors on leak-free features using a chronological
per-user split. Compares Naive Baseline, Linear Regression, Random Forest,
and Gradient Boosting, serializing the winning model.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

from ml.preprocessing import (
    SAFE_FEATURE_COLUMNS,
    EXCLUDED_LEAKAGE_COLUMNS,
    chronological_per_user_split,
    extract_safe_features,
    extract_targets,
    circular_error_minutes,
)
from ml.model import (
    NaiveBaselinePredictor,
    CircularTargetRegressor,
    save_circular_model,
)
from ml.evaluate import (
    calculate_circular_metrics,
    analyze_errors_by_segments,
    plot_model_comparison,
    plot_actual_vs_predicted,
    plot_prediction_error_distribution,
    plot_error_by_user,
    plot_error_by_profile,
)


def run_training_pipeline(
    data_path: str = "data/charging_behavior.csv",
    output_model_dir: str = "ml/models",
    docs_analysis_dir: str = "docs/model_analysis",
) -> Dict[str, Any]:
    """
    Executes the complete baseline machine learning experiment.
    """
    print("=" * 80)
    print("SMART BATTERY AI - BASELINE MACHINE LEARNING EXPERIMENT")
    print("=" * 80)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Charging behavior dataset not found at: {data_path}")

    # 1. Load Dataset
    print(f"\n1. LOADING LONGITUDINAL DATASET: {data_path}")
    raw_df = pd.read_csv(data_path)
    print(f"   - Total rows: {len(raw_df):,}")
    print(f"   - Unique users: {raw_df['user_id'].nunique()}")

    # 2. Chronological Per-User Train/Test Split
    print("\n2. EXECUTING CHRONOLOGICAL PER-USER TRAIN/TEST SPLIT (80% / 20%)...")
    train_df, test_df = chronological_per_user_split(raw_df, train_ratio=0.8)
    n_train = len(train_df)
    n_test = len(test_df)
    n_users_train = train_df["user_id"].nunique()
    n_users_test = test_df["user_id"].nunique()

    print(f"   - Training Set:   {n_train:,} rows ({n_train / len(raw_df) * 100:.1f}%) | Users: {n_users_train}")
    print(f"   - Testing Set:    {n_test:,} rows ({n_test / len(raw_df) * 100:.1f}%) | Users: {n_users_test}")
    print("   - Temporal guarantee: For all 100 users, all training sessions chronologically precede test sessions.")

    # 3. Feature Extraction (Strictly Leakage-Safe)
    print("\n3. EXTRACTING LEAKAGE-SAFE FEATURES...")
    print(f"   - Features Used ({len(SAFE_FEATURE_COLUMNS)}): {', '.join(SAFE_FEATURE_COLUMNS)}")
    print(f"   - Features Banned ({len(EXCLUDED_LEAKAGE_COLUMNS)}): {', '.join(EXCLUDED_LEAKAGE_COLUMNS)}")

    X_train = extract_safe_features(train_df)
    y_train_hour, y_train_sin, y_train_cos = extract_targets(train_df)

    X_test = extract_safe_features(test_df)
    y_test_hour, y_test_sin, y_test_cos = extract_targets(test_df)

    # 4. Define Candidate Architectures
    candidates: List[Tuple[str, Any]] = [
        ("Naive Baseline", NaiveBaselinePredictor()),
        ("Linear Regression", CircularTargetRegressor(
            LinearRegression(),
            LinearRegression(),
            name="Linear Regression"
        )),
        ("Random Forest", CircularTargetRegressor(
            RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1),
            RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1),
            name="Random Forest"
        )),
        ("Gradient Boosting", CircularTargetRegressor(
            GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.08, random_state=42),
            GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.08, random_state=42),
            name="Gradient Boosting"
        )),
    ]

    # 5. Fit & Evaluate Models
    print("\n4. TRAINING & EVALUATING CANDIDATE MODELS...")
    results = []
    trained_models = {}
    test_predictions = {}

    for name, model in candidates:
        print(f"   --> Training: {name}...")
        model.fit(X_train, y_train_sin, y_train_cos)
        preds_hour = model.predict_hour(X_test)

        metrics = calculate_circular_metrics(y_test_hour, preds_hour)
        metrics["Model"] = name
        results.append(metrics)
        trained_models[name] = model
        test_predictions[name] = preds_hour

    # 6. Format Model Comparison Table
    comp_df = pd.DataFrame(results)
    comp_df = comp_df[["Model", "mae_minutes", "median_minutes", "rmse_minutes", "within_15_min_pct", "within_30_min_pct", "within_60_min_pct"]]
    comp_df.columns = ["Model", "MAE (min)", "Median Error (min)", "RMSE (min)", "Within 15 min (%)", "Within 30 min (%)", "Within 60 min (%)"]

    print("\n" + "=" * 80)
    print("BASELINE MODEL COMPARISON RESULTS (CHRONOLOGICAL TEST SET)")
    print("=" * 80)
    print(comp_df.to_string(index=False))
    print("=" * 80)

    # 7. Select Best Model (Primary Metric: Lowest Test MAE)
    best_row = comp_df.sort_values(by="MAE (min)").iloc[0]
    best_model_name = best_row["Model"]
    best_mae = best_row["MAE (min)"]
    best_model = trained_models[best_model_name]
    best_preds = test_predictions[best_model_name]

    print(f"\n5. MODEL SELECTION:")
    print(f"   - Selected Winner:  **{best_model_name}**")
    print(f"   - Validation MAE:   **{best_mae:.2f} minutes** ({best_mae / 60.0:.2f} hours)")
    print(f"   - Within 30 min:    **{best_row['Within 30 min (%)']:.1f}%**")
    print(f"   - Within 60 min:    **{best_row['Within 60 min (%)']:.1f}%**")

    # 8. Save Best Model & Metadata
    os.makedirs(output_model_dir, exist_ok=True)
    metadata = {
        "model_version": "1.0.0-baseline-global",
        "algorithm": best_model_name,
        "training_timestamp": datetime.utcnow().isoformat() + "Z",
        "features": SAFE_FEATURE_COLUMNS,
        "excluded_features": EXCLUDED_LEAKAGE_COLUMNS,
        "dataset_split": {
            "strategy": "chronological_per_user",
            "train_ratio": 0.8,
            "train_rows": n_train,
            "test_rows": n_test,
            "unique_users": n_users_train,
        },
        "target_representation": {
            "target": "unplug_hour",
            "strategy": "dual_sin_cos_circular",
            "period": 24.0,
        },
        "metrics": {
            "mae_minutes": float(best_row["MAE (min)"]),
            "median_minutes": float(best_row["Median Error (min)"]),
            "rmse_minutes": float(best_row["RMSE (min)"]),
            "within_15_min_pct": float(best_row["Within 15 min (%)"]),
            "within_30_min_pct": float(best_row["Within 30 min (%)"]),
            "within_60_min_pct": float(best_row["Within 60 min (%)"]),
        },
        "all_model_comparison": comp_df.to_dict(orient="records"),
    }

    if hasattr(best_model, "model_sin") and hasattr(best_model, "model_cos"):
        save_circular_model(best_model.model_sin, best_model.model_cos, metadata, model_dir=output_model_dir)
    else:
        # Save naive baseline if it won
        save_circular_model(best_model, best_model, metadata, model_dir=output_model_dir)

    print(f"   [OK] Best model artifacts saved in: {output_model_dir}")

    # 9. Segmented Error Analysis
    print("\n6. CONDUCTING SEGMENTED ERROR ANALYSIS FOR BEST MODEL...")
    segment_results = analyze_errors_by_segments(test_df, y_test_hour, best_preds)

    print("\n   A. Performance by Behavioral Profile:")
    for prof, pstats in segment_results["profile_mae"].items():
        print(f"      - {prof:18s}: MAE = {pstats['mae_minutes']:6.1f} min | Median = {pstats['median_minutes']:5.1f} min (N={pstats['sessions']})")

    print("\n   B. Performance by Calendar Type:")
    print(f"      - Weekday MAE: {segment_results['calendar_mae']['weekday_mae_minutes']} minutes")
    print(f"      - Weekend MAE: {segment_results['calendar_mae']['weekend_mae_minutes']} minutes")

    print("\n   C. User-Level Outliers:")
    print("      - Top 3 Best-Predicted Users (Lowest Error):")
    for u in segment_results["lowest_error_users"][:3]:
        print(f"        * User {u['user_id']:3d}: MAE = {u['user_mae']:.1f} min ({u['session_count']} test sessions)")
    print("      - Top 3 Hardest-to-Predict Users (Highest Error):")
    for u in segment_results["highest_error_users"][:3]:
        print(f"        * User {u['user_id']:3d}: MAE = {u['user_mae']:.1f} min ({u['session_count']} test sessions)")

    # 10. Generate Visualizations (Matplotlib ONLY)
    print(f"\n7. GENERATING EVALUATION VISUALIZATIONS in {docs_analysis_dir}...")
    os.makedirs(docs_analysis_dir, exist_ok=True)
    p1 = plot_model_comparison(comp_df, docs_analysis_dir)
    print(f"   [OK] {os.path.basename(p1)} saved")
    p2 = plot_actual_vs_predicted(y_test_hour, best_preds, docs_analysis_dir)
    print(f"   [OK] {os.path.basename(p2)} saved")
    err_min = circular_error_minutes(y_test_hour, best_preds, period=24.0)
    p3 = plot_prediction_error_distribution(err_min, docs_analysis_dir)
    print(f"   [OK] {os.path.basename(p3)} saved")
    p4 = plot_error_by_user(segment_results["per_user_errors"], docs_analysis_dir)
    print(f"   [OK] {os.path.basename(p4)} saved")
    p5 = plot_error_by_profile(segment_results["analysis_df"], docs_analysis_dir)
    print(f"   [OK] {os.path.basename(p5)} saved")

    print("\n" + "=" * 80)
    print("BASELINE ML PIPELINE EXECUTION COMPLETED SUCCESSFULLY.")
    print("=" * 80)

    return {
        "comparison_df": comp_df,
        "best_model_name": best_model_name,
        "metadata": metadata,
        "segment_results": segment_results,
    }


if __name__ == "__main__":
    run_training_pipeline()
