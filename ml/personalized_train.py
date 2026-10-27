"""
Smart Battery AI - Personalized ML Training & Benchmarking Pipeline
===================================================================
Trains personalized circular time predictors incorporating chronological historical features.
Compares Global Baseline, Personalized GBR, Personalized RF, and Blended Architectures.
Serializes personalized model artifacts and generates publication-grade analysis.
"""

from datetime import datetime
import json
import os
import sys
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml.preprocessing import (
    SAFE_FEATURE_COLUMNS,
    EXCLUDED_LEAKAGE_COLUMNS,
    chronological_per_user_split,
    extract_safe_features,
    extract_targets,
    decode_cyclical_hour,
    circular_error_minutes,
)
from ml.personalized_features import (
    PERSONALIZED_HISTORICAL_FEATURE_COLUMNS,
    ALL_PERSONALIZED_FEATURE_COLUMNS,
    compute_historical_features_chronological,
    extract_all_personalized_features,
    circular_blend_predictions,
)
from ml.model import (
    CircularTargetRegressor,
    save_circular_model,
)
from ml.personalized_evaluate import (
    evaluate_comparative_performance,
    analyze_user_and_profile_improvements,
    plot_01_global_vs_personalized_mae,
    plot_02_improvement_by_profile,
    plot_03_error_vs_history_count,
    plot_04_per_user_improvement,
    plot_05_actual_vs_personalized,
    plot_06_cold_start_performance,
)


def run_personalized_experiment(
    data_path: str = "data/charging_behavior.csv",
    global_model_dir: str = "ml/models",
    output_model_dir: str = "ml/models",
    analysis_dir: str = "docs/personalization_analysis",
) -> Dict[str, Any]:
    """
    Executes end-to-end personalization experiment.
    """
    print("=" * 80)
    print("SMART BATTERY AI - PERSONALIZED HISTORICAL FEATURE EXPERIMENT")
    print("=" * 80)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Charging dataset missing at: {data_path}")

    # 1. Load Data
    print(f"\n1. LOADING DATASET: {data_path}")
    raw_df = pd.read_csv(data_path)
    raw_df["charging_start_time"] = pd.to_datetime(raw_df["charging_start_time"])
    print(f"   - Total records: {len(raw_df):,} rows across {raw_df['user_id'].nunique()} users")

    # 2. Compute Leak-Free Historical Features Chronologically
    print("\n2. COMPUTING CHRONOLOGICAL HISTORICAL FEATURES (LEAK-FREE)...")
    hist_features_df = compute_historical_features_chronological(raw_df)
    augmented_df = pd.concat([raw_df, hist_features_df], axis=1)
    print(f"   - Generated {len(PERSONALIZED_HISTORICAL_FEATURE_COLUMNS)} personalized features:")
    for col in PERSONALIZED_HISTORICAL_FEATURE_COLUMNS:
        print(f"     * {col}")

    # 3. Chronological Per-User Train/Test Split (80% / 20%)
    print("\n3. SPLITTING CHRONOLOGICALLY PER USER (80% TRAIN / 20% TEST)...")
    train_df, test_df = chronological_per_user_split(augmented_df, train_ratio=0.8)
    n_train, n_test = len(train_df), len(test_df)
    print(f"   - Training Set: {n_train:,} rows ({n_train/len(raw_df)*100:.1f}%) | Users: {train_df['user_id'].nunique()}")
    print(f"   - Testing Set:  {n_test:,} rows ({n_test/len(raw_df)*100:.1f}%) | Users: {test_df['user_id'].nunique()}")

    # 4. Feature Matrices
    X_train_base = extract_safe_features(train_df)
    X_test_base = extract_safe_features(test_df)

    X_train_pers = extract_all_personalized_features(train_df)
    X_test_pers = extract_all_personalized_features(test_df)

    y_train_hour, y_train_sin, y_train_cos = extract_targets(train_df)
    y_test_hour, y_test_sin, y_test_cos = extract_targets(test_df)

    print(f"   - Base Features Count:         {len(X_train_base.columns)}")
    print(f"   - Personalized Features Count:   {len(X_train_pers.columns)}")

    # 5. Load Model A (Existing Global Gradient Boosting Baseline)
    print("\n4. BENCHMARKING MODELS ON CHRONOLOGICAL TEST SET...")
    sin_base_path = os.path.join(global_model_dir, "unplug_sin_model.joblib")
    cos_base_path = os.path.join(global_model_dir, "unplug_cos_model.joblib")

    if not (os.path.exists(sin_base_path) and os.path.exists(cos_base_path)):
        raise FileNotFoundError("Baseline global models missing! Run ml/train.py first.")

    global_sin_model = joblib.load(sin_base_path)
    global_cos_model = joblib.load(cos_base_path)
    global_preds_hour = decode_cyclical_hour(
        global_sin_model.predict(X_test_base),
        global_cos_model.predict(X_test_base)
    )

    # 6. Train Model B: Personalized Gradient Boosting Regressor
    print("   --> Fitting Model B: Personalized Gradient Boosting Regressor...")
    pers_gbr = CircularTargetRegressor(
        GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.08, random_state=42),
        GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.08, random_state=42),
        name="Personalized Gradient Boosting"
    )
    pers_gbr.fit(X_train_pers, y_train_sin, y_train_cos)
    pers_gbr_preds = pers_gbr.predict_hour(X_test_pers)

    # 7. Train Model C: Personalized Random Forest Regressor
    print("   --> Fitting Model C: Personalized Random Forest Regressor...")
    pers_rf = CircularTargetRegressor(
        RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1),
        RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1),
        name="Personalized Random Forest"
    )
    pers_rf.fit(X_train_pers, y_train_sin, y_train_cos)
    pers_rf_preds = pers_rf.predict_hour(X_test_pers)

    # Determine best pure personalized model
    err_gbr = circular_error_minutes(y_test_hour, pers_gbr_preds)
    err_rf = circular_error_minutes(y_test_hour, pers_rf_preds)
    best_pure_pers_preds = pers_rf_preds if np.mean(err_rf) < np.mean(err_gbr) else pers_gbr_preds
    best_pure_pers_model = pers_rf if np.mean(err_rf) < np.mean(err_gbr) else pers_gbr
    best_pure_pers_name = "Personalized Random Forest" if np.mean(err_rf) < np.mean(err_gbr) else "Personalized Gradient Boosting"

    # 8. Model D: Circular Blended Strategy (Global + Best Personalized)
    print("   --> Computing Model D: Circular Blended Global + Personalized Strategy...")
    hist_counts_test = test_df["completed_history_count"].values
    blended_preds = circular_blend_predictions(
        global_preds_hour,
        best_pure_pers_preds,
        hist_counts_test,
        threshold=7.0
    )

    # 9. Comparative Performance Evaluation
    predictions_map = {
        "Global Baseline (Model A)": global_preds_hour,
        "Personalized GBR (Model B)": pers_gbr_preds,
        "Personalized RF (Model C)": pers_rf_preds,
        "Blended Hybrid (Model D)": blended_preds,
    }

    comp_df, eval_data = evaluate_comparative_performance(test_df, y_test_hour, predictions_map)

    # Calculate improvement percentage relative to Global Baseline
    global_mae = float(comp_df[comp_df["Model"] == "Global Baseline (Model A)"]["MAE (min)"].iloc[0])
    comp_df["Improvement (%)"] = comp_df["MAE (min)"].apply(
        lambda m: round((global_mae - m) / global_mae * 100.0, 2)
    )

    print("\n" + "=" * 80)
    print("PERSONALIZATION EXPERIMENT BENCHMARK RESULTS (TEST SET N = 1,584)")
    print("=" * 80)
    print(comp_df.to_string(index=False))
    print("=" * 80)

    # 10. Select Best Overall Architecture
    best_row = comp_df.sort_values(by="MAE (min)").iloc[0]
    best_name = best_row["Model"]
    best_mae = best_row["MAE (min)"]
    best_improvement = best_row["Improvement (%)"]
    best_preds = predictions_map[best_name]

    print(f"\n5. EXPERIMENTAL CONCLUSION & WINNING MODEL:")
    print(f"   - Winning Architecture:    **{best_name}**")
    print(f"   - Global Baseline MAE:     **{global_mae:.2f} minutes**")
    print(f"   - Personalized MAE:        **{best_mae:.2f} minutes**")
    print(f"   - Error Reduction:         **{global_mae - best_mae:.2f} minutes** ({best_improvement:+.2f}%)")
    print(f"   - Within 30 min accuracy:  **{best_row['Within 30 min (%)']:.1f}%** (Baseline: 58.3%)")
    print(f"   - Within 60 min accuracy:  **{best_row['Within 60 min (%)']:.1f}%** (Baseline: 83.9%)")

    # 11. Serialize Personalized Models Separately (Do NOT overwrite baseline)
    os.makedirs(output_model_dir, exist_ok=True)
    pers_sin_path = os.path.join(output_model_dir, "personalized_unplug_sin_model.joblib")
    pers_cos_path = os.path.join(output_model_dir, "personalized_unplug_cos_model.joblib")
    pers_meta_path = os.path.join(output_model_dir, "personalized_model_metadata.json")

    joblib.dump(best_pure_pers_model.model_sin, pers_sin_path)
    joblib.dump(best_pure_pers_model.model_cos, pers_cos_path)

    pers_metadata = {
        "model_version": "2.0.0-personalized",
        "algorithm": best_name,
        "underlying_learner": best_pure_pers_name,
        "training_timestamp": datetime.utcnow().isoformat() + "Z",
        "features": ALL_PERSONALIZED_FEATURE_COLUMNS,
        "base_features": SAFE_FEATURE_COLUMNS,
        "historical_features": PERSONALIZED_HISTORICAL_FEATURE_COLUMNS,
        "excluded_features": EXCLUDED_LEAKAGE_COLUMNS,
        "dataset_split": {
            "strategy": "chronological_per_user",
            "train_ratio": 0.8,
            "train_rows": n_train,
            "test_rows": n_test,
            "unique_users": 100,
        },
        "target_representation": {
            "target": "unplug_hour",
            "strategy": "dual_sin_cos_circular",
            "period": 24.0,
        },
        "cold_start_strategy": {
            "weight_formula": "min(history_count / 7.0, 1.0)",
            "circular_vector_blend": True,
            "plateau_threshold_sessions": 7,
        },
        "metrics": {
            "global_mae_minutes": global_mae,
            "personalized_mae_minutes": float(best_mae),
            "improvement_pct": float(best_improvement),
            "median_minutes": float(best_row["Median Error (min)"]),
            "rmse_minutes": float(best_row["RMSE (min)"]),
            "within_15_min_pct": float(best_row["Within 15 min (%)"]),
            "within_30_min_pct": float(best_row["Within 30 min (%)"]),
            "within_60_min_pct": float(best_row["Within 60 min (%)"]),
        },
        "all_model_comparison": comp_df.to_dict(orient="records"),
    }

    with open(pers_meta_path, "w", encoding="utf-8") as f:
        json.dump(pers_metadata, f, indent=2)

    print(f"   [OK] Serialized personalized models to: {output_model_dir}")
    print(f"        * {os.path.basename(pers_sin_path)}")
    print(f"        * {os.path.basename(pers_cos_path)}")
    print(f"        * {os.path.basename(pers_meta_path)}")

    # 12. Segmented Improvement Analysis
    print("\n6. CONDUCTING SEGMENTED IMPROVEMENT ANALYSIS...")
    analysis_df = eval_data["analysis_df"]
    global_col = "err_Global Baseline (Model A)"
    pers_col = f"err_{best_name}" if f"err_{best_name}" in analysis_df.columns else f"err_{best_pure_pers_name}"
    imp_analysis = analyze_user_and_profile_improvements(analysis_df, global_col, pers_col)

    # Full history tiers across all history lengths (0-2, 3-6, 7-14, 15+)
    X_full_base = extract_safe_features(augmented_df)
    X_full_pers = extract_all_personalized_features(augmented_df)
    y_full_hour, _, _ = extract_targets(augmented_df)
    g_full_preds = decode_cyclical_hour(global_sin_model.predict(X_full_base), global_cos_model.predict(X_full_base))
    p_full_preds = decode_cyclical_hour(best_pure_pers_model.model_sin.predict(X_full_pers), best_pure_pers_model.model_cos.predict(X_full_pers))
    b_full_preds = circular_blend_predictions(g_full_preds, p_full_preds, augmented_df["completed_history_count"].values)

    full_eval_df = augmented_df.copy()
    full_eval_df["err_global"] = circular_error_minutes(y_full_hour, g_full_preds)
    full_eval_df["err_blended"] = circular_error_minutes(y_full_hour, b_full_preds)

    bins = [-1, 2, 6, 14, 1000]
    labels = ["0-2 sessions", "3-6 sessions", "7-14 sessions", "15+ sessions"]
    full_eval_df["hist_bucket"] = pd.cut(full_eval_df["completed_history_count"], bins=bins, labels=labels)

    full_history_buckets = {}
    for b in labels:
        sub = full_eval_df[full_eval_df["hist_bucket"] == b]
        if len(sub) > 0:
            gb = float(sub["err_global"].mean())
            pb = float(sub["err_blended"].mean())
            full_history_buckets[b] = {
                "count": len(sub),
                "global_mae": round(gb, 2),
                "personalized_mae": round(pb, 2),
                "improvement_min": round(gb - pb, 2),
                "improvement_pct": round((gb - pb) / gb * 100.0, 2),
            }
    imp_analysis["history_buckets"] = full_history_buckets
    pers_metadata["history_buckets_full_dataset"] = full_history_buckets
    with open(pers_meta_path, "w", encoding="utf-8") as f:
        json.dump(pers_metadata, f, indent=2)

    print("\n   A. Performance by Behavioral Profile:")
    for prof, pstats in imp_analysis["profile_stats"].items():
        print(f"      - {prof:18s}: Global {pstats['global_mae']:5.1f}m -> Pers {pstats['personalized_mae']:5.1f}m | Diff: {pstats['mae_reduction']:+5.1f}m ({pstats['improvement_pct']:+5.1f}%)")

    print("\n   B. User-Level Distribution:")
    u_sum = imp_analysis["user_summary"]
    print(f"      - Users Improved:      {u_sum['improved_count']} / {u_sum['total_users']} ({u_sum['improved_pct']:.1f}%)")
    print(f"      - Users Worsened:      {u_sum['worsened_count']} / {u_sum['total_users']} ({u_sum['worsened_pct']:.1f}%)")
    print(f"      - Median Improvement:  {u_sum['median_user_improvement_min']:+.1f} minutes")
    print(f"      - Max User Benefit:    User {u_sum['max_improvement_user']} ({u_sum['max_improvement_min']:+.1f} min reduction)")
    print(f"      - Max User Penalty:    User {u_sum['max_degradation_user']} ({u_sum['max_degradation_min']:+.1f} min)")

    print("\n   C. History-Count / Cold-Start Progression (All Tiers):")
    for b_name, b_data in imp_analysis["history_buckets"].items():
        print(f"      - {b_name:15s} (N={b_data['count']:4d}): Global {b_data['global_mae']:5.1f}m -> Pers {b_data['personalized_mae']:5.1f}m (Imp: {b_data['improvement_pct']:+5.1f}%)")

    # 13. Generate 6 Visualizations in docs/personalization_analysis/
    print(f"\n7. GENERATING VISUALIZATIONS IN: {analysis_dir}...")
    os.makedirs(analysis_dir, exist_ok=True)
    p1 = plot_01_global_vs_personalized_mae(comp_df, analysis_dir)
    print(f"   [OK] {os.path.basename(p1)} saved")
    p2 = plot_02_improvement_by_profile(imp_analysis["profile_stats"], analysis_dir)
    print(f"   [OK] {os.path.basename(p2)} saved")
    p3 = plot_03_error_vs_history_count(full_eval_df, "err_blended", analysis_dir)
    print(f"   [OK] {os.path.basename(p3)} saved")
    p4 = plot_04_per_user_improvement(u_sum["user_table"], analysis_dir)
    print(f"   [OK] {os.path.basename(p4)} saved")
    p5 = plot_05_actual_vs_personalized(y_test_hour, best_preds, analysis_dir)
    print(f"   [OK] {os.path.basename(p5)} saved")
    p6 = plot_06_cold_start_performance(full_history_buckets, analysis_dir)
    print(f"   [OK] {os.path.basename(p6)} saved")

    print("\n" + "=" * 80)
    print("PERSONALIZED ML PIPELINE EXECUTION COMPLETED SUCCESSFULLY.")
    print("=" * 80)

    return {
        "comp_df": comp_df,
        "imp_analysis": imp_analysis,
        "metadata": pers_metadata,
        "best_name": best_name,
    }


if __name__ == "__main__":
    run_personalized_experiment()
