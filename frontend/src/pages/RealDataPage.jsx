import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import {
  getTelemetryStatus,
  getRealSessions,
  getTelemetrySamples,
  triggerTelemetryPoll,
} from '../services/api';
import { Icon } from '../components/Icons';
import {
  formatTelemetryTimestamp,
  formatLocalTime,
  formatLocalDate,
} from '../utils/dateUtils';

export default function RealDataPage() {
  const { selectedUserId, showNotification } = useApp();
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [status, setStatus] = useState({
    collector_running: false,
    last_poll_time: null,
    poll_interval_seconds: 120,
    user_id: selectedUserId,
    device_battery: { available: false, battery_percent: null, is_plugged_in: null },
    active_session: null,
    real_sessions_count: 0,
    personalization_stage: 'LEARNING',
    personalization_progress_pct: 0.0,
    today_active_minutes: 0.0,
    today_idle_minutes: 0.0,
    sleep_events_count: 0,
    privacy_notice: 'Telemetry collects only aggregate battery levels and idle durations.',
  });
  const [realSessions, setRealSessions] = useState([]);
  const [samples, setSamples] = useState([]);

  // Detect browser local timezone name for user clarity
  const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [st, sess, smp] = await Promise.all([
        getTelemetryStatus(selectedUserId),
        getRealSessions(selectedUserId, 20),
        getTelemetrySamples(selectedUserId, 15),
      ]);
      if (st) setStatus(st);
      if (sess) setRealSessions(sess);
      if (smp) setSamples(smp);
    } catch (err) {
      console.warn('Failed to load telemetry data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedUserId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // 15s refresh
    return () => clearInterval(interval);
  }, [fetchData]);

  const handlePollNow = async () => {
    setPolling(true);
    try {
      const res = await triggerTelemetryPoll(selectedUserId);
      if (res && res.success) {
        showNotification(
          res.transition_event ? `Poll executed: ${res.transition_event}` : 'Live battery sampled successfully',
          'success'
        );
        await fetchData();
      } else {
        showNotification(res?.message || 'Poll failed', 'error');
      }
    } catch (e) {
      showNotification('Error triggering poll', 'error');
    } finally {
      setPolling(false);
    }
  };

  const getStageBadge = (stage) => {
    switch (stage) {
      case 'PERSONALIZED':
        return { label: 'Personalized (7+ Sessions)', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' };
      case 'BLENDED':
        return { label: 'Blended (3–6 Sessions)', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' };
      default:
        return { label: 'Learning (0–2 Sessions)', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' };
    }
  };

  const stageInfo = getStageBadge(status.personalization_stage);

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
              Real User Behavior Telemetry
            </h2>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '6px',
                background: 'rgba(56, 189, 248, 0.2)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                letterSpacing: '0.5px',
              }}
            >
              REAL WINDOWS DATA
            </span>
          </div>
          <p style={{ margin: '6px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Privacy-conscious Windows telemetry tracking real charging sessions, active/idle time, and personalizing ML predictions.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handlePollNow}
            disabled={polling}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 18px',
              background: '#0284c7',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '13px',
              cursor: polling ? 'not-allowed' : 'pointer',
              opacity: polling ? 0.7 : 1,
            }}
          >
            <Icon name="refresh" size={16} />
            {polling ? 'Sampling...' : 'Poll Sensor Now'}
          </button>
        </div>
      </div>

      {/* Top 4 Metric KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {/* Card 1: Data Source */}
        <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
          <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
            Active Data Source
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38bdf8' }} />
            REAL WINDOWS
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            Host: {status.device_battery?.source || 'WINDOWS_SYSTEM'}
          </div>
        </div>

        {/* Card 2: Real Sessions Collected */}
        <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
          <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
            Real Sessions Collected
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: '#f8fafc' }}>
            {status.real_sessions_count} <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 500 }}>/ 7 target</span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            {7 - status.real_sessions_count > 0
              ? `${7 - status.real_sessions_count} more session(s) until Personalized`
              : 'Full Personalization Active'}
          </div>
        </div>

        {/* Card 3: Personalization Tier */}
        <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
          <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
            Personalization Stage
          </div>
          <div style={{ display: 'inline-block', padding: '4px 10px', borderRadius: '6px', background: stageInfo.bg, color: stageInfo.color, fontWeight: 700, fontSize: '14px' }}>
            {status.personalization_stage}
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
            {stageInfo.label}
          </div>
        </div>

        {/* Card 4: Live Host Battery */}
        <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
          <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
            Live Device Battery
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: status.device_battery?.is_plugged_in ? '#10b981' : '#f8fafc' }}>
            {status.device_battery?.battery_percent !== null ? `${status.device_battery?.battery_percent}%` : '--%'}
            <span style={{ fontSize: '13px', fontWeight: 500, marginLeft: '8px', color: '#94a3b8' }}>
              {status.device_battery?.is_plugged_in ? '(Charging)' : '(On Battery)'}
            </span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            Last poll: {status.last_poll_time ? formatTelemetryTimestamp(status.last_poll_time, { showSeconds: true, showDateContext: true }) : '--:--'}
          </div>
        </div>
      </div>

      {/* Personalization Progress & Cold Start Milestone */}
      <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: '#f8fafc' }}>
            ML Personalization Learning Progress
          </div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: '#38bdf8' }}>
            {status.personalization_progress_pct}% ({status.real_sessions_count} / 7)
          </div>
        </div>

        {/* Progress bar track */}
        <div style={{ width: '100%', height: '8px', background: '#0f172a', borderRadius: '4px', overflow: 'hidden', marginBottom: '20px' }}>
          <div
            style={{
              width: `${Math.min(100, status.personalization_progress_pct)}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #f59e0b 0%, #38bdf8 50%, #10b981 100%)',
              transition: 'width 0.4s ease',
            }}
          />
        </div>

        {/* Milestone Steps */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div style={{ padding: '12px', background: status.real_sessions_count < 3 ? 'rgba(245, 158, 11, 0.1)' : '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
            <div style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 700 }}>STAGE 1: 0–2 SESSIONS</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc', marginTop: '4px' }}>Global Baseline</div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>Uses circular population priors while initial habits are collected.</div>
          </div>

          <div style={{ padding: '12px', background: status.real_sessions_count >= 3 && status.real_sessions_count < 7 ? 'rgba(56, 189, 248, 0.1)' : '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
            <div style={{ fontSize: '12px', color: '#38bdf8', fontWeight: 700 }}>STAGE 2: 3–6 SESSIONS</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc', marginTop: '4px' }}>Blended Adaptation</div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>Dynamically weights population baseline with personal circular history.</div>
          </div>

          <div style={{ padding: '12px', background: status.real_sessions_count >= 7 ? 'rgba(16, 185, 129, 0.1)' : '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
            <div style={{ fontSize: '12px', color: '#10b981', fontWeight: 700 }}>STAGE 3: 7+ SESSIONS</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc', marginTop: '4px' }}>Full Personalization</div>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>Purely user-driven circular unplug prediction and optimized charging windows.</div>
          </div>
        </div>
      </div>

      {/* Privacy Guarantee Card */}
      <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '12px', padding: '18px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0f172a', fontWeight: 'bold' }}>
            ✓
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: '#10b981' }}>
            Privacy-First Architecture Guarantee
          </div>
        </div>
        <p style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#cbd5e1', lineHeight: '1.5' }}>
          Smart Battery AI is engineered to protect user privacy. All data is collected and stored exclusively on this local computer in SQLite:
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', fontSize: '12px', color: '#94a3b8' }}>
          <div>🛡️ <strong>Zero Keystrokes:</strong> No typing or keystroke logging.</div>
          <div>🛡️ <strong>Zero Screen Content:</strong> No window titles, apps, or URLs.</div>
          <div>🛡️ <strong>Aggregate Idle Only:</strong> Measures idle seconds via Windows API.</div>
          <div>🛡️ <strong>100% Local Storage:</strong> Stored strictly in local SQLite database.</div>
        </div>
      </div>

      {/* Windows Background Collector Command Box */}
      <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc', marginBottom: '8px' }}>
          Background Telemetry Service (Browser-Independent)
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', margin: '0 0 12px 0' }}>
          You do not need to keep the browser open. Run the collector script in the background to automatically record real charging cycles:
        </p>
        <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '13px', color: '#38bdf8', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>python scripts/run_windows_collector.py</span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>Interval: 120s</span>
        </div>
      </div>

      {/* Real Charging Sessions Table */}
      <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
            Collected Real Sessions ({realSessions.length})
          </h3>
          <span style={{ fontSize: '12px', color: '#64748b' }}>
            Source: REAL_WINDOWS
          </span>
        </div>

        {realSessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px 16px', background: '#0f172a', borderRadius: '8px', border: '1px dashed #334155' }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
              No real completed charging sessions recorded yet.
            </div>
            <div style={{ fontSize: '12px', color: '#64748b', maxWidth: '440px', margin: '0 auto' }}>
              Plug in your laptop to start an automatic real session. When you later unplug, the session will be finalized with actual duration, start SoC, and active computer usage.
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                  <th style={{ padding: '10px 12px' }}>Date</th>
                  <th style={{ padding: '10px 12px' }}>Plug Time</th>
                  <th style={{ padding: '10px 12px' }}>Unplug Time</th>
                  <th style={{ padding: '10px 12px' }}>Duration</th>
                  <th style={{ padding: '10px 12px' }}>Start → End SoC</th>
                  <th style={{ padding: '10px 12px' }}>Active Usage</th>
                  <th style={{ padding: '10px 12px' }}>Idle Time</th>
                  <th style={{ padding: '10px 12px' }}>Tag</th>
                </tr>
              </thead>
              <tbody>
                {realSessions.map((s) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td style={{ padding: '10px 12px', color: '#f8fafc' }}>{formatLocalDate(s.start_time)}</td>
                    <td style={{ padding: '10px 12px', color: '#38bdf8' }}>{formatLocalTime(s.start_time, { hour12: true })}</td>
                    <td style={{ padding: '10px 12px', color: s.end_time ? '#10b981' : '#f59e0b' }}>
                      {s.end_time ? formatLocalTime(s.end_time, { hour12: true }) : 'Charging Now'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#f8fafc' }}>
                      {s.charging_duration_minutes ? `${s.charging_duration_minutes} min` : '--'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#f8fafc' }}>
                      {s.start_battery_percent}% → {s.end_battery_percent !== null ? `${s.end_battery_percent}%` : '--'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {s.screen_usage_minutes ? `${s.screen_usage_minutes} min` : '0 min'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {s.idle_usage_minutes ? `${s.idle_usage_minutes} min` : '0 min'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
                        REAL_WINDOWS
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Periodic Telemetry Samples Feed */}
      {samples.length > 0 && (
        <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc' }}>
              Recent Periodic Telemetry Heartbeats (Rate-Limited)
            </div>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
              Browser Timezone: <strong style={{ color: '#38bdf8' }}>{localTimezone}</strong>
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                  <th style={{ padding: '8px 10px' }}>Sample Time</th>
                  <th style={{ padding: '8px 10px' }}>Battery SoC</th>
                  <th style={{ padding: '8px 10px' }}>Power State</th>
                  <th style={{ padding: '8px 10px' }}>User State</th>
                  <th style={{ padding: '8px 10px' }}>Idle Duration</th>
                  <th style={{ padding: '8px 10px' }}>Sleep Gap</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((s) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid #0f172a' }}>
                    <td style={{ padding: '8px 10px', color: '#f8fafc', fontWeight: 500 }}>
                      {formatTelemetryTimestamp(s.timestamp, { showSeconds: true, showDateContext: true })}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#38bdf8', fontWeight: 600 }}>{s.battery_percent}%</td>
                    <td style={{ padding: '8px 10px' }}>
                      <span style={{ color: s.is_plugged_in ? '#10b981' : '#94a3b8', fontWeight: 600 }}>
                        {s.is_plugged_in ? 'Plugged (AC)' : 'On Battery'}
                      </span>
                    </td>
                    <td style={{ padding: '8px 10px', color: s.is_user_active ? '#10b981' : '#f59e0b' }}>
                      {s.is_user_active ? 'Active' : 'Idle'}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#94a3b8' }}>{s.idle_duration_seconds}s</td>
                    <td style={{ padding: '8px 10px', color: s.sleep_gap_seconds > 0 ? '#f59e0b' : '#64748b' }}>
                      {s.sleep_gap_seconds > 0 ? `${s.sleep_gap_seconds}s` : 'None'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
