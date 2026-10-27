"""
Smart Battery AI - Recommendation Strategy Simulation & Evaluation
===================================================================
Simulates and benchmarks two charging management strategies on the chronological
test set (1,584 sessions across 100 users):

1. Strategy A: Immediate Charging (Standard baseline behavior)
   - Device starts charging immediately upon plug-in.
   - Sits idle at target SOC until user unplugs.
   - Incurs high-SOC chemical stress during early-completion idle waiting time.

2. Strategy B: Personalized Delayed Charging (Recommendation Engine)
   - Computes optimal start time from predicted unplug time and safety buffer.
   - Holds battery at lower SOC, completing charge shortly before unplug.
   - Minimizes time spent at elevated SOC while maintaining high user readiness.

Outputs quantitative metrics:
- Average early-completion high-SOC idle waiting time (minutes & hours)
- Percentage reduction in high-SOC idle time
- Mode distribution (DELAYED_CHARGE, CHARGE_NOW, CONSERVATIVE_CHARGE, etc.)
- Readiness percentage at unplug time
- Profile-level comparative breakdown
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import joblib

# Ensure project root and backend are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ml.preprocessing import (
    chronological_per_user_split,
    extract_safe_features,
    decode_cyclical_hour,
)
from ml.personalized_features import (
    compute_historical_features_chronological,
    extract_all_personalized_features,
    circular_blend_predictions,
)
from app.services.recommendation_engine import (
    RecommendationEngine,
    RecommendationConfig,
)
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationMode,
)


def run_recommendation_evaluation(
    data_path: str = "data/charging_behavior.csv",
    model_dir: str = "ml/models",
    target_soc: float = 80.0,
) -> Dict[str, Any]:
    """
    Simulates charging sessions on the chronological test split.
    """
    print("=" * 80)
    print("SMART BATTERY AI - RECOMMENDATION STRATEGY SIMULATION & EVALUATION")
    print("=" * 80)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file missing at: {data_path}")

    # 1. Load Data & Compute Historical Features
    print(f"\n1. LOADING DATASET: {data_path}")
    raw_df = pd.read_csv(data_path)
    raw_df["charging_start_time"] = pd.to_datetime(raw_df["charging_start_time"])
    raw_df["unplug_time"] = pd.to_datetime(raw_df["unplug_time"])

    print("2. COMPUTING LEAK-FREE HISTORICAL FEATURES CHRONOLOGICALLY...")
    hist_features = compute_historical_features_chronological(raw_df)
    augmented_df = pd.concat([raw_df, hist_features], axis=1)

    print("3. SPLITTING CHRONOLOGICALLY PER USER (80% TRAIN / 20% TEST)...")
    train_df, test_df = chronological_per_user_split(augmented_df, train_ratio=0.8)
    n_test = len(test_df)
    print(f"   - Test Set: {n_test:,} sessions across {test_df['user_id'].nunique()} users")

    # 4. Load Models & Generate Predictions
    print("\n4. LOADING ML MODELS & COMPUTING TEST PREDICTIONS...")
    global_sin_path = os.path.join(model_dir, "unplug_sin_model.joblib")
    global_cos_path = os.path.join(model_dir, "unplug_cos_model.joblib")
    pers_sin_path = os.path.join(model_dir, "personalized_unplug_sin_model.joblib")
    pers_cos_path = os.path.join(model_dir, "personalized_unplug_cos_model.joblib")

    g_sin_model = joblib.load(global_sin_path)
    g_cos_model = joblib.load(global_cos_path)
    p_sin_model = joblib.load(pers_sin_path)
    p_cos_model = joblib.load(pers_cos_path)

    X_test_base = extract_safe_features(test_df)
    X_test_pers = extract_all_personalized_features(test_df)

    g_preds = decode_cyclical_hour(g_sin_model.predict(X_test_base), g_cos_model.predict(X_test_base))
    p_preds = decode_cyclical_hour(p_sin_model.predict(X_test_pers), p_cos_model.predict(X_test_pers))
    blended_hours = circular_blend_predictions(
        g_preds,
        p_preds,
        test_df["completed_history_count"].values,
        threshold=7.0,
    )
    test_df = test_df.copy()
    test_df["predicted_unplug_hour"] = blended_hours

    # 5. Initialize Recommendation Engine
    engine = RecommendationEngine(RecommendationConfig(default_target_soc=target_soc))

    # 6. Execute Session Simulations
    print(f"\n5. SIMULATING CHARGING STRATEGIES (Target SOC = {target_soc:.0f}%)...")
    sim_records = []

    for _, row in test_df.iterrows():
        user_id = int(row["user_id"])
        start_dt = row["charging_start_time"].to_pydatetime()
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        actual_unplug_dt = row["unplug_time"].to_pydatetime()
        if actual_unplug_dt.tzinfo is None:
            actual_unplug_dt = actual_unplug_dt.replace(tzinfo=timezone.utc)

        start_soc = float(row["start_battery_percent"])
        charger_type = str(row.get("charger_type", "standard")).lower()
        profile = str(row.get("profile_type", "UNKNOWN"))
        circ_std = float(row.get("user_hist_unplug_circular_std", 1.0))
        rate_pct_per_hr = engine.get_charging_rate(charger_type)

        # Convert predicted clock hour to datetime
        pred_hour = float(row["predicted_unplug_hour"])
        pred_h_int = int(pred_hour)
        pred_m_int = int((pred_hour - pred_h_int) * 60.0)
        candidate_dt = start_dt.replace(hour=pred_h_int, minute=pred_m_int, second=0, microsecond=0)
        if candidate_dt <= start_dt:
            candidate_dt += timedelta(days=1)

        # Calculate prediction confidence from circular consistency
        conf_score = max(0.50, min(0.95, 1.0 - (circ_std / 5.0)))

        # -------------------------------------------------------------
        # Strategy A: Immediate Charging
        # -------------------------------------------------------------
        needed_soc_imm = max(0.0, target_soc - start_soc)
        duration_imm_min = (needed_soc_imm / rate_pct_per_hr) * 60.0
        finish_imm_dt = start_dt + timedelta(minutes=duration_imm_min)

        if actual_unplug_dt > finish_imm_dt:
            imm_idle_mins = (actual_unplug_dt - finish_imm_dt).total_seconds() / 60.0
            imm_soc_at_unplug = target_soc
        else:
            imm_idle_mins = 0.0
            actual_charge_mins = (actual_unplug_dt - start_dt).total_seconds() / 60.0
            imm_soc_at_unplug = min(target_soc, start_soc + (actual_charge_mins * rate_pct_per_hr / 60.0))

        # -------------------------------------------------------------
        # Strategy B: Personalized Recommendation Engine
        # -------------------------------------------------------------
        req = RecommendationRequest(
            user_id=user_id,
            current_battery_percent=start_soc,
            target_battery_percent=target_soc,
            plug_time=start_dt,
            charger_type=charger_type,
            prediction_override=candidate_dt,
            confidence_score_override=conf_score,
        )
        rec = engine.generate_recommendation(
            req,
            history_count=int(row["completed_history_count"]),
            circular_std=circ_std,
            is_irregular=(profile == "IRREGULAR"),
        )

        rec_start_dt = rec.recommended_start_time
        rec_finish_dt = rec.estimated_finish_time

        if rec.mode == RecommendationMode.ALREADY_ABOVE_TARGET.value:
            pers_idle_mins = 0.0
            pers_soc_at_unplug = start_soc
        elif actual_unplug_dt <= rec_start_dt:
            # Unplugged before delayed charge began
            pers_idle_mins = 0.0
            pers_soc_at_unplug = start_soc
        elif rec_start_dt < actual_unplug_dt < rec_finish_dt:
            # Unplugged during active charging
            pers_idle_mins = 0.0
            actual_pers_charge_mins = (actual_unplug_dt - rec_start_dt).total_seconds() / 60.0
            pers_soc_at_unplug = min(target_soc, start_soc + (actual_pers_charge_mins * rate_pct_per_hr / 60.0))
        else:
            # Reached target SOC
            pers_idle_mins = (actual_unplug_dt - rec_finish_dt).total_seconds() / 60.0
            pers_soc_at_unplug = target_soc

        sim_records.append({
            "user_id": user_id,
            "profile_type": profile,
            "charger_type": charger_type,
            "start_soc": start_soc,
            "imm_idle_mins": imm_idle_mins,
            "imm_soc_at_unplug": imm_soc_at_unplug,
            "pers_idle_mins": pers_idle_mins,
            "pers_soc_at_unplug": pers_soc_at_unplug,
            "mode": rec.mode,
            "confidence_level": rec.confidence_level,
            "idle_holding_minutes": rec.idle_holding_minutes,
        })

    results_df = pd.DataFrame(sim_records)

    # 7. Aggregate Metrics
    imm_mean_idle = float(results_df["imm_idle_mins"].mean())
    imm_median_idle = float(results_df["imm_idle_mins"].median())
    pers_mean_idle = float(results_df["pers_idle_mins"].mean())
    pers_median_idle = float(results_df["pers_idle_mins"].median())

    idle_reduction_mins = imm_mean_idle - pers_mean_idle
    idle_reduction_pct = (idle_reduction_mins / imm_mean_idle) * 100.0 if imm_mean_idle > 0 else 0.0

    # User readiness: % of sessions where SOC at unplug reached target or >= 95% of target
    imm_readiness_pct = float((results_df["imm_soc_at_unplug"] >= (target_soc * 0.95)).mean() * 100.0)
    pers_readiness_pct = float((results_df["pers_soc_at_unplug"] >= (target_soc * 0.95)).mean() * 100.0)

    # Mode breakdown
    mode_counts = results_df["mode"].value_counts()
    mode_distribution = {m: {"count": int(c), "pct": round(c / n_test * 100.0, 2)} for m, c in mode_counts.items()}

    # Profile-level breakdown
    profile_summary = {}
    for prof, grp in results_df.groupby("profile_type"):
        g_imm = float(grp["imm_idle_mins"].mean())
        g_pers = float(grp["pers_idle_mins"].mean())
        g_red = g_imm - g_pers
        g_red_pct = (g_red / g_imm * 100.0) if g_imm > 0 else 0.0
        g_ready = float((grp["pers_soc_at_unplug"] >= (target_soc * 0.95)).mean() * 100.0)
        profile_summary[prof] = {
            "sessions": len(grp),
            "immediate_idle_mean_min": round(g_imm, 1),
            "personalized_idle_mean_min": round(g_pers, 1),
            "idle_reduction_min": round(g_red, 1),
            "idle_reduction_pct": round(g_red_pct, 1),
            "readiness_pct": round(g_ready, 1),
            "dominant_mode": grp["mode"].mode()[0] if not grp["mode"].empty else "N/A",
        }

    # Print Summary Report
    print("\n" + "=" * 80)
    print("SIMULATION RESULTS: IMMEDIATE VS PERSONALIZED DELAYED CHARGING")
    print("=" * 80)
    print(f"Total Test Sessions:              {n_test:,}")
    print(f"Target State of Charge (SOC):     {target_soc:.0f}%\n")

    print(f"1. HIGH-SOC IDLE WAITING TIME REDUCTION:")
    print(f"   - Strategy A (Immediate Charge):  {imm_mean_idle:6.1f} min ({imm_mean_idle/60.0:.2f} hrs) | Median: {imm_median_idle:5.1f} min")
    print(f"   - Strategy B (Recommendation):    {pers_mean_idle:6.1f} min ({pers_mean_idle/60.0:.2f} hrs) | Median: {pers_median_idle:5.1f} min")
    print(f"   - Mean Idle Time Reduced:         {idle_reduction_mins:6.1f} min ({idle_reduction_mins/60.0:.2f} hrs)")
    print(f"   - RELATIVE REDUCTION:             {idle_reduction_pct:6.2f}%\n")

    print(f"2. BATTERY READINESS AT UNPLUG (>= {target_soc * 0.95:.0f}% SOC):")
    print(f"   - Immediate Charging Readiness:   {imm_readiness_pct:6.2f}%")
    print(f"   - Personalized Schedule Readiness:{pers_readiness_pct:6.2f}%\n")

    print(f"3. RECOMMENDATION ENGINE MODE DISTRIBUTION:")
    for mode_name, data in mode_distribution.items():
        print(f"   - {mode_name:24s}: {data['count']:5d} sessions ({data['pct']:5.1f}%)")

    print(f"\n4. COMPARATIVE PERFORMANCE BY BEHAVIORAL PROFILE:")
    print(f"   {'Profile':18s} | {'Sessions':8s} | {'Imm Idle':8s} | {'Pers Idle':9s} | {'Reduction':9s} | {'Readiness':9s} | {'Dominant Mode':16s}")
    print(f"   {'-'*18}-|-{'-'*8}-|-{'-'*8}-|-{'-'*9}-|-{'-'*9}-|-{'-'*9}-|-{'-'*16}")
    for prof, pdata in profile_summary.items():
        print(f"   {prof:18s} | {pdata['sessions']:8d} | {pdata['immediate_idle_mean_min']:7.1f}m | {pdata['personalized_idle_mean_min']:7.1f}m  | {pdata['idle_reduction_pct']:+7.1f}%  | {pdata['readiness_pct']:7.1f}%  | {pdata['dominant_mode']:16s}")

    # 8. Generate Visualizations (Matplotlib ONLY)
    plot_dir = os.path.join(BASE_DIR, "docs", "recommendation_analysis")
    os.makedirs(plot_dir, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Plot 1: Profile Idle Time Comparison
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    profiles = sorted(profile_summary.keys())
    x = np.arange(len(profiles))
    width = 0.35

    imm_vals = [profile_summary[p]["immediate_idle_mean_min"] for p in profiles]
    pers_vals = [profile_summary[p]["personalized_idle_mean_min"] for p in profiles]

    r1 = ax.bar(x - width/2, imm_vals, width, label="Strategy A (Immediate Charge)", color="#e76f51", alpha=0.9)
    r2 = ax.bar(x + width/2, pers_vals, width, label="Strategy B (Personalized Delay)", color="#2a9d8f", alpha=0.9)

    for i, p in enumerate(profiles):
        red_pct = profile_summary[p]["idle_reduction_pct"]
        ax.annotate(f"-{red_pct:.1f}%", xy=(x[i] + width/2, pers_vals[i]), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8.5, fontweight="bold",
                    color="#1d3557")

    ax.set_title("Early-Completion High-SOC Idle Time by Profile: Immediate vs. Personalized", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile", fontsize=10)
    ax.set_ylabel("Mean High-SOC Idle Time (Minutes)", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("_", "\n") for p in profiles], fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")
    plt.tight_layout()
    p1_path = os.path.join(plot_dir, "idle_time_by_profile.png")
    plt.savefig(p1_path)
    plt.close()

    # Plot 2: Idle Time Distribution Boxplot / CDF
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    ax.hist(results_df["imm_idle_mins"], bins=40, alpha=0.6, color="#e76f51", label=f"Immediate (Mean: {imm_mean_idle:.0f}m)")
    ax.hist(results_df["pers_idle_mins"], bins=40, alpha=0.6, color="#2a9d8f", label=f"Personalized (Mean: {pers_mean_idle:.0f}m)")
    ax.set_title("Distribution of Early-Completion High-SOC Idle Stress (N=1,584)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Minutes Spent Idle at High SOC Before Unplug", fontsize=10)
    ax.set_ylabel("Session Count", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")
    plt.tight_layout()
    p2_path = os.path.join(plot_dir, "idle_distribution.png")
    plt.savefig(p2_path)
    plt.close()

    print(f"\n5. GENERATED VISUALIZATIONS IN: {plot_dir}")
    print(f"   [OK] idle_time_by_profile.png")
    print(f"   [OK] idle_distribution.png")
    print("=" * 80)

    return {
        "n_test": n_test,
        "immediate_mean_idle_mins": round(imm_mean_idle, 2),
        "personalized_mean_idle_mins": round(pers_mean_idle, 2),
        "idle_reduction_mins": round(idle_reduction_mins, 2),
        "idle_reduction_pct": round(idle_reduction_pct, 2),
        "immediate_readiness_pct": round(imm_readiness_pct, 2),
        "personalized_readiness_pct": round(pers_readiness_pct, 2),
        "mode_distribution": mode_distribution,
        "profile_summary": profile_summary,
    }


if __name__ == "__main__":
    run_recommendation_evaluation()

