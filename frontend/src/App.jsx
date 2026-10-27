import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import DashboardPage from './pages/DashboardPage';
import RealDataPage from './pages/RealDataPage';
import ChargingHistoryPage from './pages/ChargingHistoryPage';
import PredictionPage from './pages/PredictionPage';
import RecommendationPage from './pages/RecommendationPage';
import AnalyticsPage from './pages/AnalyticsPage';
import ModelEvaluationPage from './pages/ModelEvaluationPage';
import SystemStatusPage from './pages/SystemStatusPage';
import { Icon } from './components/Icons';

function MainLayout() {
  const { activeTab, notification } = useApp();

  const renderActivePage = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage />;
      case 'realdata':
        return <RealDataPage />;
      case 'history':
        return <ChargingHistoryPage />;
      case 'prediction':
        return <PredictionPage />;
      case 'recommendation':
        return <RecommendationPage />;
      case 'analytics':
        return <AnalyticsPage />;
      case 'evaluation':
        return <ModelEvaluationPage />;
      case 'status':
        return <SystemStatusPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="app-layout">
      {/* Toast Notification */}
      {notification && (
        <div className={`toast-notification ${notification.type}`}>
          <Icon
            name={notification.type === 'error' ? 'alert' : 'check'}
            size={16}
            color={notification.type === 'error' ? '#ef4444' : '#10b981'}
          />
          <span>{notification.message}</span>
        </div>
      )}

      {/* Left Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <TopBar />
        <main className="content-area">
          {renderActivePage()}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <MainLayout />
    </AppProvider>
  );
}
