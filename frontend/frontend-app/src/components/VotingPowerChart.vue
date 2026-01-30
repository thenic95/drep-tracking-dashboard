<template>
  <div class="voting-power-chart">
    <div v-if="loading" class="text-gray-500 text-center py-8">Loading chart data...</div>
    <div v-else-if="!chartData || chartData.labels.length === 0" class="text-gray-500 text-center py-8">
      No voting power history available.
    </div>
    <Line v-else :data="chartData" :options="chartOptions" />
  </div>
</template>

<script>
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

export default {
  name: 'VotingPowerChart',
  components: { Line },
  props: {
    snapshots: {
      type: Array,
      required: true,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    chartData() {
      if (!this.snapshots || this.snapshots.length === 0) return null

      // Sort by epoch ascending, take last 50
      const sorted = [...this.snapshots]
        .sort((a, b) => a.epoch - b.epoch)
        .slice(-50)

      return {
        labels: sorted.map(s => `Epoch ${s.epoch}`),
        datasets: [
          {
            label: 'Voting Power (ADA)',
            data: sorted.map(s => s.voting_power / 1_000_000),
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 6,
          }
        ]
      }
    },
    delegatorData() {
      if (!this.snapshots || this.snapshots.length === 0) return []
      return [...this.snapshots].sort((a, b) => a.epoch - b.epoch).slice(-50)
    },
    chartOptions() {
      const delegators = this.delegatorData
      return {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: true, position: 'top' },
          tooltip: {
            callbacks: {
              afterLabel: (context) => {
                const idx = context.dataIndex
                if (delegators[idx]) {
                  return `Delegators: ${delegators[idx].delegator_count}`
                }
                return ''
              }
            }
          }
        },
        scales: {
          x: { title: { display: true, text: 'Epoch' } },
          y: {
            title: { display: true, text: 'Voting Power (ADA)' },
            beginAtZero: false,
            ticks: {
              callback: (value) => value.toLocaleString()
            }
          }
        }
      }
    }
  }
}
</script>
