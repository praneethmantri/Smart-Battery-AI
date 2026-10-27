import React from 'react';

export function ModeBadge({ mode }) {
  const modeStyles = {
    DELAYED_CHARGE: {
      bg: 'rgba(16, 185, 129, 0.18)',
      color: '#34d399',
      border: 'rgba(16, 185, 129, 0.4)',
      label: 'Optimal Delayed Charge',
    },
    CHARGE_NOW: {
      bg: 'rgba(59, 130, 246, 0.18)',
      color: '#60a5fa',
      border: 'rgba(59, 130, 246, 0.4)',
      label: 'Charge Now (Immediate)',
    },
    CONSERVATIVE_CHARGE: {
      bg: 'rgba(245, 158, 11, 0.18)',
      color: '#fbbf24',
      border: 'rgba(245, 158, 11, 0.4)',
      label: 'Conservative Charge',
    },
    HOLD_AT_THRESHOLD: {
      bg: 'rgba(168, 85, 247, 0.18)',
      color: '#c084fc',
      border: 'rgba(168, 85, 247, 0.4)',
      label: 'Hold at 80% Threshold',
    },
    MAINTAIN_LEVEL: {
      bg: 'rgba(148, 163, 184, 0.18)',
      color: '#cbd5e1',
      border: 'rgba(148, 163, 184, 0.4)',
      label: 'Maintain Current Level',
    },
  };

  const style = modeStyles[mode] || {
    bg: 'rgba(100, 116, 139, 0.2)',
    color: '#94a3b8',
    border: 'rgba(100, 116, 139, 0.4)',
    label: mode || 'Unknown',
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: '0.3rem 0.75rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.025em',
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
      }}
    >
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: style.color }} />
      {style.label}
    </span>
  );
}

export function SourceBadge({ source }) {
  const sourceMap = {
    PERSONALIZED: {
      label: 'PERSONALIZED (7+ sessions)',
      bg: 'rgba(16, 185, 129, 0.15)',
      color: '#10b981',
      border: 'rgba(16, 185, 129, 0.35)',
    },
    BLENDED: {
      label: 'BLENDED (3-6 sessions)',
      bg: 'rgba(245, 158, 11, 0.15)',
      color: '#f59e0b',
      border: 'rgba(245, 158, 11, 0.35)',
    },
    GLOBAL_BASELINE: {
      label: 'GLOBAL BASELINE (0-2 sessions)',
      bg: 'rgba(59, 130, 246, 0.15)',
      color: '#38bdf8',
      border: 'rgba(59, 130, 246, 0.35)',
    },
  };

  const current = sourceMap[source] || {
    label: source || 'MODEL',
    bg: 'rgba(148, 163, 184, 0.15)',
    color: '#94a3b8',
    border: 'rgba(148, 163, 184, 0.35)',
  };

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.25rem 0.65rem',
        borderRadius: '6px',
        fontSize: '0.7rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        backgroundColor: current.bg,
        color: current.color,
        border: `1px solid ${current.border}`,
      }}
    >
      {current.label}
    </span>
  );
}

export function ConfidenceBadge({ score, level }) {
  let color = '#10b981';
  let bg = 'rgba(16, 185, 129, 0.15)';
  let border = 'rgba(16, 185, 129, 0.3)';

  const normalizedScore = score !== undefined ? score : (level === 'HIGH' ? 0.9 : level === 'MEDIUM' ? 0.65 : 0.4);
  const normalizedLevel = level || (normalizedScore >= 0.75 ? 'HIGH' : normalizedScore >= 0.55 ? 'MEDIUM' : 'LOW');

  if (normalizedLevel === 'LOW') {
    color = '#ef4444';
    bg = 'rgba(239, 68, 68, 0.15)';
    border = 'rgba(239, 68, 68, 0.3)';
  } else if (normalizedLevel === 'MEDIUM') {
    color = '#f59e0b';
    bg = 'rgba(245, 158, 11, 0.15)';
    border = 'rgba(245, 158, 11, 0.3)';
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: '0.25rem 0.6rem',
        borderRadius: '6px',
        fontSize: '0.75rem',
        fontWeight: 600,
        backgroundColor: bg,
        color: color,
        border: `1px solid ${border}`,
      }}
    >
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: color }} />
      {normalizedLevel} ({(normalizedScore * 100).toFixed(0)}%)
    </span>
  );
}
