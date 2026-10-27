# Smart Battery AI - Dataset Documentation

This directory contains simulated user behavioral profiles and longitudinal battery charging records engineered for developing personalized charging prediction algorithms (specifically predicting **expected unplug time**).

---

## 1. Overview of Generated Datasets

### A. `users.csv`
Contains static behavioral preferences and baseline characteristics for 100 simulated smartphone users over 60 simulated days.

| Column | Type | Description | Range / Values |
|---|---|---|---|
| `user_id` | Integer | Unique identifier for each simulated user | 1 to 100 |
| `profile_type` | String | Dominant behavioral archetype | 6 distinct profiles (see Section 2) |
| `typical_weekday_charge_hour` | Float | Base weekday plug-in hour in decimal time | 0.0 to 23.98 (e.g., 22.5 = 10:30 PM) |
| `typical_weekday_unplug_hour` | Float | Base weekday unplug hour in decimal time | 5.0 to 11.0 (e.g., 6.75 = 06:45 AM) |
| `typical_weekend_charge_hour` | Float | Base weekend plug-in hour in decimal time | 0.0 to 23.98 |
| `typical_weekend_unplug_hour` | Float | Base weekend unplug hour in decimal time | 6.0 to 11.5 |
| `baseline_daily_screen_minutes` | Float | Average daily screen-on time in minutes | 180.0 to 620.0 minutes |
| `preferred_charger_type` | String | Most commonly used hardware charger | `slow`, `standard`, `fast` |

---

### B. `charging_behavior.csv`
Contains longitudinal charging sessions ($\ge 7,500$ records) with behavioral temporal patterns, temperature dynamics, and battery depletion correlations.

| Column | Type | Description |
|---|---|---|
| `session_id` | String | Unique session identifier (`sess_000001` to `sess_NNNNNN`) |
| `user_id` | Integer | Foreign reference to `users.csv` (1 to 100) |
| `date` | String | Date of the session (`YYYY-MM-DD`) |
| `charging_start_time` | ISO 8601 String | Exact plug-in timestamp (`YYYY-MM-DDTHH:MM:SS`) |
| `unplug_time` | ISO 8601 String | Exact unplug timestamp (`YYYY-MM-DDTHH:MM:SS`) |
| `charging_start_hour` | Float | Decimal representation of start hour (e.g., 22.5 = 22:30) |
| `unplug_hour` | Float | Decimal representation of unplug hour (e.g., 6.75 = 06:45) |
| `start_battery_percent` | Float | Battery State of Charge (SoC) at plug-in ($0 \le \text{SoC} \le 100$) |
| `end_battery_percent` | Float | Battery State of Charge at unplug ($\text{start} < \text{end} \le 100$) |
| `average_temperature` | Float | Average pack temperature during charge ($24.0^\circ\text{C}$ to $43.0^\circ\text{C}$) |
| `charging_duration_minutes` | Float | Duration device remained plugged in (strictly $> 0$) |
| `charger_type` | String | Charger used: `slow` (5W), `standard` (15W), `fast` (30W+) |
| `screen_usage_minutes` | Float | Daily screen-on time in minutes |
| `weekday` | Integer | Day of week: 0 (Monday) to 6 (Sunday) |
| `is_weekend` | Integer | Binary flag: 1 if Saturday or Sunday, else 0 |
| `previous_day_usage_minutes` | Float | Screen-on time recorded on day $t-1$ |
| `profile_type` | String | User's behavioral charging archetype |

---

## 2. Simulated User Behavior Profiles

Every simulated user is assigned one dominant profile governing their charging and wake routines:

1. **`REGULAR_OVERNIGHT`**
   - **Characteristics**: Highly predictable daily routine. Plugs in roughly 9:30 PM–11:30 PM and unplugs around 6:00 AM–7:30 AM.
   - **Variance**: Very low unplug-time variance ($\sigma \approx 20$ minutes).
   - **Target ML Task**: Baseline high-accuracy prediction benchmark.

2. **`IRREGULAR`**
   - **Characteristics**: Unpredictable shift worker or erratic schedule. Plugs in and unplugs at varying hours.
   - **Variance**: High unplug-time variance ($\sigma > 120$ minutes).
   - **Target ML Task**: Tests algorithm confidence estimation and safe fallback mechanisms.

3. **`HEAVY_USER`**
   - **Characteristics**: Exceptionally high daily screen usage ($> 400$ minutes).
   - **Battery Impact**: Deep discharge states ($5\% - 30\%$ start SoC). Frequent midday top-up sessions ($\approx 55\%$ probability).
   - **Target ML Task**: Tests multi-session daily prediction and higher thermal stress patterns.

4. **`FREQUENT_TOPUP`**
   - **Characteristics**: Range-anxious desk worker. Plugs in multiple times a day at medium SoC ($48\% - 74\%$).
   - **Duration**: Short charging bursts ($30 - 90$ minutes).
   - **Target ML Task**: Distinguishes between quick maintenance charges and overnight full cycles.

5. **`WEEKEND_SHIFTER`**
   - **Characteristics**: Disciplined workday schedule (unplugs $\approx 06:30$ AM), but sleeps in on weekends (unplugs $\approx 09:30$–$10:30$ AM).
   - **Variance**: Pronounced difference between weekday and weekend averages ($+2.5$ to $+3.5$ hours shift).
   - **Target ML Task**: Verifies temporal calendar features (`is_weekend`, `weekday`).

6. **`LATE_NIGHT_USER`**
   - **Characteristics**: Night owl. Plugs in around midnight or later (00:00–02:30 AM) and unplugs later in the morning (08:30–10:30 AM).
   - **Target ML Task**: Verifies cyclic time encoding across the midnight boundary.

---

## 3. Important Modeling Assumptions

1. **Overnight Midnight Crossing**:
   - Sessions starting at 23:00 on Day $D$ and ending at 07:00 on Day $D+1$ are recorded with exact dates and strictly positive duration $(480\text{ mins})$.
2. **Battery Depletion & Screen Usage Coupling**:
   - Higher daily screen-on time directly drives deeper battery discharge before plug-in.
3. **Thermal Dynamics**:
   - Fast chargers generate higher charging temperatures ($+3.5^\circ\text{C}$ to $+5.5^\circ\text{C}$) compared to standard or slow chargers. Heavy simultaneous screen usage adds additional heat.
4. **Clean Data**:
   - The dataset contains zero null/missing values and zero inverted timestamps to provide an uncorrupted benchmark for exploratory analysis.

---

## 4. Limitations of Synthetic Data

1. **Synthetic Noise vs Real Hardware Drift**: Sensor noise in reality is non-Gaussian and includes analog ADC quantization steps and thermistor calibration offsets.
2. **Ambient Weather Influences**: Real smartphone temperatures fluctuate with seasonal ambient room temperature, which is omitted in this behavioral model.
3. **Battery Degradation Over Time**: Over 60 days, real battery capacity fades slightly; this dataset assumes constant nominal battery health to isolate behavioral patterns.
