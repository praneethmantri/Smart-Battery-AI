import React from 'react';
import { Icon } from './Icons';

export default function MetricCard({
  title,
  value,
  subtitle,
  icon,
  badge,
  badgeType = 'neutral',
  accentColor = '#38bdf8',
}) {
  const badgeColors = {
    green: { bg: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: 'rgba(16, 185, 129, 0.3)' },
    blue: { bg: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' },
    amber: { bg: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
    purple: { bg: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: 'rgba(168, 85, 247, 0.3)' },
    neutral: { bg: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)' },
  };

  const badgeStyle = badgeColors[badgeType] || badgeColors.neutral;

  return (
    <div
      className="card metric-card"
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderLeft: `3px solid ${accentColor}`,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 500, letterSpacing: '0.025em' }}>
            {title}
          </span>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem', letterSpacing: '-0.02em' }}>
            {value}
          </div>
        </div>

        {icon && (
          <div
            style={{
              padding: '0.5rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
              color: accentColor,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon name={icon} size={22} color={accentColor} />
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{subtitle}</span>
        {badge && (
          <span
            style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              padding: '0.15rem 0.5rem',
              borderRadius: '9999px',
              backgroundColor: badgeStyle.bg,
              color: badgeStyle.color,
              border: `1px solid ${badgeStyle.border}`,
            }}
          >
            {badge}
          </span>
        )}
      </div>
    </div>
  );
}
