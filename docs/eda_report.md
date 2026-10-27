# Smart Battery AI — Exploratory Data Analysis & Data Leakage Report

**Project**: AI-Based Personalized Battery Charging Based on User Behavior  
**Target Variable**: Expected Unplug Time (`unplug_time` / `unplug_hour`)  
**Dataset**: `data/charging_behavior.csv` (7,735 sessions) & `data/users.csv` (100 users)  
**Analysis Script**: [`scripts/analyze_charging_data.py`](file:///C:/projects/smart-battery-ai/scripts/analyze_charging_data.py)  
**Visualizations**: [`docs/analysis/`](file:///C:/projects/smart-battery-ai/docs/analysis/)  

---

## Executive Summary

The primary objective of the machine learning system in **Smart Battery AI** is to predict when a user will unplug their mobile device upon initiating a charging session. Knowing the expected unplug time allows the system to compute optimal charging trajectories—delaying or slowing down the charge to avoid prolonged exposure to high state-of-charge (SoC $\ge 80\%$) and elevated temperatures, which are the two dominant physical mechanisms of lithium-ion cell degradation.

This Exploratory Data Analysis (EDA) report rigorously evaluates the synthetic charging dataset, assesses the predictability of user routines, quantifies behavioral divergences across user personas, and establishes **strict data leakage boundaries** to ensure that production machine learning models rely exclusively on information realistically available at plug-in time.

---

## 1. Dataset Overview

The dataset comprises longitudinal records across a 60-day observation period (2026-01-01 to 2026-03-01) for 100 simulated users, generating 7,735 individual charging sessions.

### Dataset Dimensions & Schemas

| Dataset | Records | Features | Primary Keys / Foreign Keys | Date Range |
|---|---|---|---|---|
| **`charging_behavior.csv`** | 7,735 | 17 | `session_id` (PK), `user_id` (FK) | 2026-01-01 to 2026-03-01 (60 days) |
| **`users.csv`** | 100 | 8 | `user_id` (PK) | Population Profile Parameters |

### Feature Inventory & Data Types

| Column Name | Data Type | Physical Units / Encoding | Description |
|---|---|---|---|
| `session_id` | `object` (string) | Unique ID (`sess_000001`) | Unique charging event identifier |
| `user_id` | `int64` | Integer (1 to 100) | Unique user identification |
| `date` | `object` (ISO date) | `YYYY-MM-DD` | Date of charging session start |
| `charging_start_time` | `datetime64[ns]` | ISO 8601 timestamp | Exact timestamp when charging started |
| `unplug_time` | `datetime64[ns]` | ISO 8601 timestamp | Exact timestamp when device was unplugged |
| `charging_start_hour` | `float64` | Decimal hour (0.00 – 24.00) | Time of plug-in in fractional hours |
| `unplug_hour` | `float64` | Decimal hour (0.00 – 24.00) | Time of unplug in fractional hours (**ML Target**) |
| `start_battery_percent` | `float64` | Percentage (0.0 – 100.0%) | Battery SoC at plug-in |
| `end_battery_percent` | `float64` | Percentage (0.0 – 100.0%) | Battery SoC at unplug |
| `average_temperature` | `float64` | Celsius (°C) | Mean battery pack temperature during session |
| `charging_duration_minutes`| `float64` | Minutes | Elapsed duration between plug-in and unplug |
| `charger_type` | `object` (category) | `slow`, `standard`, `fast` | Charger hardware specification |
| `screen_usage_minutes` | `float64` | Minutes / day | Total active screen-on time on session date |
| `weekday` | `int64` | Integer (0=Monday ... 6=Sunday) | Day-of-week index |
| `is_weekend` | `int64` | Binary (0=Weekday, 1=Weekend) | Weekend indicator flag |
| `previous_day_usage_minutes`| `float64` | Minutes / day | Screen-on time recorded on day $t-1$ |
| `profile_type` | `object` (category) | 6 synthetic profile personas | Simulation ground-truth profile |

### User Population Demographics

The 100 simulated users are categorized across six behavioral archetypes:
1. **`REGULAR_OVERNIGHT`** (20 users, 20%): Highly structured bedtime and morning routines.
2. **`HEAVY_USER`** (18 users, 18%): High daily screen consumption requiring midday top-ups and fast charging.
3. **`WEEKEND_SHIFTER`** (18 users, 18%): Consistent weekday schedules with delayed weekend sleep and wake times.
4. **`FREQUENT_TOPUP`** (15 users, 15%): Low tolerance for battery depletion; frequent partial charges at high SoC.
5. **`IRREGULAR`** (15 users, 15%): Unpredictable routines with high variance in plug-in and unplug timings.
6. **`LATE_NIGHT_USER`** (14 users, 14%): Nocturnal habits; plugs in well past midnight (01:00 – 03:00) and wakes mid-morning.

---

## 2. Data Quality Audit

A thorough audit confirms that the dataset meets the strictest quality criteria:

- **Missing Values**: 0 missing values across all 7,735 records (100% complete).
- **Duplicate Records**: 0 duplicate session IDs or duplicate timestamp entries.
- **Physical Validity**:
  - `start_battery_percent`: Min = 1.0%, Max = 80.0%, Mean = 41.01%.
  - `end_battery_percent`: Min = 40.0%, Max = 100.0%, Mean = 92.51%.
  - $\text{end\_battery\_percent} \ge \text{start\_battery\_percent}$ strictly holds for 100% of sessions.
- **Temporal Consistency**:
  - `charging_duration_minutes` > 0 for all records (Min = 15.0 min, Max = 811.0 min, Mean = 428.2 min).
  - Calculated duration exactly matches `(unplug_time - charging_start_time)` in total minutes.
  - Correct midnight-crossing handling: Sessions starting at 23:00 and ending at 07:00 next day have `unplug_time` registered on $date + 1$ with positive durations.

---

## 3. User Behavior Analysis & Routine Predictability

Real humans exhibit varying degrees of routine adherence. A model predicting unplug time must recognize that some users are exceptionally predictable, while others have volatile schedules.

### Per-User Routine Dispersion

Using circular statistics on overnight charging sessions (which constitute core routine sleep events), each user's circular standard deviation of unplug time $\sigma_{circ}$ was calculated:

$$\sigma_{circ} = \sqrt{-2 \ln(R)} \times \frac{24}{2\pi}$$

where $R = \frac{1}{N} \sqrt{\left(\sum \sin \theta_i\right)^2 + \left(\sum \cos \theta_i\right)^2}$.

Users were grouped into three predictability tiers:

| Predictability Tier | Dispersion Criteria ($\sigma_{circ}$) | User Count | Percentage | Profile Representation |
|---|---|---|---|---|
| **Highly Predictable** | $\sigma_{circ} < 0.75$ hours (< 45 mins) | **59 users** | **59.0%** | `REGULAR_OVERNIGHT`, `WEEKEND_SHIFTER` (weekday), `LATE_NIGHT_USER` |
| **Moderately Predictable** | $0.75 \le \sigma_{circ} < 1.50$ hours (45 – 90 mins) | **15 users** | **15.0%** | `HEAVY_USER`, `FREQUENT_TOPUP` |
| **Irregular / High Variance** | $\sigma_{circ} \ge 1.50$ hours (> 90 mins) | **26 users** | **26.0%** | `IRREGULAR`, shift workers |

![User Unplug Variability](analysis/10_user_unplug_variability.png)

### Session Frequency Distribution

Over the 60-day window, users recorded between 58 and 126 sessions (Mean = 77.4 sessions, Median = 67.0 sessions).
- Users with standard overnight habits average ~1.1 sessions/day.
- Frequent top-up users and heavy users average 1.7 to 2.1 sessions/day due to midday boosts.

![Sessions per User](analysis/08_sessions_per_user.png)

---

## 4. Behavioral Profile Analysis

Exploratory evaluation confirms that the six simulated behavioral profiles exhibit distinct, statistically measurable signatures across all key operational metrics.

### Summary Statistics by Profile

| Profile Type | Total Sessions | Mean Start Hour | Mean Unplug Hour | Mean Start SoC (%) | Mean End SoC (%) | Mean Temp (°C) | Mean Duration (min) | Mean Screen Time (min) |
|---|---|---|---|---|---|---|---|---|
| **`REGULAR_OVERNIGHT`** | 1,339 | 21.34 (21:20) | 7.78 (07:47) | 38.25% | 94.57% | 29.74°C | 477.38 (8.0h) | 222.24 |
| **`HEAVY_USER`** | 1,664 | 20.09 (20:05) | 10.21 (10:12) | 20.53% | 83.87% | 33.59°C | 341.89 (5.7h) | 460.95 |
| **`FREQUENT_TOPUP`** | 1,576 | 19.28 (19:17) | 10.73 (10:44) | 67.05% | 95.63% | 30.89°C | 308.97 (5.1h) | 191.86 |
| **`WEEKEND_SHIFTER`** | 1,219 | 16.23 (16:14) | 8.33 (08:20) | 38.26% | 94.49% | 29.78°C | 461.47 (7.7h) | 244.22 |
| **`IRREGULAR`** | 1,006 | 19.68 (19:41) | 8.73 (08:44) | 37.00% | 94.55% | 29.58°C | 579.30 (9.7h) | 273.37 |
| **`LATE_NIGHT_USER`** | 931 | 2.73 (02:44) | 9.89 (09:53) | 34.33% | 94.71% | 31.04°C | 430.05 (7.2h) | 371.54 |

![Unplug Hour by Profile](analysis/03_unplug_by_profile.png)

### Key Behavioral Insights:
1. **Plug-in Threshold Divergence**: `FREQUENT_TOPUP` users plug in at a high average SoC of **67.05%**, whereas `HEAVY_USER` individuals regularly draw their battery down to **20.53%** before seeking a charger.
2. **Thermal Load**: `HEAVY_USER` sessions exhibit significantly higher average temperatures (**33.59°C** vs ~29.7°C baseline), driven by their predominant utilization of fast chargers combined with intensive usage.
3. **Nocturnal Outliers**: `LATE_NIGHT_USER` charging events start after midnight (mean 02:44), waking and unplugging later in the morning (mean 09:53).

---

## 5. Time-of-Day & Circular Time Analysis

### Diurnal Session Distribution

The timing of plug-in events exhibits a marked **bimodal distribution**:
- **Overnight Peak**: 73.9% of all charging sessions ($N = 5,720$) initiate between 20:00 and 04:00.
- **Midday Top-up Peak**: 26.1% initiate between 11:30 and 15:00, primarily composed of heavy users and top-up users topping off battery levels during lunch or work breaks.

![Charging Start Hour Distribution](analysis/01_charging_start_distribution.png)

Correspondingly, unplug events cluster heavily around the **morning wake-up window** (06:00 – 08:30) and the **post-lunch unplug window** (13:30 – 15:00).

![Unplug Time Distribution](analysis/02_unplug_time_distribution.png)

### The Circular Time Problem

Time on a 24-hour clock is intrinsically cyclical:
- 23:30 (23.50) and 00:30 (0.50) are physically **1.0 hour apart**.
- In standard linear Cartesian space, $|23.50 - 0.50| = 23.00\text{ hours}$.

Applying standard linear algorithms (Linear Regression, Gradient Boosting, standard Neural Networks) directly to raw numerical hours introduces an artificial mathematical cliff at midnight, severely corrupting distance metrics, gradients, and decision splits.

### Linear vs. Circular Statistics Comparison

| Variable | Linear Arithmetic Mean | Linear Std Dev | Directional Circular Mean | Directional Circular Std Dev |
|---|---|---|---|---|
| **`charging_start_hour`** | 17.39h (17:23) | 7.57h | **21.79h (21:47)** | **3.85h** |
| **`unplug_hour` (Target)**| 9.37h (09:22) | 3.60h | **8.68h (08:41)** | **3.58h** |

*Notice that the linear mean for start hour (17.39h) is heavily biased toward late afternoon because it averages late-night sessions (e.g. 23:00) with post-midnight sessions (e.g. 02:00) linearly $((23 + 2)/2 = 12.5)$, whereas circular vector averaging correctly identifies the nighttime center of mass at **21.79h (21:47)**.*

### Recommended Cyclical Feature Transformation

For future ML modeling, all time-of-day features must be transformed into continuous circular 2D coordinates:

$$x_{\sin} = \sin\left(\frac{2\pi \times \text{hour}}{24}\right), \quad x_{\cos} = \cos\left(\frac{2\pi \times \text{hour}}{24}\right)$$

This preserves Euclidean distance: points 1 hour apart maintain identical spatial distances regardless of whether they span across midnight or occur at noon.

---

## 6. Weekday vs. Weekend Behavioral Shifts

Human charging routines are heavily dictated by the working week. On weekends, alarm clocks are often turned off, leading to delayed wake-up and unplug times.

### Profile Weekend Sensitivity

| Profile Type | Weekday Mean Unplug Hour | Weekend Mean Unplug Hour | Weekend Shift ($\Delta t$) |
|---|---|---|---|
| **`WEEKEND_SHIFTER`** | **7.39h (07:23)** | **10.44h (10:26)** | **+3.05 hours (+183 min)** |
| **`IRREGULAR`** | 8.45h (08:27) | 9.39h (09:23) | +0.94 hours (+56 min) |
| **`REGULAR_OVERNIGHT`** | 7.59h (07:35) | 8.22h (08:13) | +0.63 hours (+38 min) |
| **`LATE_NIGHT_USER`** | 9.76h (09:45) | 10.21h (10:12) | +0.44 hours (+27 min) |
| **`HEAVY_USER`** | 10.08h (10:05) | 10.50h (10:30) | +0.41 hours (+25 min) |
| **`FREQUENT_TOPUP`** | 10.61h (10:36) | 11.01h (11:00) | +0.40 hours (+24 min) |

![Weekday vs Weekend Unplug Hour](analysis/06_weekday_vs_weekend_unplug.png)

`WEEKEND_SHIFTER` exhibits an unmistakable **+3.05 hour shift**. Models that include `is_weekend` or categorical day-of-week will easily capture this shift, whereas models lacking calendar awareness will produce systematic 3-hour underpredictions on Saturday and Sunday mornings.

---

## 7. Screen Usage Analysis

Daily screen usage reflects user workload and device reliance.

- **Global Mean Screen Time**: 351.3 minutes/day (~5.85 hours/day).
- **Profile Variation**:
  - `HEAVY_USER`: Mean = 460.9 min/day (IQR: 420 – 510 min).
  - `LATE_NIGHT_USER`: Mean = 371.5 min/day.
  - `REGULAR_OVERNIGHT`: Mean = 222.2 min/day.
  - `FREQUENT_TOPUP`: Mean = 191.9 min/day.

![Screen Usage by Profile](analysis/05_screen_usage_by_profile.png)

### Screen Usage vs. Plug-in SoC Correlation

An inverse relationship exists between daily screen usage and plug-in battery percentage ($r = -0.49$). High screen consumption depletes the battery faster, forcing users to plug in at lower battery percentages ($10\% - 25\%$).

![Start SoC vs Screen Usage](analysis/09_start_soc_vs_screen_usage.png)

### Crucial Feature Distinction: Current Day vs. Previous Day

- `screen_usage_minutes`: Represents the **total cumulative screen-on time for the entire calendar day**. At 13:00 or 22:00 when a charging session begins, the device OS does not yet know how much total screen time will accumulate by 23:59:59. Using this current-day total constitutes subtle future data leakage.
- `previous_day_usage_minutes`: Screen time from day $t-1$. This value is **100% complete, immutable, and fully known** when the user plugs in. It serves as an effective, leakage-free proxy for user intensity.

---

## 8. Battery State of Charge (SoC) Analysis

Battery SoC at plug-in provides strong context on user intent:

- **Start SoC Distribution**:
  - Global Mean = 41.01%, Median = 38.30%, Range = 1.0% to 80.0%.
  - When users plug in below 20%, they are experiencing battery depletion anxiety.
  - When users plug in above 60%, they are performing habitual top-ups (e.g., before leaving home or desk).

![Start SoC Distribution](analysis/04_start_soc_distribution.png)

### End Battery Percent: Direct Data Leakage

- `end_battery_percent`: Mean = 92.51%, Range = 40.0% to 100.0%.
- In overnight charging, batteries sit at 95%–100% for hours. In brief daytime charges, users unplug when reaching 60%–75%.
- **Verdict**: `end_battery_percent` is recorded **only after the cable is disconnected**. Under no circumstances can it be used as an input feature to predict unplug time.

---

## 9. Battery Temperature Analysis

Thermal dynamics directly impact battery health. High temperature accelerated SEI layer growth and lithium plating.

### Temperature by Charger Classification

| Charger Classification | Power Range | Session Count | Mean Temperature | Std Dev | Min Temp | Max Temp |
|---|---|---|---|---|---|---|
| **`slow`** | 5W – 10W (Standard 5V/1A USB) | 571 (7.4%) | **28.18°C** | 1.95°C | 24.0°C | 35.2°C |
| **`standard`** | 15W – 20W (Standard Fast/QC) | 4,400 (56.9%) | **29.81°C** | 1.83°C | 24.0°C | 36.4°C |
| **`fast`** | 30W – 65W+ (USB-PD High Power) | 2,764 (35.7%) | **33.32°C** | 1.90°C | 26.7°C | 39.5°C |

![Temperature by Charger](analysis/07_temperature_by_charger.png)

### Temperature as an Input Feature

- In the synthetic dataset, `average_temperature` represents the mean temperature **across the entire duration** of the charging session. Because thermal elevation accumulates over the course of charging, the full session average is unavailable at plug-in time (post-event information).
- In a real device deployment, the system can measure the **instantaneous temperature at plug-in ($t_0$)**, but not the session-long average. Therefore, `average_temperature` in this dataset must be excluded or treated as an approximation of ambient/initial temperature.

---

## 10. Charger Type & Duration Analysis

### Charger Type Distribution

- **Standard**: 56.9% (4,400 sessions)
- **Fast**: 35.7% (2,764 sessions)
- **Slow**: 7.4% (571 sessions)

### Charging Duration: The Ultimate Target Leakage

The dataset contains `charging_duration_minutes`:
- By definition: $\text{charging\_duration\_minutes} = \frac{\text{unplug\_time} - \text{charging\_start\_time}}{60\text{ seconds}}$.
- If an ML algorithm has access to `charging_duration_minutes` and `charging_start_time`, it can solve for `unplug_time` via trivial arithmetic with **$R^2 = 1.000$ and MSE = 0.000**.
- In our correlation analysis, `charging_duration_minutes` exhibits a Pearson correlation of $r = -0.754$ with `unplug_hour` because overnight charges last 480–600 minutes and unplug in the early morning (07:00), while daytime charges last 45–60 minutes and unplug in the afternoon (14:00).
- **Rule**: `charging_duration_minutes` is **pure data leakage** when predicting `unplug_time`. It must be permanently banned from feature sets.

---

## 11. Data Leakage & Feature Correlation Analysis

![Feature Correlation Matrix](analysis/11_feature_correlation_matrix.png)

The correlation matrix cleanly separates variables into two distinct operational domains:
1. **Pre-Event Domain (Safe)**: Start hour, start SoC, weekday, weekend flag, previous day usage. These show moderate, realistic correlations with user behavior without mathematical leakage.
2. **Post-Event Domain (Leaking)**: End SoC, duration minutes, session average temperature, and current-day final screen usage. These variables correlate strongly with unplug time precisely because they are generated by or during the charging event itself.

---

## 12. Complete Feature Availability & Leakage Classification Table

This table classifies every single column in the dataset according to the strict 5-tier classification framework:
- **A. SAFE AT PREDICTION TIME**: Information realistically accessible when the user connects the charger ($t_0$).
- **B. HISTORICAL / DERIVED BUT SAFE**: Information aggregated strictly from previous, completed sessions prior to $t_0$.
- **C. TARGET**: The variable to be predicted.
- **D. DATA LEAKAGE / POST-EVENT INFORMATION**: Information unavailable until the charging session finishes.
- **E. SIMULATION-ONLY INFORMATION**: Synthetic ground-truth labels that do not exist on physical consumer devices.

| Feature Name | Available at $t_0$? | Classification Tier | Leakage? | Include in ML? | Technical Rationale |
|---|---|---|---|---|---|
| **`user_id`** | **Yes** | A (Safe) | None | **Yes** | Known device owner identifier; used to query user-specific historical baselines. |
| **`date`** | **Yes** | A (Safe) | None | **Yes** | System clock date when charging starts. |
| **`charging_start_time`** | **Yes** | A (Safe) | None | **Yes** | Exact timestamp when charging begins ($t_0$). Base reference point for prediction. |
| **`charging_start_hour`** | **Yes** | A (Safe) | None | **Yes** (as $\sin$/$\cos$) | Decimal hour extracted from $t_0$. Primary temporal signal. |
| **`start_battery_percent`**| **Yes** | A (Safe) | None | **Yes** | Instantaneous battery level queried from BatteryManager API at $t_0$. |
| **`charger_type`** | **Yes** | A (Safe) | None | **Yes** (One-hot) | Hardware power profile negotiated via USB-PD / QC handshake at connection. |
| **`weekday`** | **Yes** | A (Safe) | None | **Yes** | Calendar day of the week (0–6) derived from system clock at $t_0$. |
| **`is_weekend`** | **Yes** | A (Safe) | None | **Yes** | Binary weekend indicator derived from calendar at $t_0$. |
| **`previous_day_usage_minutes`** | **Yes** | A (Safe) | None | **Yes** | Immutable historical screen time from day $t-1$. Stored locally in OS battery stats. |
| **`unplug_time`** | **No** | C (Target) | Target | **TARGET** | Primary ground-truth prediction target. |
| **`unplug_hour`** | **No** | C (Target) | Target | **TARGET** | Target variable in decimal hours (0.00 – 24.00). |
| **`end_battery_percent`** | **No** | D (Post-Event) | **DIRECT LEAKAGE**| **NO** | Only known after the user unplugs the device. |
| **`charging_duration_minutes`**| **No** | D (Post-Event) | **DIRECT LEAKAGE**| **NO** | Derived directly from $\text{unplug\_time} - \text{start\_time}$. Complete target leakage. |
| **`average_temperature`** | **No** | D (Post-Event) | **POST-EVENT LEAKAGE**| **NO** | In dataset, this is the mean across the whole session. At $t_0$, only $T_0$ is known. |
| **`screen_usage_minutes`** | **No** | D (Post-Event) | **POST-EVENT LEAKAGE**| **NO** | Total cumulative screen time for the full day. Not finalized until 23:59:59. |
| **`profile_type`** | **No** | E (Simulation-Only) | **SYNTHETIC CHEATING** | **NO** | Ground-truth simulation label. Real OS devices have no such label pre-assigned. |
| **`session_id`** | **Yes** | Administrative | None | **NO** | Arbitrary unique string identifier with zero predictive capacity. |

---

## 13. Recommended ML Feature Engineering Pipeline

Based on the empirical findings of this EDA, the following feature set is recommended for the upcoming ML baseline modeling phase:

### 1. Instantaneous Session Features (Available at $t_0$)
- **`start_hour_sin`**: $\sin\left(\frac{2\pi \times \text{charging\_start\_hour}}{24}\right)$
- **`start_hour_cos`**: $\cos\left(\frac{2\pi \times \text{charging\_start\_hour}}{24}\right)$
- **`start_battery_percent`**: Continuous (0 – 100%)
- **`is_weekend`**: Binary (0 or 1)
- **`weekday_sin`**: $\sin\left(\frac{2\pi \times \text{weekday}}{7}\right)$
- **`weekday_cos`**: $\cos\left(\frac{2\pi \times \text{weekday}}{7}\right)$
- **`charger_is_fast`**: Binary flag
- **`charger_is_slow`**: Binary flag
- **`previous_day_usage_minutes`**: Continuous log-scaled screen minutes

### 2. Historical User Features (Computed Strictly from Past Sessions)
To personalize predictions for each `user_id` without leaking future sessions:
- **`user_hist_unplug_circ_mean`**: Circular mean of unplug hour across the user's prior $K$ completed sessions.
- **`user_hist_unplug_circ_std`**: Circular standard deviation of unplug hour across prior sessions (captures individual routine strength).
- **`user_hist_weekday_unplug_mean`**: Day-specific historical circular mean (vital for capturing Weekend Shifter users).
- **`user_hist_weekend_unplug_mean`**: Weekend-specific historical circular mean.
- **`user_prior_session_count`**: Total completed sessions for cold-start detection.

---

## 14. Features Strictly Excluded from Machine Learning

| Excluded Feature | Reason for Exclusion | Consequence if Included |
|---|---|---|
| **`charging_duration_minutes`** | Mathematical target equivalent ($\text{duration} = \text{unplug} - \text{start}$). | 100% trivial cheating; model fails completely in production. |
| **`end_battery_percent`** | Post-event battery level recorded at unplug time. | False correlation with duration and target; unavailable at $t_0$. |
| **`average_temperature`** | Session-wide temperature average across hours of charging. | Post-event thermal integration leakage. |
| **`screen_usage_minutes`** | Cumulative daily screen time finalized at midnight. | Future information leakage for daytime and early evening sessions. |
| **`profile_type`** | Synthetic simulation persona label. | Model memorizes synthetic cluster labels that real phones never have. |
| **`session_id`** | Arbitrary index key. | High cardinality noise / overfitting risk. |

---

## 15. Dataset Limitations

As with any synthetic dataset, several inherent limitations must be considered before deploying models into physical consumer devices:

1. **Gaussian Simplicity**: Synthetic habits were generated using Gaussian perturbations around persona centroids. Real human behavior features heavy-tailed anomalies, unexpected late nights, flights, insomnia, and spontaneous travel that standard normal distributions underestimate.
2. **Static Personas**: In this dataset, a user assigned to `WEEKEND_SHIFTER` exhibits that pattern consistently across all 60 days. In reality, human habits evolve over time due to job changes, semester breaks, or lifestyle adjustments (concept drift).
3. **Thermal Model Approximations**: Thermal behavior was simulated using charger-dependent mean values. Real-world device thermal profiles depend on ambient room temperature, device casing materials, active background processing, and screen brightness during charging.
4. **Synthetic Accuracy vs. Real-World Expectations**: High baseline model accuracy on this synthetic dataset indicates that the ML algorithms are correctly recovering the underlying behavioral equations. It does **not** guarantee equivalent accuracy on noisy, uncontrolled real-world telemetry. Real anonymized charging logs should be incorporated in future validation phases.

---

## 16. Conclusion & Readiness Assessment

### Summary of Major Findings

1. **Diurnal Predictability**: 73.9% of charging sessions represent overnight routines. For 59% of users, overnight unplug times have a circular standard deviation under 45 minutes, confirming that personalized smart charging is mathematically viable for the majority of the population.
2. **Weekend Sensitivity**: Weekend Shifters sleep in by **+3.05 hours** on Saturdays and Sundays. Temporal calendar awareness is an indispensable predictor.
3. **Data Leakage Risk**: Four columns (`charging_duration_minutes`, `end_battery_percent`, `average_temperature`, `screen_usage_minutes`) represent post-event information. Restricting models strictly to pre-event signals and rolling historical user statistics guarantees valid, real-world deployability.

### Primary Question Answered

> **"Which information can genuinely be known at the moment the system predicts expected unplug time?"**
>
> At the exact moment charging begins ($t_0$):
> 1. **Device Clock & Calendar**: Current start timestamp, fractional hour of day, day of week, weekend indicator.
> 2. **Instantaneous Battery State**: Starting battery percentage (SoC), instantaneous plug-in temperature, charging hardware profile (negotiated charger type / wattage).
> 3. **Historical Telemetry (Pre-Event)**: Previous day's total screen usage, and historical aggregations (circular mean unplug hour, variance, weekday vs. weekend averages) computed exclusively from the user's **past, completed charging sessions**.
>
> All session durations, end battery states, session-wide temperatures, and future screen times are **strictly unknown** at $t_0$.

### Phase Readiness Declaration

The Exploratory Data Analysis and Feature / Data Leakage Analysis phase is **100% complete**. All 11 publication-grade visualizations have been generated and validated. The project architecture, database layer, REST backend, test suite, and feature definitions are fully aligned and **ready for Phase 5: Baseline Machine Learning Model Development**.
