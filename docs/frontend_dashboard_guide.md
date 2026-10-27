# Smart Battery AI - Frontend Dashboard Architecture & User Guide

## 1. Overview & Research Objective

The **Smart Battery AI Frontend Dashboard** is a high-performance, responsive React dashboard built for the college R&D project:

> **"AI-Based Personalized Battery Charging Based on User Behavior"**

The dashboard provides real-time visualization of battery telemetry, historical charging patterns, multi-tier machine learning unplug predictions, and degradation-mitigating charging schedule recommendations.

---

## 2. Technology Stack & Design System

- **Core Framework**: React 18 (`react`, `react-dom`)
- **Bundler & Dev Server**: Vite 5
- **Data Visualization**: Chart.js v4 + `react-chartjs-2`
- **State Management**: React Context API (`AppContext`)
- **Architecture**: Modular Component-Driven, Zero heavy external CSS UI dependencies
- **Design Theme**: Professional Dark Navy & Slate Theme
  - Primary Background: `#0a0f1d` / `#0f172a`
  - Card Surfaces: `#1e293b` with `#334155` borders
  - Primary Accents: Electric Cyan (`#38bdf8`), Blue (`#3b82f6`)
  - Semantic Status: Emerald Green (`#10b981`), Amber (`#f59e0b`), Purple (`#a855f7`), Rose (`#ef4444`)
  - Typography: Clean sans-serif with high contrast (`#f8fafc` text main, `#94a3b8` muted)

---

## 3. Dashboard Architecture & Navigation

The application uses a persistent left navigation sidebar and a top status bar:

### Navigation Structure
1. **Dashboard** (`/`): High-level operational overview, 6 KPI cards, hero recommendation plan, live battery telemetry gauge, and charging trajectory comparison curve.
2. **Charging History** (`/history`): Interactive session log with configurable fetch limits (10/25/50/100), pagination, start vs unplug SoC trend line chart, and summary averages.
3. **AI Prediction** (`/prediction`): Interactive inference console allowing users to test unplug-time predictions with custom SoC, plug-in timestamp, charger hardware, and prior-day usage. Includes multi-tier routing explanation.
4. **Smart Recommendation** (`/recommendation`): Full parameter recommendation solver supporting target SoC limits, 100% full charge toggle, delayed charging toggle, thermal limits, and charging rates. Generates step-by-step visual charging sequences.
5. **Analytics** (`/analytics`): Six Chart.js visualizations including SoC trend, start vs unplug hour comparison, session duration distribution, day-of-week frequency, charger type breakdown, and operating temperature profiles.
6. **Model Evaluation** (`/evaluation`): R&D research benchmark suite comparing Global GBR (37.69m MAE) against Personalized Hybrid RF (33.96m MAE), 71% cohort improvement, behavioral archetype performance, and the 89.89% high-SoC dwell time reduction benchmark.
7. **System Status** (`/status`): Live status monitors for FastAPI backend, SQLAlchemy database, Global model, and Personalized model, along with an end-to-end pipeline diagram and test suite status (83/83 tests green).

---

## 4. Scientific Honesty & R&D Disclaimers

### Dwell-Time Reduction Metric:
- **Baseline Immediate High-SoC Idle Time**: 353.4 minutes
- **Personalized Delayed Charging Idle Time**: 35.7 minutes
- **Dwell Time Reduction**: **89.89%** (317.7 minutes saved per overnight session)
- **Required Scientific Disclaimer**:
  > *"This 89.89% reduction represents a simulated reduction in early high-SOC waiting (dwell) time. Dwell time at high state-of-charge is a well-established theoretical proxy for calendar degradation in lithium-ion batteries, but this metric is an optimization proxy and does NOT make explicit real-world claims of battery longevity elongation or hardware warranty extension."*

### Hardware & Platform Boundaries:
- **Advisory & Scheduling Only**: The system functions strictly in an advisory and predictive scheduling capacity. No direct hardware actuators, kernel drivers, or physical relay switches are triggered.
- **Local Windows Device Battery Integration**:
  - In local development/demonstration mode on Windows, the backend reads physical battery hardware state (percentage, AC plug status, and discharge runtime) via `psutil.sensors_battery()`.
  - The API exposes `GET /api/device-battery` and `GET /api/v1/device-battery`.
  - The React dashboard and recommendation forms automatically prefill using this real-time hardware SoC (e.g. 50% instead of static/mock values), while still allowing user manual override with explicit visual tagging (`LIVE DEVICE` vs `MANUAL INPUT`).
- **Platform Limitations & Future Deployment**:
  - Modern web browsers do not grant client-side JavaScript direct access to physical battery hardware (the W3C Battery Status API was deprecated due to fingerprinting concerns).
  - For future **Android** deployments, a native Android background service utilizing the Android BatteryManager API (`ACTION_BATTERY_CHANGED`) is required to post telemetry to this REST backend.
  - For dedicated **IoT / EV** hardware, an embedded microcontroller (e.g., ESP32, STM32) with an ADC or I2C coulomb counter (e.g., INA219, MAX17048) or CAN-bus telemetry interface is used to stream live state-of-charge data.

---

## 5. Development & Execution Instructions

### Starting Backend REST Service
From the repository root:
```bash
# Set Python path to backend
$env:PYTHONPATH = "C:\projects\smart-battery-ai\backend"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Starting Frontend Dashboard
From the `frontend/` directory:
```bash
# Run local development server
npm run dev
# Or preview production build
npm run preview -- --port 5173
```
Open your browser at `http://localhost:5173`.

### Resilient Offline Demo Mode
If the backend is not actively running, the frontend automatically activates its **Demo Mode** with full mock fixtures from `data/users.csv` and `data/charging_behavior.csv`, ensuring all tabs, charts, predictions, and recommendations remain fully testable and responsive.
