<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, Title, Tooltip, Legend, LineElement, LinearScale, PointElement, CategoryScale, Filler } from 'chart.js'

ChartJS.register(Title, Tooltip, Legend, LineElement, LinearScale, PointElement, CategoryScale, Filler)

const props = defineProps({ data: Array, faction: String })

const chartData = computed(() => {
  return {
    labels: props.data.map(d => {
      const gold = Math.floor(d.price / 10000)
      const silver = Math.floor((d.price % 10000) / 100)
      const c = d.price % 100
      let out = []
      if (gold > 0) out.push(`${gold}g`)
      if (silver > 0) out.push(`${silver}s`)
      if (c > 0 && gold === 0) out.push(`${c}c`)
      return out.join(' ')
    }),
    datasets: [
      {
        label: 'Total Units Available',
        data: props.data.map(d => d.cumulative_units),
        borderColor: props.faction === 'Horde' ? '#ef4444' : '#3b82f6',
        backgroundColor: props.faction === 'Horde' ? '#ef444433' : '#3b82f633',
        fill: true,
        step: 'after', // Creates a stair-step effect
        pointRadius: 0,
        borderWidth: 2
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        title: (context) => `Price: ${context[0].label}`,
        label: (context) => `Total Supply: ${context.raw} units`
      }
    }
  },
  scales: {
    x: { grid: { color: '#374151' }, ticks: { color: '#9ca3af' } },
    y: { grid: { color: '#374151' }, ticks: { color: '#9ca3af' }, beginAtZero: true }
  }
}
</script>

<template>
  <div class="h-64 w-full">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>