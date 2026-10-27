# REST API Specification

Smart Battery AI Backend REST API documentation.
Accessible with both `/api` and `/api/v1` prefixes.

Interactive Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## 1. System Health

### `GET /health` or `GET /api/health`
Returns the status of the API, database connectivity, and ML model availability.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "database": "connected",
  "ml_model_loaded": false,
  "timestamp": "2026-09-09T14:30:00Z"
}
```

---

## 2. Users

### `POST /api/users`
Create a new user.

**Request Body**:
```json
{
  "name": "Demo User",
  "email": "demo@example.com"
}
```

**Response `201 Created`**:
```json
{
  "id": 1,
  "name": "Demo User",
  "email": "demo@example.com",
  "created_at": "2026-09-09T14:30:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Duplicate email registered or invalid ID.
- `422 Unprocessable Entity`: Validation failure (e.g. invalid email format, empty name).

---

### `GET /api/users/{user_id}`
Retrieve profile and registration details for a user.

**Response `200 OK`**:
```json
{
  "id": 1,
  "name": "Demo User",
  "email": "demo@example.com",
  "created_at": "2026-09-09T14:30:00Z"
}
```

**Error Responses**:
- `404 Not Found`: User does not exist.
- `400 Bad Request`: Negative or non-integer ID.

---

## 3. Charging Sessions

### `POST /api/charging-sessions`
Create a charging session record.

**Request Body**:
```json
{
  "user_id": 1,
  "start_time": "2026-09-09T23:00:00Z",
  "end_time": null,
  "start_battery_percent": 24.5,
  "end_battery_percent": null,
  "average_temperature": 32.1,
  "charging_duration_minutes": null,
  "charger_type": "fast_dc",
  "screen_usage_minutes": 10.0,
  "day_of_week": 2
}
```

**Response `201 Created`**:
```json
{
  "id": 1,
  "user_id": 1,
  "start_time": "2026-09-09T23:00:00Z",
  "end_time": null,
  "start_battery_percent": 24.5,
  "end_battery_percent": null,
  "average_temperature": 32.1,
  "charging_duration_minutes": null,
  "charger_type": "fast_dc",
  "screen_usage_minutes": 10.0,
  "day_of_week": 2,
  "created_at": "2026-09-09T23:00:00Z"
}
```

**Error Responses**:
- `404 Not Found`: `user_id` does not exist in the database.
- `422 Unprocessable Entity`: `start_battery_percent` outside 0–100 or negative duration.

---

### `GET /api/charging-sessions/{user_id}`
List historical charging sessions for a user, ordered by `start_time` descending.

**Response `200 OK`**:
```json
[
  {
    "id": 1,
    "user_id": 1,
    "start_time": "2026-09-09T23:00:00Z",
    "end_time": "2026-09-10T07:30:00Z",
    "start_battery_percent": 24.5,
    "end_battery_percent": 100.0,
    "average_temperature": 32.1,
    "charging_duration_minutes": 510.0,
    "charger_type": "fast_dc",
    "screen_usage_minutes": 10.0,
    "day_of_week": 2,
    "created_at": "2026-09-09T23:00:00Z"
  }
]
```

---

### `GET /api/charging-sessions/{user_id}/latest`
Fetch the most recent charging session for a user.

**Response `200 OK`**: (Charging session object)
**Error Response**: `404 Not Found` if user does not exist or has no sessions.

---

## 4. Battery Readings

### `POST /api/battery-readings`
Ingest high-frequency battery telemetry.

**Request Body**:
```json
{
  "user_id": 1,
  "timestamp": "2026-09-09T23:15:00Z",
  "voltage": 4.05,
  "current": 1.45,
  "temperature": 31.5,
  "battery_percent": 65.0
}
```

**Response `201 Created`**:
```json
{
  "id": 1,
  "user_id": 1,
  "timestamp": "2026-09-09T23:15:00Z",
  "voltage": 4.05,
  "current": 1.45,
  "temperature": 31.5,
  "battery_percent": 65.0
}
```

---

### `GET /api/battery-readings/{user_id}`
Retrieve time-series battery readings for a user.

**Query Parameters**:
- `order`: `desc` (default) or `asc`
- `limit`: default 100, max 500
- `offset`: default 0

**Response `200 OK`**: List of battery readings.

---

### `GET /api/battery-readings/{user_id}/latest`
Retrieve the single most recent battery reading for a user.

**Response `200 OK`**: Battery reading object.
**Error Response**: `404 Not Found` if no readings exist for user.

---

## 5. Predictions

### `GET /api/predictions/{user_id}`
Return previous ML predictions for the user ordered by creation timestamp descending.

**Response `200 OK`**:
```json
[
  {
    "id": 1,
    "user_id": 1,
    "predicted_unplug_time": "2026-09-10T07:30:00Z",
    "confidence_score": 0.88,
    "model_version": "1.0.0",
    "created_at": "2026-09-09T23:05:00Z"
  }
]
```
*Note: Returns `[]` if no predictions have been generated yet.*

---

### `GET /api/predictions/{user_id}/latest`
Retrieve the latest recorded prediction for a user.

**Response `200 OK`**: Prediction object.
**Error Response**: `404 Not Found` if user has no predictions.

---

## 6. Recommendations

### `GET /api/recommendations/{user_id}`
Return historical personalized charging recommendations for a user.

**Response `200 OK`**:
```json
[
  {
    "id": 1,
    "session_id": 1,
    "user_id": 1,
    "predicted_unplug_time": "2026-09-10T07:30:00Z",
    "recommended_start_time": "2026-09-10T06:45:00Z",
    "target_soc": 80.0,
    "recommendation_message": "Optimized schedule: Fast charge to 80%, hold until 06:45, top off to 100% by 07:25.",
    "mode": "optimized_delayed",
    "confidence_score": 0.89,
    "created_at": "2026-09-09T23:00:00Z"
  }
]
```

---

### `GET /api/recommendations/{user_id}/latest`
Retrieve the latest charging recommendation for a user.

**Response `200 OK`**: Recommendation object.
**Error Response**: `404 Not Found` if user has no recommendations.

---

## 7. Device Battery Sensor (Local Development / Demonstration)

### `GET /api/device-battery` and `GET /api/v1/device-battery`
Queries the physical host operating system battery hardware sensor via Python `psutil`. Used in local development mode to feed actual Windows laptop battery State of Charge (SoC) into the AI dashboard and recommendation solver.

**Response `200 OK` (Hardware battery detected)**:
```json
{
  "available": true,
  "battery_percent": 47.0,
  "is_plugged_in": false,
  "seconds_left": 7459,
  "source": "WINDOWS_SYSTEM",
  "timestamp": "2026-09-09T16:16:16.053065+00:00"
}
```

**Response `200 OK` (Desktop PC / VM / battery unavailable)**:
```json
{
  "available": false,
  "battery_percent": null,
  "is_plugged_in": null,
  "seconds_left": null,
  "source": "UNAVAILABLE",
  "timestamp": "2026-09-09T16:16:16.053065+00:00"
}
```
