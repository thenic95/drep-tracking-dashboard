<template>
  <div class="space-y-8">
    <!-- Page Header -->
    <div>
      <h1 class="page-title">Dashboard Overview</h1>
      <p class="text-gray-500">Track and monitor Cardano DRep governance activity</p>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="Tracked DReps"
        :value="stats.trackedDreps"
        icon="users"
        color="blue"
      />
      <StatCard
        title="Total Voting Power"
        :value="formatVotingPower(stats.totalVotingPower)"
        icon="chart"
        color="green"
        suffix="ADA"
      />
      <StatCard
        title="Active DReps"
        :value="stats.activeDreps"
        icon="check"
        color="emerald"
      />
      <StatCard
        title="Recent Actions"
        :value="stats.recentActions"
        icon="document"
        color="purple"
      />
    </div>

    <!-- Quick Access Cards -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Recent Activity Card -->
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="section-title mb-0">Recent DRep Activity</h2>
          <router-link to="/dreps" class="text-primary text-sm hover:underline">
            View all
          </router-link>
        </div>
        <div v-if="loading" class="text-gray-500 text-center py-8">Loading...</div>
        <div v-else-if="recentDreps.length === 0" class="text-gray-500 text-center py-8">
          No DReps tracked yet
        </div>
        <ul v-else class="divide-y divide-gray-100">
          <li v-for="drep in recentDreps" :key="drep.drep_id" class="py-3">
            <div class="flex justify-between items-center">
              <div>
                <p class="font-medium text-gray-800">{{ getDrepDisplayName(drep) }}</p>
                <p class="text-sm text-gray-500 font-mono">{{ drep.drep_id.substring(0, 20) }}...</p>
              </div>
              <span
                class="px-2 py-1 text-xs rounded-full"
                :class="getStatusClass(drep.activity_status)"
              >
                {{ drep.activity_status || 'Unknown' }}
              </span>
            </div>
          </li>
        </ul>
      </div>

      <!-- Recent Governance Actions Card -->
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="section-title mb-0">Recent Governance Actions</h2>
          <router-link to="/governance" class="text-primary text-sm hover:underline">
            View all
          </router-link>
        </div>
        <div v-if="loadingGAs" class="text-gray-500 text-center py-8">Loading...</div>
        <div v-else-if="recentGAs.length === 0" class="text-gray-500 text-center py-8">
          No governance actions found
        </div>
        <ul v-else class="divide-y divide-gray-100">
          <li v-for="ga in recentGAs" :key="ga.ga_id" class="py-3">
            <div>
              <p class="font-medium text-gray-800">{{ ga.title || ga.ga_id.substring(0, 25) + '...' }}</p>
              <div class="flex items-center space-x-3 mt-1">
                <span class="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded">
                  {{ ga.type }}
                </span>
                <span class="text-sm text-gray-500">
                  Epoch {{ ga.submission_epoch }}
                </span>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import apiService from '@/services/apiService'
import StatCard from '@/components/ui/StatCard.vue'

const trackedDreps = ref([])
const governanceActions = ref([])
const loading = ref(true)
const loadingGAs = ref(true)

const stats = computed(() => ({
  trackedDreps: trackedDreps.value.length,
  totalVotingPower: trackedDreps.value.reduce((sum, d) => sum + (d.total_voting_power || 0), 0),
  activeDreps: trackedDreps.value.filter(d => d.activity_status === 'Active').length,
  recentActions: governanceActions.value.length
}))

const recentDreps = computed(() => trackedDreps.value.slice(0, 5))
const recentGAs = computed(() => governanceActions.value.slice(0, 5))

const formatVotingPower = (lovelace) => {
  const ada = lovelace / 1000000
  if (ada >= 1000000) return (ada / 1000000).toFixed(2) + 'M'
  if (ada >= 1000) return (ada / 1000).toFixed(1) + 'K'
  return ada.toLocaleString()
}

const getDrepDisplayName = (drep) => {
  if (drep.drep_id === 'drep1yfjez5zup0gystdvc933w2mn8k64hcy3krvc2namluwjxdcfhm8wd') return 'Sidan Lab'
  if (drep.drep_id === 'drep1yv4uesaj92wk8ljlsh4p7jzndnzrflchaz5fzug3zxg4naqkpeas3') return 'MESH'
  return drep.name || 'Unknown DRep'
}

const getStatusClass = (status) => {
  switch (status) {
    case 'Active': return 'bg-green-100 text-green-700'
    case 'Inactive': return 'bg-gray-100 text-gray-600'
    default: return 'bg-yellow-100 text-yellow-700'
  }
}

onMounted(async () => {
  try {
    const [drepsRes, gasRes] = await Promise.all([
      apiService.getTrackedDreps(),
      apiService.getGovernanceActions(10, 0)
    ])
    trackedDreps.value = drepsRes.data || []
    governanceActions.value = gasRes.data || []
  } catch (err) {
    console.error('Error loading dashboard data:', err)
  } finally {
    loading.value = false
    loadingGAs.value = false
  }
})
</script>
