"""
Smart Battery AI - Synthetic Charging Behavior Dataset Generator
Generates realistic, behavioral charging data for machine learning development.
"""

import os
import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Supported profiles
PROFILES = [
    "REGULAR_OVERNIGHT",
    "IRREGULAR",
    "HEAVY_USER",
    "FREQUENT_TOPUP",
    "WEEKEND_SHIFTER",
    "LATE_NIGHT_USER",
]

CHARGER_TYPES = ["slow", "standard", "fast"]


def generate_synthetic_users(num_users: int = 100, seed: int = 42) -> pd.DataFrame:
    """
    Generates simulated user population with realistic behavioral charging profiles.
    """
    np.random.seed(seed)
    random.seed(seed)

    # Distribute profiles realistically across the 100 users:
    # 20 Regular, 15 Irregular, 18 Heavy, 15 Frequent Top-up, 18 Weekend Shifter, 14 Late Night
    profile_assignments = (
        ["REGULAR_OVERNIGHT"] * 20
        + ["IRREGULAR"] * 15
        + ["HEAVY_USER"] * 18
        + ["FREQUENT_TOPUP"] * 15
        + ["WEEKEND_SHIFTER"] * 18
        + ["LATE_NIGHT_USER"] * 14
    )
    if num_users != len(profile_assignments):
        profile_assignments = list(np.random.choice(PROFILES, size=num_users))
    else:
        random.shuffle(profile_assignments)

    users = []
    for user_id in range(1, num_users + 1):
        profile = profile_assignments[user_id - 1]

        if profile == "REGULAR_OVERNIGHT":
            weekday_charge = round(random.uniform(21.5, 23.2), 2)
            weekday_unplug = round(random.uniform(6.2, 7.3), 2)
            weekend_charge = round(weekday_charge + random.uniform(0.2, 0.5), 2)
            weekend_unplug = round(weekday_unplug + random.uniform(0.3, 0.7), 2)
            baseline_screen = round(random.uniform(180, 280), 1)
            preferred_charger = random.choices(["standard", "slow", "fast"], weights=[0.75, 0.20, 0.05])[0]

        elif profile == "IRREGULAR":
            weekday_charge = round(random.uniform(19.0, 23.5), 2)
            weekday_unplug = round(random.uniform(6.0, 9.0), 2)
            weekend_charge = round(random.uniform(20.0, 24.5) % 24.0, 2)
            weekend_unplug = round(random.uniform(7.0, 10.5), 2)
            baseline_screen = round(random.uniform(220, 380), 1)
            preferred_charger = random.choices(["standard", "fast", "slow"], weights=[0.50, 0.35, 0.15])[0]

        elif profile == "HEAVY_USER":
            weekday_charge = round(random.uniform(22.0, 23.8), 2)
            weekday_unplug = round(random.uniform(6.5, 7.8), 2)
            weekend_charge = round(weekday_charge + random.uniform(0.3, 0.8), 2)
            weekend_unplug = round(weekday_unplug + random.uniform(0.5, 1.0), 2)
            baseline_screen = round(random.uniform(430, 620), 1)  # Substantially above global avg
            preferred_charger = random.choices(["fast", "standard", "slow"], weights=[0.80, 0.18, 0.02])[0]

        elif profile == "FREQUENT_TOPUP":
            weekday_charge = round(random.uniform(22.0, 23.5), 2)
            weekday_unplug = round(random.uniform(6.5, 7.5), 2)
            weekend_charge = round(random.uniform(22.2, 23.8), 2)
            weekend_unplug = round(random.uniform(7.0, 8.2), 2)
            baseline_screen = round(random.uniform(190, 310), 1)
            preferred_charger = random.choices(["standard", "fast", "slow"], weights=[0.65, 0.30, 0.05])[0]

        elif profile == "WEEKEND_SHIFTER":
            weekday_charge = round(random.uniform(21.5, 22.8), 2)  # Earlier sleep on weekdays
            weekday_unplug = round(random.uniform(6.0, 6.9), 2)    # Earlier wake on weekdays
            weekend_charge = round(random.uniform(23.8, 25.5) % 24.0, 2)
            weekend_unplug = round(random.uniform(8.8, 10.2), 2)   # Noticeably later wake (+2.5 to 3.5 hrs)
            baseline_screen = round(random.uniform(210, 340), 1)
            preferred_charger = random.choices(["standard", "fast", "slow"], weights=[0.70, 0.25, 0.05])[0]

        elif profile == "LATE_NIGHT_USER":
            weekday_charge = round(random.uniform(0.2, 2.2), 2)    # Midnight or later
            weekday_unplug = round(random.uniform(8.2, 9.8), 2)    # Late morning
            weekend_charge = round(random.uniform(0.5, 2.8), 2)
            weekend_unplug = round(random.uniform(8.8, 10.5), 2)
            baseline_screen = round(random.uniform(320, 480), 1)
            preferred_charger = random.choices(["standard", "fast", "slow"], weights=[0.60, 0.30, 0.10])[0]

        users.append({
            "user_id": user_id,
            "profile_type": profile,
            "typical_weekday_charge_hour": weekday_charge,
            "typical_weekday_unplug_hour": weekday_unplug,
            "typical_weekend_charge_hour": weekend_charge,
            "typical_weekend_unplug_hour": weekend_unplug,
            "baseline_daily_screen_minutes": baseline_screen,
            "preferred_charger_type": preferred_charger,
        })

    return pd.DataFrame(users)


def generate_synthetic_charging_sessions(
    users_df: pd.DataFrame,
    num_days: int = 60,
    start_date: datetime = datetime(2026, 1, 1),
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates multi-day charging behavior time-series with realistic behavioral correlations,
    proper overnight time handling, temperature dynamics, and top-up sessions.
    """
    np.random.seed(seed)
    random.seed(seed)

    sessions = []
    session_counter = 1

    for _, user in users_df.iterrows():
        user_id = int(user["user_id"])
        profile = user["profile_type"]
        baseline_screen = float(user["baseline_daily_screen_minutes"])
        preferred_charger = user["preferred_charger_type"]

        # Track previous day's usage for autocorrelation
        prev_usage = baseline_screen * random.uniform(0.9, 1.1)

        for day_idx in range(num_days):
            current_day = start_date + timedelta(days=day_idx)
            weekday = current_day.weekday()
            is_weekend = 1 if weekday >= 5 else 0

            # 1. Screen usage for today (correlated with user profile and previous day)
            day_noise = float(np.random.normal(0, 30))
            if profile == "HEAVY_USER":
                day_noise += 40
            screen_usage = max(60.0, round(0.7 * baseline_screen + 0.3 * prev_usage + day_noise, 1))
            if profile == "HEAVY_USER":
                screen_usage = max(400.0, screen_usage)

            # 2. Daytime top-up session probability
            has_daytime_topup = False
            if profile == "FREQUENT_TOPUP":
                has_daytime_topup = random.random() < 0.75
            elif profile == "HEAVY_USER":
                has_daytime_topup = random.random() < 0.55
            else:
                has_daytime_topup = random.random() < 0.12

            # If daytime top-up occurs
            if has_daytime_topup:
                topup_charger = random.choices(
                    [preferred_charger, "fast", "standard"], weights=[0.6, 0.25, 0.15]
                )[0]
                # Start between 12:30 PM and 4:30 PM
                topup_start_hour = random.uniform(12.5, 16.5)
                topup_duration_mins = random.uniform(35.0, 120.0)
                if topup_charger == "fast":
                    topup_duration_mins = random.uniform(25.0, 65.0)

                topup_start_dt = current_day + timedelta(minutes=int(round(topup_start_hour * 60)))
                topup_start_dt = topup_start_dt.replace(second=0, microsecond=0)
                topup_unplug_dt = topup_start_dt + timedelta(minutes=int(round(topup_duration_mins)))
                topup_unplug_dt = topup_unplug_dt.replace(second=0, microsecond=0)
                actual_duration = round((topup_unplug_dt - topup_start_dt).total_seconds() / 60.0, 1)

                if profile == "FREQUENT_TOPUP":
                    start_soc = round(random.uniform(48.0, 74.0), 1)
                elif profile == "HEAVY_USER":
                    start_soc = round(random.uniform(12.0, 28.0), 1)
                else:
                    start_soc = round(random.uniform(30.0, 55.0), 1)

                soc_gain = (actual_duration / 60.0) * (55.0 if topup_charger == "fast" else 32.0)
                end_soc = round(min(100.0, start_soc + max(8.0, soc_gain)), 1)
                if end_soc <= start_soc:
                    end_soc = round(min(100.0, start_soc + 10.0), 1)

                # Temperature calculation
                temp_base = 28.0 + (4.5 if topup_charger == "fast" else 1.8) + (screen_usage / 400.0)
                temp = round(float(np.clip(np.random.normal(temp_base, 1.6), 24.5, 42.8)), 1)

                sessions.append({
                    "session_id": f"sess_{session_counter:06d}",
                    "user_id": user_id,
                    "date": current_day.strftime("%Y-%m-%d"),
                    "charging_start_time": topup_start_dt.isoformat(),
                    "unplug_time": topup_unplug_dt.isoformat(),
                    "charging_start_hour": round(topup_start_dt.hour + topup_start_dt.minute / 60.0, 2),
                    "unplug_hour": round(topup_unplug_dt.hour + topup_unplug_dt.minute / 60.0, 2),
                    "start_battery_percent": start_soc,
                    "end_battery_percent": end_soc,
                    "average_temperature": temp,
                    "charging_duration_minutes": actual_duration,
                    "charger_type": topup_charger,
                    "screen_usage_minutes": round(screen_usage * 0.35, 1),
                    "weekday": weekday,
                    "is_weekend": is_weekend,
                    "previous_day_usage_minutes": round(prev_usage, 1),
                    "profile_type": profile,
                })
                session_counter += 1

            # 3. Primary / Overnight Charging Session
            target_charge_h = float(
                user["typical_weekend_charge_hour"] if is_weekend else user["typical_weekday_charge_hour"]
            )
            target_unplug_h = float(
                user["typical_weekend_unplug_hour"] if is_weekend else user["typical_weekday_unplug_hour"]
            )

            # Profile-specific variance
            if profile == "REGULAR_OVERNIGHT":
                charge_noise = float(np.random.normal(0, 0.35))  # low variance (~20 mins)
                unplug_noise = float(np.random.normal(0, 0.35))
            elif profile == "IRREGULAR":
                charge_noise = float(np.random.normal(0, 2.5))   # high variance (~150 mins)
                unplug_noise = float(np.random.normal(0, 2.2))
            elif profile == "WEEKEND_SHIFTER":
                charge_noise = float(np.random.normal(0, 0.45))
                unplug_noise = float(np.random.normal(0, 0.40))
            elif profile == "LATE_NIGHT_USER":
                charge_noise = float(np.random.normal(0, 0.50))
                unplug_noise = float(np.random.normal(0, 0.55))
            else:
                charge_noise = float(np.random.normal(0, 0.60))
                unplug_noise = float(np.random.normal(0, 0.60))

            actual_charge_h = target_charge_h + charge_noise
            actual_unplug_h = target_unplug_h + unplug_noise

            # Determine start datetime and unplug datetime with proper midnight crossing
            if actual_charge_h >= 12.0:
                # Evening start on current_day
                actual_charge_h = min(23.98, max(12.0, actual_charge_h))
                start_dt = current_day + timedelta(minutes=int(round(actual_charge_h * 60)))
                # Next morning unplug on current_day + 1
                actual_unplug_h = min(14.0, max(4.0, actual_unplug_h))
                unplug_dt = (current_day + timedelta(days=1)) + timedelta(minutes=int(round(actual_unplug_h * 60)))
            else:
                # Late night / early morning start on current_day + 1 (e.g. 01:15 AM)
                actual_charge_h = max(0.0, min(5.0, actual_charge_h))
                start_dt = (current_day + timedelta(days=1)) + timedelta(minutes=int(round(actual_charge_h * 60)))
                actual_unplug_h = max(actual_charge_h + 3.0, min(14.0, actual_unplug_h))
                unplug_dt = (current_day + timedelta(days=1)) + timedelta(minutes=int(round(actual_unplug_h * 60)))

            start_dt = start_dt.replace(second=0, microsecond=0)
            unplug_dt = unplug_dt.replace(second=0, microsecond=0)

            # Ensure unplug_dt is strictly after start_dt
            if unplug_dt <= start_dt:
                unplug_dt = start_dt + timedelta(minutes=int(round(random.uniform(4.5, 7.5) * 60)))
                unplug_dt = unplug_dt.replace(second=0, microsecond=0)

            duration_mins = round((unplug_dt - start_dt).total_seconds() / 60.0, 1)

            # Start battery % calculation
            usage_factor = (screen_usage - 250.0) / 400.0
            if profile == "HEAVY_USER":
                base_start = random.uniform(6.0, 24.0) - (usage_factor * 8.0)
            elif profile == "FREQUENT_TOPUP":
                base_start = random.uniform(45.0, 72.0)
            else:
                base_start = random.uniform(20.0, 50.0) - (usage_factor * 12.0)

            if has_daytime_topup:
                base_start += random.uniform(15.0, 30.0)

            start_soc = round(float(np.clip(base_start, 5.0, 78.0)), 1)
            end_soc = round(float(np.clip(random.uniform(92.0, 100.0), start_soc + 5.0, 100.0)), 1)
            if end_soc <= start_soc:
                end_soc = round(min(100.0, start_soc + 8.0), 1)

            # Primary charger
            charger = random.choices(
                [preferred_charger, "standard", "fast"], weights=[0.85, 0.10, 0.05]
            )[0]

            # Primary temperature
            temp_base = 27.5
            if charger == "fast":
                temp_base += 4.5
            elif charger == "standard":
                temp_base += 1.8
            if screen_usage > 400:
                temp_base += 2.0
            if start_soc < 15.0:
                temp_base += 1.2

            primary_temp = round(float(np.clip(np.random.normal(temp_base, 1.6), 24.0, 42.5)), 1)

            sessions.append({
                "session_id": f"sess_{session_counter:06d}",
                "user_id": user_id,
                "date": current_day.strftime("%Y-%m-%d"),
                "charging_start_time": start_dt.isoformat(),
                "unplug_time": unplug_dt.isoformat(),
                "charging_start_hour": round(start_dt.hour + start_dt.minute / 60.0, 2),
                "unplug_hour": round(unplug_dt.hour + unplug_dt.minute / 60.0, 2),
                "start_battery_percent": start_soc,
                "end_battery_percent": end_soc,
                "average_temperature": primary_temp,
                "charging_duration_minutes": duration_mins,
                "charger_type": charger,
                "screen_usage_minutes": round(screen_usage, 1),
                "weekday": weekday,
                "is_weekend": is_weekend,
                "previous_day_usage_minutes": round(prev_usage, 1),
                "profile_type": profile,
            })
            session_counter += 1

            prev_usage = screen_usage

    return pd.DataFrame(sessions)


def validate_dataset(df: pd.DataFrame, users_df: pd.DataFrame) -> dict:
    """
    Validates dataset integrity against all 11 required realism and structural rules.
    """
    checks = {}

    # 1. Total rows (>= 6000)
    total_rows = len(df)
    checks["1_total_rows"] = {
        "status": total_rows >= 6000,
        "value": total_rows,
        "requirement": ">= 6,000",
    }

    # 2. Number of unique users (100)
    unique_users = df["user_id"].nunique()
    checks["2_unique_users"] = {
        "status": unique_users == len(users_df) == 100,
        "value": unique_users,
        "requirement": "100",
    }

    # 3. Missing values
    missing_count = int(df.isnull().sum().sum()) + int(users_df.isnull().sum().sum())
    checks["3_missing_values"] = {
        "status": missing_count == 0,
        "value": missing_count,
        "requirement": "0 missing values",
    }

    # 4. Duplicate session IDs
    duplicate_sessions = int(df["session_id"].duplicated().sum())
    checks["4_duplicate_session_ids"] = {
        "status": duplicate_sessions == 0,
        "value": duplicate_sessions,
        "requirement": "0 duplicates",
    }

    # 5. Battery percentages outside 0-100
    invalid_soc = int(
        ((df["start_battery_percent"] < 0) | (df["start_battery_percent"] > 100)
         | (df["end_battery_percent"] < 0) | (df["end_battery_percent"] > 100)).sum()
    )
    checks["5_invalid_battery_percent"] = {
        "status": invalid_soc == 0,
        "value": invalid_soc,
        "requirement": "0 out-of-bounds",
    }

    # 6. end SOC <= start SOC
    end_less_than_start = int((df["end_battery_percent"] <= df["start_battery_percent"]).sum())
    checks["6_end_soc_le_start_soc"] = {
        "status": end_less_than_start == 0,
        "value": end_less_than_start,
        "requirement": "0 occurrences",
    }

    # 7. Negative charging duration
    negative_duration = int((df["charging_duration_minutes"] <= 0).sum())
    checks["7_negative_duration"] = {
        "status": negative_duration == 0,
        "value": negative_duration,
        "requirement": "0 occurrences",
    }

    # 8. Unrealistic temperatures (< 20C or > 48C)
    unrealistic_temp = int(((df["average_temperature"] < 20.0) | (df["average_temperature"] > 48.0)).sum())
    checks["8_unrealistic_temperatures"] = {
        "status": unrealistic_temp == 0,
        "value": unrealistic_temp,
        "requirement": "0 occurrences",
    }

    # 9. Invalid weekday values (not in 0..6)
    invalid_weekday = int((~df["weekday"].isin(range(7))).sum())
    checks["9_invalid_weekday"] = {
        "status": invalid_weekday == 0,
        "value": invalid_weekday,
        "requirement": "0 occurrences",
    }

    # 10. Invalid charger types
    invalid_chargers = int((~df["charger_type"].isin(CHARGER_TYPES)).sum())
    checks["10_invalid_charger_types"] = {
        "status": invalid_chargers == 0,
        "value": invalid_chargers,
        "requirement": "0 occurrences",
    }

    # 11. Timestamps where unplug occurs before or equal to charging start
    start_dt_series = pd.to_datetime(df["charging_start_time"], format="ISO8601")
    unplug_dt_series = pd.to_datetime(df["unplug_time"], format="ISO8601")
    inverted_timestamps = int((unplug_dt_series <= start_dt_series).sum())
    checks["11_inverted_timestamps"] = {
        "status": inverted_timestamps == 0,
        "value": inverted_timestamps,
        "requirement": "0 occurrences",
    }

    return checks


def print_summary_statistics(df: pd.DataFrame, users_df: pd.DataFrame):
    """Prints dataset shape, profile distribution, and key behavioral metrics."""
    print("=" * 70)
    print("DATASET SUMMARY STATISTICS")
    print("=" * 70)
    print(f"Charging Behavior Dataset Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"Users Dataset Shape:             {users_df.shape[0]} rows x {users_df.shape[1]} columns")
    print(f"Unique Users:                    {df['user_id'].nunique()}")
    print(f"Total Charging Sessions:         {len(df)}")
    print("\nProfile Distribution:")
    for profile, count in users_df["profile_type"].value_counts().items():
        sess_count = len(df[df["profile_type"] == profile])
        print(f"  - {profile:20s}: {count:2d} users ({sess_count:5d} sessions)")

    print("\nGlobal Averages:")
    print(f"  - Start Battery Percent:       {df['start_battery_percent'].mean():.2f}%")
    print(f"  - End Battery Percent:         {df['end_battery_percent'].mean():.2f}%")
    print(f"  - Battery Temperature:         {df['average_temperature'].mean():.2f}°C")
    print(f"  - Charging Duration:           {df['charging_duration_minutes'].mean():.2f} mins ({df['charging_duration_minutes'].mean()/60:.2f} hrs)")
    print(f"  - Daily Screen Usage:          {df['screen_usage_minutes'].mean():.2f} mins")

    print("\nAverage Unplug Hour by Profile:")
    unplug_by_prof = df.groupby("profile_type")["unplug_hour"].agg(["mean", "std"])
    for prof, row in unplug_by_prof.iterrows():
        print(f"  - {prof:20s}: mean = {row['mean']:5.2f}h | std = {row['std']:4.2f}h")

    # Weekend shifter analysis
    ws_df = df[df["profile_type"] == "WEEKEND_SHIFTER"]
    ws_weekday = ws_df[ws_df["is_weekend"] == 0]["unplug_hour"].mean()
    ws_weekend = ws_df[ws_df["is_weekend"] == 1]["unplug_hour"].mean()
    print("\nWeekend Shifter Behavioral Shift:")
    print(f"  - Weekday Average Unplug Hour: {ws_weekday:.2f}h")
    print(f"  - Weekend Average Unplug Hour: {ws_weekend:.2f}h")
    print(f"  - Weekend Shift Delta:        +{ws_weekend - ws_weekday:.2f} hours later")

    print("\nFirst 10 Rows of Charging Behavior Dataset:")
    print(df.head(10).to_string(index=False))


def run_quality_checks(df: pd.DataFrame) -> dict:
    """
    Performs statistical validation showing that behavioral profiles
    exhibit genuine, statistically distinct characteristics.
    """
    print("\n" + "=" * 70)
    print("BEHAVIORAL QUALITY & PROFILE DIVERGENCE CHECKS")
    print("=" * 70)
    results = {}

    # Check 1: Regular Overnight vs Irregular Unplug Variance
    var_regular = float(df[df["profile_type"] == "REGULAR_OVERNIGHT"]["unplug_hour"].var())
    var_irregular = float(df[df["profile_type"] == "IRREGULAR"]["unplug_hour"].var())
    check_1 = var_irregular > var_regular
    results["variance_check"] = {
        "passed": check_1,
        "regular_variance": round(var_regular, 3),
        "irregular_variance": round(var_irregular, 3),
        "description": "IRREGULAR unplug-time variance is substantially higher than REGULAR_OVERNIGHT",
    }
    print(f"[Check 1] Unplug Time Variance:")
    print(f"  REGULAR_OVERNIGHT Variance: {var_regular:.3f} | IRREGULAR Variance: {var_irregular:.3f} -> Passed: {check_1}")

    # Check 2: Weekend Shifter weekday vs weekend unplug difference
    ws_df = df[df["profile_type"] == "WEEKEND_SHIFTER"]
    ws_weekday = float(ws_df[ws_df["is_weekend"] == 0]["unplug_hour"].mean())
    ws_weekend = float(ws_df[ws_df["is_weekend"] == 1]["unplug_hour"].mean())
    check_2 = (ws_weekend - ws_weekday) >= 1.5
    results["weekend_shifter_check"] = {
        "passed": check_2,
        "weekday_mean": round(ws_weekday, 2),
        "weekend_mean": round(ws_weekend, 2),
        "delta": round(ws_weekend - ws_weekday, 2),
        "description": "WEEKEND_SHIFTER unplugs at least 1.5 hours later on weekends",
    }
    print(f"[Check 2] Weekend Shifter Shift:")
    print(f"  Weekday: {ws_weekday:.2f}h | Weekend: {ws_weekend:.2f}h (Delta: +{ws_weekend - ws_weekday:.2f}h) -> Passed: {check_2}")

    # Check 3: Heavy user screen usage > global screen usage
    global_screen = float(df["screen_usage_minutes"].mean())
    heavy_screen = float(df[df["profile_type"] == "HEAVY_USER"]["screen_usage_minutes"].mean())
    check_3 = heavy_screen > global_screen
    results["heavy_screen_check"] = {
        "passed": check_3,
        "heavy_screen_mean": round(heavy_screen, 1),
        "global_screen_mean": round(global_screen, 1),
        "description": "HEAVY_USER has higher average screen usage than global average",
    }
    print(f"[Check 3] Screen Usage Comparison:")
    print(f"  HEAVY_USER Mean: {heavy_screen:.1f} mins | Global Mean: {global_screen:.1f} mins -> Passed: {check_3}")

    # Check 4: Frequent top-up start SOC > heavy user start SOC
    topup_soc = float(df[df["profile_type"] == "FREQUENT_TOPUP"]["start_battery_percent"].mean())
    heavy_soc = float(df[df["profile_type"] == "HEAVY_USER"]["start_battery_percent"].mean())
    check_4 = topup_soc > heavy_soc
    results["topup_vs_heavy_soc_check"] = {
        "passed": check_4,
        "frequent_topup_mean_soc": round(topup_soc, 1),
        "heavy_user_mean_soc": round(heavy_soc, 1),
        "description": "FREQUENT_TOPUP has higher average start SOC than HEAVY_USER",
    }
    print(f"[Check 4] Start SOC Comparison:")
    print(f"  FREQUENT_TOPUP Mean Start SOC: {topup_soc:.1f}% | HEAVY_USER Mean Start SOC: {heavy_soc:.1f}% -> Passed: {check_4}")

    return results


def main():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    users_file = os.path.join(data_dir, "users.csv")
    charging_file = os.path.join(data_dir, "charging_behavior.csv")

    print(f"Generating synthetic population (100 users)...")
    users_df = generate_synthetic_users(num_users=100, seed=42)
    users_df.to_csv(users_file, index=False)
    print(f"Saved users dataset to: {users_file}")

    print(f"Generating 60 days of charging behavior per user...")
    charging_df = generate_synthetic_charging_sessions(users_df, num_days=60, seed=42)
    charging_df.to_csv(charging_file, index=False)
    print(f"Saved charging behavior dataset to: {charging_file}")

    # Validation
    print("\n" + "=" * 70)
    print("DATA INTEGRITY VALIDATION")
    print("=" * 70)
    val_results = validate_dataset(charging_df, users_df)
    all_passed = True
    for rule, info in val_results.items():
        status_str = "PASS" if info["status"] else "FAIL"
        if not info["status"]:
            all_passed = False
        print(f"  [{status_str}] {rule}: {info['value']} (Req: {info['requirement']})")

    if all_passed:
        print("\nAll 11 Data Integrity Validation Rules Passed Successfully.")
    else:
        print("\nWarning: Some data integrity rules failed.")

    # Summary Statistics & Quality Checks
    print_summary_statistics(charging_df, users_df)
    run_quality_checks(charging_df)


if __name__ == "__main__":
    main()
