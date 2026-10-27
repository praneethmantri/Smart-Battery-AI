import React from 'react';
import { Icon } from './Icons';

export default function ScheduleTimeline({
  plugTime = '22:30',
  plugDatetime,
  recommendedStartTime = '05:15',
  recommendedStartDatetime,
  estimatedFinishTime = '07:15',
  estimatedFinishDatetime,
  predictedUnplugTime = '07:35',
  predictedUnplugDatetime,
  currentSoc = 24,
  targetSoc = 80,
  mode = 'DELAYED_CHARGE',
}) {
  const isDelayed = mode === 'DELAYED_CHARGE';

  // Helper to determine if a scheduled step crosses into the next day / tomorrow
  const checkRollover = (stepDt, stepTimeStr, baseDt, baseTimeStr) => {
    if (stepDt && baseDt) {
      try {
        const d1 = new Date(stepDt);
        const d0 = new Date(baseDt);
        if (!isNaN(d1.getTime()) && !isNaN(d0.getTime())) {
          return d1.toDateString() !== d0.toDateString();
        }
      } catch {
        // Fallback to clock string comparison below
      }
    }
    if (stepTimeStr && baseTimeStr) {
      const [h1, m1] = stepTimeStr.split(':').map(Number);
      const [h0, m0] = baseTimeStr.split(':').map(Number);
      if (!isNaN(h1) && !isNaN(h0)) {
        return (h1 * 60 + m1) < (h0 * 60 + m0);
      }
    }
    return false;
  };

  const startRollover = checkRollover(recommendedStartDatetime, recommendedStartTime, plugDatetime, plugTime);
  const finishRollover = checkRollover(estimatedFinishDatetime, estimatedFinishTime, plugDatetime, plugTime);
  const unplugRollover = checkRollover(predictedUnplugDatetime, predictedUnplugTime, plugDatetime, plugTime);

  const badgeStyle = (color, bg) => ({
    fontSize: '0.65rem',
    fontWeight: 600,
    color: color,
    backgroundColor: bg,
    border: `1px solid ${color}40`,
    padding: '0.1rem 0.35rem',
    borderRadius: '4px',
    marginLeft: '0.35rem',
    display: 'inline-block',
    verticalAlign: 'middle',
  });

  return (
    <div style={{ marginTop: '1.25rem' }}>
      <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Charging Schedule Sequence
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '0.75rem',
          position: 'relative',
        }}
      >
        {/* Step 1: Plug-in */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#94a3b8', fontSize: '0.75rem' }}>
            <Icon name="clock" size={14} /> Plug-In
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>{plugTime}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>SoC: {currentSoc}%</div>
        </div>

        {/* Step 2: Phase 1 / Delay */}
        <div
          style={{
            backgroundColor: isDelayed ? 'rgba(16, 185, 129, 0.08)' : '#0f172a',
            border: `1px solid ${isDelayed ? 'rgba(16, 185, 129, 0.3)' : '#334155'}`,
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: isDelayed ? '#10b981' : '#38bdf8', fontSize: '0.75rem' }}>
            <Icon name="shield" size={14} /> {isDelayed ? 'Rest / Delay' : 'Charge Active'}
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: isDelayed ? '#10b981' : '#f8fafc' }}>
            {isDelayed ? 'Idle Hold' : 'Immediate'}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
            {isDelayed ? 'Avoid High-SoC Stress' : 'Continuous'}
          </div>
        </div>

        {/* Step 3: Start Active Charge */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#38bdf8', fontSize: '0.75rem' }}>
            <Icon name="zap" size={14} /> Start Charge
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
            {recommendedStartTime}
            {startRollover && <span style={badgeStyle('#38bdf8', 'rgba(56, 189, 248, 0.15)')}>Next Day</span>}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>To target {targetSoc}%</div>
        </div>

        {/* Step 4: Ready at Target */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#10b981', fontSize: '0.75rem' }}>
            <Icon name="check" size={14} /> Target Ready
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#10b981', display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
            {estimatedFinishTime}
            {finishRollover && <span style={badgeStyle('#10b981', 'rgba(16, 185, 129, 0.15)')}>Next Day</span>}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Target {targetSoc}% Reached</div>
        </div>

        {/* Step 5: Predicted Unplug */}
        <div
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.08)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#38bdf8', fontSize: '0.75rem' }}>
            <Icon name="clock" size={14} /> Predicted Unplug
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
            {predictedUnplugTime}
            {unplugRollover && <span style={badgeStyle('#38bdf8', 'rgba(56, 189, 248, 0.15)')}>Next Day</span>}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>+20 min safety margin</div>
        </div>
      </div>
    </div>
  );
}
