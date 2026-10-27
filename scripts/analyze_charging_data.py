"""
Smart Battery AI - Exploratory Data Analysis (EDA) & Feature / Data-Leakage Analysis
==================================================================================
Analyzes charging behavior patterns, circular time distributions, user predictability,
charger characteristics, and strictly classifies features to prevent data leakage in
predicting expected unplug time.

Generates 11 publication-grade visualizations using matplotlib only (strictly no seaborn).
"""

import os
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for automated CLI execution
import matplotlib.pyplot as plt


# Project directory structure
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
ANALYSIS_DIR = os.path.join(DOCS_DIR, "analysis")

CHARGING_CSV = os.path.join(DATA_DIR, "charging_behavior.csv")
USERS_CSV = os.path.join(DATA_DIR, "users.csv")


def ensure_output_dir(path: str = ANALYSIS_DIR) -> str:
    """Ensure destination directory exists."""
    os.makedirs(path, exist_ok=True)
    return path


def circular_mean_std(hours: pd.Series, period: float = 24.0):
    """
    Computes directional circular mean and circular standard deviation for periodic hours.
    Crucial for capturing 23:59 -> 00:01 continuity without artificial 24-hour linear jump.
    """
    angles = hours * (2.0 * np.pi / period)
    sin_sum = np.sum(np.sin(angles))
    cos_sum = np.sum(np.cos(angles))
    mean_angle = np.arctan2(sin_sum, cos_sum)
    if mean_angle < 0:
        mean_angle += 2.0 * np.pi
    circ_mean = mean_angle * (period / (2.0 * np.pi))

    n = len(hours)
    R = np.sqrt(sin_sum**2 + cos_sum**2) / max(n, 1)
    # Standard directional circular standard deviation in hours
    circ_std = np.sqrt(max(0.0, -2.0 * np.log(max(R, 1e-10)))) * (period / (2.0 * np.pi))
    return circ_mean, circ_std


def load_datasets():
    """Loads and validates input datasets."""
    if not os.path.exists(CHARGING_CSV):
        raise FileNotFoundError(f"Charging behavior dataset missing: {CHARGING_CSV}")
    if not os.path.exists(USERS_CSV):
        raise FileNotFoundError(f"Users dataset missing: {USERS_CSV}")

    df = pd.read_csv(CHARGING_CSV)
    users = pd.read_csv(USERS_CSV)

    # Convert timestamps
    df["charging_start_time"] = pd.to_datetime(df["charging_start_time"])
    df["unplug_time"] = pd.to_datetime(df["unplug_time"])
    df["date"] = pd.to_datetime(df["date"])

    return df, users


# ==============================================================================
# VISUALIZATION FUNCTIONS (Matplotlib ONLY)
# ==============================================================================

def plot_01_charging_start_distribution(df: pd.DataFrame, out_dir: str) -> str:
    """01: Charging start hour distribution across the 24-hour diurnal cycle."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    bins = np.linspace(0, 24, 49)  # 30-minute intervals

    n, bins_out, patches = ax.hist(
        df["charging_start_hour"],
        bins=bins,
        color="#2b5c8f",
        edgecolor="#16324f",
        alpha=0.85,
        density=True,
    )

    # Annotate primary daytime and overnight peaks
    ax.axvline(13.0, color="#d9534f", linestyle="--", linewidth=1.5, label="Midday Top-up Cluster (~13:00)")
    ax.axvline(22.5, color="#2a9d8f", linestyle="--", linewidth=1.5, label="Evening Overnight Cluster (~22:30)")

    ax.set_title("Distribution of Charging Session Start Hours (N = 7,735)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Hour of Day (0.00 - 24.00)", fontsize=11)
    ax.set_ylabel("Probability Density", fontsize=11)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_xlim(0, 24)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "01_charging_start_distribution.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_02_unplug_time_distribution(df: pd.DataFrame, out_dir: str) -> str:
    """02: Unplug hour distribution (Primary ML Target)."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    bins = np.linspace(0, 24, 49)

    n, bins_out, patches = ax.hist(
        df["unplug_hour"],
        bins=bins,
        color="#028090",
        edgecolor="#004e64",
        alpha=0.85,
        density=True,
    )

    # Annotate primary peaks
    ax.axvline(7.0, color="#e76f51", linestyle="--", linewidth=1.5, label="Morning Wakeup Peak (~07:00)")
    ax.axvline(14.0, color="#f4a261", linestyle="--", linewidth=1.5, label="Post-Top-up Unplug Peak (~14:00)")

    ax.set_title("Distribution of Unplug Hours (Primary Target Variable)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Hour of Day (0.00 - 24.00)", fontsize=11)
    ax.set_ylabel("Probability Density", fontsize=11)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_xlim(0, 24)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "02_unplug_time_distribution.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_03_unplug_by_profile(df: pd.DataFrame, out_dir: str) -> str:
    """03: Unplug hour comparison across the 6 behavioral profiles."""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    profiles = sorted(df["profile_type"].unique())
    data = [df[df["profile_type"] == p]["unplug_hour"].values for p in profiles]

    box = ax.boxplot(
        data,
        patch_artist=True,
        tick_labels=[p.replace("_", "\n") for p in profiles],
        medianprops=dict(color="#d90429", linewidth=2),
        boxprops=dict(facecolor="#8ecae6", edgecolor="#023047", alpha=0.8),
        whiskerprops=dict(color="#023047", linewidth=1.2),
        capprops=dict(color="#023047", linewidth=1.2),
        flierprops=dict(marker="o", markerfacecolor="#219ebc", markersize=3, alpha=0.4),
    )

    ax.set_title("Unplug Hour Distribution by User Behavioral Profile", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile Type", fontsize=11)
    ax.set_ylabel("Unplug Hour (0.00 - 24.00)", fontsize=11)
    ax.set_yticks(range(0, 25, 2))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    path = os.path.join(out_dir, "03_unplug_by_profile.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_04_start_soc_distribution(df: pd.DataFrame, out_dir: str) -> str:
    """04: Starting battery State-of-Charge (%) distribution."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    bins = np.linspace(0, 100, 41)
    ax.hist(
        df["start_battery_percent"],
        bins=bins,
        color="#3a86ff",
        edgecolor="#1d3557",
        alpha=0.85,
        density=True,
    )

    mean_soc = df["start_battery_percent"].mean()
    median_soc = df["start_battery_percent"].median()
    ax.axvline(mean_soc, color="#d90429", linestyle="--", linewidth=1.5, label=f"Mean SoC: {mean_soc:.1f}%")
    ax.axvline(median_soc, color="#ffb703", linestyle="-.", linewidth=1.5, label=f"Median SoC: {median_soc:.1f}%")

    ax.set_title("Distribution of Battery State-of-Charge (SoC) at Plug-in", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Start Battery Percentage (%)", fontsize=11)
    ax.set_ylabel("Probability Density", fontsize=11)
    ax.set_xlim(0, 100)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "04_start_soc_distribution.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_05_screen_usage_by_profile(df: pd.DataFrame, out_dir: str) -> str:
    """05: Screen usage comparison across profiles."""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    profiles = sorted(df["profile_type"].unique())
    data = [df[df["profile_type"] == p]["screen_usage_minutes"].values for p in profiles]

    colors = ["#457b9d", "#e63946", "#f4a261", "#2a9d8f", "#e76f51", "#264653"]
    box = ax.boxplot(
        data,
        patch_artist=True,
        tick_labels=[p.replace("_", "\n") for p in profiles],
        medianprops=dict(color="#1d3557", linewidth=2),
    )

    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    global_mean = df["screen_usage_minutes"].mean()
    ax.axhline(global_mean, color="#e63946", linestyle="--", linewidth=1.5, label=f"Global Mean: {global_mean:.1f} mins")

    ax.set_title("Daily Screen Usage (Minutes) Grouped by User Profile", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile Type", fontsize=11)
    ax.set_ylabel("Screen Usage (Minutes / Day)", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "05_screen_usage_by_profile.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_06_weekday_vs_weekend_unplug(df: pd.DataFrame, out_dir: str) -> str:
    """06: Weekday vs Weekend unplug hour comparison highlighting WEEKEND_SHIFTER."""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    profiles = sorted(df["profile_type"].unique())
    weekday_means = [df[(df["profile_type"] == p) & (df["is_weekend"] == 0)]["unplug_hour"].mean() for p in profiles]
    weekend_means = [df[(df["profile_type"] == p) & (df["is_weekend"] == 1)]["unplug_hour"].mean() for p in profiles]

    x = np.arange(len(profiles))
    width = 0.35

    rects1 = ax.bar(x - width/2, weekday_means, width, label="Weekday (Mon-Fri)", color="#1d3557", alpha=0.85)
    rects2 = ax.bar(x + width/2, weekend_means, width, label="Weekend (Sat-Sun)", color="#e76f51", alpha=0.85)

    # Add text labels on bars
    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.2f}h", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.2f}h", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax.set_title("Mean Unplug Hour: Weekday vs. Weekend Across Profiles", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Behavioral Profile Type", fontsize=11)
    ax.set_ylabel("Mean Unplug Hour (0.00 - 24.00)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("_", "\n") for p in profiles], fontsize=9)
    ax.set_ylim(0, 14)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#ccc")

    # Callout annotation for Weekend Shifter
    ws_idx = profiles.index("WEEKEND_SHIFTER")
    diff = weekend_means[ws_idx] - weekday_means[ws_idx]
    ax.annotate(
        f"+{diff:.2f} hrs Weekend Shift!",
        xy=(x[ws_idx] + width/2, weekend_means[ws_idx]),
        xytext=(x[ws_idx] + 0.3, weekend_means[ws_idx] + 1.8),
        arrowprops=dict(facecolor="black", arrowstyle="->", lw=1.2),
        fontweight="bold", color="#d90429", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="#ffeedd", ec="#e76f51", lw=1)
    )

    plt.tight_layout()
    path = os.path.join(out_dir, "06_weekday_vs_weekend_unplug.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_07_temperature_by_charger(df: pd.DataFrame, out_dir: str) -> str:
    """07: Average battery temperature by charger type."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    charger_order = ["slow", "standard", "fast"]
    data = [df[df["charger_type"] == c]["average_temperature"].values for c in charger_order]

    colors = ["#2a9d8f", "#457b9d", "#e76f51"]
    box = ax.boxplot(
        data,
        patch_artist=True,
        tick_labels=["Slow Charger\n(~5W-10W)", "Standard Charger\n(~15W-20W)", "Fast Charger\n(~30W-65W+)"],
        medianprops=dict(color="#1d3557", linewidth=2),
    )

    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.set_title("Battery Temperature Distribution Across Charger Types", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Charger Hardware Type", fontsize=11)
    ax.set_ylabel("Average Session Temperature (°C)", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")

    # Add means annotations
    for i, c in enumerate(charger_order):
        m = df[df["charger_type"] == c]["average_temperature"].mean()
        ax.text(i + 1, 38, f"Mean: {m:.1f}°C", ha="center", fontsize=9, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#999"))

    plt.tight_layout()
    path = os.path.join(out_dir, "07_temperature_by_charger.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_08_sessions_per_user(df: pd.DataFrame, out_dir: str) -> str:
    """08: Distribution of total charging sessions per user over the 60-day observation window."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

    counts = df.groupby("user_id")["session_id"].count()

    ax.hist(counts, bins=25, color="#6a4c93", edgecolor="#392b58", alpha=0.85)

    mean_s = counts.mean()
    median_s = counts.median()
    ax.axvline(mean_s, color="#d90429", linestyle="--", linewidth=1.5, label=f"Mean: {mean_s:.1f} sessions")
    ax.axvline(median_s, color="#ffca3a", linestyle="-.", linewidth=1.5, label=f"Median: {median_s:.0f} sessions")

    ax.set_title("Distribution of Charging Sessions per User (60-Day Period)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Total Sessions Recorded", fontsize=11)
    ax.set_ylabel("User Count", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "08_sessions_per_user.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_09_start_soc_vs_screen_usage(df: pd.DataFrame, out_dir: str) -> str:
    """09: Starting Battery SoC vs Daily Screen Usage (with linear regression line)."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    sample_df = df.sample(n=min(1500, len(df)), random_state=42)

    ax.scatter(
        sample_df["screen_usage_minutes"],
        sample_df["start_battery_percent"],
        alpha=0.35,
        color="#1d3557",
        edgecolors="none",
        s=25,
        label="Charging Sessions (Sampled N=1500)",
    )

    z = np.polyfit(df["screen_usage_minutes"], df["start_battery_percent"], 1)
    p = np.poly1d(z)
    x_vals = np.linspace(df["screen_usage_minutes"].min(), df["screen_usage_minutes"].max(), 100)
    corr = df["screen_usage_minutes"].corr(df["start_battery_percent"])
    ax.plot(x_vals, p(x_vals), color="#e63946", linewidth=2.5,
            label=f"Trendline (r = {corr:.2f}, slope = {z[0]:.3f})")

    ax.set_title("Plug-in State of Charge (SoC) vs. Daily Screen Usage", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Screen Usage (Minutes / Day)", fontsize=11)
    ax.set_ylabel("Start Battery Percentage (%)", fontsize=11)
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "09_start_soc_vs_screen_usage.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_10_user_unplug_variability(df: pd.DataFrame, out_dir: str) -> str:
    """10: User unplug variability (circular standard deviation per user) showing predictability tiers."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    user_stds = []
    for uid, grp in df.groupby("user_id"):
        overnight = grp[(grp["charging_start_hour"] >= 20) | (grp["charging_start_hour"] <= 4)]
        if len(overnight) >= 5:
            _, c_std = circular_mean_std(overnight["unplug_hour"])
        else:
            _, c_std = circular_mean_std(grp["unplug_hour"])
        user_stds.append(c_std)

    user_stds = np.array(user_stds)

    bins = np.linspace(0, 4.0, 33)
    n, bins_out, patches = ax.hist(user_stds, bins=bins, color="#457b9d", edgecolor="#1d3557", alpha=0.85)

    ax.axvline(0.75, color="#2a9d8f", linestyle="--", linewidth=2, label="High Predictability Threshold (<0.75h / 45m)")
    ax.axvline(1.50, color="#e76f51", linestyle="--", linewidth=2, label="Moderate Predictability (0.75h - 1.50h)")

    ax.axvspan(0, 0.75, color="#2a9d8f", alpha=0.12)
    ax.axvspan(0.75, 1.5, color="#e9c46a", alpha=0.12)
    ax.axvspan(1.5, 4.0, color="#e76f51", alpha=0.12)

    ax.text(0.35, max(n)*0.85, "High\nRoutine", ha="center", fontsize=10, fontweight="bold", color="#1d3557")
    ax.text(1.12, max(n)*0.85, "Moderate\nRoutine", ha="center", fontsize=10, fontweight="bold", color="#1d3557")
    ax.text(2.6, max(n)*0.85, "Irregular /\nHigh Variance", ha="center", fontsize=10, fontweight="bold", color="#1d3557")

    ax.set_title("User-Level Unplug Time Standard Deviation (Routine Predictability)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Circular Standard Deviation of Unplug Time (Hours)", fontsize=11)
    ax.set_ylabel("Number of Users (N=100)", fontsize=11)
    ax.set_xlim(0, 4.0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ccc")

    plt.tight_layout()
    path = os.path.join(out_dir, "10_user_unplug_variability.png")
    plt.savefig(path)
    plt.close()
    return path


def plot_11_feature_correlation_matrix(df: pd.DataFrame, out_dir: str) -> str:
    """11: Correlation matrix highlighting SAFE features vs POST-EVENT LEAKAGE features."""
    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=300)

    cols = [
        "charging_start_hour",
        "start_battery_percent",
        "weekday",
        "is_weekend",
        "previous_day_usage_minutes",
        "unplug_hour",               # Target
        "end_battery_percent",       # LEAKAGE
        "charging_duration_minutes", # LEAKAGE
        "average_temperature",      # LEAKAGE (session-wide average)
        "screen_usage_minutes"       # LEAKAGE (end of day total)
    ]
    labels = [
        "start_hour (SAFE)",
        "start_soc (SAFE)",
        "weekday (SAFE)",
        "is_weekend (SAFE)",
        "prev_day_usage (SAFE)",
        "unplug_hour [TARGET]",
        "end_soc [LEAKAGE]",
        "duration_mins [LEAKAGE]",
        "avg_temp [LEAKAGE]",
        "screen_usage [LEAKAGE]"
    ]

    corr = df[cols].corr().values
    n = len(cols)

    im = ax.imshow(corr, cmap="coolwarm", vmin=-1.0, vmax=1.0)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Pearson Correlation Coefficient", rotation=270, labelpad=15, fontsize=10)

    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)

    # Divider lines separating SAFE (0..4), TARGET (5), LEAKAGE (6..9)
    ax.axvline(4.5, color="black", linewidth=2.5)
    ax.axhline(4.5, color="black", linewidth=2.5)
    ax.axvline(5.5, color="red", linewidth=2.5)
    ax.axhline(5.5, color="red", linewidth=2.5)

    for i in range(n):
        for j in range(n):
            text_color = "white" if abs(corr[i, j]) > 0.45 else "black"
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", color=text_color, fontsize=8)

    ax.set_title("Feature Correlation Matrix with Strict Data Leakage Demarcation", fontsize=12, fontweight="bold", pad=15)
    plt.tight_layout()
    path = os.path.join(out_dir, "11_feature_correlation_matrix.png")
    plt.savefig(path)
    plt.close()
    return path


# ==============================================================================
# STATISTICAL ANALYSIS & REPORT GENERATION
# ==============================================================================

def run_comprehensive_analysis():
    """Performs end-to-end exploratory analysis, prints results, and saves plots."""
    print("=" * 80)
    print("SMART BATTERY AI - EXPLORATORY DATA ANALYSIS & DATA LEAKAGE REPORT")
    print("=" * 80)

    out_dir = ensure_output_dir()
    df, users = load_datasets()

    print(f"\n1. DATASET DIMENSIONS:")
    print(f"   - Charging Sessions: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"   - User Registry:     {users.shape[0]:,} rows x {users.shape[1]} columns")
    print(f"   - Date Range:        {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')} (60 days)")
    print(f"   - Unique Users:      {df['user_id'].nunique()}")
    print(f"   - Missing Values:    {df.isnull().sum().sum()} across entire dataset")
    print(f"   - Duplicate Records: {df.duplicated().sum()}")

    # Generate all plots
    print(f"\n2. GENERATING VISUALIZATIONS (Matplotlib Only)...")
    p1 = plot_01_charging_start_distribution(df, out_dir)
    print(f"   [OK] 01_charging_start_distribution.png saved")
    p2 = plot_02_unplug_time_distribution(df, out_dir)
    print(f"   [OK] 02_unplug_time_distribution.png saved")
    p3 = plot_03_unplug_by_profile(df, out_dir)
    print(f"   [OK] 03_unplug_by_profile.png saved")
    p4 = plot_04_start_soc_distribution(df, out_dir)
    print(f"   [OK] 04_start_soc_distribution.png saved")
    p5 = plot_05_screen_usage_by_profile(df, out_dir)
    print(f"   [OK] 05_screen_usage_by_profile.png saved")
    p6 = plot_06_weekday_vs_weekend_unplug(df, out_dir)
    print(f"   [OK] 06_weekday_vs_weekend_unplug.png saved")
    p7 = plot_07_temperature_by_charger(df, out_dir)
    print(f"   [OK] 07_temperature_by_charger.png saved")
    p8 = plot_08_sessions_per_user(df, out_dir)
    print(f"   [OK] 08_sessions_per_user.png saved")
    p9 = plot_09_start_soc_vs_screen_usage(df, out_dir)
    print(f"   [OK] 09_start_soc_vs_screen_usage.png saved")
    p10 = plot_10_user_unplug_variability(df, out_dir)
    print(f"   [OK] 10_user_unplug_variability.png saved")
    p11 = plot_11_feature_correlation_matrix(df, out_dir)
    print(f"   [OK] 11_feature_correlation_matrix.png saved")

    # Time-of-Day & Circular Analysis
    print(f"\n3. TIME-OF-DAY & CIRCULAR TIME ANALYSIS:")
    lin_mean_start = df["charging_start_hour"].mean()
    lin_std_start = df["charging_start_hour"].std()
    circ_mean_start, circ_std_start = circular_mean_std(df["charging_start_hour"])

    lin_mean_unplug = df["unplug_hour"].mean()
    lin_std_unplug = df["unplug_hour"].std()
    circ_mean_unplug, circ_std_unplug = circular_mean_std(df["unplug_hour"])

    print(f"   - Charging Start Hour:")
    print(f"     * Linear Metric:   Mean = {lin_mean_start:.2f}h, Std = {lin_std_start:.2f}h")
    print(f"     * Circular Metric: Mean = {circ_mean_start:.2f}h, Std = {circ_std_start:.2f}h")
    print(f"   - Unplug Hour (Primary Target):")
    print(f"     * Linear Metric:   Mean = {lin_mean_unplug:.2f}h, Std = {lin_std_unplug:.2f}h")
    print(f"     * Circular Metric: Mean = {circ_mean_unplug:.2f}h, Std = {circ_std_unplug:.2f}h")

    overnight_mask = (df["charging_start_hour"] >= 20) | (df["charging_start_hour"] <= 4)
    overnight_pct = (overnight_mask.sum() / len(df)) * 100.0
    print(f"   - Overnight Sessions (Start between 20:00 and 04:00): {overnight_mask.sum():,} ({overnight_pct:.1f}%)")

    # User Behavior & Predictability
    print(f"\n4. USER BEHAVIOR & PREDICTABILITY TIERS:")
    user_metrics = []
    for uid, grp in df.groupby("user_id"):
        c_mean, c_std = circular_mean_std(grp["unplug_hour"])
        overnight = grp[(grp["charging_start_hour"] >= 20) | (grp["charging_start_hour"] <= 4)]
        if len(overnight) >= 5:
            _, ov_std = circular_mean_std(overnight["unplug_hour"])
        else:
            ov_std = c_std
        user_metrics.append({
            "user_id": uid,
            "profile": grp["profile_type"].iloc[0],
            "sessions": len(grp),
            "circ_std": c_std,
            "overnight_circ_std": ov_std,
            "mean_soc": grp["start_battery_percent"].mean(),
            "mean_screen": grp["screen_usage_minutes"].mean()
        })
    u_df = pd.DataFrame(user_metrics)

    high_pred = (u_df["overnight_circ_std"] < 0.75).sum()
    mod_pred = ((u_df["overnight_circ_std"] >= 0.75) & (u_df["overnight_circ_std"] < 1.50)).sum()
    irr_pred = (u_df["overnight_circ_std"] >= 1.50).sum()

    print(f"   - Highly Predictable Users (Overnight Unplug Std < 45 min): {high_pred} users ({high_pred}%)")
    print(f"   - Moderately Predictable Users (Overnight Unplug Std 45m - 90m): {mod_pred} users ({mod_pred}%)")
    print(f"   - Irregular Users (Overnight Unplug Std >= 90 min): {irr_pred} users ({irr_pred}%)")

    # Profile Analysis
    print(f"\n5. BEHAVIORAL PROFILE SUMMARY:")
    prof_grp = df.groupby("profile_type")
    prof_stats = prof_grp.agg(
        sessions=("session_id", "count"),
        mean_start_hr=("charging_start_hour", "mean"),
        mean_unplug_hr=("unplug_hour", "mean"),
        mean_start_soc=("start_battery_percent", "mean"),
        mean_end_soc=("end_battery_percent", "mean"),
        mean_temp=("average_temperature", "mean"),
        mean_duration=("charging_duration_minutes", "mean"),
        mean_screen=("screen_usage_minutes", "mean")
    )
    print(prof_stats.to_string())

    # Weekday vs Weekend Analysis
    print(f"\n6. WEEKDAY VS. WEEKEND UNPLUG DELTA:")
    pivot = df.groupby(["profile_type", "is_weekend"])["unplug_hour"].mean().unstack()
    pivot["Weekend_Shift_Hours"] = pivot[1] - pivot[0]
    print(pivot[[0, 1, "Weekend_Shift_Hours"]].rename(columns={0: "Weekday_Mean", 1: "Weekend_Mean"}))

    # Charger Type Analysis
    print(f"\n7. CHARGER TYPE CHARACTERISTICS:")
    charger_stats = df.groupby("charger_type").agg(
        count=("session_id", "count"),
        mean_temp=("average_temperature", "mean"),
        std_temp=("average_temperature", "std"),
        mean_duration=("charging_duration_minutes", "mean")
    )
    print(charger_stats.to_string())

    # Data Leakage Summary
    print(f"\n8. DATA LEAKAGE CLASSIFICATION SUMMARY:")
    print(f"   - SAFE at Prediction Time:        date, weekday, is_weekend, charging_start_time, charging_start_hour,")
    print(f"                                     start_battery_percent, charger_type, previous_day_usage_minutes, user_id")
    print(f"   - HISTORICAL / DERIVED (Safe):    user_past_avg_unplug, user_past_unplug_std, user_weekday_avg_unplug")
    print(f"   - TARGET:                         unplug_time / unplug_hour (or derived session duration)")
    print(f"   - DATA LEAKAGE (MUST EXCLUDE):    end_battery_percent, charging_duration_minutes,")
    print(f"                                     average_temperature (full session average), screen_usage_minutes (daily total)")
    print(f"   - SIMULATION-ONLY (MUST EXCLUDE): profile_type (synthetic ground truth)")

    print("=" * 80)
    print("ANALYSIS COMPLETE. ALL 11 CHARTS GENERATED IN:", out_dir)
    print("=" * 80)


if __name__ == "__main__":
    run_comprehensive_analysis()
