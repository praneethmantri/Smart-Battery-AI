import React from 'react';
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

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function ChargingChart() {
  const data = {
    labels: ['23:00', '00:00', '01:00', '03:00', '05:00', '06:30', '07:30'],
    datasets: [
      {
        label: 'Optimized Battery SoC (%)',
        data: [20, 75, 80, 80, 80, 80, 100],
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        fill: true,
        tension: 0.3,
      },
      {
        label: 'Standard Uncontrolled Charging',
        data: [20, 80, 100, 100, 100, 100, 100],
        borderColor: '#ef4444',
        borderDash: [5, 5],
        fill: false,
        tension: 0.3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#cbd5e1' },
      },
      title: {
        display: true,
        text: 'Predicted Charging Trajectory vs Uncontrolled Charging',
        color: '#f1f5f9',
      },
    },
    scales: {
      y: {
        min: 0,
        max: 100,
        ticks: { color: '#94a3b8' },
        grid: { color: '#334155' },
      },
      x: {
        ticks: { color: '#94a3b8' },
        grid: { color: '#334155' },
      },
    },
  };

  return (
    <div className="card" style={{ height: '350px' }}>
      <Line data={data} options={options} />
    </div>
  );
}
