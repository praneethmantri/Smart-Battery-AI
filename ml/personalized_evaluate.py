"""
Smart Battery AI - Personalized Model Evaluation & Visual Analysis
==================================================================
Calculates comparative performance metrics between global and personalized models,
evaluates cold-start progression, and generates 6 publication-grade matplotlib figures.
"""

import os
import sys
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml.preprocessing import circular_error_minutes
from ml.evaluate import calculate_circular_metrics


def evaluate_comparative_performance(
    test_df: pd.DataFrame,
    y_true: np.ndarray,
    predictions_dict: Dict[str, np.ndarray],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Evaluates multiple candidate models on the chronological test set.
    Computes comparative metrics, profile breakdowns, user improvements,
    and history-count error progressions.
    """
    results = []
    error_dict = {}

    for name, preds in predictions_dict.items():
        metrics = calculate_circular_metrics(y_true, preds)
        metrics["Model"] = name
        results.append(metrics)
        error_dict[name] = circular_error_minutes(y_true, preds, period=24.0)

    comp_df = pd.DataFrame(results)
    comp_df = comp_df[["Model", "mae_minutes", "median_minutes", "rmse_minutes", "within_15_min_pct", "within_30_min_pct", "within_60_min_pct"]]
    comp_df.columns = ["Model", "MAE (min)", "Median Error (min)", "RMSE (min)", "Within 15 min (%)", "Within 30 min (%)", "Within 60 min (%)"]

    # Profile-level breakdown (comparing Global vs Best Personalized)
    analysis_df = test_df.copy()
    analysis_df["actual_hour"] = y_true
    for name, errs in error_dict.items():
        analysis_df[f"err_{name}"] = errs

    return comp_df, {
        "analysis_df": analysis_df,
        "error_dict": error_dict,
    }


def analyze_user_and_profile_improvements(
    analysis_df: pd.DataFrame,
    global_col: str,
    personalized_col: str,
) -> Dict[str, Any]:
    """
    Computes detailed per-user and per-profile comparative statistics.
    """
    # 1. Profile Comparison
    prof_stats = {}
    if "profile_type" in analysis_df.columns:
        for prof, grp in analysis_df.groupby("profile_type"):
            g_m = float(grp[global_col].mean())
            p_m = float(grp[personalized_col].mean())
            diff = g_m - p_m
            imp_pct = (diff / g_m * 100.0) if g_m > 0 else 0.0
            prof_stats[prof] = {
                "global_mae": round(g_m, 2),
                "personalized_mae": round(p_m, 2),
                "mae_reduction": round(diff, 2),
                "improvement_pct": round(imp_pct, 2),
                "sessions": len(grp),
            }

    # 2. User-Level Comparison
    user_comp = analysis_df.groupby("user_id")[[global_col, personalized_col]].mean().reset_index()
    user_comp["improvement_minutes"] = user_comp[global_col] - user_comp[personalized_col]
    user_comp["improvement_pct"] = (user_comp["improvement_minutes"] / user_comp[global_col]) * 100.0

    n_users = len(user_comp)
    improved_count = int((user_comp["improvement_minutes"] > 0).sum())
    worsened_count = int((user_comp["improvement_minutes"] < 0).sum())
    unchanged_count = n_users - improved_count - worsened_count

    user_summary = {
        "total_users": n_users,
        "improved_count": improved_count,
        "improved_pct": round(improved_count / n_users * 100.0, 2),
        "worsened_count": worsened_count,
        "worsened_pct": round(worsened_count / n_users * 100.0, 2),
        "unchanged_count": unchanged_count,
        "median_user_improvement_min": round(float(user_comp["improvement_minutes"].median()), 2),
        "mean_user_improvement_min": round(float(user_comp["improvement_minutes"].mean()), 2),
        "max_improvement_min": round(float(user_comp["improvement_minutes"].max()), 2),
        "max_improvement_user": int(user_comp.loc[user_comp["improvement_minutes"].idxmax(), "user_id"]),
        "max_degradation_min": round(float(user_comp["improvement_minutes"].min()), 2),
        "max_degradation_user": int(user_comp.loc[user_comp["improvement_minutes"].idxmin(), "user_id"]),
        "user_table": user_comp,
    }

    # 3. Minimum History / Cold-Start Buckets
    history_buckets = {}
    bins = [-1, 2, 6, 14, 1000]
    labels = ["0-2 sessions", "3-6 sessions", "7-14 sessions", "15+ sessions"]
    analysis_df["hist_bucket"] = pd.cut(analysis_df["completed_history_count"], bins=bins, labels=labels)

    for b in labels:
        sub = analysis_df[analysis_df["hist_bucket"] == b]
        if len(sub) > 0:
            g_b = float(sub[global_col].mean())
            p_b = float(sub[personalized_col].mean())
            history_buckets[b] = {
                "count": len(sub),
                "global_mae": round(g_b, 2),
                "personalized_mae": round(p_b, 2),
                "improvement_min": round(g_b - p_b, 2),
                "improvement_pct": round((g_b - p_b) / g_b * 100.0, 2) if g_b > 0 else 0.0,
            }

    return {
        "profile_stats": prof_stats,
        "user_summary": user_summary,
        "history_buckets": history_buckets,
    }


# ==============================================================================
# VISUALIZATIONS (Matplotlib ONLY)
# ==============================================================================

def plot_01_global_vs_personalized_mae(comp_df: pd.DataFrame, out_dir: str) -> str:
    """01: Grouped bar chart comparing Global Baseline vs Personalized architectures."""
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)

    models = comp_df["Model"].tolist()
    x = np.arange(len(models))
    width = 0.25

    mae_vals = comp_df["MAE (min)"].values
    med_vals = comp_df["Median Error (min)"].values
    rmse_vals = comp_df["RMSE (min)"].values

    r1 = ax.bar(x - width, mae_vals, width, label="MAE (min)", color="#2b5c8f", alpha=0.9)
    r2 = ax.bar(x, med_vals, width, label="Median Error (min)", color="#028090", alpha=0.9)
    r3 = ax.bar(x + width, rmse_vals, width, label="RMSE (min)", color="#e76f51", alpha=0.9)

    for rect in r1:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}m", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for rect in r2:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}m", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in r3:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}m", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8)

    ax.set_title("Global Baseline vs. Personalized Models (Unseen Test Set)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Model Architecture", fontsize=11)
    ax.set_ylabel("Error in Minutes (Lower is Better)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace(" ", "\n") for m in models], fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "global_vs_personalized_mae.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_02_improvement_by_profile(profile_stats: Dict[str, Any], out_dir: str) -> str:
    """02: Bar chart comparing Global vs Personalized MAE across behavioral profiles."""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    profiles = sorted(profile_stats.keys())
    x = np.arange(len(profiles))
    width = 0.35

    g_maes = [profile_stats[p]["global_mae"] for p in profiles]
    p_maes = [profile_stats[p]["personalized_mae"] for p in profiles]

    r1 = ax.bar(x - width/2, g_maes, width, label="Global Baseline MAE", color="#457b9d", alpha=0.85)
    r2 = ax.bar(x + width/2, p_maes, width, label="Personalized Model MAE", color="#2a9d8f", alpha=0.85)

    for i, p in enumerate(profiles):
        red = profile_stats[p]["mae_reduction"]
        pct = profile_stats[p]["improvement_pct"]
        ax.annotate(f"{pct:+.1f}%", xy=(x[i] + width/2, p_maes[i]), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold",
                    color="#1d3557" if pct >= 0 else "#d90429")

    ax.set_title("Prediction Error by User Profile: Global vs. Personalized", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile Type", fontsize=11)
    ax.set_ylabel("Mean Absolute Error (Minutes)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("_", "\n") for p in profiles], fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "improvement_by_profile.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_03_error_vs_history_count(analysis_df: pd.DataFrame, error_col: str, out_dir: str) -> str:
    """03: Error vs history count showing how prediction error diminishes with more sessions."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    # Bin history count by 5s up to 60
    binned = analysis_df.copy()
    binned["hist_bin"] = (binned["completed_history_count"] // 5) * 5
    grouped = binned.groupby("hist_bin")[error_col].agg(["mean", "std", "count"]).reset_index()
    grouped = grouped[grouped["count"] >= 10]

    ax.plot(grouped["hist_bin"], grouped["mean"], marker="o", color="#1d3557", linewidth=2.2, label="Mean Error (min)")
    ax.fill_between(
        grouped["hist_bin"],
        grouped["mean"] - 0.25 * grouped["std"],
        grouped["mean"] + 0.25 * grouped["std"],
        color="#457b9d",
        alpha=0.25,
        label="±0.25 Std Dev Band",
    )

    ax.axvline(7, color="#e76f51", linestyle="--", linewidth=1.5, label="Cold-Start Plateau (~7 sessions)")

    ax.set_title("Prediction Error vs. Available Historical Sessions", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Number of Prior Completed Charging Sessions", fontsize=11)
    ax.set_ylabel("Mean Absolute Error (Minutes)", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "error_vs_history_count.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_04_per_user_improvement(user_comp: pd.DataFrame, out_dir: str) -> str:
    """04: Waterfall / Sorted bar plot of per-user MAE improvement."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    sorted_df = user_comp.sort_values(by="improvement_minutes", ascending=False).reset_index(drop=True)
    x = np.arange(len(sorted_df))
    colors = ["#2a9d8f" if v >= 0 else "#e76f51" for v in sorted_df["improvement_minutes"]]

    ax.bar(x, sorted_df["improvement_minutes"], color=colors, width=0.85, alpha=0.85)
    ax.axhline(0, color="black", linewidth=1.0)

    med_imp = sorted_df["improvement_minutes"].median()
    ax.axhline(med_imp, color="#1d3557", linestyle="--", linewidth=1.5, label=f"Median Improvement: {med_imp:+.1f} min")

    improved_pct = (sorted_df["improvement_minutes"] > 0).mean() * 100.0
    ax.text(10, sorted_df["improvement_minutes"].max() * 0.8,
            f"{improved_pct:.0f}% of Users Improved\nwith Personalization",
            fontsize=10, fontweight="bold", color="#2a9d8f",
            bbox=dict(boxstyle="round,pad=0.3", fc="#eef9f6", ec="#2a9d8f"))

    ax.set_title("Per-User Error Improvement (Global MAE − Personalized MAE)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Simulated Users Sorted by Improvement (N = 100)", fontsize=11)
    ax.set_ylabel("Improvement in Minutes (Positive = Better)", fontsize=11)
    ax.set_xlim(-1, 101)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "per_user_improvement.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_05_actual_vs_personalized(actual: np.ndarray, predicted: np.ndarray, out_dir: str) -> str:
    """05: Scatter plot of Actual vs Predicted for Best Personalized Model."""
    fig, ax = plt.subplots(figsize=(8.5, 7), dpi=300)

    indices = np.random.RandomState(42).choice(len(actual), size=min(1200, len(actual)), replace=False)
    ax.scatter(actual[indices], predicted[indices], alpha=0.35, color="#028090", edgecolors="none", s=22, label="Test Sessions (N=1200)")

    ax.plot([0, 24], [0, 24], color="#e63946", linestyle="--", linewidth=2, label="Ideal Prediction (y = x)")

    ax.set_title("Actual vs. Predicted Unplug Hour (Personalized Model)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Actual Unplug Hour (0.00 - 24.00)", fontsize=11)
    ax.set_ylabel("Predicted Unplug Hour (0.00 - 24.00)", fontsize=11)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_yticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "actual_vs_personalized_prediction.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_06_cold_start_performance(history_buckets: Dict[str, Any], out_dir: str) -> str:
    """06: Error comparison across cold-start history tiers."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    tiers = list(history_buckets.keys())
    x = np.arange(len(tiers))
    width = 0.35

    g_vals = [history_buckets[t]["global_mae"] for t in tiers]
    p_vals = [history_buckets[t]["personalized_mae"] for t in tiers]

    ax.bar(x - width/2, g_vals, width, label="Global Model MAE", color="#457b9d", alpha=0.85)
    ax.bar(x + width/2, p_vals, width, label="Personalized Model MAE", color="#2a9d8f", alpha=0.85)

    for i, t in enumerate(tiers):
        cnt = history_buckets[t]["count"]
        ax.text(x[i], max(g_vals[i], p_vals[i]) + 2.0, f"N={cnt}", ha="center", fontsize=8, color="#555")

    ax.set_title("Cold-Start to Warm History Performance Progression", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Historical Session Depth Available at Inference", fontsize=11)
    ax.set_ylabel("Mean Absolute Error (Minutes)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(tiers, fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "cold_start_performance.png")
    plt.savefig(path)
    plt.close()
    return path
