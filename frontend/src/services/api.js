/**
 * API Service for Smart Battery AI Dashboard.
 * Integrates with FastAPI REST endpoints with resilient mock fallbacks for offline demo.
 */

import {
  MOCK_USERS,
  MOCK_SESSIONS,
  MOCK_HEALTH,
  MOCK_PREDICTION_RESULT,
  MOCK_RECOMMENDATION_RESULT,
} from '../data/mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Fetch system and ML model health status.
 */
export async function getHealthStatus() {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Backend /health unreachable, using mock health status:', err.message);
    return { ...MOCK_HEALTH, status: 'offline (demo mode)' };
  }
}

/**
 * Fetch all registered users.
 */
export async function getUsers() {
  try {
    const res = await fetch(`${BASE_URL}/api/users`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data && data.length > 0 ? data : MOCK_USERS;
  } catch (err) {
    console.warn('Backend /api/users unreachable, using mock users:', err.message);
    return MOCK_USERS;
  }
}

/**
 * Fetch a single user by ID.
 */
export async function getUser(userId) {
  try {
    const res = await fetch(`${BASE_URL}/api/users/${userId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    const fallback = MOCK_USERS.find((u) => u.id === Number(userId)) || MOCK_USERS[0];
    return fallback;
  }
}

/**
 * Fetch historical charging sessions for a user.
 */
export async function getChargingHistory(userId, limit = 50) {
  try {
    const res = await fetch(`${BASE_URL}/api/charging-sessions/${userId}?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.warn(`Backend /api/charging-sessions/${userId} unreachable, using mock sessions:`, err.message);
    return MOCK_SESSIONS;
  }
}

/**
 * Fetch latest battery telemetry reading for a user.
 */
export async function getLatestBatteryReading(userId) {
  try {
    const res = await fetch(`${BASE_URL}/api/battery-readings/${userId}/latest`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return {
      id: 1,
      user_id: userId,
      timestamp: new Date().toISOString(),
      battery_percent: 74.0,
      voltage: 3.98,
      current: 1.45,
      temperature: 32.5,
    };
  }
}

/**
 * Request ML unplug-time prediction for a user.
 * POST /api/predict/{user_id}
 */
export async function predictUnplugTime(userId, payload) {
  try {
    const res = await fetch(`${BASE_URL}/api/predict/${userId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Prediction failed (HTTP ${res.status})`);
    }
    return await res.json();
  } catch (err) {
    console.warn('Live prediction failed, returning calculated mock prediction:', err.message);
    // Dynamically calculate mock based on input
    const plugHour = payload?.plug_time ? new Date(payload.plug_time).getHours() : 22;
    const targetUnplugHour = (plugHour >= 20 || plugHour <= 2) ? 7.5 : (plugHour + 4.5) % 24;
    const hours = Math.floor(targetUnplugHour);
    const mins = Math.floor((targetUnplugHour - hours) * 60);
    const timeStr = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;

    return {
      ...MOCK_PREDICTION_RESULT,
      user_id: Number(userId),
      predicted_unplug_time: timeStr,
      predicted_unplug_hour: targetUnplugHour,
      created_at: new Date().toISOString(),
    };
  }
}

/**
 * Request personalized charging recommendation.
 * POST /api/recommendations/{user_id}/generate
 */
export async function generateRecommendation(userId, payload) {
  try {
    const res = await fetch(`${BASE_URL}/api/recommendations/${userId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Recommendation generation failed (HTTP ${res.status})`);
    }
    return await res.json();
  } catch (err) {
    console.warn('Live recommendation failed, returning simulated mock recommendation:', err.message);
    const currentSoc = payload.current_battery_percent ?? 25;
    const targetSoc = payload.wants_full_charge ? 100 : (payload.preferred_target_soc ?? 80);
    const isFast = payload.charger_type === 'fast';
    const rate = payload.estimated_charging_rate_percent_per_hour || (isFast ? 40 : 25);
    const chargingMinutes = Math.round(((targetSoc - currentSoc) / rate) * 60);

    const now = new Date(payload.plug_time || Date.now());
    const predictedUnplugDt = new Date(now.getTime() + 8.5 * 3600000);
    const finishDt = new Date(predictedUnplugDt.getTime() - 20 * 60000); // 20m buffer
    const startDt = new Date(finishDt.getTime() - chargingMinutes * 60000);

    const allowDelay = payload.allow_delayed_charging !== false;
    const mode = (allowDelay && startDt > now) ? 'DELAYED_CHARGE' : 'CHARGE_NOW';

    const fmt = (d) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

    return {
      user_id: Number(userId),
      prediction: {
        predicted_unplug_time: fmt(predictedUnplugDt),
        prediction_source: 'PERSONALIZED',
        confidence_level: 'HIGH',
        confidence_score: 0.88,
        history_count: 52,
        predicted_unplug_datetime: predictedUnplugDt.toISOString(),
      },
      recommendation: {
        mode: mode,
        current_soc: currentSoc,
        target_soc: targetSoc,
        recommended_start_time: mode === 'DELAYED_CHARGE' ? fmt(startDt) : fmt(now),
        estimated_finish_time: fmt(finishDt),
        estimated_charging_minutes: chargingMinutes,
        message: mode === 'DELAYED_CHARGE'
          ? `Delay charging until ${fmt(startDt)} to reach ${targetSoc}% target SoC by ${fmt(finishDt)}, with 20 minutes safety buffer before anticipated unplug at ${fmt(predictedUnplugDt)}.`
          : `Start charging immediately to reach ${targetSoc}% target SoC by ${fmt(finishDt)}.`,
        reason: mode === 'DELAYED_CHARGE'
          ? 'Personalized prediction indicates sufficient idle buffer before unplug time. Delaying charging start avoids battery sitting at high voltage.'
          : 'Immediate charging scheduled per timing constraints or user preference.',
        warnings: payload.current_temperature > 40 ? ['High battery temperature detected. Charging rate may be throttled.'] : [],
        recommended_start_datetime: (mode === 'DELAYED_CHARGE' ? startDt : now).toISOString(),
        estimated_finish_datetime: finishDt.toISOString(),
      },
      recommendation_id: Math.floor(Math.random() * 1000) + 1,
      prediction_id: Math.floor(Math.random() * 1000) + 1,
      created_at: new Date().toISOString(),
    };
  }
}

/**
 * Fetch past predictions for a user.
 */
export async function getUserPredictions(userId, limit = 20) {
  try {
    const res = await fetch(`${BASE_URL}/api/predictions/${userId}?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return [MOCK_PREDICTION_RESULT];
  }
}

/**
 * Fetch past recommendations for a user.
 */
export async function getUserRecommendations(userId, limit = 20) {
  try {
    const res = await fetch(`${BASE_URL}/api/recommendations/${userId}?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return [
      {
        id: 1,
        user_id: userId,
        target_soc: 80.0,
        mode: 'DELAYED_CHARGE',
        confidence_score: 0.88,
        recommendation_message: 'Delay charging until 05:15 to preserve battery health.',
        created_at: new Date().toISOString(),
      },
    ];
  }
}

/**
 * Fetch real local hardware device battery telemetry from host OS (via /api/device-battery).
 */
export async function getDeviceBattery() {
  try {
    const res = await fetch(`${BASE_URL}/api/device-battery`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Host device battery endpoint unreachable or unsupported:', err.message);
    return {
      available: false,
      battery_percent: null,
      is_plugged_in: null,
      seconds_left: null,
      source: 'UNAVAILABLE',
    };
  }
}

/**
 * Fetch background telemetry collector status and personalization progression.
 */
export async function getTelemetryStatus(userId = 1) {
  try {
    const res = await fetch(`${BASE_URL}/api/telemetry/status?user_id=${userId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Telemetry status endpoint unreachable, using fallback:', err.message);
    return {
      collector_running: false,
      last_poll_time: null,
      poll_interval_seconds: 120,
      user_id: userId,
      device_battery: { available: false, battery_percent: 50.0, is_plugged_in: false },
      active_session: null,
      real_sessions_count: 0,
      personalization_stage: 'LEARNING',
      personalization_progress_pct: 0.0,
      target_sessions_for_full_personalization: 7,
      today_active_minutes: 0.0,
      today_idle_minutes: 0.0,
      sleep_events_count: 0,
      privacy_notice: 'Telemetry collects only aggregate battery levels and idle durations.',
    };
  }
}

/**
 * Fetch real Windows charging sessions for a user.
 */
export async function getRealSessions(userId = 1, limit = 50) {
  try {
    const res = await fetch(`${BASE_URL}/api/telemetry/sessions?user_id=${userId}&limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Real sessions endpoint unreachable:', err.message);
    return [];
  }
}

/**
 * Fetch recent periodic telemetry samples.
 */
export async function getTelemetrySamples(userId = 1, limit = 30) {
  try {
    const res = await fetch(`${BASE_URL}/api/telemetry/samples?user_id=${userId}&limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Telemetry samples endpoint unreachable:', err.message);
    return [];
  }
}

/**
 * Trigger immediate telemetry polling cycle on backend.
 */
export async function triggerTelemetryPoll(userId = 1) {
  try {
    const res = await fetch(`${BASE_URL}/api/telemetry/poll-now?user_id=${userId}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Trigger telemetry poll failed:', err.message);
    return { success: false, message: err.message };
  }
}
