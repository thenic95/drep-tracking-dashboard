<template>
  <div class="drep-profile max-w-6xl mx-auto px-4 py-6">
    <router-link to="/dreps" class="text-blue-500 hover:underline text-sm mb-4 inline-block">
      &larr; Back to DReps
    </router-link>

    <div v-if="loading" class="text-gray-500 text-center py-12">Loading DRep profile...</div>
    <div v-else-if="error" class="text-red-500 text-center py-12">{{ error }}</div>
    <div v-else-if="drep">
      <!-- Profile Header -->
      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <div class="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-800">{{ drep.name || 'Unnamed DRep' }}</h1>
            <div class="flex items-center gap-2 mt-2">
              <span class="font-mono text-sm text-gray-500" :title="drep.drep_id">
                {{ drep.drep_id.substring(0, 24) }}...
              </span>
              <button
                @click="copyDrepId"
                class="text-blue-500 hover:text-blue-700 text-xs border border-blue-300 rounded px-2 py-0.5"
              >
                {{ copied ? 'Copied!' : 'Copy' }}
              </button>
            </div>
            <div class="mt-3 flex flex-wrap gap-3 text-sm text-gray-600">
              <span>
                <strong>Status:</strong>
                <span class="px-2 py-0.5 text-xs rounded-full ml-1" :class="getStatusClass(drep.activity_status)">
                  {{ drep.activity_status || 'Unknown' }}
                </span>
              </span>
              <span v-if="drep.registration_epoch !== null">
                <strong>Reg. Epoch:</strong> {{ drep.registration_epoch }}
              </span>
              <span v-if="drep.registration_date">
                <strong>Reg. Date:</strong> {{ formatDate(drep.registration_date) }}
              </span>
              <span v-if="drep.metadata_status">
                <strong>Metadata:</strong> {{ drep.metadata_status }}
              </span>
            </div>
            <div v-if="drep.metadata_url" class="mt-2 text-sm">
              <a :href="drep.metadata_url" target="_blank" rel="noopener noreferrer" class="text-blue-500 hover:underline">
                Metadata URL
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- Stat Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-white rounded-lg shadow p-5 text-center">
          <div class="text-3xl font-bold text-blue-600">{{ totalVotes }}</div>
          <div class="text-sm text-gray-500 mt-1">Total Votes</div>
        </div>
        <div class="bg-white rounded-lg shadow p-5 text-center">
          <div class="text-3xl font-bold text-green-600">
            {{ drep.delegator_count !== null ? drep.delegator_count.toLocaleString() : 'N/A' }}
          </div>
          <div class="text-sm text-gray-500 mt-1">Total Delegators</div>
        </div>
        <div class="bg-white rounded-lg shadow p-5 text-center">
          <div class="text-3xl font-bold text-purple-600">
            {{ drep.total_voting_power !== null ? (drep.total_voting_power / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A' }}
          </div>
          <div class="text-sm text-gray-500 mt-1">Voting Power (ADA)</div>
        </div>
      </div>

      <!-- Voting Power Chart -->
      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Voting Power Over Time</h2>
        <VotingPowerChart :snapshots="votingPowerSnapshots" :loading="loadingHistory" />
      </div>

      <!-- Vote History -->
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Vote History</h2>
        <VoteHistoryTable :votes="votes" />
      </div>
    </div>
  </div>
</template>

<script>
import apiService from '@/services/apiService'
import VotingPowerChart from '@/components/VotingPowerChart.vue'
import VoteHistoryTable from '@/components/VoteHistoryTable.vue'

export default {
  name: 'DRepProfileView',
  components: { VotingPowerChart, VoteHistoryTable },
  data() {
    return {
      drep: null,
      votes: [],
      votingPowerSnapshots: [],
      loading: true,
      loadingHistory: true,
      error: null,
      copied: false
    }
  },
  computed: {
    totalVotes() {
      return this.votes.length
    }
  },
  async created() {
    const drepId = this.$route.params.drepId
    await this.fetchProfile(drepId)
  },
  methods: {
    async fetchProfile(drepId) {
      this.loading = true
      this.error = null
      try {
        const [profileRes, votesRes] = await Promise.all([
          apiService.getDRepById(drepId),
          apiService.getVotesByDrep(drepId, 1000, 0)
        ])
        this.drep = profileRes.data
        this.votes = votesRes.data
      } catch (e) {
        this.error = e.response?.status === 404
          ? 'DRep not found.'
          : 'Failed to load DRep profile.'
      } finally {
        this.loading = false
      }

      // Fetch voting power history separately (non-blocking)
      this.loadingHistory = true
      try {
        const historyRes = await apiService.getVotingPowerHistory(drepId, 100, 0)
        this.votingPowerSnapshots = historyRes.data
      } catch (e) {
        this.votingPowerSnapshots = []
      } finally {
        this.loadingHistory = false
      }
    },
    formatDate(dateString) {
      if (!dateString) return 'N/A'
      try {
        return new Date(dateString).toLocaleDateString(undefined, {
          year: 'numeric', month: 'short', day: 'numeric'
        })
      } catch {
        return dateString
      }
    },
    getStatusClass(status) {
      switch (status) {
        case 'Active': return 'bg-green-100 text-green-700'
        case 'Inactive': return 'bg-gray-100 text-gray-600'
        default: return 'bg-yellow-100 text-yellow-700'
      }
    },
    async copyDrepId() {
      try {
        await navigator.clipboard.writeText(this.drep.drep_id)
        this.copied = true
        setTimeout(() => { this.copied = false }, 2000)
      } catch {
        // Fallback: do nothing
      }
    }
  }
}
</script>
