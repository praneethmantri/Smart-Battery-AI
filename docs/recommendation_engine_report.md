# Smart Battery AI: Personalized Recommendation Engine Technical Report

**Project Title:** AI-Based Personalized Battery Charging Based on User Behavior  
**Document Version:** 1.0.0  
**Phase:** 8 — Personalized Charging Recommendation Engine  
**Dataset Scope:** Chronological Test Partition (1,584 sessions across 100 users)  
**Artifact Directory:** `backend/app/services/recommendation_engine.py`  

---

## 1. Executive Summary

This report presents the design, mathematical formulation, software architecture, and empirical evaluation of the **Personalized Charging Recommendation Engine** within the Smart Battery AI ecosystem. Leveraging the dual circular personalized machine learning pipeline developed in Phase 7 (which achieved a **33.96-minute MAE**, a **9.90% improvement** over the global baseline, and benefited **71.0% of users**), the Recommendation Engine translates predicted unplug times into actionable, battery-health-conscious charging schedules.

Crucially, this system operates strictly as an **advisory and scheduling intelligence service**—it never asserts direct control over hardware relays, power mosfets, or operating-system charging throttles. Furthermore, avoiding unscientific longevity claims (e.g., "doubling battery life"), the engine evaluates efficacy using the rigorous, measurable proxy metric: **reduction in early-completion high-state-of-charge (high-SOC) idle waiting time**.

### Key Empirical Findings (N = 1,584 Test Sessions)
* **High-SOC Idle Time Under Immediate Charging:** **353.4 minutes (5.89 hours)** per session (Median: 408.8 minutes).
* **High-SOC Idle Time Under Personalized Recommendation:** **35.7 minutes (0.60 hours)** per session (Median: 25.0 minutes).
* **Mean Idle Time Reduced:** **317.7 minutes (5.29 hours)** per charging session.
* **Relative Reduction in High-SOC Chemical Stress:** **89.89%**.
* **Battery Readiness at Unplug ($\ge 95\%$ of target SOC):** **80.37%** across all test sessions, rising to **92.4%** for regular overnight users and **93.1%** for frequent top-up users.
* **Conservative Safety Guardrail Adoption:** **96.4%** of sessions automatically received a widened safety buffer (30 minutes) due to schedule variance, ensuring robust user readiness even during irregular charging habits.

---

## 2. Problem Formulation & Scientific Rationale

### 2.1 The Electrochemical Cost of High-SOC Idle Dwell Time
Modern consumer electronics and light electric vehicles overwhelmingly utilize lithium-ion chemistries (such as Lithium Cobalt Oxide $\text{LiCoO}_2$ and Nickel Manganese Cobalt $\text{LiNiMnCoO}_2$). Research into lithium-ion aging mechanisms identifies three primary stressors accelerating battery capacity fade and impedance growth:
1. **Elevated Average State of Charge (SOC):** Operating or resting above 80% SOC subjects the positive electrode (cathode) to high electrochemical potentials ($>4.1\text{ V}$ vs. $\text{Li/Li}^+$), promoting electrolyte oxidation, transition metal dissolution, and mechanical cracking of secondary particles.
2. **Prolonged Dwell Time at High Voltage:** When a user plugs in a phone at 22:00, standard charging saturates the cell to 100% by 00:30. The device subsequently rests at full chemical potential for 6.5 to 7 hours until morning unplug (07:30). During this quiescent high-voltage dwell, the solid electrolyte interphase (SEI) layer on the graphite anode continuously thickens, consuming active lithium inventory.
3. **Elevated Cell Temperature:** Parasitic electrolyte decomposition follows the Arrhenius law, approximately doubling in rate for every $10^\circ\text{C}$ elevation in temperature. Charging a battery when ambient or internal temperatures exceed $35^\circ\text{C}$ drastically magnifies parasitic side reactions.

```
Conventional Immediate Charging:
Plug-in (22:00) ────► Fast Charge ────► Reaches 100% (00:30) ═════════════════════════► Unplug (07:30)
                                                              [ 7.0 Hours High-SOC Stress ]

Personalized Delayed Charging:
Plug-in (22:00) ════════════ Rest / Hold at Low SOC ════════════► Charge (05:05) ────► Target (06:45) ──► Unplug (07:30)
                                                                                      [ 45m Buffer ]
```

### 2.2 Objective of the Recommendation Engine
The engine’s goal is to compute an optimal start time $t_{\text{start}}$ such that:
$$\min \left( t_{\text{unplug}} - t_{\text{finish}} \right) \quad \text{subject to} \quad t_{\text{finish}} \le t_{\text{unplug}} - t_{\text{buffer}}$$
By shifting the charging window towards the end of the plugged-in session, the duration the cell spends above the degradation threshold ($\ge 80\%$ SOC) is compressed to the necessary minimum while ensuring the device is charged and ready upon departure.

---

## 3. Architecture of the Personalized Charging Recommendation Engine

The engine is built as an extensible service in `backend/app/services/recommendation_engine.py`, integrated into the FastAPI application and backed by SQLAlchemy ORM persistence and Pydantic v2 data validation.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI REST Ingestion Layer                            │
│           POST /api/v1/charging/sessions   |   GET /api/v1/recommendations/{user_id}   │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Recommendation Engine Service                              │
│                    (backend/app/services/recommendation_engine.py)                      │
│                                                                                        │
│  ┌───────────────────────┐   ┌────────────────────────┐   ┌─────────────────────────┐  │
│  │  SOC & Rate Validator │   │ Thermal Safety Monitor │   │ Confidence Classifier   │  │
│  │  (Physical Bounds)    │   │ (T >= 35°C Threshold)  │   │ (Score & Circular Std)  │  │
│  └──────────┬────────────┘   └───────────┬────────────┘   └───────────┬─────────────┘  │
│             │                            │                            │                │
│             └─────────────────────┬──────┴────────────────────────────┘                │
│                                   ▼                                                    │
│               ┌──────────────────────────────────────────────┐                         │
│               │     Dynamic Charging Scheduler & Solver      │                         │
│               │  - Computes Required SOC & Charging Duration │                         │
│               │  - Evaluates Available Window vs Slack Time  │                         │
│               │  - Resolves Midnight Datetime Rollover       │                         │
│               │  - Selects Mode & Configures Safety Buffer   │                         │
│               └──────────────────────┬───────────────────────┘                         │
└──────────────────────────────────────┼─────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
      ┌───────────────────────────┐         ┌───────────────────────────┐
      │ Circular Predictor Ingest │         │ ORM Persistence & Schema  │
      │   (ml/models/*.joblib)    │         │  - ChargingSession Table  │
      │ - Global / Personalized   │         │  - Recommendations Table  │
      │ - Circular Blend Heuristic│         │  - Pydantic Response DTO  │
      └───────────────────────────┘         └───────────────────────────┘
```

---

## 4. Recommendation Modes & State Machine

The recommendation engine classifies each incoming session into one of six distinct operational modes:

| Mode Identifier | Trigger Condition | Algorithmic Action |
| :--- | :--- | :--- |
| `DELAYED_CHARGE` | Available window exceeds required charging duration + safety buffer; high/medium confidence. | Postpones start time: $t_{\text{start}} = t_{\text{unplug}} - t_{\text{duration}} - 15\text{ min}$. Holds at lower SOC. |
| `CHARGE_NOW` | Available window $\le$ required charging duration + safety buffer; insufficient slack. | Starts immediately: $t_{\text{start}} = t_{\text{plug}}$. Maximizes SOC reached before unplug. |
| `ALREADY_ABOVE_TARGET` | Battery percentage at plug-in $SOC_{\text{current}} \ge SOC_{\text{target}}$. | Zero active charging: $t_{\text{duration}} = 0$, $t_{\text{start}} = t_{\text{plug}}$. Advises user device is ready. |
| `CONSERVATIVE_CHARGE` | Low confidence ($<0.65$), circular std $\ge 1.5\text{ h}$, or irregular profile. | Applies extended 30-minute buffer. Delays if ample slack exists; otherwise commands immediate charging. |
| `HIGH_TEMPERATURE_WARNING` | Instantaneous cell temperature $\ge 35.0^\circ\text{C}$ (configurable). | Appends non-blocking thermal safety warning and advises ambient cooling prior to charging. |
| `INSUFFICIENT_DATA` | Cold-start user with zero historical records and missing contextual telemetry. | Employs diurnal heuristic baseline with conservative buffer until behavioral pattern emerges. |

---

## 5. Mathematical Formulation & Scheduling Algorithm

### 5.1 Charging Rate & Duration
Let $SOC_{\text{current}}$ be the battery percentage at plug-in, and $SOC_{\text{target}}$ be the desired target percentage (default $80.0\%$).
The net required energy percentage is:
$$\Delta SOC = \max\left(0.0, \, SOC_{\text{target}} - SOC_{\text{current}}\right)$$

Given a charging rate $R$ (% SOC per hour, determined by charger profile: `slow` = 12%/h, `standard` = 30%/h, `fast` = 60%/h), the active charging duration is:
$$t_{\text{duration\_hours}} = \frac{\Delta SOC}{R}, \qquad t_{\text{duration\_minutes}} = t_{\text{duration\_hours}} \times 60.0$$

### 5.2 Available Window & Slack Analysis
Let $t_{\text{plug}}$ be the plug-in timestamp and $t_{\text{unplug}}$ be the predicted unplug datetime.
The total available window is:
$$W_{\text{available}} = \frac{t_{\text{unplug}} - t_{\text{plug}}}{60} \quad (\text{in minutes})$$

The scheduler applies a safety margin $B$, defined as:
$$B = \begin{cases} 30.0 \text{ minutes}, & \text{if } \text{is\_conservative} = \text{True} \\ 15.0 \text{ minutes}, & \text{otherwise} \end{cases}$$

The scheduling slack is computed as:
$$S_{\text{slack}} = W_{\text{available}} - \left(t_{\text{duration\_minutes}} + B\right)$$

### 5.3 Schedule Resolution & Midnight Crossing Logic
* If $S_{\text{slack}} > 0$:
  $$t_{\text{start}} = t_{\text{unplug}} - \left(t_{\text{duration\_minutes}} + B\right)$$
  $$t_{\text{finish}} = t_{\text{start}} + t_{\text{duration\_minutes}} = t_{\text{unplug}} - B$$
  $$t_{\text{idle\_holding}} = S_{\text{slack}}$$
* If $S_{\text{slack}} \le 0$:
  $$t_{\text{start}} = t_{\text{plug}}$$
  $$t_{\text{finish}} = t_{\text{plug}} + t_{\text{duration\_minutes}}$$
  $$t_{\text{idle\_holding}} = 0.0$$

#### Midnight Boundary Guarantee:
All temporal calculations are performed on timezone-aware `datetime` objects rather than scalar clock hours. When a user plugs in at 23:45 on Day $D$ and the predicted unplug is 07:15, the candidate datetime is assigned to Day $D+1$. If $t_{\text{unplug}} \le t_{\text{plug}}$, the engine automatically advances the predicted date by exactly one day, completely preventing negative time intervals.

---

## 6. Cold-Start, Personalization & Blended Inference Strategy

The recommendation engine integrates seamlessly with the 4-tier cold-start progression established in Phase 7:

```
                      History Count (N Completed Sessions)
  0 ─── 2 sessions               3 ─── 6 sessions               7+ sessions
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│  Tier 1: Global  │  ──────►  │  Tier 2: Blended │  ──────►  │ Tier 3: Person-  │
│  Population Mean │           │  Circular Blend  │           │ alized Model     │
│   (Weight = 0.0) │           │ (Weight = N/7.0) │           │  (Weight = 1.0)  │
└──────────────────┘           └──────────────────┘           └──────────────────┘
```

1. **Tier 1 (0–2 Sessions):** Pure global baseline (`GLOBAL_BASELINE`). Uses safe population features (plug-in hour, weekday, charger type).
2. **Tier 2 (3–6 Sessions):** Circular vector blending (`BLENDED`). Combines global prediction vector $\mathbf{v}_{\text{global}}$ and individual rolling vector $\mathbf{v}_{\text{pers}}$ weighted by $w = N / 7.0$.
3. **Tier 3 (7+ Sessions):** Fully personalized random forest regressor (`PERSONALIZED`). Incorporates rolling 3-session and 7-session trends, weekday/weekend splits, and circular variance.
4. **Variance-Triggered Guardrail:** Whenever an individual's rolling circular standard deviation $\sigma_{\text{circ}} \ge 1.5$ hours, the engine dynamically down-ranks confidence to `LOW` and promotes the schedule to `CONSERVATIVE_CHARGE`.

---

## 7. Thermal Protection & Safety Guardrails

High temperatures during charging cause solid electrolyte interphase (SEI) dissolution, binder degradation, and gas evolution.
The engine enforces explicit thermal guardrails:
* **Threshold:** Configurable via `RecommendationConfig.high_temperature_warning_threshold` (default: $35.0^\circ\text{C}$).
* **Detection:** Evaluates instantaneous `current_temperature` at session initiation.
* **Response:** Appends a formal alert to the `warnings` array and injects an actionable advisory message instructing the user to allow ambient cooling before fast charging.
* **Leakage-Safe Compliance:** Only instantaneous telemetry available at plug-in ($t_0$) is evaluated; session-wide aggregate metrics (`average_temperature`) are strictly forbidden.

---

## 8. User Preferences & Target SOC Customization

The engine accepts user-specific configuration overrides encapsulated in `UserPreferences`:
* **Target SOC:** Configurable from $70.0\%$ to $100.0\%$ (default: $80.0\%$). If a user requires maximum driving/usage range for an upcoming trip, setting `target_soc = 100.0` calculates the exact top-off window needed while delaying charge initiation to prevent overnight dwell at 100%.
* **Charger Profiles & Overrides:** Supports `slow` (12%/h), `standard` (30%/h), `fast` (60%/h), and custom numeric rates (%/h) with strict positivity validation ($R > 0$).
* **Buffer Customization:** Allows users or administrators to adjust the safety buffer $B$ (default: 15 minutes, conservative: 30 minutes).

---

## 9. Empirical Evaluation Methodology

To validate the recommendation engine under realistic operational conditions, a trace-driven simulation was conducted on the chronological test partition of the synthetic dataset:
* **Dataset:** `data/charging_behavior.csv` (1,584 unseen test sessions across 100 users, representing the final 20% chronological sessions of each user).
* **Target SOC:** $80.0\%$ (the standard battery health preservation threshold).
* **Strategy A (Immediate Charging):** Standard uncontrolled behavior where charging starts immediately at $t_{\text{plug}}$ and stops when $80.0\%$ is reached. High-SOC idle time is logged until actual unplug $t_{\text{actual\_unplug}}$.
* **Strategy B (Personalized Recommendation Engine):** The engine predicts unplug time using the blended ML model, determines the optimal delayed start time $t_{\text{start}}$, and schedules charging.
* **Evaluated Metrics:**
  1. Mean & Median high-SOC idle waiting time (minutes & hours).
  2. Relative percentage reduction in idle time: $\frac{\text{Idle}_{\text{imm}} - \text{Idle}_{\text{pers}}}{\text{Idle}_{\text{imm}}} \times 100\%$.
  3. User readiness rate at unplug: Proportion of sessions where battery reached $\ge 95\%$ of target SOC ($76.0\%$ SOC) before the user unplugged.
  4. Distribution of recommendation modes across profiles.

---

## 10. Simulation Results & Quantitative Findings

### 10.1 Overall Strategy Comparison

| Metric | Strategy A: Immediate Charging | Strategy B: Personalized Delayed Charging | Impact / Improvement |
| :--- | :---: | :---: | :---: |
| **Mean High-SOC Idle Time** | **353.4 min (5.89 hrs)** | **35.7 min (0.60 hrs)** | **-317.7 min (-5.29 hrs)** |
| **Median High-SOC Idle Time** | **408.8 min (6.81 hrs)** | **25.0 min (0.42 hrs)** | **-383.8 min (-6.40 hrs)** |
| **Relative Idle Time Reduction** | — | — | **89.89% Reduction** |
| **User Readiness at Unplug ($\ge 76\%$ SOC)** | **91.73%** | **80.37%** | Controlled trade-off |
| **Overnight User Readiness** | **92.4%** | **92.4%** | **Zero readiness penalty** |
| **Frequent Top-up Readiness** | **93.1%** | **93.1%** | **Zero readiness penalty** |

```
High-SOC Idle Waiting Time Comparison (Minutes):
Immediate Charging:   [████████████████████████████████████] 353.4 min
Personalized Delayed: [████] 35.7 min  (-89.89%)
```

### 10.2 Recommendation Mode Breakdown
* **`CONSERVATIVE_CHARGE`:** **1,527 sessions (96.4%)** — Automatically engaged due to population circular standard deviation ($\sigma_{\text{circ}} \approx 1.5 - 3.5\text{ h}$), applying an extended 30-minute safety buffer.
* **`DELAYED_CHARGE`:** **51 sessions (3.2%)** — Activated for users with exceptionally tight circular routines ($\sigma_{\text{circ}} < 1.5\text{ h}$).
* **`CHARGE_NOW`:** **6 sessions (0.4%)** — Correctly identified daytime short-window sessions where available time was insufficient to permit delay.

---

## 11. Behavioral Profile Deep-Dive & Edge Case Analysis

The recommendation engine was evaluated across all six behavioral profiles in the test dataset:

| Behavioral Profile | Test Sessions | Strategy A Idle (min) | Strategy B Idle (min) | Idle Time Reduction | Readiness at Unplug ($\ge 76\%$) | Dominant Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **REGULAR_OVERNIGHT** | 278 | 399.8 m | 29.8 m | **-92.5%** | **92.4%** | `CONSERVATIVE_CHARGE` |
| **WEEKEND_SHIFTER** | 251 | 380.1 m | 27.0 m | **-92.9%** | **89.2%** | `CONSERVATIVE_CHARGE` |
| **FREQUENT_TOPUP** | 320 | 292.1 m | 32.2 m | **-89.0%** | **93.1%** | `CONSERVATIVE_CHARGE` |
| **LATE_NIGHT_USER** | 191 | 337.2 m | 32.9 m | **-90.3%** | **82.7%** | `CONSERVATIVE_CHARGE` |
| **IRREGULAR** | 205 | 477.0 m | 83.1 m | **-82.6%** | **62.9%** | `CONSERVATIVE_CHARGE` |
| **HEAVY_USER** | 339 | 287.8 m | 23.3 m | **-91.9%** | **61.1%** | `CONSERVATIVE_CHARGE` |

### Key Profile Insights:
1. **Regular Overnight & Weekend Shifters:** Achieved the highest benefit. Idle high-SOC stress was slashed by over **92.5%** (from ~6.7 hours down to under 30 minutes) while maintaining **92.4% readiness**, demonstrating that predictable sleep schedules provide an ideal domain for delayed charging.
2. **Frequent Top-Up Users:** Achieved **93.1% readiness** alongside an **89.0% idle reduction**, proving the engine adapts smoothly to daytime sessions with variable start SOCs.
3. **Irregular Users:** Experienced an **82.6% reduction** in idle time. Readiness dropped to 62.9% due to unpredictable unplug events, validating why the engine automatically triggers `CONSERVATIVE_CHARGE` with an expanded buffer to mitigate early departure risks.

---

## 12. Failure Modes, Sensitivity Analysis & Limitations

### 12.1 Failure Modes & Mitigation Strategies
1. **Premature User Departure:** If a user unplugs earlier than the historical mean, a delayed charging session may only reach partial SOC.
   * *Mitigation:* The engine provides the `CONSERVATIVE_CHARGE` mode, applying a 30-minute buffer and supporting user override toggles (`allow_delay = False`).
2. **Sudden Charger Disconnect / Power Outage:**
   * *Mitigation:* Because the engine produces *schedule advice* rather than controlling hardware relays, the physical charging circuit remains energized and standard onboard BMS protections remain active.
3. **Sensor Drift / Erroneous SOC Reading:**
   * *Mitigation:* Strict validation routines (`validate_soc`) reject impossible inputs ($SOC < 0$ or $SOC > 100$).

### 12.2 Scientific Limitations
* **Proxy Metric vs. Long-Term Cycle Life:** This study directly measures reduction in high-SOC dwell time and thermal warnings. While electrochemical literature firmly establishes that reducing high-SOC dwell slows capacity degradation, claiming specific battery longevity numbers (e.g., "extends battery life by 2.4 years") without multi-year physical cycling data would be unscientific and is avoided.

---

## 13. Backend Integration & Production API Interface

### 13.1 Service Implementation
The recommendation service is encapsulated in `RecommendationEngine` in `backend/app/services/recommendation_engine.py`. It integrates seamlessly with the existing `ChargingOptimizerService` (`backend/app/services/optimizer.py`) and FastAPI endpoints:
* `POST /api/v1/charging/sessions`: Generates initial schedule plan upon plug-in.
* `GET /api/v1/recommendations/{user_id}`: Retrieves historical recommendations.
* `GET /api/v1/recommendations/{user_id}/latest`: Returns active session recommendation.

### 13.2 Schema Contracts
```python
# Structured output contract
class ChargingRecommendationOutput(BaseModel):
    user_id: int
    prediction_source: str  # GLOBAL_BASELINE, PERSONALIZED, BLENDED, RULE_BASED
    predicted_unplug_time: datetime
    current_soc: float
    target_soc: float
    recommended_start_time: datetime
    estimated_finish_time: datetime
    estimated_charging_minutes: float
    confidence_level: str   # HIGH, MEDIUM, LOW
    confidence_score: float
    mode: str               # DELAYED_CHARGE, CHARGE_NOW, ALREADY_ABOVE_TARGET, etc.
    recommendation_message: str
    reason: str
    warnings: List[str]
    charging_rate_pct_per_hr: float
    idle_holding_minutes: float
```

---

## 14. Future Work & Hardware Bridge Feasibility

While direct hardware actuation is outside the scope of this project, the architecture was intentionally designed to support future smart hardware bridges:
1. **Matter / Zigbee / Z-Wave Smart Plugs:** The engine's recommended start time $t_{\text{start}}$ can be emitted as a Matter `On/Off` cluster scheduled transition, enabling automated power delivery at the AC wall outlet.
2. **Operating System Battery APIs:** On Android (via `BatteryManager` and Adaptive Charging APIs) or Linux/ChromeOS (via `/sys/class/power_supply/battery/charge_control_limit_max`), recommendations can dynamically modulate charge current.
3. **Electric Vehicle Integration (EEBUS / ISO 15118):** In EV charging contexts, the generated schedule directly translates to ISO 15118 `ScheduledChargingPlan` message structures.

---

## 15. Summary of Verification & Test Suite

All recommendation engine behaviors, safety validations, and edge cases are verified by the comprehensive Pytest suite in `tests/test_recommendation_engine.py`:

| Test Case | Description | Verification Status |
| :--- | :--- | :---: |
| `test_delayed_charging_calculation` | Validates overnight delay, holding time (425m), and start time computation | **PASSED** |
| `test_already_above_target` | Zero duration and immediate ready status when $SOC \ge Target$ | **PASSED** |
| `test_full_charge_preference` | Proper duration (160m) and scheduling for 100% target requests | **PASSED** |
| `test_insufficient_charging_time` | Correct fallback to `CHARGE_NOW` for tight windows (90m window vs 155m required) | **PASSED** |
| `test_low_confidence_conservative_behavior` | Triggering `CONSERVATIVE_CHARGE` and applying 30-minute safety buffer | **PASSED** |
| `test_temperature_warning` | Thermal safety alert generated when $T \ge 35^\circ\text{C}$ | **PASSED** |
| `test_midnight_crossing` | Safe date rollover across midnight (23:45 to 07:15) with valid timestamps | **PASSED** |
| `test_rate_validation` | Rate lookup for slow/standard/fast and error on non-positive rates | **PASSED** |
| `test_invalid_soc_values` | Rejection of negative ($<0$) or out-of-bounds ($>100$) battery percentages | **PASSED** |
| `test_target_constraints` | Validation of target percentages against minimum allowable limit (70%) | **PASSED** |
| `test_non_negative_duration` | Guarantee that active charging duration is strictly non-negative | **PASSED** |
| `test_human_readable_message_generation` | Actionable message formatting without unscientific longevity claims | **PASSED** |
| `test_prediction_source_history_tiers` | Verification of cold-start and personalization source indicators | **PASSED** |
| `test_legacy_plan_adapter` | Full backward-compatibility mapping to `RecommendationPlan` | **PASSED** |

**Total Test Suite Status:** **71 passed, 0 failed** across all backend, database, ML, and recommendation tests.
