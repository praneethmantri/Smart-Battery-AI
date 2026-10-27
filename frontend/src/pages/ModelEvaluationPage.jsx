import React from 'react';
import { EVALUATION_METRICS } from '../data/mockData';
import { Icon } from '../components/Icons';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function ModelEvaluationPage() {
  const { global, personalized, modelComparison, profilesBreakdown, simulation } = EVALUATION_METRICS;

  const comparisonChartData = {
    labels: modelComparison.map((m) => m.name),
    datasets: [
      {
        label: 'Mean Absolute Error (Minutes) - Lower is Better',
        data: modelComparison.map((m) => m.mae),
        backgroundColor: modelComparison.map((m) => m.color),
        borderRadius: 6,
      },
    ],
  };

  const comparisonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
        callbacks: {
          label: (ctx) => ` MAE: ${ctx.parsed.y.toFixed(2)} minutes`,
        },
      },
    },
    scales: {
      y: {
        title: { display: true, text: 'MAE (Minutes)', color: '#94a3b8' },
        ticks: { color: '#94a3b8' },
        grid: { color: '#1e293b' },
      },
      x: {
        ticks: { color: '#94a3b8', maxRotation: 20 },
        grid: { color: '#1e293b' },
      },
    },
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="section-title">Model Evaluation & Research Benchmarks</h2>
          <p className="section-desc">
            Rigorous experimental results evaluating whether personalized historical modeling improves expected unplug-time prediction accuracy.
          </p>
        </div>
      </div>

      {/* Head-to-Head Comparison Cards */}
      <div className="metrics-grid">
        <div className="card" style={{ borderLeft: '3px solid #38bdf8' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Global Baseline (GBR)</span>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.25rem' }}>
            {global.maeMinutes} <span style={{ fontSize: '1rem', fontWeight: 500 }}>min</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.5rem' }}>
            Median Error: <strong>{global.medianMinutes}m</strong>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Within ±30m: <strong>{global.within30MinPct}%</strong> • ±60m: <strong>{global.within60MinPct}%</strong>
          </div>
        </div>

        <div className="card" style={{ borderLeft: '3px solid #10b981' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Personalized Hybrid RF</span>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#10b981', marginTop: '0.25rem' }}>
            {personalized.maeMinutes} <span style={{ fontSize: '1rem', fontWeight: 500 }}>min</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.5rem' }}>
            Error Reduction: <strong style={{ color: '#10b981' }}>+{personalized.improvementPct}%</strong>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Within ±30m: <strong>{personalized.within30MinPct}%</strong> • ±60m: <strong>{personalized.within60MinPct}%</strong>
          </div>
        </div>

        <div className="card" style={{ borderLeft: '3px solid #a855f7' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Users Benefited</span>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#a855f7', marginTop: '0.25rem' }}>
            {personalized.usersImprovedPct}%
          </div>
          <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.5rem' }}>
            71 of 100 cohorts improved
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Statistically significant Wilcoxon test p &lt; 0.001
          </div>
        </div>

        <div className="card" style={{ borderLeft: '3px solid #f59e0b' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>High-SoC Dwell Reduction</span>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#f59e0b', marginTop: '0.25rem' }}>
            {simulation.reductionPercent}%
          </div>
          <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.5rem' }}>
            {simulation.baselineEarlyIdleMinutes}m → {simulation.smartDelayIdleMinutes}m idle
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            317.7 minutes less stress/session
          </div>
        </div>
      </div>

      {/* Model Benchmark Bar Chart */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 className="card-title">Model Architecture Comparison (MAE in Minutes)</h3>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem' }}>
          Evaluating baseline models from simple naive heuristic to personalized ensemble. Personalized Hybrid RF achieves lowest overall prediction error.
        </p>
        <div style={{ height: '260px', width: '100%' }}>
          <Bar data={comparisonChartData} options={comparisonChartOptions} />
        </div>
      </div>

      {/* Profile Breakdown Table */}
      <div className="card" style={{ marginBottom: '1.5rem', overflowX: 'auto' }}>
        <h3 className="card-title">Behavioral Profile Breakdown</h3>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem' }}>
          Personalization impact categorized across 6 user archetypes. Regular overnight and weekend shifters exhibit the greatest accuracy gains.
        </p>

        <table className="data-table">
          <thead>
            <tr>
              <th>Profile Cohort</th>
              <th>Behavioral Description</th>
              <th>Global MAE</th>
              <th>Personalized MAE</th>
              <th>Error Delta</th>
              <th>Category Assessment</th>
            </tr>
          </thead>
          <tbody>
            {profilesBreakdown.map((row) => (
              <tr key={row.profile}>
                <td style={{ fontWeight: 600, color: '#f8fafc' }}>{row.profile}</td>
                <td style={{ color: '#94a3b8' }}>{row.description}</td>
                <td>{row.globalMae}m</td>
                <td style={{ color: '#10b981', fontWeight: 600 }}>{row.persMae}m</td>
                <td style={{ color: '#10b981', fontWeight: 700 }}>-{row.improvementPct}%</td>
                <td>
                  <span className="badge badge-green">{row.tag}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recommendation Dwell Time Benchmark & Scientific Honesty Disclaimer Box */}
      <div className="card" style={{ border: '1px solid rgba(56, 189, 248, 0.3)', backgroundColor: 'rgba(15, 23, 42, 0.75)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div style={{ color: '#38bdf8' }}>
            <Icon name="shield" size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
              Optimization Strategy Benchmark: High-SoC Waiting Time Simulation
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#38bdf8' }}>
              89.89% Reduction in Early High-Voltage Dwell Time (353.4m → 35.7m)
            </span>
          </div>
        </div>

        <div className="disclaimer-alert">
          <div style={{ color: '#f59e0b', flexShrink: 0 }}>
            <Icon name="alert" size={20} />
          </div>
          <div style={{ fontSize: '0.825rem', color: '#cbd5e1', lineHeight: 1.6 }}>
            <strong style={{ color: '#fbbf24' }}>Scientific Disclaimer & R&D Boundary: </strong>
            {simulation.disclaimer}
          </div>
        </div>
      </div>
    </div>
  );
}
