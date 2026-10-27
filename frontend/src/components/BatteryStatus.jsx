import React from 'react';

export default function BatteryStatus({ batteryPct = 78, isCharging = true, phase = 'Holding at 80%' }) {
  const getBatteryColor = (pct) => {
    if (pct > 70) return '#10b981';
    if (pct > 25) return '#3b82f6';
    return '#ef4444';
  };

  return (
    <div className="card">
      <h2 className="card-title">Live Battery Telemetry</h2>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginTop: '1rem' }}>
        <div style={{
          width: '100px',
          height: '50px',
          border: '3px solid #64748b',
          borderRadius: '8px',
          position: 'relative',
          padding: '4px',
          display: 'flex',
          alignItems: 'center'
        }}>
          <div style={{
            width: `${batteryPct}%`,
            height: '100%',
            backgroundColor: getBatteryColor(batteryPct),
            borderRadius: '4px',
            transition: 'width 0.5s ease',
          }} />
          <div style={{
            position: 'absolute',
            right: '-10px',
            top: '12px',
            width: '6px',
            height: '20px',
            backgroundColor: '#64748b',
            borderRadius: '0 3px 3px 0'
          }} />
        </div>
        <div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{batteryPct}%</div>
          <span className={`badge ${isCharging ? 'badge-green' : 'badge-amber'}`}>
            {isCharging ? '⚡ Connected' : 'Unplugged'}
          </span>
        </div>
      </div>
      <div style={{ marginTop: '1.25rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        Current State: <strong style={{ color: '#fff' }}>{phase}</strong>
      </div>
    </div>
  );
}
