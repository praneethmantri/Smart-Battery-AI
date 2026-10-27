import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { getChargingHistory } from '../services/api';
import { Icon } from '../components/Icons';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function ChargingHistoryPage() {
  const { selectedUserId, currentUser } = useApp();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(25);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getChargingHistory(selectedUserId, limit)
      .then((data) => {
        if (isMounted) {
          setSessions(data || []);
          setLoading(false);
          setPage(1);
        }
      })
      .catch(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [selectedUserId, limit]);

  // Pagination calculation
  const totalPages = Math.ceil(sessions.length / pageSize) || 1;
  const paginatedSessions = sessions.slice((page - 1) * pageSize, page * pageSize);

  // Summary Metrics
  const avgDuration = sessions.length > 0
    ? (sessions.reduce((acc, s) => acc + (s.charging_duration_minutes || 0), 0) / sessions.length).toFixed(0)
    : 0;
  const avgStartSoc = sessions.length > 0
    ? (sessions.reduce((acc, s) => acc + (s.start_battery_percent || 0), 0) / sessions.length).toFixed(1)
    : 0;
  const avgEndSoc = sessions.length > 0
    ? (sessions.reduce((acc, s) => acc + (s.end_battery_percent || 0), 0) / sessions.length).toFixed(1)
    : 0;
  const avgTemp = sessions.length > 0
    ? (sessions.reduce((acc, s) => acc + (s.average_temperature || 0), 0) / sessions.length).toFixed(1)
    : 0;

  // Chart data for Start vs End SOC
  const chartSessions = [...sessions].reverse().slice(-15);
  const chartData = {
    labels: chartSessions.map((s, idx) => {
      if (s.start_time) {
        const d = new Date(s.start_time);
        return `${d.getMonth() + 1}/${d.getDate()}`;
      }
      return `#${idx + 1}`;
    }),
    datasets: [
      {
        label: 'Start Battery (%)',
        data: chartSessions.map((s) => s.start_battery_percent),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.15)',
        tension: 0.2,
        pointRadius: 4,
      },
      {
        label: 'End Battery (%)',
        data: chartSessions.map((s) => s.end_battery_percent),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        tension: 0.2,
        pointRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#cbd5e1', boxWidth: 12 },
      },
      tooltip: {
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
      },
    },
    scales: {
      y: {
        min: 0,
        max: 100,
        ticks: { color: '#94a3b8', callback: (v) => `${v}%` },
        grid: { color: '#1e293b' },
      },
      x: {
        ticks: { color: '#94a3b8' },
        grid: { color: '#1e293b' },
      },
    },
  };

  return (
    <div className="page-container">
      {/* Header bar */}
      <div className="page-header">
        <div>
          <h2 className="section-title">Charging Session History</h2>
          <p className="section-desc">
            Showing recorded charging sessions for {currentUser.name} (User ID: {selectedUserId}).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <label style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Fetch Limit:</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="user-select-dropdown"
            style={{ minWidth: '80px' }}
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="metrics-grid">
        <div className="card" style={{ padding: '1rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Total Sessions</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
            {sessions.length}
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Retrieved from database</span>
        </div>

        <div className="card" style={{ padding: '1rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Avg Duration</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.25rem' }}>
            {avgDuration} <span style={{ fontSize: '0.85rem' }}>min</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>~{(avgDuration / 60).toFixed(1)} hrs/session</span>
        </div>

        <div className="card" style={{ padding: '1rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Avg Start / End SoC</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981', marginTop: '0.25rem' }}>
            {avgStartSoc}% <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>→</span> {avgEndSoc}%
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Mean charge delta: {(avgEndSoc - avgStartSoc).toFixed(0)}%</span>
        </div>

        <div className="card" style={{ padding: '1rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Mean Temperature</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: avgTemp > 35 ? '#f59e0b' : '#38bdf8', marginTop: '0.25rem' }}>
            {avgTemp}°C
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Thermal operating condition</span>
        </div>
      </div>

      {/* History Trend Chart */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 className="card-title">Recent Session Battery SoC Progression</h3>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem' }}>
          Historical start state of charge (amber) and unplug state of charge (green) across recent charging sessions.
        </p>
        {sessions.length > 0 ? (
          <div style={{ height: '220px', width: '100%' }}>
            <Line data={chartData} options={chartOptions} />
          </div>
        ) : (
          <div style={{ height: '100px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.85rem' }}>
            No completed charging sessions recorded for this user yet. Plug in to record telemetry.
          </div>
        )}
      </div>

      {/* Data Table */}
      <div className="card" style={{ overflowX: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 className="card-title" style={{ margin: 0 }}>Session Records</h3>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Page {page} of {totalPages} ({sessions.length} total)
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
            Loading historical sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
            No completed sessions found for this user in database.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Start Time</th>
                <th>End / Unplug</th>
                <th>Start SoC</th>
                <th>End SoC</th>
                <th>Duration</th>
                <th>Charger</th>
                <th>Temp</th>
                <th>Day</th>
              </tr>
            </thead>
            <tbody>
              {paginatedSessions.map((s) => {
                const startStr = s.start_time
                  ? new Date(s.start_time).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                  : '—';
                const endStr = s.end_time
                  ? new Date(s.end_time).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                  : 'Active';
                const dayName = s.day_of_week !== undefined && s.day_of_week !== null
                  ? DAYS[s.day_of_week % 7]
                  : '—';

                return (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600, color: '#38bdf8' }}>#{s.id}</td>
                    <td>{startStr}</td>
                    <td>{endStr}</td>
                    <td>
                      <span className="soc-tag">{s.start_battery_percent?.toFixed(1) || '0'}%</span>
                    </td>
                    <td>
                      <span className="soc-tag high">{s.end_battery_percent?.toFixed(1) || '—'}%</span>
                    </td>
                    <td>{s.charging_duration_minutes ? `${s.charging_duration_minutes.toFixed(0)}m` : '—'}</td>
                    <td>
                      <span className={`badge ${s.charger_type === 'fast' ? 'badge-blue' : 'badge-neutral'}`}>
                        {s.charger_type || 'standard'}
                      </span>
                    </td>
                    <td>{s.average_temperature ? `${s.average_temperature.toFixed(1)}°C` : '—'}</td>
                    <td>{dayName}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #334155' }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
            >
              Previous
            </button>
            <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.8rem', color: '#94a3b8', padding: '0 0.5rem' }}>
              Page {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
