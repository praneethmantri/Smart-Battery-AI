import React from 'react';
import { useApp } from '../context/AppContext';
import { Icon } from './Icons';

export default function Sidebar() {
  const { activeTab, setActiveTab } = useApp();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', badge: null },
    { id: 'realdata', label: 'Real Data', icon: 'zap', badge: 'LIVE' },
    { id: 'history', label: 'Charging History', icon: 'history', badge: null },
    { id: 'prediction', label: 'AI Prediction', icon: 'prediction', badge: 'ML' },
    { id: 'recommendation', label: 'Smart Recommendation', icon: 'recommendation', badge: 'REC' },
    { id: 'analytics', label: 'Analytics', icon: 'analytics', badge: null },
    { id: 'evaluation', label: 'Model Evaluation', icon: 'evaluation', badge: 'R&D' },
    { id: 'status', label: 'System Status', icon: 'status', badge: null },
  ];

  return (
    <aside className="sidebar">
      {/* Brand / Logo */}
      <div className="sidebar-brand">
        <div className="brand-icon">
          <Icon name="zap" size={20} color="#38bdf8" />
        </div>
        <div className="brand-text">
          <h1 className="brand-title">Smart Battery AI</h1>
          <span className="brand-subtitle">Personalized Charging</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <div className="nav-icon">
                <Icon name={item.icon} size={18} color={isActive ? '#38bdf8' : '#94a3b8'} />
              </div>
              <span className="nav-label">{item.label}</span>
              {item.badge && (
                <span className={`nav-badge ${isActive ? 'active' : ''}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Research Badge Footer */}
      <div className="sidebar-footer">
        <div className="rd-badge">
          <div className="rd-indicator" />
          <div>
            <div className="rd-title">College R&D Project</div>
            <div className="rd-dept">AI-Driven Degradation Mitigation</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
