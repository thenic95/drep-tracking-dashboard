<template>
  <div class="space-y-6">
    <div>
      <h1 class="page-title">Governance Actions</h1>
      <p class="text-gray-500">Track voting activity across governance actions</p>
    </div>

    <div class="card overflow-hidden">
      <div v-if="loading" class="text-center py-12">
        <div class="inline-flex items-center space-x-2 text-gray-500">
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Loading governance data...</span>
        </div>
      </div>
      <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
        {{ error }}
      </div>
      <GovernanceActionMatrix
        v-else
        :governanceActions="governanceActions"
        :trackedDreps="trackedDreps"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import apiService from '@/services/apiService'
import GovernanceActionMatrix from '@/components/GovernanceActionMatrix.vue'

const governanceActions = ref([])
const trackedDreps = ref([])
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const [gasRes, drepsRes] = await Promise.all([
      apiService.getGovernanceActions(20, 0),
      apiService.getTrackedDreps()
    ])
    governanceActions.value = gasRes.data || []
    trackedDreps.value = drepsRes.data || []
  } catch (err) {
    error.value = 'Failed to load governance data.'
    console.error('Error fetching governance data:', err)
  } finally {
    loading.value = false
  }
})
</script>
