import React from 'react';

export default function RecommendationCard({ recommendation }) {
  if (!recommendation) {
    return (
      <div className="card">
        <h2 className="card-title">AI Charging Recommendation</h2>
        <p style={{ color: 'var(--text-muted)' }}>No active charging schedule generated yet.</p>
      </div>
    );
  }

  const {
    mode,
    phase_1_fast_charge_until,
    hold_at_pct,
    phase_2_topoff_start,
    estimated_ready_time,
    confidence_score,
  } = recommendation;

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="card-title" style={{ margin: 0 }}>AI Smart Plan</h2>
        <span className="badge badge-blue">{mode}</span>
      </div>

      <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
        ML Confidence: <strong>{(confidence_score * 100).toFixed(0)}%</strong>
      </p>

      <ul className="timeline">
        <li className="timeline-item">
          <span>Phase 1: Charge to {hold_at_pct}%</span>
          <strong>{phase_1_fast_charge_until ? new Date(phase_1_fast_charge_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Immediate'}</strong>
        </li>
        <li className="timeline-item">
          <span>Phase 2: Hold at {hold_at_pct}% (SEI Preservation)</span>
          <span style={{ color: 'var(--accent-green)' }}>Active Idle Hold</span>
        </li>
        <li className="timeline-item">
          <span>Phase 3: Top-off to 100% Starts</span>
          <strong>{phase_2_topoff_start ? new Date(phase_2_topoff_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Continuous'}</strong>
        </li>
        <li className="timeline-item">
          <span>Target Ready By</span>
          <strong style={{ color: 'var(--accent-blue)' }}>
            {estimated_ready_time ? new Date(estimated_ready_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Unplug'}
          </strong>
        </li>
      </ul>
    </div>
  );
}
