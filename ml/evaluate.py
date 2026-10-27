"""
Smart Battery AI - Model Evaluation & Visual Error Analysis
===========================================================
Calculates circular time prediction metrics, conducts segmented error analysis,
and generates publication-grade visualizations using matplotlib only.
"""

import os
import sys
from typing import Dict, Any, List

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ml.preprocessing import circular_error_minutes


def calculate_circular_metrics(
    actual_hours: np.ndarray,
    predicted_hours: np.ndarray,
) -> Dict[str, float]:
    """
    Computes rigorous circular time error metrics.
    Primary metric: Circular Mean Absolute Error in minutes.
    """
    errors_minutes = circular_error_minutes(actual_hours, predicted_hours, period=24.0)

    mae_min = float(np.mean(errors_minutes))
    median_min = float(np.median(errors_minutes))
    rmse_min = float(np.sqrt(np.mean(errors_minutes**2)))
    w15_pct = float(np.mean(errors_minutes <= 15.0) * 100.0)
    w30_pct = float(np.mean(errors_minutes <= 30.0) * 100.0)
    w60_pct = float(np.mean(errors_minutes <= 60.0) * 100.0)

    return {
        "mae_minutes": round(mae_min, 2),
        "median_minutes": round(median_min, 2),
        "rmse_minutes": round(rmse_min, 2),
        "within_15_min_pct": round(w15_pct, 2),
        "within_30_min_pct": round(w30_pct, 2),
        "within_60_min_pct": round(w60_pct, 2),
    }


def analyze_errors_by_segments(
    test_df: pd.DataFrame,
    actual_hours: np.ndarray,
    predicted_hours: np.ndarray,
) -> Dict[str, Any]:
    """
    Conducts segmented error analysis across behavioral profiles, calendar splits, and users.
    NOTE: profile_type and user_id are evaluation metadata ONLY, never ML inputs.
    """
    errors_min = circular_error_minutes(actual_hours, predicted_hours, period=24.0)
    analysis_df = test_df.copy()
    analysis_df["error_minutes"] = errors_min
    analysis_df["actual_hour"] = actual_hours
    analysis_df["predicted_hour"] = predicted_hours

    # 1. Error by Profile
    profile_mae = {}
    if "profile_type" in analysis_df.columns:
        prof_grp = analysis_df.groupby("profile_type")["error_minutes"].agg(["mean", "median", "count"])
        for prof, row in prof_grp.iterrows():
            profile_mae[prof] = {
                "mae_minutes": round(float(row["mean"]), 2),
                "median_minutes": round(float(row["median"]), 2),
                "sessions": int(row["count"]),
            }

    # 2. Error by Weekday vs. Weekend
    weekend_mae = {}
    if "is_weekend" in analysis_df.columns:
        we_grp = analysis_df.groupby("is_weekend")["error_minutes"].mean()
        weekend_mae["weekday_mae_minutes"] = round(float(we_grp.get(0, 0.0)), 2)
        weekend_mae["weekend_mae_minutes"] = round(float(we_grp.get(1, 0.0)), 2)

    # 3. User-Level Errors (Top 5 highest and lowest)
    user_grp = analysis_df.groupby("user_id")["error_minutes"].agg(["mean", "count"]).reset_index()
    user_grp.columns = ["user_id", "user_mae", "session_count"]
    user_grp = user_grp.sort_values(by="user_mae")

    lowest_users = user_grp.head(5).to_dict(orient="records")
    highest_users = user_grp.tail(5).iloc[::-1].to_dict(orient="records")

    return {
        "profile_mae": profile_mae,
        "calendar_mae": weekend_mae,
        "lowest_error_users": lowest_users,
        "highest_error_users": highest_users,
        "per_user_errors": user_grp,
        "analysis_df": analysis_df,
    }


# ==============================================================================
# VISUALIZATIONS (Matplotlib ONLY)
# ==============================================================================

def plot_model_comparison(comparison_df: pd.DataFrame, out_dir: str) -> str:
    """01: Bar chart comparing models across key metrics."""
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    models = comparison_df["Model"].tolist()
    x = np.arange(len(models))
    width = 0.25

    mae_vals = comparison_df["MAE (min)"].values
    med_vals = comparison_df["Median Error (min)"].values
    rmse_vals = comparison_df["RMSE (min)"].values

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

    ax.set_title("Baseline Machine Learning Model Comparison (Circular Time Errors)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Predictor Model Architecture", fontsize=11)
    ax.set_ylabel("Error in Minutes (Lower is Better)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "model_comparison.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_actual_vs_predicted(actual: np.ndarray, predicted: np.ndarray, out_dir: str) -> str:
    """02: Scatter plot of Actual vs. Predicted Unplug Hour with ideal identity line."""
    fig, ax = plt.subplots(figsize=(8.5, 7), dpi=300)

    # Subsample 1200 points for clear visual clarity
    indices = np.random.RandomState(42).choice(len(actual), size=min(1200, len(actual)), replace=False)
    act_sub = actual[indices]
    pred_sub = predicted[indices]

    ax.scatter(act_sub, pred_sub, alpha=0.35, color="#1d3557", edgecolors="none", s=22, label="Test Sessions (N=1200)")

    # Ideal identity line
    ax.plot([0, 24], [0, 24], color="#e63946", linestyle="--", linewidth=2, label="Ideal Prediction (y = x)")

    ax.set_title("Actual vs. Predicted Unplug Hour (Best Baseline Model)", fontsize=13, fontweight="bold", pad=12)
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
    path = os.path.join(out_dir, "actual_vs_predicted_unplug.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_prediction_error_distribution(errors_min: np.ndarray, out_dir: str) -> str:
    """03: Histogram and cumulative CDF of prediction error in minutes."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Histogram
    bins = np.linspace(0, 360, 49)  # up to 6 hours
    ax1.hist(errors_min, bins=bins, color="#028090", edgecolor="#004e64", alpha=0.85, density=True)
    mean_err = np.mean(errors_min)
    median_err = np.median(errors_min)

    ax1.axvline(mean_err, color="#e63946", linestyle="--", linewidth=1.5, label=f"Mean Error: {mean_err:.1f}m")
    ax1.axvline(median_err, color="#ffb703", linestyle="-.", linewidth=1.5, label=f"Median Error: {median_err:.1f}m")
    ax1.axvline(30.0, color="#2a9d8f", linestyle=":", linewidth=1.5, label="±30 min target")

    ax1.set_title("Distribution of Circular Error (Minutes)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Prediction Error (Minutes)", fontsize=10)
    ax1.set_ylabel("Probability Density", fontsize=10)
    ax1.set_xlim(0, 360)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right", fontsize=9)

    # Cumulative CDF
    sorted_err = np.sort(errors_min)
    cdf = np.arange(1, len(sorted_err) + 1) / len(sorted_err) * 100.0

    ax2.plot(sorted_err, cdf, color="#1d3557", linewidth=2)
    ax2.axvline(15.0, color="#2a9d8f", linestyle="--", alpha=0.7)
    ax2.axvline(30.0, color="#f4a261", linestyle="--", alpha=0.7)
    ax2.axvline(60.0, color="#e76f51", linestyle="--", alpha=0.7)

    w15 = np.mean(errors_min <= 15.0) * 100.0
    w30 = np.mean(errors_min <= 30.0) * 100.0
    w60 = np.mean(errors_min <= 60.0) * 100.0

    ax2.text(16, 20, f"Within 15m:\n{w15:.1f}%", fontsize=9, color="#2a9d8f", fontweight="bold")
    ax2.text(32, 45, f"Within 30m:\n{w30:.1f}%", fontsize=9, color="#f4a261", fontweight="bold")
    ax2.text(62, 70, f"Within 60m:\n{w60:.1f}%", fontsize=9, color="#e76f51", fontweight="bold")

    ax2.set_title("Cumulative Error Accuracy Curve", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Error Threshold (Minutes)", fontsize=10)
    ax2.set_ylabel("Cumulative Percentage (%)", fontsize=10)
    ax2.set_xlim(0, 240)
    ax2.set_ylim(0, 105)
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    path = os.path.join(out_dir, "prediction_error_distribution.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_error_by_user(user_df: pd.DataFrame, out_dir: str) -> str:
    """04: User-level prediction error distribution across the 100 users."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    user_mae_sorted = user_df.sort_values(by="user_mae").reset_index(drop=True)
    x = np.arange(len(user_mae_sorted))

    ax.bar(x, user_mae_sorted["user_mae"], color="#457b9d", width=0.8, edgecolor="#1d3557", alpha=0.8)

    mean_user_mae = user_mae_sorted["user_mae"].mean()
    ax.axhline(mean_user_mae, color="#e63946", linestyle="--", linewidth=1.5, label=f"Average User MAE: {mean_user_mae:.1f}m")

    ax.set_title("Mean Absolute Error per User (N = 100 Users)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Users Sorted by Prediction Accuracy (Best to Worst)", fontsize=11)
    ax.set_ylabel("Mean Absolute Error (Minutes)", fontsize=11)
    ax.set_xlim(-1, 101)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "error_by_user.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_error_by_profile(analysis_df: pd.DataFrame, out_dir: str) -> str:
    """05: Boxplot comparing circular error in minutes grouped by behavioral profile."""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    profiles = sorted(analysis_df["profile_type"].unique())
    data = [analysis_df[analysis_df["profile_type"] == p]["error_minutes"].values for p in profiles]

    colors = ["#457b9d", "#e63946", "#f4a261", "#2a9d8f", "#e76f51", "#264653"]
    box = ax.boxplot(
        data,
        patch_artist=True,
        tick_labels=[p.replace("_", "\n") for p in profiles],
        medianprops=dict(color="#1d3557", linewidth=2),
        flierprops=dict(marker="o", markerfacecolor="#219ebc", markersize=3, alpha=0.4),
    )

    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    global_mean = analysis_df["error_minutes"].mean()
    ax.axhline(global_mean, color="#e63946", linestyle="--", linewidth=1.5, label=f"Global Test MAE: {global_mean:.1f} min")

    ax.set_title("Prediction Error by User Profile (Evaluating Model Robustness)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile Type (Post-Hoc Evaluation Metadata)", fontsize=11)
    ax.set_ylabel("Prediction Error (Minutes)", fontsize=11)
    ax.set_ylim(0, 360)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "error_by_profile.png")
    plt.savefig(path)
    plt.close()
    return path
