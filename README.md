# AI-Based Personalized Battery Charging Based on User Behavior

> **College R&D Project**: Smart charging system that analyzes historical usage patterns using machine learning to predict unplug times and recommend health-preserving charging schedules (e.g., 80% limit with scheduled top-off).

---

## 1. System Architecture & Interaction Flow

The project consists of four interconnected core components operating in a modular, decoupled architecture:

```
+-------------------------------------------------------------+
|                     React 18 + Vite Frontend                |
|  - Real-time battery status widget                          |
|  - Historical charging charts (Chart.js)                    |
|  - Personalized charging schedule & recommendation cards    |
+------------------------------+------------------------------+
                               |
                               | REST API (HTTP / JSON)
                               v
+-------------------------------------------------------------+
|                     FastAPI Backend Engine                  |
|  - Session ingestion (/api/v1/charging-sessions)            |
|  - Charging schedule optimization service                   |
|  - Invokes ML prediction pipeline                           |
+---------------+-----------------------------+---------------+
                |                             |
     SQLAlchemy | ORM              In-Memory  | Joblib Model
                v                             v
+-----------------------------+ +-----------------------------+
|    Database Layer           | |     Machine Learning (ML)   |
|  - SQLite (Local Dev)       | |  - Feature Extraction       |
|  - PostgreSQL (Cloud Ready) | |  - Scikit-learn Regressor   |
|  - Historical charging logs | |  - Predicts unplug timestamp|
|  - Recommendation audits    | |  - Model training pipeline  |
+-----------------------------+ +-----------------------------+
```

### End-to-End Workflow:
1. **Event Ingestion**: When a device is plugged in, the frontend or client device pushes a session initiation event (`plug_time`, `start_battery_pct`, `user_id`) to the FastAPI backend.
2. **Feature Extraction**: Backend passes current context (`plug_time`, day of week, hour, historical user averages) to the ML module.
3. **Unplug Prediction**: The trained Scikit-learn model predicts the expected unplug time (e.g., predicted unplug at 07:15 AM).
4. **Optimization Logic**: The backend optimizer computes the optimal charging strategy:
   - **Phase 1**: Quick charge up to 80% State of Charge (SoC).
   - **Phase 2**: Trickle or pause charging to minimize high-voltage stress during idle plugged hours.
   - **Phase 3**: Top-off to 100% just before the predicted unplug time.
5. **Database Storage**: The session and recommendation are logged in SQLite via SQLAlchemy ORM.
6. **Frontend Presentation**: React visualizes the predicted unplug curve, recommended charging intervals, and historical stats using Chart.js.

---

## 2. Directory Structure

```
smart-battery-ai/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/              # API endpoints (v1 routes)
│   │   ├── core/             # App configuration and environment variables
│   │   ├── db/               # SQLAlchemy engine, session, and base
│   │   ├── models/           # Database models (ChargingSession, Recommendation, TelemetrySample)
│   │   ├── schemas/          # Pydantic validation schemas
│   │   ├── services/         # Business logic & charging optimizer
│   │   └── main.py           # FastAPI application entrypoint
│   └── requirements.txt      # Backend Python dependencies
├── frontend/                 # React 18 + Vite Application
│   ├── src/
│   │   ├── components/       # UI components (BatteryStatus, ChargingChart, etc.)
│   │   ├── pages/            # View pages (Dashboard, Analytics, RealData, etc.)
│   │   ├── services/         # API client module
│   │   ├── App.jsx           # Dashboard layout & routing
│   │   ├── index.css         # Styling
│   │   └── main.jsx          # React DOM entry
│   ├── index.html            # Vite HTML template
│   ├── package.json          # Node dependencies & scripts
│   └── vite.config.js        # Vite configuration
├── ml/                       # Machine Learning Pipeline
│   ├── models/               # Production trained circular ML models (.joblib)
│   ├── artifacts/            # Model artifact storage (.gitkeep)
│   ├── feature_engineering.py# Temporal and behavioral feature transformations
│   ├── personalized_train.py # Personalized model training pipeline
│   ├── train.py              # Baseline ML training script
│   └── requirements.txt      # ML Python dependencies
├── data/                     # Datasets and SQLite Storage
│   ├── raw/                  # Raw sensor/session logs
│   ├── processed/            # Cleaned ML training datasets
│   ├── charging_behavior.csv # Base synthetic behavior dataset
│   └── README.md             # Data schema documentation
├── tests/                    # Automated Test Suite
│   ├── conftest.py           # Pytest test fixtures & mock DB
│   ├── test_api.py           # Endpoint integration tests
│   ├── test_optimizer.py     # Charging algorithm unit tests
│   ├── test_ml_pipeline.py   # Model inference & feature tests
│   └── requirements.txt      # Test dependencies
├── scripts/                  # Utility Scripts
│   ├── run_windows_collector.py   # Windows laptop background telemetry collector
│   ├── generate_synthetic_data.py # Generates realistic user charging logs
│   └── train_model.py             # CLI for training ML model
├── docs/                     # Architectural & API Specifications
│   ├── architecture.md       # Deep-dive design notes
│   ├── api_spec.md           # API endpoints reference
│   └── windows_telemetry_setup.md # Windows collector setup guide
├── .env.example              # Sample environment configuration
├── .gitignore                # Production Git exclusion rules
└── README.md                 # Project documentation (this file)
```

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, Vite 5, JavaScript | Fast, reactive user dashboard |
| **Data Viz** | Chart.js 4, react-chartjs-2 | Interactive charging curves and trends |
| **Backend** | Python 3.10+, FastAPI | High-performance asynchronous REST API |
| **ORM / DB** | SQLAlchemy 2.0, SQLite / PostgreSQL | Decoupled data layer, cloud deployable |
| **Machine Learning** | Pandas, NumPy, Scikit-learn, Joblib | Circular unplug time prediction & model serialization |
| **OS Telemetry** | Python psutil, Win32 API | Real laptop charging & user activity tracking |
| **Testing** | Pytest, HTTPX | Automated unit and integration testing |

---

## 4. Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Git

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment configuration:
   ```bash
   cp ../.env.example .env
   ```
5. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   API Swagger Docs will be available at: `http://localhost:8000/docs`

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server on port 5173:
   ```bash
   npm run dev
   ```
   The dashboard will be available at: `http://localhost:5173`

### Windows Telemetry Collector (Real Device Telemetry)
The background telemetry collector captures real battery charge events and user idle periods directly from the Windows OS without requiring manual session logging:
1. Ensure the Python virtual environment is activated and backend dependencies are installed.
2. Run the collector script:
   ```bash
   python scripts/run_windows_collector.py
   ```
3. Configuration options:
   - Poll interval (default 180s / 3m): `python scripts/run_windows_collector.py --poll-interval 120`
   - Specific user ID: `python scripts/run_windows_collector.py --user-id 1`
   - Single poll snapshot test: `python scripts/run_windows_collector.py --once`
4. For detailed background service setup and Task Scheduler configuration, see [docs/windows_telemetry_setup.md](docs/windows_telemetry_setup.md).

### Machine Learning Setup & Training
1. Navigate to root or ml directory:
   ```bash
   pip install -r ml/requirements.txt
   ```
2. Generate synthetic user charging behavior data:
   ```bash
   python scripts/generate_synthetic_data.py
   ```
3. Train the unplug time predictor:
   ```bash
   python scripts/train_model.py
   ```

### Running Tests
Execute test suite using pytest:
```bash
pip install -r tests/requirements.txt
pytest tests/
```

---

## 5. R&D Research Highlights
- **Battery Degradation Prevention**: Lithium-ion batteries experience accelerated stress when held at high voltage (100% SoC) and elevated temperatures. By delaying the final 20% charge until shortly before wake/unplug time, battery lifespan is significantly prolonged.
- **Pattern Learning**: The ML model accommodates distinct workday vs. weekend routines, detecting irregular patterns and safely falling back to standard safe charging profiles when prediction confidence is low.
- **Circular Time Encoding**: Hour-of-day features are encoded using sine and cosine projections ($\sin(2\pi \cdot t / 24)$ and $\cos(2\pi \cdot t / 24)$) to maintain smooth temporal continuity across the midnight boundary.

---

## 6. Academic Research & Longevity Disclaimer

> [!WARNING]
> **Research & Engineering Disclaimer**: The machine learning models and battery optimization strategies in this repository were developed and evaluated using synthetic behavioral datasets and simulated degradation curves for academic research and demonstration purposes. Model performance metrics (e.g., MAE, R²) and simulated battery health metrics do **not** represent clinically or chemically verified battery longevity gains under real-world electrochemical cycling conditions. Always adhere to your hardware manufacturer's charging guidelines for physical device longevity and safety.
