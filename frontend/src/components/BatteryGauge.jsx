import React from 'react';
import { Icon } from './Icons';

export default function BatteryGauge({
  soc = 50,
  voltage = 3.98,
  temperature = 32.5,
  isCharging = false,
  isLiveDevice = false,
  source = 'WINDOWS_SYSTEM',
  secondsLeft = null,
  mode = 'DELAYED_CHARGE',
  targetSoc = 80,
}) {
  const getBatteryColor = (pct) => {
    if (pct <= 20) return '#ef4444'; // Red
    if (pct <= 60) return '#f59e0b'; // Amber
    if (pct <= 85) return '#38bdf8'; // Blue/Cyan
    return '#10b981'; // Emerald Green
  };

  const currentColor = getBatteryColor(soc);

  const formatRuntime = (secs) => {
    if (!secs || secs <= 0) return null;
    const hrs = Math.floor(secs / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    if (hrs > 0) return `${hrs}h ${mins}m left`;
    return `${mins}m left`;
  };

  const runtimeStr = formatRuntime(secondsLeft);

  return (
    <div className="card battery-gauge-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 className="card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Icon name="battery" size={20} color="#38bdf8" />
          {isLiveDevice ? 'Live Windows Battery' : 'Battery Telemetry'}
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          {isLiveDevice && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                padding: '0.2rem 0.5rem',
                borderRadius: '9999px',
                fontSize: '0.7rem',
                fontWeight: 700,
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#38bdf8' }} />
              LIVE
            </span>
          )}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.2rem 0.6rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 600,
              backgroundColor: isCharging ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
              color: isCharging ? '#10b981' : '#94a3b8',
              border: `1px solid ${isCharging ? 'rgba(16, 185, 129, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`,
            }}
          >
            {isCharging ? (
              <>
                <Icon name="zap" size={13} color="#10b981" /> Connected
              </>
            ) : (
              'On Battery'
            )}
          </span>
        </div>
      </div>

      {/* Battery Graphic + Big Percentage */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.75rem', padding: '1rem 0' }}>
        <div
          style={{
            position: 'relative',
            width: '130px',
            height: '64px',
            border: '3px solid #475569',
            borderRadius: '12px',
            padding: '4px',
            backgroundColor: '#0f172a',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {/* Fill level */}
          <div
            style={{
              width: `${Math.min(100, Math.max(0, soc))}%`,
              height: '100%',
              backgroundColor: currentColor,
              borderRadius: '6px',
              transition: 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
              backgroundImage: 'linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {isCharging && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
                  animation: 'pulse 1.8s infinite',
                }}
              />
            )}
          </div>

          {/* Battery terminal pip */}
          <div
            style={{
              position: 'absolute',
              right: '-11px',
              top: '18px',
              width: '7px',
              height: '24px',
              backgroundColor: '#475569',
              borderRadius: '0 4px 4px 0',
            }}
          />

          {/* Target marker line if target is less than 100 */}
          {targetSoc < 100 && (
            <div
              title={`Target SoC: ${targetSoc}%`}
              style={{
                position: 'absolute',
                left: `${targetSoc}%`,
                top: '2px',
                bottom: '2px',
                width: '2px',
                backgroundColor: '#ffffff',
                opacity: 0.7,
                boxShadow: '0 0 4px rgba(255,255,255,0.8)',
              }}
            />
          )}
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '2.5rem', fontWeight: 800, color: '#f8fafc', lineHeight: 1 }}>
              {soc}
            </span>
            <span style={{ fontSize: '1.25rem', fontWeight: 600, color: '#94a3b8' }}>%</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
            Target: <strong style={{ color: '#38bdf8' }}>{targetSoc}%</strong>
            {runtimeStr && (
              <span style={{ marginLeft: '0.5rem', color: '#10b981', fontSize: '0.75rem' }}>
                ({runtimeStr})
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Secondary Telemetry Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0.75rem',
          marginTop: '1rem',
          paddingTop: '1rem',
          borderTop: '1px solid #334155',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ color: '#38bdf8' }}>
            <Icon name="zap" size={16} />
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
              {isLiveDevice ? 'Power State' : 'Cell Voltage'}
            </div>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e2e8f0' }}>
              {isLiveDevice ? (isCharging ? 'AC Connected' : 'Discharging') : `${voltage} V`}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ color: temperature > 38 ? '#ef4444' : '#10b981' }}>
            <Icon name="thermometer" size={16} />
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
              {isLiveDevice ? 'Hardware Sensor' : 'Battery Temp'}
            </div>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e2e8f0' }}>
              {isLiveDevice ? (source || 'WINDOWS_SYSTEM') : `${temperature}°C`}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
