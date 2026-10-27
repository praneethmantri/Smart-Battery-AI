import React from 'react';
import { useApp } from '../context/AppContext';
import { Icon } from './Icons';

export default function TopBar() {
  const {
    activeTab,
    selectedUserId,
    setSelectedUserId,
    availableUsers,
    currentUser,
    backendHealth,
    refreshUserData,
    currentTime,
  } = useApp();

  const tabTitles = {
    dashboard: 'System Overview & Telemetry',
    history: 'Charging Session History',
    prediction: 'AI Expected Unplug-Time Prediction',
    recommendation: 'Personalized Charging Optimization',
    analytics: 'Charging Behavior Analytics',
    evaluation: 'Model Evaluation & Research Benchmarks',
    status: 'System Health & Architecture Status',
  };

  const isHealthy = backendHealth?.status === 'healthy';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <h2 className="page-title">{tabTitles[activeTab] || 'Dashboard'}</h2>
        <span className="page-breadcrumb">Smart Battery AI / {activeTab}</span>
      </div>

      <div className="topbar-right">
        {/* Live Clock */}
        <div className="clock-pill">
          <Icon name="clock" size={14} color="#94a3b8" />
          <span>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>

        {/* User Selector */}
        <div className="user-selector-container">
          <label htmlFor="user-select" className="user-selector-label">
            <Icon name="user" size={14} color="#38bdf8" />
            User:
          </label>
          <select
            id="user-select"
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(Number(e.target.value))}
            className="user-select-dropdown"
          >
            {availableUsers.map((u) => (
              <option key={u.id} value={u.id}>
                User {u.id}: {u.name}
              </option>
            ))}
          </select>
        </div>

        {/* Backend Status Pill */}
        <div
          className={`backend-pill ${isHealthy ? 'healthy' : 'demo'}`}
          title={isHealthy ? 'Backend API connected on http://127.0.0.1:8000' : 'Operating in offline demo mode with realistic mock fixtures'}
        >
          <span className="status-dot" />
          <span>{isHealthy ? 'Backend Connected' : 'Demo Mode (Offline)'}</span>
        </div>

        {/* Refresh Button */}
        <button
          onClick={refreshUserData}
          className="icon-button"
          title="Refresh User Data"
        >
          <Icon name="refresh" size={16} />
        </button>
      </div>
    </header>
  );
}
