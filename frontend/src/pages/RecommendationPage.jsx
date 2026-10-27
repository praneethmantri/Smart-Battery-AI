import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { generateRecommendation } from '../services/api';
import { ModeBadge, ConfidenceBadge, SourceBadge } from '../components/StatusBadge';
import ScheduleTimeline from '../components/ScheduleTimeline';
import { Icon } from '../components/Icons';
import { parseUtcDate } from '../utils/dateUtils';

export default function RecommendationPage() {
  const {
    selectedUserId,
    currentUser,
    latestRecommendation,
    setLatestRecommendation,
    showNotification,
    deviceBattery,
    telemetry,
  } = useApp();

  const isDeviceAvailable = Boolean(deviceBattery?.available && deviceBattery?.battery_percent !== null);
  const liveSoc = isDeviceAvailable ? deviceBattery.battery_percent : (telemetry.battery_percent ?? 50);

  const [isManualOverride, setIsManualOverride] = useState(false);
  const [currentSoc, setCurrentSoc] = useState(liveSoc);
  const [preferredTargetSoc, setPreferredTargetSoc] = useState(80);
  const [minRequiredSoc, setMinRequiredSoc] = useState(70);
  const [wantsFullCharge, setWantsFullCharge] = useState(false);
  const [allowDelayedCharging, setAllowDelayedCharging] = useState(true);
  const [chargerType, setChargerType] = useState('fast');
  const [temperature, setTemperature] = useState(32.5);
  const [chargingRate, setChargingRate] = useState(40);
  const [plugTime, setPlugTime] = useState(() => {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Auto-sync currentSoc with live device battery if user hasn't manually overridden it
  useEffect(() => {
    if (!isManualOverride && liveSoc !== undefined && liveSoc !== null) {
      setCurrentSoc(liveSoc);
    }
  }, [liveSoc, isManualOverride]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const payload = {
        current_battery_percent: Number(currentSoc),
        preferred_target_soc: Number(preferredTargetSoc),
        minimum_required_soc: Number(minRequiredSoc),
        wants_full_charge: wantsFullCharge,
        allow_delayed_charging: allowDelayedCharging,
        charger_type: chargerType,
        current_temperature: Number(temperature),
        estimated_charging_rate_percent_per_hour: Number(chargingRate),
        plug_time: new Date(plugTime).toISOString(),
      };

      const result = await generateRecommendation(selectedUserId, payload);
      setLatestRecommendation(result);
      showNotification(`Recommendation generated using ${isManualOverride ? 'manual' : 'live device'} SoC (${currentSoc}%)!`, 'success');
    } catch (err) {
      showNotification(err.message || 'Failed to generate recommendation', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const rec = latestRecommendation?.recommendation || {};
  const pred = latestRecommendation?.prediction || {};

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

  const effectiveTargetSoc = wantsFullCharge ? 100 : (rec.target_soc || preferredTargetSoc);
  const mode = rec.mode || 'DELAYED_CHARGE';
  const startTime = formatTime(rec.recommended_start_datetime, rec.recommended_start_time || '05:15');
  const finishTime = formatTime(rec.estimated_finish_datetime, rec.estimated_finish_time || '07:15');
  const unplugTime = formatTime(pred.predicted_unplug_datetime, pred.predicted_unplug_time || '07:35');
  const durationMin = rec.estimated_charging_minutes || 120;
  const warnings = rec.warnings || [];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="section-title">Personalized Charging Recommendation</h2>
          <p className="section-desc">
            Calculates degradation-mitigating charging windows based on predicted unplug time and thermal thresholds.
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
            Host Battery Connected: <strong>{deviceBattery.battery_percent}%</strong> ({deviceBattery.is_plugged_in ? 'AC Charging' : 'On Battery'})
          </div>
        )}
      </div>

      <div className="two-column-grid">
        {/* Configuration Form */}
        <div className="card">
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon name="sliders" size={18} color="#38bdf8" />
            Recommendation Settings
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '1.25rem' }}>
            Configure current battery state and user charging preferences.
          </p>

          <form onSubmit={handleGenerate}>
            {/* Current SOC with Live Device vs Manual Input Badge */}
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
                    ? 'Manually overridden by user for simulation.'
                    : (isDeviceAvailable ? 'Automatically prefilled from live Windows device sensor.' : 'Prefilled from default estimate.')}
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

            {/* Target SOC and Full Charge Toggle */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Target SoC Level</label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#94a3b8', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={wantsFullCharge}
                    onChange={(e) => {
                      setWantsFullCharge(e.target.checked);
                      if (e.target.checked) setPreferredTargetSoc(100);
                    }}
                  />
                  <span>Want 100% Full Charge</span>
                </label>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Preferred ceiling:</span>
                <span style={{ fontWeight: 700, color: '#10b981' }}>{wantsFullCharge ? 100 : preferredTargetSoc}%</span>
              </div>
              <input
                type="range"
                min="60"
                max="100"
                disabled={wantsFullCharge}
                value={wantsFullCharge ? 100 : preferredTargetSoc}
                onChange={(e) => setPreferredTargetSoc(Number(e.target.value))}
                className="range-input"
                style={{ opacity: wantsFullCharge ? 0.5 : 1 }}
              />
              <span className="form-hint">
                80% SoC is recommended to minimize high-voltage lithium plating and electrolyte decomposition.
              </span>
            </div>

            {/* Charger Type and Charging Rate */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Charger Type</label>
                <select
                  value={chargerType}
                  onChange={(e) => {
                    const ct = e.target.value;
                    setChargerType(ct);
                    setChargingRate(ct === 'fast' ? 40 : ct === 'wireless' ? 20 : 25);
                  }}
                  className="text-input"
                >
                  <option value="fast">Fast (40%/hr)</option>
                  <option value="standard">Standard (25%/hr)</option>
                  <option value="wireless">Wireless (20%/hr)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Charging Rate (%/hr)</label>
                <input
                  type="number"
                  min="5"
                  max="120"
                  value={chargingRate}
                  onChange={(e) => setChargingRate(Number(e.target.value))}
                  className="text-input"
                />
              </div>
            </div>

            {/* Temperature and Delayed Charging Toggle */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Battery Temp (°C)</label>
                <input
                  type="number"
                  step="0.5"
                  min="-20"
                  max="70"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="text-input"
                />
                {temperature > 40 && (
                  <span style={{ color: '#ef4444', fontSize: '0.7rem' }}>Thermal warning &gt;40°C</span>
                )}
              </div>

              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: '#f8fafc', cursor: 'pointer', marginTop: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={allowDelayedCharging}
                    onChange={(e) => setAllowDelayedCharging(e.target.checked)}
                  />
                  <span>Allow Delayed Charging</span>
                </label>
                <span className="form-hint">Uncheck for urgent immediate charging</span>
              </div>
            </div>

            {/* Plug Time */}
            <div className="form-group">
              <label className="form-label">Plug-In Time</label>
              <input
                type="datetime-local"
                value={plugTime}
                onChange={(e) => setPlugTime(e.target.value)}
                className="text-input"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary"
              style={{ width: '100%', marginTop: '0.75rem', padding: '0.75rem' }}
            >
              {isSubmitting ? (
                <>
                  <Icon name="refresh" size={16} /> Generating Smart Schedule...
                </>
              ) : (
                <>
                  <Icon name="recommendation" size={16} /> Generate Smart Recommendation
                </>
              )}
            </button>
          </form>
        </div>

        {/* Recommendation Plan Output */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Personalized Recommendation Result
              </span>
              <ModeBadge mode={mode} />
            </div>

            <div style={{ margin: '1rem 0' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', margin: '0 0 0.5rem' }}>
                {rec.message || 'Optimized Charging Plan'}
              </h3>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
                {rec.reason}
              </p>
            </div>

            {/* Timing Stats Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '0.5rem',
                padding: '1rem 0',
                borderTop: '1px solid #334155',
                borderBottom: '1px solid #334155',
                textAlign: 'center',
              }}
            >
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Recommended Start</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.25rem' }}>
                  {startTime}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Target Ready</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#10b981', marginTop: '0.25rem' }}>
                  {finishTime}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Charge Duration</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
                  {durationMin.toFixed(0)}m
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Predicted Unplug</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#a855f7', marginTop: '0.25rem' }}>
                  {unplugTime}
                </div>
              </div>
            </div>

            {/* Warnings list */}
            {warnings.length > 0 && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444', fontWeight: 600, fontSize: '0.8rem' }}>
                  <Icon name="alert" size={15} /> Safety Warnings:
                </div>
                <ul style={{ margin: '0.25rem 0 0 1.25rem', fontSize: '0.75rem', color: '#fca5a5' }}>
                  {warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Visual Charging Sequence */}
            <ScheduleTimeline
              plugTime={plugTime.slice(11, 16)}
              plugDatetime={new Date(plugTime).toISOString()}
              recommendedStartTime={startTime}
              recommendedStartDatetime={rec.recommended_start_datetime}
              estimatedFinishTime={finishTime}
              estimatedFinishDatetime={rec.estimated_finish_datetime}
              predictedUnplugTime={unplugTime}
              predictedUnplugDatetime={pred.predicted_unplug_datetime}
              currentSoc={currentSoc}
              targetSoc={effectiveTargetSoc}
              mode={mode}
            />

            {/* Scientific advisory notice */}
            <div style={{ marginTop: '1.25rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
              <Icon name="info" size={14} />
              <span>Advisory & Scheduling Only. Hardware actuation is not performed.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
