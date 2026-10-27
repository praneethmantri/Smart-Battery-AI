import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { predictUnplugTime } from '../services/api';
import { SourceBadge, ConfidenceBadge } from '../components/StatusBadge';
import { Icon } from '../components/Icons';
import { parseUtcDate } from '../utils/dateUtils';

export default function PredictionPage() {
  const {
    selectedUserId,
    currentUser,
    latestPrediction,
    setLatestPrediction,
    showNotification,
    deviceBattery,
    telemetry,
  } = useApp();

  const isDeviceAvailable = Boolean(deviceBattery?.available && deviceBattery?.battery_percent !== null);
  const liveSoc = isDeviceAvailable ? deviceBattery.battery_percent : (telemetry.battery_percent ?? 50);

  const [isManualOverride, setIsManualOverride] = useState(false);
  const [currentSoc, setCurrentSoc] = useState(liveSoc);
  const [plugTime, setPlugTime] = useState(() => {
    const now = new Date();
    // Default to current local time in ISO format substring for input[type="datetime-local"]
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  });
  const [chargerType, setChargerType] = useState('fast');
  const [previousDayUsage, setPreviousDayUsage] = useState(520);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Auto-sync currentSoc with live device battery if user hasn't manually overridden it
  useEffect(() => {
    if (!isManualOverride && liveSoc !== undefined && liveSoc !== null) {
      setCurrentSoc(liveSoc);
    }
  }, [liveSoc, isManualOverride]);

  const handlePredict = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const payload = {
        current_battery_percent: Number(currentSoc),
        plug_time: new Date(plugTime).toISOString(),
        charger_type: chargerType,
        previous_day_usage_minutes: Number(previousDayUsage),
      };

      const result = await predictUnplugTime(selectedUserId, payload);
      setLatestPrediction(result);
      showNotification(`AI Unplug Time predicted using ${isManualOverride ? 'manual' : 'live device'} SoC (${currentSoc}%)!`, 'success');
    } catch (err) {
      showNotification(err.message || 'Failed to generate prediction', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatTime = (isoString, fallback) => {
    if (!isoString) return fallback;
    try {
      const d = parseUtcDate(isoString);
      if (!d) return fallback;
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return fallback;
    }
  };

  const pred = latestPrediction || {};
  const unplugTime = formatTime(pred.predicted_unplug_datetime, pred.predicted_unplug_time || '07:35');
  const confidenceScore = pred.confidence_score ?? 0.88;
  const confidenceLevel = pred.confidence_level || 'HIGH';
  const source = pred.prediction_source || 'PERSONALIZED';
  const historyCount = pred.history_count ?? 12;
  const modelVersion = pred.model_version || 'hybrid_rf_v1';

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="section-title">AI Expected Unplug-Time Prediction</h2>
          <p className="section-desc">
            Multi-tier machine learning inference predicting exact user unplug time based on historical behavioral patterns.
          </p>
        </div>

        {isDeviceAvailable && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              fontSize: '0.8rem',
              color: '#34d399',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#34d399' }} />
            Host Battery: <strong>{deviceBattery.battery_percent}%</strong> ({deviceBattery.is_plugged_in ? 'Charging' : 'On Battery'})
          </div>
        )}
      </div>

      <div className="two-column-grid">
        {/* Left Column: Input Form */}
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon name="sliders" size={18} color="#38bdf8" />
            Inference Parameters
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '1.25rem' }}>
            Provide charging context for User #{selectedUserId} ({currentUser.name}).
          </p>

          <form onSubmit={handlePredict}>
            {/* Current SOC */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <label className="form-label" style={{ margin: 0 }}>Current Battery SoC</label>
                  {isDeviceAvailable && !isManualOverride ? (
                    <span
                      className="badge badge-green"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
                    >
                      <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                      LIVE DEVICE
                    </span>
                  ) : (
                    <span
                      className="badge badge-amber"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
                    >
                      MANUAL INPUT
                    </span>
                  )}
                </div>
                <span style={{ fontWeight: 700, color: '#38bdf8' }}>{currentSoc}%</span>
              </div>
              <input
                type="range"
                min="5"
                max="95"
                value={currentSoc}
                onChange={(e) => {
                  setCurrentSoc(Number(e.target.value));
                  setIsManualOverride(true);
                }}
                className="range-input"
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                <span className="form-hint" style={{ margin: 0 }}>
                  {isManualOverride
                    ? 'Manually set for simulation.'
                    : (isDeviceAvailable ? 'Synchronized with Windows host battery.' : 'Initial estimated battery percentage.')}
                </span>
                {isManualOverride && isDeviceAvailable && (
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentSoc(deviceBattery.battery_percent);
                      setIsManualOverride(false);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#38bdf8',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      padding: 0,
                    }}
                  >
                    Reset to Live Device ({deviceBattery.battery_percent}%)
                  </button>
                )}
              </div>
            </div>

            {/* Plug Time */}
            <div className="form-group">
              <label className="form-label">Plug-In Timestamp</label>
              <input
                type="datetime-local"
                value={plugTime}
                onChange={(e) => setPlugTime(e.target.value)}
                className="text-input"
                required
              />
              <span className="form-hint">Reference time when charging starts</span>
            </div>

            {/* Charger Type */}
            <div className="form-group">
              <label className="form-label">Charger Hardware Type</label>
              <select
                value={chargerType}
                onChange={(e) => setChargerType(e.target.value)}
                className="text-input"
              >
                <option value="standard">Standard (5W - 15W)</option>
                <option value="fast">Fast Charger (20W - 65W)</option>
                <option value="wireless">Wireless Qi Dock (5W - 15W)</option>
              </select>
            </div>

            {/* Previous Day Screen Usage */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Previous Day Screen Usage</label>
                <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                  {previousDayUsage} min ({(previousDayUsage / 60).toFixed(1)} hrs)
                </span>
              </div>
              <input
                type="range"
                min="60"
                max="720"
                step="15"
                value={previousDayUsage}
                onChange={(e) => setPreviousDayUsage(e.target.value)}
                className="range-input"
              />
              <span className="form-hint">Proxy for user tiredness and wake-up variability</span>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary"
              style={{ width: '100%', marginTop: '1rem', padding: '0.75rem' }}
            >
              {isSubmitting ? (
                <>
                  <Icon name="refresh" size={16} /> Computing ML Inference...
                </>
              ) : (
                <>
                  <Icon name="prediction" size={16} /> Run Unplug Prediction
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Prediction Result */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card prediction-result-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Predicted Unplug Output
              </span>
              <SourceBadge source={source} />
            </div>

            <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
              <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Expected Unplug Time</span>
              <div style={{ fontSize: '3.5rem', fontWeight: 800, color: '#38bdf8', letterSpacing: '-0.03em', lineHeight: 1.1, margin: '0.35rem 0' }}>
                {unplugTime}
              </div>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Based on {historyCount} completed historical sessions
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '0.75rem',
                paddingTop: '1rem',
                borderTop: '1px solid #334155',
                textAlign: 'center',
              }}
            >
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Confidence</div>
                <div style={{ marginTop: '0.25rem' }}>
                  <ConfidenceBadge score={confidenceScore} level={confidenceLevel} />
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>History Count</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
                  {historyCount} sessions
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Model Version</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#10b981', marginTop: '0.25rem' }}>
                  {modelVersion}
                </div>
              </div>
            </div>
          </div>

          {/* Model Selection Pipeline Explanation Card */}
          <div className="card">
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#e2e8f0', margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Icon name="cpu" size={16} color="#10b981" />
              Multi-Tier Model Selection Architecture
            </h4>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
              The system dynamically routes inference through three tiers based on user history depth:
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0.75rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8rem' }}>
              <li style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', color: '#cbd5e1' }}>
                <strong style={{ color: '#38bdf8', minWidth: '130px' }}>0-2 Sessions:</strong>
                <span>Global Gradient Boosting model trained on population charging habits (MAE: 37.69m).</span>
              </li>
              <li style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', color: '#f59e0b', minWidth: '130px' }}>
                <strong style={{ color: '#f59e0b', minWidth: '130px' }}>3-6 Sessions:</strong>
                <span>Bayesian blended model combining user empirical mean with global baseline prior.</span>
              </li>
              <li style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', color: '#10b981', minWidth: '130px' }}>
                <strong style={{ color: '#10b981', minWidth: '130px' }}>7+ Sessions:</strong>
                <span>Personalized Hybrid Random Forest with leak-free circular statistical features (MAE: 33.96m).</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
