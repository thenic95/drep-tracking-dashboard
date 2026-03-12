<template>
  <div class="space-y-6">
    <div>
      <h1 class="page-title">Governance Actions</h1>
      <p class="text-gray-500">Track voting activity across governance actions</p>
    </div>

    <div class="card overflow-hidden">
      <GovernanceActionMatrix
        :governanceActions="governanceActions"
        :trackedDreps="trackedDreps"
        :loading="loading"
        :error="error"
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
    const [matrixRes, drepsRes] = await Promise.all([
      apiService.getVoteMatrix(20, 0),
      apiService.getTrackedDreps()
    ])
    governanceActions.value = matrixRes.data.governance_actions || []
    trackedDreps.value = drepsRes.data || []
  } catch (err) {
    error.value = 'Failed to load governance data.'
    console.error('Error fetching governance data:', err)
  } finally {
    loading.value = false
  }
})
</script>
