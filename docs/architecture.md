# System Architecture & Technical Design

## 1. Domain Problem
Lithium-ion batteries in consumer laptops, smartphones, and EVs suffer from two major degradation mechanisms:
1. **High Voltage / High State-of-Charge (SoC) Hold Time**: Leaving a battery at 100% capacity for extended periods (e.g. overnight 7-8 hours) accelerates electrolyte oxidation and SEI (Solid Electrolyte Interphase) layer thickening.
2. **Thermal Stress during High SoC**: Fast charging above 80% increases internal resistance and temperature.

The goal of this system is to intelligently **delay the final top-off charge (80% -> 100%)** until just before the user unplugs their device, based on machine learning predictions of user unplug habits.

---

## 2. Component Architecture

```
+--------------------------------------------------------------------------------+
|                                FRONTEND (React)                                |
|  - View real-time battery status                                               |
|  - Display AI predicted unplug time & charging phases                          |
|  - Historical charging telemetry & degradation insights (Chart.js)             |
+---------------------------------------+----------------------------------------+
                                        | JSON / REST
                                        v
+--------------------------------------------------------------------------------+
|                                BACKEND (FastAPI)                               |
|  [API Layer]           Endpoints: /sessions, /recommendations, /health        |
|  [Service Layer]       OptimizerService, ModelInferenceService                 |
|  [Data Access Layer]   SQLAlchemy ORM (Repository Pattern)                     |
+-------------------+------------------------------------+-----------------------+
                    |                                    |
                    v                                    v
+------------------------------------+ +-----------------------------------------+
|           DATABASE (SQL)           | |         MACHINE LEARNING PIPELINE       |
|  - SQLite (Local development)      | |  - Feature Engineering (cyclic time)    |
|  - PostgreSQL (Production target)  | |  - Random Forest / Gradient Boosting    |
|  - Tables: charging_sessions,      | |  - Joblib artifact serialization        |
|            charging_recommendations| |  - Target: predicted duration / unplug  |
+------------------------------------+ +-----------------------------------------+
```

---

## 3. Data Flow

1. **Session Start**:
   - Device connects to charger.
   - Client sends `POST /api/v1/charging/session` with `start_battery_pct`, `plug_time`, and `user_id`.
2. **Inference & Schedule Generation**:
   - Backend calls `OptimizerService.generate_plan()`.
   - Feature engineering generates features:
     - `hour_of_day_sin`, `hour_of_day_cos` (cyclic temporal encoding)
     - `day_of_week` (0-6)
     - `is_weekend` (binary flag)
     - `rolling_avg_duration_hours` (user's recent session duration)
   - `MLModel.predict_unplug_time()` returns estimated unplug datetime and confidence score.
   - The optimizer divides charging into:
     - **Phase 1 (Active Fast Charge)**: Plug-in until 80% SoC reached.
     - **Phase 2 (Protection Hold)**: Pause or micro-trickle to maintain 80%.
     - **Phase 3 (Scheduled Top-Off)**: Resume to reach 100% ~30 minutes before predicted unplug.
3. **Persist & Respond**:
   - Session & generated recommendation logged in DB.
   - JSON response returned to frontend to render scheduled charging timeline.

---

## 4. Portability & Extensibility
- **Database Portability**: SQLAlchemy abstract dialect usage allows changing `DATABASE_URL` from SQLite (`sqlite:///./data/battery_charging.db`) to PostgreSQL (`postgresql://...`) with zero code alterations.
- **Model Decoupling**: The ML model inference is wrapped behind an abstract predictor class. If the model artifact is missing or untrained, the service falls back to rule-based heuristics without crashing.
