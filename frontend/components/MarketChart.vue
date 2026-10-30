<script setup>
import { computed } from 'vue'
import { Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement, LinearScale, PointElement, CategoryScale, Filler } from 'chart.js'
import { Chart } from 'vue-chartjs'

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, LinearScale, PointElement, CategoryScale, Filler)

const props = defineProps({ data: Array, faction: String })

const chartData = computed(() => {
  const isHorde = props.faction === 'Horde'
  return {
    labels: props.data.map(d => new Date(d.time).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit' })),
    datasets: [
      {
        type: 'bar',
        label: 'Volume',
        data: props.data.map(d => isHorde ? d.HordeVolume : d.AllianceVolume),
        backgroundColor: '#4b5563',
        yAxisID: 'y1',
        order: 2
      },
      {
        type: 'line',
        label: 'Price',
        data: props.data.map(d => isHorde ? d.HordePrice : d.AlliancePrice),
        borderColor: isHorde ? '#ef4444' : '#3b82f6',
        backgroundColor: isHorde ? '#ef4444' : '#3b82f6',
        borderWidth: 2,
        tension: 0.3,
        spanGaps: true,
        yAxisID: 'y',
        order: 1
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#e5e7eb' } }
  },
  scales: {
    x: { grid: { color: '#374151' }, ticks: { color: '#9ca3af', maxRotation: 45, minRotation: 45 } },
    y: { 
      type: 'linear',
      display: true,
      position: 'left',
      grid: { color: '#374151' }, 
      ticks: { color: '#9ca3af', callback: (v) => `${v}c` } 
    },
    y1: {
      type: 'linear',
      display: true,
      position: 'right',
      grid: { drawOnChartArea: false }, 
      ticks: { color: '#9ca3af' }
    }
  }
}
</script>

<template>
  <div class="h-72 w-full">
    <Chart type="bar" :data="chartData" :options="chartOptions" />
  </div>
</template>