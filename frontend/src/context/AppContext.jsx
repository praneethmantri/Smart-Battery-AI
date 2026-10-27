import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getHealthStatus,
  getUsers,
  getLatestBatteryReading,
  getUserPredictions,
  getUserRecommendations,
  getDeviceBattery,
} from '../services/api';
import { MOCK_USERS, MOCK_RECOMMENDATION_RESULT, MOCK_PREDICTION_RESULT } from '../data/mockData';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedUserId, setSelectedUserId] = useState(1);
  const [availableUsers, setAvailableUsers] = useState(MOCK_USERS);
  const [backendHealth, setBackendHealth] = useState({ status: 'checking...' });
  const [deviceBattery, setDeviceBattery] = useState({
    available: false,
    battery_percent: null,
    is_plugged_in: null,
    seconds_left: null,
    source: 'UNAVAILABLE',
  });
  const [telemetry, setTelemetry] = useState({
    battery_percent: 50,
    voltage: 3.98,
    current: 1.45,
    temperature: 32.5,
    is_charging: false,
    is_live_device: false,
    source: 'STORED',
  });
  const [latestPrediction, setLatestPrediction] = useState(MOCK_PREDICTION_RESULT);
  const [latestRecommendation, setLatestRecommendation] = useState(MOCK_RECOMMENDATION_RESULT);
  const [notification, setNotification] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Clock ticker
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const showNotification = useCallback((message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
    setTimeout(() => setNotification(null), 4000);
  }, []);

  // Fetch real physical host battery telemetry from operating system
  const fetchDeviceBattery = useCallback(async () => {
    try {
      const batt = await getDeviceBattery();
      if (batt && batt.available && batt.battery_percent !== null) {
        setDeviceBattery(batt);
        setTelemetry((prev) => ({
          ...prev,
          battery_percent: batt.battery_percent,
          is_charging: batt.is_plugged_in !== null ? batt.is_plugged_in : prev.is_charging,
          is_live_device: true,
          source: batt.source || 'WINDOWS_SYSTEM',
          seconds_left: batt.seconds_left,
        }));
        return batt;
      } else {
        setDeviceBattery((prev) => ({ ...prev, available: false }));
      }
    } catch (err) {
      console.warn('Could not query host device battery sensor:', err);
    }
    return null;
  }, []);

  // Periodic 30-second auto-refresh and health heartbeat
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const health = await getHealthStatus();
        setBackendHealth(health);
      } catch (err) {
        setBackendHealth({ status: 'offline (demo mode)' });
      }
      await fetchDeviceBattery();
    };

    checkStatus();
    getUsers().then((users) => {
      if (users && users.length > 0) setAvailableUsers(users);
    }).catch(() => {});

    const interval = setInterval(checkStatus, 30000); // 30 seconds heartbeat
    return () => clearInterval(interval);
  }, [fetchDeviceBattery]);

  // Refresh user-specific data whenever selectedUserId changes or on manual refresh
  const refreshUserData = useCallback(async () => {
    try {
      // Re-check backend health & hardware battery
      try {
        const health = await getHealthStatus();
        setBackendHealth(health);
      } catch (e) {
        setBackendHealth({ status: 'offline (demo mode)' });
      }

      await fetchDeviceBattery();

      const [reading, preds, recs] = await Promise.allSettled([
        getLatestBatteryReading(selectedUserId),
        getUserPredictions(selectedUserId, 1),
        getUserRecommendations(selectedUserId, 1),
      ]);

      if (reading.status === 'fulfilled' && reading.value) {
        setTelemetry((prev) => ({
          ...prev,
          // Only use stored DB percent if real hardware battery is NOT available
          battery_percent: prev.is_live_device ? prev.battery_percent : (reading.value.battery_percent ?? prev.battery_percent),
          voltage: reading.value.voltage ?? prev.voltage,
          current: reading.value.current ?? prev.current,
          temperature: reading.value.temperature ?? prev.temperature,
        }));
      }

      if (preds.status === 'fulfilled' && preds.value && preds.value.length > 0) {
        setLatestPrediction(preds.value[0]);
      }

      if (recs.status === 'fulfilled' && recs.value && recs.value.length > 0) {
        const rec = recs.value[0];
        if (rec.mode) {
          setLatestRecommendation((prev) => ({
            ...prev,
            user_id: selectedUserId,
            recommendation: {
              ...prev.recommendation,
              mode: rec.mode,
              target_soc: rec.target_soc,
              message: rec.recommendation_message || prev.recommendation.message,
            },
          }));
        }
      }
    } catch (err) {
      console.warn('Error refreshing user data:', err);
    }
  }, [selectedUserId, fetchDeviceBattery]);

  useEffect(() => {
    refreshUserData();
  }, [refreshUserData]);

  const currentUser = availableUsers.find((u) => u.id === Number(selectedUserId)) || availableUsers[0] || {
    id: selectedUserId,
    name: `User ${selectedUserId}`,
    email: `user${selectedUserId}@campus.edu`,
    profile: 'REGULAR_OVERNIGHT',
  };

  const value = {
    activeTab,
    setActiveTab,
    selectedUserId,
    setSelectedUserId,
    availableUsers,
    currentUser,
    backendHealth,
    setBackendHealth,
    deviceBattery,
    fetchDeviceBattery,
    telemetry,
    setTelemetry,
    latestPrediction,
    setLatestPrediction,
    latestRecommendation,
    setLatestRecommendation,
    notification,
    showNotification,
    refreshUserData,
    currentTime,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
}
